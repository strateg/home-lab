"""Unit tests for network validator checks (L2 network validation)."""

import importlib.util
from pathlib import Path
from typing import Any, Dict

import pytest


def _load_module_from_path(path: Path, name: str):
    """Load Python module directly from file path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None:
        raise RuntimeError(f"Could not load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    if loader is None:
        raise RuntimeError(f"Could not find loader for {path}")
    loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[3]
NETWORK_PY = ROOT / "topology-tools" / "scripts" / "validators" / "checks" / "network.py"
network_mod = _load_module_from_path(NETWORK_PY, "network_checks")

# Import functions under test
check_vlan_tags = network_mod.check_vlan_tags
check_network_refs = network_mod.check_network_refs
check_bridge_refs = network_mod.check_bridge_refs
check_reserved_ranges = network_mod.check_reserved_ranges
check_trust_zone_firewall_refs = network_mod.check_trust_zone_firewall_refs


@pytest.fixture
def minimal_topology_network() -> Dict[str, Any]:
    """Minimal topology with L2 network configuration."""
    return {
        "L1_foundation": {
            "devices": [
                {
                    "id": "hos-srv-test",
                    "interfaces": [
                        {"id": "eth0", "name": "Ethernet 0"},
                        {"id": "eth1", "name": "Ethernet 1"},
                    ],
                },
            ],
        },
        "L2_network": {
            "networks": [
                {
                    "id": "net-mgmt",
                    "name": "Management",
                    "cidr": "10.0.0.0/24",
                    "gateway": "10.0.0.1",
                    "vlan": None,
                    "profile_ref": None,
                    "reserved_ranges": [
                        {"start": "10.0.0.1", "end": "10.0.0.10", "purpose": "gateway"},
                    ],
                },
                {
                    "id": "net-data",
                    "name": "Data",
                    "cidr": "10.0.1.0/24",
                    "gateway": "10.0.1.1",
                    "vlan": 100,
                    "profile_ref": None,
                    "reserved_ranges": [
                        {"start": "10.0.1.1", "end": "10.0.1.10", "purpose": "gateway"},
                    ],
                },
            ],
            "bridges": [
                {
                    "id": "br-data",
                    "name": "Data Bridge",
                    "vlan_aware": True,
                    "device_ref": "hos-srv-test",
                    "ports": ["eth0", "eth1"],
                },
            ],
            "network_profiles": {},
            "trust_zones": {},
            "firewall_policies": [],
        },
        "L4_platform": {
            "lxc": [
                {
                    "id": "lxc-test-1",
                    "name": "Test LXC",
                    "networks": [
                        {
                            "network_ref": "net-mgmt",
                            "bridge_ref": "br-data",
                            "vlan_tag": None,
                        }
                    ],
                }
            ],
            "vms": [],
        },
    }


def test_check_vlan_tags_no_errors(minimal_topology_network):
    """Test VLAN tag validation with valid config."""
    errors = []
    warnings = []
    check_vlan_tags(minimal_topology_network, errors=errors, warnings=warnings)
    # net-mgmt has no VLAN, vlan_tag is None — should be OK
    assert not any("vlan_tag" in e and "does not match" in e for e in errors)


def test_check_vlan_tags_mismatch(minimal_topology_network):
    """Test VLAN tag mismatch detection."""
    # Add vlan_tag that doesn't match network VLAN
    minimal_topology_network["L4_platform"]["lxc"][0]["networks"][0]["vlan_tag"] = 200
    minimal_topology_network["L4_platform"]["lxc"][0]["networks"][0]["network_ref"] = "net-data"

    errors = []
    warnings = []
    check_vlan_tags(minimal_topology_network, errors=errors, warnings=warnings)

    assert any("vlan_tag" in e and "does not match" in e for e in errors)


def test_check_vlan_tags_missing_tag_warning(minimal_topology_network):
    """Test warning when VLAN tag not set but network has VLAN."""
    # net-data has vlan=100 but vlan_tag not set
    minimal_topology_network["L4_platform"]["lxc"][0]["networks"][0]["network_ref"] = "net-data"
    minimal_topology_network["L4_platform"]["lxc"][0]["networks"][0]["vlan_tag"] = None

    errors = []
    warnings = []
    check_vlan_tags(minimal_topology_network, errors=errors, warnings=warnings)

    assert any("vlan_tag is not set" in w for w in warnings)


def test_check_network_refs_valid(minimal_topology_network):
    """Test network references validation with valid refs."""
    ids = {
        "networks": {"net-mgmt", "net-data"},
        "trust_zones": set(),
        "network_profiles": set(),
    }
    errors = []
    warnings = []

    check_network_refs(minimal_topology_network, ids, errors=errors, warnings=warnings)

    # No errors for valid network refs
    assert not errors


def test_check_network_refs_invalid_trust_zone(minimal_topology_network):
    """Test error on invalid trust_zone_ref."""
    minimal_topology_network["L2_network"]["networks"][0]["trust_zone_ref"] = "zone-nonexistent"

    ids = {
        "networks": {"net-mgmt", "net-data"},
        "trust_zones": set(),
        "network_profiles": set(),
    }
    errors = []
    warnings = []

    check_network_refs(minimal_topology_network, ids, errors=errors, warnings=warnings)

    assert any("trust_zone_ref" in e and "does not exist" in e for e in errors)


def test_check_bridge_refs_valid(minimal_topology_network):
    """Test bridge references are valid."""
    ids = {
        "bridges": {"br-data"},
        "devices": {"hos-srv-test"},
        "networks": {"net-mgmt", "net-data"},
        "interfaces": {"eth0", "eth1"},
    }
    errors = []
    warnings = []

    check_bridge_refs(minimal_topology_network, ids, errors=errors, warnings=warnings)

    # Valid config should have no errors
    assert not errors


def test_check_bridge_refs_missing_bridge(minimal_topology_network):
    """Test error on missing bridge reference."""
    # Add port that doesn't exist in device interfaces
    minimal_topology_network["L2_network"]["bridges"][0]["ports"].append("eth99")

    ids = {
        "bridges": {"br-data"},
        "devices": {"hos-srv-test"},
        "networks": {"net-mgmt", "net-data"},
        "interfaces": {"eth0", "eth1"},
    }
    errors = []
    warnings = []

    check_bridge_refs(minimal_topology_network, ids, errors=errors, warnings=warnings)

    assert any("port" in e and "does not exist" in e for e in errors)


def test_check_reserved_ranges_overlap_detection(minimal_topology_network):
    """Test detection of overlapping IP ranges."""
    # Add overlapping reserved ranges in same network
    minimal_topology_network["L2_network"]["networks"][0]["reserved_ranges"].append(
        {"start": "10.0.0.5", "end": "10.0.0.20", "purpose": "reserved"},  # Overlaps with existing 10.0.0.1-10.0.0.10
    )

    errors = []
    warnings = []

    check_reserved_ranges(minimal_topology_network, errors=errors, warnings=warnings)

    # Should detect overlap
    assert any("overlap" in e.lower() for e in errors)


def test_check_reserved_ranges_no_overlap(minimal_topology_network):
    """Test non-overlapping ranges pass."""
    errors = []
    warnings = []

    check_reserved_ranges(minimal_topology_network, errors=errors, warnings=warnings)

    # No overlaps — no errors
    assert not errors


def test_check_trust_zone_firewall_refs_no_zones(minimal_topology_network):
    """Test firewall refs check with minimal config."""
    ids = {"firewall_policies": set(), "networks": {"net-mgmt", "net-data"}}
    errors = []
    warnings = []

    check_trust_zone_firewall_refs(minimal_topology_network, ids, errors=errors, warnings=warnings)

    # No errors with minimal config
    assert not errors
