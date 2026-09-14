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
real compiled model. The projection keeps its local derivation as a parity
oracle, which is how this project detects a divergence rather than assuming its
absence.
"""

from __future__ import annotations

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


def _zone_instances() -> dict[str, dict]:
    return {path.stem: load_yaml_file(path) for path in sorted(INSTANCES.glob("inst.trust_zone.*.yaml"))}


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
    assert _reads_key(PROJECTIONS, "additional_networks"), (
        "the projection's local derivation is the parity oracle; if it goes, so does "
        "the ability to notice the two disagreeing"
    )


def test_the_generator_consumes_the_channel_rather_than_deriving() -> None:
    """A24: derived exactly once, by a core-level plugin.

    The manifest contract and the call are checked together. A generator that
    subscribed without passing the result through would still be deriving.
    """
    import ast

    manifest = load_yaml_file(REPO_ROOT / "topology/object-modules/mikrotik/plugins.yaml") or {}
    spec = next(
        item for item in manifest["plugins"] if item["id"] == "object.mikrotik.generator.terraform"
    )
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

    assert {"security_matrices", "vlan_cidr_map"} <= passed, (
        "the generator subscribes but does not hand the channel to the projection"
    )


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
    import importlib.util
    import re

    effective = REPO_ROOT / "build" / "effective-topology.json"
    rendered = REPO_ROOT / "generated" / "home-lab" / "terraform" / "mikrotik" / "zone_firewall.tf"
    if not effective.exists() or not rendered.exists():
        pytest.skip("needs a compiled model and rendered artifacts; run compile-topology.py first")

    import json

    spec = importlib.util.spec_from_file_location("w05_projections", PROJECTIONS)
    module = importlib.util.module_from_spec(spec)
    sys.modules["w05_projections"] = module
    spec.loader.exec_module(module)

    local = module.build_mikrotik_projection(json.loads(effective.read_text(encoding="utf-8")))
    oracle: dict[str, list[str]] = {
        str(zone_id).rsplit(".", 1)[-1]: list(values.get("cidrs") or [])
        for zone_id, values in (local["security_matrix"]["zones"] or {}).items()
    }

    pattern = (
        r'resource "routeros_ip_firewall_addr_list" "\w+" \{\s*list\s*=\s*"zone-([^"]+)"'
        r'\s*address\s*=\s*"([^"]+)"'
    )
    produced: dict[str, list[str]] = {}
    for zone, address in re.findall(pattern, rendered.read_text(encoding="utf-8")):
        produced.setdefault(zone, []).append(address)

    assert produced, "no address lists in the rendered artifact; this differential would prove nothing"
    for zone, addresses in sorted(produced.items()):
        assert addresses == oracle.get(zone), (
            f"zone '{zone}': the pipeline rendered {addresses} and the local derivation says "
            f"{oracle.get(zone)}"
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
    import importlib.util
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from plugins.compilers.security_matrix_compiler import SecurityMatrixCompiler

    spec = importlib.util.spec_from_file_location("w05_selector_projections", PROJECTIONS)
    module = importlib.util.module_from_spec(spec)
    _sys.modules["w05_selector_projections"] = module
    spec.loader.exec_module(module)

    assert tuple(module.ADDRESS_DOMAIN_CLASSES) == tuple(SecurityMatrixCompiler._ADDRESS_DOMAIN_CLASSES)
    assert module.TRUST_ZONE_CLASS == "class.network.trust_zone"

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

    assert not [item for item in prefixes if item.startswith("inst.")], (
        f"the compiler still selects instances by identifier shape: {prefixes}"
    )


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
    assert (
        SecurityMatrixCompiler._class_of({"class": {"lineage": ["class.network.vlan"]}}) == "class.network.vlan"
    )
    assert SecurityMatrixCompiler._class_of({}) is None
