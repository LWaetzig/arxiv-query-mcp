"""Tests for arxiv_related_papers (Semantic Scholar)."""
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

import arxiv_query_mcp.server as _server_module
from arxiv_query_mcp.models import RelatedPapersInput, Relation, ResponseFormat
from arxiv_query_mcp.server import arxiv_related_papers

ON_ARXIV = {
    "title": "Transformer++",
    "authors": [{"name": "A"}, {"name": "B"}, {"name": "C"}, {"name": "D"}],
    "year": 2020,
    "publicationDate": "2020-03-11",
    "externalIds": {"ArXiv": "2003.04974", "DOI": "10.1/x"},
    "citationCount": 12,
    "abstract": "An improved transformer.",
    "url": "https://www.semanticscholar.org/paper/abc",
    "venue": "arXiv.org",
}
NOT_ON_ARXIV = {
    "title": "A Journal Paper",
    "authors": [{"name": "E"}],
    "year": 2019,
    "publicationDate": None,
    "externalIds": {"DOI": "10.2/y"},
    "citationCount": 3,
    "abstract": None,
    "url": "https://www.semanticscholar.org/paper/def",
    "venue": "Some Journal",
}


def _route(mock_client, responses):
    """Answer GETs from *responses*: (url_fragment[|pool], status, body) tuples."""
    calls = []

    async def fake_get(url, params=None, headers=None, **kwargs):
        calls.append((url, params, headers))
        for fragment, status, body in responses:
            pool = None
            if "|" in fragment:
                fragment, pool = fragment.split("|")
            if fragment in url and (pool is None or (params or {}).get("from") == pool):
                return httpx.Response(
                    status, json=body, request=httpx.Request("GET", url)
                )
        raise AssertionError(f"unexpected request {url} {params}")

    mock_client.get = AsyncMock(side_effect=fake_get)
    return calls


@pytest.mark.asyncio
async def test_similar_papers_markdown(_init_http_client):
    calls = _route(
        _init_http_client,
        [("forpaper/ARXIV:1706.03762|all-cs", 200,
          {"recommendedPapers": [ON_ARXIV, NOT_ON_ARXIV]})],
    )

    result = await arxiv_related_papers(RelatedPapersInput(paper_id="1706.03762"))

    assert calls[0][0] == (
        "https://api.semanticscholar.org/recommendations/v1/papers/forpaper/"
        "ARXIV:1706.03762"
    )
    assert calls[0][1]["limit"] == 10
    assert "# Papers similar to 1706.03762" in result
    assert "### [2003.04974] Transformer++" in result
    assert "https://arxiv.org/abs/2003.04974" in result
    assert "A, B, C … (+1 more)" in result
    assert "**Citations:** 12" in result
    assert "### A Journal Paper" in result
    assert "(not on arXiv)" in result


@pytest.mark.asyncio
async def test_similar_falls_back_to_recent_pool(_init_http_client):
    calls = _route(
        _init_http_client,
        [
            ("forpaper/ARXIV:2402.03300|all-cs", 200, {"recommendedPapers": []}),
            ("forpaper/ARXIV:2402.03300|recent", 200, {"recommendedPapers": [ON_ARXIV]}),
        ],
    )

    result = await arxiv_related_papers(RelatedPapersInput(paper_id="2402.03300"))

    assert [c[1]["from"] for c in calls] == ["all-cs", "recent"]
    assert "Transformer++" in result


@pytest.mark.asyncio
async def test_references_json_with_paging_and_unresolved_entries(_init_http_client):
    calls = _route(
        _init_http_client,
        [("paper/ARXIV:1706.03762/references", 200, {
            "offset": 20,
            "next": 22,
            "data": [
                {"citedPaper": ON_ARXIV},
                {"citedPaper": {"paperId": None, "title": None}},
                {"citedPaper": NOT_ON_ARXIV},
            ],
        })],
    )

    result = await arxiv_related_papers(
        RelatedPapersInput(
            paper_id="https://arxiv.org/abs/1706.03762v2",
            relation=Relation.REFERENCES,
            max_results=2,
            start=20,
            response_format=ResponseFormat.JSON,
        )
    )

    assert calls[0][1] == {"fields": calls[0][1]["fields"], "limit": 2, "offset": 20}
    page = json.loads(result)
    assert page["paper_id"] == "1706.03762"
    assert page["relation"] == "references"
    assert page["next_start"] == 22 and page["has_more"] is True
    assert [p["title"] for p in page["papers"]] == ["Transformer++", "A Journal Paper"]
    assert page["papers"][1]["arxiv_id"] == ""
    assert page["papers"][1]["url"] == "https://www.semanticscholar.org/paper/def"


@pytest.mark.asyncio
async def test_cited_by_uses_citations_endpoint(_init_http_client):
    _route(
        _init_http_client,
        [("paper/ARXIV:1412.6980/citations", 200,
          {"offset": 0, "data": [{"citingPaper": ON_ARXIV}]})],
    )

    result = await arxiv_related_papers(
        RelatedPapersInput(paper_id="1412.6980", relation=Relation.CITED_BY)
    )

    assert "# Papers citing 1412.6980" in result
    assert "Transformer++" in result
    assert "start=" not in result  # no "next" → no further pages


@pytest.mark.asyncio
async def test_unknown_paper_raises_tool_error(_init_http_client):
    _route(
        _init_http_client,
        [("forpaper/ARXIV:2611.99999|all-cs", 404, {"error": "not found"})],
    )

    with pytest.raises(ToolError, match="no record of arXiv paper '2611.99999'"):
        await arxiv_related_papers(RelatedPapersInput(paper_id="2611.99999"))


@pytest.mark.asyncio
async def test_rate_limit_message_mentions_api_key(_init_http_client):
    _route(
        _init_http_client,
        [("paper/ARXIV:1706.03762/citations", 429, {"message": "Too Many Requests"})],
    )

    with pytest.raises(ToolError, match="ARXIV_MCP_S2_API_KEY"):
        await arxiv_related_papers(
            RelatedPapersInput(paper_id="1706.03762", relation=Relation.CITED_BY)
        )


@pytest.mark.asyncio
async def test_api_key_is_sent_when_configured(_init_http_client, monkeypatch):
    monkeypatch.setattr(
        _server_module, "config", replace(_server_module.config, s2_api_key="k-123")
    )
    calls = _route(
        _init_http_client,
        [("forpaper/ARXIV:1706.03762|all-cs", 200, {"recommendedPapers": [ON_ARXIV]})],
    )

    await arxiv_related_papers(RelatedPapersInput(paper_id="1706.03762"))

    assert calls[0][2] == {"x-api-key": "k-123"}


@pytest.mark.asyncio
async def test_no_api_key_header_by_default(_init_http_client):
    calls = _route(
        _init_http_client,
        [("forpaper/ARXIV:1706.03762|all-cs", 200, {"recommendedPapers": [ON_ARXIV]})],
    )

    await arxiv_related_papers(RelatedPapersInput(paper_id="1706.03762"))

    assert calls[0][2] is None


@pytest.mark.asyncio
async def test_empty_citations_message(_init_http_client):
    _route(
        _init_http_client,
        [("paper/ARXIV:2611.00001/citations", 200, {"offset": 0, "data": []})],
    )

    result = await arxiv_related_papers(
        RelatedPapersInput(paper_id="2611.00001", relation=Relation.CITED_BY)
    )

    assert result == "Semantic Scholar lists no citing papers for 2611.00001."


def test_similar_rejects_start():
    with pytest.raises(ValidationError, match="does not support start"):
        RelatedPapersInput(paper_id="1706.03762", start=10)
