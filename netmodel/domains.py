"""Address domains: the L2 entity that owns a prefix, a gateway and a zone.

ADR 0118 D2 generalizes the VLAN case: a VLAN is one kind of address domain, and
bridges, point-to-point links and overlays declare their own domain instead of a
synthetic VLAN. ADR 0110 section 1.5 fixes the direction of zone membership: the
network references the zone, never the other way round.

Two consequences are encoded here rather than described.

Addresses are a numeric offset from the network address, not a last-octet
substitution. The legacy helper returns `10.0.0.300` for a `/23` at offset 300 and
`10.0.0.2` for `10.0.0.128/25` at offset 2; both are wrong and the second is wrong
silently. Offsets outside the prefix raise instead of producing an address that
looks plausible.

The gateway belongs to the domain. It is not assumed to be offset 1 and it is
never copied from somewhere else, so a domain that declares no gateway has none.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Mapping

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class DomainError(ValueError):
    """Raised when a domain or an allocation cannot be resolved."""


@dataclass(frozen=True, slots=True)
class AddressDomain:
    """One addressable L2 domain.

    `kind` records what the domain is modeled as - a VLAN, a bridge, an overlay -
    because capability requirements differ per kind. It carries no authorization
    meaning: membership of a zone classifies, it does not permit.
    """

    domain_id: str
    kind: str
    prefix: IPNetwork | None = None
    gateway: IPAddress | None = None
    trust_zone_ref: str | None = None

    def resolve_host(self, host: int) -> IPAddress:
        """Return the address at `host` offsets from the network address."""
        if self.prefix is None:
            raise DomainError(f"{self.domain_id}: no prefix declared, cannot resolve host {host}")
        if isinstance(host, bool) or not isinstance(host, int):
            raise DomainError(f"{self.domain_id}: host offset must be an integer, got {host!r}")
        if host < 0:
            raise DomainError(f"{self.domain_id}: host offset must not be negative, got {host}")

        low, high = offset_range(self.prefix)
        if host < low or host > high:
            raise DomainError(
                f"{self.domain_id}: host offset {host} is not usable in {self.prefix} "
                f"(usable offsets {low}..{high})"
            )
        return self.prefix.network_address + host

    def contains(self, address: IPAddress | str) -> bool:
        if self.prefix is None:
            return False
        return ipaddress.ip_address(str(address)) in self.prefix


def offset_range(prefix: IPNetwork) -> tuple[int, int]:
    """The inclusive range of host offsets a prefix admits.

    Corrected 2026-09-11. The earlier version accepted any offset inside the
    prefix, which handed out the network address at offset 0 and the broadcast
    address at the top of an IPv4 subnet as if they were host addresses. Neither
    is assignable, and a model that derives an unusable address is worse than one
    that refuses, because the error surfaces on the device rather than in review.

    The two edge cases are real, not decoration: a /31 (RFC 3021) and a /127
    (RFC 6164) are point-to-point links where both addresses are hosts, and a
    /32 or /128 is a single host at offset 0.

    Computed, never enumerated: `list(prefix.hosts())` on an IPv6 /64 asks for
    2**64 addresses and does not return.
    """
    size = prefix.num_addresses
    if prefix.prefixlen == prefix.max_prefixlen:
        return (0, 0)
    if prefix.prefixlen == prefix.max_prefixlen - 1:
        return (0, 1)
    if prefix.version == 4:
        return (1, size - 2)
    return (1, size - 1)


def parse_prefix(value: str | None) -> IPNetwork | None:
    """Parse a declared CIDR. An absent prefix is valid; a malformed one is not."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise DomainError(f"malformed prefix {text!r}: {exc}") from exc


def parse_address(value: str | None) -> IPAddress | None:
    text = str(value or "").strip()
    if not text:
        return None
    # A declared gateway may carry a prefix length; the address is what matters.
    text = text.split("/", 1)[0]
    try:
        return ipaddress.ip_address(text)
    except ValueError as exc:
        raise DomainError(f"malformed address {text!r}: {exc}") from exc


def zone_membership(domains: Iterable[AddressDomain]) -> dict[str, list[str]]:
    """Map each zone to the domains that reference it.

    Only the domain's own declaration is consulted. A zone does not enumerate its
    members, so there is exactly one direction for this relation and exactly one
    place to change it. Output is sorted: ordering is never left to iteration.
    """
    members: dict[str, list[str]] = {}
    for domain in domains:
        zone = (domain.trust_zone_ref or "").strip()
        if not zone:
            continue
        members.setdefault(zone, []).append(domain.domain_id)
    return {zone: sorted(ids) for zone, ids in sorted(members.items())}


def zone_prefixes(domains: Iterable[AddressDomain]) -> dict[str, list[str]]:
    """Map each zone to the prefixes of its domains, deduplicated and sorted.

    A domain without a prefix contributes nothing; it is still a member of its
    zone, which matters for policy selectors that address the domain by name.
    """
    by_id: Mapping[str, AddressDomain] = {domain.domain_id: domain for domain in domains}
    result: dict[str, list[str]] = {}
    for zone, domain_ids in zone_membership(by_id.values()).items():
        prefixes = {str(by_id[d].prefix) for d in domain_ids if by_id[d].prefix is not None}
        result[zone] = sorted(prefixes)
    return result
