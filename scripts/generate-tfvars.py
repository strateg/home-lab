#!/usr/bin/env python3
"""Generate terraform.tfvars from SOPS-encrypted Terraform secrets."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _decrypt_yaml(secret_file: Path) -> dict[str, Any]:
    command = ["sops", "-d", str(secret_file)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"sops decryption failed for '{secret_file}' (exit={result.returncode}): {stderr}")
    payload = yaml.safe_load(result.stdout) or {}
    if not isinstance(payload, dict):
        raise RuntimeError(f"Decrypted payload must be mapping/object: {secret_file}")
    return payload


def _require_mapping(node: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise RuntimeError(f"Expected mapping/object at '{path}'.")
    return node


def _require_scalar(node: Any, *, path: str) -> Any:
    if isinstance(node, (dict, list)) or node is None:
        raise RuntimeError(f"Expected scalar at '{path}'.")
    return node


def _render_list(items: list[Any]) -> str:
    """Render a list of objects as HCL."""
    if not items:
        return "[]"
    parts = []
    for item in items:
        if isinstance(item, dict):
            obj_lines = []
            for k, v in item.items():
                if isinstance(v, bool):
                    rendered = "true" if v else "false"
                elif isinstance(v, list):
                    rendered = str(v)  # Simple fallback
                else:
                    rendered = _render_string(v)
                obj_lines.append(f"    {k} = {rendered}")
            parts.append("  {\n" + "\n".join(obj_lines) + "\n  }")
        else:
            parts.append(f"  {_render_string(item)}")
    return "[\n" + ",\n".join(parts) + "\n]"


def _render_string(value: Any) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_tfvars(values: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, list):
            rendered = _render_list(value)
        else:
            rendered = _render_string(_require_scalar(value, path=key))
        lines.append(f"{key} = {rendered}")
    return "\n".join(lines) + "\n"


def _build_proxmox_values(payload: dict[str, Any]) -> dict[str, Any]:
    proxmox = _require_mapping(payload.get("proxmox"), path="proxmox")
    return {
        "proxmox_node": _require_scalar(proxmox.get("node"), path="proxmox.node"),
        "proxmox_api_url": _require_scalar(proxmox.get("api_url"), path="proxmox.api_url"),
        "proxmox_api_token": _require_scalar(proxmox.get("api_token"), path="proxmox.api_token"),
        "proxmox_insecure": bool(proxmox.get("insecure")),
        "proxmox_ssh_user": _require_scalar(proxmox.get("ssh_user"), path="proxmox.ssh_user"),
        "proxmox_ssh_key_path": _require_scalar(proxmox.get("ssh_key_path"), path="proxmox.ssh_key_path"),
    }


def _build_mikrotik_values(payload: dict[str, Any]) -> dict[str, Any]:
    mikrotik = _require_mapping(payload.get("mikrotik"), path="mikrotik")
    wireguard = _require_mapping(payload.get("wireguard"), path="wireguard")
    containers = _require_mapping(payload.get("containers"), path="containers")
    peers = wireguard.get("peers", [])
    if not isinstance(peers, list):
        peers = []
    return {
        "mikrotik_host": _require_scalar(mikrotik.get("host"), path="mikrotik.host"),
        "mikrotik_username": _require_scalar(mikrotik.get("username"), path="mikrotik.username"),
        "mikrotik_password": _require_scalar(mikrotik.get("password"), path="mikrotik.password"),
        "mikrotik_insecure": bool(mikrotik.get("insecure")),
        "wireguard_private_key": _require_scalar(wireguard.get("private_key"), path="wireguard.private_key"),
        "wireguard_peers": peers,
        "adguard_password": _require_scalar(containers.get("adguard_password"), path="containers.adguard_password"),
        "tailscale_authkey": _require_scalar(containers.get("tailscale_authkey"), path="containers.tailscale_authkey"),
    }


def _build_values(target: str, payload: dict[str, Any]) -> dict[str, Any]:
    if target == "proxmox":
        return _build_proxmox_values(payload)
    if target == "mikrotik":
        return _build_mikrotik_values(payload)
    raise RuntimeError(f"Unsupported target: {target}")


def _cleanup_tfvars(target: str) -> int:
    """Remove generated terraform.tfvars for target."""
    repo_root = _repo_root()
    output_file = repo_root / ".work" / "native" / "terraform" / target / "terraform.tfvars"

    if not output_file.exists():
        print(f"Skip: {output_file} (not found)")
        return 0

    output_file.unlink()
    print(f"Removed: {output_file}")
    return 0


def _generate_tfvars(target: str) -> int:
    """Generate terraform.tfvars for target from SOPS secrets."""
    repo_root = _repo_root()
    secret_file = repo_root / "secrets" / "terraform" / f"{target}.yaml"
    output_dir = repo_root / ".work" / "native" / "terraform" / target
    output_file = output_dir / "terraform.tfvars"

    if not secret_file.exists():
        print(f"Error: secret file not found: {secret_file}", file=sys.stderr)
        return 1
    if not output_dir.exists():
        print(f"Error: output directory not found: {output_dir}", file=sys.stderr)
        print("Run 'make assemble-native' first.", file=sys.stderr)
        return 1

    try:
        payload = _decrypt_yaml(secret_file)
        values = _build_values(target, payload)
        content = _render_tfvars(values)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_file.write_text(content, encoding="utf-8")
    try:
        os.chmod(output_file, 0o600)
    except OSError:
        # Best effort only; chmod semantics differ on Windows.
        pass
    print(f"Generated: {output_file}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate terraform.tfvars from SOPS-encrypted YAML secrets.")
    parser.add_argument(
        "target",
        choices=["proxmox", "mikrotik", "all"],
        help="Terraform target name (or 'all' for both).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove generated tfvars instead of generating.",
    )
    args = parser.parse_args()

    targets = ["proxmox", "mikrotik"] if args.target == "all" else [args.target]
    action = _cleanup_tfvars if args.cleanup else _generate_tfvars

    exit_code = 0
    for target in targets:
        result = action(target)
        if result != 0:
            exit_code = result

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
