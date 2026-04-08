#!/usr/bin/env python3
"""Setup MikroTik MCP server for Codex with SOPS credential decryption.

Usage:
    python setup-mikrotik-mcp-codex.py [--check] [--remove] [--secret-file PATH]

This script:
1. Decrypts MikroTik SSH credentials from SOPS-encrypted secrets
2. Verifies SSH connectivity to the router
3. Registers the MCP server via `codex mcp`
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]

DEFAULT_SECRET_FILE = REPO_ROOT / "projects" / "home-lab" / "secrets" / "terraform" / "mikrotik.yaml"
BOOTSTRAP_SECRET_FILE = REPO_ROOT / "projects" / "home-lab" / "secrets" / "bootstrap" / "rtr-mikrotik.chateau.yaml"
MCP_SERVER_NAME = "mikrotik-mcp"

MCP_SERVER_CANDIDATES = [
    REPO_ROOT.parent.parent / "tools" / "mikrotik-mcp" / "src" / "mcp_mikrotik" / "server.py",
    REPO_ROOT / ".work" / "mcp" / "mikrotik" / ".venv" / "bin" / "mcp-server-mikrotik",
    Path.home() / "workspaces" / "tools" / "mikrotik-mcp" / "src" / "mcp_mikrotik" / "server.py",
]


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with UTF-8 capture."""
    return subprocess.run(args, check=check, capture_output=True, text=True)


def find_mcp_server() -> tuple[str, list[str]]:
    """Find the MCP server executable/script."""
    for candidate in MCP_SERVER_CANDIDATES:
        if candidate.exists():
            if candidate.suffix == ".py":
                return "python3", [str(candidate)]
            return str(candidate), []
    return "npx", ["-y", "mcp-server-mikrotik"]


def decrypt_sops(secret_file: Path, extract_path: str) -> str:
    """Decrypt a value from SOPS-encrypted file."""
    try:
        result = run_command(["sops", "-d", "--extract", extract_path, str(secret_file)])
        return result.stdout.strip().strip('"')
    except FileNotFoundError:
        print("[error] sops not found. Install: https://github.com/getsops/sops", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(stderr or f"cannot decrypt {extract_path}") from exc


def decrypt_first(secret_file: Path, paths: list[str]) -> str:
    """Try multiple extract paths and return the first successful value."""
    for path in paths:
        try:
            value = decrypt_sops(secret_file, path)
        except RuntimeError:
            continue
        if value:
            return value
    joined = ", ".join(paths)
    raise RuntimeError(f"failed to decrypt any of: {joined}")


def decrypt_credentials(secret_file: Path) -> dict[str, str]:
    """Decrypt MikroTik credentials from a SOPS secret file."""
    print(f"[info] Decrypting credentials from {secret_file.name}...")
    try:
        host_raw = decrypt_first(secret_file, ['["mikrotik"]["host"]', '["ssh"]["host"]'])
        username = decrypt_first(secret_file, ['["mikrotik"]["username"]', '["ssh"]["username"]'])
        password = decrypt_first(secret_file, ['["mikrotik"]["password"]', '["ssh"]["password"]'])
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)

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
                "sshpass",
                "-p",
                password,
                "ssh",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "BatchMode=no",
                "-p",
                str(port),
                f"{username}@{host}",
                "/system/identity/print",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            print(f"[ok] Connected: {result.stdout.strip()}")
            return True
        print(f"[warn] SSH returned code {result.returncode}: {result.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("[warn] sshpass not found — skipping SSH check (apt install sshpass)")
        return True
    except subprocess.TimeoutExpired:
        print("[warn] SSH connection timed out")
        return False


def codex_mcp_get(server_name: str) -> dict | None:
    """Read MCP config from codex; return None when not found."""
    try:
        result = run_command(["codex", "mcp", "get", server_name, "--json"])
        return json.loads(result.stdout)
    except FileNotFoundError:
        print("[error] codex command not found in PATH", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError:
        return None
    except json.JSONDecodeError:
        return None


def register_mcp_server(host: str, username: str, password: str, port: int = 22) -> bool:
    """Register MikroTik MCP server in Codex config."""
    existing = codex_mcp_get(MCP_SERVER_NAME)
    if existing is not None:
        print(f"[info] Updating existing '{MCP_SERVER_NAME}' config...")
        run_command(["codex", "mcp", "remove", MCP_SERVER_NAME], check=True)
    else:
        print(f"[info] Adding new '{MCP_SERVER_NAME}' server...")

    command, extra_args = find_mcp_server()
    add_cmd = [
        "codex",
        "mcp",
        "add",
        MCP_SERVER_NAME,
        "--env",
        f"MIKROTIK_HOST={host}",
        "--env",
        f"MIKROTIK_USERNAME={username}",
        "--env",
        f"MIKROTIK_PASSWORD={password}",
        "--env",
        f"MIKROTIK_PORT={port}",
        "--",
        command,
        *extra_args,
        "--host",
        host,
        "--port",
        str(port),
        "--username",
        username,
        "--password",
        password,
    ]

    try:
        run_command(add_cmd, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        print(f"[error] Failed to register MCP server: {stderr}", file=sys.stderr)
        return False

    print(f"[ok] Registered '{MCP_SERVER_NAME}' in Codex config")
    return True


def remove_mcp_server() -> bool:
    """Remove MikroTik MCP server from Codex config."""
    existing = codex_mcp_get(MCP_SERVER_NAME)
    if existing is None:
        print(f"[info] '{MCP_SERVER_NAME}' not found in Codex config")
        return False
    run_command(["codex", "mcp", "remove", MCP_SERVER_NAME], check=True)
    print(f"[ok] Removed '{MCP_SERVER_NAME}'")
    return True


def check_status() -> None:
    """Print current MCP server status."""
    srv = codex_mcp_get(MCP_SERVER_NAME)
    if srv is None:
        print(f"[info] '{MCP_SERVER_NAME}' is NOT configured")
        return

    env = srv.get("env", {})
    host = env.get("MIKROTIK_HOST", "?")
    user = env.get("MIKROTIK_USERNAME", env.get("MIKROTIK_USER", "?"))
    port = int(env.get("MIKROTIK_PORT", "22"))

    print(f"[info] Server: {MCP_SERVER_NAME}")
    print(f"  host:     {host}")
    print(f"  user:     {user}")
    print(f"  port:     {port}")
    print(f"  command:  {srv.get('command', '?')}")
    print(f"  args:     {' '.join(srv.get('args', []))}")

    password = env.get("MIKROTIK_PASSWORD", "")
    if password and host != "?" and user != "?":
        check_ssh(host, user, password, port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup MikroTik MCP server for Codex")
    parser.add_argument("--check", action="store_true", help="Check current configuration and connectivity")
    parser.add_argument("--remove", action="store_true", help="Remove MikroTik MCP server from Codex config")
    parser.add_argument(
        "--secret-file",
        type=Path,
        default=None,
        help=f"SOPS secret file path (default: {DEFAULT_SECRET_FILE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH port (default: 22)")
    args = parser.parse_args()

    if args.check:
        check_status()
        return

    if args.remove:
        remove_mcp_server()
        return

    secret_file = args.secret_file or DEFAULT_SECRET_FILE
    if not secret_file.exists():
        if BOOTSTRAP_SECRET_FILE.exists():
            secret_file = BOOTSTRAP_SECRET_FILE
        else:
            print(f"[error] Secret file not found: {secret_file}", file=sys.stderr)
            sys.exit(1)

    creds = decrypt_credentials(secret_file)
    ssh_ok = check_ssh(creds["host"], creds["username"], creds["password"], args.ssh_port)
    if not ssh_ok:
        print("[warn] SSH check failed — registering anyway")

    ok = register_mcp_server(
        host=creds["host"],
        username=creds["username"],
        password=creds["password"],
        port=args.ssh_port,
    )
    if ok:
        print()
        print("Done! Restart Codex to activate the MCP server if it is already running.")
        print("  Verify: codex mcp list")
        print(f"  Remove: python {Path(__file__).name} --remove")


if __name__ == "__main__":
    main()
