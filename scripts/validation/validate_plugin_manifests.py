#!/usr/bin/env python3
"""Validate plugin manifests against schema and entry module paths."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _discover_manifests(repo_root: Path) -> list[Path]:
    manifests = [repo_root / "topology-tools" / "plugins" / "plugins.yaml"]
    manifests.extend(sorted((repo_root / "topology" / "class-modules").rglob("plugins.yaml")))
    manifests.extend(sorted((repo_root / "topology" / "object-modules").rglob("plugins.yaml")))
    return manifests


def _resolve_entry_manifest_relative(manifest_dir: Path, entry: str) -> Path | None:
    if ":" not in entry:
        return None
    module_path = entry.split(":", 1)[0].strip()
    if not module_path:
        return None
    return manifest_dir / module_path


def main() -> int:
    repo_root = _repo_root()
    schema_path = repo_root / "topology-tools" / "schemas" / "plugin-manifest.schema.json"
    schema = _load_schema(schema_path)
    manifests = _discover_manifests(repo_root)

    if not manifests:
        print("ERROR: no plugin manifests discovered")
        return 1

    for manifest_path in manifests:
        if not manifest_path.exists():
            print(f"ERROR: missing manifest: {manifest_path}")
            return 1

        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = yaml.safe_load(handle) or {}

        try:
            jsonschema.validate(manifest, schema)
            print(f"OK schema: {manifest_path}")
        except jsonschema.ValidationError as exc:
            print(f"ERROR schema: {manifest_path}: {exc.message}")
            return 1

        manifest_dir = manifest_path.parent
        for plugin in manifest.get("plugins", []):
            plugin_id = plugin.get("id", "<unknown>")
            entry = str(plugin.get("entry", ""))
            resolved = _resolve_entry_manifest_relative(manifest_dir, entry)
            if resolved is None:
                continue
            if not resolved.exists():
                print(f"ERROR entry: {plugin_id}: {resolved} (from {manifest_path})")
                return 1
            print(f"OK entry: {plugin_id}")

    print("All plugin manifests validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
