#!/usr/bin/env python3
"""Verify that tracked secrets YAML files are SOPS-encrypted."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

SECRET_SUBDIRS = ("instances", "terraform", "ansible", "bootstrap")


def _validate_encrypted_payload(node: Any, *, path: str, parent_key: str | None = None) -> list[str]:
    errors: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "sops":
                continue
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and key.endswith("_unencrypted"):
                continue
            errors.extend(_validate_encrypted_payload(value, path=child_path, parent_key=str(key)))
        return errors
    if isinstance(node, list):
        for idx, value in enumerate(node):
            child_path = f"{path}[{idx}]"
            errors.extend(_validate_encrypted_payload(value, path=child_path, parent_key=parent_key))
        return errors
    if isinstance(parent_key, str) and parent_key.endswith("_unencrypted"):
        return errors
    if node == "":
        # Empty placeholders are tolerated during staged migration.
        return errors
    if isinstance(node, str) and node.startswith("ENC["):
        return errors
    errors.append(f"ERROR: plaintext value at '{path}' (expected ENC[...] value).")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    errors: list[str] = []

    for subdir in SECRET_SUBDIRS:
        directory = repo_root / "secrets" / subdir
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                content = path.read_text(encoding="utf-8")
                payload = yaml.safe_load(content) or {}
            except OSError as exc:
                errors.append(f"ERROR: failed to read {path}: {exc}")
                continue
            except yaml.YAMLError as exc:
                errors.append(f"ERROR: failed to parse YAML {path}: {exc}")
                continue

            if not isinstance(payload, dict):
                errors.append(f"ERROR: {path} must contain a YAML mapping/object root.")
                continue
            if "sops" not in payload or not isinstance(payload.get("sops"), dict):
                errors.append(f"ERROR: {path} is not encrypted (missing top-level 'sops' mapping).")
                continue

            file_errors = _validate_encrypted_payload(payload, path="")
            for item in file_errors:
                errors.append(f"ERROR: {path}: {item.removeprefix('ERROR: ')}")

    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
