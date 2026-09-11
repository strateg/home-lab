#!/usr/bin/env python3
"""Concrete segment addressing belongs to the instance, not to the object.

Class defines the schema, object supplies reusable defaults, instance binds real
resources. A `vlan_id`, a `cidr` and a `gateway` name one concrete segment, so
they are instance data. ADR 0110 section 1.5 states this directly: its normative
example declares all three on `inst.vlan.servers_db` while extending
`obj.network.vlan.servers`, because one object serves many segments.

The project proved the point by itself. `obj.network.vlan.vpn_tunnel` is extended
by four instances - vpn_amnezia, vpn_exit, vpn_germany and vpn_sweden - each with
its own VLAN id and prefix. The object's own `vlan_id: 50` and
`cidr: 192.168.50.0/24` were reachable by none of them: an object cannot supply
four segments their own addressing. Leaving those values in place was a trap, as
a fifth VPN VLAN would have silently inherited a colliding prefix.

These checks keep the layering from drifting back. They are about where a value
is declared, not about which value it is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from yaml_loader import load_yaml_file

VLAN_OBJECTS = sorted((REPO_ROOT / "topology" / "object-modules" / "network").glob("obj.network.vlan.*.yaml"))
VLAN_INSTANCES = sorted(
    (REPO_ROOT / "projects" / "home-lab" / "topology" / "instances" / "network").glob("inst.vlan.*.yaml")
)

# Values that identify one concrete segment and therefore cannot be shared.
SEGMENT_FIELDS = ("vlan_id", "cidr", "gateway")


@pytest.mark.parametrize("path", VLAN_OBJECTS, ids=lambda p: p.stem)
def test_vlan_object_declares_no_concrete_segment_addressing(path: Path) -> None:
    properties = (load_yaml_file(path) or {}).get("properties") or {}

    leaked = [field for field in SEGMENT_FIELDS if field in properties]

    assert not leaked, (
        f"{path.name} declares {leaked} at object level. One object can serve several "
        f"segments, so concrete addressing belongs to each instance. Reusable defaults "
        f"such as mtu, dhcp_enabled and dns_servers stay here."
    )


@pytest.mark.parametrize("path", VLAN_INSTANCES, ids=lambda p: p.stem)
def test_vlan_instance_declares_its_own_segment_addressing(path: Path) -> None:
    data = load_yaml_file(path) or {}

    missing = [field for field in SEGMENT_FIELDS if data.get(field) is None]

    assert not missing, (
        f"{path.name} does not declare {missing}. A VLAN instance is one addressable "
        f"segment; inheriting its prefix from an object hides which segment it is and "
        f"breaks as soon as a second instance extends the same object."
    )


def test_vlan_objects_still_carry_their_reusable_defaults() -> None:
    """The move must not have emptied the objects of what they legitimately own."""
    for path in VLAN_OBJECTS:
        properties = (load_yaml_file(path) or {}).get("properties") or {}
        assert properties, f"{path.name} lost all properties; reusable defaults belong here"


def test_segment_addressing_is_unique_across_instances() -> None:
    """Two segments cannot share a VLAN id or a prefix.

    With the values on instances this is checkable at all; while they lived on
    objects, a shared object made the question meaningless.
    """
    seen_ids: dict[int, str] = {}
    seen_prefixes: dict[str, str] = {}

    for path in VLAN_INSTANCES:
        data = load_yaml_file(path) or {}
        vlan_id = data.get("vlan_id")
        cidr = str(data.get("cidr", "")).strip()

        assert vlan_id not in seen_ids, f"{path.stem} reuses vlan_id {vlan_id} of {seen_ids.get(vlan_id)}"
        assert cidr not in seen_prefixes, f"{path.stem} reuses prefix {cidr} of {seen_prefixes.get(cidr)}"
        seen_ids[vlan_id] = path.stem
        seen_prefixes[cidr] = path.stem
