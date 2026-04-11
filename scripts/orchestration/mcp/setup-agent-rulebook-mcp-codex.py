#!/usr/bin/env python3
"""Register the ADR0096 rulebook MCP server in Codex.

Usage:
    python setup-agent-rulebook-mcp-codex.py [--check] [--remove] [--print-config]

This helper avoids editing repo files directly. It can:
1. Print the expected project-scoped `.mcp.json` snippet
2. Check whether Codex already has the server configured
3. Register or remove the server via `codex mcp`
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MCP_SERVER_NAME = "home-lab-ai-rulebook"
MCP_SERVER_SCRIPT = SCRIPT_DIR / "agent_rulebook_mcp_server.py"


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with UTF-8 capture."""
    return subprocess.run(args, check=check, capture_output=True, text=True)


def resolve_python_command() -> str:
    """Prefer the repo venv so the MCP runtime matches validation tooling."""
    repo_python = REPO_ROOT / ".venv" / "bin" / "python"
    if repo_python.exists():
        return str(repo_python)
    return "python3"


def build_server_spec() -> dict[str, Any]:
    """Build the canonical stdio server spec for Codex/`.mcp.json`."""
    return {
        "type": "stdio",
        "command": resolve_python_command(),
        "args": [str(MCP_SERVER_SCRIPT)],
        "env": {},
    }


def build_mcp_config_snippet() -> dict[str, Any]:
    """Build a project-level `.mcp.json` snippet for manual registration."""
    return {"mcpServers": {MCP_SERVER_NAME: build_server_spec()}}


def build_codex_add_command() -> list[str]:
    """Build the `codex mcp add` command for the canonical server spec."""
    spec = build_server_spec()
    return ["codex", "mcp", "add", MCP_SERVER_NAME, "--", spec["command"], *spec["args"]]


def codex_mcp_get(server_name: str) -> dict[str, Any] | None:
    """Read MCP config from Codex; return None when not found."""
    try:
        result = run_command(["codex", "mcp", "get", server_name, "--json"])
        return json.loads(result.stdout)
    except FileNotFoundError:
        print("[error] codex command not found in PATH", file=sys.stderr)
        raise SystemExit(1) from None
    except subprocess.CalledProcessError:
        return None
    except json.JSONDecodeError:
        return None


def register_mcp_server() -> bool:
    """Register or replace the MCP server in Codex config."""
    existing = codex_mcp_get(MCP_SERVER_NAME)
    if existing is not None:
        print(f"[info] Updating existing '{MCP_SERVER_NAME}' config...")
        run_command(["codex", "mcp", "remove", MCP_SERVER_NAME], check=True)
    else:
        print(f"[info] Adding new '{MCP_SERVER_NAME}' server...")

    try:
        run_command(build_codex_add_command(), check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        print(f"[error] Failed to register MCP server: {stderr}", file=sys.stderr)
        return False

    print(f"[ok] Registered '{MCP_SERVER_NAME}' in Codex config")
    return True


def remove_mcp_server() -> bool:
    """Remove the MCP server from Codex config."""
    existing = codex_mcp_get(MCP_SERVER_NAME)
    if existing is None:
        print(f"[info] '{MCP_SERVER_NAME}' not found in Codex config")
        return False
    run_command(["codex", "mcp", "remove", MCP_SERVER_NAME], check=True)
    print(f"[ok] Removed '{MCP_SERVER_NAME}'")
    return True


def _matches_expected_spec(existing: dict[str, Any] | None) -> bool:
    """Return whether the current Codex entry matches the canonical runtime spec."""
    if existing is None:
        return False
    spec = build_server_spec()
    return existing.get("command") == spec["command"] and list(existing.get("args", [])) == spec["args"]


def check_status() -> int:
    """Print a machine-readable summary of current Codex MCP registration."""
    existing = codex_mcp_get(MCP_SERVER_NAME)
    spec = build_server_spec()
    summary = {
        "server_name": MCP_SERVER_NAME,
        "configured": existing is not None,
        "matches_expected": _matches_expected_spec(existing),
        "expected_command": spec["command"],
        "expected_args": spec["args"],
    }
    if existing is not None:
        summary["actual_command"] = existing.get("command")
        summary["actual_args"] = list(existing.get("args", []))
    print(json.dumps(summary, ensure_ascii=True))
    return 0 if summary["matches_expected"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Setup ADR0096 rulebook MCP server for Codex")
    parser.add_argument("--check", action="store_true", help="Check current Codex MCP registration")
    parser.add_argument("--remove", action="store_true", help="Remove the rulebook MCP server from Codex config")
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print a project-scoped .mcp.json snippet for manual registration",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.print_config:
        print(json.dumps(build_mcp_config_snippet(), indent=2, ensure_ascii=False))
        return 0

    if args.check:
        return check_status()

    if args.remove:
        return 0 if remove_mcp_server() else 1

    return 0 if register_mcp_server() else 1


if __name__ == "__main__":
    raise SystemExit(main())
