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


# Trust zones repeat the pattern: obj.network.trust_zone.vpn_tunnel is shared by
# two zones whose security classification differs, so classification belongs to
# each instance.
ZONE_OBJECTS = sorted((REPO_ROOT / "topology" / "object-modules" / "network").glob("obj.network.trust_zone.*.yaml"))
ZONE_INSTANCES = sorted(
    (REPO_ROOT / "projects" / "home-lab" / "topology" / "instances" / "network").glob("inst.trust_zone.*.yaml")
)
ZONE_FIELDS = ("name", "security_level", "isolated")


@pytest.mark.parametrize("path", ZONE_OBJECTS, ids=lambda p: p.stem)
def test_shared_zone_object_declares_no_classification(path: Path) -> None:
    """Only objects serving more than one zone are constrained.

    A single-instance object holding its zone's values is redundant rather than
    wrong; a shared one is wrong for every instance but at most one.
    """
    instances = [
        inst
        for inst in ZONE_INSTANCES
        if str((load_yaml_file(inst) or {}).get("@extends", "")) == (load_yaml_file(path) or {}).get("@object")
    ]
    if len(instances) < 2:
        pytest.skip(f"{path.stem} serves {len(instances)} instance(s); sharing is what makes this a defect")

    leaked = [field for field in ZONE_FIELDS if field in ((load_yaml_file(path) or {}).get("properties") or {})]

    assert not leaked, (
        f"{path.name} declares {leaked} while serving {len(instances)} zones "
        f"({', '.join(i.stem for i in instances)}). Classification feeds the policy "
        f"algebra, so it must be true for the zone that declares it."
    )


def _zone_instances_of(object_path: Path) -> list[Path]:
    object_id = (load_yaml_file(object_path) or {}).get("@object")
    return [
        inst for inst in ZONE_INSTANCES if str((load_yaml_file(inst) or {}).get("@extends", "")) == object_id
    ]


@pytest.mark.parametrize("path", ZONE_INSTANCES, ids=lambda p: p.stem)
def test_zone_sharing_an_object_classifies_itself(path: Path) -> None:
    """Required where the object is shared, not everywhere.

    A single-instance object that holds its zone's values is redundant, not
    wrong, and rewriting those zones would be churn with no defect behind it.
    Sharing is what makes inherited classification unsound.
    """
    extends = str((load_yaml_file(path) or {}).get("@extends", ""))
    siblings = [inst for inst in ZONE_INSTANCES if str((load_yaml_file(inst) or {}).get("@extends", "")) == extends]
    if len(siblings) < 2:
        pytest.skip(f"{path.stem} does not share its object")

    data = load_yaml_file(path) or {}
    missing = [field for field in ("security_level", "isolated") if data.get(field) is None]

    assert not missing, (
        f"{path.name} shares {extends} with {len(siblings) - 1} other zone(s) and still "
        f"inherits {missing}. A shared object cannot classify them both."
    )
