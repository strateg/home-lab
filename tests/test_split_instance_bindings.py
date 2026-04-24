#!/usr/bin/env python3
"""Contract tests for split-instance-bindings canonical shard output."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "topology-tools" / "utils" / "split-instance-bindings.py"
    spec = importlib.util.spec_from_file_location("split_instance_bindings", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load split-instance-bindings module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_compiler_runtime():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "topology-tools" / "compiler_runtime.py"
    spec = importlib.util.spec_from_file_location("compiler_runtime", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load compiler_runtime module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_write_shards_emits_canonical_semantic_keys(tmp_path: Path) -> None:
    mod = _load_module()
    output_root = tmp_path / "instances"
    bindings = {
        "instance_bindings": {
            "devices": [
                {
                    "instance": "inst.router.a",
                    "object_ref": "obj.router",
                    "layer": "L1",
                    "class_ref": "class.router",
                    "note": "preserved",
                }
            ]
        }
    }

    count, rewrite_map = mod._write_shards(
        bindings=bindings,
        output_root=output_root,
        drop_class_ref=True,
        sanitize_instance_ids=False,
        force=True,
    )

    assert count == 1
    assert rewrite_map == {}

    payload = yaml.safe_load((output_root / "devices" / "inst.router.a.yaml").read_text(encoding="utf-8")) or {}
    assert payload["@instance"] == "inst.router.a"
    assert payload["@extends"] == "obj.router"
    assert payload["@version"] == "1.0.0"
    assert payload["@group"] == "devices"
    assert payload["note"] == "preserved"
    assert "layer" not in payload
    assert "class_ref" not in payload
    assert "object_ref" not in payload
    assert "instance" not in payload
    assert "version" not in payload


def test_write_shards_requires_non_empty_object_ref(tmp_path: Path) -> None:
    mod = _load_module()
    output_root = tmp_path / "instances"
    bindings = {
        "instance_bindings": {
            "devices": [
                {
                    "instance": "inst.router.a",
                    "layer": "L1",
                }
            ]
        }
    }

    try:
        mod._write_shards(
            bindings=bindings,
            output_root=output_root,
            drop_class_ref=True,
            sanitize_instance_ids=False,
            force=True,
        )
    except ValueError as exc:
        assert "missing non-empty 'object_ref'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing object_ref.")


def test_default_paths_target_project_instances_root() -> None:
    mod = _load_module()
    assert mod.DEFAULT_OUTPUT_ROOT.as_posix().endswith("projects/home-lab/topology/instances")
    assert mod.DEFAULT_PROJECT_FILE.as_posix().endswith("projects/home-lab/topology/instances/project.yaml")


def test_split_output_without_instance_layer_is_ingestable_via_object_class_derivation(tmp_path: Path) -> None:
    split_mod = _load_module()
    runtime_mod = _load_compiler_runtime()

    # Seed class/object chain for derived layer resolution.
    (tmp_path / "classes").mkdir(parents=True, exist_ok=True)
    (tmp_path / "objects").mkdir(parents=True, exist_ok=True)
    (tmp_path / "classes" / "class.test.yaml").write_text(
        yaml.safe_dump({"@version": "1.0.0", "@class": "class.test", "@layer": "L1"}, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / "objects" / "obj.router.yaml").write_text(
        yaml.safe_dump({"@version": "1.0.0", "@object": "obj.router", "@extends": "class.test"}, sort_keys=False),
        encoding="utf-8",
    )

    layer_contract = tmp_path / "layer-contract.yaml"
    layer_contract.write_text(
        yaml.safe_dump({"schema_version": 1, "group_layers": {"devices": "L1"}}, sort_keys=False),
        encoding="utf-8",
    )

    project_root = tmp_path / "projects" / "test"
    instances_root = project_root / "instances"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "secrets").mkdir(parents=True, exist_ok=True)

    # Generate canonical shard (without @layer) from legacy-like row.
    bindings = {
        "instance_bindings": {
            "devices": [{"instance": "inst.router.a", "object_ref": "obj.router", "layer": "L1"}]
        }
    }
    split_mod._write_shards(
        bindings=bindings,
        output_root=instances_root,
        drop_class_ref=True,
        sanitize_instance_ids=False,
        force=True,
    )

    bundle = runtime_mod.resolve_manifest_paths(
        framework_paths={
            "class_modules_root": "classes",
            "object_modules_root": "objects",
            "capability_catalog": "catalog.yaml",
            "capability_packs": "packs.yaml",
            "layer_contract": str(layer_contract),
            "model_lock": "model.lock.yaml",
        },
        project_id="test",
        project_root=project_root,
        project_manifest={"instances_root": "instances", "secrets_root": "secrets"},
        resolve_repo_path=lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )

    diagnostics: list[dict[str, str]] = []

    def _load_yaml(path: Path, *, code_missing: str, code_parse: str, stage: str):
        _ = code_missing, code_parse, stage
        if not path.exists():
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def _add_diag(**kwargs):
        diagnostics.append(kwargs)

    inputs = runtime_mod.load_core_compile_inputs(
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
    assert rows[0]["object_ref"] == "obj.router"
    assert rows[0]["layer"] == "L1"
    assert not any(item.get("severity") == "error" for item in diagnostics)
