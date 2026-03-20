#!/usr/bin/env python3
"""Tests for framework distribution builder."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "v5" / "topology-tools" / "build-framework-distribution.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_framework_distribution", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_distribution_creates_archives_manifest_and_checksums(tmp_path: Path):
    mod = _load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    (repo_root / "v5" / "topology").mkdir(parents=True, exist_ok=True)
    (repo_root / "v5" / "topology-tools").mkdir(parents=True, exist_ok=True)
    class_file = repo_root / "v5" / "topology" / "class-modules.yaml"
    tool_file = repo_root / "v5" / "topology-tools" / "tool.py"
    class_file.write_text("class: class.test\nversion: 1.0.0\n", encoding="utf-8")
    tool_file.write_text("print('ok')\n", encoding="utf-8")

    framework_manifest = repo_root / "v5" / "topology" / "framework.yaml"
    framework_manifest.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "infra-topology-framework",
                "framework_api_version": "1.0.0",
                "framework_release_channel": "snapshot",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        "v5/topology/class-modules.yaml",
                        "v5/topology-tools/tool.py",
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    output_root = repo_root / "v5-dist" / "framework"
    config = mod.BuildConfig(
        repo_root=repo_root,
        framework_manifest=framework_manifest,
        output_root=output_root,
        version="1.2.3",
        archive_format="both",
        keep_staging=False,
    )
    result = mod.build_distribution(config)
    assert result == 0

    release_dir = output_root / "infra-topology-framework" / "1.2.3"
    assert (release_dir / "infra-topology-framework-1.2.3.zip").exists()
    assert (release_dir / "infra-topology-framework-1.2.3.tar.gz").exists()
    assert (release_dir / "checksums.sha256").exists()

    manifest_path = release_dir / "framework-dist-manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["framework_id"] == "infra-topology-framework"
    assert payload["distribution_version"] == "1.2.3"
    file_paths = {item["path"] for item in payload["files"]}
    assert "v5/topology/class-modules.yaml" in file_paths
    assert "v5/topology-tools/tool.py" in file_paths
