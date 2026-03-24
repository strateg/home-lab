#!/usr/bin/env python3
"""Tests for framework distribution builder."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import yaml


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "topology-tools").is_dir() or (candidate / "topology-tools").is_dir():
            return candidate
    return current.parents[3]


def _tools_root(repo_root: Path) -> Path:
    extracted = repo_root / "topology-tools"
    if extracted.is_dir():
        return extracted
    return repo_root / "topology-tools"


REPO_ROOT = _detect_repo_root()
SCRIPT_PATH = _tools_root(REPO_ROOT) / "build-framework-distribution.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_framework_distribution", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_module_from(path: Path):
    spec = importlib.util.spec_from_file_location("build_framework_distribution_extracted", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_distribution_creates_archives_manifest_and_checksums(tmp_path: Path):
    mod = _load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    (repo_root / "topology").mkdir(parents=True, exist_ok=True)
    (repo_root / "topology-tools").mkdir(parents=True, exist_ok=True)
    class_file = repo_root / "topology" / "class-modules.yaml"
    tool_file = repo_root / "topology-tools" / "tool.py"
    class_file.write_text("class: class.test\nversion: 1.0.0\n", encoding="utf-8")
    tool_file.write_text("print('ok')\n", encoding="utf-8")

    framework_manifest = repo_root / "topology" / "framework.yaml"
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
                        "topology/class-modules.yaml",
                        "topology-tools/tool.py",
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    output_root = repo_root / "dist" / "framework"
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
    assert "topology/class-modules.yaml" in file_paths
    assert "topology-tools/tool.py" in file_paths


def test_default_paths_detect_extracted_layout(tmp_path: Path):
    framework_root = tmp_path / "framework"
    tools_root = framework_root / "topology-tools"
    tools_root.mkdir(parents=True, exist_ok=True)

    framework_manifest = framework_root / "framework.yaml"
    framework_manifest.write_text("schema_version: 1\nframework_id: test\n", encoding="utf-8")

    copied_script = tools_root / "build-framework-distribution.py"
    copied_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    mod = _load_module_from(copied_script)

    assert mod._default_repo_root() == framework_root
    assert mod._default_framework_manifest() == framework_manifest
    assert mod._default_output_root() == framework_root / "dist" / "framework"


def test_build_distribution_supports_include_mapping_with_topology_targets(tmp_path: Path):
    mod = _load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    source_framework = repo_root / "topology"
    source_tools = repo_root / "topology-tools"
    (source_framework / "class-modules").mkdir(parents=True, exist_ok=True)
    source_tools.mkdir(parents=True, exist_ok=True)
    (source_framework / "class-modules" / "class.yaml").write_text("class: test\n", encoding="utf-8")
    (source_tools / "compile-topology.py").write_text("print('ok')\n", encoding="utf-8")

    framework_manifest = source_framework / "framework.yaml"
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
                        {"from": "topology/framework.yaml", "to": "framework.yaml"},
                        {"from": "topology/class-modules", "to": "topology/class-modules"},
                        {"from": "topology-tools", "to": "topology-tools"},
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    output_root = repo_root / "dist" / "framework"
    config = mod.BuildConfig(
        repo_root=repo_root,
        framework_manifest=framework_manifest,
        output_root=output_root,
        version="2.0.0",
        archive_format="both",
        keep_staging=False,
    )
    result = mod.build_distribution(config)
    assert result == 0

    release_dir = output_root / "infra-topology-framework" / "2.0.0"
    manifest_path = release_dir / "framework-dist-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    file_paths = {item["path"] for item in payload["files"]}
    assert "framework.yaml" in file_paths
    assert "topology/class-modules/class.yaml" in file_paths
    assert "topology-tools/compile-topology.py" in file_paths
    assert all(not path.startswith("v5/") for path in file_paths)

    archive_path = release_dir / "infra-topology-framework-2.0.0.zip"
    with zipfile.ZipFile(archive_path) as archive:
        framework_yaml = archive.read("infra-topology-framework-2.0.0/framework.yaml").decode("utf-8")
    framework_payload = yaml.safe_load(framework_yaml) or {}
    distribution = framework_payload.get("distribution", {})
    include = distribution.get("include", [])
    assert "framework.yaml" in include
    assert "topology/class-modules" in include
    assert "topology-tools" in include
    assert all(not str(item).startswith("v5/") for item in include)
