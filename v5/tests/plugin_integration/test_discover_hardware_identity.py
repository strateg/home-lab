#!/usr/bin/env python3
"""Tests for discover-hardware-identity utility helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "v5" / "topology-tools" / "discover-hardware-identity.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("discover_hardware_identity", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_hardware_identity_secret_paths_includes_serial_and_interface_macs():
    mod = _load_module()
    payload = {
        "hardware_identity": {
            "serial_number": "@optional_secret:string",
        },
        "hardware_specs": {
            "interfaces": {
                "ethernet": [
                    {"name": "wan", "mac": "@optional_secret:mac"},
                    {"name": "lan1", "mac": "@optional_secret:mac"},
                ],
                "wireless": [
                    {"name": "wlan0", "band": "5ghz", "mac": "@optional_secret:mac"},
                ],
            }
        },
    }
    paths = mod.collect_hardware_identity_secret_paths(payload)
    assert "hardware_identity.serial_number" in paths
    assert "hardware_identity.mac_addresses.wan" in paths
    assert "hardware_identity.mac_addresses.lan1" in paths
    assert "hardware_identity.mac_addresses.wlan0_5ghz" in paths


def test_build_patch_prefers_discovered_values_and_fills_placeholders():
    mod = _load_module()
    annotation = mod.FieldAnnotation(
        name="optional_secret",
        value_type="mac",
        required=False,
        optional=True,
        secret=True,
    )
    serial = mod.FieldAnnotation(
        name="optional_secret",
        value_type="string",
        required=False,
        optional=True,
        secret=True,
    )
    path_specs = {
        "hardware_identity.serial_number": serial,
        "hardware_identity.mac_addresses.wan": annotation,
    }
    discovered = {
        "hardware_identity": {
            "serial_number": "SN-001",
        }
    }
    formats = {
        "string": {"type": "string"},
        "mac": {"type": "string", "pattern": "^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"},
    }
    patch, errors = mod.build_hardware_identity_patch(
        instance_id="rtr-test",
        path_specs=path_specs,
        discovered=discovered,
        include_placeholders=True,
        formats=formats,
    )
    assert errors == []
    assert patch is not None
    assert patch["instance"] == "rtr-test"
    assert patch["hardware_identity"]["serial_number"] == "SN-001"
    assert patch["hardware_identity"]["mac_addresses"]["wan"] == "<DISCOVER_MAC_WAN>"


def test_build_patch_rejects_invalid_discovered_format():
    mod = _load_module()
    annotation = mod.FieldAnnotation(
        name="optional_secret",
        value_type="mac",
        required=False,
        optional=True,
        secret=True,
    )
    patch, errors = mod.build_hardware_identity_patch(
        instance_id="rtr-test",
        path_specs={"hardware_identity.mac_addresses.wan": annotation},
        discovered={"hardware_identity": {"mac_addresses": {"wan": "BAD-MAC"}}},
        include_placeholders=False,
        formats={"mac": {"type": "string", "pattern": "^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"}},
    )
    assert patch is None
    assert errors
