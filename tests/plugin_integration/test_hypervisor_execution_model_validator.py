#!/usr/bin/env python3
"""Integration tests for hypervisor execution model validator plugin (ADR 0087 Phase 2)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.hypervisor_execution_model"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_hypervisor_execution_model_manifest_requires_normalized_rows() -> None:
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
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def _base_rows_bare_metal() -> list[dict]:
    """Base rows with L1 bare_metal hypervisor."""
    return [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "extensions": {},
        },
    ]


def _base_rows_hosted() -> list[dict]:
    """Base rows with L1 hosted hypervisor."""
    return [
        {
            "group": "os",
            "instance": "os-win10",
            "class_ref": "class.os.windows.10",
            "layer": "L1",
        },
        {
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
            "extensions": {
                "execution_model": "hosted",
                "host_os_ref": "os-win10",
            },
        },
    ]


def test_hypervisor_execution_model_accepts_bare_metal_at_l1():
    """Test validator accepts bare_metal hypervisor at L1 without hardware_ref."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows_bare_metal())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []
    # Should emit info about bare_metal at L1
    infos = [d for d in result.diagnostics if d.severity == "info"]
    assert any(d.code == "I7899" for d in infos)


def test_hypervisor_execution_model_accepts_hosted_with_host_os_ref():
    """Test validator accepts hosted hypervisor with valid host_os_ref."""
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows_hosted())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_hypervisor_execution_model_rejects_hosted_without_host_os_ref():
    """Test validator rejects hosted hypervisor without host_os_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
            "extensions": {
                "execution_model": "hosted",
                # Missing host_os_ref!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7899" and "host_os_ref" in diag.message for diag in result.diagnostics)


def test_hypervisor_execution_model_rejects_hosted_with_unknown_host_os_ref():
    """Test validator rejects hosted hypervisor with unknown host_os_ref."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
            "extensions": {
                "execution_model": "hosted",
                "host_os_ref": "os-missing",  # Unknown!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7899" and "does not reference" in diag.message for diag in result.diagnostics)


def test_hypervisor_execution_model_warns_hosted_with_non_os_host_os_ref():
    """Test validator warns when host_os_ref targets non-OS class."""
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
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
            "extensions": {
                "execution_model": "hosted",
                "host_os_ref": "vlan-a",  # Not an OS!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    # Should warn about non-OS target
    assert any(diag.code == "W7899" for diag in result.diagnostics)


def test_hypervisor_execution_model_rejects_invalid_execution_model():
    """Test validator rejects invalid execution_model value."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "extensions": {
                "execution_model": "invalid_model",  # Invalid!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7899" and "invalid execution_model" in diag.message for diag in result.diagnostics)


def test_hypervisor_execution_model_validates_hardware_ref_if_present():
    """Test validator validates hardware_ref if specified for bare_metal."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "extensions": {
                "hardware_ref": "hw-missing",  # Unknown!
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7899" and "hardware_ref" in diag.message for diag in result.diagnostics)


def test_hypervisor_execution_model_accepts_valid_hardware_ref():
    """Test validator accepts valid hardware_ref for bare_metal."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "hardware",
            "instance": "hw-chassis-a",
            "class_ref": "class.hardware.chassis",
            "layer": "L0",
        },
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            "extensions": {
                "hardware_ref": "hw-chassis-a",
            },
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_hypervisor_execution_model_derives_from_class_ref():
    """Test validator derives execution_model from class_ref when not specified."""
    registry = _registry()
    ctx = _context()
    # Proxmox defaults to bare_metal
    rows = [
        {
            "group": "devices",
            "instance": "srv-a",
            "class_ref": "class.compute.hypervisor.proxmox",
            "layer": "L1",
            # No execution_model specified, should default to bare_metal
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    # Should have info about bare_metal at L1
    infos = [d for d in result.diagnostics if d.severity == "info"]
    assert any(d.code == "I7899" and "bare_metal" in d.message for d in infos)


def test_hypervisor_execution_model_requires_compiler_rows():
    """Test validator requires normalized rows from compiler."""
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_hypervisor_execution_model_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/instance_rows_compiler.py').as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/hypervisor_execution_model_validator.py').as_posix()}:HypervisorExecutionModelValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 145,
                "depends_on": ["base.compiler.instance_rows"],
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


def test_hypervisor_execution_model_accepts_top_level_fields():
    """Test validator accepts execution_model and refs at top level."""
    registry = _registry()
    ctx = _context()
    rows = [
        {
            "group": "os",
            "instance": "os-win10",
            "class_ref": "class.os.windows.10",
            "layer": "L1",
        },
        {
            "group": "devices",
            "instance": "srv-vbox",
            "class_ref": "class.compute.hypervisor.vbox",
            "layer": "L1",
            "execution_model": "hosted",  # Top-level
            "host_os_ref": "os-win10",  # Top-level
        },
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == []


def test_hypervisor_execution_model_ignores_non_hypervisor_classes():
    """Test validator ignores non-hypervisor classes."""
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
    # No diagnostics for non-hypervisor class
    assert result.diagnostics == []
