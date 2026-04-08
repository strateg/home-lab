#!/usr/bin/env python3
"""Setup MikroTik MCP server for Claude Code with SOPS credential decryption.

Usage:
    python setup-mikrotik-mcp.py [--check] [--remove] [--secret-file PATH]

This script:
1. Decrypts MikroTik SSH credentials from SOPS-encrypted secrets
2. Verifies SSH connectivity to the router
3. Registers the MCP server in Claude Code project config
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]

DEFAULT_SECRET_FILE = REPO_ROOT / "projects" / "home-lab" / "secrets" / "terraform" / "mikrotik.yaml"
MCP_SERVER_NAME = "mikrotik-mcp"
MCP_SERVER_ENTRY = REPO_ROOT.parent.parent / "tools" / "mikrotik-mcp" / "src" / "mcp_mikrotik" / "server.py"

# Fallback: search common locations
MCP_SERVER_CANDIDATES = [
    REPO_ROOT.parent.parent / "tools" / "mikrotik-mcp" / "src" / "mcp_mikrotik" / "server.py",
    REPO_ROOT / ".work" / "mcp" / "mikrotik" / ".venv" / "bin" / "mcp-server-mikrotik",
    Path.home() / "workspaces" / "tools" / "mikrotik-mcp" / "src" / "mcp_mikrotik" / "server.py",
]


def find_mcp_server() -> tuple[str, list[str]]:
    """Find the MCP server executable/script."""
    for candidate in MCP_SERVER_CANDIDATES:
        if candidate.exists():
            if candidate.suffix == ".py":
                return "python3", [str(candidate)]
            return str(candidate), []
    # Fallback to npx
    return "npx", ["-y", "mcp-server-mikrotik"]


def decrypt_sops(secret_file: Path, extract_path: str) -> str:
    """Decrypt a value from SOPS-encrypted file."""
    try:
        result = subprocess.run(
            ["sops", "-d", "--extract", extract_path, str(secret_file)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().strip('"')
    except FileNotFoundError:
        print("[error] sops not found. Install: https://github.com/getsops/sops", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"[error] Failed to decrypt {extract_path}: {exc.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


def decrypt_credentials(secret_file: Path) -> dict[str, str]:
    """Decrypt MikroTik credentials from SOPS secret file."""
    print(f"[info] Decrypting credentials from {secret_file.name}...")

    host_raw = decrypt_sops(secret_file, '["mikrotik"]["host"]')
    username = decrypt_sops(secret_file, '["mikrotik"]["username"]')
    password = decrypt_sops(secret_file, '["mikrotik"]["password"]')

    # Extract hostname/IP from URL if needed (e.g. https://192.168.88.1:8443 -> 192.168.88.1)
    host = host_raw
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split(":")[0].split("/")[0]

    return {"host": host, "username": username, "password": password}


def check_ssh(host: str, username: str, password: str, port: int = 22) -> bool:
    """Verify SSH connectivity to MikroTik."""
    print(f"[info] Testing SSH to {username}@{host}:{port}...")
    try:
        result = subprocess.run(
            [
                "sshpass", "-p", password,
                "ssh",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=no",
                "-p", str(port),
                f"{username}@{host}",
                "/system/identity/print",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            identity = result.stdout.strip()
            print(f"[ok] Connected: {identity}")
            return True
        print(f"[warn] SSH returned code {result.returncode}: {result.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("[warn] sshpass not found — skipping SSH check (apt install sshpass)")
        return True  # Assume OK if we can't test
    except subprocess.TimeoutExpired:
        print("[warn] SSH connection timed out")
        return False


def find_claude_config() -> Path:
    """Find the Claude Code config file."""
    return Path.home() / ".claude.json"


def register_mcp_server(
    host: str,
    username: str,
    password: str,
    port: int = 22,
    project_path: str | None = None,
) -> bool:
    """Register MikroTik MCP server in Claude Code config."""
    config_path = find_claude_config()

    if not config_path.exists():
        print(f"[error] Claude config not found at {config_path}", file=sys.stderr)
        return False

    config = json.loads(config_path.read_text(encoding="utf-8"))

    command, extra_args = find_mcp_server()

    server_config = {
        "type": "stdio",
        "command": command,
        "args": [
            *extra_args,
            "--host", host,
            "--port", str(port),
            "--username", username,
            "--password", password,
        ],
        "env": {
            "MIKROTIK_HOST": host,
            "MIKROTIK_USERNAME": username,
            "MIKROTIK_PASSWORD": password,
            "MIKROTIK_PORT": str(port),
        },
    }

    # Determine target: project-scoped or global
    target_path = project_path or str(REPO_ROOT)
    projects = config.setdefault("projects", {})
    project = projects.setdefault(target_path, {})
    mcp_servers = project.setdefault("mcpServers", {})

    # Check if already configured
    if MCP_SERVER_NAME in mcp_servers:
        print(f"[info] Updating existing '{MCP_SERVER_NAME}' config...")
    else:
        print(f"[info] Adding new '{MCP_SERVER_NAME}' server...")

    mcp_servers[MCP_SERVER_NAME] = server_config

    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] Registered '{MCP_SERVER_NAME}' for project {target_path}")
    print(f"[ok] Config written to {config_path}")
    return True


def remove_mcp_server(project_path: str | None = None) -> bool:
    """Remove MikroTik MCP server from Claude Code config."""
    config_path = find_claude_config()

    if not config_path.exists():
        print("[warn] No Claude config found")
        return False

    config = json.loads(config_path.read_text(encoding="utf-8"))
    target_path = project_path or str(REPO_ROOT)

    project = config.get("projects", {}).get(target_path, {})
    mcp_servers = project.get("mcpServers", {})

    if MCP_SERVER_NAME not in mcp_servers:
        print(f"[info] '{MCP_SERVER_NAME}' not found in config")
        return False

    del mcp_servers[MCP_SERVER_NAME]
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] Removed '{MCP_SERVER_NAME}' from {target_path}")
    return True


def check_status(project_path: str | None = None) -> None:
    """Print current MCP server status."""
    config_path = find_claude_config()

    if not config_path.exists():
        print("[warn] No Claude config found")
        return

    config = json.loads(config_path.read_text(encoding="utf-8"))
    target_path = project_path or str(REPO_ROOT)

    project = config.get("projects", {}).get(target_path, {})
    mcp_servers = project.get("mcpServers", {})

    if MCP_SERVER_NAME not in mcp_servers:
        print(f"[info] '{MCP_SERVER_NAME}' is NOT configured")
        return

    srv = mcp_servers[MCP_SERVER_NAME]
    env = srv.get("env", {})
    host = env.get("MIKROTIK_HOST", "?")
    user = env.get("MIKROTIK_USERNAME", env.get("MIKROTIK_USER", "?"))
    port = env.get("MIKROTIK_PORT", "22")

    print(f"[info] Server: {MCP_SERVER_NAME}")
    print(f"  host:     {host}")
    print(f"  user:     {user}")
    print(f"  port:     {port}")
    print(f"  command:  {srv.get('command', '?')}")
    print(f"  args:     {' '.join(srv.get('args', []))}")

    # Run connectivity check
    password = env.get("MIKROTIK_PASSWORD", "")
    if password:
        check_ssh(host, user, password, int(port))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Setup MikroTik MCP server for Claude Code",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check current configuration and connectivity",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove MikroTik MCP server from Claude Code config",
    )
    parser.add_argument(
        "--secret-file",
        type=Path,
        default=None,
        help=f"SOPS secret file path (default: {DEFAULT_SECRET_FILE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=22,
        help="SSH port (default: 22)",
    )
    parser.add_argument(
        "--project-path",
        type=str,
        default=None,
        help=f"Claude Code project path (default: {REPO_ROOT})",
    )
    args = parser.parse_args()

    if args.check:
        check_status(args.project_path)
        return

    if args.remove:
        remove_mcp_server(args.project_path)
        return

    secret_file = args.secret_file or DEFAULT_SECRET_FILE
    if not secret_file.exists():
        # Try bootstrap secret fallback
        fallback = REPO_ROOT / "projects" / "home-lab" / "secrets" / "bootstrap" / "rtr-mikrotik.chateau.yaml"
        if fallback.exists():
            secret_file = fallback
        else:
            print(f"[error] Secret file not found: {secret_file}", file=sys.stderr)
            sys.exit(1)

    # Step 1: Decrypt
    creds = decrypt_credentials(secret_file)

    # Step 2: Verify SSH
    ssh_ok = check_ssh(creds["host"], creds["username"], creds["password"], args.ssh_port)
    if not ssh_ok:
        print("[warn] SSH check failed — registering anyway (may work via API)")

    # Step 3: Register
    ok = register_mcp_server(
        host=creds["host"],
        username=creds["username"],
        password=creds["password"],
        port=args.ssh_port,
        project_path=args.project_path,
    )

    if ok:
        print()
        print("Done! Restart Claude Code to activate the MCP server.")
        print(f"  Verify: claude mcp list")
        print(f"  Remove: python {Path(__file__).name} --remove")


if __name__ == "__main__":
    main()
