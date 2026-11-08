"""Tests for Config defaults and environment-variable overrides."""
import pytest

from arxiv_query_mcp import __version__
from arxiv_query_mcp.config import Config

_ENV_VARS = [
    "ARXIV_MCP_SKILL_URL",
    "ARXIV_API_URL",
    "ARXIV_MCP_CACHE_DIR",
    "ARXIV_MCP_L1_TTL",
    "ARXIV_MCP_L2_TTL",
    "ARXIV_MCP_NEGATIVE_TTL",
    "ARXIV_MCP_L1_MAXSIZE",
    "ARXIV_MCP_RATE_LIMIT_PERIOD",
    "ARXIV_MCP_MAX_CONCURRENCY",
    "ARXIV_MCP_MAX_RETRIES",
    "ARXIV_MCP_BACKOFF_BASE",
    "ARXIV_MCP_BACKOFF_MAX",
    "ARXIV_MCP_USER_AGENT",
    "ARXIV_MCP_CACHE_ENABLED",
    "ARXIV_MCP_RATE_LIMIT_ENABLED",
    "ARXIV_MCP_REQUEST_TIMEOUT",
    "ARXIV_MCP_MAX_FETCH_CHARS",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove every recognised variable so tests start from the defaults."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_from_env_defaults_match_dataclass_defaults():
    """With nothing set, from_env() equals Config()."""
    assert Config.from_env() == Config()


def test_from_env_overrides(monkeypatch, tmp_path):
    """Each variable overrides its field with the right type."""
    monkeypatch.setenv("ARXIV_MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("ARXIV_MCP_L1_TTL", "12.5")
    monkeypatch.setenv("ARXIV_MCP_L1_MAXSIZE", "7")
    monkeypatch.setenv("ARXIV_MCP_MAX_RETRIES", "9")
    monkeypatch.setenv("ARXIV_MCP_USER_AGENT", "custom/1.0")
    monkeypatch.setenv("ARXIV_MCP_REQUEST_TIMEOUT", "5")
    monkeypatch.setenv("ARXIV_API_URL", "https://example.test/api")

    cfg = Config.from_env()

    assert cfg.cache_dir == str(tmp_path)
    assert cfg.l1_ttl == 12.5
    assert cfg.l1_maxsize == 7
    assert cfg.max_retries == 9
    assert cfg.user_agent == "custom/1.0"
    assert cfg.request_timeout == 5.0
    assert cfg.arxiv_api_url == "https://example.test/api"


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off"])
def test_from_env_bool_false_values(monkeypatch, raw):
    """Falsy spellings disable the boolean switches."""
    monkeypatch.setenv("ARXIV_MCP_CACHE_ENABLED", raw)
    monkeypatch.setenv("ARXIV_MCP_RATE_LIMIT_ENABLED", raw)
    cfg = Config.from_env()
    assert cfg.cache_enabled is False
    assert cfg.rate_limit_enabled is False


@pytest.mark.parametrize("raw", ["1", "true", "yes", "on"])
def test_from_env_bool_true_values(monkeypatch, raw):
    """Truthy spellings keep the switches enabled."""
    monkeypatch.setenv("ARXIV_MCP_CACHE_ENABLED", raw)
    assert Config.from_env().cache_enabled is True


def test_from_env_invalid_int_names_the_variable(monkeypatch):
    """A bad integer raises a ValueError that names the variable."""
    monkeypatch.setenv("ARXIV_MCP_MAX_RETRIES", "abc")
    with pytest.raises(ValueError, match="ARXIV_MCP_MAX_RETRIES"):
        Config.from_env()


def test_from_env_invalid_float_names_the_variable(monkeypatch):
    """A bad float raises a ValueError that names the variable."""
    monkeypatch.setenv("ARXIV_MCP_L1_TTL", "soon")
    with pytest.raises(ValueError, match="ARXIV_MCP_L1_TTL"):
        Config.from_env()


def test_default_user_agent_contains_package_version():
    """The default User-Agent tracks the installed package version."""
    assert f"arxiv-query-mcp/{__version__}" in Config().user_agent


def test_resolved_cache_dir_prefers_explicit_value(tmp_path):
    """An explicit cache_dir is returned unchanged."""
    assert Config(cache_dir=str(tmp_path)).resolved_cache_dir == str(tmp_path)


def test_resolved_cache_dir_default_is_non_empty():
    """Without cache_dir a platform default path is used."""
    assert "arxiv-query-mcp" in Config().resolved_cache_dir


def test_skill_url_default_points_to_skill_md():
    """The default skill URL ends in the shipped SKILL.md path."""
    assert Config().skill_url.endswith("skills/arxiv-query-mcp/SKILL.md")


def test_skill_url_env_override_and_disable(monkeypatch):
    """ARXIV_MCP_SKILL_URL overrides the URL; an empty value disables it."""
    monkeypatch.setenv("ARXIV_MCP_SKILL_URL", "https://example.test/SKILL.md")
    assert Config.from_env().skill_url == "https://example.test/SKILL.md"
    monkeypatch.setenv("ARXIV_MCP_SKILL_URL", "")
    assert Config.from_env().skill_url == ""
