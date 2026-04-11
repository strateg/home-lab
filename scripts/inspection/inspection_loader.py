#!/usr/bin/env python3
"""Shared loading and path-resolution helpers for topology inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_effective(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"effective topology not found: {path}. Run `task validate:default` first.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid effective topology payload type: {type(payload).__name__}")
    return payload


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_existing_path(path_raw: str, *, bases: list[Path]) -> Path:
    candidate = Path(path_raw)
    if candidate.is_absolute():
        return candidate
    for base in bases:
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved
    return (bases[0] / candidate).resolve()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid YAML payload type at {path}: {type(payload).__name__}")
    return payload


def load_capability_pack_catalog(
    payload: dict[str, Any],
    *,
    effective_path: Path,
) -> tuple[dict[str, dict[str, Any]], Path]:
    topology_manifest = payload.get("topology_manifest") or "topology/topology.yaml"
    manifest_path = resolve_existing_path(
        str(topology_manifest),
        bases=[Path.cwd(), repo_root(), effective_path.parent, effective_path.parent.parent],
    )
    manifest = load_yaml(manifest_path)
    framework = manifest.get("framework", {})
    if not isinstance(framework, dict):
        raise ValueError(f"invalid framework section in topology manifest: {manifest_path}")
    packs_rel = framework.get("capability_packs")
    if not isinstance(packs_rel, str) or not packs_rel.strip():
        raise ValueError(f"framework.capability_packs missing in topology manifest: {manifest_path}")

    packs_path = resolve_existing_path(
        packs_rel,
        bases=[manifest_path.parent, Path.cwd(), repo_root()],
    )
    packs_payload = load_yaml(packs_path)
    packs_raw = packs_payload.get("packs", [])
    if not isinstance(packs_raw, list):
        raise ValueError(f"invalid packs list in capability catalog: {packs_path}")

    packs: dict[str, dict[str, Any]] = {}
    for row in packs_raw:
        if not isinstance(row, dict):
            continue
        pack_id = row.get("id")
        if not isinstance(pack_id, str) or not pack_id:
            continue
        packs[pack_id] = row
    return packs, packs_path
