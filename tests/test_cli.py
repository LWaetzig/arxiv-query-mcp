import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from arxiv_query_mcp.cli import clients, skill
from arxiv_query_mcp.cli import targets as target_mod


def test_bundled_skill_has_frontmatter() -> None:
    assert skill.bundled_skill().startswith("---")


def test_fetch_skill_falls_back_to_bundled_on_network_error() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("offline")):
        text, source = skill.fetch_skill("https://example.invalid/SKILL.md")
    assert source == "bundled copy"
    assert text == skill.bundled_skill()


def test_fetch_skill_rejects_non_https() -> None:
    _, source = skill.fetch_skill("http://example.com/SKILL.md")
    assert source == "bundled copy"


SKILL = "---\nname: x\ndescription: Find papers.\n---\n# Body\n"


def _install(targets, root, force=False):
    with patch.object(target_mod, "fetch_skill", return_value=(SKILL, "test")):
        return target_mod.install_skill(targets, root, force)


def test_claude_project_install_is_idempotent_and_no_clobber(tmp_path: Path) -> None:
    dst = tmp_path / ".claude" / "skills" / "arxiv-query-mcp" / "SKILL.md"
    assert _install(["claude"], tmp_path)[0][1] == "installed"
    assert dst.read_text() == SKILL
    assert _install(["claude"], tmp_path)[0][1] == "current"
    dst.write_text("custom")
    assert _install(["claude"], tmp_path)[0][1] == "skipped"
    assert dst.read_text() == "custom"
    assert _install(["claude"], tmp_path, force=True)[0][1] == "installed"
    assert dst.read_text() == SKILL


def test_cursor_rule_has_frontmatter_and_body(tmp_path: Path) -> None:
    _install(["cursor"], tmp_path)
    text = (tmp_path / ".cursor/rules/arxiv-query-mcp.mdc").read_text()
    assert text.startswith("---\ndescription: Find papers.\nalwaysApply: false\n---")
    assert text.endswith("# Body\n")


def test_windsurf_rule(tmp_path: Path) -> None:
    _install(["windsurf"], tmp_path)
    text = (tmp_path / ".windsurf/rules/arxiv-query-mcp.md").read_text()
    assert "trigger: model_decision" in text


def test_agents_md_block_preserves_existing_content(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Mine\nkeep me\n")
    assert _install(["agents"], tmp_path)[0][1] == "installed"
    text = agents.read_text()
    assert text.startswith("# Mine\nkeep me\n")
    assert text.count(skill.BLOCK_BEGIN) == 1
    assert ".agents/skills/arxiv-query-mcp/SKILL.md" in text
    assert (
        tmp_path / ".agents/skills/arxiv-query-mcp/SKILL.md"
    ).read_text() == SKILL
    assert _install(["agents"], tmp_path)[0][1] == "current"
    assert agents.read_text().count(skill.BLOCK_BEGIN) == 1


def test_gemini_creates_file_and_shares_skill(tmp_path: Path) -> None:
    _install(["agents", "gemini"], tmp_path)
    assert (tmp_path / "GEMINI.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_detect_targets(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    (tmp_path / "AGENTS.md").write_text("")
    found = target_mod.detect_targets(tmp_path)
    assert {"cursor", "agents", "claude-user"} <= set(found)
    assert "windsurf" not in found


def test_update_claude_desktop_preserves_other_servers(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "k": 1}))
    assert clients.update_claude_desktop(cfg, "/bin/arxiv")
    data = json.loads(cfg.read_text())
    assert data["k"] == 1
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["arxiv"] == {"command": "/bin/arxiv"}


def test_update_claude_desktop_keeps_existing_env(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "arxiv": {"command": "old", "env": {"ARXIV_MCP_L2_TTL": "5"}}
                }
            }
        )
    )
    clients.update_claude_desktop(cfg, "new")
    entry = json.loads(cfg.read_text())["mcpServers"]["arxiv"]
    assert entry == {"command": "new", "env": {"ARXIV_MCP_L2_TTL": "5"}}


def test_update_claude_desktop_refuses_invalid_json(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text("{not json")
    assert clients.update_claude_desktop(cfg, "x") is False
    assert cfg.read_text() == "{not json"


def test_update_claude_code_carries_over_env(tmp_path: Path) -> None:
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {"mcpServers": {"arxiv": {"env": {"ARXIV_MCP_L2_TTL": "86400"}}}}
        )
    )
    calls: list[list[str]] = []

    def fake_run(argv, **_kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    with (
        patch.object(Path, "home", return_value=tmp_path),
        patch("shutil.which", return_value="/bin/claude"),
        patch("subprocess.run", side_effect=fake_run),
    ):
        assert clients.update_claude_code("/bin/arxiv")
    add = calls[-1]
    assert add[:3] == ["/bin/claude", "mcp", "add"]
    assert add[add.index("-e") + 1] == "ARXIV_MCP_L2_TTL=86400"
    assert add[-2:] == ["--", "/bin/arxiv"]


def test_existing_claude_code_env_missing_file(tmp_path: Path) -> None:
    with patch.object(Path, "home", return_value=tmp_path):
        assert clients.existing_claude_code_env() == {}


def test_update_claude_code_restores_previous_entry_on_failure(tmp_path: Path) -> None:
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "arxiv": {
                        "command": "old",
                        "args": ["x"],
                        "env": {"A": "1"},
                    }
                }
            }
        )
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        adds = [c for c in calls if "add" in c]
        code = 1 if len(adds) == 1 and "add" in argv else 0
        return subprocess.CompletedProcess(argv, code, "", "boom")

    with (
        patch.object(Path, "home", return_value=tmp_path),
        patch("shutil.which", return_value="/bin/claude"),
        patch("subprocess.run", side_effect=fake_run),
    ):
        assert clients.update_claude_code("new") is False
    last = calls[-1]
    assert last[last.index("--") + 1 :] == ["old", "x"]
    assert "A=1" in last
