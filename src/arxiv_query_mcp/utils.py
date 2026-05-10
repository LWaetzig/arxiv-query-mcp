import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import httpx

from .config import Config

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
    match = re.search(r"(?:abs|pdf|html)/(.+)$", raw)
    candidate = match.group(1) if match else raw.strip()
    return re.sub(r"v\d+$", "", candidate).strip("/")


def _parse_entry(entry: ET.Element, cfg: Config) -> dict:
    """Convert one Atom <entry> element to a paper metadata dict.

    Args:
        entry: An XML element representing a single arXiv paper entry.
        cfg: Server configuration providing base URLs for links.

    Returns:
        A dict with keys: id, title, authors, abstract, published, updated,
        primary_category, categories, abstract_url, pdf_url, html_url,
        comment, journal_ref, doi.
    """

    def text(tag: str, ns: str = "atom") -> str:
        el = entry.find(f"{{{_NS[ns]}}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    raw_id = text("id")
    paper_id = _clean_id(raw_id)

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
        "title": text("title").replace("\n", " ").strip(),
        "authors": authors,
        "abstract": text("summary").replace("\n", " ").strip(),
        "published": text("published"),
        "updated": text("updated"),
        "primary_category": primary_cat,
        "categories": categories,
        "abstract_url": abs_url,
        "pdf_url": pdf_url,
        "html_url": f"{cfg.arxiv_html_base}/{paper_id}",
        "comment": opt("comment"),
        "journal_ref": opt("journal_ref"),
        "doi": opt("doi"),
    }


async def _fetch_arxiv(
    params: dict,
    cfg: Config,
    client: httpx.AsyncClient,
) -> tuple[int, list[dict]]:
    """Call the arXiv Atom API and return parsed results.

    Args:
        params: Query parameters forwarded verbatim to the API
            (e.g. ``search_query``, ``id_list``, ``start``, ``max_results``).
        cfg: Server configuration (API URL, base URLs for links).
        client: Shared async HTTP client managed by the server lifespan.

    Returns:
        A tuple of ``(total_results, papers)`` where ``papers`` is a list of
        dicts produced by :func:`_parse_entry`.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses from arXiv.
        xml.etree.ElementTree.ParseError: If the response body is not valid XML.
    """
    response = await client.get(cfg.arxiv_api_url, params=params)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    total_el = root.find(f"{{{_NS['opensearch']}}}totalResults")
    total = int(total_el.text) if total_el is not None and total_el.text else 0
    papers = [_parse_entry(e, cfg) for e in root.findall(f"{{{_NS['atom']}}}entry")]
    return total, papers


def _handle_error(exc: Exception) -> str:
    """Return a user-friendly, actionable error string for a caught exception.

    Recognises common arXiv API errors (400 bad query, 429 rate limit, timeouts)
    and produces a plain-text message that can be returned directly as a tool
    result without leaking internal stack details.

    Args:
        exc: The exception to convert.

    Returns:
        A human-readable ``"Error: …"`` string describing the problem and, where
        possible, suggesting a remediation step.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 400:
            return "Error: Invalid query syntax. Example: 'ti:attention AND cat:cs.LG'."
        if code == 429:
            return "Error: Rate limit exceeded. Wait a few seconds and retry."
        return f"Error: arXiv API returned HTTP {code}."
    if isinstance(exc, httpx.TimeoutException):
        return "Error: Request to arXiv timed out. Please try again."
    if isinstance(exc, ET.ParseError):
        return "Error: Could not parse arXiv API response XML."
    return f"Error: {type(exc).__name__}: {exc}"


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
    """

    _SKIP_TAGS: frozenset[str] = frozenset({"script", "style", "nav", "header", "footer"})

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._article_parts: list[str] = []
        self._skip_depth = 0
        self._article_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        """Increment depth counters for skip and article tags."""
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "article":
            self._article_depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Decrement depth counters when leaving skip and article tags."""
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "article":
            self._article_depth = max(0, self._article_depth - 1)

    def handle_data(self, data: str) -> None:
        """Accumulate visible text, routing article content to a separate buffer."""
        if self._skip_depth > 0:
            return
        self._parts.append(data)
        if self._article_depth > 0:
            self._article_parts.append(data)

    def get_text(self) -> str:
        """Return extracted text, collapsing whitespace.

        Returns:
            Article body text if an ``<article>`` element was found; otherwise
            all visible page text. Consecutive whitespace is collapsed to a
            single space.
        """
        source = self._article_parts if self._article_parts else self._parts
        return re.sub(r"\s+", " ", "".join(source)).strip()


def _strip_html(html: str) -> str:
    """Convert an HTML document to plain text using :class:`_TextExtractor`.

    Args:
        html: Raw HTML string (e.g. from an arXiv paper HTML page).

    Returns:
        Visible text with collapsed whitespace. Article body content is
        preferred over full-page text when an ``<article>`` element exists.
    """
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()
