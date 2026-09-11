"""Checks for address resolution and its source map.

Gate G2 lists the cases these have to cover: boundaries, invalid types,
reservations, collisions, /24, /23, /25 and /30, inheritance, disabled refs, and
a source map - with no fallback to any, to a first attachment, or to a product
default. The last part is the important one and is checked as an absence: a
resolver that guesses when it cannot derive is how "any" enters a security model.
"""

from __future__ import annotations

import ipaddress

import pytest

from netmodel.domains import AddressDomain
from netmodel.resolve import (
    Layer,
    Origin,
    ResolutionError,
    resolve_attachment,
)

LAN = AddressDomain(
    domain_id="inst.vlan.lan",
    kind="vlan",
    prefix=ipaddress.ip_network("192.168.88.0/24"),
    gateway=ipaddress.ip_address("192.168.88.1"),
)
SHIFTED = AddressDomain(domain_id="inst.vlan.shifted", kind="vlan", prefix=ipaddress.ip_network("10.0.30.128/25"))
WIDE = AddressDomain(domain_id="inst.vlan.wide", kind="vlan", prefix=ipaddress.ip_network("10.0.30.0/23"))
POINT = AddressDomain(domain_id="inst.vlan.p2p", kind="vlan", prefix=ipaddress.ip_network("10.9.9.0/30"))
NO_PREFIX = AddressDomain(domain_id="inst.vlan.bare", kind="vlan")

DOMAINS = {domain.domain_id: domain for domain in (LAN, SHIFTED, WIDE, POINT, NO_PREFIX)}


def _authored(**values) -> Layer:
    return Layer(origin=Origin.AUTHORED, source_ref="inst.lxc.probe", values=values)


def _resolve(*layers: Layer, owner: str = "inst.lxc.probe", local_key: str = "primary"):
    return resolve_attachment(owner=owner, local_key=local_key, layers=layers, domains=DOMAINS)


# --- the offset is an offset ---------------------------------------------------


@pytest.mark.parametrize(
    ("domain_id", "host", "expected"),
    [
        ("inst.vlan.lan", 20, "192.168.88.20"),  # /24
        ("inst.vlan.wide", 5, "10.0.30.5"),  # /23, lower half
        ("inst.vlan.wide", 300, "10.0.31.44"),  # /23, upper half - unreachable by last-octet arithmetic
        ("inst.vlan.shifted", 10, "10.0.30.138"),  # shifted /25
        ("inst.vlan.p2p", 1, "10.9.9.1"),  # /30
        ("inst.vlan.p2p", 2, "10.9.9.2"),
    ],
)
def test_the_address_is_the_offset_from_the_network_address(domain_id: str, host: int, expected: str) -> None:
    resolved = _resolve(_authored(network_ref=domain_id, address={"allocation": "static", "host": host}))

    assert resolved.address is not None
    assert resolved.address.value == expected


def test_a_resolved_address_is_always_inside_its_own_network() -> None:
    """The property the legacy path breaks on every shifted subnet."""
    for domain in (LAN, SHIFTED, WIDE, POINT):
        assert domain.prefix is not None
        low = 1 if domain.prefix.prefixlen < domain.prefix.max_prefixlen - 1 else 0
        resolved = _resolve(_authored(network_ref=domain.domain_id, address={"allocation": "static", "host": low}))

        assert resolved.address is not None
        assert ipaddress.ip_address(resolved.address.value) in domain.prefix


@pytest.mark.parametrize(
    ("domain_id", "host"),
    [
        ("inst.vlan.lan", 0),  # network address
        ("inst.vlan.lan", 255),  # broadcast
        ("inst.vlan.lan", 256),  # past the end
        ("inst.vlan.p2p", 3),  # broadcast of a /30
        ("inst.vlan.shifted", 130),  # does not exist in a 128-address subnet
    ],
)
def test_an_offset_the_prefix_does_not_admit_is_refused(domain_id: str, host: int) -> None:
    with pytest.raises(ResolutionError, match="Usable offsets"):
        _resolve(_authored(network_ref=domain_id, address={"allocation": "static", "host": host}))


# --- refusal, never fallback ---------------------------------------------------


def test_an_unmodeled_network_is_refused_not_guessed() -> None:
    with pytest.raises(ResolutionError, match="not a modeled address domain"):
        _resolve(_authored(network_ref="inst.vlan.ghost"))


def test_no_network_ref_in_any_layer_is_refused() -> None:
    with pytest.raises(ResolutionError, match="nothing to resolve against"):
        _resolve(_authored(interface="eth0"))


def test_a_static_request_against_a_domain_with_no_prefix_is_refused() -> None:
    with pytest.raises(ResolutionError, match="declares no prefix"):
        _resolve(_authored(network_ref="inst.vlan.bare", address={"allocation": "static", "host": 5}))


def test_a_static_request_without_an_offset_is_refused() -> None:
    with pytest.raises(ResolutionError, match="needs a host offset"):
        _resolve(_authored(network_ref="inst.vlan.lan", address={"allocation": "static"}))


@pytest.mark.parametrize("intent", ["10.0.0.5", 20, ["static"]])
def test_an_address_that_is_not_an_object_is_refused(intent) -> None:
    with pytest.raises(ResolutionError, match="must be an object"):
        _resolve(_authored(network_ref="inst.vlan.lan", address=intent))


def test_a_dynamic_allocation_resolves_to_no_address() -> None:
    """Inventing one would put a value in the model that nothing can honour."""
    resolved = _resolve(_authored(network_ref="inst.vlan.lan", address={"allocation": "dynamic"}))

    assert resolved.address is None
    assert resolved.address_family is not None  # the family is still known


def test_an_attachment_without_an_address_block_resolves_to_no_address() -> None:
    resolved = _resolve(_authored(network_ref="inst.vlan.lan"))

    assert resolved.address is None


# --- the gateway belongs to the domain -----------------------------------------


def test_the_gateway_comes_from_the_domain() -> None:
    resolved = _resolve(_authored(network_ref="inst.vlan.lan"))

    assert resolved.gateway is not None
    assert resolved.gateway.value == "192.168.88.1"
    assert resolved.gateway.provenance.origin is Origin.DERIVED


def test_a_domain_with_no_gateway_yields_none_rather_than_the_first_address() -> None:
    """The legacy path defaulted to .1 unconditionally and put gateways outside
    their own network on every shifted subnet. Absent must stay absent."""
    resolved = _resolve(_authored(network_ref="inst.vlan.shifted"))

    assert resolved.gateway is None


# --- precedence and provenance --------------------------------------------------


def test_an_authored_value_overrides_an_object_default_and_says_so() -> None:
    resolved = _resolve(
        Layer(origin=Origin.OBJECT_DEFAULT, source_ref="obj.lxc.base", values={"interface": "eth0"}),
        _authored(network_ref="inst.vlan.lan", interface="eth1"),
    )

    interface = resolved.fields["interface"]
    assert interface.value == "eth1"
    assert interface.provenance.origin is Origin.AUTHORED
    assert [entry.origin for entry in interface.overridden] == [Origin.OBJECT_DEFAULT]


def test_an_object_default_overrides_a_host_default() -> None:
    resolved = _resolve(
        Layer(origin=Origin.HOST_DEFAULT, source_ref="@on:host.pve", values={"driver": "bridge"}),
        Layer(origin=Origin.OBJECT_DEFAULT, source_ref="obj.lxc.base", values={"driver": "macvlan"}),
        _authored(network_ref="inst.vlan.lan"),
    )

    driver = resolved.fields["driver"]
    assert driver.value == "macvlan"
    assert driver.provenance.origin is Origin.OBJECT_DEFAULT
    assert [entry.origin for entry in driver.overridden] == [Origin.HOST_DEFAULT]


def test_layer_order_in_the_argument_does_not_change_the_result() -> None:
    """Precedence is a property of the origin, not of the call."""
    host = Layer(origin=Origin.HOST_DEFAULT, source_ref="@on:host.pve", values={"driver": "bridge"})
    authored = _authored(network_ref="inst.vlan.lan", driver="macvlan")

    forward = resolve_attachment(owner="o", local_key="primary", layers=(host, authored), domains=DOMAINS)
    backward = resolve_attachment(owner="o", local_key="primary", layers=(authored, host), domains=DOMAINS)

    assert forward.fields["driver"].value == backward.fields["driver"].value == "macvlan"


def test_a_key_a_layer_does_not_mention_leaves_the_one_below_in_place() -> None:
    resolved = _resolve(
        Layer(origin=Origin.OBJECT_DEFAULT, source_ref="obj.lxc.base", values={"driver": "bridge"}),
        _authored(network_ref="inst.vlan.lan", interface="eth0"),
    )

    assert resolved.fields["driver"].value == "bridge"
    assert resolved.fields["driver"].provenance.origin is Origin.OBJECT_DEFAULT


def test_the_source_map_names_where_every_value_came_from() -> None:
    resolved = _resolve(
        Layer(origin=Origin.HOST_DEFAULT, source_ref="@on:host.pve", values={"driver": "bridge"}),
        _authored(network_ref="inst.vlan.lan", address={"allocation": "static", "host": 20}, interface="eth0"),
    )

    source_map = resolved.source_map()

    assert source_map["network_ref"] == "authored at inst.lxc.probe:network.attachments.primary.network_ref"
    assert source_map["driver"] == "host_default at @on:host.pve:network.attachments.primary.driver"
    assert source_map["address"] == (
        "derived from inst.vlan.lan (offset 20 from the network address of 192.168.88.0/24)"
    )
    assert source_map["gateway"] == "derived from inst.vlan.lan (declared on the address domain)"
    assert source_map["address_family"] == "derived from inst.vlan.lan (the version of the domain's prefix)"


def test_a_derived_value_never_claims_an_authored_origin() -> None:
    """The schema forbids authoring these; the resolver must not relabel them.

    If a derived value could carry an authored provenance, a reviewer reading the
    source map would go looking for a field that is not allowed to exist.
    """
    resolved = _resolve(_authored(network_ref="inst.vlan.lan", address={"allocation": "static", "host": 20}))

    for name in ("address", "gateway", "address_family"):
        value = getattr(resolved, name)
        if value is not None:
            assert value.provenance.origin is Origin.DERIVED


def test_the_address_request_is_kept_as_what_the_derivation_replaced() -> None:
    """A reviewer can see the authored intent beside the derived result."""
    resolved = _resolve(_authored(network_ref="inst.vlan.lan", address={"allocation": "static", "host": 20}))

    assert resolved.address is not None
    assert resolved.address.overridden[0].origin is Origin.AUTHORED
    assert "address" in resolved.address.overridden[0].field_path
