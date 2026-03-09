#!/usr/bin/env python3
"""Test ADR 0064 capability derivation end-to-end."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EFFECTIVE_JSON = REPO_ROOT / "v5-build" / "effective-topology.json"
COMPILER = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"


def run_compiler() -> int:
    """Run v5 compiler and return exit code."""
    result = subprocess.run(
        [sys.executable, str(COMPILER), "--require-new-model"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Compiler failed:\n{result.stdout}\n{result.stderr}")
    return result.returncode


def load_effective_topology() -> dict:
    """Load the effective topology JSON."""
    with open(EFFECTIVE_JSON) as f:
        return json.load(f)


def test_compiler_succeeds() -> bool:
    """Test that compiler succeeds with --require-new-model."""
    exit_code = run_compiler()
    if exit_code != 0:
        print("FAIL: Compiler did not succeed with --require-new-model")
        return False
    print("PASS: Compiler succeeds with --require-new-model")
    return True


def test_firmware_capabilities_derived() -> bool:
    """Test that firmware capabilities are properly derived."""
    data = load_effective_topology()

    # Check mikrotik-chateau device
    device = None
    for inst in data["instances"].get("l1_devices", []):
        if inst["id"] == "mikrotik-chateau":
            device = inst
            break

    if device is None:
        print("FAIL: mikrotik-chateau device not found")
        return False

    derived_caps = device.get("instance", {}).get("derived_capabilities", [])

    # Expected firmware capabilities
    expected_firmware_caps = [
        "cap.firmware.mikrotik",
        "cap.firmware.routeros",
        "cap.firmware.arch.arm64",
        "cap.arch.arm64",
    ]

    missing = [cap for cap in expected_firmware_caps if cap not in derived_caps]
    if missing:
        print(f"FAIL: Missing firmware capabilities: {missing}")
        print(f"  Got: {derived_caps}")
        return False

    print("PASS: Firmware capabilities correctly derived")
    return True


def test_os_capabilities_derived() -> bool:
    """Test that OS capabilities are properly derived."""
    data = load_effective_topology()

    # Check mikrotik-chateau device
    device = None
    for inst in data["instances"].get("l1_devices", []):
        if inst["id"] == "mikrotik-chateau":
            device = inst
            break

    if device is None:
        print("FAIL: mikrotik-chateau device not found")
        return False

    derived_caps = device.get("instance", {}).get("derived_capabilities", [])

    # Expected OS capabilities
    expected_os_caps = [
        "cap.os.routeros",
        "cap.os.routeros.7",
        "cap.os.init.proprietary",
        "cap.os.pkg.none",
    ]

    missing = [cap for cap in expected_os_caps if cap not in derived_caps]
    if missing:
        print(f"FAIL: Missing OS capabilities: {missing}")
        print(f"  Got: {derived_caps}")
        return False

    print("PASS: OS capabilities correctly derived")
    return True


def test_effective_software_populated() -> bool:
    """Test that effective_software is properly populated."""
    data = load_effective_topology()

    # Check mikrotik-chateau device
    device = None
    for inst in data["instances"].get("l1_devices", []):
        if inst["id"] == "mikrotik-chateau":
            device = inst
            break

    if device is None:
        print("FAIL: mikrotik-chateau device not found")
        return False

    effective_software = device.get("instance", {}).get("effective_software", {})

    # Check firmware
    firmware = effective_software.get("firmware")
    if not firmware:
        print("FAIL: effective_software.firmware is empty")
        return False

    if firmware.get("vendor") != "mikrotik":
        print(f"FAIL: Expected vendor=mikrotik, got {firmware.get('vendor')}")
        return False

    if firmware.get("architecture") != "arm64":
        print(f"FAIL: Expected architecture=arm64, got {firmware.get('architecture')}")
        return False

    # Check OS
    os_list = effective_software.get("os", [])
    if not os_list:
        print("FAIL: effective_software.os is empty")
        return False

    os_entry = os_list[0]
    if os_entry.get("family") != "routeros":
        print(f"FAIL: Expected family=routeros, got {os_entry.get('family')}")
        return False

    print("PASS: effective_software correctly populated")
    return True


def test_firmware_ref_os_refs_present() -> bool:
    """Test that firmware_ref and os_refs are present for devices per class policy."""
    data = load_effective_topology()

    all_pass = True
    for inst in data["instances"].get("l1_devices", []):
        instance_data = inst.get("instance", {})
        firmware_ref = instance_data.get("firmware_ref")
        os_refs = instance_data.get("os_refs", [])
        class_data = inst.get("class", {})
        os_policy = class_data.get("os_policy", "allowed")

        if not firmware_ref:
            print(f"FAIL: {inst['id']} missing firmware_ref")
            all_pass = False

        # Only require os_refs if os_policy is "required"
        if os_policy == "required" and not os_refs:
            print(f"FAIL: {inst['id']} missing os_refs (os_policy=required)")
            all_pass = False

        # os_refs must be empty if os_policy is "forbidden"
        if os_policy == "forbidden" and os_refs:
            print(f"FAIL: {inst['id']} has os_refs but os_policy=forbidden")
            all_pass = False

    if all_pass:
        print("PASS: All devices have correct firmware_ref and os_refs per class policy")
    return all_pass


def test_arch_from_firmware_only() -> bool:
    """Test that cap.arch.* comes only from firmware (single source of truth)."""
    data = load_effective_topology()

    # Check that architecture capability is present and consistent
    device = None
    for inst in data["instances"].get("l1_devices", []):
        if inst["id"] == "mikrotik-chateau":
            device = inst
            break

    if device is None:
        print("FAIL: mikrotik-chateau device not found")
        return False

    derived_caps = device.get("instance", {}).get("derived_capabilities", [])
    arch_caps = [cap for cap in derived_caps if cap.startswith("cap.arch.")]

    if len(arch_caps) != 1:
        print(f"FAIL: Expected exactly 1 cap.arch.* capability, got {len(arch_caps)}: {arch_caps}")
        return False

    if arch_caps[0] != "cap.arch.arm64":
        print(f"FAIL: Expected cap.arch.arm64, got {arch_caps[0]}")
        return False

    print("PASS: Architecture capability correctly derived from firmware only")
    return True


def main() -> int:
    """Run all tests and return exit code."""
    print("=" * 60)
    print("ADR 0064 Capability Derivation Tests")
    print("=" * 60)
    print()

    tests = [
        test_compiler_succeeds,
        test_firmware_capabilities_derived,
        test_os_capabilities_derived,
        test_effective_software_populated,
        test_firmware_ref_os_refs_present,
        test_arch_from_firmware_only,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__} raised exception: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
