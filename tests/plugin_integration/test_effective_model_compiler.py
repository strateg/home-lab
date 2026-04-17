#!/usr/bin/env python3
"""Integration tests for ADR0069 effective model compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.effective_model"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_effective_model_compiler_publishes_candidate():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={
            "class.router": {
                "class": "class.router",
                "version": "1.0.0",
                "required_capabilities": ["cap.net.interface.ethernet"],
            }
        },
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
                "enabled_capabilities": ["cap.net.interface.ethernet"],
            }
        },
        config={},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "rtr-1",
                "layer": "L1",
                "source_id": "rtr-1",
                "class_ref": "class.router",
                "object_ref": "obj.router.test",
                "status": "modeled",
                "notes": "",
                "runtime": None,
                "firmware_ref": None,
                "os_refs": [],
                "embedded_in": None,
                "extensions": {
                    "length_m": 3,
                    "endpoint_a": {"device_ref": "left", "port": "eth0"},
                },
            }
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    keys = ctx.get_published_keys(PLUGIN_ID)
    assert "effective_model_candidate" in keys
    assert isinstance(ctx.compiled_json, dict)
    assert "instances" in ctx.compiled_json
    assert "devices" in ctx.compiled_json["instances"]
    first_row = ctx.compiled_json["instances"]["devices"][0]
    assert first_row["instance_id"] == "rtr-1"
    assert first_row["instance_data"]["length_m"] == 3
    assert first_row["instance_data"]["endpoint_a"]["port"] == "eth0"
    assert first_row["class"]["parent_class"] is None
    assert first_row["class"]["lineage"] == ["class.router"]
    assert first_row["object"]["extends_class"] == "class.router"
    assert first_row["object"]["materializes_class"] == "class.router"
    assert first_row["object"]["class_lineage"] == ["class.router"]
    assert first_row["instance"]["extends_object"] == "obj.router.test"
    assert first_row["instance"]["materializes_object"] == "obj.router.test"
    assert first_row["instance"]["materializes_class"] == "class.router"
    assert first_row["instance"]["resolved_lineage"] == ["class.router"]
    assert ctx.compiled_json["classes"]["class.router"]["lineage"] == ["class.router"]
    assert ctx.compiled_json["objects"]["obj.router.test"]["class_lineage"] == ["class.router"]
    assert ctx.compiled_json["compiled_model_version"] == "1.0"
    assert isinstance(ctx.compiled_json.get("compiled_at"), str)
    assert isinstance(ctx.compiled_json.get("compiler_pipeline_version"), str)
    assert isinstance(ctx.compiled_json.get("source_manifest_digest"), str)
    assert "class_ref" not in first_row
    assert "object_ref" not in first_row


def test_effective_model_compiler_requires_subscribed_normalized_rows():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={"class.router": {"class": "class.router", "version": "1.0.0"}},
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
            }
        },
        config={},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-from-raw-bindings",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.FAILED
    assert result.has_errors
    assert any(diag.code == "E6901" for diag in result.diagnostics)


def test_effective_model_compiler_reads_normalized_rows_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={"class.router": {"class": "class.router", "version": "1.0.0"}},
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
            }
        },
        config={},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-from-raw-bindings",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )

    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "rtr-from-subscribe",
                "layer": "L1",
                "source_id": "rtr-from-subscribe",
                "class_ref": "class.router",
                "object_ref": "obj.router.test",
                "status": "modeled",
                "notes": "",
                "runtime": None,
                "firmware_ref": None,
                "os_refs": [],
                "embedded_in": None,
                "extensions": {"length_m": 1},
            }
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    rows = ctx.compiled_json["instances"]["devices"]
    assert [row["instance_id"] for row in rows] == ["rtr-from-subscribe"]
    assert rows[0]["instance_data"]["length_m"] == 1


def test_effective_model_execute_stage_commits_compiled_json_authoritatively(tmp_path):
    (tmp_path / "stubs.py").write_text(
        "\n".join(
            [
                "from kernel import CompilerPlugin, PluginResult, Stage",
                "",
                "class NoopRowsCompiler(CompilerPlugin):",
                "    def execute(self, ctx, stage: Stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": "stubs.py:NoopRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 40,
                "produces": [{"key": "normalized_rows", "scope": "pipeline_shared"}],
            },
            {
                "id": PLUGIN_ID,
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
                "compiled_json_owner": True,
                "subinterpreter_compatible": True,
                "depends_on": ["base.compiler.instance_rows"],
                "produces": [{"key": "effective_model_candidate", "scope": "pipeline_shared"}],
                "consumes": [{"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": False}],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={"class.router": {"class": "class.router", "version": "1.0.0"}},
        objects={"obj.router.test": {"object": "obj.router.test", "version": "1.0.0", "class_ref": "class.router"}},
        config={},
        instance_bindings={"instance_bindings": {"devices": []}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "node-stage",
                "layer": "L1",
                "source_id": "node-stage",
                "class_ref": "class.router",
                "object_ref": "obj.router.test",
                "status": "modeled",
                "notes": "",
                "runtime": None,
                "firmware_ref": None,
                "os_refs": [],
                "embedded_in": None,
                "extensions": {"rack": "R1"},
            }
        ],
    )
    ctx._clear_execution_context()

    results = registry.execute_stage(Stage.COMPILE, ctx, parallel_plugins=False)

    assert [result.plugin_id for result in results] == ["base.compiler.instance_rows", PLUGIN_ID]
    assert all(result.status == PluginStatus.SUCCESS for result in results)
    assert isinstance(ctx.compiled_json, dict)
    assert ctx.compiled_json["instances"]["devices"][0]["instance_id"] == "node-stage"
    assert ctx.compiled_json["instances"]["devices"][0]["instance_data"]["rack"] == "R1"
    assert ctx.get_published_data()[PLUGIN_ID]["effective_model_candidate"] == ctx.compiled_json


def test_effective_model_compiler_includes_inherited_lineage_fields():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={
            "class.base": {"class": "class.base", "version": "1.0.0"},
            "class.child": {"class": "class.child", "version": "1.0.0", "extends": "class.base"},
        },
        objects={
            "obj.child": {"object": "obj.child", "version": "1.0.0", "class_ref": "class.child"},
        },
        config={},
        instance_bindings={"instance_bindings": {"devices": []}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "node-1",
                "layer": "L1",
                "source_id": "node-1",
                "class_ref": "class.child",
                "object_ref": "obj.child",
                "status": "modeled",
                "notes": "",
                "runtime": None,
                "firmware_ref": None,
                "os_refs": [],
                "embedded_in": None,
                "extensions": {},
            }
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    row = ctx.compiled_json["instances"]["devices"][0]
    assert row["class"]["lineage"] == ["class.base", "class.child"]
    assert row["class"]["parent_class"] == "class.base"
    assert row["object"]["class_lineage"] == ["class.base", "class.child"]
    assert row["instance"]["resolved_lineage"] == ["class.base", "class.child"]
    assert ctx.compiled_json["classes"]["class.child"]["lineage"] == ["class.base", "class.child"]
    assert ctx.compiled_json["objects"]["obj.child"]["class_lineage"] == ["class.base", "class.child"]
