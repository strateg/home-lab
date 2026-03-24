#!/usr/bin/env python3
"""Tests for v5 scaffold strict-only manifest checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_scaffold_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "v5" / "scripts" / "validation" / "validate_v5_scaffold.py"
    spec = importlib.util.spec_from_file_location("validate_v5_scaffold_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(tmp_root: Path, *, include_legacy_paths: bool) -> None:
    topology_root = tmp_root / "v5" / "topology"
    projects_root = tmp_root / "v5" / "projects" / "home-lab"
    topology_root.mkdir(parents=True, exist_ok=True)
    projects_root.mkdir(parents=True, exist_ok=True)
    (topology_root / "class-modules").mkdir(parents=True, exist_ok=True)
    (topology_root / "object-modules").mkdir(parents=True, exist_ok=True)
    (topology_root / "class-modules" / "router").mkdir(parents=True, exist_ok=True)
    (projects_root / "instances").mkdir(parents=True, exist_ok=True)
    (projects_root / "secrets").mkdir(parents=True, exist_ok=True)
    (topology_root / "model.lock.yaml").write_text(
        "core_model_version: 1.0.0\nclasses: {}\nobjects: {}\n", encoding="utf-8"
    )
    (topology_root / "layer-contract.yaml").write_text("group_layers: {}\n", encoding="utf-8")
    (topology_root / "class-modules" / "router" / "capability-catalog.yaml").write_text(
        "capabilities: []\n", encoding="utf-8"
    )
    (topology_root / "class-modules" / "router" / "capability-packs.yaml").write_text("packs: []\n", encoding="utf-8")
    (projects_root / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": "home-lab",
                "instances_root": "instances",
                "secrets_root": "secrets",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest = {
        "version": "5.0.0",
        "model": "class-object-instance",
        "framework": {
            "class_modules_root": "v5/topology/class-modules",
            "object_modules_root": "v5/topology/object-modules",
            "model_lock": "v5/topology/model.lock.yaml",
            "layer_contract": "v5/topology/layer-contract.yaml",
            "capability_catalog": "v5/topology/class-modules/router/capability-catalog.yaml",
            "capability_packs": "v5/topology/class-modules/router/capability-packs.yaml",
        },
        "project": {
            "active": "home-lab",
            "projects_root": "v5/projects",
        },
    }
    if include_legacy_paths:
        manifest["paths"] = {"instances_root": "v5/topology/instances"}
    (topology_root / "topology.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_check_topology_manifest_reports_e7808_for_legacy_paths(monkeypatch, tmp_path: Path) -> None:
    mod = _load_scaffold_module()
    _write_manifest(tmp_path, include_legacy_paths=True)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    errors: list[dict[str, str]] = []
    mod.check_topology_manifest(errors)

    assert any(item.get("code") == "E7808" for item in errors)
    assert any("section 'paths'" in str(item.get("message", "")) for item in errors)


def test_check_topology_manifest_accepts_sharded_only_paths(monkeypatch, tmp_path: Path) -> None:
    mod = _load_scaffold_module()
    _write_manifest(tmp_path, include_legacy_paths=False)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    errors: list[dict[str, str]] = []
    mod.check_topology_manifest(errors)

    assert not any(item.get("code") == "E7808" for item in errors)
