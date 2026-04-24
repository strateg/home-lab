#!/usr/bin/env python3
"""Tests for verify-framework-artifact-contents utility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "verify-framework-artifact-contents.py"


def _write_manifest(path: Path, files: list[str]) -> None:
    payload = {
        "schema_version": 1,
        "framework_id": "infra-topology-framework",
        "distribution_version": "1.2.3",
        "files": [{"path": item, "size": 1, "sha256": "0" * 64} for item in files],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def test_verify_framework_artifact_contents_passes_on_runtime_only_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "dist" / "framework" / "infra-topology-framework" / "1.2.3" / "framework-dist-manifest.json"
    _write_manifest(
        manifest,
        [
            "framework.yaml",
            "topology/class-modules/L1-foundation/router/class.router.yaml",
            "topology/object-modules/router/object.router.yaml",
            "topology/layer-contract.yaml",
            "topology/model.lock.yaml",
            "topology/profile-map.yaml",
            "topology/module-index.yaml",
            "topology/semantic-keywords.yaml",
            "topology-tools/compile-topology.py",
        ],
    )

    output = tmp_path / "result.json"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--output-json",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_verify_framework_artifact_contents_fails_on_forbidden_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "dist" / "framework" / "infra-topology-framework" / "1.2.3" / "framework-dist-manifest.json"
    _write_manifest(
        manifest,
        [
            "framework.yaml",
            "topology/class-modules/L1-foundation/router/class.router.yaml",
            "topology/object-modules/router/object.router.yaml",
            "topology/layer-contract.yaml",
            "topology/model.lock.yaml",
            "topology/profile-map.yaml",
            "topology/module-index.yaml",
            "topology/semantic-keywords.yaml",
            "topology-tools/compile-topology.py",
            "docs/README.md",
        ],
    )

    output = tmp_path / "result.json"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--output-json",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "docs/README.md" in payload["forbidden_present"]
