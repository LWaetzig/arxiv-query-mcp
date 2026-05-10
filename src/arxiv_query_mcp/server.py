from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
from mcp.server.fastmcp import FastMCP

from .config import Config
from .models import (
    FetchPaperTextInput,
    GetPaperInput,
    ListByCategoryInput,
    ResponseFormat,
    SearchInput,
)
from .utils import (
    _author_line,
    _clean_id,
    _fetch_arxiv,
    _format_paper_detail,
    _format_paper_list,
    _handle_error,
    _strip_html,
)

# MARK: Config

config = Config()
_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(app: FastMCP):
    """FastMCP lifespan: create and tear down the shared HTTP client.

    The client is stored in the module-level ``_client`` variable so all tool
    functions can access it via :func:`_http` without requiring Context
    injection in every signature.
    """
    global _client
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=config.request_timeout,
    ) as client:
        _client = client
        yield


def _http() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized")
    return _client


mcp = FastMCP("arxiv-query-mcp", lifespan=_lifespan)


# MARK: Tools

@mcp.tool(
    name="arxiv_search",
)
async def arxiv_search(params: SearchInput) -> str:
    """Search arXiv for academic papers using full query syntax.

    Supports field-specific search and boolean operators. Returns paginated
    results with title, authors, abstract snippet, and direct links.

    Args:
        params (SearchInput):
            - query (str): Query string, e.g. 'ti:attention AND cat:cs.LG'
            - max_results (int): Results per page (1 - 50, default 10)
            - start (int): Pagination offset (default 0)
            - sort_by (str): relevance | lastUpdatedDate | submittedDate
            - sort_order (str): descending | ascending
            - response_format (str): markdown | json

    Returns:
        str: Paginated list of matching papers with metadata and links.

        JSON schema when response_format='json':
        {
          "total": int,
          "count": int,
          "start": int,
          "has_more": bool,
          "next_start": int | null,
          "papers": [{ "id", "title", "authors", "abstract", "published",
                       "updated", "primary_category", "categories",
                       "abstract_url", "pdf_url", "html_url",
                       "comment", "journal_ref", "doi" }]
        }

    Examples:
        - 'ti:large language model AND cat:cs.LG' — LLM papers in ML
        - 'au:lecun AND cat:cs.CV' — LeCun's vision papers
        - 'abs:diffusion AND abs:image generation' — diffusion image gen
        - 'ti:attention is all you need' — search by title phrase
    """
    try:
        total, papers = await _fetch_arxiv(
            {
                "search_query": params.query,
                "start": params.start,
                "max_results": params.max_results,
                "sortBy": params.sort_by.value,
                "sortOrder": params.sort_order.value,
            },
            config,
            _http(),
        )

        if not papers:
            return f"No papers found for query: '{params.query}'"

        if params.response_format == ResponseFormat.JSON:
            next_start = (
                params.start + len(papers)
                if total > params.start + len(papers)
                else None
            )
            return json.dumps(
                {
                    "total": total,
                    "count": len(papers),
                    "start": params.start,
                    "has_more": next_start is not None,
                    "next_start": next_start,
                    "papers": papers,
                },
                indent=2,
            )

        return _format_paper_list(papers, total, params.start, params.query)

    except Exception as exc:
        return _handle_error(exc)


@mcp.tool(
    name="arxiv_get_paper",
)
async def arxiv_get_paper(params: GetPaperInput) -> str:
    """Retrieve full metadata for a specific arXiv paper by its ID.

    Returns complete information: title, all authors, full abstract, categories,
    dates, journal reference, DOI, and direct links to abstract, PDF, and HTML.

    Args:
        params (GetPaperInput):
            - paper_id (str): arXiv ID, e.g. '2303.08774', '1706.03762v2',
                              or old-style 'hep-th/9901001'
            - response_format (str): markdown | json

    Returns:
        str: Full paper metadata.

        JSON schema when response_format='json':
        { "id", "title", "authors", "abstract", "published", "updated",
          "primary_category", "categories", "abstract_url", "pdf_url",
          "html_url", "comment", "journal_ref", "doi" }

    Examples:
        - Attention Is All You Need: paper_id='1706.03762'
        - GPT-4 technical report:    paper_id='2303.08774'
        - AlphaFold:                 paper_id='2108.10991'
    """
    try:
        clean = _clean_id(params.paper_id)
        _, papers = await _fetch_arxiv(
            {"id_list": clean},
            config,
            _http(),
        )

        if not papers:
            return (
                f"No paper found with ID '{params.paper_id}'. "
                "Verify the ID using arxiv_search if unsure."
            )

        paper = papers[0]
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(paper, indent=2)

        return _format_paper_detail(paper)

    except Exception as exc:
        return _handle_error(exc)


@mcp.tool(
    name="arxiv_list_by_category",
)
async def arxiv_list_by_category(params: ListByCategoryInput) -> str:
    """List recent papers in a specific arXiv subject category.

    Retrieves papers filtered to one category, sorted by submission date by
    default. Useful for monitoring a research area's latest preprints.

    Args:
        params (ListByCategoryInput):
            - category (str): arXiv category code, e.g. 'cs.LG', 'math.CO'
            - max_results (int): Results per page (1 - 50, default 20)
            - start (int): Pagination offset
            - sort_by (str): relevance | lastUpdatedDate | submittedDate
            - sort_order (str): descending | ascending
            - response_format (str): markdown | json

    Returns:
        str: Paginated list of papers in the category.

    Common category codes:
        cs.LG  — Machine Learning        cs.AI  — Artificial Intelligence
        cs.CL  — Computation & Language  cs.CV  — Computer Vision
        cs.CR  — Cryptography            cs.RO  — Robotics
        cs.NE  — Neural & Evolutionary   math.CO — Combinatorics
        math.ST — Statistics Theory      physics.quant-ph — Quantum Physics
        stat.ML — Statistics / ML        econ.GN — General Economics
        q-bio.NC — Neurons & Cognition
    """
    try:
        total, papers = await _fetch_arxiv(
            {
                "search_query": f"cat:{params.category}",
                "start": params.start,
                "max_results": params.max_results,
                "sortBy": params.sort_by.value,
                "sortOrder": params.sort_order.value,
            },
            config,
            _http(),
        )

        if not papers:
            return (
                f"No papers found in category '{params.category}'. "
                "Check that the category code is valid (e.g. 'cs.LG', 'math.CO')."
            )

        if params.response_format == ResponseFormat.JSON:
            next_start = (
                params.start + len(papers)
                if total > params.start + len(papers)
                else None
            )
            return json.dumps(
                {
                    "total": total,
                    "count": len(papers),
                    "start": params.start,
                    "category": params.category,
                    "has_more": next_start is not None,
                    "next_start": next_start,
                    "papers": papers,
                },
                indent=2,
            )

        return _format_paper_list(
            papers, total, params.start, f"Category: {params.category}"
        )

    except Exception as exc:
        return _handle_error(exc)


@mcp.tool(
    name="arxiv_fetch_paper_text",
)
async def arxiv_fetch_paper_text(params: FetchPaperTextInput) -> str:
    """Fetch the readable text content of an arXiv paper.

    First tries the HTML version of the paper (available for most papers
    submitted after ~2023 with LaTeX source). Falls back to returning the
    full abstract and metadata if the HTML version is unavailable.

    Use arxiv_get_paper first to find the paper ID, then call this tool
    to read the paper's content.

    Args:
        params (FetchPaperTextInput):
            - paper_id (str): arXiv paper ID, e.g. '2303.08774'

    Returns:
        str: Extracted paper text (up to 10,000 characters) or full abstract
             with links when HTML is unavailable.
    """
    try:
        clean = _clean_id(params.paper_id)
        html_url = f"{config.arxiv_html_base}/{clean}"
        client = _http()

        html_resp = await client.get(html_url)

        if html_resp.status_code == 200 and "text/html" in html_resp.headers.get(
            "content-type", ""
        ):
            text = _strip_html(html_resp.text)
            if len(text) > 500:
                truncated = text[: config.max_fetch_chars]
                suffix = (
                    f"\n\n… [truncated at {config.max_fetch_chars} chars — full HTML: {html_url}]"
                    if len(text) > config.max_fetch_chars
                    else ""
                )
                return (
                    f"# Paper Text: {clean}\nSource: {html_url}\n\n{truncated}{suffix}"
                )

        # Fallback: return full abstract from API using same client
        _, papers = await _fetch_arxiv({"id_list": clean}, config, client)
        if not papers:
            return f"Error: Paper '{clean}' not found. Verify the ID with arxiv_search."

        p = papers[0]
        return (
            f"# {p['title']}\n\n"
            f"**arXiv ID:** {p['id']}\n"
            f"**Authors:** {_author_line(p['authors'])}\n"
            f"**Published:** {p['published'][:10]}\n"
            f"**PDF:** {p['pdf_url']}\n"
            f"**HTML (may not be available):** {p['html_url']}\n\n"
            f"## Abstract\n\n{p['abstract']}\n\n"
            f"---\n"
            f"*HTML version unavailable for this paper. "
            f"Read the full text at: {p['pdf_url']}*"
        )

    except Exception as exc:
        return _handle_error(exc)


# MARK: Entry Point


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
