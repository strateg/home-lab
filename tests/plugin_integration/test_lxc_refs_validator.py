#!/usr/bin/env python3
"""Integration tests for LXC refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.lxc_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(*, objects: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def _base_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "network", "instance": "tz-a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {"group": "network", "instance": "vlan-a", "class_ref": "class.network.vlan", "layer": "L2"},
        {"group": "os", "instance": "os-a", "class_ref": "class.os", "layer": "L1"},
        {"group": "storage", "instance": "endpoint-a", "class_ref": "class.storage.storage_endpoint", "layer": "L3"},
        {"group": "storage", "instance": "asset-a", "class_ref": "class.storage.data_asset", "layer": "L3"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.container",
            "layer": "L4",
            "extensions": {
                "device_ref": "srv-a",
                "trust_zone_ref": "tz-a",
                "host_os_ref": "os-a",
                "networks": [{"network_ref": "vlan-a"}],
                "storage": {
                    "rootfs": {"storage_endpoint_ref": "endpoint-a", "data_asset_ref": "asset-a"},
                    "volumes": [{"storage_endpoint_ref": "endpoint-a", "data_asset_ref": "asset-a"}],
                },
            },
        },
    ]


def test_lxc_refs_validator_accepts_valid_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_lxc_refs_validator_rejects_unknown_network_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["networks"] = [{"network_ref": "vlan-missing"}]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7885" for diag in result.diagnostics)


def test_lxc_refs_validator_rejects_unknown_data_asset_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["storage"]["rootfs"]["data_asset_ref"] = "asset-missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7887" for diag in result.diagnostics)


def test_lxc_refs_validator_rejects_host_os_ref_outside_device_os_bindings():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["os-b"]  # type: ignore[index]
    rows.insert(4, {"group": "os", "instance": "os-b", "class_ref": "class.os", "layer": "L1", "status": "active"})
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7883" for diag in result.diagnostics)


def test_lxc_refs_validator_requires_host_os_ref_when_multiple_active_device_os_bindings():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["os-a", "os-b"]  # type: ignore[index]
    rows.insert(4, {"group": "os", "instance": "os-b", "class_ref": "class.os", "layer": "L1", "status": "active"})
    rows[-1]["extensions"].pop("host_os_ref")  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7883" for diag in result.diagnostics)


def test_lxc_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7880" for diag in result.diagnostics)


def test_lxc_refs_validator_rejects_rootfs_storage_endpoint_with_non_proxmox_platform():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[4]["extensions"] = {"platform": "nfs"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7886" for diag in result.diagnostics)


def test_lxc_refs_validator_rejects_rootfs_storage_endpoint_with_non_proxmox_top_level_platform():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[4]["platform"] = "nfs"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7886" for diag in result.diagnostics)


def test_lxc_refs_validator_rejects_resolved_host_os_without_lxc_capability():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["os-a"]  # type: ignore[index]
    rows[3]["status"] = "active"  # type: ignore[index]
    rows[3]["extensions"] = {"capabilities": ["docker"]}  # type: ignore[index]
    rows[-1]["extensions"].pop("host_os_ref")  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7888" for diag in result.diagnostics)


def test_lxc_refs_validator_rejects_resolved_host_os_without_top_level_lxc_capability():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["os-a"]  # type: ignore[index]
    rows[3]["status"] = "active"  # type: ignore[index]
    rows[3]["capabilities"] = ["docker"]  # type: ignore[index]
    rows[-1]["extensions"].pop("host_os_ref")  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7888" for diag in result.diagnostics)


def test_lxc_refs_validator_warns_on_guest_template_architecture_mismatch():
    registry = _registry()
    ctx = _context(objects={"obj.lxc.template.arm64": {"properties": {"architecture": "arm64"}}})
    rows = _base_rows()
    rows.append(
        {
            "group": "templates",
            "instance": "tmpl-arm64",
            "class_ref": "class.compute.workload.container",
            "layer": "L4",
            "object_ref": "obj.lxc.template.arm64",
        }
    )
    rows[-2]["extensions"]["template_ref"] = "tmpl-arm64"  # type: ignore[index]
    rows[-2]["extensions"]["os"] = {"architecture": "x86_64"}  # type: ignore[index]
    rows[-2]["extensions"].pop("host_os_ref")  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7888" for diag in result.diagnostics)


def test_lxc_refs_validator_keeps_deprecation_warnings_without_storage_section():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"] = {  # type: ignore[index]
        "device_ref": "srv-a",
        "trust_zone_ref": "tz-a",
        "host_os_ref": "os-a",
        "type": "legacy",
        "role": "legacy",
        "resources": {"cpu": 1},
        "ansible": {"vars": {"postgresql_version": "16"}},
    }
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    warning_codes = [diag.code for diag in result.diagnostics if diag.severity == "warning"]
    assert warning_codes.count("W7888") >= 4


def test_lxc_refs_validator_keeps_top_level_deprecation_warnings_without_storage_section():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1].pop("extensions")  # type: ignore[index]
    rows[-1]["device_ref"] = "srv-a"  # type: ignore[index]
    rows[-1]["trust_zone_ref"] = "tz-a"  # type: ignore[index]
    rows[-1]["host_os_ref"] = "os-a"  # type: ignore[index]
    rows[-1]["type"] = "legacy"  # type: ignore[index]
    rows[-1]["role"] = "legacy"  # type: ignore[index]
    rows[-1]["resources"] = {"cpu": 1}  # type: ignore[index]
    rows[-1]["ansible"] = {"vars": {"postgresql_version": "16"}}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    warning_codes = [diag.code for diag in result.diagnostics if diag.severity == "warning"]
    assert warning_codes.count("W7888") >= 4
