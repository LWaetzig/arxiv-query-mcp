"""Two-tier cache (L1 in-memory + L2 diskcache) for arXiv API results."""
from __future__ import annotations

import asyncio
import hashlib
import pickle
import time
from collections import OrderedDict
from typing import Any, Callable, Coroutine

import diskcache

from .config import Config


class _LeaderCancelled(Exception):
    """Raised to waiters when the single-flight leader was cancelled.

    Waiters catch this and retry on their own instead of inheriting the
    leader's cancellation.
    """


class TwoTierCache:
    """Two-tier cache with an in-memory L1 and a shared disk-backed L2.

    L1 is a size-bounded ``OrderedDict`` used as an LRU cache with a TTL.
    L2 is a ``diskcache.Cache`` (SQLite-backed) that can be shared across
    multiple processes via the filesystem.

    Concurrent in-process requests for the same key are coalesced via
    single-flight: only one underlying fetch runs and all waiters share the
    result via an ``asyncio.Future``.

    Args:
        cfg: Server configuration providing cache settings.
        dc: Open ``diskcache.Cache`` instance used as the L2 store.  The
            caller is responsible for closing it.
    """

    def __init__(self, cfg: Config, dc: diskcache.Cache) -> None:
        self._cfg = cfg
        self._l1: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._l2 = dc
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(key: tuple[Any, ...]) -> str:
        """Produce a stable hex-digest key from an arbitrary hashable tuple.

        Args:
            key: A tuple of hashable values (e.g. cache-key components).

        Returns:
            A 64-character hex string (SHA-256 digest).
        """
        raw = pickle.dumps(key, protocol=5)
        return hashlib.sha256(raw).hexdigest()

    def _l1_get(self, hkey: str) -> tuple[bool, Any]:
        """Return ``(hit, value)`` from L1, evicting the entry if expired.

        Args:
            hkey: Hex-digest cache key.

        Returns:
            A tuple where the first element is ``True`` on a cache hit.
        """
        entry = self._l1.get(hkey)
        if entry is None:
            return False, None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._l1[hkey]
            return False, None
        self._l1.move_to_end(hkey)
        return True, value

    def _l1_set(self, hkey: str, value: Any, ttl: float) -> None:
        """Store *value* in L1 with *ttl*, evicting the LRU entry when full.

        Args:
            hkey: Hex-digest cache key.
            value: The value to store.
            ttl: Seconds until the entry expires (measured from now).
        """
        self._l1[hkey] = (time.monotonic() + ttl, value)
        self._l1.move_to_end(hkey)
        while len(self._l1) > self._cfg.l1_maxsize:
            self._l1.popitem(last=False)

    def _choose_ttls(self, result: Any) -> tuple[float, float]:
        """Return ``(l1_ttl, l2_ttl)`` appropriate for *result*.

        Empty API results (``(0, [])`` or ``(_, [])`` tuples with an empty
        paper list) receive the shorter :attr:`~Config.negative_ttl` so that
        a transient arXiv miss does not get cached for hours.

        Args:
            result: The value returned by the fetch factory.

        Returns:
            A ``(l1_ttl, l2_ttl)`` pair in seconds.
        """
        if isinstance(result, tuple) and len(result) == 2:
            _, second = result
            if isinstance(second, list) and not second:
                return self._cfg.negative_ttl, self._cfg.negative_ttl
        if result is None or result == "":
            return self._cfg.negative_ttl, self._cfg.negative_ttl
        return self._cfg.l1_ttl, self._cfg.l2_ttl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_fetch(
        self,
        key: tuple[Any, ...],
        fetch_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Return a cached value or delegate to *fetch_factory*.

        Look-up order: L1 hit → return; L2 hit → promote to L1 → return;
        miss → single-flight fetch → store L1 + L2 → return.

        When :attr:`~Config.cache_enabled` is ``False`` this method is a
        transparent pass-through: it always calls *fetch_factory* and never
        reads or writes any cache.

        Concurrent calls with identical *key* values are coalesced: the first
        caller runs *fetch_factory*, while subsequent callers await the same
        ``asyncio.Future``.

        Args:
            key: Hashable tuple that identifies the request (e.g.
                ``("api", tuple(sorted(params.items())))``.
            fetch_factory: Zero-argument callable that returns a coroutine
                performing the actual fetch.  Called at most once per key
                during the single-flight window.

        Returns:
            The cached or freshly fetched value.

        Raises:
            Exception: Any exception raised by *fetch_factory* is propagated
                to all waiters and is not stored in the cache.
        """
        if not self._cfg.cache_enabled:
            return await fetch_factory()

        hkey = self._make_key(key)

        # L1 check
        hit, value = self._l1_get(hkey)
        if hit:
            return value

        # L2 check (SQLite I/O runs in a thread to keep the event loop free)
        l2_value = await asyncio.to_thread(self._l2.get, hkey, None)
        if l2_value is not None:
            l1_ttl, _ = self._choose_ttls(l2_value)
            self._l1_set(hkey, l2_value, l1_ttl)
            return l2_value

        # Single-flight: if already inflight await the existing Future
        inflight = self._inflight.get(hkey)
        if inflight is not None:
            try:
                return await asyncio.shield(inflight)
            except _LeaderCancelled:
                # The leader was cancelled; take over with our own fetch.
                return await self.get_or_fetch(key, fetch_factory)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._inflight[hkey] = future

        try:
            result = await fetch_factory()
            l1_ttl, l2_ttl = self._choose_ttls(result)
            self._l1_set(hkey, result, l1_ttl)
            await asyncio.to_thread(self._l2.set, hkey, result, l2_ttl)
            future.set_result(result)
            return result
        except BaseException as exc:
            # Always resolve the future, including on cancellation, so that
            # waiters never hang.
            if not future.done():
                if isinstance(exc, Exception):
                    future.set_exception(exc)
                else:
                    future.set_exception(_LeaderCancelled())
                # Mark as retrieved: there may be no waiters.
                future.exception()
            raise
        finally:
            self._inflight.pop(hkey, None)

    def close(self) -> None:
        """No-op: the underlying diskcache is managed by the caller."""
