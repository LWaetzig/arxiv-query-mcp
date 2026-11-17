import json
from dataclasses import replace
from datetime import date
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from mcp.server.mcpserver.exceptions import ToolError

import arxiv_query_mcp.server as _server_module
from arxiv_query_mcp.server import (
    arxiv_search,
    arxiv_get_paper,
    arxiv_list_by_category,
    arxiv_fetch_paper_text,
)
from arxiv_query_mcp.models import (
    SearchInput,
    GetPaperInput,
    ListByCategoryInput,
    FetchPaperTextInput,
    ResponseFormat,
    SortBy,
    SortOrder,
)


SAMPLE_PAPER = {
    "id": "2303.08774",
    "title": "GPT-4 Technical Report",
    "authors": ["OpenAI"],
    "abstract": "This is a test abstract.",
    "published": "2023-03-15T00:00:00Z",
    "updated": "2023-03-15T00:00:00Z",
    "primary_category": "cs.LG",
    "categories": ["cs.LG", "cs.AI"],
    "abstract_url": "https://arxiv.org/abs/2303.08774",
    "pdf_url": "https://arxiv.org/pdf/2303.08774",
    "html_url": "https://arxiv.org/html/2303.08774",
    "comment": "test comment",
    "journal_ref": "None",
    "doi": "test-doi",
}


# MARK: Test arxiv_search


@pytest.mark.asyncio
async def test_arxiv_search_with_markdown_response():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (100, [SAMPLE_PAPER])

        params = SearchInput(
            query="test query",
            max_results=10,
            start=0,
            sort_by=SortBy.RELEVANCE,
            sort_order=SortOrder.DESCENDING,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await arxiv_search(params)
        assert isinstance(result, str)
        assert "arXiv Search" in result
        assert "2303.08774" in result
        assert "GPT-4 Technical Report" in result


@pytest.mark.asyncio
async def test_arxiv_search_with_json_response():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (100, [SAMPLE_PAPER])

        params = SearchInput(
            query="test query",
            max_results=10,
            start=0,
            response_format=ResponseFormat.JSON,
        )

        result = await arxiv_search(params)
        data = json.loads(result)
        assert data["total"] == 100
        assert data["count"] == 1
        assert data["start"] == 0
        assert data["has_more"] is True
        assert len(data["papers"]) == 1
        assert data["papers"][0]["id"] == "2303.08774"


@pytest.mark.asyncio
async def test_arxiv_search_no_results():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (0, [])

        params = SearchInput(query="nonexistent paper")
        result = await arxiv_search(params)
        assert "No papers found" in result
        assert "nonexistent paper" in result


@pytest.mark.asyncio
async def test_arxiv_search_passes_correct_params():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (0, [])

        params = SearchInput(
            query="ti:attention AND cat:cs.LG",
            max_results=25,
            start=5,
            sort_by=SortBy.SUBMITTED,
            sort_order=SortOrder.ASCENDING,
        )

        await arxiv_search(params)

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args[0][0]
        assert call_args["search_query"] == "ti:attention AND cat:cs.LG"
        assert call_args["max_results"] == 25
        assert call_args["start"] == 5
        assert call_args["sortBy"] == "submittedDate"
        assert call_args["sortOrder"] == "ascending"


# MARK: Test arxiv_get_paper


@pytest.mark.asyncio
async def test_arxiv_get_paper_with_markdown():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])

        params = GetPaperInput(
            paper_id="2303.08774", response_format=ResponseFormat.MARKDOWN
        )

        result = await arxiv_get_paper(params)
        assert "GPT-4 Technical Report" in result
        assert "2303.08774" in result
        assert "OpenAI" in result


@pytest.mark.asyncio
async def test_arxiv_get_paper_with_json():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])

        params = GetPaperInput(
            paper_id="2303.08774", response_format=ResponseFormat.JSON
        )

        result = await arxiv_get_paper(params)
        data = json.loads(result)
        assert data["id"] == "2303.08774"
        assert data["title"] == "GPT-4 Technical Report"


@pytest.mark.asyncio
async def test_arxiv_get_paper_cleans_id():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])

        await arxiv_get_paper(
            GetPaperInput(paper_id="https://arxiv.org/abs/2303.08774/")
        )

        assert mock_fetch.call_args[0][0] == {"id_list": "2303.08774"}


@pytest.mark.asyncio
async def test_arxiv_get_paper_keeps_requested_version():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])

        await arxiv_get_paper(GetPaperInput(paper_id="arxiv.org/pdf/2303.08774v2"))

        assert mock_fetch.call_args[0][0] == {"id_list": "2303.08774v2"}


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_reads_requested_version(_init_http_client):
    mock_client = _init_http_client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.text = "<article>" + "<p>versioned text here.</p>" * 40 + "</article>"
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await arxiv_fetch_paper_text(FetchPaperTextInput(paper_id="2303.08774v1"))

    assert mock_client.get.call_args[0][0] == "https://arxiv.org/html/2303.08774v1"
    assert "Paper Text: 2303.08774v1" in result


@pytest.mark.asyncio
async def test_arxiv_get_paper_not_found():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (0, [])

        params = GetPaperInput(paper_id="invalid-id")
        result = await arxiv_get_paper(params)
        assert "No paper found" in result
        assert "invalid-id" in result


# MARK: Test arxiv_list_by_category


@pytest.mark.asyncio
async def test_arxiv_list_by_category_with_markdown():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (500, [SAMPLE_PAPER])

        params = ListByCategoryInput(
            category="cs.LG",
            max_results=20,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await arxiv_list_by_category(params)
        assert "Category: cs.LG" in result
        assert "arXiv Search" in result
        assert "2303.08774" in result


@pytest.mark.asyncio
async def test_arxiv_list_by_category_with_json():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (500, [SAMPLE_PAPER])

        params = ListByCategoryInput(
            category="cs.LG", response_format=ResponseFormat.JSON
        )

        result = await arxiv_list_by_category(params)
        data = json.loads(result)
        assert data["category"] == "cs.LG"
        assert data["total"] == 500
        assert len(data["papers"]) == 1


@pytest.mark.asyncio
async def test_arxiv_list_by_category_passes_correct_query():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (0, [])

        params = ListByCategoryInput(category="math.CO")
        await arxiv_list_by_category(params)

        call_args = mock_fetch.call_args[0][0]
        assert call_args["search_query"] == "cat:math.CO"


@pytest.mark.asyncio
async def test_arxiv_list_by_category_empty():
    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (0, [])

        params = ListByCategoryInput(category="invalid.XX")
        result = await arxiv_list_by_category(params)
        assert "No papers found" in result
        assert "invalid.XX" in result


# MARK: Test arxiv_fetch_paper_text


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_with_html(_init_http_client):
    """HTML path: mock client returns a 200 response with enough article text."""
    mock_client = _init_http_client
    article_text = "This is the paper content. " * 30  # > 500 chars

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.text = f"<html><body><article>{article_text}</article></body></html>"
    mock_client.get = AsyncMock(return_value=mock_resp)

    params = FetchPaperTextInput(paper_id="2303.08774")
    result = await arxiv_fetch_paper_text(params)

    assert "Paper Text" in result
    assert "2303.08774" in result
    assert "paper content" in result.lower()


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_fallback_to_abstract(_init_http_client):
    """Fallback path: HTML returns 404, fall back to abstract via _fetch_arxiv."""
    mock_client = _init_http_client

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {}
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])

        params = FetchPaperTextInput(paper_id="2303.08774")
        result = await arxiv_fetch_paper_text(params)

        assert "GPT-4 Technical Report" in result
        assert "Abstract" in result
        assert "This is a test abstract." in result


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_not_found(_init_http_client):
    """Fallback path: paper not found in API either."""
    mock_client = _init_http_client

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {}
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (0, [])

        params = FetchPaperTextInput(paper_id="invalid-id")
        with pytest.raises(ToolError, match="not found"):
            await arxiv_fetch_paper_text(params)


# ---- server instructions ---------------------------------------------------


def test_instructions_advertise_skill_url():
    """The server instructions point agents at the configured SKILL.md."""
    from arxiv_query_mcp.config import Config

    text = _server_module._build_instructions(Config(skill_url="https://x.test/SKILL.md"))
    assert "https://x.test/SKILL.md" in text
    assert "SKILL.md" in text


def test_instructions_without_skill_url_omit_notice():
    """An empty skill_url removes the skill notice."""
    from arxiv_query_mcp.config import Config

    text = _server_module._build_instructions(Config(skill_url=""))
    assert "SKILL.md" not in text
    assert "arxiv_search" in text


def test_server_exposes_instructions():
    """The live server object carries the instructions with the default skill URL."""
    from arxiv_query_mcp.config import DEFAULT_SKILL_URL

    instructions = _server_module.mcp.instructions
    assert instructions is not None
    assert "arxiv_search" in instructions
    assert DEFAULT_SKILL_URL in instructions


# ---- arxiv_fetch_paper_text pagination --------------------------------------


def _html_response(mock_client, article_text: str) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.text = f"<html><body><article>{article_text}</article></body></html>"
    mock_client.get = AsyncMock(return_value=mock_resp)


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_pages_cover_whole_text(_init_http_client):
    """Following next_offset reads the complete text without gaps or overlap."""
    article_text = " ".join(f"word{i}" for i in range(6000))  # > 3 pages
    _html_response(_init_http_client, article_text)

    parts: list[str] = []
    offset: int | None = 0
    while offset is not None:
        result = await arxiv_fetch_paper_text(
            FetchPaperTextInput(
                paper_id="2303.08774",
                offset=offset,
                response_format=ResponseFormat.JSON,
            )
        )
        page = json.loads(result)
        assert page["total_chars"] == len(article_text)
        assert page["count"] <= _server_module.config.max_fetch_chars
        parts.append(page["text"])
        offset = page["next_offset"]
        assert page["has_more"] == (offset is not None)

    assert len(parts) > 1
    assert "".join(parts) == article_text


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_markdown_reports_next_offset(_init_http_client):
    """Markdown output tells the caller which offset continues the paper."""
    _html_response(_init_http_client, "lorem ipsum " * 2000)

    result = await arxiv_fetch_paper_text(FetchPaperTextInput(paper_id="2303.08774"))

    assert "call again with offset=" in result


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_offset_past_end(_init_http_client):
    """An offset beyond the text length returns an actionable error."""
    _html_response(_init_http_client, "short paper text. " * 40)

    with pytest.raises(ToolError, match="past the end"):
        await arxiv_fetch_paper_text(
            FetchPaperTextInput(paper_id="2303.08774", offset=10_000_000)
        )


# ---- date filtering ----------------------------------------------------------


@pytest.mark.asyncio
async def test_arxiv_search_applies_date_range():
    with patch(
        "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])

        result = await arxiv_search(
            SearchInput(
                query="ti:attention OR ti:transformer",
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 31),
            )
        )

        assert mock_fetch.call_args[0][0]["search_query"] == (
            "(ti:attention OR ti:transformer) AND "
            "submittedDate:[202601010000 TO 202601312359]"
        )
        assert "submitted 2026-01-01 to 2026-01-31" in result


@pytest.mark.asyncio
async def test_arxiv_search_open_ended_date_range():
    with patch(
        "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (0, [])

        await arxiv_search(SearchInput(query="au:hinton", date_from=date(2026, 10, 1)))
        assert mock_fetch.call_args[0][0]["search_query"] == (
            "(au:hinton) AND submittedDate:[202610010000 TO 999912312359]"
        )

        await arxiv_search(SearchInput(query="au:hinton", date_to=date(2015, 12, 31)))
        assert mock_fetch.call_args[0][0]["search_query"] == (
            "(au:hinton) AND submittedDate:[190001010000 TO 201512312359]"
        )


@pytest.mark.asyncio
async def test_arxiv_list_by_category_applies_date_range():
    with patch(
        "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (0, [])

        await arxiv_list_by_category(
            ListByCategoryInput(category="cs.LG", date_from=date(2026, 11, 1))
        )

        assert mock_fetch.call_args[0][0]["search_query"] == (
            "(cat:cs.LG) AND submittedDate:[202611010000 TO 999912312359]"
        )


def test_date_inputs_accept_iso_strings_and_reject_reversed_range():
    parsed = SearchInput.model_validate({"query": "x", "date_from": "2026-01-01"})
    assert parsed.date_from == date(2026, 1, 1)

    with pytest.raises(ValueError, match="date_from must not be later"):
        SearchInput(query="x", date_from=date(2026, 2, 1), date_to=date(2026, 1, 1))


# ---- error results and annotations -------------------------------------------


@pytest.mark.asyncio
async def test_upstream_failure_is_raised_as_tool_error():
    """A failed arXiv request becomes an error result, not normal text."""
    response = httpx.Response(400, request=httpx.Request("GET", "https://x"))
    failure = httpx.HTTPStatusError("bad", request=response.request, response=response)

    with patch(
        "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = failure

        with pytest.raises(ToolError, match="Invalid query syntax"):
            await arxiv_search(SearchInput(query="ti:(("))


@pytest.mark.asyncio
async def test_all_tools_are_annotated_read_only():
    tools = await _server_module.mcp.list_tools()

    assert len(tools) == 5
    for tool in tools:
        assert tool.title
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is True


# ---- PDF fallback ------------------------------------------------------------


def _html_missing_pdf_present(mock_client, pdf_bytes: bytes = b"%PDF-fake") -> None:
    """Make the HTML URL return 404 and the PDF URL return a PDF body."""

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        if "/pdf/" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "application/pdf"}
            resp.content = pdf_bytes
        else:
            resp.status_code = 404
            resp.headers = {}
        return resp

    mock_client.get = AsyncMock(side_effect=fake_get)


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_falls_back_to_pdf(_init_http_client):
    """Without an HTML version the text comes from the PDF."""
    _html_missing_pdf_present(_init_http_client)
    pdf_text = "Extracted pdf line.\n" * 60

    with patch("arxiv_query_mcp.server._pdf_to_text", return_value=pdf_text):
        result = await arxiv_fetch_paper_text(
            FetchPaperTextInput(
                paper_id="hep-th/9901001", response_format=ResponseFormat.JSON
            )
        )

    page = json.loads(result)
    assert page["format"] == "pdf"
    assert page["source"] == "https://arxiv.org/pdf/hep-th/9901001"
    assert page["text"] == pdf_text
    assert page["has_more"] is False


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_skips_oversized_pdf(_init_http_client, monkeypatch):
    """A PDF above max_pdf_bytes is not parsed; the abstract is returned."""
    _html_missing_pdf_present(_init_http_client, pdf_bytes=b"x" * 2048)
    monkeypatch.setattr(
        _server_module, "config", replace(_server_module.config, max_pdf_bytes=1024)
    )

    with (
        patch("arxiv_query_mcp.server._pdf_to_text") as mock_extract,
        patch(
            "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
        ) as mock_fetch,
    ):
        mock_fetch.return_value = (1, [SAMPLE_PAPER])
        result = await arxiv_fetch_paper_text(
            FetchPaperTextInput(paper_id="2303.08774")
        )

    mock_extract.assert_not_called()
    assert "This is a test abstract." in result


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_pdf_fallback_can_be_disabled(
    _init_http_client, monkeypatch
):
    """max_pdf_bytes=0 never requests the PDF."""
    _html_missing_pdf_present(_init_http_client)
    monkeypatch.setattr(
        _server_module, "config", replace(_server_module.config, max_pdf_bytes=0)
    )

    with patch(
        "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])
        await arxiv_fetch_paper_text(FetchPaperTextInput(paper_id="2303.08774"))

    requested = [call.args[0] for call in _init_http_client.get.call_args_list]
    assert not any("/pdf/" in url for url in requested)


@pytest.mark.asyncio
async def test_arxiv_fetch_paper_text_pdf_timeout_falls_back_to_abstract(
    _init_http_client,
):
    """A PDF download that times out degrades to the abstract, not an error."""

    async def fake_get(url, **kwargs):
        if "/pdf/" in url:
            raise httpx.ReadTimeout("slow", request=httpx.Request("GET", url))
        resp = MagicMock()
        resp.status_code = 404
        resp.headers = {}
        return resp

    _init_http_client.get = AsyncMock(side_effect=fake_get)

    with patch(
        "arxiv_query_mcp.server._fetch_arxiv", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (1, [SAMPLE_PAPER])
        result = await arxiv_fetch_paper_text(FetchPaperTextInput(paper_id="1412.6980"))

    assert "This is a test abstract." in result
