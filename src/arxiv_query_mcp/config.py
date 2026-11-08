from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

from . import __version__


DEFAULT_SKILL_URL = (
    "https://raw.githubusercontent.com/LWaetzig/arxiv-query-mcp/main/"
    "skills/arxiv-query-mcp/SKILL.md"
)


def _default_user_agent() -> str:
    """Return the default User-Agent string including the package version."""
    return (
        f"arxiv-query-mcp/{__version__} (https://github.com/LWaetzig/arxiv-query-mcp; "
        "MCP server for academic paper search)"
    )


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration for the arXiv MCP server.

    All fields have sensible defaults so no environment variables or files are
    required. Instantiate once at module level and share across tools.

    Use :meth:`from_env` to create an instance that respects environment-variable
    overrides, which is what the server lifespan does.

    Attributes:
        arxiv_api_url: Base URL for the arXiv Atom API.
        arxiv_abs_base: Base URL for arXiv abstract pages.
        arxiv_html_base: Base URL for arXiv HTML paper pages.
        arxiv_pdf_base: Base URL for arXiv PDF download pages.
        request_timeout: Seconds before an outgoing HTTP request times out.
        max_fetch_chars: Maximum characters returned by arxiv_fetch_paper_text.
        cache_dir: Directory for the persistent L2 disk cache.  Empty string
            means "use the platform default via platformdirs or a temp dir".
        l1_ttl: Time-to-live (seconds) for in-memory L1 cache entries.
        l2_ttl: Time-to-live (seconds) for disk L2 cache entries.
        negative_ttl: TTL (seconds) for empty / not-found cache entries.
        l1_maxsize: Maximum number of entries kept in the L1 in-memory cache.
        rate_limit_period: Minimum seconds between consecutive arXiv requests
            (cross-process, enforced via diskcache).
        max_concurrency: Maximum simultaneous in-process HTTP requests
            (asyncio.Semaphore bound).
        max_retries: Maximum number of attempts made by resilient_get before
            re-raising the final exception.
        backoff_base: Initial exponential-backoff interval in seconds.
        backoff_max: Maximum exponential-backoff interval in seconds.
        user_agent: User-Agent header sent with every outgoing request.
        cache_enabled: When False the cache layer is a transparent pass-through.
        rate_limit_enabled: When False rate limiting and the semaphore are skipped.
        skill_url: URL of the agent ``SKILL.md`` that explains how and when to
            use this server.  It is advertised to clients in the server
            instructions.  An empty string disables the notice.
    """

    # ---- existing fields ----
    arxiv_api_url: str = "https://export.arxiv.org/api/query"
    arxiv_abs_base: str = "https://arxiv.org/abs"
    arxiv_html_base: str = "https://arxiv.org/html"
    arxiv_pdf_base: str = "https://arxiv.org/pdf"
    request_timeout: float = 30.0
    max_fetch_chars: int = 10_000

    # ---- resilience / caching fields ----
    cache_dir: str = ""
    l1_ttl: float = 300.0
    l2_ttl: float = 14_400.0
    negative_ttl: float = 60.0
    l1_maxsize: int = 256
    rate_limit_period: float = 3.0
    max_concurrency: int = 2
    max_retries: int = 4
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    user_agent: str = field(default_factory=_default_user_agent)
    cache_enabled: bool = True
    rate_limit_enabled: bool = True
    skill_url: str = DEFAULT_SKILL_URL

    @property
    def resolved_cache_dir(self) -> str:
        """Return the effective cache directory, resolving the platform default.

        Returns:
            An absolute path string.  When :attr:`cache_dir` is non-empty it is
            returned as-is; otherwise the platform user-cache directory (via
            ``platformdirs``) is used, falling back to a subdirectory of the
            system temp directory if ``platformdirs`` is unavailable.
        """
        if self.cache_dir:
            return self.cache_dir
        try:
            from platformdirs import user_cache_dir

            return user_cache_dir("arxiv-query-mcp")
        except Exception:
            return os.path.join(tempfile.gettempdir(), "arxiv-query-mcp")

    @classmethod
    def from_env(cls) -> Config:
        """Construct a :class:`Config` with environment-variable overrides.

        Each field can be overridden by a corresponding environment variable.
        Unset variables fall back to the field's default value.

        Environment variables recognised:
            ``ARXIV_API_URL``, ``ARXIV_MCP_CACHE_DIR``, ``ARXIV_MCP_L1_TTL``,
            ``ARXIV_MCP_L2_TTL``, ``ARXIV_MCP_NEGATIVE_TTL``,
            ``ARXIV_MCP_L1_MAXSIZE``, ``ARXIV_MCP_RATE_LIMIT_PERIOD``,
            ``ARXIV_MCP_MAX_CONCURRENCY``, ``ARXIV_MCP_MAX_RETRIES``,
            ``ARXIV_MCP_BACKOFF_BASE``, ``ARXIV_MCP_BACKOFF_MAX``,
            ``ARXIV_MCP_USER_AGENT``, ``ARXIV_MCP_CACHE_ENABLED``,
            ``ARXIV_MCP_RATE_LIMIT_ENABLED``, ``ARXIV_MCP_REQUEST_TIMEOUT``,
            ``ARXIV_MCP_MAX_FETCH_CHARS``, ``ARXIV_MCP_SKILL_URL``.

        Returns:
            A fully populated, immutable :class:`Config` instance.

        Raises:
            ValueError: If a numeric variable is set to a non-numeric value. The
                message names the offending variable.
        """

        def _str(key: str, default: str) -> str:
            return os.environ.get(key, default)

        def _float(key: str, default: float) -> float:
            val = os.environ.get(key)
            if val is None:
                return default
            try:
                return float(val)
            except ValueError:
                raise ValueError(
                    f"Invalid value for {key}: {val!r} (expected a number)"
                ) from None

        def _int(key: str, default: int) -> int:
            val = os.environ.get(key)
            if val is None:
                return default
            try:
                return int(val)
            except ValueError:
                raise ValueError(
                    f"Invalid value for {key}: {val!r} (expected an integer)"
                ) from None

        def _bool(key: str, default: bool) -> bool:
            val = os.environ.get(key)
            if val is None:
                return default
            return val.lower() not in ("0", "false", "no", "off")

        defaults = cls()
        return cls(
            arxiv_api_url=_str("ARXIV_API_URL", defaults.arxiv_api_url),
            arxiv_abs_base=defaults.arxiv_abs_base,
            arxiv_html_base=defaults.arxiv_html_base,
            arxiv_pdf_base=defaults.arxiv_pdf_base,
            request_timeout=_float("ARXIV_MCP_REQUEST_TIMEOUT", defaults.request_timeout),
            max_fetch_chars=_int("ARXIV_MCP_MAX_FETCH_CHARS", defaults.max_fetch_chars),
            cache_dir=_str("ARXIV_MCP_CACHE_DIR", defaults.cache_dir),
            l1_ttl=_float("ARXIV_MCP_L1_TTL", defaults.l1_ttl),
            l2_ttl=_float("ARXIV_MCP_L2_TTL", defaults.l2_ttl),
            negative_ttl=_float("ARXIV_MCP_NEGATIVE_TTL", defaults.negative_ttl),
            l1_maxsize=_int("ARXIV_MCP_L1_MAXSIZE", defaults.l1_maxsize),
            rate_limit_period=_float(
                "ARXIV_MCP_RATE_LIMIT_PERIOD", defaults.rate_limit_period
            ),
            max_concurrency=_int("ARXIV_MCP_MAX_CONCURRENCY", defaults.max_concurrency),
            max_retries=_int("ARXIV_MCP_MAX_RETRIES", defaults.max_retries),
            backoff_base=_float("ARXIV_MCP_BACKOFF_BASE", defaults.backoff_base),
            backoff_max=_float("ARXIV_MCP_BACKOFF_MAX", defaults.backoff_max),
            user_agent=_str("ARXIV_MCP_USER_AGENT", defaults.user_agent),
            cache_enabled=_bool("ARXIV_MCP_CACHE_ENABLED", defaults.cache_enabled),
            rate_limit_enabled=_bool(
                "ARXIV_MCP_RATE_LIMIT_ENABLED", defaults.rate_limit_enabled
            ),
            skill_url=_str("ARXIV_MCP_SKILL_URL", defaults.skill_url),
        )
