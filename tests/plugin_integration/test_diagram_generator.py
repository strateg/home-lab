#!/usr/bin/env python3
"""Integration checks for Mermaid diagram generator plugin."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from kernel.plugin_base import PluginContext, PluginStatus, Stage


def _load_generator_class():
    module_path = TOOLS_ROOT / "plugins" / "generators" / "diagram_generator.py"
    spec = importlib.util.spec_from_file_location("test_diagram_generator_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DiagramGenerator


DiagramGenerator = _load_generator_class()


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
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


def test_diagram_generator_emits_icon_cache_manifest_in_icon_node_mode(tmp_path: Path) -> None:
    icon_pack = {
        "prefix": "mdi",
        "width": 24,
        "height": 24,
        "icons": {
            "router-network": {"body": "<path d='M1 1h22v22H1z'/>"},
            "shield-half-full": {"body": "<path d='M2 2h20v20H2z'/>"},
            "lan": {"body": "<path d='M3 3h18v18H3z'/>"},
            "bridge": {"body": "<path d='M4 4h16v16H4z'/>"},
            "cube-outline": {"body": "<path d='M5 5h14v14H5z'/>"},
            "chart-line": {"body": "<path d='M6 6h12v12H6z'/>"},
        },
    }
    pack_dir = tmp_path / "workspace" / "node_modules" / "@iconify-json" / "mdi"
    pack_dir.mkdir(parents=True)
    (pack_dir / "icons.json").write_text(json.dumps(icon_pack), encoding="utf-8")

    generator = DiagramGenerator("base.generator.diagrams")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_compiled_fixture(),
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "mermaid_icon_mode": "icon-nodes",
            "icon_pack_search_roots": [str(tmp_path / "workspace")],
        },
    )

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    cache_root = tmp_path / "generated" / "docs" / "diagrams" / "icons"
    manifest_path = cache_root / "icon-cache.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["icons_total"] > 0
    assert manifest["icons_resolved"] > 0
    assert "mdi" in manifest["packs_loaded"]


def test_diagram_generator_uses_embedded_fallback_icons_when_packs_missing(tmp_path: Path) -> None:
    generator = DiagramGenerator("base.generator.diagrams")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_compiled_fixture(),
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "mermaid_icon_mode": "icon-nodes",
            "icon_pack_search_roots": [str(tmp_path / "workspace-without-packs")],
        },
    )

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    cache_root = tmp_path / "generated" / "docs" / "diagrams" / "icons"
    manifest = json.loads((cache_root / "icon-cache.json").read_text(encoding="utf-8"))
    assert manifest["icons_total"] > 0
    assert manifest["icons_resolved_via_fallback"] > 0
    assert manifest["icons_unresolved"] == 0
