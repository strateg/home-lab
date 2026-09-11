"""Differential check: the model must express the real topology.

This is the forcing function of the reference package. Without it a clean model
drifts into fiction, staying internally consistent while losing contact with the
sources it is meant to replace. Here the model reads the actual compiled topology
and its output is compared with what the current pipeline renders.

The comparison target is the rendered address lists, because those are what the
firewall actually matches on. The expected delta is stated exactly rather than
tolerated: the model reproduces every zone's VLAN-derived prefixes, and differs
only by the two overlay CIDRs that today are declared on the zone instead of on a
domain. That delta is the W05 finding, and it is what the target model removes by
making the overlays address domains with their own `trust_zone_ref`.

If the delta ever grows, the model has lost a fact the pipeline still has.
If it shrinks to nothing, the overlays have been migrated and the A24 cutover has
become a genuine parity step.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from netmodel.domains import zone_prefixes
from netmodel.snapshot import DEFAULT_SNAPSHOT, load_snapshot, read_domains, read_zone_overlay_networks

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDERED = REPO_ROOT / "generated" / "home-lab" / "terraform" / "mikrotik" / "zone_firewall.tf"

ADDR_LIST_RE = re.compile(
    r'resource "routeros_ip_firewall_addr_list" "[^"]+" \{\s*\n'
    r'\s*list\s*=\s*"([^"]+)"\s*\n'
    r'\s*address\s*=\s*"([^"]+)"'
)

# Overlay networks a zone declares on itself. These are the only prefixes the
# model is expected to miss, and only until they become address domains.
EXPECTED_OVERLAY_DELTA = {
    "inst.trust_zone.vpn_exit": {"10.100.1.0/24"},
    "inst.trust_zone.vpn_tunnel": {"10.100.0.0/24"},
}


def _rendered_zone_prefixes() -> dict[str, set[str]]:
    rendered: dict[str, set[str]] = {}
    for list_name, address in ADDR_LIST_RE.findall(RENDERED.read_text(encoding="utf-8")):
        zone_id = f"inst.trust_zone.{list_name.removeprefix('zone-')}"
        rendered.setdefault(zone_id, set()).add(address)
    return rendered


@pytest.fixture(scope="module")
def model():
    if not DEFAULT_SNAPSHOT.exists():
        pytest.skip(f"{DEFAULT_SNAPSHOT} absent; run `task netmodel:snapshot` first")
    return load_snapshot()


def test_model_reads_every_addressable_domain(model) -> None:
    domains = read_domains(model)

    assert domains, "the model found no domains in the real topology"
    ids = {d.domain_id for d in domains}
    # Both kinds must be present: a VLAN-only reader would miss the container bridge.
    assert any(d.kind == "vlan" for d in domains)
    assert "inst.bridge.containers" in ids

    without_prefix = sorted(d.domain_id for d in domains if d.prefix is None)
    assert without_prefix == ["inst.bridge.vmbr0"], (
        "every domain except the prefixless bridge must resolve a prefix; a domain "
        "that lost its object-level default would show up here"
    )


def test_zone_prefixes_match_rendered_address_lists_except_the_overlay_delta(model) -> None:
    if not RENDERED.exists():
        pytest.skip(f"{RENDERED} absent")

    rendered = _rendered_zone_prefixes()
    derived = {zone: set(prefixes) for zone, prefixes in zone_prefixes(read_domains(model)).items()}

    assert set(derived) == set(rendered), "the model and the pipeline disagree on which zones exist"

    for zone in sorted(rendered):
        missing = rendered[zone] - derived[zone]
        extra = derived[zone] - rendered[zone]
        assert not extra, f"{zone}: model claims prefixes the pipeline does not render: {sorted(extra)}"
        assert missing == EXPECTED_OVERLAY_DELTA.get(zone, set()), (
            f"{zone}: unexpected delta against the rendered address list. "
            f"missing={sorted(missing)} expected={sorted(EXPECTED_OVERLAY_DELTA.get(zone, set()))}"
        )


def test_the_delta_is_exactly_what_the_zones_declare_as_overlays(model) -> None:
    """The gap has one cause, not several.

    Tying the delta to the declared source proves the model is not missing those
    prefixes for some other reason that happens to produce the same numbers.
    """
    overlays = {zone: set(cidrs) for zone, cidrs in read_zone_overlay_networks(model).items()}

    assert overlays == EXPECTED_OVERLAY_DELTA


def test_migrating_the_overlays_would_close_the_delta(model) -> None:
    """Parity proof for the W05 decision, computed rather than asserted.

    Modelling each overlay as a domain that declares the same zone yields exactly
    the rendered set. This is why moving them is a parity change and not an
    exposure change.
    """
    if not RENDERED.exists():
        pytest.skip(f"{RENDERED} absent")

    rendered = _rendered_zone_prefixes()
    derived = {zone: set(prefixes) for zone, prefixes in zone_prefixes(read_domains(model)).items()}

    for zone, overlay_cidrs in read_zone_overlay_networks(model).items():
        derived[zone] |= set(overlay_cidrs)

    assert derived == rendered


# --- address resolution against the live topology -----------------------------


def test_the_strict_resolver_reproduces_every_live_address(model) -> None:
    """The forcing function for W04.

    Every address domain in the topology is an unshifted /24, where last-octet
    arithmetic and offset arithmetic agree. The compiler's derivation and the
    strict resolver must therefore produce identical addresses today - and if they
    do not, one of them is wrong about a source that is currently deployed, which
    is worth knowing before anything is migrated.

    This is not a test of the legacy path's correctness. It is a test that the
    replacement does not silently change a live address while the two agree.
    """
    import ipaddress

    from netmodel.domains import AddressDomain
    from netmodel.resolve import Layer, Origin, resolve_attachment

    domains = {domain.domain_id: domain for domain in read_domains(model)}
    assert domains, "no address domains in the snapshot"

    compared = 0
    for group, rows in model.get("instances", {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            data = row.get("instance_data")
            network = data.get("network") if isinstance(data, dict) else None
            if not isinstance(network, dict):
                continue

            # The compiler writes its derived values under a leading underscore.
            # Reading the wrong key makes this test pass by skipping everything,
            # which is what the `compared` guard below exists to catch.
            rendered = network.get("_resolved_ip") or network.get("ip")
            network_ref = network.get("vlan_ref") or network.get("bridge_ref") or network.get("network_ref")
            host = network.get("host")
            if not (isinstance(rendered, str) and isinstance(network_ref, str)):
                continue
            if not isinstance(host, int) or isinstance(host, bool):
                continue
            if network_ref not in domains:
                continue

            resolved = resolve_attachment(
                owner=row.get("instance_id", "?"),
                local_key="primary",
                layers=(
                    Layer(
                        origin=Origin.AUTHORED,
                        source_ref=row.get("instance_id", "?"),
                        values={"network_ref": network_ref, "address": {"allocation": "static", "host": host}},
                    ),
                ),
                domains=domains,
            )

            assert resolved.address is not None
            expected = rendered.split("/")[0]
            assert resolved.address.value == expected, (
                f"{row.get('instance_id')}: pipeline rendered {expected}, "
                f"strict resolver derives {resolved.address.value} "
                f"for host {host} in {domains[network_ref].prefix}"
            )
            assert ipaddress.ip_address(resolved.address.value) in domains[network_ref].prefix

            rendered_gateway = network.get("_resolved_gateway")
            if isinstance(rendered_gateway, str) and domains[network_ref].gateway is not None:
                assert resolved.gateway is not None
                assert resolved.gateway.value == rendered_gateway

            compared += 1

    assert compared >= 10, f"only {compared} live addresses compared; the differential is not exercising anything"
