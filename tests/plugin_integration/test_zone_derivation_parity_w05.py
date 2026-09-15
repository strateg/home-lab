#!/usr/bin/env python3
"""W05 characterization: the two zone/vlan derivations are not equivalent.

The ADR 0118/0119 plan requires the generator to stop recomputing zone membership
and consume the compiler's published channel instead (acceptance case A24), and it
requires that cutover to be a parity step with identical managed artifacts. W05
says to characterize both derivations first, because a divergence means a separate
behaviour change rather than a refactor.

They diverge. `security_matrix_compiler` builds a zone's `cidrs` purely from the
VLANs that reference the zone. `mikrotik/plugins/projections.py` additionally
appends `additional_networks` declared on the trust-zone instance. Two zones in
this project use that field, and the overlay CIDRs they contribute are present in
the rendered address lists today.

**Cutover performed 2026-09-14.** The decision recorded in the characterization
was the parity-preserving one: the core learned `additional_networks`, so the
rendered address lists are unchanged and zone membership is derived once. These
tests changed with it. What they pinned - "only the generator reads the field" -
was the signal that the cutover had become possible, and it has fired.

They now assert the other side: the compiler reads the field, the generator
consumes the channel rather than deriving, and the two derivations agree over the
real compiled model.

**The oracle moved here on 2026-09-15.** It used to live inside
`mikrotik/plugins/projections.py` as a dormant fallback the generator could still
reach, which is a second derivation whatever its comment says - A24 forbids that,
and W07 says the generator renders rather than decides. A parity oracle belongs
to the test that runs it, so `_oracle_zone_cidrs` below is an independent
re-derivation from the compiled model, written against the same authored fields
and deliberately not importing the compiler. The differential is unchanged in
what it proves: two implementations, one answer, checked against the artifact the
pipeline actually rendered.
"""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from yaml_loader import load_yaml_file

INSTANCES = REPO_ROOT / "projects" / "home-lab" / "topology" / "instances" / "network"
COMPILER = REPO_ROOT / "topology-tools" / "plugins" / "compilers" / "security_matrix_compiler.py"
PROJECTIONS = REPO_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "projections.py"

# Zones that declare overlay networks, and the CIDR each contributes.
OVERLAY_ZONES = {
    "inst.trust_zone.vpn_tunnel": "10.100.0.0/24",
    "inst.trust_zone.vpn_exit": "10.100.1.0/24",
}


# The oracle's own copy of what counts as an address domain. Separate from the
# compiler's list on purpose: an oracle that imported it could not disagree. A
# test below asserts the two agree.
ORACLE_ADDRESS_DOMAIN_CLASSES = ("class.network.vlan",)
ORACLE_TRUST_ZONE_CLASS = "class.network.trust_zone"


def _zone_instances() -> dict[str, dict]:
    return {path.stem: load_yaml_file(path) for path in sorted(INSTANCES.glob("inst.trust_zone.*.yaml"))}


def _oracle_object_ref(row: dict) -> str:
    block = row.get("instance")
    if isinstance(block, dict):
        for field in ("extends_object", "materializes_object"):
            value = block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


def _oracle_row_class(row: dict) -> str | None:
    class_ref = row.get("class_ref")
    if isinstance(class_ref, str) and class_ref:
        return class_ref
    payload = row.get("class")
    lineage = payload.get("lineage") if isinstance(payload, dict) else None
    return lineage[-1] if isinstance(lineage, list) and lineage else None


def _oracle_properties(object_ref: str, objects_map: dict) -> dict:
    obj = objects_map.get(object_ref) if isinstance(objects_map, dict) else None
    props = obj.get("properties") if isinstance(obj, dict) else None
    return props if isinstance(props, dict) else {}


def _oracle_zone_cidrs(compiled_json: dict) -> dict[str, list[str]]:
    """Re-derive each MikroTik zone's address list from the compiled model.

    An independent implementation of what `base.compiler.security_matrix` does,
    kept so the pipeline's answer has something to be checked against. It reads
    the same authored fields - `trust_zone_ref`, `cidr`, `additional_networks` -
    and imports neither the compiler nor the projection.
    """
    objects_map = compiled_json.get("objects") or {}
    rows = (compiled_json.get("instances") or {}).get("network") or []

    router_ids = {
        str(row.get("instance_id", "")).strip()
        for row in (compiled_json.get("instances") or {}).get("devices") or []
        if _oracle_object_ref(row).startswith("obj.mikrotik.")
    }

    zone_refs: list[str] = []
    for row in rows:
        if "security_matrix" not in _oracle_object_ref(row):
            continue
        inst = row.get("instance_data")
        if not isinstance(inst, dict):
            continue
        if str(inst.get("managed_by_ref", "")).strip() not in router_ids:
            continue
        declared = inst.get("zone_refs")
        if isinstance(declared, list):
            zone_refs = [str(item) for item in declared]

    vlan_zone: dict[str, str] = {}
    vlan_cidr: dict[str, str] = {}
    for row in rows:
        if _oracle_row_class(row) not in ORACLE_ADDRESS_DOMAIN_CLASSES:
            continue
        inst = row.get("instance_data")
        if not isinstance(inst, dict):
            continue
        instance_id = str(row.get("instance_id", "")).strip()
        zone_ref = str(inst.get("trust_zone_ref", "")).strip()
        cidr = str(inst.get("cidr", "")).strip()
        if not cidr:
            cidr = str(_oracle_properties(_oracle_object_ref(row), objects_map).get("cidr", "")).strip()
        if zone_ref:
            vlan_zone[instance_id] = zone_ref
        if cidr:
            vlan_cidr[instance_id] = cidr

    zone_vlans: dict[str, list[str]] = {}
    for vlan_ref, zone_ref in vlan_zone.items():
        zone_vlans.setdefault(zone_ref, []).append(vlan_ref)
    for vlans in zone_vlans.values():
        vlans.sort()

    derived: dict[str, list[str]] = {}
    for row in rows:
        if _oracle_row_class(row) != ORACLE_TRUST_ZONE_CLASS:
            continue
        zone_instance = str(row.get("instance_id", "")).strip()
        if zone_instance not in zone_refs:
            continue
        inst = row.get("instance_data")
        if not isinstance(inst, dict):
            inst = {}
        cidrs = [vlan_cidr[v] for v in zone_vlans.get(zone_instance, []) if v in vlan_cidr]
        for net in inst.get("additional_networks") or []:
            if isinstance(net, dict):
                cidr = str(net.get("cidr", "")).strip()
                if cidr and cidr not in cidrs:
                    cidrs.append(cidr)
        derived[zone_instance] = cidrs

    return derived


@pytest.mark.parametrize(("zone_id", "cidr"), sorted(OVERLAY_ZONES.items()))
def test_overlay_zones_declare_additional_networks(zone_id: str, cidr: str) -> None:
    """The authored input exists: this divergence is driven by real source data."""
    zone = _zone_instances()[zone_id]
    declared = zone.get("additional_networks")

    assert isinstance(declared, list) and declared, f"{zone_id} must declare additional_networks"
    assert cidr in [str(entry.get("cidr", "")).strip() for entry in declared if isinstance(entry, dict)]


def _reads_key(path, key: str) -> bool:
    """Whether the module actually reads `key`, rather than merely mentioning it.

    A substring test over the source cannot tell a lookup from a comment
    explaining why the lookup is absent - and it failed on exactly that, when the
    compiler gained a comment describing this divergence. Consumption is a
    subscript or a `.get`, so that is what is looked for.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            index = node.slice
            if isinstance(index, ast.Constant) and index.value == key:
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and argument.value == key:
                    return True
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant) and node.left.value == key:
            return True  # `"key" in mapping`
    return False


def test_both_sides_now_read_additional_networks() -> None:
    """Divergence 1, closed. The compiler was missing an authored input.

    The field is L2 source intent on a trust-zone instance, and zone derivation
    is the compiler's responsibility, so the generator was compensating for a
    gap in the core. Deleting the generator's copy would have removed two
    address-list entries covering the WireGuard admin and road-warrior networks -
    a reduction of matched sources, not a refactor.
    """
    assert _reads_key(COMPILER, "additional_networks"), "the core must derive the whole zone"
    assert "additional_networks" in pathlib.Path(__file__).read_text(encoding="utf-8"), (
        "the oracle must read the field too; if it stops, the differential agrees by "
        "not looking rather than by matching"
    )
    assert not _reads_key(PROJECTIONS, "additional_networks"), (
        "the projection is reading the field again - that is a second derivation at "
        "generate, which is what A24 and W07 both forbid"
    )


def test_the_generator_consumes_the_channel_rather_than_deriving() -> None:
    """A24: derived exactly once, by a core-level plugin.

    The manifest contract and the call are checked together. A generator that
    subscribed without passing the result through would still be deriving.
    """
    import ast

    manifest = load_yaml_file(REPO_ROOT / "topology/object-modules/mikrotik/plugins.yaml") or {}
    spec = next(item for item in manifest["plugins"] if item["id"] == "object.mikrotik.generator.terraform")
    consumed = {(item["key"], item["from_plugin"]) for item in spec.get("consumes", [])}

    assert ("security_matrices", "base.compiler.security_matrix") in consumed
    assert ("vlan_cidr_map", "base.compiler.security_matrix") in consumed

    generator = REPO_ROOT / "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py"
    tree = ast.parse(generator.read_text(encoding="utf-8"))
    passed = {
        keyword.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_mikrotik_projection"
        for keyword in node.keywords
    }

    assert {
        "security_matrices",
        "vlan_cidr_map",
    } <= passed, "the generator subscribes but does not hand the channel to the projection"


def test_both_paths_sort_for_determinism_now() -> None:
    """Divergence 2, closed - and it is what made the cutover byte-identical.

    Zone order followed row iteration on one path and nothing on the other. The
    compiler sorts zones as well as each zone's VLANs, which on this topology
    reproduces the generator's own output exactly.
    """
    compiler_src = COMPILER.read_text(encoding="utf-8")

    assert "zone_vlans[zone_ref].sort()" in compiler_src
    assert "for zone_ref in sorted(zone_refs):" in compiler_src


def test_the_two_derivations_agree_on_the_real_model() -> None:
    """The differential, over the rendered artifact and the local oracle.

    One side is what the pipeline actually produced from the compiler's channel;
    the other is the projection deriving zones for itself. They are separate
    implementations and they must agree - that is the whole reason the second one
    was kept rather than deleted.
    """
    import json
    import re

    effective = REPO_ROOT / "build" / "effective-topology.json"
    rendered = REPO_ROOT / "generated" / "home-lab" / "terraform" / "mikrotik" / "zone_firewall.tf"
    if not effective.exists() or not rendered.exists():
        pytest.skip("needs a compiled model and rendered artifacts; run compile-topology.py first")

    derived = _oracle_zone_cidrs(json.loads(effective.read_text(encoding="utf-8")))
    oracle: dict[str, list[str]] = {str(zone_id).rsplit(".", 1)[-1]: list(cidrs) for zone_id, cidrs in derived.items()}
    assert oracle, "the oracle derived no zones; this differential would prove nothing"

    pattern = (
        r'resource "routeros_ip_firewall_addr_list" "\w+" \{\s*list\s*=\s*"zone-([^"]+)"' r'\s*address\s*=\s*"([^"]+)"'
    )
    produced: dict[str, list[str]] = {}
    for zone, address in re.findall(pattern, rendered.read_text(encoding="utf-8")):
        produced.setdefault(zone, []).append(address)

    assert produced, "no address lists in the rendered artifact; this differential would prove nothing"
    for zone, addresses in sorted(produced.items()):
        assert addresses == oracle.get(zone), (
            f"zone '{zone}': the pipeline rendered {addresses} and the local derivation says " f"{oracle.get(zone)}"
        )


def test_the_overlay_cidrs_still_reach_the_rendered_artifact() -> None:
    """The measurement the characterization was written to protect."""
    rendered = REPO_ROOT / "generated" / "home-lab" / "terraform" / "mikrotik" / "zone_firewall.tf"
    if not rendered.exists():
        pytest.skip("needs rendered artifacts; run compile-topology.py first")

    text = rendered.read_text(encoding="utf-8")
    for cidr in OVERLAY_ZONES.values():
        assert cidr in text, f"{cidr} left the address lists; that is an exposure change, not a refactor"


def test_the_routing_policies_that_used_to_pass_the_selector_still_exist() -> None:
    """Divergence 3, and why closing it mattered.

    The projection selected address domains by a substring of the object ref, so
    five routing policies extending `obj.network.routing_policy.vpn_vlan` passed
    the filter. They were harmless only because they declare neither
    `trust_zone_ref` nor `cidr`, so both guards skipped them - one that ever
    gained a `cidr` would have entered the address lists through that path alone.

    The instances are still there. What changed is that a substring of an
    identifier no longer decides what a network is.
    """
    matched = [
        path.stem
        for path in sorted(INSTANCES.glob("inst.routing_policy.*.yaml"))
        if "vlan" in str(load_yaml_file(path).get("@extends", ""))
    ]

    assert matched, "expected routing policies extending a vlan-named object"


def test_both_derivations_select_address_domains_by_class() -> None:
    """Divergence 3, closed on both sides.

    The lists are separate copies on purpose - the projection is the parity
    oracle and has to be able to disagree with the core - so this asserts they
    agree rather than that one imports the other.
    """
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from plugins.compilers.security_matrix_compiler import SecurityMatrixCompiler

    assert tuple(ORACLE_ADDRESS_DOMAIN_CLASSES) == tuple(SecurityMatrixCompiler._ADDRESS_DOMAIN_CLASSES)
    assert ORACLE_TRUST_ZONE_CLASS == "class.network.trust_zone"

    source = PROJECTIONS.read_text(encoding="utf-8")
    assert '"vlan" not in net_object_ref' not in source, "the substring selector is back"
    assert '"trust_zone" not in net_object_ref' not in source


# --- selection by kind, not by identifier shape --------------------------------


def test_the_compiler_selects_by_class_not_by_instance_id_prefix() -> None:
    """The dependency that had to go before overlays can become domains.

    Reading `inst.vlan.` meant the compiler could only ever see networks whose
    author named them that way. An overlay network that is an address domain
    without being a VLAN was unrepresentable, which is *why* two trust zones
    carry `additional_networks` at all - the divergence is downstream of a
    selector, not of a disagreement about zones.

    Both selectors returned the same ten instances on the current topology, which
    is why this moved no artifact. The test asserts the prefix is gone rather than
    the result, because the result is identical by construction today.
    """
    import ast

    tree = ast.parse(COMPILER.read_text(encoding="utf-8"))

    prefixes = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]

    assert not [
        item for item in prefixes if item.startswith("inst.")
    ], f"the compiler still selects instances by identifier shape: {prefixes}"


def test_the_address_domain_set_is_named_once_and_can_grow() -> None:
    """One list to extend when an overlay network becomes declarable."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from plugins.compilers.security_matrix_compiler import SecurityMatrixCompiler

    assert "class.network.vlan" in SecurityMatrixCompiler._ADDRESS_DOMAIN_CLASSES


def test_the_class_of_a_row_is_read_from_either_stage_shape() -> None:
    """normalized_rows carry class_ref; effective-model rows carry a payload.

    Reading only one silently matches nothing in the other stage, which is the
    same mistake that made the validator's lineage walk find no declarations.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from plugins.compilers.security_matrix_compiler import SecurityMatrixCompiler

    assert SecurityMatrixCompiler._class_of({"class_ref": "class.network.vlan"}) == "class.network.vlan"
    assert SecurityMatrixCompiler._class_of({"class": {"lineage": ["class.network.vlan"]}}) == "class.network.vlan"
    assert SecurityMatrixCompiler._class_of({}) is None
