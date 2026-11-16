"""Command line entry point: run the server, configure clients, install the skill.

``arxiv-query-mcp`` with no arguments still starts the stdio server, so MCP
client configs written before these subcommands existed keep working.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clients import (
    claude_desktop_configs,
    find_executable,
    other_json_clients,
    update_claude_code,
    update_claude_desktop,
    update_json_client,
)
from .constants import COMMAND_NAME
from .targets import TARGETS, install_skill


def setup(args: argparse.Namespace) -> int:
    """Register the server with detected MCP clients and install the skill.

    Args:
        args (argparse.Namespace): Parsed ``setup`` options
            (``no_claude_desktop``, ``no_claude_code``, ``no_skill``,
            ``force``, ``target``).

    Returns:
        int: Exit code, ``0`` if something was configured, ``1`` if not.
    """
    command = find_executable()
    print(f"Configuring {COMMAND_NAME} ({command})")
    done = False
    if not args.no_claude_desktop:
        for path in claude_desktop_configs():
            done |= update_claude_desktop(path, command)
    if not args.no_claude_code:
        done |= update_claude_code(command)
    for label, path in other_json_clients():
        if path.parent.is_dir():
            done |= update_json_client(path, command, label)
    if not args.no_skill:
        results = install_skill(args.target, force=args.force)
        done |= any(status != "error" for _, status, _p in results)
    if not done:
        print("Nothing configured. Add the server by hand: command =", command)
        return 1
    print("\nRestart Claude Desktop / Claude Code to pick up the changes.")
    return 0


# MARK: Entry point


def main(argv: list[str] | None = None) -> None:
    """Run the ``arxiv-query-mcp`` command.

    Without a subcommand (or with ``serve``) the stdio MCP server starts.

    Args:
        argv (list[str] | None): Arguments; ``None`` means ``sys.argv[1:]``.

    Returns:
        None: ``setup`` and ``install-skill`` end the process via
        ``SystemExit``; ``serve`` blocks until the client disconnects.

    Raises:
        SystemExit: With the command's exit code, or ``2`` on invalid arguments.
    """
    parser = argparse.ArgumentParser(prog=COMMAND_NAME, description="arXiv MCP server")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")

    p_setup = sub.add_parser(
        "setup", help="register with Claude Desktop / Claude Code and install the skill"
    )
    p_setup.add_argument("--no-claude-desktop", action="store_true")
    p_setup.add_argument("--no-claude-code", action="store_true")
    p_setup.add_argument("--no-skill", action="store_true")
    p_setup.add_argument(
        "--force", action="store_true", help="overwrite a differing skill"
    )
    p_setup.add_argument(
        "--target",
        action="append",
        choices=list(TARGETS),
        help="skill destination (repeatable; default: user Claude + detected harnesses)",
    )

    p_skill = sub.add_parser(
        "install-skill", help="download and install the agent skill"
    )
    p_skill.add_argument(
        "--target",
        action="append",
        choices=list(TARGETS),
        help="destination (repeatable): " + ", ".join(TARGETS) + ". Default: detect",
    )
    p_skill.add_argument("--root", type=Path, help="project directory (default: cwd)")
    p_skill.add_argument(
        "--force", action="store_true", help="overwrite a differing skill"
    )

    args = parser.parse_args(argv)

    if args.command == "setup":
        sys.exit(setup(args))
    if args.command == "install-skill":
        results = install_skill(args.target, args.root, args.force)
        sys.exit(0 if results and all(st != "error" for _, st, _p in results) else 1)

    from ..server import main as serve  # heavy import only when serving

    serve()


if __name__ == "__main__":
    main()
