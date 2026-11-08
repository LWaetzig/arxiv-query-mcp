"""Cross-process rate limiter and resilient HTTP getter with tenacity retry."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import diskcache
import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import Config

_RATE_TS_KEY = "arxiv_mcp_last_request_ts"
_RATE_LOCK_KEY = "arxiv_mcp_rate_lock"


def _is_retryable(exc: BaseException) -> bool:
    """Return ``True`` if *exc* should trigger a retry.

    Retries on transient network issues and server-side throttling:

    - :class:`httpx.TimeoutException` — request timed out.
    - :class:`httpx.TransportError` — low-level transport failure.
    - :class:`httpx.HTTPStatusError` with status 429 / 500 / 502 / 503 / 504.

    Args:
        exc: The exception to classify.

    Returns:
        ``True`` when *exc* is considered transient and a retry is warranted.
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


class RateLimiter:
    """Cross-process rate limiter backed by diskcache with in-process concurrency cap.

    The last-request timestamp is stored in a shared :class:`diskcache.Cache`,
    and a :class:`diskcache.Lock` guards the read-modify-write so that multiple
    processes coordinate without collisions.  The synchronous lock section runs
    in a thread via :func:`asyncio.to_thread` so the event loop is never blocked.

    An :class:`asyncio.Semaphore` additionally caps the number of simultaneous
    in-process outgoing HTTP connections.

    When :attr:`~Config.rate_limit_enabled` is ``False`` (e.g. in tests) the
    spacing sleep is skipped entirely; only the semaphore still applies.

    Args:
        cfg: Server configuration providing rate-limit and concurrency settings.
        dc: Open :class:`diskcache.Cache` used to store the shared timestamp and
            the distributed lock.  The caller is responsible for closing it.
    """

    def __init__(self, cfg: Config, dc: diskcache.Cache) -> None:
        self._cfg = cfg
        self._dc = dc
        self._semaphore = asyncio.Semaphore(cfg.max_concurrency)

    async def acquire(self) -> None:
        """Acquire the in-process slot and enforce the cross-process rate limit.

        This method must be awaited before every outgoing HTTP request.  Call
        :meth:`release` (ideally in a ``finally`` block) after the request
        completes.
        """
        await self._semaphore.acquire()
        try:
            if self._cfg.rate_limit_enabled and self._cfg.rate_limit_period > 0:
                await asyncio.to_thread(self._sync_rate_limit)
        except BaseException:
            # Don't leak the slot if the spacing wait fails or is cancelled.
            self._semaphore.release()
            raise

    def release(self) -> None:
        """Release the in-process concurrency slot."""
        self._semaphore.release()

    def _sync_rate_limit(self) -> None:
        """Enforce the cross-process spacing in a background thread.

        Acquires a :class:`diskcache.Lock`, reads the last-request timestamp,
        sleeps if needed, then updates the timestamp before releasing the lock.
        Running this in a thread ensures the asyncio event loop is never stalled.
        """
        period = self._cfg.rate_limit_period
        with diskcache.Lock(self._dc, _RATE_LOCK_KEY, expire=period + 10):
            now = time.time()
            last: float = self._dc.get(_RATE_TS_KEY, default=0.0)  # type: ignore[assignment]
            delay = period - (now - last)
            if delay > 0:
                time.sleep(delay)
            self._dc.set(_RATE_TS_KEY, time.time())


def _retry_after_seconds(exc: BaseException | None) -> float | None:
    """Return the ``Retry-After`` delay in seconds carried by *exc*, if any.

    Only the numeric-seconds form of the header is supported; HTTP-date values
    and unparsable values are ignored.

    Args:
        exc: The exception raised by the last attempt, or ``None``.

    Returns:
        The non-negative delay in seconds, or ``None`` when absent or invalid.
    """
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    raw = exc.response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        delay = float(raw)
    except ValueError:
        return None
    return delay if delay >= 0 else None


async def resilient_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    cfg: Config,
    limiter: RateLimiter,
) -> httpx.Response:
    """Perform a rate-limited, retrying HTTP GET request.

    The *limiter* slot is acquired before **every** attempt (including
    retries) and released as soon as the attempt finishes, so retries obey the
    same request spacing as first attempts and no slot is held during back-off.
    On retryable failures (see :func:`_is_retryable`) tenacity waits with
    exponential back-off + jitter and tries again up to
    :attr:`~Config.max_retries` times.  When the failed response carries a
    ``Retry-After`` header the wait is the larger of that value and the
    back-off interval, capped at :attr:`~Config.backoff_max`.

    The final exception (after all retries are exhausted) is re-raised so the
    caller's error handler (e.g. :func:`~arxiv_query_mcp.utils._handle_error`)
    can classify it.

    Args:
        client: Shared async HTTP client (managed by the server lifespan).
        url: Target URL.
        params: Optional query-string parameters forwarded to ``client.get``.
        cfg: Server configuration providing ``max_retries``, ``backoff_base``,
            and ``backoff_max``.
        limiter: :class:`RateLimiter` whose :meth:`~RateLimiter.acquire` is
            called before each HTTP attempt.

    Returns:
        The successful :class:`httpx.Response`.

    Raises:
        httpx.HTTPStatusError: When the final attempt returns a non-2xx status.
        httpx.TimeoutException: When the final attempt times out.
        httpx.TransportError: When the final attempt encounters a transport error.
    """
    backoff = wait_exponential_jitter(
        multiplier=cfg.backoff_base,
        max=cfg.backoff_max,
        jitter=1.0,
    )

    def _wait(state: RetryCallState) -> float:
        wait = backoff(state)
        outcome = state.outcome
        retry_after = _retry_after_seconds(
            outcome.exception() if outcome is not None else None
        )
        if retry_after is not None:
            wait = max(wait, min(retry_after, cfg.backoff_max))
        return wait

    last_resp: httpx.Response | None = None
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(_is_retryable),
        wait=_wait,
        stop=stop_after_attempt(cfg.max_retries),
        reraise=True,
    ):
        with attempt:
            await limiter.acquire()
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            finally:
                limiter.release()
            last_resp = resp

    # last_resp is always set when no exception is raised above.
    assert last_resp is not None
    return last_resp
