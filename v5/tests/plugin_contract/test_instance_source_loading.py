#!/usr/bin/env python3
"""Contract tests for ADR0071 instance source loading modes."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from compiler_runtime import load_core_compile_inputs, resolve_instance_source_mode, resolve_manifest_paths


def _load_yaml(path: Path, *, code_missing: str, code_parse: str, stage: str):
    _ = code_missing, code_parse, stage
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_layer_contract(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "group_layers": {
                    "l1_devices": "L1",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_resolve_manifest_paths_supports_optional_instance_sources(tmp_path: Path) -> None:
    manifest_paths = {
        "class_modules_root": "classes",
        "object_modules_root": "objects",
        "capability_catalog": "catalog.yaml",
        "capability_packs": "packs.yaml",
        "layer_contract": "layer-contract.yaml",
        "model_lock": "model.lock.yaml",
    }
    bundle = resolve_manifest_paths(
        manifest_paths=manifest_paths,
        resolve_repo_path=lambda value: tmp_path / value,
    )

    assert bundle.instances_root_path is None


def test_resolve_instance_source_mode_auto_resolves_to_sharded_only(tmp_path: Path) -> None:
    bundle = resolve_manifest_paths(
        manifest_paths={
            "class_modules_root": "classes",
            "object_modules_root": "objects",
            "capability_catalog": "catalog.yaml",
            "capability_packs": "packs.yaml",
            "layer_contract": "layer-contract.yaml",
            "instances_root": "instances",
            "model_lock": "model.lock.yaml",
        },
        resolve_repo_path=lambda value: tmp_path / value,
    )
    assert resolve_instance_source_mode(requested_mode="auto", paths=bundle) == "sharded-only"


def test_load_core_compile_inputs_sharded_only_loads_rows(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    shard_root = tmp_path / "instances"
    shard_file = shard_root / "l1_devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "version": "1.0.0",
                "instance": "inst.router.a",
                "group": "l1_devices",
                "layer": "L1",
                "object_ref": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = resolve_manifest_paths(
        manifest_paths={
            "class_modules_root": "classes",
            "object_modules_root": "objects",
            "capability_catalog": "catalog.yaml",
            "capability_packs": "packs.yaml",
            "layer_contract": str(layer_contract_path),
            "instances_root": str(shard_root),
            "model_lock": "model.lock.yaml",
        },
        resolve_repo_path=lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )

    diagnostics: list[dict[str, str]] = []

    def _add_diag(**kwargs):
        diagnostics.append(kwargs)

    inputs = load_core_compile_inputs(
        paths=bundle,
        instances_mode="sharded-only",
        load_yaml=_load_yaml,
        add_diag=_add_diag,
        repo_root=tmp_path,
    )

    assert inputs.instance_source_mode == "sharded-only"
    assert isinstance(inputs.instance_payload, dict)
    rows = inputs.instance_payload["instance_bindings"]["l1_devices"]
    assert len(rows) == 1
    assert rows[0]["instance"] == "inst.router.a"
    assert rows[0]["object_ref"] == "obj.shard.router"
    assert not any(item.get("severity") == "error" for item in diagnostics)


def test_load_core_compile_inputs_reports_group_layer_mismatch(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    shard_root = tmp_path / "instances"
    shard_file = shard_root / "l1_devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "version": "1.0.0",
                "instance": "inst.router.a",
                "group": "l1_devices",
                "layer": "L2",
                "object_ref": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = resolve_manifest_paths(
        manifest_paths={
            "class_modules_root": "classes",
            "object_modules_root": "objects",
            "capability_catalog": "catalog.yaml",
            "capability_packs": "packs.yaml",
            "layer_contract": str(layer_contract_path),
            "instances_root": str(shard_root),
            "model_lock": "model.lock.yaml",
        },
        resolve_repo_path=lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )

    diagnostics: list[dict[str, str]] = []

    def _add_diag(**kwargs):
        diagnostics.append(kwargs)

    inputs = load_core_compile_inputs(
        paths=bundle,
        instances_mode="sharded-only",
        load_yaml=_load_yaml,
        add_diag=_add_diag,
        repo_root=tmp_path,
    )

    assert inputs.instance_payload is None
    assert any(item.get("code") == "E3201" and "must use layer" in item.get("message", "") for item in diagnostics)


def test_load_core_compile_inputs_rejects_filename_unsafe_instance_id(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    shard_root = tmp_path / "instances"
    shard_file = shard_root / "l1_devices" / "inst.router.bad.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "version": "1.0.0",
                "instance": "inst.router:bad",
                "group": "l1_devices",
                "layer": "L1",
                "object_ref": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = resolve_manifest_paths(
        manifest_paths={
            "class_modules_root": "classes",
            "object_modules_root": "objects",
            "capability_catalog": "catalog.yaml",
            "capability_packs": "packs.yaml",
            "layer_contract": str(layer_contract_path),
            "instances_root": str(shard_root),
            "model_lock": "model.lock.yaml",
        },
        resolve_repo_path=lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )

    diagnostics: list[dict[str, str]] = []

    def _add_diag(**kwargs):
        diagnostics.append(kwargs)

    inputs = load_core_compile_inputs(
        paths=bundle,
        instances_mode="sharded-only",
        load_yaml=_load_yaml,
        add_diag=_add_diag,
        repo_root=tmp_path,
    )

    assert inputs.instance_payload is None
    assert any(item.get("code") == "E3201" and "filename-unsafe" in item.get("message", "") for item in diagnostics)
