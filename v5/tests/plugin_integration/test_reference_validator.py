#!/usr/bin/env python3
"""Integration tests for reference validator plugin ownership/parity prep."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.references"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_reference_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "core"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_reference_validator_detects_missing_refs_when_plugin_owner():
    registry = _registry()
    rows = [
        {
            "group": "l1_devices",
            "instance": "inst.dev.1",
            "class_ref": "class.router",
            "object_ref": "obj.router",
            "firmware_ref": "inst.fw.unknown",
            "os_refs": ["inst.os.unknown"],
        }
    ]
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" and d.stage == "resolve" for d in result.diagnostics)


def test_reference_validator_enforces_required_software_policies():
    registry = _registry()
    rows = [
        {
            "group": "l1_devices",
            "instance": "inst.dev.2",
            "class_ref": "class.router",
            "object_ref": "obj.router",
            "firmware_ref": None,
            "os_refs": [],
        }
    ]
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={
            "class.router": {
                "class": "class.router",
                "os_policy": "required",
                "firmware_policy": "required",
                "multi_boot": False,
            }
        },
        objects={"obj.router": {"object": "obj.router", "class_ref": "class.router"}},
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    policy_errors = [d for d in result.diagnostics if d.code == "E3201"]
    assert len(policy_errors) >= 2


def test_reference_validator_reads_rows_and_catalog_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "l1_devices",
                "instance": "inst.dev.subscribed",
                "class_ref": "class.router",
                "object_ref": "obj.router",
                "firmware_ref": "inst.fw.unknown",
                "os_refs": ["inst.os.unknown"],
            }
        ],
    )
    ctx._clear_execution_context()

    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" and d.stage == "resolve" for d in result.diagnostics)


def test_reference_validator_accepts_valid_storage_relations():
    registry = _registry()
    rows = [
        {
            "group": "l3_storage",
            "instance": "inst.pool.local",
            "layer": "L3",
            "class_ref": "class.storage.pool",
            "object_ref": "obj.pool.local",
            "extensions": {},
        },
        {
            "group": "l3_storage",
            "instance": "inst.vol.local",
            "layer": "L3",
            "class_ref": "class.storage.volume",
            "object_ref": "obj.vol.local",
            "extensions": {},
        },
        {
            "group": "l4_lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.container",
            "object_ref": "obj.workload.local",
            "extensions": {"storage": {"pool_ref": "inst.pool.local"}},
        },
        {
            "group": "l5_services",
            "instance": "inst.service.local",
            "layer": "L5",
            "class_ref": "class.service.database",
            "object_ref": "obj.service.local",
            "extensions": {"storage": {"volume_ref": "inst.vol.local"}},
        },
    ]
    classes = {
        "class.storage.pool": {"class": "class.storage.pool"},
        "class.storage.volume": {"class": "class.storage.volume"},
        "class.compute.workload.container": {"class": "class.compute.workload.container"},
        "class.service.database": {"class": "class.service.database"},
    }
    objects = {
        "obj.pool.local": {"object": "obj.pool.local", "class_ref": "class.storage.pool"},
        "obj.vol.local": {"object": "obj.vol.local", "class_ref": "class.storage.volume"},
        "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.container"},
        "obj.service.local": {"object": "obj.service.local", "class_ref": "class.service.database"},
    }

    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E74") for d in result.diagnostics)


def test_reference_validator_rejects_unknown_storage_relation_target():
    registry = _registry()
    rows = [
        {
            "group": "l4_lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.container",
            "object_ref": "obj.workload.local",
            "extensions": {"storage": {"pool_ref": "inst.pool.missing"}},
        }
    ]
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={"class.compute.workload.container": {"class": "class.compute.workload.container"}},
        objects={
            "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.container"}
        },
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7401" for d in result.diagnostics)


def test_reference_validator_rejects_storage_relation_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "l3_storage",
            "instance": "inst.pool.local",
            "layer": "L3",
            "class_ref": "class.storage.pool",
            "object_ref": "obj.pool.local",
            "extensions": {},
        },
        {
            "group": "l1_devices",
            "instance": "inst.router.local",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.local",
            "extensions": {"storage": {"pool_ref": "inst.pool.local"}},
        },
    ]
    classes = {
        "class.storage.pool": {"class": "class.storage.pool"},
        "class.router": {"class": "class.router"},
    }
    objects = {
        "obj.pool.local": {"object": "obj.pool.local", "class_ref": "class.storage.pool"},
        "obj.router.local": {"object": "obj.router.local", "class_ref": "class.router"},
    }

    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7403" for d in result.diagnostics)


def test_reference_validator_rejects_storage_relation_target_class_mismatch():
    registry = _registry()
    rows = [
        {
            "group": "l3_storage",
            "instance": "inst.pool.local",
            "layer": "L3",
            "class_ref": "class.storage.pool",
            "object_ref": "obj.pool.local",
            "extensions": {},
        },
        {
            "group": "l5_services",
            "instance": "inst.service.local",
            "layer": "L5",
            "class_ref": "class.service.database",
            "object_ref": "obj.service.local",
            "extensions": {"storage": {"volume_ref": "inst.pool.local"}},
        },
    ]
    classes = {
        "class.storage.pool": {"class": "class.storage.pool"},
        "class.service.database": {"class": "class.service.database"},
    }
    objects = {
        "obj.pool.local": {"object": "obj.pool.local", "class_ref": "class.storage.pool"},
        "obj.service.local": {"object": "obj.service.local", "class_ref": "class.service.database"},
    }

    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7402" for d in result.diagnostics)
