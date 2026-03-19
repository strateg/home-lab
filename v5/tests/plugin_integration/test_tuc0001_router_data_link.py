#!/usr/bin/env python3
"""Integration checks for TUC-0001 router cable/channel modeling."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
V5_TOOLS = REPO_ROOT / "v5" / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

NETWORK_PLUGIN_ID = "object_network.validator_json.ethernet_cable_endpoints"
NETWORK_PLUGIN_MANIFEST = REPO_ROOT / "v5" / "topology" / "object-modules" / "network" / "plugins.yaml"


def _load_compiler_module():
    module_path = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module_tuc0001", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _registry_for_network_validator() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(NETWORK_PLUGIN_MANIFEST)
    return registry


def _base_bindings() -> dict[str, Any]:
    return {
        "instance_bindings": {
            "devices": [
                {
                    "instance": "rtr-mikrotik-chateau",
                    "class_ref": "class.router",
                    "object_ref": "obj.mikrotik.chateau_lte7_ax",
                },
                {
                    "instance": "rtr-slate",
                    "class_ref": "class.router",
                    "object_ref": "obj.glinet.slate_ax1800",
                },
                {
                    "instance": "inst.ethernet_cable.cat5e",
                    "class_ref": "class.network.physical_link",
                    "object_ref": "obj.network.ethernet_cable",
                    "endpoint_a": {"device_ref": "rtr-mikrotik-chateau", "port": "ether2"},
                    "endpoint_b": {"device_ref": "rtr-slate", "port": "lan1"},
                    "creates_channel_ref": "inst.chan.eth.chateau_to_slate",
                    "length_m": 3,
                    "shielding": "utp",
                },
            ],
            "network": [
                {
                    "instance": "inst.chan.eth.chateau_to_slate",
                    "class_ref": "class.network.data_link",
                    "object_ref": "obj.network.ethernet_channel",
                    "endpoint_a": {"device_ref": "rtr-mikrotik-chateau", "port": "ether2"},
                    "endpoint_b": {"device_ref": "rtr-slate", "port": "lan1"},
                    "link_ref": "inst.ethernet_cable.cat5e",
                }
            ],
        }
    }


def _base_objects() -> dict[str, Any]:
    return {
        "obj.mikrotik.chateau_lte7_ax": {
            "class_ref": "class.router",
            "hardware_specs": {"interfaces": {"ethernet": [{"name": "ether1"}, {"name": "ether2"}]}},
        },
        "obj.glinet.slate_ax1800": {
            "class_ref": "class.router",
            "hardware_specs": {"interfaces": {"ethernet": [{"name": "wan"}, {"name": "lan1"}]}},
        },
        "obj.network.ethernet_cable": {
            "class_ref": "class.network.physical_link",
        },
        "obj.network.ethernet_channel": {
            "class_ref": "class.network.data_link",
            "properties": {
                "protocol_family": "ieee_802_3",
                "backing_link_class": "class.network.physical_link",
            },
        },
    }


def _new_context() -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test-real",
        model_lock={},
        classes={},
        objects=copy.deepcopy(_base_objects()),
        instance_bindings=copy.deepcopy(_base_bindings()),
    )


def _find_row(bindings: dict[str, Any], *, instance_id: str) -> dict[str, Any]:
    groups = bindings["instance_bindings"]
    for rows in groups.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("instance") == instance_id:
                return row
    raise AssertionError(f"Instance not found: {instance_id}")


def _run_network_validator(modify: Callable[[PluginContext], None] | None = None):
    registry = _registry_for_network_validator()
    ctx = _new_context()
    if modify:
        modify(ctx)
    return registry.execute_plugin(NETWORK_PLUGIN_ID, ctx, Stage.VALIDATE)


def test_tuc0001_network_validator_accepts_valid_cable_and_channel():
    result = _run_network_validator()
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors


def test_tuc0001_network_validator_rejects_unknown_endpoint_instance():
    def _modify(ctx: PluginContext) -> None:
        cable = _find_row(ctx.instance_bindings, instance_id="inst.ethernet_cable.cat5e")
        cable["endpoint_a"]["device_ref"] = "rtr-unknown"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7304" for diag in result.diagnostics)


def test_tuc0001_network_validator_rejects_unknown_mikrotik_port():
    def _modify(ctx: PluginContext) -> None:
        cable = _find_row(ctx.instance_bindings, instance_id="inst.ethernet_cable.cat5e")
        cable["endpoint_a"]["port"] = "ether99"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7305" for diag in result.diagnostics)


def test_tuc0001_network_validator_rejects_unknown_glinet_port():
    def _modify(ctx: PluginContext) -> None:
        cable = _find_row(ctx.instance_bindings, instance_id="inst.ethernet_cable.cat5e")
        cable["endpoint_b"]["port"] = "lan99"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7305" for diag in result.diagnostics)


def test_tuc0001_network_validator_rejects_wrong_cable_class():
    def _modify(ctx: PluginContext) -> None:
        cable = _find_row(ctx.instance_bindings, instance_id="inst.ethernet_cable.cat5e")
        cable["class_ref"] = "class.network.data_link"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7304" for diag in result.diagnostics)


def test_tuc0001_network_validator_requires_created_channel_ref():
    def _modify(ctx: PluginContext) -> None:
        cable = _find_row(ctx.instance_bindings, instance_id="inst.ethernet_cable.cat5e")
        cable.pop("creates_channel_ref", None)

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7307" for diag in result.diagnostics)


def test_tuc0001_network_validator_rejects_channel_link_mismatch():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.eth.chateau_to_slate")
        channel["link_ref"] = "inst.ethernet_cable.other"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7308" for diag in result.diagnostics)


def test_tuc0001_network_validator_rejects_endpoint_pair_mismatch():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.eth.chateau_to_slate")
        channel["endpoint_b"]["port"] = "wan"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7308" for diag in result.diagnostics)


def test_tuc0001_compile_preserves_cable_instance_data(tmp_path: Path):
    mod = _load_compiler_module()
    out_dir = mod.REPO_ROOT / "v5-build" / "test-tuc0001" / tmp_path.name
    output_json = out_dir / "effective-topology.json"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=output_json,
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=True,
        fail_on_warning=False,
        require_new_model=False,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    l1_rows = payload.get("instances", {}).get("data-links", [])
    cable_row = next((row for row in l1_rows if row.get("source_id") == "inst.ethernet_cable.cat5e"), None)
    assert isinstance(cable_row, dict)
    assert cable_row.get("class_ref") == "class.network.physical_link"
    instance_data = cable_row.get("instance_data")
    assert isinstance(instance_data, dict)
    assert instance_data.get("length_m") == 3
    assert instance_data.get("shielding") == "utp"
    assert instance_data.get("category") == "cat5e"
    assert instance_data.get("endpoint_a", {}).get("port") == "ether2"
    assert instance_data.get("endpoint_b", {}).get("port") == "lan1"


def test_tuc0001_compile_preserves_power_source_bindings(tmp_path: Path):
    mod = _load_compiler_module()
    out_dir = mod.REPO_ROOT / "v5-build" / "test-tuc0001" / f"{tmp_path.name}-power"
    output_json = out_dir / "effective-topology.json"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=output_json,
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=True,
        fail_on_warning=False,
        require_new_model=False,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    l1_rows = payload.get("instances", {}).get("devices", [])
    by_source_id = {row.get("source_id"): row for row in l1_rows if isinstance(row, dict)}

    mikrotik = by_source_id.get("rtr-mikrotik-chateau")
    slate = by_source_id.get("rtr-slate")
    pdu = by_source_id.get("pdu-rack")
    assert isinstance(mikrotik, dict)
    assert isinstance(slate, dict)
    assert isinstance(pdu, dict)

    assert mikrotik.get("instance_data", {}).get("power", {}).get("source_ref") == "pdu-rack"
    assert mikrotik.get("instance_data", {}).get("power", {}).get("outlet_ref") == "outlet_01"
    assert slate.get("instance_data", {}).get("power", {}).get("source_ref") == "pdu-rack"
    assert slate.get("instance_data", {}).get("power", {}).get("outlet_ref") == "outlet_02"
    assert pdu.get("instance_data", {}).get("power", {}).get("source_ref") == "ups-main"
