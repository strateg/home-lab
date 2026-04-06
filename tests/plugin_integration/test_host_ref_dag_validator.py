#!/usr/bin/env python3
"""Integration tests for host_ref DAG validator plugin (ADR 0087 AC-6)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.host_ref_dag"


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
    """Base rows with L1 device and L4 LXC."""
    return [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "srv-a"},
        },
    ]


def test_host_ref_dag_validator_accepts_valid_dag():
    """Test validator accepts valid DAG with depth 1."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_host_ref_dag_validator_accepts_depth_2():
    """Test validator accepts valid DAG with depth 2 (L1 -> L4 LXC -> L4 Docker)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "srv-a"},
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {"host_ref": "lxc-a"},
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_host_ref_dag_validator_rejects_cycle():
    """Test validator rejects cycle in host_ref graph."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "lxc-b"},  # Points to lxc-b
        },
        {
            "group": "lxc",
            "instance": "lxc-b",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "lxc-a"},  # Points back to lxc-a - cycle!
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7896" for diag in result.diagnostics)


def test_host_ref_dag_validator_rejects_self_reference():
    """Test validator rejects self-reference cycle."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "lxc-a"},  # Self-reference - cycle!
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7896" for diag in result.diagnostics)


def test_host_ref_dag_validator_rejects_depth_3():
    """Test validator rejects depth > 2 (L1 -> L4 -> L4 -> L4)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"host_ref": "srv-a"},  # Depth 1
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {"host_ref": "lxc-a"},  # Depth 2
        },
        {
            "group": "docker",
            "instance": "docker-b",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {"host_ref": "docker-a"},  # Depth 3 - exceeds limit!
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7897" for diag in result.diagnostics)


def test_host_ref_dag_validator_accepts_vm_workload():
    """Test validator accepts VM workload with host_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.workload.vm",
            "layer": "L4",
            "extensions": {"device_ref": "srv-a"},
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_host_ref_dag_validator_requires_compiler_rows():
    """Test validator requires normalized rows from compiler."""
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7890" for diag in result.diagnostics)


def test_host_ref_dag_validator_accepts_top_level_host_ref():
    """Test validator accepts host_ref at top level (not in extensions)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "host_ref": "srv-a",  # Top-level host_ref
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_host_ref_dag_validator_accepts_device_ref_alias():
    """Test validator accepts device_ref as alias for host_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"device_ref": "srv-a"},  # device_ref alias
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []
