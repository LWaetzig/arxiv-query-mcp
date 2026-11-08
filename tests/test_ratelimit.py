"""Tests for the cross-process rate limiter and resilient_get."""
import time
from unittest.mock import AsyncMock, MagicMock

import diskcache
import httpx
import pytest

from arxiv_query_mcp.config import Config
from arxiv_query_mcp.ratelimit import RateLimiter, _is_retryable, resilient_get


# ---- fixtures --------------------------------------------------------------


@pytest.fixture
def rl_cfg(tmp_path):
    """Config with a short rate-limit period to keep tests fast."""
    return Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=True,
        rate_limit_period=0.1,
        max_concurrency=4,
        max_retries=3,
        backoff_base=0.01,
        backoff_max=0.05,
    )


@pytest.fixture
def dc(rl_cfg):
    """Open diskcache for the rate-limiter tests."""
    d = diskcache.Cache(rl_cfg.cache_dir)
    yield d
    d.close()


@pytest.fixture
def limiter(rl_cfg, dc):
    """RateLimiter instance backed by the test diskcache."""
    return RateLimiter(rl_cfg, dc)


# ---- _is_retryable ---------------------------------------------------------


def test_is_retryable_timeout():
    """TimeoutException is retryable."""
    assert _is_retryable(httpx.TimeoutException("timeout"))


def test_is_retryable_transport():
    """TransportError is retryable."""
    assert _is_retryable(httpx.TransportError("transport"))


def test_is_retryable_429():
    """HTTPStatusError with status 429 is retryable."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    exc = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp)
    assert _is_retryable(exc)


def test_is_retryable_404():
    """HTTPStatusError with status 404 is NOT retryable."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    exc = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_resp)
    assert not _is_retryable(exc)


def test_is_retryable_500():
    """HTTPStatusError with status 500 is retryable."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    exc = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_resp)
    assert _is_retryable(exc)


def test_is_retryable_value_error():
    """Generic exceptions are not retryable."""
    assert not _is_retryable(ValueError("oops"))


# ---- rate-limit spacing ----------------------------------------------------


async def test_rate_limit_spacing(rl_cfg, dc):
    """Two sequential acquire/release cycles are spaced at least period seconds apart."""
    lim = RateLimiter(rl_cfg, dc)

    t0 = time.monotonic()
    await lim.acquire()
    lim.release()

    await lim.acquire()
    lim.release()

    elapsed = time.monotonic() - t0
    # The second call must have waited for the period.  Allow a generous 80 % lower bound
    # to account for scheduling jitter in CI.
    assert elapsed >= rl_cfg.rate_limit_period * 0.8


async def test_rate_limit_disabled(tmp_path, dc):
    """When rate_limit_enabled=False there is no inter-request sleep."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=False,
        rate_limit_period=10.0,  # would be very slow if enforced
        max_concurrency=4,
    )
    lim = RateLimiter(cfg, dc)

    t0 = time.monotonic()
    await lim.acquire()
    lim.release()
    await lim.acquire()
    lim.release()

    assert time.monotonic() - t0 < 1.0  # well under the 10s period


# ---- resilient_get ---------------------------------------------------------


async def test_resilient_get_success(rl_cfg, dc):
    """A 200 response is returned on the first attempt."""
    lim = RateLimiter(rl_cfg, dc)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.raise_for_status.return_value = None

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=mock_resp)

    result = await resilient_get(client, "https://example.com", cfg=rl_cfg, limiter=lim)
    assert result is mock_resp
    assert client.get.call_count == 1


async def test_resilient_get_retries_429_then_succeeds(tmp_path):
    """resilient_get retries after a 429 and succeeds on the second attempt."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=False,
        max_retries=3,
        backoff_base=0.01,
        backoff_max=0.05,
    )
    dc = diskcache.Cache(cfg.cache_dir)
    lim = RateLimiter(cfg, dc)

    call_count = 0

    mock_429 = MagicMock(spec=httpx.Response)
    mock_429.status_code = 429
    mock_429.headers = {}
    mock_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=mock_429
    )

    mock_200 = MagicMock(spec=httpx.Response)
    mock_200.status_code = 200
    mock_200.headers = {}
    mock_200.raise_for_status.return_value = None

    async def mock_get(url: str, params: object = None) -> object:
        nonlocal call_count
        call_count += 1
        return mock_429 if call_count == 1 else mock_200

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = mock_get

    result = await resilient_get(client, "https://example.com", cfg=cfg, limiter=lim)
    assert result is mock_200
    assert call_count == 2

    dc.close()


async def test_resilient_get_exhausted_retries(tmp_path):
    """resilient_get re-raises after all retry attempts are exhausted."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=False,
        max_retries=2,
        backoff_base=0.01,
        backoff_max=0.05,
    )
    dc = diskcache.Cache(cfg.cache_dir)
    lim = RateLimiter(cfg, dc)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 503
    mock_resp.headers = {}
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=mock_resp
    )

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=mock_resp)

    with pytest.raises(httpx.HTTPStatusError):
        await resilient_get(client, "https://example.com", cfg=cfg, limiter=lim)

    assert client.get.call_count == 2  # exactly max_retries attempts

    dc.close()


async def test_resilient_get_retry_after_header(tmp_path):
    """Retry-After header on 429 is honoured (short sleep)."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=False,
        max_retries=3,
        backoff_base=0.01,
        backoff_max=0.05,
    )
    dc = diskcache.Cache(cfg.cache_dir)
    lim = RateLimiter(cfg, dc)

    call_count = 0

    mock_429 = MagicMock(spec=httpx.Response)
    mock_429.status_code = 429
    mock_429.headers = {"Retry-After": "0.05"}  # 50 ms
    mock_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=mock_429
    )

    mock_200 = MagicMock(spec=httpx.Response)
    mock_200.status_code = 200
    mock_200.headers = {}
    mock_200.raise_for_status.return_value = None

    async def mock_get(url: str, params: object = None) -> object:
        nonlocal call_count
        call_count += 1
        return mock_429 if call_count == 1 else mock_200

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = mock_get

    t0 = time.monotonic()
    result = await resilient_get(client, "https://example.com", cfg=cfg, limiter=lim)
    elapsed = time.monotonic() - t0

    assert result is mock_200
    assert elapsed >= 0.04  # Retry-After sleep was honoured

    dc.close()


# ---- per-attempt limiting and Retry-After parsing --------------------------


def _status_error(status: int, headers: dict[str, str] | None = None):
    """Build an HTTPStatusError whose response has *status* and *headers*."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.headers = headers or {}
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        str(status), request=MagicMock(), response=resp
    )
    return resp


def test_retry_after_seconds_parsing():
    """Numeric Retry-After values parse; missing, HTTP-date, negative are ignored."""
    from arxiv_query_mcp.ratelimit import _retry_after_seconds

    def exc(headers: dict[str, str]) -> httpx.HTTPStatusError:
        resp = MagicMock(spec=httpx.Response)
        resp.headers = headers
        return httpx.HTTPStatusError("429", request=MagicMock(), response=resp)

    assert _retry_after_seconds(exc({"Retry-After": "2"})) == 2.0
    assert _retry_after_seconds(exc({})) is None
    assert _retry_after_seconds(exc({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})) is None
    assert _retry_after_seconds(exc({"Retry-After": "-5"})) is None
    assert _retry_after_seconds(ValueError("x")) is None
    assert _retry_after_seconds(None) is None


async def test_resilient_get_acquires_limiter_on_every_attempt(tmp_path):
    """Each retry takes (and releases) a limiter slot, so retries are rate limited."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=False,
        max_retries=3,
        backoff_base=0.01,
        backoff_max=0.05,
    )
    limiter = MagicMock(spec=RateLimiter)
    limiter.acquire = AsyncMock()

    ok = MagicMock(spec=httpx.Response)
    ok.status_code = 200
    ok.headers = {}
    ok.raise_for_status.return_value = None

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=[_status_error(503), _status_error(503), ok])

    result = await resilient_get(client, "https://example.com", cfg=cfg, limiter=limiter)

    assert result is ok
    assert limiter.acquire.await_count == 3
    assert limiter.release.call_count == 3


async def test_resilient_get_releases_slot_on_non_retryable_error(tmp_path):
    """A 404 is raised immediately and the limiter slot is still released."""
    cfg = Config(cache_dir=str(tmp_path / "cache"), max_retries=3)
    limiter = MagicMock(spec=RateLimiter)
    limiter.acquire = AsyncMock()

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_status_error(404))

    with pytest.raises(httpx.HTTPStatusError):
        await resilient_get(client, "https://example.com", cfg=cfg, limiter=limiter)

    assert client.get.call_count == 1
    assert limiter.release.call_count == 1


async def test_retry_after_is_not_added_on_top_of_backoff(tmp_path):
    """The wait is max(Retry-After, backoff), not their sum."""
    cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        rate_limit_enabled=False,
        max_retries=2,
        backoff_base=0.3,
        backoff_max=0.3,
    )
    dc = diskcache.Cache(cfg.cache_dir)
    lim = RateLimiter(cfg, dc)

    ok = MagicMock(spec=httpx.Response)
    ok.status_code = 200
    ok.headers = {}
    ok.raise_for_status.return_value = None

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=[_status_error(429, {"Retry-After": "0.3"}), ok])

    t0 = time.monotonic()
    await resilient_get(client, "https://example.com", cfg=cfg, limiter=lim)
    elapsed = time.monotonic() - t0

    # Old behaviour slept Retry-After (0.3) *and* the backoff (>=0.3) => >= 0.6.
    assert 0.25 <= elapsed < 0.55
    dc.close()


async def test_acquire_releases_semaphore_when_spacing_fails(rl_cfg, dc, monkeypatch):
    """If the spacing step raises, the concurrency slot is not leaked."""
    lim = RateLimiter(rl_cfg, dc)

    def boom() -> None:
        raise RuntimeError("disk error")

    monkeypatch.setattr(lim, "_sync_rate_limit", boom)

    for _ in range(rl_cfg.max_concurrency + 2):
        with pytest.raises(RuntimeError):
            await lim.acquire()
