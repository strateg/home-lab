"""Unit tests for Terraform resolver helpers."""

from scripts.generators.terraform.resolvers import build_storage_map, resolve_interface_names, resolve_lxc_resources


def _base_topology():
    return {
        "L1_foundation": {
            "devices": [
                {
                    "id": "hyper-1",
                    "type": "hypervisor",
                    "interfaces": [
                        {"id": "if-eth-usb", "physical_name": "enx123"},
                        {"id": "if-eth-builtin", "physical_name": "enp3s0"},
                    ],
                }
            ]
        },
        "L3_data": {
            "storage": [
                {"id": "local-lvm", "type": "lvm"},
            ],
            "storage_endpoints": [
                {"id": "local", "platform": "proxmox"},
                {"id": "host-root", "platform": "host"},
            ],
        },
        "L4_platform": {
            "resource_profiles": [
                {"id": "small", "cpu": {"cores": 2}, "memory": {"mb": 1024}},
            ]
        },
    }


def test_resolve_interface_names():
    topology = _base_topology()
    bridges = [{"id": "br0", "ports": ["if-eth-usb", "unknown"]}]
    resolved = resolve_interface_names(topology, bridges)

    assert resolved[0]["ports"] == ["enx123", "unknown"]


def test_resolve_lxc_resources_profile():
    topology = _base_topology()
    lxc = [{"id": "ct1", "resource_profile_ref": "small"}]
    resolved = resolve_lxc_resources(topology, lxc)

    assert resolved[0]["resources"]["cores"] == 2
    assert resolved[0]["resources"]["memory_mb"] == 1024


def test_build_storage_map_filters_platform():
    topology = _base_topology()
    storage = build_storage_map(topology, platform="proxmox")

    assert "local" in storage
    assert "host-root" not in storage
