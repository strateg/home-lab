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
from plugins.generators.projections import build_ansible_projection  # noqa: E402

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
                {"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"},
                {"instance_id": "srv-gamayun", "object_ref": "obj.proxmox.ve"},
                {"instance_id": "srv-orangepi5", "object_ref": "obj.orangepi.rk3588.debian"},
                {
                    "instance_id": "inst.ethernet_cable.cat5e",
                    "class_ref": "class.network.physical_link",
                    "object_ref": "obj.network.ethernet_cable",
                },
            ],
            "lxc": [
                {"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"},
                {"instance_id": "lxc-grafana", "object_ref": "obj.proxmox.lxc.debian12.base"},
            ],
            "network": [
                {"instance_id": "inst.net.lan", "object_ref": "obj.network.l2_segment"},
                {"instance_id": "inst.net.wan", "object_ref": "obj.network.l2_segment"},
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
