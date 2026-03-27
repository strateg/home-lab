#!/usr/bin/env python3
"""Integration checks for ADR0079 docs domain projection modules."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.docs.network_projection import build_network_projection  # noqa: E402
from plugins.generators.docs.operations_projection import build_operations_projection  # noqa: E402
from plugins.generators.docs.physical_projection import build_physical_projection  # noqa: E402
from plugins.generators.docs.security_projection import build_security_projection  # noqa: E402
from plugins.generators.docs.storage_projection import build_storage_projection  # noqa: E402


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-a",
                    "object_ref": "obj.router.a",
                    "class_ref": "class.network.router",
                    "status": "mapped",
                }
            ],
            "network": [
                {
                    "instance_id": "inst.trust_zone.servers",
                    "object_ref": "obj.network.trust_zone.servers",
                    "class_ref": "class.network.trust_zone",
                    "status": "mapped",
                },
                {
                    "instance_id": "inst.bridge.vmbr0",
                    "object_ref": "obj.network.bridge.vmbr0",
                    "class_ref": "class.network.bridge",
                    "status": "mapped",
                    "instance_data": {"host_ref": "srv-hv"},
                },
                {
                    "instance_id": "inst.vlan.servers",
                    "object_ref": "obj.network.vlan.servers",
                    "class_ref": "class.network.vlan",
                    "status": "mapped",
                    "instance_data": {
                        "managed_by_ref": "rtr-a",
                        "trust_zone_ref": "inst.trust_zone.servers",
                        "dhcp_range": "10.0.30.100-10.0.30.200",
                        "ip_allocations": [{"ip": "10.0.30.2", "device_ref": "srv-a"}],
                    },
                },
            ],
            "data-channels": [
                {
                    "instance_id": "inst.chan.eth.rtr_to_srv",
                    "class_ref": "class.network.data_link",
                    "instance_data": {
                        "endpoint_a": {"device_ref": "rtr-a", "port": "ether1"},
                        "endpoint_b": {"device_ref": "srv-a", "port": "eno1"},
                    },
                }
            ],
            "physical-links": [
                {
                    "instance_id": "inst.ethernet_cable.rtr_to_srv",
                    "class_ref": "class.network.physical_link",
                    "instance_data": {
                        "endpoint_a": {"device_ref": "rtr-a", "port": "ether1"},
                        "endpoint_b": {"device_ref": "srv-a", "port": "eno1"},
                    },
                }
            ],
            "power": [
                {
                    "instance_id": "ups-main",
                    "class_ref": "class.power.ups",
                    "instance_data": {"power": {"external_source": "utility-grid", "max_watts": 500}},
                }
            ],
            "firewall": [
                {
                    "instance_id": "inst.fw.default",
                    "object_ref": "obj.network.firewall_policy.default",
                    "class_ref": "class.network.firewall_policy",
                    "instance_data": {"chain": "forward", "managed_by_ref": "rtr-a"},
                    "status": "mapped",
                }
            ],
            "storage": [
                {
                    "instance_id": "inst.pool.local",
                    "object_ref": "obj.storage.pool.local",
                    "class_ref": "class.storage.pool",
                    "instance_data": {"host_ref": "srv-a"},
                    "status": "mapped",
                },
                {
                    "instance_id": "inst.data_asset.pg",
                    "object_ref": "obj.storage.asset.pg",
                    "class_ref": "class.storage.data_asset",
                    "instance_data": {"host_ref": "srv-a", "engine": "postgresql"},
                    "status": "mapped",
                },
            ],
            "operations": [
                {
                    "instance_id": "backup-pg",
                    "object_ref": "obj.operations.backup.default",
                    "class_ref": "class.operations.backup",
                    "instance_data": {
                        "target_ref": "lxc-postgresql",
                        "storage_ref": "inst.pool.local",
                        "data_asset_ref": "inst.data_asset.pg",
                    },
                    "status": "mapped",
                }
            ],
            "observability": [
                {
                    "instance_id": "health-pg",
                    "object_ref": "obj.observability.healthcheck.pg",
                    "class_ref": "class.observability.healthcheck",
                    "instance_data": {"target_ref": "lxc-postgresql", "interval": "60s"},
                    "status": "mapped",
                },
                {
                    "instance_id": "alert-pg",
                    "object_ref": "obj.observability.alert.pg",
                    "class_ref": "class.observability.alert",
                    "instance_data": {"severity": "critical", "channels": ["email"]},
                    "status": "mapped",
                },
            ],
            "services": [
                {
                    "instance_id": "svc-vpn",
                    "object_ref": "obj.service.vpn.tailscale",
                    "class_ref": "class.service.vpn",
                    "instance_data": {"vpn_type": "tailscale", "trust_zone_ref": "inst.trust_zone.servers"},
                    "status": "mapped",
                }
            ],
            "qos": [
                {
                    "instance_id": "inst.qos.wan",
                    "object_ref": "obj.network.qos.wan",
                    "class_ref": "class.network.qos",
                    "instance_data": {"managed_by_ref": "rtr-a", "interface": "ether1"},
                    "status": "mapped",
                }
            ],
        }
    }


def test_network_projection_extracts_vlan_bridge_and_allocations() -> None:
    projection = build_network_projection(_compiled_fixture())
    assert projection["counts"]["networks"] == 1
    assert projection["counts"]["bridges"] == 1
    assert projection["counts"]["allocations"] == 1
    assert projection["networks"][0]["instance_id"] == "inst.vlan.servers"


def test_physical_projection_extracts_devices_and_links() -> None:
    projection = build_physical_projection(_compiled_fixture())
    assert projection["counts"]["devices"] == 1
    assert projection["counts"]["data_links"] == 1
    assert projection["counts"]["physical_links"] == 1


def test_security_projection_extracts_zone_bindings_and_firewall() -> None:
    projection = build_security_projection(_compiled_fixture())
    assert projection["counts"]["trust_zones"] == 1
    assert projection["counts"]["vlans"] == 1
    assert projection["counts"]["firewall_policies"] == 1
    assert projection["zone_network_bindings"]["inst.trust_zone.servers"] == ["inst.vlan.servers"]


def test_storage_projection_extracts_pools_assets_and_mount_chains() -> None:
    projection = build_storage_projection(_compiled_fixture())
    assert projection["counts"]["storage_pools"] == 1
    assert projection["counts"]["data_assets"] == 1
    assert projection["counts"]["mount_chains"] == 1


def test_operations_projection_extracts_monitoring_backup_vpn_qos_ups() -> None:
    projection = build_operations_projection(_compiled_fixture())
    assert projection["counts"]["healthchecks"] == 1
    assert projection["counts"]["alerts"] == 1
    assert projection["counts"]["backup_policies"] == 1
    assert projection["counts"]["vpn_services"] == 1
    assert projection["counts"]["qos_policies"] == 1
    assert projection["counts"]["ups_inventory"] == 1
