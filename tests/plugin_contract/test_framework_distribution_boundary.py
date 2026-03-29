#!/usr/bin/env python3
"""Contract checks for framework artifact boundary policy (ADR 0081)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

import framework_lock  # noqa: E402


def _framework_manifest() -> dict:
    manifest_path = REPO_ROOT / "topology" / "framework.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict)
    return payload


def test_framework_distribution_includes_module_index() -> None:
    payload = _framework_manifest()
    files = framework_lock.collect_framework_files(
        framework_root=REPO_ROOT,
        framework_manifest=payload,
    )
    included_paths = {str(item["path"]) for item in files}
    assert "topology/module-index.yaml" in included_paths


def test_framework_distribution_excludes_topology_tools_docs() -> None:
    payload = _framework_manifest()
    files = framework_lock.collect_framework_files(
        framework_root=REPO_ROOT,
        framework_manifest=payload,
    )
    leaked = [str(item["path"]) for item in files if str(item["path"]).startswith("topology-tools/docs/")]
    assert leaked == []
