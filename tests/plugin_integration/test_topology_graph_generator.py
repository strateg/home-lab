#!/usr/bin/env python3
"""Integration checks for unified topology graph generator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginRegistry
from kernel.plugin_base import PluginContext, PluginStatus, Stage

PLUGIN_ID = "base.generator.topology_graph"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _semanticize(compiled_json: dict) -> dict:
    payload = copy.deepcopy(compiled_json)
    instances = payload.get("instances")
    if not isinstance(instances, dict):
        return payload
    for rows in instances.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            object_ref = row.pop("object_ref", None)
            class_ref = row.pop("class_ref", None)
            if not isinstance(object_ref, str) and not isinstance(class_ref, str):
                continue
            instance_block = row.get("instance")
            if not isinstance(instance_block, dict):
                instance_block = {}
                row["instance"] = instance_block
            if isinstance(object_ref, str) and object_ref:
                instance_block.setdefault("materializes_object", object_ref)
            if isinstance(class_ref, str) and class_ref:
                instance_block.setdefault("materializes_class", class_ref)
    return payload


def _compiled_fixture() -> dict:
    return _semanticize(
        {
            "instances": {
                "devices": [
                    {
                        "instance_id": "srv-pve",
                        "object_ref": "obj.proxmox.ve",
                        "class_ref": "class.compute.hypervisor",
                        "layer": "L1",
                    }
                ],
                "lxc": [
                    {
                        "instance_id": "lxc-grafana",
                        "object_ref": "obj.proxmox.lxc.debian12.base",
                        "class_ref": "class.compute.workload.container",
                        "layer": "L1",
                        "instance_data": {"host_ref": "srv-pve"},
                    }
                ],
                "services": [
                    {
                        "instance_id": "svc-grafana",
                        "object_ref": "obj.service.grafana",
                        "class_ref": "class.service.visualization",
                        "layer": "L4",
                        "runtime": {"target_ref": "lxc-grafana"},
                        "instance_data": {"dependencies": [{"service_ref": "svc-prometheus"}]},
                    },
                    {
                        "instance_id": "svc-prometheus",
                        "object_ref": "obj.service.prometheus",
                        "class_ref": "class.service.monitoring",
                        "layer": "L4",
                        "runtime": {"target_ref": "lxc-grafana"},
                    },
                ],
                "network": [
                    {
                        "instance_id": "inst.trust_zone.servers",
                        "object_ref": "obj.network.trust_zone.servers",
                        "class_ref": "class.network.trust_zone",
                    },
                    {
                        "instance_id": "inst.vlan.servers",
                        "object_ref": "obj.network.vlan.servers",
                        "class_ref": "class.network.vlan",
                        "instance_data": {
                            "managed_by_ref": "srv-pve",
                            "trust_zone_ref": "inst.trust_zone.servers",
                        },
                    },
                    {
                        "instance_id": "inst.data_link.wan",
                        "object_ref": "obj.network.data_link.wan",
                        "class_ref": "class.network.data_link",
                        "instance_data": {
                            "endpoint_a": {"device_ref": "srv-pve"},
                            "endpoint_b": {"external_ref": "external.internet"},
                        },
                    },
                ],
                "pools": [
                    {
                        "instance_id": "inst.pool.fast",
                        "object_ref": "obj.storage.pool.fast",
                        "class_ref": "class.storage.pool.zfs",
                        "instance_data": {"host_ref": "srv-pve"},
                    }
                ],
                "data-assets": [
                    {
                        "instance_id": "inst.data.asset.monitoring",
                        "object_ref": "obj.storage.data_asset.monitoring",
                        "class_ref": "class.storage.data_asset",
                        "instance_data": {"host_ref": "srv-pve"},
                    }
                ],
                "operations": [
                    {
                        "instance_id": "inst.backup.monitoring",
                        "object_ref": "obj.ops.backup",
                        "class_ref": "class.ops.backup_policy",
                        "instance_data": {
                            "target_ref": "svc-grafana",
                            "data_asset_ref": "inst.data.asset.monitoring",
                            "storage_ref": "inst.pool.fast",
                        },
                    }
                ],
                "observability": [],
                "power": [],
                "qos": [],
                "firewall": [],
            }
        }
    )


def _context(tmp_path: Path, config: dict | None = None) -> PluginContext:
    payload = {
        "generator_artifacts_root": str(tmp_path / "generated"),
    }
    if isinstance(config, dict):
        payload.update(config)
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_compiled_fixture(),
        output_dir=str(tmp_path / "build"),
        config=payload,
    )


def test_topology_graph_generator_writes_unified_diagram(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(tmp_path)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    output_path = tmp_path / "generated" / "docs" / "diagrams" / "unified-topology.md"
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Unified Topology Graph" in content
    assert "svc_grafana -->|runtime_target| lxc_grafana" in content
    assert "svc_grafana -->|service_dependency| svc_prometheus" in content
    assert "inst_backup_monitoring -->|writes_to_storage| inst_pool_fast" in content
    assert "external_internet" in content


def test_topology_graph_generator_honors_domain_and_layer_filters(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(
        tmp_path,
        {
            "domain_filter": ["services"],
            "layer_filter": ["L4"],
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    output_path = tmp_path / "generated" / "docs" / "diagrams" / "unified-topology.md"
    content = output_path.read_text(encoding="utf-8")
    assert "Domains: services" in content
    assert "Layers: L4" in content
    assert "Edge Types: all" in content
    assert "svc_grafana" in content
    assert "svc_prometheus" in content
    assert "srv_pve" not in content
    assert "service_dependency" not in content


def test_topology_graph_generator_honors_edge_type_filter(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(
        tmp_path,
        {
            "edge_type_filter": ["runtime_target"],
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    output_path = tmp_path / "generated" / "docs" / "diagrams" / "unified-topology.md"
    content = output_path.read_text(encoding="utf-8")
    assert "Edge Types: runtime_target" in content
    assert "runtime_target" in content
    assert "service_dependency" not in content
    assert "writes_to_storage" not in content
