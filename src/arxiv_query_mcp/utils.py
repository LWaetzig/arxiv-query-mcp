from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

import httpx
from pypdf import PdfReader

from .config import Config

if TYPE_CHECKING:
    from .cache import TwoTierCache
    from .ratelimit import RateLimiter

_NS: dict[str, str] = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def _clean_id(raw: str) -> str:
    """Extract a clean, version-stripped arXiv ID from a URL or raw string.

    Handles full arXiv URLs (abs/pdf/html paths), bare IDs with version suffixes
    (e.g. '2303.08774v2'), and old-style category IDs ('hep-th/9901001').

    Args:
        raw: Raw input — a URL, a versioned ID, or a plain ID string.

    Returns:
        Normalised arXiv ID with no version suffix and no trailing slash,
        e.g. '2303.08774' or 'hep-th/9901001'.
    """
    return re.sub(r"v\d+$", "", _versioned_id(raw))


def _versioned_id(raw: str) -> str:
    """Extract an arXiv ID from a URL or raw string, keeping any version.

    Use this for IDs supplied by a caller, so that asking for
    ``'1706.03762v2'`` addresses that version instead of the latest one.

    Args:
        raw: Raw input — a URL, a versioned ID, or a plain ID string.

    Returns:
        The arXiv ID without surrounding URL parts or slashes, e.g.
        ``'2303.08774'``, ``'2303.08774v2'`` or ``'hep-th/9901001'``.
    """
    match = re.search(r"(?:abs|pdf|html)/(.+)$", raw.strip())
    candidate = match.group(1) if match else raw.strip()
    return candidate.strip("/")


def _id_version(raw: str) -> str:
    """Return the version suffix of an arXiv ID or URL.

    Args:
        raw: An arXiv ID or URL, with or without a version.

    Returns:
        The suffix such as ``'v2'``, or an empty string when there is none.
    """
    match = re.search(r"v\d+$", _versioned_id(raw))
    return match.group(0) if match else ""


def _with_date_filter(
    query: str, date_from: date | None, date_to: date | None
) -> str:
    """Restrict *query* to papers submitted within an inclusive date range.

    arXiv's ``submittedDate:[A TO B]`` filter needs both bounds, so a missing
    bound is replaced by a date far enough in the past or future to be open.

    Args:
        query: arXiv search query (field prefixes and boolean operators).
        date_from: First submission day to include, or ``None`` for no lower
            bound.
        date_to: Last submission day to include, or ``None`` for no upper
            bound.

    Returns:
        *query* unchanged when both bounds are ``None``; otherwise the query
        in parentheses combined with a ``submittedDate`` clause via ``AND``.
    """
    if date_from is None and date_to is None:
        return query
    lower = f"{date_from:%Y%m%d}0000" if date_from else "190001010000"
    upper = f"{date_to:%Y%m%d}2359" if date_to else "999912312359"
    return f"({query}) AND submittedDate:[{lower} TO {upper}]"


def _date_range_label(date_from: date | None, date_to: date | None) -> str:
    """Describe a submission-date range for result headings.

    Args:
        date_from: Lower bound, or ``None``.
        date_to: Upper bound, or ``None``.

    Returns:
        A suffix such as ``" (submitted 2026-01-01 to 2026-01-31)"``, or an
        empty string when no bound is set.
    """
    if date_from and date_to:
        return f" (submitted {date_from} to {date_to})"
    if date_from:
        return f" (submitted since {date_from})"
    if date_to:
        return f" (submitted until {date_to})"
    return ""


def _parse_entry(entry: ET.Element, cfg: Config) -> dict:
    """Convert one Atom <entry> element to a paper metadata dict.

    Args:
        entry: An XML element representing a single arXiv paper entry.
        cfg: Server configuration providing base URLs for links.

    Returns:
        A dict with keys: id, version, title, authors, abstract, published, updated,
        primary_category, categories, abstract_url, pdf_url, html_url,
        comment, journal_ref, doi.
    """

    def text(tag: str, ns: str = "atom") -> str:
        el = entry.find(f"{{{_NS[ns]}}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    raw_id = text("id")
    paper_id = _clean_id(raw_id)
    version = _id_version(raw_id)

    authors = []
    for a in entry.findall(f"{{{_NS['atom']}}}author"):
        name_el = a.find(f"{{{_NS['atom']}}}name")
        if name_el is not None and name_el.text is not None:
            authors.append(name_el.text.strip())

    categories = [
        cat.get("term", "")
        for cat in entry.findall(f"{{{_NS['atom']}}}category")
        if cat.get("term")
    ]

    pdf_url = abs_url = ""
    for link in entry.findall(f"{{{_NS['atom']}}}link"):
        rel = link.get("rel", "")
        typ = link.get("type", "")
        href = link.get("href", "")
        if typ == "application/pdf" or link.get("title") == "pdf":
            pdf_url = href
        elif rel == "alternate" or typ == "text/html":
            abs_url = href

    if not abs_url:
        abs_url = f"{cfg.arxiv_abs_base}/{paper_id}"
    if not pdf_url:
        pdf_url = f"{cfg.arxiv_pdf_base}/{paper_id}"

    def opt(tag: str, ns: str = "arxiv") -> str:
        el = entry.find(f"{{{_NS[ns]}}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    primary_cat_el = entry.find(f"{{{_NS['arxiv']}}}primary_category")
    primary_cat = (
        primary_cat_el.get("term", "")
        if primary_cat_el is not None
        else (categories[0] if categories else "")
    )

    return {
        "id": paper_id,
        "version": version,
        "title": text("title").replace("\n", " ").strip(),
        "authors": authors,
        "abstract": text("summary").replace("\n", " ").strip(),
        "published": text("published"),
        "updated": text("updated"),
        "primary_category": primary_cat,
        "categories": categories,
        "abstract_url": abs_url,
        "pdf_url": pdf_url,
        "html_url": f"{cfg.arxiv_html_base}/{paper_id}{version}",
        "comment": opt("comment"),
        "journal_ref": opt("journal_ref"),
        "doi": opt("doi"),
    }


def _parse_atom_response(
    text: str,
    cfg: Config,
) -> tuple[int, list[dict]]:
    """Parse an arXiv Atom API XML response body into structured data.

    Args:
        text: Raw XML response text from the arXiv API.
        cfg: Server configuration providing base URLs for building paper links.

    Returns:
        A tuple of ``(total_results, papers)`` where ``papers`` is a list of
        dicts produced by :func:`_parse_entry`.

    Raises:
        xml.etree.ElementTree.ParseError: If *text* is not valid XML.
    """
    root = ET.fromstring(text)
    total_el = root.find(f"{{{_NS['opensearch']}}}totalResults")
    total = int(total_el.text) if total_el is not None and total_el.text else 0
    papers = [_parse_entry(e, cfg) for e in root.findall(f"{{{_NS['atom']}}}entry")]
    return total, papers


async def _fetch_arxiv(
    params: dict[str, Any],
    cfg: Config,
    client: httpx.AsyncClient,
    *,
    cache: TwoTierCache | None = None,
    limiter: RateLimiter | None = None,
) -> tuple[int, list[dict]]:
    """Call the arXiv Atom API and return parsed results.

    When both *cache* and *limiter* are provided the call is routed through the
    two-tier cache and the cross-process rate limiter with tenacity retry.
    Otherwise a direct ``client.get`` is used (backwards-compatible path that
    keeps unit tests simple when the resilience layer is not required).

    Args:
        params: Query parameters forwarded verbatim to the API
            (e.g. ``search_query``, ``id_list``, ``start``, ``max_results``).
        cfg: Server configuration (API URL, base URLs for links).
        client: Shared async HTTP client managed by the server lifespan.
        cache: Optional :class:`~arxiv_query_mcp.cache.TwoTierCache` instance.
            When ``None`` the caching layer is bypassed.
        limiter: Optional :class:`~arxiv_query_mcp.ratelimit.RateLimiter`
            instance.  When ``None`` the rate-limiting layer is bypassed.

    Returns:
        A tuple of ``(total_results, papers)`` where ``papers`` is a list of
        dicts produced by :func:`_parse_entry`.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses from arXiv.
        xml.etree.ElementTree.ParseError: If the response body is not valid XML.
    """
    if cache is not None and limiter is not None:
        from .ratelimit import resilient_get

        cache_key: tuple[object, ...] = ("api", tuple(sorted(params.items())))
        _limiter = limiter  # capture for closure

        async def _do_fetch() -> tuple[int, list[dict]]:
            response = await resilient_get(
                client,
                cfg.arxiv_api_url,
                params=dict(params),
                cfg=cfg,
                limiter=_limiter,
            )
            return _parse_atom_response(response.text, cfg)

        return await cache.get_or_fetch(cache_key, _do_fetch)

    # Legacy / test path: direct HTTP call with no caching or rate limiting.
    response = await client.get(cfg.arxiv_api_url, params=params)
    response.raise_for_status()
    return _parse_atom_response(response.text, cfg)


def _handle_error(exc: Exception) -> str:
    """Return a user-friendly, actionable error string for a caught exception.

    Recognises common arXiv API errors (400 bad query, 429 rate limit, timeouts)
    and produces a plain-text message for a tool error result (the caller raises
    it as a ``ToolError``) without leaking internal stack details.

    Args:
        exc: The exception to convert.

    Returns:
        A human-readable ``"…"`` string describing the problem and, where
        possible, suggesting a remediation step.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 400:
            return "Invalid query syntax. Example: 'ti:attention AND cat:cs.LG'."
        if code == 429:
            return "Rate limit exceeded. Wait a few seconds and retry."
        return f"arXiv API returned HTTP {code}."
    if isinstance(exc, httpx.TimeoutException):
        return "Request to arXiv timed out. Please try again."
    if isinstance(exc, ET.ParseError):
        return "Could not parse arXiv API response XML."
    return f"{type(exc).__name__}: {exc}"


def _author_line(authors: list[str], limit: int = 5) -> str:
    """Format an author list as a compact string, truncating beyond *limit*.

    Args:
        authors: Ordered list of author name strings.
        limit: Maximum number of names to display before appending a count
            of omitted authors.

    Returns:
        Comma-separated author names, e.g. ``"Alice, Bob … (+3 more)"``.
    """
    if len(authors) <= limit:
        return ", ".join(authors)
    return ", ".join(authors[:limit]) + f" … (+{len(authors) - limit} more)"


def _format_paper_detail(paper: dict) -> str:
    """Render a single paper's full metadata as a Markdown string.

    Includes all available fields: title, ID, authors, dates, categories,
    URLs, journal reference, DOI, comment, and the full abstract.

    Args:
        paper: A paper dict as returned by :func:`_parse_entry`.

    Returns:
        A multi-line Markdown string suitable for direct display.
    """
    lines = [
        f"## {paper['title']}",
        f"**arXiv ID:** {paper['id']}",
        *([f"**Version:** {paper['version']}"] if paper.get("version") else []),
        f"**Authors:** {_author_line(paper['authors'])}",
        f"**Published:** {paper['published'][:10]}",
        f"**Last updated:** {paper['updated'][:10]}",
        f"**Primary category:** {paper['primary_category']}",
        f"**All categories:** {', '.join(paper['categories'])}",
        f"**Abstract URL:** {paper['abstract_url']}",
        f"**PDF URL:** {paper['pdf_url']}",
        f"**HTML URL:** {paper['html_url']}",
    ]
    if paper.get("journal_ref"):
        lines.append(f"**Journal:** {paper['journal_ref']}")
    if paper.get("doi"):
        lines.append(f"**DOI:** https://doi.org/{paper['doi']}")
    if paper.get("comment"):
        lines.append(f"**Comment:** {paper['comment']}")
    lines += ["", "### Abstract", paper["abstract"]]
    return "\n".join(lines)


def _format_paper_list(papers: list[dict], total: int, start: int, label: str) -> str:
    """Render a page of search results as a Markdown string.

    Each paper entry shows title, authors (up to 3), publication date,
    primary category, links, and a 250-character abstract snippet. A
    pagination hint is appended when more results exist.

    Args:
        papers: List of paper dicts for the current page.
        total: Total number of results matching the query (may exceed this page).
        start: Zero-based offset of the first result on this page.
        label: Human-readable label displayed in the heading (query or category).

    Returns:
        A multi-line Markdown string with one section per paper.
    """
    lines = [
        f"# arXiv Search: {label}",
        f"Showing {len(papers)} of {total} results (offset: {start})",
        "",
    ]
    for p in papers:
        short_abs = p["abstract"][:250] + ("…" if len(p["abstract"]) > 250 else "")
        lines += [
            f"### [{p['id']}] {p['title']}",
            f"**Authors:** {_author_line(p['authors'], 3)}",
            f"**Published:** {p['published'][:10]}  |  **Category:** {p['primary_category']}",
            f"**Links:** [Abstract]({p['abstract_url']}) · [PDF]({p['pdf_url']}) · [HTML]({p['html_url']})",
            short_abs,
            "",
        ]
    if total > start + len(papers):
        lines.append(f"*Use `start={start + len(papers)}` to fetch the next page.*")
    return "\n".join(lines)


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, preferring ``<article>`` body content.

    Skips content inside ``<script>``, ``<style>``, ``<nav>``, ``<header>``,
    and ``<footer>`` tags. When an ``<article>`` element is present the
    extracted text is taken exclusively from that element; otherwise the full
    visible page text is returned. Handles nested skipped tags correctly via
    depth counters.

    Document structure is kept as lightweight Markdown: block elements become
    paragraphs separated by a blank line, ``<h1>``-``<h6>`` become ``#``
    headings and list items are prefixed with ``-``. A ``<math>`` element is
    replaced by its LaTeX source (the ``alttext`` attribute) wrapped in ``$``
    instead of the unreadable text of its MathML children.
    """

    _SKIP_TAGS: frozenset[str] = frozenset(
        {"script", "style", "nav", "header", "footer"}
    )
    _HEADING_TAGS: frozenset[str] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
    _BLOCK_TAGS: frozenset[str] = frozenset(
        {
            "p", "div", "section", "article", "ul", "ol", "li", "table", "tr",
            "figure", "figcaption", "blockquote", "pre", "dl", "dt", "dd",
        }
    ) | _HEADING_TAGS

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._article_parts: list[str] = []
        self._skip_depth = 0
        self._article_depth = 0
        self._math_depth = 0

    def _emit(self, data: str) -> None:
        """Append *data* to the page buffer and, inside an article, to its buffer."""
        self._parts.append(data)
        if self._article_depth > 0:
            self._article_parts.append(data)

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        """Track skip/article/math depth and emit structure markers."""
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "article":
            self._article_depth += 1
        if tag == "math":
            self._math_depth += 1
            if self._math_depth == 1 and self._skip_depth == 0:
                alttext = dict(attrs).get("alttext") or ""
                if alttext.strip():
                    self._emit(f"${alttext.strip()}$")
            return
        if self._skip_depth > 0 or self._math_depth > 0:
            return
        if tag == "br":
            self._emit("\n")
        elif tag in self._BLOCK_TAGS:
            self._emit("\n\n")
            if tag in self._HEADING_TAGS:
                self._emit("#" * int(tag[1]) + " ")
            elif tag == "li":
                self._emit("- ")
        elif tag in ("td", "th"):
            self._emit(" ")

    def handle_endtag(self, tag: str) -> None:
        """Decrement depth counters and close block elements."""
        if tag == "math":
            self._math_depth = max(0, self._math_depth - 1)
        elif (
            tag in self._BLOCK_TAGS
            and self._skip_depth == 0
            and self._math_depth == 0
        ):
            self._emit("\n\n")
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "article":
            self._article_depth = max(0, self._article_depth - 1)

    def handle_data(self, data: str) -> None:
        """Accumulate visible text, routing article content to a separate buffer."""
        if self._skip_depth > 0 or self._math_depth > 0:
            return
        # Source line breaks are not meaningful in HTML; only tags create them.
        self._emit(re.sub(r"\s+", " ", data))

    def get_text(self) -> str:
        """Return extracted text with normalised whitespace.

        Returns:
            Article body text if an ``<article>`` element was found; otherwise
            all visible page text. Runs of spaces are collapsed, lines are
            trimmed, and paragraphs are separated by exactly one blank line.
        """
        source = self._article_parts if self._article_parts else self._parts
        text = re.sub(r"[ \t]+", " ", "".join(source))
        text = re.sub(r" ?\n ?", "\n", text)
        # A marker left alone on its line belongs to the text that follows it.
        text = re.sub(r"^(#{1,6}|-)\n+(?=\S)", r"\1 ", text, flags=re.M)
        text = re.sub(r"^(#{1,6}|-) ?$\n?", "", text, flags=re.M)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def _strip_html(html: str) -> str:
    """Convert an HTML document to plain text using :class:`_TextExtractor`.

    Args:
        html: Raw HTML string (e.g. from an arXiv paper HTML page).

    Returns:
        Visible text as lightweight Markdown (headings, paragraphs, list
        items, LaTeX math). Article body content is preferred over full-page
        text when an ``<article>`` element exists.
    """
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


# Typographic ligatures that PDF fonts emit as single characters.
_PDF_LIGATURES: dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}


def _pdf_to_text(data: bytes) -> str:
    """Extract the text of a PDF document.

    Pages are separated by a blank line and typographic ligatures are
    expanded to plain letters. Line breaks inside a page are kept
    as they appear in the PDF, since reflowing them would merge headings and
    table rows into the surrounding text.

    Args:
        data: Raw bytes of a PDF file.

    Returns:
        The extracted text, or an empty string when the document cannot be
        read or contains no extractable text (e.g. a scanned PDF).
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return ""
    cleaned = []
    for page in pages:
        for ligature, letters in _PDF_LIGATURES.items():
            page = page.replace(ligature, letters)
        lines = (re.sub(r"[ \t]+", " ", line).strip() for line in page.splitlines())
        text = "\n".join(line for line in lines if line)
        if text:
            cleaned.append(text)
    return "\n\n".join(cleaned)
