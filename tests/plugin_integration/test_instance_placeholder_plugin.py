#!/usr/bin/env python3
"""Integration tests for ADR0068 placeholder validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.instance_placeholders"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(
    *,
    object_defaults: dict,
    instance_overrides: dict | None,
    config: dict | None = None,
    status: str | None = None,
) -> PluginContext:
    row: dict = {
        "instance": "dev-1",
        "layer": "L1",
        "class_ref": "class.router",
        "object_ref": "obj.test.device",
    }
    if isinstance(status, str) and status:
        row["status"] = status
    if instance_overrides is not None:
        row["instance_overrides"] = instance_overrides

    return PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        config=config or {},
        classes={"class.router": {"class": "class.router"}},
        objects={
            "obj.test.device": {
                "object": "obj.test.device",
                "defaults": object_defaults,
            }
        },
        instance_bindings={"instance_bindings": {"devices": [row]}},
    )


def test_placeholder_plugin_valid_overrides():
    registry = _registry()
    ctx = _context(
        object_defaults={
            "hardware_identity": {
                "serial_number": "@required:string",
                "mac_wan": "@optional:mac",
            }
        },
        instance_overrides={
            "defaults": {
                "hardware_identity": {
                    "serial_number": "GL-AXT-001122",
                    "mac_wan": "AA:BB:CC:DD:EE:01",
                }
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors


def test_placeholder_plugin_missing_required():
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"serial_number": "@required:string"}},
        instance_overrides={"defaults": {"hardware_identity": {}}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6802" for d in result.diagnostics)


def test_placeholder_plugin_rejects_unmarked_override():
    registry = _registry()
    ctx = _context(
        object_defaults={
            "role": "gateway",
            "hardware_identity": {"serial_number": "@required:string"},
        },
        instance_overrides={
            "defaults": {
                "role": "travel_router",
                "hardware_identity": {"serial_number": "SN-001"},
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6803" for d in result.diagnostics)


def test_placeholder_plugin_rejects_invalid_format():
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"mac_wan": "@required:mac"}},
        instance_overrides={"defaults": {"hardware_identity": {"mac_wan": "INVALID-MAC"}}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6805" for d in result.diagnostics)


def test_placeholder_plugin_detects_unknown_format_token():
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"serial_number": "@required:not_registered"}},
        instance_overrides={"defaults": {"hardware_identity": {"serial_number": "SN-001"}}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6801" for d in result.diagnostics)


def test_placeholder_plugin_accepts_hardware_identity_mac_addresses():
    registry = _registry()
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={
            "obj.test.router": {
                "object": "obj.test.router",
                "hardware_specs": {
                    "interfaces": {
                        "ethernet": [
                            {"name": "wan", "mac": "@optional:mac"},
                            {"name": "lan1", "mac": "@optional:mac"},
                        ]
                    }
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "router-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.test.router",
                        "hardware_identity": {
                            "mac_addresses": {
                                "wan": "AA:BB:CC:DD:EE:01",
                                "lan1": "AA:BB:CC:DD:EE:02",
                            }
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors


def test_placeholder_plugin_rejects_invalid_hardware_identity_mac():
    registry = _registry()
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={
            "obj.test.router": {
                "object": "obj.test.router",
                "hardware_specs": {
                    "interfaces": {
                        "ethernet": [
                            {"name": "wan", "mac": "@optional:mac"},
                        ]
                    }
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "router-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.test.router",
                        "hardware_identity": {
                            "mac_addresses": {
                                "wan": "INVALID-MAC",
                            }
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6805" for d in result.diagnostics)
    assert any("hardware_identity.mac_addresses.wan" in d.path for d in result.diagnostics)


def test_placeholder_plugin_accepts_wireless_alias_and_cellular_mac():
    registry = _registry()
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={
            "obj.test.router": {
                "object": "obj.test.router",
                "hardware_specs": {
                    "interfaces": {
                        "wireless": [
                            {"name": "wlan0", "band": "5ghz", "mac": "@optional:mac"},
                        ],
                        "cellular": [
                            {"name": "lte1", "mac": "@optional:mac"},
                        ],
                    }
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "router-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.test.router",
                        "hardware_identity": {
                            "mac_addresses": {
                                "wlan0_5ghz": "AA:BB:CC:DD:EE:10",
                                "lte1": "AA:BB:CC:DD:EE:20",
                            }
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors


def test_placeholder_plugin_detects_unresolved_instance_marker():
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"mac_wan": "@required:mac"}},
        instance_overrides={"defaults": {"hardware_identity": {"mac_wan": "@required:mac"}}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6806" for d in result.diagnostics)


def test_placeholder_plugin_warn_mode_downgrades_missing_required():
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"serial_number": "@required:string"}},
        instance_overrides={"defaults": {"hardware_identity": {}}},
        config={"enforcement_mode": "warn"},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(d.code == "E6802" and d.severity == "warning" for d in result.diagnostics)


def test_placeholder_plugin_warn_gate_new_keeps_modeled_strict():
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"serial_number": "@required:string"}},
        instance_overrides={"defaults": {"hardware_identity": {}}},
        config={"enforcement_mode": "warn+gate-new", "gate_statuses": ["modeled"]},
        status="modeled",
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6802" and d.severity == "error" for d in result.diagnostics)


def test_placeholder_plugin_accepts_optional_secret_annotations():
    registry = _registry()
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={
            "obj.test.router": {
                "object": "obj.test.router",
                "hardware_specs": {
                    "interfaces": {
                        "ethernet": [
                            {"name": "wan", "mac": "@optional_secret:mac"},
                        ]
                    }
                },
            }
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "router-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.test.router",
                        "hardware_identity": {
                            "mac_addresses": {
                                "wan": "@optional_secret:mac",
                            }
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors


def test_placeholder_plugin_rejects_plaintext_for_optional_secret() -> None:
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"serial_number": "@optional_secret:string"}},
        instance_overrides={"defaults": {"hardware_identity": {"serial_number": "HM80BF3ZNBB"}}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E6807" for d in result.diagnostics)


def test_placeholder_plugin_accepts_sops_ciphertext_for_optional_secret() -> None:
    registry = _registry()
    ctx = _context(
        object_defaults={"hardware_identity": {"serial_number": "@optional_secret:string"}},
        instance_overrides={
            "defaults": {"hardware_identity": {"serial_number": "ENC[AES256_GCM,data:abc,iv:def,tag:ghi,type:str]"}}
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
