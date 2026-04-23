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
                    "devices": "L1",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _resolve_bundle(
    tmp_path: Path,
    *,
    layer_contract_path: Path,
    instances_root: str,
) -> object:
    project_root = tmp_path / "projects" / "test"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "secrets").mkdir(parents=True, exist_ok=True)
    return resolve_manifest_paths(
        framework_paths={
            "class_modules_root": "classes",
            "object_modules_root": "objects",
            "capability_catalog": "catalog.yaml",
            "capability_packs": "packs.yaml",
            "layer_contract": str(layer_contract_path),
            "model_lock": "model.lock.yaml",
        },
        project_id="test",
        project_root=project_root,
        project_manifest={
            "instances_root": instances_root,
            "secrets_root": "secrets",
        },
        resolve_repo_path=lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )


def _write_object(path: Path, *, object_id: str, layer: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@object": object_id,
                "@extends": "class.test",
                "@layer": layer,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_resolve_manifest_paths_reads_project_relative_paths(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
    )

    assert bundle.instances_root_path == tmp_path / "projects" / "test" / "instances"
    assert bundle.secrets_root_path == tmp_path / "projects" / "test" / "secrets"
    assert bundle.project_id == "test"
    assert bundle.project_manifest_path == tmp_path / "projects" / "test" / "project.yaml"


def test_resolve_instance_source_mode_auto_resolves_to_sharded_only(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)
    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
    )
    assert resolve_instance_source_mode(requested_mode="auto", paths=bundle) == "sharded-only"


def test_load_core_compile_inputs_sharded_only_loads_rows(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    rows = inputs.instance_payload["instance_bindings"]["devices"]
    assert len(rows) == 1
    assert rows[0]["instance"] == "inst.router.a"
    assert rows[0]["object_ref"] == "obj.shard.router"
    assert not any(item.get("severity") == "error" for item in diagnostics)


def test_load_core_compile_inputs_reports_group_layer_mismatch(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L2",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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


def test_load_core_compile_inputs_accepts_semantic_instance_keys(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
                "@title": "Router instance",
                "@summary": "Semantic summary",
                "@description": "Semantic description",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    rows = inputs.instance_payload["instance_bindings"]["devices"]
    assert len(rows) == 1
    assert rows[0]["instance"] == "inst.router.a"
    assert rows[0]["object_ref"] == "obj.shard.router"
    assert rows[0]["layer"] == "L1"
    assert rows[0]["title"] == "Router instance"
    assert rows[0]["summary"] == "Semantic summary"
    assert rows[0]["description"] == "Semantic description"
    assert "@title" not in rows[0]
    assert "@summary" not in rows[0]
    assert "@description" not in rows[0]
    assert not any(item.get("severity") == "error" for item in diagnostics)


def test_load_core_compile_inputs_derives_layer_from_object_when_missing(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)
    _write_object(tmp_path / "objects" / "obj.shard.router.yaml", object_id="obj.shard.router", layer="L1")

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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

    assert isinstance(inputs.instance_payload, dict)
    rows = inputs.instance_payload["instance_bindings"]["devices"]
    assert len(rows) == 1
    assert rows[0]["layer"] == "L1"
    assert not any(item.get("severity") == "error" for item in diagnostics)


def test_load_core_compile_inputs_rejects_instance_layer_conflict_with_object(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)
    _write_object(tmp_path / "objects" / "obj.shard.router.yaml", object_id="obj.shard.router", layer="L1")

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L2",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    assert any(item.get("code") == "E3201" and "conflicts with object" in item.get("message", "") for item in diagnostics)


def test_load_core_compile_inputs_rejects_semantic_metadata_collision(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
                "@title": "Router instance",
                "title": "Legacy duplicate",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    assert any(item.get("code") == "E8801" and "title" in item.get("message", "") for item in diagnostics)


def test_load_core_compile_inputs_rejects_legacy_class_ref_in_shard(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
                "class_ref": "class.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    assert any(item.get("code") == "E8801" and "class_ref" in item.get("message", "") for item in diagnostics)


def test_load_core_compile_inputs_rejects_filename_unsafe_instance_id(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.bad.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router:bad",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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


def test_load_core_compile_inputs_rejects_wrong_layer_bucket(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L2-network" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    assert any(item.get("code") == "E7108" for item in diagnostics)


def test_load_core_compile_inputs_rejects_group_directory_mismatch(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "network" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    assert any(item.get("code") == "E7109" for item in diagnostics)


def test_load_core_compile_inputs_accepts_host_sharded_instance_path(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "host-a" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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

    assert isinstance(inputs.instance_payload, dict)
    rows = inputs.instance_payload["instance_bindings"]["devices"]
    assert len(rows) == 1
    assert rows[0]["instance"] == "inst.router.a"
    assert not any(item.get("severity") == "error" for item in diagnostics)


def test_load_core_compile_inputs_warns_on_non_sharded_l4_path(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    layer_contract_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "group_layers": {
                    "vm": "L4",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L4-platform" / "vm" / "inst.vm.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "inst.vm.a",
                "group": "vm",
                "@layer": "L4",
                "@extends": "obj.shard.vm",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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

    assert isinstance(inputs.instance_payload, dict)
    assert any(item.get("code") == "W7110" for item in diagnostics)


def test_load_core_compile_inputs_accepts_host_sharded_l5_path_without_warning(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    layer_contract_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "group_layers": {
                    "services": "L5",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L5-application" / "services" / "host-a" / "svc.app.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "@version": "1.0.0",
                "@instance": "svc.app.a",
                "group": "services",
                "@layer": "L5",
                "@extends": "obj.shard.service",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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

    assert isinstance(inputs.instance_payload, dict)
    assert not any(item.get("code") == "W7110" for item in diagnostics)


def test_load_core_compile_inputs_rejects_legacy_schema_version_field(tmp_path: Path) -> None:
    layer_contract_path = tmp_path / "layer-contract.yaml"
    _write_layer_contract(layer_contract_path)

    project_root = tmp_path / "projects" / "test"
    shard_root = project_root / "instances"
    shard_file = shard_root / "L1-foundation" / "devices" / "inst.router.a.yaml"
    shard_file.parent.mkdir(parents=True, exist_ok=True)
    shard_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "@instance": "inst.router.a",
                "group": "devices",
                "@layer": "L1",
                "@extends": "obj.shard.router",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = _resolve_bundle(
        tmp_path,
        layer_contract_path=layer_contract_path,
        instances_root="instances",
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
    assert any(item.get("code") == "E7104" and "@version" in item.get("message", "") for item in diagnostics)
