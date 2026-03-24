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
        topology_path="topology/topology.yaml",
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "passthrough",
            "secrets_root": "projects/home-lab/secrets",
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "nonexistent-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "@optional_secret:string",
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "strict",
            "secrets_root": "projects/home-lab/secrets",
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "nonexistent-strict-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "@optional_secret:string",
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


def test_strict_mode_ignores_non_secret_todo_placeholders():
    """Strict secrets mode must not fail on TODO markers outside secret annotation paths."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "strict",
            "secrets_root": "projects/home-lab/secrets",
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "firmware": [
                    {
                        "instance": "inst.firmware.test",
                        "layer": "L1",
                        "class_ref": "class.firmware",
                        "object_ref": "obj.firmware",
                        "deployment": {
                            "version": "<TODO_FW_VERSION>",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    error_codes = [d.code for d in result.diagnostics if d.severity == "error"]
    assert "E7208" not in error_codes
    assert "E7210" not in error_codes


def test_placeholder_non_placeholders_preserved():
    """Non-placeholder values in hardware_identity should never be modified."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": False,
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
            stdout=("instance: different-instance\n" "hardware_identity:\n" "  serial_number: SHOULD-NOT-BE-MERGED\n"),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": False,
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "devices": [
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
    assert any(d.code == "E3201" and "hardware_identity_secret_ref" in d.message for d in result.diagnostics)


def test_instance_rows_compiler_rejects_unsafe_identifiers():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "inst:bad",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                    },
                    {
                        "instance": "inst.good",
                        "layer": "L1",
                        "class_ref": "class.router:bad",
                        "object_ref": "obj.router?bad",
                    },
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.has_errors
    e3201_messages = [d.message for d in result.diagnostics if d.code == "E3201"]
    assert any("instance id 'inst:bad'" in message for message in e3201_messages)
    assert any("class_ref 'class.router:bad'" in message for message in e3201_messages)
    assert any("object_ref 'obj.router?bad'" in message for message in e3201_messages)


def test_sidecar_secret_annotations_are_replaced(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=(
                "instance: rtr-slate\n"
                "hardware_identity:\n"
                "  serial_number: SECRET-SN-001\n"
                "  mac_addresses:\n"
                "    wan: AA:BB:CC:DD:EE:01\n"
            ),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "@secret",
                            "mac_addresses": {
                                "wan": "@optional_secret:mac",
                            },
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    assert hw_identity.get("serial_number") == "SECRET-SN-001"
    assert hw_identity.get("mac_addresses", {}).get("wan") == "AA:BB:CC:DD:EE:01"


def test_sidecar_plaintext_conflict_emits_error(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=("instance: rtr-slate\n" "hardware_identity:\n" "  serial_number: SECRET-SN-001\n"),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "PLAINTEXT-SN",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.has_errors
    assert any(d.code == "E7212" for d in result.diagnostics)
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    assert hw_identity.get("serial_number") == "PLAINTEXT-SN"


def test_sidecar_uses_object_secret_annotations_without_instance_mac_duplication(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=(
                "instance: rtr-slate\n"
                "hardware_identity:\n"
                "  serial_number: SECRET-SN-001\n"
                "  mac_addresses:\n"
                "    wan: AA:BB:CC:DD:EE:01\n"
                "    lan1: AA:BB:CC:DD:EE:02\n"
                "    lan2: AA:BB:CC:DD:EE:03\n"
                "    wlan0_5ghz: AA:BB:CC:DD:EE:10\n"
            ),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        objects={
            "obj.glinet.slate_ax1800": {
                "object": "obj.glinet.slate_ax1800",
                "hardware_specs": {
                    "interfaces": {
                        "ethernet": [
                            {"name": "wan", "mac": "@optional_secret:mac"},
                            {"name": "lan1", "mac": "@optional_secret:mac"},
                            {"name": "lan2", "mac": "@optional_secret:mac"},
                        ],
                        "wireless": [
                            {"name": "wlan0", "band": "5ghz", "mac": "@optional_secret:mac"},
                        ],
                    }
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.glinet.slate_ax1800",
                        "hardware_identity": {
                            "serial_number": "@secret",
                            "mac_addresses": {},
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    assert hw_identity.get("serial_number") == "SECRET-SN-001"
    macs = hw_identity.get("mac_addresses", {})
    assert macs.get("wan") == "AA:BB:CC:DD:EE:01"
    assert macs.get("lan1") == "AA:BB:CC:DD:EE:02"
    assert macs.get("lan2") == "AA:BB:CC:DD:EE:03"
    assert macs.get("wlan0_5ghz") == "AA:BB:CC:DD:EE:10"


def test_object_interface_mac_annotations_resolve_without_instance_hardware_identity(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=(
                "instance: rtr-slate\n"
                "hardware_identity:\n"
                "  serial_number: SECRET-SN-001\n"
                "  mac_addresses:\n"
                "    wan: AA:BB:CC:DD:EE:01\n"
                "    lan1: AA:BB:CC:DD:EE:02\n"
                "    lan2: AA:BB:CC:DD:EE:03\n"
                "    wlan0_5ghz: AA:BB:CC:DD:EE:10\n"
            ),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        objects={
            "obj.glinet.slate_ax1800": {
                "object": "obj.glinet.slate_ax1800",
                "hardware_specs": {
                    "interfaces": {
                        "ethernet": [
                            {"name": "wan", "mac": "@optional_secret:mac"},
                            {"name": "lan1", "mac": "@optional_secret:mac"},
                            {"name": "lan2", "mac": "@optional_secret:mac"},
                        ],
                        "wireless": [
                            {"name": "wlan0", "band": "5ghz", "mac": "@optional_secret:mac"},
                        ],
                    }
                },
                "hardware_identity": {"serial_number": "@optional_secret:string"},
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.glinet.slate_ax1800",
                    }
                ]
            }
        },
    )

    annotation_result = registry.execute_plugin("base.compiler.annotation_resolver", ctx, Stage.COMPILE)
    assert annotation_result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    assert hw_identity.get("serial_number") == "SECRET-SN-001"
    macs = hw_identity.get("mac_addresses", {})
    assert macs.get("wan") == "AA:BB:CC:DD:EE:01"
    assert macs.get("lan1") == "AA:BB:CC:DD:EE:02"
    assert macs.get("lan2") == "AA:BB:CC:DD:EE:03"
    assert macs.get("wlan0_5ghz") == "AA:BB:CC:DD:EE:10"


def test_annotation_resolver_formats_validate_secret_values(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=("instance: rtr-slate\n" "hardware_identity:\n" "  mac_addresses:\n" "    wan: NOT-A-MAC\n"),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "mac_addresses": {
                                "wan": "@optional_secret:mac",
                            },
                        },
                    }
                ]
            }
        },
    )

    annotation_result = registry.execute_plugin("base.compiler.annotation_resolver", ctx, Stage.COMPILE)
    assert annotation_result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.has_errors
    assert any(d.code == "E7213" for d in result.diagnostics)
    rows = result.output_data.get("normalized_rows", [])
    wan_value = rows[0]["extensions"]["hardware_identity"]["mac_addresses"]["wan"]
    assert wan_value == "@optional_secret:mac"


def test_object_level_secret_annotation_resolves_serial_without_instance_marker(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=("instance: rtr-slate\n" "hardware_identity:\n" "  serial_number: SECRET-SN-OBJ\n"),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        objects={
            "obj.glinet.slate_ax1800": {
                "object": "obj.glinet.slate_ax1800",
                "hardware_identity": {
                    "serial_number": "@optional_secret:string",
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.glinet.slate_ax1800",
                        "hardware_identity": {},
                    }
                ]
            }
        },
    )

    annotation_result = registry.execute_plugin("base.compiler.annotation_resolver", ctx, Stage.COMPILE)
    assert annotation_result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows", [])
    serial = rows[0]["extensions"]["hardware_identity"]["serial_number"]
    assert serial == "SECRET-SN-OBJ"


def test_object_level_typed_secret_annotation_rejects_invalid_scalar(monkeypatch):
    class FakeResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResult(
            returncode=0,
            stdout=("instance: rtr-slate\n" "hardware_identity:\n" "  serial_number: 12345\n"),
        )

    monkeypatch.setattr(instance_rows_module.subprocess, "run", fake_run)

    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "projects/home-lab/secrets",
            "require_unlock": True,
            "repo_root": str(V5_TOOLS.parent),
        },
        objects={
            "obj.glinet.slate_ax1800": {
                "object": "obj.glinet.slate_ax1800",
                "hardware_identity": {
                    "serial_number": "@optional_secret:string",
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "rtr-slate",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.glinet.slate_ax1800",
                        "hardware_identity": {},
                    }
                ]
            }
        },
    )

    annotation_result = registry.execute_plugin("base.compiler.annotation_resolver", ctx, Stage.COMPILE)
    assert annotation_result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.has_errors
    assert any(d.code == "E7213" for d in result.diagnostics)
    rows = result.output_data.get("normalized_rows", [])
    assert "serial_number" not in rows[0]["extensions"]["hardware_identity"]
