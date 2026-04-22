#!/usr/bin/env python3
"""Integration checks for generator projection helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.object_projection_loader import (  # noqa: E402
    load_bootstrap_projection_module,
    load_object_projection_module,
)
from plugins.generators.projections import (  # noqa: E402
    build_ansible_projection,
    build_docs_projection,
    build_topology_projection,
)

_PROXMOX_PROJECTIONS = load_object_projection_module("proxmox")
_MIKROTIK_PROJECTIONS = load_object_projection_module("mikrotik")
_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()

ProjectionError = _PROXMOX_PROJECTIONS.ProjectionError
build_proxmox_projection = _PROXMOX_PROJECTIONS.build_proxmox_projection
build_mikrotik_projection = _MIKROTIK_PROJECTIONS.build_mikrotik_projection
build_bootstrap_projection = _BOOTSTRAP_PROJECTIONS.build_bootstrap_projection


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-mk",
                    "instance": {
                        "materializes_object": "obj.mikrotik.chateau_lte7_ax",
                        "materializes_class": "class.network.router",
                    },
                },
                {
                    "instance_id": "srv-gamayun",
                    "instance": {
                        "materializes_object": "obj.proxmox.ve",
                        "materializes_class": "class.compute.hypervisor.proxmox",
                    },
                },
                {
                    "instance_id": "srv-orangepi5",
                    "instance": {
                        "materializes_object": "obj.orangepi.rk3588.debian",
                        "materializes_class": "class.compute.sbc",
                    },
                },
                {
                    "instance_id": "inst.ethernet_cable.cat5e",
                    "instance": {
                        "materializes_object": "obj.network.ethernet_cable",
                        "materializes_class": "class.network.physical_link",
                    },
                },
            ],
            "lxc": [
                {
                    "instance_id": "lxc-redis",
                    "instance": {
                        "materializes_object": "obj.proxmox.lxc.debian12.redis",
                        "materializes_class": "class.compute.workload.container",
                    },
                },
                {
                    "instance_id": "lxc-grafana",
                    "instance": {
                        "materializes_object": "obj.proxmox.lxc.debian12.base",
                        "materializes_class": "class.compute.workload.container",
                    },
                },
            ],
            "network": [
                {
                    "instance_id": "inst.net.lan",
                    "instance": {
                        "materializes_object": "obj.network.l2_segment",
                        "materializes_class": "class.network.l2_segment",
                    },
                },
                {
                    "instance_id": "inst.net.wan",
                    "instance": {
                        "materializes_object": "obj.network.l2_segment",
                        "materializes_class": "class.network.l2_segment",
                    },
                },
            ],
            "vm": [
                {
                    "instance_id": "vm-analytics",
                    "instance": {
                        "materializes_object": "obj.proxmox.vm.debian12.analytics",
                        "materializes_class": "class.compute.workload.vm",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                    "layer": "L1",
                }
            ],
            "services": [
                {"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}},
                {"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}},
            ],
        }
    }


def test_proxmox_projection_is_stable_and_scoped() -> None:
    projection = build_proxmox_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["proxmox_nodes"]] == ["srv-gamayun"]
    assert [row["instance_id"] for row in projection["lxc"]] == ["lxc-grafana", "lxc-redis"]
    assert [row["instance_id"] for row in projection["services"]] == ["svc-redis"]


def test_mikrotik_projection_is_stable_and_scoped() -> None:
    projection = build_mikrotik_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["routers"]] == ["rtr-mk"]
    assert [row["instance_id"] for row in projection["networks"]] == ["inst.net.lan", "inst.net.wan"]
    assert [row["instance_id"] for row in projection["services"]] == ["svc-snmp"]


def test_ansible_projection_contains_hosts_from_l1_and_l4() -> None:
    projection = build_ansible_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["hosts"]] == [
        "lxc-grafana",
        "lxc-redis",
        "rtr-mk",
        "srv-gamayun",
        "srv-orangepi5",
    ]
    assert "inst.ethernet_cable.cat5e" not in [row["instance_id"] for row in projection["hosts"]]


def test_bootstrap_projection_selects_target_devices() -> None:
    projection = build_bootstrap_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["proxmox_nodes"]] == ["srv-gamayun"]
    assert [row["instance_id"] for row in projection["mikrotik_nodes"]] == ["rtr-mk"]
    assert [row["instance_id"] for row in projection["orangepi_nodes"]] == ["srv-orangepi5"]


def test_ansible_projection_accepts_wave3_lineage_fallback_refs() -> None:
    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-mk",
                    "instance": {
                        "materializes_object": "obj.mikrotik.chateau_lte7_ax",
                        "materializes_class": "class.network.router",
                    },
                }
            ],
            "lxc": [],
        }
    }
    projection = build_ansible_projection(payload)
    assert [row["instance_id"] for row in projection["hosts"]] == ["rtr-mk"]
    assert projection["hosts"][0]["object_ref"] == "obj.mikrotik.chateau_lte7_ax"


@pytest.mark.parametrize(
    "builder",
    [
        build_proxmox_projection,
        build_mikrotik_projection,
        build_ansible_projection,
        build_bootstrap_projection,
    ],
)
def test_projection_requires_instances_mapping(builder) -> None:
    with pytest.raises(ProjectionError, match="compiled_json.instances must be mapping/object"):
        builder({})


def test_projection_requires_required_fields() -> None:
    payload = _compiled_fixture()
    payload["instances"]["lxc"][0]["instance_id"] = ""
    with pytest.raises(
        ProjectionError,
        match=r"compiled_json\.instances\.lxc\[0\]\.instance_id must be non-empty string",
    ):
        build_proxmox_projection(payload)


def test_docs_projection_includes_service_dependencies() -> None:
    """Test that build_docs_projection extracts service dependencies with safe_id."""
    payload = {
        "instances": {
            "devices": [],
            "lxc": [],
            "services": [
                {
                    "instance_id": "svc-grafana@lxc.lxc-grafana",
                    "instance": {
                        "materializes_object": "obj.service.grafana",
                        "materializes_class": "class.service.visualization",
                    },
                    "instance_data": {
                        "dependencies": [
                            {"service_ref": "svc-prometheus@lxc.lxc-prometheus"},
                        ],
                    },
                },
                {
                    "instance_id": "svc-prometheus@lxc.lxc-prometheus",
                    "instance": {
                        "materializes_object": "obj.service.prometheus",
                        "materializes_class": "class.service.monitoring",
                    },
                    "instance_data": {},
                },
            ],
            "network": [],
        }
    }

    projection = build_docs_projection(payload)

    assert "service_dependencies" in projection
    deps = projection["service_dependencies"]
    assert len(deps) == 1
    assert deps[0]["service_id"] == "svc-grafana@lxc.lxc-grafana"
    assert deps[0]["depends_on"] == "svc-prometheus@lxc.lxc-prometheus"
    assert deps[0]["service_safe_id"] == "svc_grafana_lxc_lxc_grafana"
    assert deps[0]["depends_on_safe_id"] == "svc_prometheus_lxc_lxc_prometheus"


def test_docs_projection_includes_vms_with_host_ref() -> None:
    payload = {
        "instances": {
            "devices": [],
            "lxc": [],
            "services": [],
            "network": [],
            "vm": [
                {
                    "instance_id": "vm-analytics",
                    "instance": {
                        "materializes_object": "obj.proxmox.vm.debian12.analytics",
                        "materializes_class": "class.compute.workload.vm",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                }
            ],
        }
    }

    projection = build_docs_projection(payload)

    assert "vms" in projection
    assert len(projection["vms"]) == 1
    assert projection["vms"][0]["instance_id"] == "vm-analytics"
    assert projection["vms"][0]["host_ref"] == "srv-gamayun"


def test_safe_id_sanitizes_special_characters() -> None:
    """Test that safe_id replaces '.', '-', and '@' with '_'."""
    from plugins.generators.projections import _safe_id

    assert _safe_id("svc-grafana@lxc.lxc-grafana") == "svc_grafana_lxc_lxc_grafana"
    assert _safe_id("inst.vlan.servers") == "inst_vlan_servers"
    assert _safe_id("rtr-mikrotik-chateau") == "rtr_mikrotik_chateau"
    assert _safe_id("svc-redis") == "svc_redis"
    assert _safe_id("simple") == "simple"


def test_topology_projection_contains_cross_domain_nodes_and_edges() -> None:
    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "srv-gamayun",
                    "instance": {
                        "materializes_object": "obj.proxmox.ve",
                        "materializes_class": "class.compute.hypervisor.proxmox",
                    },
                    "layer": "L1",
                }
            ],
            "lxc": [
                {
                    "instance_id": "lxc-grafana",
                    "instance": {
                        "materializes_object": "obj.proxmox.lxc.debian12.base",
                        "materializes_class": "class.compute.workload.container",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                    "layer": "L1",
                }
            ],
            "vm": [
                {
                    "instance_id": "vm-analytics",
                    "instance": {
                        "materializes_object": "obj.proxmox.vm.debian12.analytics",
                        "materializes_class": "class.compute.workload.vm",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                    "layer": "L1",
                }
            ],
            "services": [
                {
                    "instance_id": "svc-grafana",
                    "instance": {
                        "materializes_object": "obj.service.grafana",
                        "materializes_class": "class.service.visualization",
                    },
                    "runtime": {"target_ref": "lxc-grafana", "network_binding_ref": "inst.vlan.servers"},
                    "instance_data": {"dependencies": [{"service_ref": "svc-prometheus"}]},
                    "layer": "L4",
                },
                {
                    "instance_id": "svc-prometheus",
                    "instance": {
                        "materializes_object": "obj.service.prometheus",
                        "materializes_class": "class.service.monitoring",
                    },
                    "runtime": {"target_ref": "lxc-grafana"},
                    "instance_data": {},
                    "layer": "L4",
                },
            ],
            "network": [
                {
                    "instance_id": "inst.trust_zone.servers",
                    "instance": {
                        "materializes_object": "obj.network.trust_zone.servers",
                        "materializes_class": "class.network.trust_zone",
                    },
                },
                {
                    "instance_id": "inst.vlan.servers",
                    "instance": {
                        "materializes_object": "obj.network.vlan.servers",
                        "materializes_class": "class.network.vlan",
                    },
                    "instance_data": {
                        "managed_by_ref": "srv-gamayun",
                        "trust_zone_ref": "inst.trust_zone.servers",
                    },
                },
            ],
            "pools": [
                {
                    "instance_id": "inst.pool.fast",
                    "instance": {
                        "materializes_object": "obj.storage.pool.fast",
                        "materializes_class": "class.storage.pool.zfs",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                }
            ],
            "data-assets": [
                {
                    "instance_id": "inst.data.asset.monitoring",
                    "instance": {
                        "materializes_object": "obj.storage.data_asset.monitoring",
                        "materializes_class": "class.storage.data_asset",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                }
            ],
            "operations": [
                {
                    "instance_id": "inst.backup.monitoring",
                    "instance": {
                        "materializes_object": "obj.ops.backup",
                        "materializes_class": "class.ops.backup_policy",
                    },
                    "instance_data": {
                        "target_ref": "svc-grafana",
                        "data_asset_ref": "inst.data.asset.monitoring",
                        "storage_ref": "inst.pool.fast",
                    },
                }
            ],
            "observability": [],
            "firewall": [],
            "power": [],
            "qos": [],
        }
    }

    projection = build_topology_projection(payload)
    nodes = projection["nodes"]
    edges = projection["edges"]
    assert any(row["instance_id"] == "srv-gamayun" and row["domain"] == "physical" for row in nodes)
    assert any(row["instance_id"] == "vm-analytics" and row["node_type"] == "vm" for row in nodes)
    assert any(row["instance_id"] == "svc-grafana" and row["domain"] == "services" for row in nodes)
    assert any(row["instance_id"] == "inst.vlan.servers" and row["domain"] == "network" for row in nodes)
    assert any(row["instance_id"] == "inst.pool.fast" and row["domain"] == "storage" for row in nodes)
    assert any(row["instance_id"] == "inst.backup.monitoring" and row["domain"] == "operations" for row in nodes)

    edge_tuples = {(row["source_id"], row["target_id"], row["edge_type"]) for row in edges}
    assert ("lxc-grafana", "srv-gamayun", "hosted_on") in edge_tuples
    assert ("vm-analytics", "srv-gamayun", "hosted_on") in edge_tuples
    assert ("svc-grafana", "svc-prometheus", "service_dependency") in edge_tuples
    assert ("svc-grafana", "lxc-grafana", "runtime_target") in edge_tuples
    assert ("svc-grafana", "inst.vlan.servers", "runtime_network_binding") in edge_tuples
    assert ("inst.vlan.servers", "srv-gamayun", "managed_by") in edge_tuples
    assert ("inst.backup.monitoring", "inst.pool.fast", "writes_to_storage") in edge_tuples


def test_topology_projection_materializes_external_nodes_for_edge_endpoints() -> None:
    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-main",
                    "instance": {
                        "materializes_object": "obj.network.router.main",
                        "materializes_class": "class.network.router",
                    },
                }
            ],
            "network": [
                {
                    "instance_id": "inst.data_link.wan",
                    "instance": {
                        "materializes_object": "obj.network.data_link.wan",
                        "materializes_class": "class.network.data_link",
                    },
                    "instance_data": {
                        "endpoint_a": {"device_ref": "rtr-main"},
                        "endpoint_b": {"external_ref": "external.internet"},
                    },
                }
            ],
            "services": [],
            "lxc": [],
            "vm": [],
            "pools": [],
            "data-assets": [],
            "operations": [],
            "observability": [],
            "firewall": [],
            "power": [],
            "qos": [],
        }
    }

    projection = build_topology_projection(payload)
    nodes = projection["nodes"]
    edges = projection["edges"]

    assert any(row["instance_id"] == "external.internet" and row["node_type"] == "external_ref" for row in nodes)
    assert ("rtr-main", "external.internet", "data_link") in {
        (row["source_id"], row["target_id"], row["edge_type"]) for row in edges
    }
