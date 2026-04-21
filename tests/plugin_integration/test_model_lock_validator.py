#!/usr/bin/env python3
"""Integration tests for model_lock validator plugin ownership/cutover."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.model_lock"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_model_lock_validator_manifest_requires_normalized_rows() -> None:
    registry = _registry()

    normalized_rows = next(
        consume
        for consume in registry.specs[PLUGIN_ID].consumes
        if consume["from_plugin"] == "base.compiler.instance_rows" and consume["key"] == "normalized_rows"
    )
    assert normalized_rows["required"] is True
    lock_payload = next(
        consume
        for consume in registry.specs[PLUGIN_ID].consumes
        if consume["from_plugin"] == "base.compiler.model_lock_loader" and consume["key"] == "lock_payload"
    )
    model_lock_loaded = next(
        consume
        for consume in registry.specs[PLUGIN_ID].consumes
        if consume["from_plugin"] == "base.compiler.model_lock_loader" and consume["key"] == "model_lock_loaded"
    )
    assert lock_payload["required"] is True
    assert model_lock_loaded["required"] is True


def test_model_lock_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_model_lock": "core"},
        classes={"class.router": {"version": "1.0.0"}},
        objects={"obj.router": {"version": "1.0.0"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {"instance": "r1", "class_ref": "class.router", "object_ref": "obj.router"},
                ]
            }
        },
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])
    publish_for_test(ctx, "base.compiler.model_lock_loader", "lock_payload", {})
    publish_for_test(ctx, "base.compiler.model_lock_loader", "model_lock_loaded", True)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_model_lock_validator_plugin_owner_missing_lock_strict_mode():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_model_lock": "plugin",
            "strict_mode": True,
        },
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.model_lock_loader", "lock_payload", {})
    publish_for_test(ctx, "base.compiler.model_lock_loader", "model_lock_loaded", False)
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E3201" for d in result.diagnostics)
    assert any(d.path == "model.lock" for d in result.diagnostics)


def test_model_lock_validator_matches_legacy_rules_when_plugin_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_model_lock": "plugin",
            "strict_mode": False,
        },
        classes={
            "class.router": {"version": "1.0.0"},
            "class.unpinned": {"version": "0.1.0"},
        },
        objects={
            "obj.router": {"version": "2.0.0"},
            "obj.unpinned": {"version": "0.1.0"},
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {"instance": "r1", "class_ref": "class.router", "object_ref": "obj.router"},
                    {"instance": "r2", "class_ref": "class.unpinned", "object_ref": "obj.unpinned"},
                ]
            }
        },
    )
    publish_for_test(ctx, "base.compiler.model_lock_loader", "model_lock_loaded", True)
    publish_for_test(
        ctx,
        "base.compiler.model_lock_loader",
        "lock_payload",
        {
            "classes": {
                "class.router": {"version": "1.1.0"},
            },
            "objects": {
                "obj.router": {"version": "2.1.0", "class_ref": "class.switch"},
            },
        },
    )
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {"group": "devices", "instance": "r1", "class_ref": "class.router", "object_ref": "obj.router"},
            {"group": "devices", "instance": "r2", "class_ref": "class.unpinned", "object_ref": "obj.unpinned"},
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED

    codes = [d.code for d in result.diagnostics]
    assert "I2401" in codes
    assert "W2402" in codes
    assert "W2403" in codes
    assert "E2403" in codes
    # Both class and object version mismatches produce W3201
    assert codes.count("W3201") >= 2
    assert any(d.code == "I2401" and d.stage == "load" for d in result.diagnostics)


def test_model_lock_validator_reads_lock_and_rows_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_model_lock": "plugin",
            "strict_mode": False,
        },
        classes={"class.router": {"version": "1.0.0"}},
        objects={"obj.router": {"version": "1.0.0"}},
        instance_bindings={"instance_bindings": {}},
    )

    publish_for_test(ctx, "base.compiler.model_lock_loader", "model_lock_loaded", True)
    publish_for_test(ctx, "base.compiler.model_lock_loader", "lock_payload", {"classes": {}, "objects": {}})
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "r1",
                "class_ref": "class.router",
                "object_ref": "obj.router",
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    codes = [d.code for d in result.diagnostics]
    assert "I2401" in codes
    assert "W2402" in codes
    assert "W2403" in codes
    assert "E2402" not in codes


def test_model_lock_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.validator.references",
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/reference_validator.py').as_posix()}:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
            },
            {
                "id": "base.compiler.model_lock_loader",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/model_lock_loader_compiler.py').as_posix()}:ModelLockLoaderCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "init",
                "order": 35,
            },
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/instance_rows_compiler.py').as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/model_lock_validator.py').as_posix()}:ModelLockValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 110,
                "depends_on": [
                    "base.validator.references",
                    "base.compiler.model_lock_loader",
                    "base.compiler.instance_rows",
                ],
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True},
                    {"from_plugin": "base.compiler.model_lock_loader", "key": "lock_payload", "required": True},
                    {"from_plugin": "base.compiler.model_lock_loader", "key": "model_lock_loaded", "required": True},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_model_lock": "plugin", "strict_mode": False},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    model_lock_result = next(result for result in results if result.plugin_id == PLUGIN_ID)
    assert model_lock_result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in model_lock_result.diagnostics)
