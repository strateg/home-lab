#!/usr/bin/env python3
"""Integration tests for Docker refs validator plugin (ADR 0087 Phase 1)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.docker_refs"


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
    """Base rows with L1 device and L4 Docker."""
    return [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "extensions": {"capabilities": ["cap.compute.runtime.container_host"]},
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "image": "nginx:latest",
            },
        },
    ]


def test_docker_refs_validator_accepts_valid_refs():
    """Test validator accepts valid Docker container with host_ref."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_rejects_missing_host_ref():
    """Test validator rejects Docker container without host_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {"image": "nginx:latest"},
            # No host_ref!
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7891" for diag in result.diagnostics)


def test_docker_refs_validator_rejects_unknown_host_ref():
    """Test validator rejects Docker container with unknown host_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-missing",  # Unknown host
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7891" for diag in result.diagnostics)


def test_docker_refs_validator_rejects_wrong_host_layer():
    """Test validator rejects Docker container with L2/L3 host."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "network", "instance": "vlan-a", "class_ref": "class.network.vlan", "layer": "L2"},
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "vlan-a",  # L2 is not valid host
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7891" for diag in result.diagnostics)


def test_docker_refs_validator_accepts_lxc_host_with_nesting():
    """Test validator accepts L4 LXC host with nesting feature."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "features": {"nesting": True},
                "capabilities": ["cap.compute.runtime.container_host"],
            },
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "lxc-docker",
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_warns_lxc_host_without_nesting():
    """Test validator warns when L4 LXC host lacks nesting feature."""
    registry = _registry()
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor.proxmox", "layer": "L1"},
        {
            "group": "lxc",
            "instance": "lxc-docker",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "features": {"nesting": False},  # Nesting disabled
                "capabilities": ["cap.compute.runtime.container_host"],
            },
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "lxc-docker",
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    # Should warn about nesting
    assert any(diag.code == "W7892" and "nesting" in diag.message for diag in result.diagnostics)


def test_docker_refs_validator_warns_host_lacks_capability():
    """Test validator warns when host lacks docker capability (migration period)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            # No docker capability!
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "srv-a",
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    # During migration period, this is WARNING not ERROR
    assert any(diag.code == "W7892" and "lacks docker capability" in diag.message for diag in result.diagnostics)


def test_docker_refs_validator_rejects_empty_image():
    """Test validator rejects Docker container with empty image."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["image"] = ""  # Empty image
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7893" for diag in result.diagnostics)


def test_docker_refs_validator_accepts_structured_image():
    """Test validator accepts Docker container with structured image reference."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["image"] = {
        "repository": "nginx",
        "tag": "latest",
        "registry": "docker.io",
    }
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_rejects_structured_image_missing_repository():
    """Test validator rejects structured image without repository."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["image"] = {
        "tag": "latest",
        # No repository!
    }
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7893" for diag in result.diagnostics)


def test_docker_refs_validator_rejects_unknown_network_ref():
    """Test validator rejects Docker container with unknown network_ref."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["networks"] = [{"network_ref": "vlan-missing"}]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7894" for diag in result.diagnostics)


def test_docker_refs_validator_accepts_valid_network_ref():
    """Test validator accepts Docker container with valid network_ref."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows.insert(1, {"group": "network", "instance": "vlan-a", "class_ref": "class.network.vlan", "layer": "L2"})
    rows[2]["extensions"]["networks"] = [{"network_ref": "vlan-a"}]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_rejects_unknown_volume_ref():
    """Test validator rejects Docker container with unknown volume_ref."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["storage"] = {"volumes": [{"volume_ref": "vol-missing"}]}
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7895" for diag in result.diagnostics)


def test_docker_refs_validator_accepts_valid_volume_ref():
    """Test validator accepts Docker container with valid volume_ref."""
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows.insert(1, {"group": "storage", "instance": "vol-a", "class_ref": "class.storage.volume", "layer": "L3"})
    rows[2]["extensions"]["storage"] = {"volumes": [{"volume_ref": "vol-a"}]}
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_requires_compiler_rows():
    """Test validator requires normalized rows from compiler."""
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7890" for diag in result.diagnostics)


def test_docker_refs_validator_accepts_top_level_host_ref():
    """Test validator accepts host_ref at top level (not in extensions)."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "capabilities": ["cap.compute.runtime.container_host"],
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "host_ref": "srv-a",  # Top-level host_ref
            "image": "nginx:latest",
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_accepts_device_ref_alias():
    """Test validator accepts device_ref as alias for host_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "extensions": {"capabilities": ["cap.compute.runtime.container_host"]},
        },
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "device_ref": "srv-a",  # device_ref alias
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_docker_refs_validator_rejects_l4_non_lxc_host():
    """Test validator rejects L4 host that is not LXC."""
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
        {
            "group": "docker",
            "instance": "docker-a",
            "class_ref": "class.compute.workload.docker",
            "layer": "L4",
            "extensions": {
                "host_ref": "vm-a",  # L4 VM is not valid Docker host
                "image": "nginx:latest",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7891" and "lxc" in diag.message.lower() for diag in result.diagnostics)
