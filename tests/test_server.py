import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
        with patch("arxiv_query_mcp.server._clean_id") as mock_clean:
            mock_clean.return_value = "2303.08774"
            mock_fetch.return_value = (1, [SAMPLE_PAPER])

            params = GetPaperInput(paper_id="2303.08774v2")
            await arxiv_get_paper(params)

            mock_clean.assert_called_once_with("2303.08774v2")


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
        result = await arxiv_fetch_paper_text(params)

        assert "not found" in result
