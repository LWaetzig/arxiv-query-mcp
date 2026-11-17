from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import diskcache
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .cache import TwoTierCache
from .config import Config
from .models import (
    FetchPaperTextInput,
    GetPaperInput,
    ListByCategoryInput,
    RelatedPapersInput,
    Relation,
    ResponseFormat,
    SearchInput,
)
from .ratelimit import RateLimiter, resilient_get
from .semantic_scholar import fetch_related, format_related, related_error_message
from .utils import (
    _author_line,
    _clean_id,
    _date_range_label,
    _fetch_arxiv,
    _format_paper_detail,
    _format_paper_list,
    _handle_error,
    _pdf_to_text,
    _strip_html,
    _versioned_id,
    _with_date_filter,
)

# MARK: Config

config = Config.from_env()
_client: httpx.AsyncClient | None = None
_cache: TwoTierCache | None = None
_limiter: RateLimiter | None = None
_s2_limiter: RateLimiter | None = None
_disk_cache: diskcache.Cache | None = None


@asynccontextmanager
async def _lifespan(app: MCPServer):
    """MCPServer lifespan: create and tear down the shared HTTP client and cache.

    The client, cache, and rate limiter are stored in module-level variables so
    all tool functions can access them without requiring Context injection in
    every signature.  The diskcache is closed on shutdown so no SQLite
    connections are leaked.
    """
    global _client, _cache, _limiter, _s2_limiter, _disk_cache
    _disk_cache = diskcache.Cache(config.resolved_cache_dir)
    _cache = TwoTierCache(config, _disk_cache)
    _limiter = RateLimiter(config, _disk_cache)
    _s2_limiter = RateLimiter(
        config, _disk_cache, namespace="s2", period=config.s2_rate_limit_period
    )
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=config.request_timeout,
        headers={"User-Agent": config.user_agent},
    ) as client:
        _client = client
        try:
            yield
        finally:
            _disk_cache.close()
            _disk_cache = None
            _cache = None
            _limiter = None
            _s2_limiter = None


def _http() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized")
    return _client


def _build_instructions(cfg: Config) -> str:
    """Build the server instructions shown to clients when they connect.

    Args:
        cfg: Server configuration; ``skill_url`` decides whether the skill
            notice is included.

    Returns:
        A short description of the server, followed by a pointer to the agent
        skill when ``cfg.skill_url`` is set.
    """
    text = (
        "Read-only access to arXiv: search papers, get metadata by ID, browse "
        "subject categories, read paper text, and find similar, cited and "
        "citing papers. Start with arxiv_search, confirm candidates with "
        "arxiv_get_paper, use arxiv_related_papers to expand from a known "
        "paper, and use arxiv_fetch_paper_text only for papers that must be "
        "read in depth."
    )
    if cfg.skill_url:
        text += (
            "\n\nAgent skill: a SKILL.md with guidance on when and how to use "
            f"these tools is available at {cfg.skill_url}. If your client "
            "supports skills or can fetch URLs, read it before your first call."
        )
    return text


mcp = MCPServer(
    "arxiv-query-mcp",
    instructions=_build_instructions(config),
    lifespan=_lifespan,
)


# MARK: Tools


def _read_only(title: str) -> ToolAnnotations:
    """Annotations shared by every tool: read-only queries against arXiv.

    Args:
        title: Human-readable tool title shown by clients.

    Returns:
        Annotations marking the tool as read-only, idempotent and talking to
        an external service, so clients need not ask for confirmation.
    """
    return ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=True,
    )


@mcp.tool(
    name="arxiv_search",
    title="Search arXiv",
    annotations=_read_only("Search arXiv"),
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
            - date_from (str): Only papers submitted on/after YYYY-MM-DD
            - date_to (str): Only papers submitted on/before YYYY-MM-DD
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
          "papers": [{ "id", "version", "title", "authors", "abstract", "published",
                       "updated", "primary_category", "categories",
                       "abstract_url", "pdf_url", "html_url",
                       "comment", "journal_ref", "doi" }]
        }

    Examples:
        - 'ti:large language model AND cat:cs.LG' — LLM papers in ML
        - 'au:lecun AND cat:cs.CV' — LeCun's vision papers
        - 'abs:diffusion AND abs:image generation' — diffusion image gen
        - 'ti:attention is all you need' — search by title phrase
        - query='abs:agents', date_from='2026-10-01' — recent papers only
    """
    try:
        date_label = _date_range_label(params.date_from, params.date_to)
        total, papers = await _fetch_arxiv(
            {
                "search_query": _with_date_filter(
                    params.query, params.date_from, params.date_to
                ),
                "start": params.start,
                "max_results": params.max_results,
                "sortBy": params.sort_by.value,
                "sortOrder": params.sort_order.value,
            },
            config,
            _http(),
            cache=_cache,
            limiter=_limiter,
        )

        if not papers:
            return f"No papers found for query: '{params.query}'{date_label}"

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

        return _format_paper_list(
            papers, total, params.start, f"{params.query}{date_label}"
        )

    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(_handle_error(exc)) from exc


@mcp.tool(
    name="arxiv_get_paper",
    title="Get arXiv paper metadata",
    annotations=_read_only("Get arXiv paper metadata"),
)
async def arxiv_get_paper(params: GetPaperInput) -> str:
    """Retrieve full metadata for a specific arXiv paper by its ID.

    Returns complete information: title, all authors, full abstract, categories,
    dates, journal reference, DOI, and direct links to abstract, PDF, and HTML.

    Args:
        params (GetPaperInput):
            - paper_id (str): arXiv ID, e.g. '2303.08774', '1706.03762v2',
                              or old-style 'hep-th/9901001'. A version
                              suffix selects that version; without one the
                              latest version is returned.
            - response_format (str): markdown | json

    Returns:
        str: Full paper metadata.

        JSON schema when response_format='json':
        { "id", "version", "title", "authors", "abstract", "published",
          "updated", "primary_category", "categories", "abstract_url", "pdf_url",
          "html_url", "comment", "journal_ref", "doi" }

    Examples:
        - Attention Is All You Need: paper_id='1706.03762'
        - GPT-4 technical report:    paper_id='2303.08774'
        - AlphaFold:                 paper_id='2108.10991'
    """
    try:
        clean = _versioned_id(params.paper_id)
        _, papers = await _fetch_arxiv(
            {"id_list": clean},
            config,
            _http(),
            cache=_cache,
            limiter=_limiter,
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

    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(_handle_error(exc)) from exc


@mcp.tool(
    name="arxiv_list_by_category",
    title="List arXiv papers by category",
    annotations=_read_only("List arXiv papers by category"),
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
            - date_from (str): Only papers submitted on/after YYYY-MM-DD
            - date_to (str): Only papers submitted on/before YYYY-MM-DD
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
        date_label = _date_range_label(params.date_from, params.date_to)
        total, papers = await _fetch_arxiv(
            {
                "search_query": _with_date_filter(
                    f"cat:{params.category}", params.date_from, params.date_to
                ),
                "start": params.start,
                "max_results": params.max_results,
                "sortBy": params.sort_by.value,
                "sortOrder": params.sort_order.value,
            },
            config,
            _http(),
            cache=_cache,
            limiter=_limiter,
        )

        if not papers:
            return (
                f"No papers found in category '{params.category}'{date_label}. "
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
            papers, total, params.start, f"Category: {params.category}{date_label}"
        )

    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(_handle_error(exc)) from exc


@mcp.tool(
    name="arxiv_fetch_paper_text",
    title="Read arXiv paper text",
    annotations=_read_only("Read arXiv paper text"),
)
async def arxiv_fetch_paper_text(params: FetchPaperTextInput) -> str:
    """Fetch the readable text content of an arXiv paper.

    First tries the HTML version of the paper (available for most papers
    submitted after ~2023 with LaTeX source). Without one, the text is
    extracted from the PDF instead. Only if neither works does it return the
    full abstract and metadata.

    Use arxiv_get_paper first to find the paper ID, then call this tool
    to read the paper's content.

    Args:
        params (FetchPaperTextInput):
            - paper_id (str): arXiv paper ID, e.g. '2303.08774'; add a
                              version suffix ('2303.08774v1') to read
                              that version instead of the latest
            - offset (int): Character offset to start from (default 0)
            - response_format (str): markdown | json

    Returns:
        str: One page of extracted paper text (about 10,000 characters) or
             the full abstract with links when no text can be extracted. Long
             papers span several pages: when more text remains, the response
             reports the next offset; call again with that offset to continue.

        JSON schema when response_format='json' (text available):
        { "id", "source", "format" ("html" | "pdf"), "total_chars", "offset", "count", "has_more",
          "next_offset", "text" }
    """
    try:
        clean = _versioned_id(params.paper_id)
        html_url = f"{config.arxiv_html_base}/{clean}"
        client = _http()

        # Fetch HTML through the resilient layer (retry on 429/5xx) and cache
        # the extracted text so repeated calls skip the network entirely.
        async def _fetch_html() -> str:
            """Return stripped paper text, or '' when HTML is unavailable."""
            if _cache is not None and _limiter is not None:
                try:
                    resp = await resilient_get(
                        client, html_url, cfg=config, limiter=_limiter
                    )
                except httpx.HTTPStatusError:
                    return ""
                if resp.status_code == 200 and "text/html" in resp.headers.get(
                    "content-type", ""
                ):
                    text = _strip_html(resp.text)
                    return text if len(text) > 500 else ""
                return ""
            else:
                # Fallback path used when lifespan has not run (e.g. unit tests
                # that do not initialise _cache / _limiter).
                resp = await client.get(html_url)
                if resp.status_code == 200 and "text/html" in resp.headers.get(
                    "content-type", ""
                ):
                    text = _strip_html(resp.text)
                    return text if len(text) > 500 else ""
                return ""

        if _cache is not None:
            text: str = await _cache.get_or_fetch(("text-v2", html_url), _fetch_html)
        else:
            text = await _fetch_html()
        source_url, source_format = html_url, "html"

        # No HTML version (typical for papers before ~2023): extract the PDF.
        async def _fetch_pdf() -> str:
            """Return text extracted from the PDF, or '' when unavailable."""
            try:
                if _limiter is not None:
                    resp = await resilient_get(
                        client, pdf_url, cfg=config, limiter=_limiter
                    )
                else:
                    resp = await client.get(pdf_url)
            except httpx.HTTPError:
                # Includes timeouts: a slow PDF falls back to the abstract.
                return ""
            if resp.status_code != 200 or "application/pdf" not in resp.headers.get(
                "content-type", ""
            ):
                return ""
            if len(resp.content) > config.max_pdf_bytes:
                return ""
            pdf_text = await asyncio.to_thread(_pdf_to_text, resp.content)
            return pdf_text if len(pdf_text) > 500 else ""

        if not text and config.max_pdf_bytes > 0:
            pdf_url = f"{config.arxiv_pdf_base}/{clean}"
            if _cache is not None:
                text = await _cache.get_or_fetch(("pdf-text-v1", pdf_url), _fetch_pdf)
            else:
                text = await _fetch_pdf()
            source_url, source_format = pdf_url, "pdf"

        if text:
            total = len(text)
            offset = params.offset
            if offset >= total:
                raise ToolError(
                    f"offset {offset} is past the end of the paper text "
                    f"({total} characters). Use an offset below {total}."
                )

            end = min(offset + config.max_fetch_chars, total)
            if end < total:
                # Prefer to end the page on a paragraph break, else between words.
                floor = offset + config.max_fetch_chars // 2
                # The separator stays on this page so the next one starts clean.
                cut = text.rfind("\n\n", floor, end - 1)
                if cut != -1:
                    end = cut + 2
                else:
                    cut = max(text.rfind(" ", floor, end), text.rfind("\n", floor, end))
                    if cut != -1:
                        end = cut + 1
            chunk = text[offset:end]
            next_offset = end if end < total else None

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(
                    {
                        "id": clean,
                        "source": source_url,
                        "format": source_format,
                        "total_chars": total,
                        "offset": offset,
                        "count": len(chunk),
                        "has_more": next_offset is not None,
                        "next_offset": next_offset,
                        "text": chunk,
                    },
                    indent=2,
                )

            note = (
                " (text extracted from the PDF; layout, tables and formulas "
                "may be imperfect)"
                if source_format == "pdf"
                else ""
            )
            suffix = (
                f"\n\n… [more text available — call again with "
                f"offset={next_offset} to continue; full paper: {source_url}]"
                if next_offset is not None
                else ""
            )
            return (
                f"# Paper Text: {clean}\nSource: {source_url}{note}\n"
                f"Characters {offset}–{end} of {total}\n\n{chunk}{suffix}"
            )

        # Fallback: return full abstract from API using same client
        _, papers = await _fetch_arxiv(
            {"id_list": clean}, config, client, cache=_cache, limiter=_limiter
        )
        if not papers:
            raise ToolError(
                f"Paper '{clean}' not found. Verify the ID with arxiv_search."
            )

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
            f"*The full text could not be extracted for this paper. "
            f"Read it at: {p['pdf_url']}*"
        )

    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(_handle_error(exc)) from exc


@mcp.tool(
    name="arxiv_related_papers",
    title="Find related papers",
    annotations=_read_only("Find related papers"),
)
async def arxiv_related_papers(params: RelatedPapersInput) -> str:
    """Find papers related to a known arXiv paper: similar, cited, or citing.

    arXiv has no citation or similarity data, so this tool uses Semantic
    Scholar. Results can include papers that are not on arXiv (they have no
    arXiv ID and link to Semantic Scholar instead). Very new preprints may not
    be indexed yet.

    Args:
        params (RelatedPapersInput):
            - paper_id (str): arXiv ID or URL, e.g. '1706.03762'
            - relation (str): similar | references | cited_by
            - max_results (int): Results per page (1 - 50, default 10)
            - start (int): Pagination offset (references and cited_by only)
            - response_format (str): markdown | json

    Returns:
        str: List of related papers with authors, year, citation count, link
        and abstract snippet.

        JSON schema when response_format='json':
        {
          "paper_id": str, "relation": str, "source": "semantic_scholar",
          "start": int, "count": int, "has_more": bool,
          "next_start": int | null,
          "papers": [{ "title", "authors", "year", "published", "arxiv_id",
                       "doi", "venue", "citation_count", "url", "abstract" }]
        }

    Examples:
        - Papers like Attention Is All You Need: paper_id='1706.03762'
        - What GPT-4's report builds on: paper_id='2303.08774',
          relation='references'
        - Follow-up work on Adam: paper_id='1412.6980', relation='cited_by'
    """
    clean = _clean_id(params.paper_id)
    try:
        next_start, papers = await fetch_related(
            clean,
            params.relation,
            params.max_results,
            params.start,
            config,
            _http(),
            cache=_cache,
            limiter=_s2_limiter,
        )
    except Exception as exc:
        raise ToolError(
            related_error_message(exc, clean) or _handle_error(exc)
        ) from exc

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "paper_id": clean,
                "relation": params.relation.value,
                "source": "semantic_scholar",
                "start": params.start,
                "count": len(papers),
                "has_more": next_start is not None,
                "next_start": next_start,
                "papers": papers,
            },
            indent=2,
        )

    if not papers:
        return {
            Relation.SIMILAR: f"Semantic Scholar has no recommendations for {clean}.",
            Relation.REFERENCES: f"Semantic Scholar lists no references for {clean}"
            + (" beyond this offset." if params.start else "."),
            Relation.CITED_BY: f"Semantic Scholar lists no citing papers for {clean}"
            + (" beyond this offset." if params.start else "."),
        }[params.relation]

    return format_related(papers, clean, params.relation, params.start, next_start)


# MARK: Entry Point


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
