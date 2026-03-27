#!/usr/bin/env python3
"""Integration checks for docs generator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.generator.docs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "srv-a",
                    "object_ref": "obj.proxmox.ve",
                    "class_ref": "class.compute.hypervisor",
                    "layer": "L1",
                    "status": "mapped",
                }
            ],
            "services": [
                {
                    "instance_id": "svc-a",
                    "object_ref": "obj.service.web",
                    "class_ref": "class.service.web_ui",
                    "status": "mapped",
                    "runtime": {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.servers"},
                }
            ],
            "lxc": [],
            "vms": [],
            "network": [],
        }
    }


def test_docs_generator_writes_expected_files(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(tmp_path, _compiled_fixture())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    docs_root = tmp_path / "generated" / "docs"
    assert (docs_root / "overview.md").exists()
    assert (docs_root / "devices.md").exists()
    assert (docs_root / "services.md").exists()
    assert (docs_root / "network-diagram.md").exists()
    assert (docs_root / "ip-allocation.md").exists()
    assert (docs_root / "dns-dhcp-overview.md").exists()
    assert (docs_root / "rack-layout.md").exists()
    assert (docs_root / "vlan-topology.md").exists()
    assert (docs_root / "trust-zones.md").exists()
    assert (docs_root / "trust-zone-firewall-policy.md").exists()
    assert (docs_root / "security-posture-matrix.md").exists()
    assert (docs_root / "service-dependencies.md").exists()
    assert (docs_root / "storage-topology.md").exists()
    assert (docs_root / "data-flow-topology.md").exists()
    assert (docs_root / "monitoring-topology.md").exists()
    assert (docs_root / "vpn-topology.md").exists()
    assert (docs_root / "qos-topology.md").exists()
    assert (docs_root / "ups-topology.md").exists()
    assert (docs_root / "backup-schedule.md").exists()
    assert (docs_root / "_generated_files.txt").exists()

    overview = (docs_root / "overview.md").read_text(encoding="utf-8")
    assert "| Devices | 1 |" in overview
    assert "| Services | 1 |" in overview
    services = (docs_root / "services.md").read_text(encoding="utf-8")
    assert "svc-a" in services
    assert "docker" in services
    network = (docs_root / "network-diagram.md").read_text(encoding="utf-8")
    assert "Network Inventory" in network


def test_docs_generator_reports_projection_error(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(tmp_path, {"instances": {"devices": [{}]}})

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9701" for diag in result.diagnostics)
