#!/usr/bin/env python3
"""Integration tests for nested topology scope validator (ADR 0087 Phase 5)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.nested_topology_scope"


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


def _base_rows_with_scope() -> list[dict]:
    """Base rows with LXC declaring a scope and nested Docker."""
    return [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
        },
        {
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {
                    "scope_id": "lxc-docker",
                    "internal_networks": [
                        {"name": "docker-net", "driver": "bridge", "subnet": "172.18.0.0/16"},
                    ],
                },
            },
        },
        {
            "group": "docker",
            "instance": "docker-app",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "lxc-docker",
                "networks": [
                    {"network_ref": "scope.lxc-docker.docker-net"},
                ],
            },
        },
    ]


def test_nested_topology_scope_accepts_valid_scope():
    """Test validator accepts valid topology_scope declaration (AC-23)."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows_with_scope())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []
    # Should emit info about the scope
    infos = [d for d in result.diagnostics if d.severity == "info"]
    assert any(d.code == "I7920" and "lxc-docker" in d.message for d in infos)


def test_nested_topology_scope_rejects_duplicate_scope_id():
    """Test validator rejects duplicate scope_id."""
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
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {"scope_id": "duplicate"},
            },
        },
        {
            "group": "lxc",
            "instance": "lxc-b",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {"scope_id": "duplicate"},  # Duplicate!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7921" for diag in result.diagnostics)


def test_nested_topology_scope_validates_internal_network_names():
    """Test validator validates internal_networks have unique names."""
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
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {
                    "scope_id": "lxc-docker",
                    "internal_networks": [
                        {"name": "net-a", "driver": "bridge"},
                        {"name": "net-a", "driver": "bridge"},  # Duplicate name!
                    ],
                },
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7922" and "duplicate" in diag.message for diag in result.diagnostics)


def test_nested_topology_scope_requires_network_name():
    """Test validator requires name property in internal_networks."""
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
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {
                    "scope_id": "lxc-docker",
                    "internal_networks": [
                        {"driver": "bridge"},  # Missing name!
                    ],
                },
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7922" and "name" in diag.message for diag in result.diagnostics)


def test_nested_topology_scope_warns_unknown_driver():
    """Test validator warns on unknown network driver."""
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
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {
                    "scope_id": "lxc-docker",
                    "internal_networks": [
                        {"name": "net-a", "driver": "unknown_driver"},
                    ],
                },
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7922" for diag in result.diagnostics)


def test_nested_topology_scope_validates_scope_reference():
    """Test validator validates scope.* references (AC-24)."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows_with_scope())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_nested_topology_scope_rejects_unknown_scope_reference():
    """Test validator rejects references to unknown scope."""
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
            "group": "docker",
            "instance": "docker-app",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "networks": [
                    {"network_ref": "scope.unknown-scope.docker-net"},  # Unknown scope!
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7923" for diag in result.diagnostics)


def test_nested_topology_scope_rejects_malformed_scope_reference():
    """Test validator rejects malformed scope.* reference."""
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
            "group": "docker",
            "instance": "docker-app",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "networks": [
                    {"network_ref": "scope.invalid"},  # Malformed - missing resource name!
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7923" and "malformed" in diag.message for diag in result.diagnostics)


def test_nested_topology_scope_warns_cross_scope_reference():
    """Test validator warns when workload references scope it's not in."""
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
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "topology_scope": {
                    "scope_id": "lxc-docker",
                    "internal_networks": [{"name": "docker-net", "driver": "bridge"}],
                },
            },
        },
        {
            "group": "docker",
            "instance": "docker-orphan",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",  # NOT nested in lxc-docker!
                "networks": [
                    {"network_ref": "scope.lxc-docker.docker-net"},  # Cross-scope reference
                ],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    # Should warn about cross-scope reference
    assert any(diag.code == "W7923" for diag in result.diagnostics)


def test_nested_topology_scope_requires_compiler_rows():
    """Test validator requires normalized rows from compiler."""
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7920" for diag in result.diagnostics)


def test_nested_topology_scope_ignores_non_workload_classes():
    """Test validator ignores non-workload classes."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "network",
            "instance": "vlan-a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_nested_topology_scope_accepts_top_level_topology_scope():
    """Test validator accepts topology_scope at top level."""
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
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "host_ref": "srv-a",  # Top-level
            "topology_scope": {  # Top-level
                "scope_id": "lxc-docker",
                "internal_networks": [{"name": "docker-net", "driver": "bridge"}],
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []
