"""Unit checks for address domains.

The cases below include the three the legacy helper gets wrong. They are stated
as expectations of the target model, not as assertions about the legacy path,
which keeps its behaviour until its own migration.
"""

from __future__ import annotations

import ipaddress

import pytest

from netmodel.domains import AddressDomain, DomainError, parse_address, parse_prefix, zone_membership, zone_prefixes


def _domain(domain_id: str, cidr: str | None, *, zone: str | None = None, gateway: str | None = None) -> AddressDomain:
    return AddressDomain(
        domain_id=domain_id,
        kind="vlan",
        prefix=parse_prefix(cidr),
        gateway=parse_address(gateway),
        trust_zone_ref=zone,
    )


@pytest.mark.parametrize(
    ("cidr", "host", "expected"),
    [
        ("192.168.88.0/24", 210, "192.168.88.210"),
        ("10.0.100.0/24", 60, "10.0.100.60"),
        ("172.18.22.0/30", 2, "172.18.22.2"),
        # The legacy helper returns 10.0.0.300, which is not an address at all.
        ("10.0.0.0/23", 300, "10.0.1.44"),
        # The legacy helper returns 10.0.0.2, silently outside the declared prefix.
        ("10.0.0.128/25", 2, "10.0.0.130"),
    ],
)
def test_host_offset_is_numeric_from_the_network_address(cidr: str, host: int, expected: str) -> None:
    assert _domain("inst.vlan.probe", cidr).resolve_host(host) == ipaddress.ip_address(expected)


def test_offset_outside_the_prefix_is_refused() -> None:
    domain = _domain("inst.vlan.probe", "10.0.0.128/25")

    with pytest.raises(DomainError) as excinfo:
        domain.resolve_host(300)

    # The message must say what the usable range is, so the fix is locatable.
    assert "10.0.0.128/25" in str(excinfo.value)
    assert "0..127" in str(excinfo.value)


@pytest.mark.parametrize("host", [-1, True, "4", 2.0])
def test_non_offset_inputs_are_refused(host: object) -> None:
    with pytest.raises(DomainError):
        _domain("inst.vlan.probe", "10.0.0.0/24").resolve_host(host)  # type: ignore[arg-type]


def test_domain_without_a_prefix_cannot_resolve_a_host() -> None:
    with pytest.raises(DomainError):
        _domain("inst.bridge.probe", None).resolve_host(2)


def test_gateway_is_taken_from_the_domain_and_is_not_assumed() -> None:
    explicit = _domain("inst.vlan.probe", "10.0.0.0/24", gateway="10.0.0.254")
    absent = _domain("inst.vlan.bare", "10.0.0.0/24")

    assert explicit.gateway == ipaddress.ip_address("10.0.0.254")
    assert absent.gateway is None, "a domain that declares no gateway has none; offset 1 is not implied"


def test_malformed_declarations_are_refused_rather_than_ignored() -> None:
    with pytest.raises(DomainError):
        parse_prefix("10.0.0.0/33")
    with pytest.raises(DomainError):
        parse_address("10.0.0.300")


def test_zone_membership_is_declared_by_the_domain_and_sorted() -> None:
    domains = [
        _domain("inst.vlan.b", "10.0.2.0/24", zone="inst.trust_zone.servers"),
        _domain("inst.vlan.a", "10.0.1.0/24", zone="inst.trust_zone.servers"),
        _domain("inst.vlan.c", "10.0.3.0/24", zone="inst.trust_zone.user"),
        _domain("inst.vlan.orphan", "10.0.4.0/24"),
    ]

    membership = zone_membership(domains)

    assert membership == {
        "inst.trust_zone.servers": ["inst.vlan.a", "inst.vlan.b"],
        "inst.trust_zone.user": ["inst.vlan.c"],
    }
    assert "inst.vlan.orphan" not in str(membership), "a domain without a zone joins none"


def test_zone_prefixes_deduplicate_and_skip_prefixless_domains() -> None:
    domains = [
        _domain("inst.vlan.a", "10.0.1.0/24", zone="inst.trust_zone.servers"),
        _domain("inst.vlan.dup", "10.0.1.0/24", zone="inst.trust_zone.servers"),
        _domain("inst.bridge.noprefix", None, zone="inst.trust_zone.servers"),
    ]

    assert zone_prefixes(domains) == {"inst.trust_zone.servers": ["10.0.1.0/24"]}
    # The prefixless domain is still a member: selectors may address it by name.
    assert zone_membership(domains)["inst.trust_zone.servers"] == [
        "inst.bridge.noprefix",
        "inst.vlan.a",
        "inst.vlan.dup",
    ]
