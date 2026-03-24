"""Unit tests for IP resolver (ADR-0044 implementation)."""

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
IP_RESOLVER_PY = ROOT / "topology-tools" / "scripts" / "generators" / "common" / "ip_resolver.py"
ip_resolver_mod = _load_module_from_path(IP_RESOLVER_PY, "ip_resolver")

IpResolver = ip_resolver_mod.IpResolver
resolve_all_service_ips = ip_resolver_mod.resolve_all_service_ips


@pytest.fixture
def topology_with_ips() -> Dict[str, Any]:
    """Topology with L2, L4 networks and services with IP refs."""
    return {
        "L1_foundation": {
            "devices": [
                {"id": "hos-srv-orangepi5-ubuntu"},
            ],
        },
        "L2_network": {
            "networks": [
                {
                    "id": "net-servers",
                    "cidr": "10.0.30.0/24",
                    "ip_allocations": [
                        {
                            "ip": "10.0.30.50/24",
                            "host_os_ref": "hos-ubuntu-orangepi5",
                            "network_ref": "net-servers",
                        },
                        {
                            "ip": "192.168.88.2/24",
                            "host_os_ref": "hos-proxmox-gamayun",
                            "network_ref": "net-mgmt",
                        },
                    ],
                },
                {
                    "id": "net-mgmt",
                    "cidr": "192.168.88.0/24",
                    "ip_allocations": [],
                },
            ],
        },
        "L4_platform": {
            "lxc": [
                {
                    "id": "lxc-postgresql",
                    "networks": [
                        {
                            "network_ref": "net-servers",
                            "ip": "10.0.30.10/24",
                        }
                    ],
                },
                {
                    "id": "lxc-redis",
                    "networks": [
                        {
                            "network_ref": "net-servers",
                            "ip": "10.0.30.20/24",
                        }
                    ],
                },
            ],
            "vms": [
                {
                    "id": "vm-test",
                    "networks": [
                        {
                            "network_ref": "net-servers",
                            "ip_config": {
                                "address": "10.0.30.100/24",
                            },
                        }
                    ],
                }
            ],
            "host_operating_systems": [
                {
                    "id": "hos-ubuntu-orangepi5",
                    "device_ref": "hos-srv-orangepi5-ubuntu",
                },
            ],
        },
        "L5_application": {
            "services": [
                {
                    "id": "svc-nextcloud",
                    "ip_refs": {
                        "postgres_ip": {
                            "lxc_ref": "lxc-postgresql",
                            "network_ref": "net-servers",
                        },
                        "redis_ip": {
                            "lxc_ref": "lxc-redis",
                            "network_ref": "net-servers",
                        },
                    },
                    "config": {
                        "POSTGRES_HOST": "{{ ip_refs.postgres_ip }}",
                        "REDIS_HOST": "{{ ip_refs.redis_ip }}",
                    },
                },
                {
                    "id": "svc-monitoring",
                    "runtime": {
                        "target_ref": "lxc-postgresql",
                        "network_binding_ref": "net-servers",
                    },
                    "url_derived": True,
                    "protocol": "http",
                    "url_port": 9090,
                },
                {
                    "id": "svc-baremetal",
                    "ip_refs": {
                        "host_ip": {
                            "host_os_ref": "hos-ubuntu-orangepi5",
                            "network_ref": "net-servers",
                        },
                    },
                },
            ],
        },
    }


def test_ip_resolver_init(topology_with_ips):
    """Test IpResolver initialization and cache building."""
    resolver = IpResolver(topology_with_ips)

    # Check caches populated
    assert resolver.lxc_ip_cache
    assert "lxc-postgresql:net-servers" in resolver.lxc_ip_cache
    assert resolver.lxc_ip_cache["lxc-postgresql:net-servers"] == "10.0.30.10"


def test_resolve_ip_ref_lxc(topology_with_ips):
    """Test resolving LXC IP reference."""
    resolver = IpResolver(topology_with_ips)

    ip_ref = {
        "lxc_ref": "lxc-postgresql",
        "network_ref": "net-servers",
    }
    ip = resolver.resolve_ip_ref(ip_ref)

    assert ip == "10.0.30.10"


def test_resolve_ip_ref_vm(topology_with_ips):
    """Test resolving VM IP reference."""
    resolver = IpResolver(topology_with_ips)

    ip_ref = {
        "vm_ref": "vm-test",
        "network_ref": "net-servers",
    }
    ip = resolver.resolve_ip_ref(ip_ref)

    assert ip == "10.0.30.100"


def test_resolve_ip_ref_host_os(topology_with_ips):
    """Test resolving host OS IP reference."""
    resolver = IpResolver(topology_with_ips)

    ip_ref = {
        "host_os_ref": "hos-ubuntu-orangepi5",
        "network_ref": "net-servers",
    }
    ip = resolver.resolve_ip_ref(ip_ref)

    assert ip == "10.0.30.50"


def test_resolve_ip_ref_nonexistent(topology_with_ips):
    """Test resolution of nonexistent reference returns None."""
    resolver = IpResolver(topology_with_ips)

    ip_ref = {
        "lxc_ref": "lxc-nonexistent",
        "network_ref": "net-servers",
    }
    ip = resolver.resolve_ip_ref(ip_ref)

    assert ip is None


def test_resolve_service_ip_refs(topology_with_ips):
    """Test resolving all ip_refs in a service."""
    resolver = IpResolver(topology_with_ips)
    service = topology_with_ips["L5_application"]["services"][0]  # svc-nextcloud

    resolved = resolver.resolve_service_ip_refs(service)

    assert resolved["postgres_ip"] == "10.0.30.10"
    assert resolved["redis_ip"] == "10.0.30.20"


def test_resolve_service_url_derived(topology_with_ips):
    """Test deriving service URL from runtime target."""
    resolver = IpResolver(topology_with_ips)
    service = topology_with_ips["L5_application"]["services"][1]  # svc-monitoring

    url = resolver.resolve_service_url(service)

    assert url == "http://10.0.30.10:9090"


def test_substitute_ip_refs_string(topology_with_ips):
    """Test substituting IP refs in string config."""
    resolver = IpResolver(topology_with_ips)

    resolved = {
        "postgres_ip": "10.0.30.10",
        "redis_ip": "10.0.30.20",
    }

    config_str = "POSTGRES_HOST={{ ip_refs.postgres_ip }}"
    result = resolver.substitute_ip_refs(config_str, resolved)

    assert result == "POSTGRES_HOST=10.0.30.10"


def test_substitute_ip_refs_dict(topology_with_ips):
    """Test substituting IP refs in dict config."""
    resolver = IpResolver(topology_with_ips)

    resolved = {
        "postgres_ip": "10.0.30.10",
        "redis_ip": "10.0.30.20",
    }

    config = {
        "POSTGRES_HOST": "{{ ip_refs.postgres_ip }}",
        "REDIS_HOST": "{{ ip_refs.redis_ip }}",
    }
    result = resolver.substitute_ip_refs(config, resolved)

    assert result["POSTGRES_HOST"] == "10.0.30.10"
    assert result["REDIS_HOST"] == "10.0.30.20"


def test_resolve_all_service_ips(topology_with_ips):
    """Test resolving all services' IP refs in topology."""
    results = resolve_all_service_ips(topology_with_ips)

    assert "svc-nextcloud" in results
    assert results["svc-nextcloud"]["ip_refs"]["postgres_ip"] == "10.0.30.10"
    assert results["svc-nextcloud"]["config"]["POSTGRES_HOST"] == "10.0.30.10"

    assert "svc-monitoring" in results
    assert results["svc-monitoring"]["url"] == "http://10.0.30.10:9090"


def test_resolve_all_service_ips_partial_resolution(topology_with_ips):
    """Test partial resolution when some refs cannot be resolved."""
    results = resolve_all_service_ips(topology_with_ips)

    # svc-baremetal should resolve host IP
    assert "svc-baremetal" in results
    assert results["svc-baremetal"]["ip_refs"]["host_ip"] == "10.0.30.50"


def test_cidr_stripping(topology_with_ips):
    """Test that CIDR notation is stripped from IPs."""
    resolver = IpResolver(topology_with_ips)

    # LXC network IPs have CIDR notation, should be stripped
    ip_ref = {
        "lxc_ref": "lxc-postgresql",
        "network_ref": "net-servers",
    }
    ip = resolver.resolve_ip_ref(ip_ref)

    # Should return just the address without /24
    assert "/" not in ip
    assert ip == "10.0.30.10"
