import pytest
from unittest.mock import AsyncMock

import diskcache
import httpx

import arxiv_query_mcp.server as _server_module
from arxiv_query_mcp.cache import TwoTierCache
from arxiv_query_mcp.config import Config
from arxiv_query_mcp.ratelimit import RateLimiter


@pytest.fixture(autouse=True)
def _init_http_client(monkeypatch, tmp_path):
    """Provide a mock HTTP client and disabled cache/rate-limiter for every test.

    Sets up:
    - A mock ``httpx.AsyncClient`` as ``server._client``.
    - A test-scoped ``Config`` with cache and rate limiting disabled and
      ``max_retries=1`` so the suite runs fast and never hits the network.
    - ``TwoTierCache`` and ``RateLimiter`` instances (using the test config)
      as ``server._cache`` / ``server._limiter``.

    Tests that need the cache or rate limiter to be *enabled* should create
    their own instances rather than relying on these module-level patches.
    """
    mock = AsyncMock(spec=httpx.AsyncClient)
    monkeypatch.setattr(_server_module, "_client", mock)

    test_cfg = Config(
        cache_dir=str(tmp_path / "cache"),
        cache_enabled=False,
        rate_limit_enabled=False,
        rate_limit_period=0.0,
        max_retries=1,
        backoff_base=0.01,
        backoff_max=0.05,
    )
    monkeypatch.setattr(_server_module, "config", test_cfg)

    dc = diskcache.Cache(str(tmp_path / "cache"))
    cache = TwoTierCache(test_cfg, dc)
    limiter = RateLimiter(test_cfg, dc)

    monkeypatch.setattr(_server_module, "_cache", cache)
    monkeypatch.setattr(_server_module, "_limiter", limiter)
    monkeypatch.setattr(_server_module, "_disk_cache", dc)

    yield mock

    dc.close()
