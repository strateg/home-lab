#!/usr/bin/env python3
"""Contract tests for layer derivation audit report utility."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "topology-tools" / "utils" / "generate-layer-derivation-report.py"
    spec = importlib.util.spec_from_file_location("generate_layer_derivation_report", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load generate-layer-derivation-report module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _seed_repo(tmp_path: Path, *, object_has_layer: bool = False, instance_layer: str | None = None) -> Path:
    topology_root = tmp_path / "topology"
    projects_root = tmp_path / "projects" / "home-lab"
    _write_yaml(
        topology_root / "topology.yaml",
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "class_modules_root": "topology/class-modules",
                "object_modules_root": "topology/object-modules",
                "semantic_keywords": "topology/semantic-keywords.yaml",
            },
            "project": {"active": "home-lab", "projects_root": "projects"},
        },
    )
    # Keep default registry by writing empty semantic file
    _write_yaml(topology_root / "semantic-keywords.yaml", {})
    _write_yaml(
        topology_root / "class-modules" / "L1-foundation" / "class.router.yaml",
        {"@class": "class.router", "@layer": "L1", "@version": "1.0.0"},
    )
    object_payload = {"@object": "obj.router", "@extends": "class.router", "@version": "1.0.0"}
    if object_has_layer:
        object_payload["@layer"] = "L1"
    _write_yaml(topology_root / "object-modules" / "obj.router.yaml", object_payload)
    _write_yaml(
        projects_root / "project.yaml",
        {"schema_version": 1, "project": "home-lab", "instances_root": "topology/instances", "secrets_root": "secrets"},
    )
    instance_payload = {"@version": "1.0.0", "@instance": "inst.router", "group": "devices", "@extends": "obj.router"}
    if instance_layer is not None:
        instance_payload["@layer"] = instance_layer
    _write_yaml(
        projects_root / "topology" / "instances" / "L1-foundation" / "devices" / "inst.router.yaml",
        instance_payload,
    )
    return topology_root / "topology.yaml"


def test_layer_derivation_report_passes_on_clean_inputs(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    topology = _seed_repo(tmp_path, object_has_layer=False, instance_layer=None)
    output_json = tmp_path / "build" / "diagnostics" / "layer-derivation-report.json"
    output_txt = tmp_path / "build" / "diagnostics" / "layer-derivation-report.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-layer-derivation-report.py",
            "--repo-root",
            str(tmp_path),
            "--topology",
            str(topology),
            "--output-json",
            str(output_json),
            "--output-txt",
            str(output_txt),
            "--enforce",
        ],
    )
    code = mod.main()
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["summary"]["violations"] == 0


def test_layer_derivation_report_fails_when_object_declares_layer(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    topology = _seed_repo(tmp_path, object_has_layer=True, instance_layer=None)
    output_json = tmp_path / "build" / "diagnostics" / "layer-derivation-report.json"
    output_txt = tmp_path / "build" / "diagnostics" / "layer-derivation-report.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-layer-derivation-report.py",
            "--repo-root",
            str(tmp_path),
            "--topology",
            str(topology),
            "--output-json",
            str(output_json),
            "--output-txt",
            str(output_txt),
            "--enforce",
        ],
    )
    code = mod.main()
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert code == 1
    assert payload["summary"]["violations"] > 0
    assert any(item["code"] == "LDR001" for item in payload["violations"])

