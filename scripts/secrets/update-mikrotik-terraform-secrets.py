#!/usr/bin/env python3
"""Update SOPS-encrypted MikroTik Terraform secrets safely.

This helper updates fields in:
  projects/<active-project>/secrets/terraform/mikrotik.yaml

It uses `sops set` and supports reading the password from stdin to avoid
putting secrets into process args/history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _active_project(repo_root: Path) -> str:
    manifest = repo_root / "topology" / "topology.yaml"
    payload = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    project = payload.get("project", {})
    if not isinstance(project, dict):
        raise RuntimeError("topology.yaml: 'project' must be mapping")
    active = project.get("active")
    if not isinstance(active, str) or not active.strip():
        raise RuntimeError("topology.yaml: 'project.active' must be non-empty string")
    return active.strip()


def _secrets_file(repo_root: Path, project_id: str) -> Path:
    project_manifest = repo_root / "projects" / project_id / "project.yaml"
    payload = yaml.safe_load(project_manifest.read_text(encoding="utf-8")) or {}
    secrets_root = payload.get("secrets_root", "secrets")
    if not isinstance(secrets_root, str) or not secrets_root.strip():
        raise RuntimeError(f"{project_manifest}: 'secrets_root' must be non-empty string")
    path = (project_manifest.parent / secrets_root / "terraform" / "mikrotik.yaml").resolve()
    if not path.exists():
        raise FileNotFoundError(f"Secrets file not found: {path}")
    return path


def _sops_set_literal(path: Path, index: str, value: object) -> None:
    value_json = json.dumps(value, ensure_ascii=False)
    command = ["sops", "set", str(path), index, value_json]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"sops set failed for {index}: {stderr}")


def _sops_set_from_stdin(path: Path, index: str, value: str) -> None:
    command = ["sops", "set", "--value-stdin", str(path), index]
    result = subprocess.run(command, input=json.dumps(value), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"sops set --value-stdin failed for {index}: {stderr}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update SOPS-encrypted MikroTik terraform secrets.")
    parser.add_argument("--host", default="", help='Example: "https://192.168.88.1:8443"')
    parser.add_argument("--username", default="", help='Example: "terraform"')
    parser.add_argument(
        "--insecure",
        choices=["true", "false", ""],
        default="",
        help="Set mikrotik.insecure explicitly (true|false).",
    )
    parser.add_argument("--password", default="", help="Password value (avoid this; prefer --password-stdin).")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read password from stdin (recommended).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()
    project_id = _active_project(repo_root)
    secret_file = _secrets_file(repo_root, project_id)

    updates: list[str] = []
    try:
        if args.host.strip():
            _sops_set_literal(secret_file, '["mikrotik"]["host"]', args.host.strip())
            updates.append("mikrotik.host")
        if args.username.strip():
            _sops_set_literal(secret_file, '["mikrotik"]["username"]', args.username.strip())
            updates.append("mikrotik.username")
        if args.insecure in {"true", "false"}:
            _sops_set_literal(secret_file, '["mikrotik"]["insecure"]', args.insecure == "true")
            updates.append("mikrotik.insecure")

        password_value = ""
        if args.password_stdin:
            password_value = sys.stdin.read()
            password_value = password_value.rstrip("\r\n")
        elif args.password:
            password_value = args.password
        if password_value:
            _sops_set_from_stdin(secret_file, '["mikrotik"]["password"]', password_value)
            updates.append("mikrotik.password")
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not updates:
        print("No updates requested. Nothing changed.")
        return 0

    print(f"Updated {secret_file}")
    print("Updated keys:")
    for key in updates:
        print(f"- {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
