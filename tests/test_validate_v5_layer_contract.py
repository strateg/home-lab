#!/usr/bin/env python3
"""Contract tests for strict v5 layer contract validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "validation" / "validate_v5_layer_contract.py"
    spec = importlib.util.spec_from_file_location("validate_v5_layer_contract", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load validate_v5_layer_contract module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _seed_repo(tmp_path: Path, *, object_has_layer: bool) -> Path:
    topology_root = tmp_path / "topology"
    projects_root = tmp_path / "projects" / "home-lab"
    class_modules_root = topology_root / "class-modules"
    object_modules_root = topology_root / "object-modules"
    instances_root = projects_root / "topology" / "instances"

    _write_yaml(
        topology_root / "topology.yaml",
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "class_modules_root": "topology/class-modules",
                "object_modules_root": "topology/object-modules",
                "model_lock": "topology/model.lock.yaml",
                "layer_contract": "topology/layer-contract.yaml",
                "capability_catalog": "topology/class-modules/L1-foundation/router/capability-catalog.yaml",
                "capability_packs": "topology/class-modules/L1-foundation/router/capability-packs.yaml",
            },
            "project": {
                "active": "home-lab",
                "projects_root": "projects",
            },
        },
    )
    _write_yaml(topology_root / "model.lock.yaml", {"core_model_version": "1.0.0", "classes": {}, "objects": {}})
    _write_yaml(
        topology_root / "layer-contract.yaml",
        {
            "group_layers": {"devices": "L1"},
            "class_layers": {"class.router": {"allowed_layers": ["L1"]}},
        },
    )
    _write_yaml(
        class_modules_root / "L1-foundation" / "class.router.yaml",
        {"@class": "class.router", "@layer": "L1", "@version": "1.0.0"},
    )
    object_payload = {"@object": "obj.router", "@extends": "class.router", "@version": "1.0.0"}
    if object_has_layer:
        object_payload["@layer"] = "L1"
    _write_yaml(object_modules_root / "obj.router.yaml", object_payload)
    _write_yaml(
        projects_root / "project.yaml",
        {
            "schema_version": 1,
            "project": "home-lab",
            "instances_root": "topology/instances",
            "secrets_root": "secrets",
        },
    )
    _write_yaml(
        instances_root / "devices" / "inst.router.a.yaml",
        {
            "@version": "1.0.0",
            "@instance": "inst.router.a",
            "group": "devices",
            "@extends": "obj.router",
        },
    )
    return tmp_path / "topology" / "topology.yaml"


def test_layer_contract_rejects_object_layer_metadata(tmp_path: Path, capsys, monkeypatch) -> None:
    mod = _load_module()
    _seed_repo(tmp_path, object_has_layer=True)
    mod.ROOT = tmp_path
    mod.DEFAULT_MANIFEST = tmp_path / "topology" / "topology.yaml"
    monkeypatch.setattr(sys, "argv", ["validate_v5_layer_contract.py"])

    code = mod.main()
    captured = capsys.readouterr()

    assert code == 1
    assert "must not declare @layer" in captured.out
    assert "object 'obj.router'" in captured.out


def test_layer_contract_accepts_class_derived_object_layers(tmp_path: Path, capsys, monkeypatch) -> None:
    mod = _load_module()
    _seed_repo(tmp_path, object_has_layer=False)
    mod.ROOT = tmp_path
    mod.DEFAULT_MANIFEST = tmp_path / "topology" / "topology.yaml"
    monkeypatch.setattr(sys, "argv", ["validate_v5_layer_contract.py"])

    code = mod.main()
    captured = capsys.readouterr()

    assert code == 0
    assert "v5 layer contract: PASS" in captured.out


def test_layer_contract_rejects_class_layer_path_mismatch(tmp_path: Path, capsys, monkeypatch) -> None:
    mod = _load_module()
    topology_path = _seed_repo(tmp_path, object_has_layer=False)
    bad_class_path = tmp_path / "topology" / "class-modules" / "L1-foundation" / "class.router.yaml"
    moved_bad_path = tmp_path / "topology" / "class-modules" / "L2-network" / "class.router.yaml"
    moved_bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_class_path.rename(moved_bad_path)

    mod.ROOT = tmp_path
    mod.DEFAULT_MANIFEST = topology_path
    monkeypatch.setattr(sys, "argv", ["validate_v5_layer_contract.py"])

    code = mod.main()
    captured = capsys.readouterr()

    assert code == 1
    assert "must be placed under 'topology/class-modules/L1-foundation/...'" in captured.out
