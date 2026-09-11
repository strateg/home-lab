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

These tests pin the current behaviour so a naive cutover fails loudly instead of
silently shrinking a firewall address list. They assert what is, not what should
be; the decision on where `additional_networks` belongs is a separate review.
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


def test_only_the_generator_side_consumes_additional_networks() -> None:
    """The asymmetry is in the code, not in a stale artifact.

    If the compiler ever learns `additional_networks`, this test fails and the
    cutover to a single derivation becomes possible. That is the intended signal.
    """
    assert "additional_networks" in PROJECTIONS.read_text(encoding="utf-8")
    assert "additional_networks" not in COMPILER.read_text(encoding="utf-8"), (
        "security_matrix_compiler now handles additional_networks; re-evaluate the "
        "A24 cutover and update this characterization"
    )


def test_compiler_sorts_zone_vlans_and_the_projection_does_not() -> None:
    """Second divergence: ordering determinism differs between the two paths."""
    compiler_src = COMPILER.read_text(encoding="utf-8")
    projection_src = PROJECTIONS.read_text(encoding="utf-8")

    assert "zone_vlans[zone_ref].sort()" in compiler_src
    assert "zone_vlans[zone_ref].sort()" not in projection_src


def test_projection_vlan_selector_matches_non_vlan_objects() -> None:
    """Third divergence, latent today.

    The compiler selects VLANs by instance id prefix; the projection selects them
    by a substring of the object ref. Five routing policies extend an object whose
    name contains "vlan" and therefore pass the projection's filter. They are
    harmless only because they carry neither `trust_zone_ref` nor `cidr`, so both
    guards skip them. This test records that the safety is incidental.
    """
    matched: list[str] = []
    for path in sorted(INSTANCES.glob("inst.routing_policy.*.yaml")):
        data = load_yaml_file(path)
        extends = str(data.get("@extends", ""))
        if "vlan" not in extends:
            continue
        matched.append(path.stem)
        assert "trust_zone_ref" not in data, f"{path.stem} would now pollute vlan_zone_map"
        assert "cidr" not in data, f"{path.stem} would now pollute vlan_cidr_map"

    assert matched, "expected routing policies extending a vlan-named object"
