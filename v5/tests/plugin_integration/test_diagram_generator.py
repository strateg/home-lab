#!/usr/bin/env python3
"""Integration checks for Mermaid diagram generator plugin."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage


def _load_generator_class():
    module_path = V5_ROOT / "topology-tools" / "plugins" / "generators" / "diagram_generator.py"
    spec = importlib.util.spec_from_file_location("test_diagram_generator_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DiagramGenerator


DiagramGenerator = _load_generator_class()


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "mermaid_icon_mode": "none",
        },
    )


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-slate",
                    "class_ref": "class.network.router",
                    "object_ref": "obj.glinet.slate_ax1800",
                    "layer": "L1",
                    "status": "mapped",
                },
                {
                    "instance_id": "srv-gamayun",
                    "class_ref": "class.compute.hypervisor",
                    "object_ref": "obj.proxmox.ve",
                    "layer": "L1",
                    "status": "mapped",
                },
            ],
            "network": [
                {
                    "instance_id": "inst.trust_zone.servers",
                    "class_ref": "class.network.trust_zone",
                    "object_ref": "obj.network.trust_zone.servers",
                    "status": "mapped",
                },
                {
                    "instance_id": "inst.vlan.servers",
                    "class_ref": "class.network.vlan",
                    "object_ref": "obj.network.vlan.servers",
                    "status": "mapped",
                    "instance_data": {
                        "vlan_id": 30,
                        "cidr": "10.0.30.0/24",
                        "gateway": "10.0.30.1",
                        "trust_zone_ref": "inst.trust_zone.servers",
                    },
                },
                {
                    "instance_id": "inst.data_link.rtr_to_hv",
                    "class_ref": "class.network.data_link",
                    "object_ref": "obj.network.ethernet_link",
                    "status": "mapped",
                    "instance_data": {
                        "endpoint_a": {"device_ref": "rtr-slate"},
                        "endpoint_b": {"device_ref": "srv-gamayun"},
                        "medium": "ethernet",
                        "speed_mbps": 1000,
                    },
                },
            ],
            "services": [
                {
                    "instance_id": "svc-prometheus",
                    "class_ref": "class.service.monitoring",
                    "object_ref": "obj.service.prometheus",
                    "status": "mapped",
                    "runtime": {"type": "container", "target_ref": "lxc-prometheus"},
                }
            ],
            "lxc": [
                {
                    "instance_id": "lxc-prometheus",
                    "class_ref": "class.compute.workload.container",
                    "object_ref": "obj.proxmox.lxc.debian12.prometheus",
                    "status": "mapped",
                    "instance_data": {
                        "hostname": "prometheus",
                        "host_ref": "srv-gamayun",
                        "trust_zone_ref": "inst.trust_zone.servers",
                    },
                }
            ],
            "vms": [],
        }
    }


def test_diagram_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = DiagramGenerator("base.generator.diagrams")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "docs" / "diagrams"
    expected_files = {
        "physical-topology.md",
        "network-topology.md",
        "icon-legend.md",
        "index.md",
        "_generated_files.txt",
    }
    assert expected_files.issubset({path.name for path in target_dir.iterdir()})

    physical = (target_dir / "physical-topology.md").read_text(encoding="utf-8")
    assert "rtr-slate" in physical
    assert "srv-gamayun" in physical


def test_diagram_generator_supports_icon_mode_override_via_env(tmp_path: Path) -> None:
    generator = DiagramGenerator("base.generator.diagrams")
    ctx = _ctx(tmp_path, _compiled_fixture())

    prev = os.environ.get("V5_DIAGRAM_ICON_MODE")
    os.environ["V5_DIAGRAM_ICON_MODE"] = "icon-nodes"
    try:
        result = generator.execute(ctx, Stage.GENERATE)
    finally:
        if prev is None:
            os.environ.pop("V5_DIAGRAM_ICON_MODE", None)
        else:
            os.environ["V5_DIAGRAM_ICON_MODE"] = prev

    assert result.status == PluginStatus.SUCCESS
    network = (tmp_path / "generated" / "docs" / "diagrams" / "network-topology.md").read_text(encoding="utf-8")
    assert "@{ icon:" in network
