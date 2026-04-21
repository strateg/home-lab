#!/usr/bin/env python3
"""Integration tests for reference validator plugin ownership/parity prep."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.references"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_reference_validator_manifest_requires_normalized_rows() -> None:
    registry = _registry()

    normalized_rows = next(
        consume
        for consume in registry.specs[PLUGIN_ID].consumes
        if consume["from_plugin"] == "base.compiler.instance_rows" and consume["key"] == "normalized_rows"
    )
    assert normalized_rows["required"] is True
    catalog_ids = next(
        consume
        for consume in registry.specs[PLUGIN_ID].consumes
        if consume["from_plugin"] == "base.compiler.capability_contract_loader" and consume["key"] == "catalog_ids"
    )
    assert catalog_ids["required"] is True


def test_reference_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "core"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_reference_validator_detects_missing_refs_when_plugin_owner():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "inst.dev.1",
            "class_ref": "class.router",
            "object_ref": "obj.router",
            "firmware_ref": "inst.fw.unknown",
            "os_refs": ["inst.os.unknown"],
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" and d.stage == "resolve" for d in result.diagnostics)


def test_reference_validator_enforces_required_software_policies():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "inst.dev.2",
            "class_ref": "class.router",
            "object_ref": "obj.router",
            "firmware_ref": None,
            "os_refs": [],
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
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
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    policy_errors = [d for d in result.diagnostics if d.code == "E3201"]
    assert len(policy_errors) >= 2


def test_reference_validator_reads_rows_and_catalog_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "inst.dev.subscribed",
                "class_ref": "class.router",
                "object_ref": "obj.router",
                "firmware_ref": "inst.fw.unknown",
                "os_refs": ["inst.os.unknown"],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" and d.stage == "resolve" for d in result.diagnostics)


def test_reference_validator_accepts_valid_storage_relations():
    registry = _registry()
    rows = [
        {
            "group": "pools",
            "instance": "inst.pool.local",
            "layer": "L3",
            "class_ref": "class.storage.pool",
            "object_ref": "obj.pool.local",
            "extensions": {},
        },
        {
            "group": "data-assets",
            "instance": "inst.vol.local",
            "layer": "L3",
            "class_ref": "class.storage.volume",
            "object_ref": "obj.vol.local",
            "extensions": {},
        },
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"storage": {"pool_ref": "inst.pool.local"}},
        },
        {
            "group": "services",
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
        "class.compute.workload.lxc": {"class": "class.compute.workload.lxc"},
        "class.service.database": {"class": "class.service.database"},
    }
    objects = {
        "obj.pool.local": {"object": "obj.pool.local", "class_ref": "class.storage.pool"},
        "obj.vol.local": {"object": "obj.vol.local", "class_ref": "class.storage.volume"},
        "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"},
        "obj.service.local": {"object": "obj.service.local", "class_ref": "class.service.database"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E74") for d in result.diagnostics)


def test_reference_validator_rejects_unknown_storage_relation_target():
    registry = _registry()
    rows = [
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"storage": {"pool_ref": "inst.pool.missing"}},
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={"class.compute.workload.lxc": {"class": "class.compute.workload.lxc"}},
        objects={"obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"}},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7401" for d in result.diagnostics)


def test_reference_validator_rejects_storage_relation_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "pools",
            "instance": "inst.pool.local",
            "layer": "L3",
            "class_ref": "class.storage.pool",
            "object_ref": "obj.pool.local",
            "extensions": {},
        },
        {
            "group": "devices",
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7403" for d in result.diagnostics)


def test_reference_validator_rejects_storage_relation_target_class_mismatch():
    registry = _registry()
    rows = [
        {
            "group": "pools",
            "instance": "inst.pool.local",
            "layer": "L3",
            "class_ref": "class.storage.pool",
            "object_ref": "obj.pool.local",
            "extensions": {},
        },
        {
            "group": "services",
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7402" for d in result.diagnostics)


def test_reference_validator_accepts_valid_network_bridge_relation():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.bridge.local",
            "layer": "L2",
            "class_ref": "class.network.bridge",
            "object_ref": "obj.bridge.local",
            "extensions": {},
        },
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"bridge_ref": "inst.bridge.local"}},
        },
    ]
    classes = {
        "class.network.bridge": {"class": "class.network.bridge"},
        "class.compute.workload.lxc": {"class": "class.compute.workload.lxc"},
    }
    objects = {
        "obj.bridge.local": {"object": "obj.bridge.local", "class_ref": "class.network.bridge"},
        "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E75") for d in result.diagnostics)


def test_reference_validator_rejects_unknown_network_bridge_target():
    registry = _registry()
    rows = [
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"bridge_ref": "inst.bridge.missing"}},
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={"class.compute.workload.lxc": {"class": "class.compute.workload.lxc"}},
        objects={"obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"}},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7501" for d in result.diagnostics)


def test_reference_validator_rejects_network_bridge_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.bridge.local",
            "layer": "L2",
            "class_ref": "class.network.bridge",
            "object_ref": "obj.bridge.local",
            "extensions": {},
        },
        {
            "group": "services",
            "instance": "inst.service.local",
            "layer": "L5",
            "class_ref": "class.service.database",
            "object_ref": "obj.service.local",
            "extensions": {"network": {"bridge_ref": "inst.bridge.local"}},
        },
    ]
    classes = {
        "class.network.bridge": {"class": "class.network.bridge"},
        "class.service.database": {"class": "class.service.database"},
    }
    objects = {
        "obj.bridge.local": {"object": "obj.bridge.local", "class_ref": "class.network.bridge"},
        "obj.service.local": {"object": "obj.service.local", "class_ref": "class.service.database"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7503" for d in result.diagnostics)


def test_reference_validator_rejects_network_bridge_target_class_mismatch():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.vlan.local",
            "layer": "L2",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.vlan.local",
            "extensions": {},
        },
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"bridge_ref": "inst.vlan.local"}},
        },
    ]
    classes = {
        "class.network.vlan": {"class": "class.network.vlan"},
        "class.compute.workload.lxc": {"class": "class.compute.workload.lxc"},
    }
    objects = {
        "obj.vlan.local": {"object": "obj.vlan.local", "class_ref": "class.network.vlan"},
        "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7502" for d in result.diagnostics)


def test_reference_validator_accepts_valid_network_vlan_relation():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.vlan.local",
            "layer": "L2",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.vlan.local",
            "extensions": {},
        },
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"vlan_ref": "inst.vlan.local"}},
        },
    ]
    classes = {
        "class.network.vlan": {"class": "class.network.vlan"},
        "class.compute.workload.lxc": {"class": "class.compute.workload.lxc"},
    }
    objects = {
        "obj.vlan.local": {"object": "obj.vlan.local", "class_ref": "class.network.vlan"},
        "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E751") for d in result.diagnostics)


def test_reference_validator_rejects_unknown_network_vlan_target():
    registry = _registry()
    rows = [
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"vlan_ref": "inst.vlan.missing"}},
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={"class.compute.workload.lxc": {"class": "class.compute.workload.lxc"}},
        objects={"obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"}},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7511" for d in result.diagnostics)


def test_reference_validator_rejects_network_vlan_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.vlan.local",
            "layer": "L2",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.vlan.local",
            "extensions": {},
        },
        {
            "group": "services",
            "instance": "inst.service.local",
            "layer": "L5",
            "class_ref": "class.service.database",
            "object_ref": "obj.service.local",
            "extensions": {"network": {"vlan_ref": "inst.vlan.local"}},
        },
    ]
    classes = {
        "class.network.vlan": {"class": "class.network.vlan"},
        "class.service.database": {"class": "class.service.database"},
    }
    objects = {
        "obj.vlan.local": {"object": "obj.vlan.local", "class_ref": "class.network.vlan"},
        "obj.service.local": {"object": "obj.service.local", "class_ref": "class.service.database"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7513" for d in result.diagnostics)


def test_reference_validator_rejects_network_vlan_target_class_mismatch():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.bridge.local",
            "layer": "L2",
            "class_ref": "class.network.bridge",
            "object_ref": "obj.bridge.local",
            "extensions": {},
        },
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"vlan_ref": "inst.bridge.local"}},
        },
    ]
    classes = {
        "class.network.bridge": {"class": "class.network.bridge"},
        "class.compute.workload.lxc": {"class": "class.compute.workload.lxc"},
    }
    objects = {
        "obj.bridge.local": {"object": "obj.bridge.local", "class_ref": "class.network.bridge"},
        "obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"},
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7512" for d in result.diagnostics)


def test_reference_validator_rejects_network_vlan_ref_format():
    registry = _registry()
    rows = [
        {
            "group": "lxc",
            "instance": "inst.workload.local",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.workload.local",
            "extensions": {"network": {"vlan_ref": []}},
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={"class.compute.workload.lxc": {"class": "class.compute.workload.lxc"}},
        objects={"obj.workload.local": {"object": "obj.workload.local", "class_ref": "class.compute.workload.lxc"}},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7514" for d in result.diagnostics)


def test_reference_validator_accepts_valid_observability_target_relation():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "inst.device.local",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.device.local",
            "extensions": {},
        },
        {
            "group": "observability",
            "instance": "inst.obs.local",
            "layer": "L6",
            "class_ref": "class.observability.healthcheck",
            "object_ref": "obj.obs.local",
            "extensions": {"observability": {"target_ref": "inst.device.local"}},
        },
    ]
    classes = {
        "class.router": {"class": "class.router", "firmware_policy": "forbidden", "os_policy": "forbidden"},
        "class.observability.healthcheck": {"class": "class.observability.healthcheck"},
    }
    objects = {
        "obj.device.local": {"object": "obj.device.local", "class_ref": "class.router"},
        "obj.obs.local": {"object": "obj.obs.local", "class_ref": "class.observability.healthcheck"},
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E760") for d in result.diagnostics)


def test_reference_validator_rejects_observability_target_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "inst.device.local",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.device.local",
            "extensions": {},
        },
        {
            "group": "services",
            "instance": "inst.svc.local",
            "layer": "L5",
            "class_ref": "class.service.database",
            "object_ref": "obj.svc.local",
            "extensions": {"observability": {"target_ref": "inst.device.local"}},
        },
    ]
    classes = {
        "class.router": {"class": "class.router", "firmware_policy": "forbidden", "os_policy": "forbidden"},
        "class.service.database": {
            "class": "class.service.database",
            "firmware_policy": "forbidden",
            "os_policy": "forbidden",
        },
    }
    objects = {
        "obj.device.local": {"object": "obj.device.local", "class_ref": "class.router"},
        "obj.svc.local": {"object": "obj.svc.local", "class_ref": "class.service.database"},
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7603" for d in result.diagnostics)


def test_reference_validator_rejects_observability_target_invalid_layer():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.vlan.local",
            "layer": "L2",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.vlan.local",
            "extensions": {},
        },
        {
            "group": "observability",
            "instance": "inst.obs.local",
            "layer": "L6",
            "class_ref": "class.observability.healthcheck",
            "object_ref": "obj.obs.local",
            "extensions": {"observability": {"target_ref": "inst.vlan.local"}},
        },
    ]
    classes = {
        "class.network.vlan": {"class": "class.network.vlan"},
        "class.observability.healthcheck": {"class": "class.observability.healthcheck"},
    }
    objects = {
        "obj.vlan.local": {"object": "obj.vlan.local", "class_ref": "class.network.vlan"},
        "obj.obs.local": {"object": "obj.obs.local", "class_ref": "class.observability.healthcheck"},
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7602" for d in result.diagnostics)


def test_reference_validator_accepts_valid_operations_target_relation():
    registry = _registry()
    rows = [
        {
            "group": "observability",
            "instance": "inst.obs.local",
            "layer": "L6",
            "class_ref": "class.observability.healthcheck",
            "object_ref": "obj.obs.local",
            "extensions": {},
        },
        {
            "group": "operations",
            "instance": "inst.ops.local",
            "layer": "L7",
            "class_ref": "class.operations.backup",
            "object_ref": "obj.ops.local",
            "extensions": {"operations": {"target_ref": "inst.obs.local"}},
        },
    ]
    classes = {
        "class.observability.healthcheck": {"class": "class.observability.healthcheck"},
        "class.operations.backup": {"class": "class.operations.backup"},
    }
    objects = {
        "obj.obs.local": {"object": "obj.obs.local", "class_ref": "class.observability.healthcheck"},
        "obj.ops.local": {"object": "obj.ops.local", "class_ref": "class.operations.backup"},
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E770") for d in result.diagnostics)


def test_reference_validator_rejects_operations_target_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "inst.device.local",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.device.local",
            "extensions": {},
        },
        {
            "group": "observability",
            "instance": "inst.obs.local",
            "layer": "L6",
            "class_ref": "class.observability.healthcheck",
            "object_ref": "obj.obs.local",
            "extensions": {"operations": {"target_ref": "inst.device.local"}},
        },
    ]
    classes = {
        "class.router": {"class": "class.router", "firmware_policy": "forbidden", "os_policy": "forbidden"},
        "class.observability.healthcheck": {"class": "class.observability.healthcheck"},
    }
    objects = {
        "obj.device.local": {"object": "obj.device.local", "class_ref": "class.router"},
        "obj.obs.local": {"object": "obj.obs.local", "class_ref": "class.observability.healthcheck"},
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7703" for d in result.diagnostics)


def test_reference_validator_rejects_operations_target_invalid_layer():
    registry = _registry()
    rows = [
        {
            "group": "network",
            "instance": "inst.vlan.local",
            "layer": "L2",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.vlan.local",
            "extensions": {},
        },
        {
            "group": "operations",
            "instance": "inst.ops.local",
            "layer": "L7",
            "class_ref": "class.operations.backup",
            "object_ref": "obj.ops.local",
            "extensions": {"operations": {"target_ref": "inst.vlan.local"}},
        },
    ]
    classes = {
        "class.network.vlan": {"class": "class.network.vlan"},
        "class.operations.backup": {"class": "class.operations.backup"},
    }
    objects = {
        "obj.vlan.local": {"object": "obj.vlan.local", "class_ref": "class.network.vlan"},
        "obj.ops.local": {"object": "obj.ops.local", "class_ref": "class.operations.backup"},
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes=classes,
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7702" for d in result.diagnostics)


def test_reference_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
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
                "id": "base.compiler.capability_contract_loader",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/capability_contract_loader_compiler.py').as_posix()}:CapabilityContractLoaderCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "init",
                "order": 45,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/reference_validator.py').as_posix()}:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "depends_on": ["base.compiler.instance_rows", "base.compiler.capability_contract_loader"],
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True},
                    {"from_plugin": "base.compiler.capability_contract_loader", "key": "catalog_ids", "required": True},
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
        config={"validation_owner_references": "plugin"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)
