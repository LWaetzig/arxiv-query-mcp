from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration for the arXiv MCP server.

    All fields have sensible defaults so no environment variables or files are
    required. Instantiate once at module level and share across tools.

    Attributes:
        arxiv_api_url: Base URL for the arXiv Atom API.
        arxiv_abs_base: Base URL for arXiv abstract pages.
        arxiv_html_base: Base URL for arXiv HTML paper pages.
        arxiv_pdf_base: Base URL for arXiv PDF download pages.
        request_timeout: Seconds before an outgoing HTTP request times out.
        max_fetch_chars: Maximum characters returned by arxiv_fetch_paper_text.
    """

    arxiv_api_url: str = "https://export.arxiv.org/api/query"
    arxiv_abs_base: str = "https://arxiv.org/abs"
    arxiv_html_base: str = "https://arxiv.org/html"
    arxiv_pdf_base: str = "https://arxiv.org/pdf"
    request_timeout: float = 30.0
    max_fetch_chars: int = 10_000
