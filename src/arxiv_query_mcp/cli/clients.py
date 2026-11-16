"""Registering the server with MCP clients (Claude Desktop/Code, Cursor, ...)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .constants import COMMAND_NAME, SERVER_NAME


def find_executable() -> str:
    """Locate the installed ``arxiv-query-mcp`` command.

    Returns:
        str: Absolute path if found on ``PATH`` or via ``sys.argv[0]``,
        otherwise the bare command name.
    """
    found = shutil.which(COMMAND_NAME)
    if found:
        return found
    candidate = Path(sys.argv[0]).resolve()
    if candidate.name.startswith(COMMAND_NAME):
        return str(candidate)
    return COMMAND_NAME


def claude_desktop_configs() -> list[Path]:
    """Find Claude Desktop config files for the current platform.

    Returns:
        list[Path]: Existing config files, or the platform default location
        if none exist.
    """
    name = "claude_desktop_config.json"
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    candidates = [base / d / name for d in ("Claude", "Claude Desktop")]
    existing = [p for p in candidates if p.exists()]
    return existing or [candidates[0]]


def update_json_client(config_path: Path, command: str, label: str) -> bool:
    """Add or replace our entry under ``mcpServers`` in a JSON config file.

    Used for every client that stores MCP servers as JSON (Claude Desktop,
    Cursor, Windsurf, Gemini CLI). Other servers and keys are preserved; an
    existing ``env`` of our entry is kept.

    Args:
        config_path (Path): JSON config file; created if missing.
        command (str): Executable the client should launch.
        label (str): Client name used in the status message.

    Returns:
        bool: ``True`` if written, ``False`` if the file holds invalid JSON
        (it is left untouched).

    Raises:
        OSError: If the file cannot be read or written.
    """
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ! {config_path} is not valid JSON; not touching it")
            return False
    servers = config.setdefault("mcpServers", {})
    existing_env = (servers.get(SERVER_NAME) or {}).get("env", {})
    servers[SERVER_NAME] = {
        "command": command,
        **({"env": existing_env} if existing_env else {}),
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"  + {label}: {config_path}")
    return True


def update_claude_desktop(config_path: Path, command: str) -> bool:
    """Register the server in a Claude Desktop config file.

    Args:
        config_path (Path): ``claude_desktop_config.json`` location.
        command (str): Executable the client should launch.

    Returns:
        bool: ``True`` if the file was written, ``False`` if it holds invalid JSON.

    Raises:
        OSError: If the file cannot be read or written.
    """
    return update_json_client(config_path, command, "Claude Desktop")


# MARK: Other
# JSON-configured clients, written only if the app's directory exists
# (so we never create config for software that is not installed).
def other_json_clients() -> list[tuple[str, Path]]:
    """List JSON-configured MCP clients besides Claude Desktop.

    Returns:
        list[tuple[str, Path]]: ``(label, config path)`` for Cursor, Windsurf
        and Gemini CLI; the files may not exist yet.
    """
    home = Path.home()
    return [
        ("Cursor", home / ".cursor" / "mcp.json"),
        ("Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json"),
        ("Gemini CLI", home / ".gemini" / "settings.json"),
    ]


def existing_claude_code_entry() -> dict:
    """Read our user-scope Claude Code entry from ``~/.claude.json``.

    Returns:
        dict: The entry (``command``, ``args``, ``env``, ...), or ``{}`` if the
        file or entry is missing or unreadable.
    """
    try:
        data = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
        entry = data["mcpServers"][SERVER_NAME]
        return entry if isinstance(entry, dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def existing_claude_code_env() -> dict[str, str]:
    """Read the env vars of our user-scope Claude Code entry.

    Returns:
        dict[str, str]: Variable names and values, empty if none.
    """
    env = existing_claude_code_entry().get("env")
    if not isinstance(env, dict):
        return {}
    return {str(k): str(v) for k, v in env.items()}


def _claude_add_argv(claude: str, command: str, args: list, env: dict) -> list[str]:
    """Build the ``claude mcp add`` command line for our server.

    Args:
        claude (str): Path of the ``claude`` executable.
        command (str): Server executable to register.
        args (list): Arguments the server command takes.
        env (dict): Environment variables to set on the entry.

    Returns:
        list[str]: The argv list.
    """
    env_args = [arg for k, v in env.items() for arg in ("-e", f"{k}={v}")]
    return [
        claude, "mcp", "add", "--scope", "user", SERVER_NAME,
        *env_args, "--", command, *[str(a) for a in args],
    ]  # fmt: skip


def update_claude_code(command: str) -> bool:
    """Register the server with Claude Code (user scope) if the CLI is present.

    An existing entry is replaced, but its env vars (cache directory, rate limits, ...) are
    carried over so re-running ``setup`` never drops the user's settings. If
    the new registration fails, the previous entry is restored.

    Args:
        command (str): Server executable to register.

    Returns:
        bool: ``True`` if registered; ``False`` if the ``claude`` CLI is
        missing or registration failed.
    """
    claude = shutil.which("claude")
    if not claude:
        return False
    old = existing_claude_code_entry()
    env = existing_claude_code_env()
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [claude, "mcp", "remove", "--scope", "user", SERVER_NAME],
        capture_output=True,
        check=False,
    )
    result = subprocess.run(  # noqa: S603
        _claude_add_argv(claude, command, [], env),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        kept = f", kept {len(env)} env var(s)" if env else ""
        print(f"  + Claude Code: registered (user scope{kept})")
        return True
    print(f"  ! Claude Code registration failed: {result.stderr.strip()}")
    if isinstance(old.get("command"), str):  # put the previous entry back
        restored = subprocess.run(  # noqa: S603
            _claude_add_argv(
                claude,
                old["command"],
                old.get("args") or [],
                {str(k): str(v) for k, v in (old.get("env") or {}).items()},
            ),
            capture_output=True,
            check=False,
        )
        state = "restored" if restored.returncode == 0 else "could NOT be restored"
        print(f"  ! previous Claude Code entry {state}")
    return False
