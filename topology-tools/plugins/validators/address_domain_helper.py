"""Address domain resolution for the v2 network model (ADR 0118, gate G1).

A second implementation of what `netmodel.domains` already does. The duplication
is deliberate and the reason is structural: `netmodel` is a root package outside
framework distribution, so an external project consuming the framework would not
have it, and a plugin that imported it would fail there. A differential test runs
both over the same inputs and requires the same answer; without that test the two
copies drift and each keeps passing its own suite.

`host` is an offset from the network address, never a last octet. The distinction
only shows itself on a prefix that is not /24 - offset 300 in a /16 is a valid
address and a meaningless last octet - which is exactly why the model insists on
the offset form and why this module refuses to guess.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


class AddressDomainError(ValueError):
    """Raised when a prefix cannot be read as a network."""


@dataclass(frozen=True, slots=True)
class Prefix:
    """One parsed prefix: its family, its network, and what it can hold."""

    family: str
    network: ipaddress.IPv4Network | ipaddress.IPv6Network

    @property
    def offset_range(self) -> tuple[int, int]:
        """The inclusive range of host offsets this prefix admits.

        Four cases, and the two special ones are not decoration:

        * a single-address prefix (/32, /128) admits offset 0 and nothing else;
        * a two-address prefix (/31 per RFC 3021, /127 per RFC 6164) admits both
          addresses, because point-to-point links have no network or broadcast
          address to set aside;
        * IPv4 otherwise reserves the network address and the broadcast address,
          leaving 1..size-2;
        * IPv6 otherwise has no broadcast address and reserves only the
          subnet-router anycast at offset 0, leaving 1..size-1.

        This is computed, never enumerated. `list(network.hosts())` on an IPv6
        /64 asks for 2**64 addresses and does not return.
        """
        size = self.network.num_addresses
        max_len = self.network.max_prefixlen
        if self.network.prefixlen == max_len:
            return (0, 0)
        if self.network.prefixlen == max_len - 1:
            return (0, 1)
        if self.family == "ipv4":
            return (1, size - 2)
        return (1, size - 1)


def parse_prefix(cidr: str) -> Prefix:
    """Read a CIDR string, refusing anything ambiguous rather than guessing."""
    text = str(cidr or "").strip()
    if not text:
        raise AddressDomainError("empty prefix")
    try:
        network = ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise AddressDomainError(f"{text!r} is not a network prefix: {exc}") from exc
    return Prefix(family="ipv6" if network.version == 6 else "ipv4", network=network)


def family_of(cidr: str) -> str | None:
    """The address family of a prefix, or None when it cannot be read.

    None means "unknown", and a caller must not treat unknown as a match: two
    attachments whose families could not be determined are not thereby in the
    same family.
    """
    try:
        return parse_prefix(cidr).family
    except AddressDomainError:
        return None


def resolve_offset(cidr: str, host: int) -> str:
    """The address at `host` offsets from the network address.

    Raises rather than clamping. An offset outside the prefix is an authoring
    error with an answer the author has to give; silently returning the last
    usable address would hand them a working config that means something else.
    """
    prefix = parse_prefix(cidr)
    if not isinstance(host, int) or isinstance(host, bool):
        raise AddressDomainError(f"host offset must be an integer, got {host!r}")
    low, high = prefix.offset_range
    if host < low or host > high:
        raise AddressDomainError(f"offset {host} is outside {cidr}: usable offsets are {low}..{high}")
    return str(prefix.network.network_address + host)


def offset_is_usable(cidr: str, host: int) -> bool:
    try:
        resolve_offset(cidr, host)
        return True
    except AddressDomainError:
        return False


__all__ = [
    "AddressDomainError",
    "Prefix",
    "family_of",
    "offset_is_usable",
    "parse_prefix",
    "resolve_offset",
]
