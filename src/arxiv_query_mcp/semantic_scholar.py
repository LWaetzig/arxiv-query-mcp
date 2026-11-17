"""Related papers (similar, references, citations) from Semantic Scholar.

arXiv itself has no similarity or citation data, so ``arxiv_related_papers``
asks the Semantic Scholar API, which indexes arXiv papers by their arXiv ID.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from .config import Config
from .models import Relation

if TYPE_CHECKING:
    from .cache import TwoTierCache
    from .ratelimit import RateLimiter

_FIELDS = (
    "title,authors,year,publicationDate,externalIds,citationCount,abstract,url,venue"
)

# Recommendation pools, tried in order. "all-cs" covers far more papers
# (including physics and maths in practice); "recent" only knows new ones.
_RECOMMENDATION_POOLS = ("all-cs", "recent")


class PaperNotIndexedError(Exception):
    """Semantic Scholar has no record of the requested arXiv paper."""


def _paper_record(raw: dict[str, Any], cfg: Config) -> dict[str, Any] | None:
    """Convert a Semantic Scholar paper object into this server's format.

    Args:
        raw: A paper object from the Semantic Scholar API.
        cfg: Server configuration providing the arXiv abstract base URL.

    Returns:
        A dict with keys ``title``, ``authors``, ``year``, ``published``,
        ``arxiv_id``, ``doi``, ``venue``, ``citation_count``, ``url`` and
        ``abstract``, or ``None`` when the entry has no title (Semantic Scholar
        lists unresolved references that way).
    """
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    ids = raw.get("externalIds") or {}
    arxiv_id = ids.get("ArXiv") or ""
    return {
        "title": title,
        "authors": [a["name"] for a in raw.get("authors") or [] if a.get("name")],
        "year": raw.get("year"),
        "published": raw.get("publicationDate") or "",
        "arxiv_id": arxiv_id,
        "doi": ids.get("DOI") or "",
        "venue": raw.get("venue") or "",
        "citation_count": raw.get("citationCount"),
        "url": f"{cfg.arxiv_abs_base}/{arxiv_id}" if arxiv_id else raw.get("url", ""),
        "abstract": (raw.get("abstract") or "").strip(),
    }


async def _get_json(
    url: str,
    params: dict[str, Any],
    cfg: Config,
    client: httpx.AsyncClient,
    limiter: RateLimiter | None,
) -> dict[str, Any]:
    """GET a Semantic Scholar endpoint and return the decoded JSON body.

    Raises:
        PaperNotIndexedError: On HTTP 404.
        httpx.HTTPStatusError: On other non-2xx responses (after retries).
    """
    from .ratelimit import resilient_get

    headers = {"x-api-key": cfg.s2_api_key} if cfg.s2_api_key else None
    try:
        if limiter is not None:
            resp = await resilient_get(
                client, url, params=params, headers=headers, cfg=cfg, limiter=limiter
            )
        else:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise PaperNotIndexedError(str(exc)) from exc
        raise
    data: dict[str, Any] = resp.json()
    return data


async def fetch_related(
    arxiv_id: str,
    relation: Relation,
    limit: int,
    offset: int,
    cfg: Config,
    client: httpx.AsyncClient,
    *,
    cache: TwoTierCache | None = None,
    limiter: RateLimiter | None = None,
) -> tuple[int | None, list[dict[str, Any]]]:
    """Fetch papers related to an arXiv paper from Semantic Scholar.

    Args:
        arxiv_id: Version-less arXiv ID, e.g. ``'1706.03762'``.
        relation: Which relation to fetch.
        limit: Maximum number of papers to return.
        offset: Pagination offset (references and citations only).
        cfg: Server configuration (API URL, key, base URLs).
        client: Shared async HTTP client.
        cache: Optional cache; results are cached like arXiv responses.
        limiter: Optional Semantic Scholar rate limiter.

    Returns:
        ``(next_offset, papers)``. ``next_offset`` is ``None`` when there are
        no further pages.

    Raises:
        PaperNotIndexedError: Semantic Scholar does not know the paper.
        httpx.HTTPStatusError: Semantic Scholar returned another error.
    """
    paper_ref = f"ARXIV:{arxiv_id}"

    async def _fetch() -> tuple[int | None, list[dict[str, Any]]]:
        if relation == Relation.SIMILAR:
            url = f"{cfg.s2_api_url}/recommendations/v1/papers/forpaper/{paper_ref}"
            for pool in _RECOMMENDATION_POOLS:
                data = await _get_json(
                    url,
                    {"fields": _FIELDS, "limit": limit, "from": pool},
                    cfg,
                    client,
                    limiter,
                )
                raw_papers = data.get("recommendedPapers") or []
                if raw_papers:
                    break
            papers = [_paper_record(p, cfg) for p in raw_papers]
            return None, [p for p in papers if p is not None]

        endpoint, key = (
            ("references", "citedPaper")
            if relation == Relation.REFERENCES
            else ("citations", "citingPaper")
        )
        data = await _get_json(
            f"{cfg.s2_api_url}/graph/v1/paper/{paper_ref}/{endpoint}",
            {"fields": _FIELDS, "limit": limit, "offset": offset},
            cfg,
            client,
            limiter,
        )
        records = [
            _paper_record(item.get(key) or {}, cfg) for item in data.get("data") or []
        ]
        next_offset = data.get("next")
        return (
            int(next_offset) if next_offset is not None else None,
            [p for p in records if p is not None],
        )

    if cache is None:
        return await _fetch()
    key = ("s2", relation.value, arxiv_id, limit, offset)
    result: tuple[int | None, list[dict[str, Any]]] = await cache.get_or_fetch(
        key, _fetch
    )
    return result


def related_error_message(exc: Exception, arxiv_id: str) -> str | None:
    """Return a helpful message for a Semantic Scholar failure, if it is one.

    Args:
        exc: The exception raised while fetching related papers.
        arxiv_id: The arXiv ID that was looked up.

    Returns:
        A message for the tool error, or ``None`` when *exc* is not specific
        to Semantic Scholar (the generic handler applies then).
    """
    if isinstance(exc, PaperNotIndexedError):
        return (
            f"Semantic Scholar has no record of arXiv paper '{arxiv_id}'. Very "
            "new papers can take a few days to be indexed; check the ID with "
            "arxiv_get_paper."
        )
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return (
                "Semantic Scholar rate limit exceeded. Wait a minute and retry; "
                "setting ARXIV_MCP_S2_API_KEY gives the server its own quota."
            )
        if code in (401, 403):
            return "Semantic Scholar rejected the API key in ARXIV_MCP_S2_API_KEY."
        return f"Semantic Scholar returned HTTP {code}."
    if isinstance(exc, httpx.TimeoutException):
        return "Request to Semantic Scholar timed out. Please try again."
    return None


def format_related(
    papers: list[dict[str, Any]],
    arxiv_id: str,
    relation: Relation,
    start: int,
    next_start: int | None,
) -> str:
    """Render related papers as Markdown.

    Args:
        papers: Records produced by :func:`_paper_record`.
        arxiv_id: The paper the results relate to.
        relation: The relation that was fetched.
        start: Offset of the first result.
        next_start: Offset of the next page, or ``None``.

    Returns:
        A Markdown list with one section per paper and a pagination hint.
    """
    heading = {
        Relation.SIMILAR: f"Papers similar to {arxiv_id}",
        Relation.REFERENCES: f"References of {arxiv_id}",
        Relation.CITED_BY: f"Papers citing {arxiv_id}",
    }[relation]
    lines = [
        f"# {heading}",
        f"Showing {len(papers)} results (offset: {start}) · source: Semantic Scholar",
        "",
    ]
    for p in papers:
        authors = ", ".join(p["authors"][:3]) + (
            f" … (+{len(p['authors']) - 3} more)" if len(p["authors"]) > 3 else ""
        )
        label = f"[{p['arxiv_id']}] " if p["arxiv_id"] else ""
        meta = [f"**Year:** {p['year'] or 'n/a'}"]
        if p["citation_count"] is not None:
            meta.append(f"**Citations:** {p['citation_count']}")
        if p["venue"]:
            meta.append(f"**Venue:** {p['venue']}")
        lines += [
            f"### {label}{p['title']}",
            f"**Authors:** {authors or 'n/a'}",
            "  |  ".join(meta),
            f"**Link:** {p['url']}" + ("" if p["arxiv_id"] else " (not on arXiv)"),
        ]
        if p["abstract"]:
            snippet = p["abstract"][:250] + ("…" if len(p["abstract"]) > 250 else "")
            lines.append(snippet)
        lines.append("")
    if next_start is not None:
        lines.append(f"*Use `start={next_start}` to fetch the next page.*")
    return "\n".join(lines)
