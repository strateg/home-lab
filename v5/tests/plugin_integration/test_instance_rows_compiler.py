#!/usr/bin/env python3
"""Integration tests for instance rows compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage
from plugins.compilers import instance_rows_compiler as instance_rows_module

PLUGIN_ID = "base.compiler.instance_rows"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_instance_rows_compiler_skips_when_core_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "core"},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data == {"normalized_rows": []}


def test_instance_rows_compiler_plugin_owner_normalizes_rows():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "dev-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "custom_flag": True,
                        "endpoint_a": {"device_ref": "a", "port": "eth0"},
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows")
    assert isinstance(rows, list)
    assert rows and rows[0]["instance"] == "dev-1"
    assert rows[0]["extensions"]["custom_flag"] is True
    assert rows[0]["extensions"]["endpoint_a"]["port"] == "eth0"
    assert "normalized_rows" in ctx.get_published_keys(PLUGIN_ID)


def test_sidecar_merge_passthrough_preserves_placeholders():
    """In passthrough mode, placeholders are preserved unchanged."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "passthrough",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "test-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                            "mac_eth0": "AA:BB:CC:DD:EE:FF",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    rows = result.output_data.get("normalized_rows", [])
    assert rows and rows[0]["instance"] == "test-device"
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    # Placeholder should be preserved in passthrough mode
    assert hw_identity.get("serial_number") == "<TODO_SERIAL_NUMBER>"
    assert hw_identity.get("mac_eth0") == "AA:BB:CC:DD:EE:FF"


def test_sidecar_missing_inject_mode_no_error():
    """In inject mode without side-car file, placeholders remain (no error)."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "nonexistent-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    # No error in inject mode when side-car is missing
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    assert not result.has_errors


def test_sidecar_missing_strict_mode_with_placeholders_emits_error():
    """In strict mode without side-car file, unresolved placeholders emit error."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "strict",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "nonexistent-strict-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    # Strict mode should emit errors for unresolved placeholders
    error_codes = [d.code for d in result.diagnostics if d.severity == "error"]
    assert "E7210" in error_codes or "E7208" in error_codes


def test_placeholder_non_placeholders_preserved():
    """Non-placeholder values in hardware_identity should never be modified."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "preserve-test",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                            "mac_eth0": "AA:BB:CC:DD:EE:FF",  # NOT a placeholder
                            "location": "rack-1",  # NOT a placeholder
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    # Non-placeholder values must be preserved exactly
    assert hw_identity.get("mac_eth0") == "AA:BB:CC:DD:EE:FF"
    assert hw_identity.get("location") == "rack-1"


def test_sidecar_decrypt_failure_inject_require_unlock_emits_error(monkeypatch):
    """inject + require_unlock must fail hard when side-car decryption fails."""

    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(returncode=2, stderr="simulated decrypt failure")

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-mikrotik-chateau",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {"serial_number": "<TODO_SERIAL_NUMBER>"},
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    error_codes = [d.code for d in result.diagnostics if d.severity == "error"]
    assert "E7201" in error_codes
    assert result.has_errors


def test_sidecar_decrypt_failure_inject_require_unlock_false_is_warning(monkeypatch):
    """inject + require_unlock=false keeps warning behavior on decrypt failure."""

    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(returncode=2, stderr="simulated decrypt failure")

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "require_unlock": False,
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-mikrotik-chateau",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {"serial_number": "<TODO_SERIAL_NUMBER>"},
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    warning_codes = [d.code for d in result.diagnostics if d.severity == "warning"]
    assert "W7210" in warning_codes
    assert not result.has_errors


def test_sidecar_instance_mismatch_does_not_merge_in_inject(monkeypatch):
    """Side-car instance mismatch must never merge secrets into row."""

    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=(
                "instance: different-instance\n"
                "hardware_identity:\n"
                "  serial_number: SHOULD-NOT-BE-MERGED\n"
            ),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "require_unlock": False,
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-mikrotik-chateau",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {"serial_number": "<TODO_SERIAL_NUMBER>"},
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    assert hw_identity.get("serial_number") == "<TODO_SERIAL_NUMBER>"
    diag_codes = [d.code for d in result.diagnostics]
    assert "E7205" in diag_codes


def test_hardware_identity_secret_ref_is_forbidden():
    """Legacy indirection field must be rejected explicitly."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "legacy-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity_secret_ref": "secret.legacy.id",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.has_errors
    assert any(
        d.code == "E3201" and "hardware_identity_secret_ref" in d.message for d in result.diagnostics
    )
