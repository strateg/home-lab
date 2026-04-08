#!/usr/bin/env python3
"""Integration tests for VM hypervisor compatibility validator (ADR 0087 Phase 3)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.vm_hypervisor_compat"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


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
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def _base_rows() -> list[dict]:
    """Base rows with L1 Proxmox hypervisor and L4 VM."""
    return [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
        },
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "disks": [
                    {
                        "disk_id": "boot0",
                        "role": "boot",
                        "format": "qcow2",
                        "bus": "scsi",
                        "slot": "0",
                    },
                ],
            },
        },
    ]


def test_vm_hypervisor_compat_accepts_valid_vm():
    """Test validator accepts VM with valid disk format/bus for Proxmox."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_vm_hypervisor_compat_rejects_invalid_format():
    """Test validator rejects VM with disk format not allowed by hypervisor (AC-13)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"][0]["format"] = "vhdx"  # Not allowed on Proxmox
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7903" for diag in result.diagnostics)


def test_vm_hypervisor_compat_rejects_invalid_bus():
    """Test validator rejects VM with disk bus not allowed by hypervisor (AC-14)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"][0]["bus"] = "xvd"  # Xen-only bus
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7904" for diag in result.diagnostics)


def test_vm_hypervisor_compat_rejects_duplicate_disk_id():
    """Test validator rejects VM with duplicate disk_id (AC-15)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"].append(
        {
            "disk_id": "boot0",  # Duplicate!
            "role": "data",
            "format": "qcow2",
            "bus": "scsi",
            "slot": "1",
        }
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7901" for diag in result.diagnostics)


def test_vm_hypervisor_compat_rejects_duplicate_bus_slot():
    """Test validator rejects VM with duplicate bus:slot (AC-16)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"].append(
        {
            "disk_id": "data0",
            "role": "data",
            "format": "qcow2",
            "bus": "scsi",
            "slot": "0",  # Duplicate bus:slot!
        }
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7902" for diag in result.diagnostics)


def test_vm_hypervisor_compat_warns_no_boot_disk():
    """Test validator warns when VM has no boot disk (AC-17)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"][0]["role"] = "data"  # No boot disk
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    # Should warn about no boot disk
    assert any(diag.code == "W7905" for diag in result.diagnostics)


def test_vm_hypervisor_compat_rejects_multiple_boot_disks():
    """Test validator rejects VM with multiple boot disks (AC-17)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"].append(
        {
            "disk_id": "boot1",
            "role": "boot",  # Second boot disk!
            "format": "qcow2",
            "bus": "scsi",
            "slot": "1",
        }
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7905" for diag in result.diagnostics)


def test_vm_hypervisor_compat_rejects_invalid_boot_order():
    """Test validator rejects boot_order referencing unknown disk_id (AC-18)."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["boot_order"] = ["boot0", "nonexistent"]  # Unknown disk_id
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7906" for diag in result.diagnostics)


def test_vm_hypervisor_compat_accepts_valid_boot_order():
    """Test validator accepts boot_order with valid disk_id references."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["disks"].append(
        {
            "disk_id": "data0",
            "role": "data",
            "format": "qcow2",
            "bus": "scsi",
            "slot": "1",
        }
    )
    rows[1]["extensions"]["boot_order"] = ["boot0", "data0"]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_vm_hypervisor_compat_validates_vbox_formats():
    """Test validator uses VirtualBox allowed formats."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
        },
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-vbox",
                "disks": [
                    {
                        "disk_id": "boot0",
                        "role": "boot",
                        "format": "vdi",  # VBox native format
                        "bus": "sata",
                        "slot": "0",
                    },
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_vm_hypervisor_compat_rejects_vbox_qcow2():
    """Test validator rejects qcow2 on VirtualBox."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
        },
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-vbox",
                "disks": [
                    {
                        "disk_id": "boot0",
                        "role": "boot",
                        "format": "qcow2",  # Not supported on VBox
                        "bus": "sata",
                        "slot": "0",
                    },
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7903" for diag in result.diagnostics)


def test_vm_hypervisor_compat_validates_hyperv_formats():
    """Test validator uses Hyper-V allowed formats."""
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
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-hyperv",
                "disks": [
                    {
                        "disk_id": "boot0",
                        "role": "boot",
                        "format": "vhdx",  # Hyper-V native format
                        "bus": "scsi",
                        "slot": "0",
                    },
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_vm_hypervisor_compat_rejects_hyperv_vmdk():
    """Test validator rejects vmdk on Hyper-V."""
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
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-hyperv",
                "disks": [
                    {
                        "disk_id": "boot0",
                        "role": "boot",
                        "format": "vmdk",  # Not supported on Hyper-V
                        "bus": "scsi",
                        "slot": "0",
                    },
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7903" for diag in result.diagnostics)


def test_vm_hypervisor_compat_requires_compiler_rows():
    """Test validator requires normalized rows from compiler."""
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7900" for diag in result.diagnostics)


def test_vm_hypervisor_compat_ignores_non_vm_classes():
    """Test validator ignores non-VM classes."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "srv-a"},
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_vm_hypervisor_compat_accepts_top_level_disks():
    """Test validator accepts disks at top level (not in extensions)."""
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
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "host_ref": "srv-a",  # Top-level
            "disks": [  # Top-level
                {
                    "disk_id": "boot0",
                    "role": "boot",
                    "format": "qcow2",
                    "bus": "scsi",
                    "slot": "0",
                },
            ],
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []
