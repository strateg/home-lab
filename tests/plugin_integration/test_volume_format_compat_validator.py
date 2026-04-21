#!/usr/bin/env python3
"""Integration tests for volume format compatibility validator (ADR 0087 Phase 4)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage
from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.volume_format_compat"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_volume_format_compat_validator_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _base_rows_with_pool() -> list[dict]:
    """Base rows with pool and volume."""
    return [
        {
            "group": "storage",
            "instance": "pool-dir",
            "class_ref": "class.storage.pool",
            "layer": "L3",
            "extensions": {"type": "dir"},
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "pool_ref": "pool-dir",
                "format": "qcow2",
            },
        },
    ]


def test_volume_format_compat_accepts_valid_pool_format():
    """Test validator accepts volume format compatible with pool type (AC-20)."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows_with_pool())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_volume_format_compat_rejects_qcow2_on_lvm():
    """Test validator rejects qcow2 format on LVM pool (AC-20)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "storage",
            "instance": "pool-lvm",
            "class_ref": "class.storage.pool",
            "layer": "L3",
            "extensions": {"type": "lvm"},
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "pool_ref": "pool-lvm",
                "format": "qcow2",  # Not allowed on LVM!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7911" for diag in result.diagnostics)


def test_volume_format_compat_accepts_raw_on_lvm():
    """Test validator accepts raw format on LVM pool."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "storage",
            "instance": "pool-lvm",
            "class_ref": "class.storage.pool",
            "layer": "L3",
            "extensions": {"type": "lvm"},
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "pool_ref": "pool-lvm",
                "format": "raw",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_volume_format_compat_accepts_subvol_on_zfs():
    """Test validator accepts subvol format on ZFS pool."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "storage",
            "instance": "pool-zfs",
            "class_ref": "class.storage.pool",
            "layer": "L3",
            "extensions": {"type": "zfspool"},
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "pool_ref": "pool-zfs",
                "format": "subvol",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_volume_format_compat_rejects_vmdk_on_zfs():
    """Test validator rejects vmdk format on ZFS pool."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "storage",
            "instance": "pool-zfs",
            "class_ref": "class.storage.pool",
            "layer": "L3",
            "extensions": {"type": "zfspool"},
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "pool_ref": "pool-zfs",
                "format": "vmdk",  # Not allowed on ZFS!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7911" for diag in result.diagnostics)


def test_volume_format_compat_validates_data_asset_ref():
    """Test validator validates data_asset_ref resolves to valid entity (AC-21)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "data-assets",
            "instance": "asset-a",
            "class_ref": "class.storage.data_asset",
            "layer": "L3",
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "format": "qcow2",
                "data_asset_ref": "asset-a",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_volume_format_compat_rejects_unknown_data_asset_ref():
    """Test validator rejects unknown data_asset_ref (AC-21)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "format": "qcow2",
                "data_asset_ref": "asset-missing",  # Unknown!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7912" for diag in result.diagnostics)


def test_volume_format_compat_warns_wrong_data_asset_class():
    """Test validator warns when data_asset_ref targets wrong class."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "network",
            "instance": "vlan-a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "format": "qcow2",
                "data_asset_ref": "vlan-a",  # Wrong class!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7912" for diag in result.diagnostics)


def test_volume_format_compat_validates_hypervisor_format():
    """Test validator validates volume format against hypervisor (AC-22)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
        },
        {
            "group": "volumes",
            "instance": "vol-boot",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {"format": "qcow2"},
        },
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "disks": [
                    {"disk_id": "boot0", "volume_ref": "vol-boot"},
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_volume_format_compat_rejects_vhdx_on_proxmox():
    """Test validator rejects vhdx format on Proxmox hypervisor (AC-22)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
        },
        {
            "group": "volumes",
            "instance": "vol-boot",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {"format": "vhdx"},  # Not allowed on Proxmox!
        },
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "disks": [
                    {"disk_id": "boot0", "volume_ref": "vol-boot"},
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7913" for diag in result.diagnostics)


def test_volume_format_compat_accepts_vhdx_on_hyperv():
    """Test validator accepts vhdx format on Hyper-V hypervisor."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-hyperv",
            "class_ref": "class.compute.hypervisor.hyperv",
            "layer": "L1",
        },
        {
            "group": "volumes",
            "instance": "vol-boot",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {"format": "vhdx"},
        },
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-hyperv",
                "disks": [
                    {"disk_id": "boot0", "volume_ref": "vol-boot"},
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_volume_format_compat_warns_unknown_pool_ref():
    """Test validator warns when pool_ref doesn't exist."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "extensions": {
                "pool_ref": "pool-missing",  # Unknown!
                "format": "qcow2",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7911" for diag in result.diagnostics)


def test_volume_format_compat_requires_compiler_rows():
    """Test validator requires normalized rows from compiler."""
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_volume_format_compat_ignores_volumes_without_format():
    """Test validator ignores volumes without format specified."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            # No format specified
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_volume_format_compat_accepts_top_level_properties():
    """Test validator accepts format/pool_ref at top level."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "storage",
            "instance": "pool-dir",
            "class_ref": "class.storage.pool",
            "layer": "L3",
            "type": "dir",  # Top-level
        },
        {
            "group": "volumes",
            "instance": "vol-a",
            "class_ref": "class.storage.volume",
            "layer": "L3",
            "pool_ref": "pool-dir",  # Top-level
            "format": "qcow2",  # Top-level
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []

def test_volume_format_compat_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    spec = _registry().specs[PLUGIN_ID]
    rel_entry, class_name = spec.entry.split(":", 1)
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / "plugins/compilers/instance_rows_compiler.py").as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": spec.kind.value,
                "entry": f"{(V5_TOOLS / "plugins" / rel_entry).as_posix()}:{class_name}",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": spec.phase.value,
                "order": spec.order,
                "depends_on": list(spec.depends_on),
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)
    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)

