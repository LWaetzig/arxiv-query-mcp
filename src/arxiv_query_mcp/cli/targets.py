"""Per-agent skill destinations (Claude, Cursor, Windsurf, AGENTS.md, Gemini)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from .constants import SKILL_NAME
from .skill import (
    BLOCK_BEGIN,
    BLOCK_END,
    fetch_skill,
    split_skill,
    upsert_block,
    write_file,
)


def shared_skill(root: Path, content: str, force: bool) -> tuple[str, Path]:
    """Write the full skill to ``.agents/skills`` for pointer blocks to refer to.

    Args:
        root (Path): Project directory.
        content (str): Full SKILL.md text.
        force (bool): Overwrite a differing existing file.

    Returns:
        tuple[str, Path]: Write status and the skill file path.

    Raises:
        OSError: If the file cannot be written.
    """
    dst = root / ".agents" / "skills" / SKILL_NAME / "SKILL.md"
    return write_file(dst, content, force), dst


def pointer_block(skill_path: Path, root: Path, description: str) -> str:
    """Build the short marked block that points an agent at the skill file.

    Args:
        skill_path (Path): Location of the full skill; must be inside ``root``.
        root (Path): Project directory the path is made relative to.
        description (str): One-line skill description shown in the block.

    Returns:
        str: Markdown block including the ``BEGIN``/``END`` markers.

    Raises:
        ValueError: If ``skill_path`` is not inside ``root``.
    """
    rel = skill_path.relative_to(root).as_posix()
    return "\n".join(
        [
            BLOCK_BEGIN,
            "",
            "## arXiv search",
            "",
            description,
            "",
            f"Read `{rel}` before using the arXiv MCP tools.",
            "",
            BLOCK_END,
        ]
    )


def _t_claude(base: Path) -> Callable[..., tuple[str, Path]]:
    """Create an installer that writes ``<base>/skills/<name>/SKILL.md``.

    Args:
        base (Path): Claude config directory (``~/.claude`` or ``.claude``).

    Returns:
        Callable[..., tuple[str, Path]]: Installer taking ``(root, content, force)``.
    """

    def install(root: Path, content: str, force: bool) -> tuple[str, Path]:
        """Install the skill for one agent.

        Args:
            root (Path): Project directory.
            content (str): Full SKILL.md text.
            force (bool): Overwrite a differing existing file.

        Returns:
            tuple[str, Path]: Status (``installed``, ``current`` or
            ``skipped``) and the file written or checked.

        Raises:
            OSError: If the file cannot be written.
        """
        dst = base / "skills" / SKILL_NAME / "SKILL.md"
        return write_file(dst, content, force), dst

    return install


def _project_claude(root: Path, content: str, force: bool) -> tuple[str, Path]:
    """Install the skill into the project's ``.claude`` directory.

    Args:
        root (Path): Project directory.
        content (str): Full SKILL.md text.
        force (bool): Overwrite a differing existing file.

    Returns:
        tuple[str, Path]: Status and the file written or checked.

    Raises:
        OSError: If the file cannot be written.
    """
    return _t_claude(root / ".claude")(root, content, force)


def _t_rules(
    rel_dir: str, suffix: str, frontmatter: str
) -> Callable[..., tuple[str, Path]]:
    """Create an installer that writes the skill as an editor rule file.

    Args:
        rel_dir (str): Rules directory relative to the project root.
        suffix (str): File extension including the dot.
        frontmatter (str): Template with a ``{description}`` placeholder.

    Returns:
        Callable[..., tuple[str, Path]]: Installer taking ``(root, content, force)``.
    """

    def install(root: Path, content: str, force: bool) -> tuple[str, Path]:
        """Install the skill for one agent.

        Args:
            root (Path): Project directory.
            content (str): Full SKILL.md text.
            force (bool): Overwrite a differing existing file.

        Returns:
            tuple[str, Path]: Status (``installed``, ``current`` or
            ``skipped``) and the file written or checked.

        Raises:
            OSError: If the file cannot be written.
        """
        desc, body = split_skill(content)
        dst = root / rel_dir / f"{SKILL_NAME}{suffix}"
        text = frontmatter.format(description=desc) + "\n" + body
        return write_file(dst, text, force), dst

    return install


def _t_instructions(filename: str) -> Callable[..., tuple[str, Path]]:
    """Create an installer that adds a pointer block to an instructions file.

    Args:
        filename (str): Shared file at the project root, e.g. ``AGENTS.md``.

    Returns:
        Callable[..., tuple[str, Path]]: Installer taking ``(root, content, force)``.
    """

    def install(root: Path, content: str, force: bool) -> tuple[str, Path]:
        """Install the skill for one agent.

        Args:
            root (Path): Project directory.
            content (str): Full SKILL.md text.
            force (bool): Overwrite a differing existing file.

        Returns:
            tuple[str, Path]: Status (``installed``, ``current`` or
            ``skipped``) and the file written or checked.

        Raises:
            OSError: If the file cannot be written.
        """
        status, skill = shared_skill(root, content, force)
        if status == "skipped":
            return status, skill
        desc, _ = split_skill(content)
        path = root / filename
        block_status = upsert_block(path, pointer_block(skill, root, desc), force)
        if block_status == "skipped":
            return "skipped", path
        merged = "installed" if "installed" in (status, block_status) else "current"
        return merged, path

    return install


# name -> (label, detect(root), install(root, content, force) -> (status, path))
TARGETS: dict[
    str, tuple[str, Callable[[Path], bool], Callable[..., tuple[str, Path]]]
] = {
    "claude-user": (
        "Claude Code (user)",
        lambda root: True,  # default destination, as before
        _t_claude(Path.home() / ".claude"),
    ),
    "claude": (
        "Claude Code (project)",
        lambda root: (root / ".claude").is_dir(),
        _project_claude,
    ),
    "cursor": (
        "Cursor",
        lambda root: (root / ".cursor").is_dir(),
        _t_rules(
            ".cursor/rules",
            ".mdc",
            "---\ndescription: {description}\nalwaysApply: false\n---\n",
        ),
    ),
    "windsurf": (
        "Windsurf",
        lambda root: (root / ".windsurf").is_dir(),
        _t_rules(
            ".windsurf/rules",
            ".md",
            "---\ntrigger: model_decision\ndescription: {description}\n---\n",
        ),
    ),
    "agents": (
        "AGENTS.md (Codex, Amp, OpenCode, Jules, ...)",
        lambda root: (root / "AGENTS.md").is_file(),
        _t_instructions("AGENTS.md"),
    ),
    "gemini": (
        "Gemini CLI",
        lambda root: (root / "GEMINI.md").is_file() or (root / ".gemini").is_dir(),
        _t_instructions("GEMINI.md"),
    ),
}


def detect_targets(root: Path) -> list[str]:
    """List the agents that appear to be used in a project.

    Args:
        root (Path): Project directory to inspect.

    Returns:
        list[str]: Names from ``TARGETS`` whose marker file or directory exists
        (``claude-user`` is always included).
    """
    return [name for name, (_, detect, _i) in TARGETS.items() if detect(root)]


def install_skill(
    targets: list[str] | None = None, root: Path | None = None, force: bool = False
) -> list[tuple[str, str, Path | None]]:
    """Install the skill into several agents.

    Never overwrites a differing file unless ``force`` is set. Per-target
    write errors are printed and reported as ``"error"`` instead of raised.

    Args:
        targets (list[str] | None): Names from ``TARGETS``; ``None`` means
            every detected agent.
        root (Path | None): Project directory (default: current directory).
        force (bool): Overwrite differing files.

    Returns:
        list[tuple[str, str, Path | None]]: ``(target, status, path)`` per
        target, status being ``installed``, ``current``, ``skipped`` or
        ``error`` (path is ``None`` on error).

    Raises:
        KeyError: If a name in ``targets`` is not in ``TARGETS``.
    """
    from ..config import DEFAULT_SKILL_URL

    root = root or Path.cwd()
    chosen = targets or detect_targets(root)
    content, source = fetch_skill(os.getenv("ARXIV_MCP_SKILL_URL", DEFAULT_SKILL_URL))
    results: list[tuple[str, str, Path | None]] = []
    for name in chosen:
        label, _detect, install = TARGETS[name]
        try:
            status, path = install(root, content, force)
        except OSError as exc:
            print(f"  x {label}: {exc}")
            results.append((name, "error", None))
            continue
        marker = {"installed": "+", "current": "=", "skipped": "!"}[status]
        extra = (
            " (differs; re-run with --force to overwrite)"
            if status == "skipped"
            else ""
        )
        src = f" from {source}" if status == "installed" else ""
        print(f"  {marker} {label}{src}: {path}{extra}")
        results.append((name, status, path))
    return results
