import pytest
from unittest.mock import AsyncMock

import httpx
import arxiv_query_mcp.server as _server_module


@pytest.fixture(autouse=True)
def _init_http_client(monkeypatch):
    """Provide a mock httpx.AsyncClient as the server's shared client for every test."""
    mock = AsyncMock(spec=httpx.AsyncClient)
    monkeypatch.setattr(_server_module, "_client", mock)
    return mock
