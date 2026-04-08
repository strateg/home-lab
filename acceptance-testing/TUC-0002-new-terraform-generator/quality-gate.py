#!/usr/bin/env python3
"""Quality gate for TUC-0002 (new Terraform generator)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml


def _list_plugin_ids(manifest_path: Path) -> set[str]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return set()
    out: set[str] = set()
    for row in plugins:
        if not isinstance(row, dict):
            continue
        plugin_id = row.get("id")
        if isinstance(plugin_id, str) and plugin_id.strip():
            out.add(plugin_id.strip())
    return out


def main() -> int:
    tuc_root = Path(__file__).resolve().parent
    repo_root = tuc_root.parents[1]
    analysis_dir = tuc_root / "analysis"
    artifacts_dir = tuc_root / "artifacts"

    required = [
        tuc_root / "TUC.md",
        tuc_root / "README.md",
        tuc_root / "TEST-MATRIX.md",
        tuc_root / "HOW-TO.md",
        tuc_root / "quality-gate.py",
        analysis_dir / "IMPLEMENTATION-PLAN.md",
        analysis_dir / "EVIDENCE-LOG.md",
        analysis_dir / "PROJECT-STATUS-REPORT.md",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        print("Quality gate failed: missing required files")
        for path in missing:
            print(f"- {path}")
        return 1

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    marker = artifacts_dir / ".gitkeep"
    if not marker.exists():
        marker.write_text("", encoding="utf-8")

    plugin_id = os.getenv("NEW_TERRAFORM_PLUGIN_ID", "").strip()
    if plugin_id:
        manifest_paths = [
            repo_root / "topology-tools" / "plugins" / "plugins.yaml",
            *sorted((repo_root / "topology" / "object-modules").glob("*/plugins.yaml")),
        ]
        discovered: set[str] = set()
        for manifest in manifest_paths:
            if manifest.exists():
                discovered.update(_list_plugin_ids(manifest))
        if plugin_id not in discovered:
            print(f"Quality gate failed: plugin id not found in manifests: {plugin_id}")
            return 1
        print(f"Plugin check passed: {plugin_id}")
    else:
        print("Plugin check skipped: set NEW_TERRAFORM_PLUGIN_ID for strict manifest validation.")

    print("Quality gate passed: TUC-0002 structure is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
