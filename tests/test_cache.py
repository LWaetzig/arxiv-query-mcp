"""Tests for the two-tier cache (L1 in-memory + L2 diskcache)."""
import asyncio
import time

import diskcache
import pytest

from arxiv_query_mcp.cache import TwoTierCache
from arxiv_query_mcp.config import Config

_PAPER = {"id": "2303.08774", "title": "Test Paper"}


@pytest.fixture
def cache_cfg(tmp_path):
    """Return a Config with caching enabled and short TTLs for fast tests."""
    return Config(
        cache_dir=str(tmp_path / "cache"),
        cache_enabled=True,
        l1_ttl=60.0,
        l2_ttl=120.0,
        negative_ttl=5.0,
        l1_maxsize=10,
    )


@pytest.fixture
def dc(cache_cfg):
    """Return an open diskcache.Cache for the test config directory."""
    d = diskcache.Cache(cache_cfg.cache_dir)
    yield d
    d.close()


@pytest.fixture
def cache(cache_cfg, dc):
    """Return a TwoTierCache backed by the test diskcache."""
    c = TwoTierCache(cache_cfg, dc)
    yield c
    c.close()


# ---- L1 hit ----------------------------------------------------------------


async def test_l1_hit(cache):
    """Second call for the same key is served from L1 (no additional fetch)."""
    calls = 0

    async def fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        return (1, [_PAPER])

    key = ("api", (("id_list", "2303.08774"),))
    r1 = await cache.get_or_fetch(key, fetch)
    r2 = await cache.get_or_fetch(key, fetch)

    assert r1 == r2 == (1, [_PAPER])
    assert calls == 1


# ---- L2 promotion ----------------------------------------------------------


async def test_l2_promotion(cache):
    """After L1 is cleared a second call is served from L2 without re-fetching."""
    calls = 0

    async def fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        return (1, [_PAPER])

    key = ("api", (("id_list", "l2promo"),))
    await cache.get_or_fetch(key, fetch)

    # Wipe L1 to force L2 lookup on next call
    cache._l1.clear()

    r2 = await cache.get_or_fetch(key, fetch)
    assert r2 == (1, [_PAPER])
    assert calls == 1  # L2 served the request, no second fetch


# ---- single-flight ---------------------------------------------------------


async def test_single_flight(cache):
    """Two concurrent requests for the same key trigger exactly one fetch."""
    calls = 0

    async def slow_fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return (1, [_PAPER])

    key = ("api", (("id_list", "concurrent"),))
    r1, r2 = await asyncio.gather(
        cache.get_or_fetch(key, slow_fetch),
        cache.get_or_fetch(key, slow_fetch),
    )

    assert r1 == r2 == (1, [_PAPER])
    assert calls == 1


# ---- TTL expiry ------------------------------------------------------------


async def test_l1_ttl_expiry(cache_cfg, dc, tmp_path):
    """An L1 entry whose TTL has elapsed is not returned."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache2"),
        cache_enabled=True,
        l1_ttl=0.05,  # 50 ms
        l2_ttl=60.0,
        negative_ttl=0.05,
        l1_maxsize=10,
    )
    d2 = diskcache.Cache(cfg.cache_dir)
    c2 = TwoTierCache(cfg, d2)

    calls = 0

    async def fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        return (1, [_PAPER])

    key = ("api", (("id_list", "ttl_test"),))
    await c2.get_or_fetch(key, fetch)

    # Expire L1 by moving its entry's timestamp into the past
    hkey = TwoTierCache._make_key(key)
    _, value = c2._l1[hkey]
    c2._l1[hkey] = (time.monotonic() - 1.0, value)  # already expired

    # Second call: L1 miss → L2 hit → promoted back to L1; still only 1 fetch
    r2 = await c2.get_or_fetch(key, fetch)
    assert r2 == (1, [_PAPER])
    assert calls == 1  # L2 still valid, no re-fetch

    d2.close()


# ---- negative caching ------------------------------------------------------


async def test_negative_caching(cache):
    """Empty-result tuples are cached and prevent a second fetch."""
    calls = 0

    async def fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        return (0, [])

    key = ("api", (("id_list", "missing"),))
    r1 = await cache.get_or_fetch(key, fetch)
    r2 = await cache.get_or_fetch(key, fetch)

    assert r1 == r2 == (0, [])
    assert calls == 1


# ---- cache disabled --------------------------------------------------------


async def test_cache_disabled(tmp_path):
    """When cache_enabled=False every call goes directly to the fetch factory."""
    cfg = Config(
        cache_dir=str(tmp_path / "nocache"),
        cache_enabled=False,
    )
    dc = diskcache.Cache(cfg.cache_dir)
    c = TwoTierCache(cfg, dc)

    calls = 0

    async def fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        return (1, [_PAPER])

    key = ("api", (("id_list", "x"),))
    await c.get_or_fetch(key, fetch)
    await c.get_or_fetch(key, fetch)

    assert calls == 2  # no caching → always fetches

    dc.close()


# ---- single-flight failure modes -------------------------------------------


async def test_single_flight_error_reaches_all_waiters_and_is_not_cached(cache):
    """A failing fetch raises for every waiter and nothing is stored."""
    calls = 0

    async def failing_fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        raise RuntimeError("boom")

    key = ("api", (("id_list", "fails"),))
    results = await asyncio.gather(
        cache.get_or_fetch(key, failing_fetch),
        cache.get_or_fetch(key, failing_fetch),
        return_exceptions=True,
    )

    assert all(isinstance(r, RuntimeError) for r in results)
    assert calls == 1

    async def ok_fetch() -> tuple[int, list]:
        return (1, [_PAPER])

    assert await cache.get_or_fetch(key, ok_fetch) == (1, [_PAPER])


async def test_cancelled_leader_does_not_hang_waiters(cache):
    """If the leader is cancelled a waiting caller takes over and gets a result."""
    started = asyncio.Event()

    async def slow_fetch() -> tuple[int, list]:
        started.set()
        await asyncio.sleep(10)
        return (1, [_PAPER])

    async def fast_fetch() -> tuple[int, list]:
        return (2, [_PAPER])

    key = ("api", (("id_list", "cancelled"),))
    leader = asyncio.create_task(cache.get_or_fetch(key, slow_fetch))
    await started.wait()
    waiter = asyncio.create_task(cache.get_or_fetch(key, fast_fetch))
    await asyncio.sleep(0.01)  # let the waiter attach to the in-flight future

    leader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await leader

    assert await asyncio.wait_for(waiter, timeout=2) == (2, [_PAPER])
    assert cache._inflight == {}


# ---- L2 expiry -------------------------------------------------------------


async def test_l2_ttl_expiry(tmp_path):
    """Once the L2 TTL has elapsed the value is fetched again."""
    cfg = Config(
        cache_dir=str(tmp_path / "l2ttl"),
        cache_enabled=True,
        l1_ttl=0.05,
        l2_ttl=0.1,
        negative_ttl=0.1,
        l1_maxsize=10,
    )
    d = diskcache.Cache(cfg.cache_dir)
    c = TwoTierCache(cfg, d)
    calls = 0

    async def fetch() -> tuple[int, list]:
        nonlocal calls
        calls += 1
        return (1, [_PAPER])

    key = ("api", (("id_list", "l2expiry"),))
    await c.get_or_fetch(key, fetch)
    await asyncio.sleep(0.25)
    await c.get_or_fetch(key, fetch)

    assert calls == 2
    d.close()


# ---- LRU eviction ----------------------------------------------------------


async def test_l1_lru_eviction(cache):
    """L1 never grows beyond l1_maxsize."""

    async def fetch() -> tuple[int, list]:
        return (1, [_PAPER])

    for i in range(25):
        await cache.get_or_fetch(("api", (("id_list", str(i)),)), fetch)

    assert len(cache._l1) == 10
