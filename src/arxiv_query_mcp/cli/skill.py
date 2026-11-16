"""Fetching the skill and writing it without clobbering user files."""

from __future__ import annotations

import re
import urllib.request
from importlib import resources
from pathlib import Path

from .constants import COMMAND_NAME, SKILL_NAME


def bundled_skill() -> str:
    """Read the SKILL.md shipped inside the package.

    Returns:
        str: Full text of the bundled SKILL.md.

    Raises:
        FileNotFoundError: If the package was built without the skill file.
    """
    return (
        resources.files("arxiv_query_mcp")
        .joinpath("skills", SKILL_NAME, "SKILL.md")
        .read_text(encoding="utf-8")
    )


def fetch_skill(url: str | None, timeout: float = 10.0) -> tuple[str, str]:
    """Download the skill, falling back to the bundled copy.

    Any failure (network, TLS, 404, non-https URL, content that does not look
    like a SKILL.md) is reported on stdout and never raised.

    Args:
        url (str | None): ``https`` URL of a SKILL.md, or ``None`` to use the
            bundled copy directly.
        timeout (float): Download timeout in seconds.

    Returns:
        tuple[str, str]: The skill text and where it came from (the URL or
        ``"bundled copy"``).
    """
    if url:
        try:
            if not url.startswith("https://"):
                raise ValueError("skill URL must use https")
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                text = resp.read().decode("utf-8")
            if text.lstrip().startswith("---"):  # looks like a SKILL.md
                return text, url
        except Exception as exc:  # network, TLS, 404, bad URL: fall back
            print(f"  ! could not download skill ({exc}); using bundled copy")
    return bundled_skill(), "bundled copy"


def split_skill(content: str) -> tuple[str, str]:
    """Split a SKILL.md into its description and body.

    Args:
        content (str): Full SKILL.md text including frontmatter.

    Returns:
        tuple[str, str]: The ``description`` frontmatter value (a generic
        fallback if missing) and the text after the frontmatter.
    """
    parts = content.split("---", 2)
    body = parts[2].lstrip("\n") if len(parts) > 2 else content
    match = re.search(r"^description:\s*(.+?)\s*$", content, re.MULTILINE)
    return (match.group(1) if match else "Search arXiv."), body


BLOCK_BEGIN = (
    f"<!-- BEGIN {SKILL_NAME} skill (managed by `{COMMAND_NAME} install-skill`) -->"
)
BLOCK_END = f"<!-- END {SKILL_NAME} skill -->"


def write_file(dst: Path, text: str, force: bool) -> str:
    """Write a file without clobbering differing content.

    Args:
        dst (Path): Destination file; parent directories are created.
        text (str): Content to write.
        force (bool): Overwrite an existing file whose content differs.

    Returns:
        str: ``"installed"`` if written, ``"current"`` if the file already
        has this content, ``"skipped"`` if it differs and ``force`` is false.

    Raises:
        OSError: If the file cannot be read or written.
    """
    if dst.exists():
        if dst.read_text(encoding="utf-8") == text:
            return "current"
        if not force:
            return "skipped"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return "installed"


def upsert_block(path: Path, block: str, force: bool) -> str:
    """Insert or update only our marked block in a shared file.

    Text outside the ``BEGIN``/``END`` markers is never modified.

    Args:
        path (Path): Shared file such as ``AGENTS.md``; created if missing.
        block (str): Block text including both markers.
        force (bool): Replace an existing block that differs.

    Returns:
        str: ``"installed"``, ``"current"`` or ``"skipped"`` (existing block
        differs and ``force`` is false).

    Raises:
        OSError: If the file cannot be read or written.
    """
    if not path.exists():
        return write_file(path, block + "\n", force)
    existing = path.read_text(encoding="utf-8")
    if BLOCK_BEGIN in existing and BLOCK_END in existing:
        a = existing.index(BLOCK_BEGIN)
        b = existing.index(BLOCK_END) + len(BLOCK_END)
        if existing[a:b] == block:
            return "current"
        if not force:
            return "skipped"
        path.write_text(existing[:a] + block + existing[b:], encoding="utf-8")
        return "installed"
    sep = (
        ""
        if existing.endswith("\n\n")
        else ("\n" if existing.endswith("\n") else "\n\n")
    )
    path.write_text(existing + sep + block + "\n", encoding="utf-8")
    return "installed"
