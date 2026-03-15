#!/usr/bin/env python3
"""ADR0064 capability derivation integration tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EFFECTIVE_JSON = REPO_ROOT / "v5-build" / "effective-topology.json"
COMPILER = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"


def _run_compiler() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMPILER), "--require-new-model"],
        capture_output=True,
        text=True,
        check=False,
    )


def _find_instance(data: dict, instance_name: str) -> dict:
    for inst in data["instances"].get("l1_devices", []):
        instance_field = inst.get("instance")
        if isinstance(instance_field, str) and instance_field == instance_name:
            return inst
        if inst.get("source_id") == instance_name:
            return inst
        if isinstance(instance_field, dict) and instance_field.get("instance") == instance_name:
            return inst
    raise AssertionError(f"Instance '{instance_name}' not found")


@pytest.fixture(scope="module")
def effective_topology() -> dict:
    result = _run_compiler()
    assert result.returncode == 0, f"Compiler failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return json.loads(EFFECTIVE_JSON.read_text(encoding="utf-8"))


def test_compiler_succeeds(effective_topology: dict) -> None:
    assert isinstance(effective_topology, dict)


def test_firmware_capabilities_derived(effective_topology: dict) -> None:
    device = _find_instance(effective_topology, "rtr-mikrotik-chateau")
    derived_caps = device.get("instance", {}).get("derived_capabilities", [])

    expected_firmware_caps = [
        "cap.firmware.mikrotik",
        "cap.firmware.routeros",
        "cap.firmware.arch.arm64",
        "cap.arch.arm64",
    ]
    missing = [cap for cap in expected_firmware_caps if cap not in derived_caps]
    assert not missing, f"Missing firmware capabilities: {missing}, got: {derived_caps}"


def test_os_capabilities_derived(effective_topology: dict) -> None:
    device = _find_instance(effective_topology, "rtr-mikrotik-chateau")
    derived_caps = device.get("instance", {}).get("derived_capabilities", [])

    expected_os_caps = [
        "cap.os.routeros",
        "cap.os.routeros.7",
        "cap.os.init.proprietary",
        "cap.os.pkg.none",
    ]
    missing = [cap for cap in expected_os_caps if cap not in derived_caps]
    assert not missing, f"Missing OS capabilities: {missing}, got: {derived_caps}"


def test_effective_software_populated(effective_topology: dict) -> None:
    device = _find_instance(effective_topology, "rtr-mikrotik-chateau")
    effective_software = device.get("instance", {}).get("effective_software", {})

    firmware = effective_software.get("firmware")
    assert firmware, "effective_software.firmware is empty"
    assert firmware.get("vendor") == "mikrotik"
    assert firmware.get("architecture") == "arm64"

    os_list = effective_software.get("os", [])
    assert os_list, "effective_software.os is empty"
    assert os_list[0].get("family") == "routeros"


def test_firmware_ref_os_refs_present(effective_topology: dict) -> None:
    # Skip non-compute entities (cables, passive components)
    skip_prefixes = ("inst.ethernet_cable", "inst.cable", "inst.patch")

    for inst in effective_topology["instances"].get("l1_devices", []):
        instance_data = inst.get("instance", {})
        instance_name = inst.get("source_id") or inst.get("instance")

        # Skip passive components that don't have firmware
        if any(instance_name.startswith(prefix) for prefix in skip_prefixes):
            continue

        firmware_ref = instance_data.get("firmware_ref")
        os_refs = instance_data.get("os_refs", [])
        class_data = inst.get("class", {})
        os_policy = class_data.get("os_policy", "allowed")

        assert firmware_ref, f"{instance_name} missing firmware_ref"
        if os_policy == "required":
            assert os_refs, f"{instance_name} missing os_refs (os_policy=required)"
        if os_policy == "forbidden":
            assert not os_refs, f"{instance_name} has os_refs but os_policy=forbidden"


def test_arch_from_firmware_only(effective_topology: dict) -> None:
    device = _find_instance(effective_topology, "rtr-mikrotik-chateau")
    derived_caps = device.get("instance", {}).get("derived_capabilities", [])
    arch_caps = [cap for cap in derived_caps if cap.startswith("cap.arch.")]

    assert len(arch_caps) == 1, f"Expected exactly 1 cap.arch.* capability, got {arch_caps}"
    assert arch_caps[0] == "cap.arch.arm64"
