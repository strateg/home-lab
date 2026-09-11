"""Resolve a v2 attachment into effective values, and say where each came from.

Gate G2 asks for a source map: not only what an address resolved to, but which
authored field, inherited default or derived rule produced it. Without that, a
review of a generated address has nothing to check it against, and the answer to
"why is this host on 10.0.99.20" is an afternoon of grep.

Two rules shape the module.

A derived value is never authored. `ip`, `gateway`, `zone`, `routing_domain` and
`address_family` are computed from the referenced domain, and the schema refuses
them on an attachment. Their provenance therefore names the domain and the rule,
not a source field - and a resolution that cannot derive a value refuses rather
than falling back, because a fallback is how "any" and "the first attachment" get
into a security model.

Precedence is explicit and recorded. A value authored on the instance wins over
an object default, which wins over a host default; the winner is what the
resolved record carries, and the losers are kept so a reviewer can see what was
overridden rather than inferring it from absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from netmodel.domains import AddressDomain, DomainError, offset_range


class ResolutionError(ValueError):
    """Raised when an attachment cannot be resolved and must not be guessed at."""


class Origin(Enum):
    """Where a resolved value came from, in precedence order."""

    AUTHORED = "authored"  # stated on the instance itself
    OBJECT_DEFAULT = "object_default"  # inherited from the object it extends
    HOST_DEFAULT = "host_default"  # an @on:host.X default (ADR 0107)
    DERIVED = "derived"  # computed; not authorable anywhere


# Precedence, lowest first. A later origin overrides an earlier one.
_PRECEDENCE = (Origin.HOST_DEFAULT, Origin.OBJECT_DEFAULT, Origin.AUTHORED)


@dataclass(frozen=True, slots=True)
class Provenance:
    """What produced a value, in terms a reviewer can go and look at."""

    origin: Origin
    source_ref: str
    field_path: str
    rule: str | None = None

    def __str__(self) -> str:
        if self.origin is Origin.DERIVED:
            return f"derived from {self.source_ref} ({self.rule})"
        return f"{self.origin.value} at {self.source_ref}:{self.field_path}"


@dataclass(frozen=True, slots=True)
class Resolved:
    """One effective value and its provenance, plus what it overrode."""

    value: Any
    provenance: Provenance
    overridden: tuple[Provenance, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedAttachment:
    """An attachment with every effective value traced to its origin."""

    owner: str
    local_key: str
    network_ref: Resolved
    address: Resolved | None
    gateway: Resolved | None
    address_family: Resolved | None
    fields: Mapping[str, Resolved] = field(default_factory=dict)

    def source_map(self) -> dict[str, str]:
        """A flat field -> provenance mapping, for review and for reports."""
        entries: dict[str, str] = {"network_ref": str(self.network_ref.provenance)}
        for name in ("address", "gateway", "address_family"):
            resolved = getattr(self, name)
            if resolved is not None:
                entries[name] = str(resolved.provenance)
        for name, resolved in sorted(self.fields.items()):
            entries[name] = str(resolved.provenance)
        return entries


@dataclass(frozen=True, slots=True)
class Layer:
    """One contributing source of values, at one origin."""

    origin: Origin
    source_ref: str
    values: Mapping[str, Any]


def _merge_layers(layers: tuple[Layer, ...], local_key: str) -> dict[str, Resolved]:
    """Apply precedence across layers, keeping what each one lost.

    Absence and an explicit null are not the same. A key a layer does not mention
    leaves the layer below it in place; `None` is not a value here, because a
    source that means "remove this" says `enabled: false` on the record.
    """
    ordered = sorted(layers, key=lambda layer: _PRECEDENCE.index(layer.origin))
    merged: dict[str, Resolved] = {}

    for layer in ordered:
        for name, value in layer.values.items():
            if value is None:
                continue
            provenance = Provenance(
                origin=layer.origin,
                source_ref=layer.source_ref,
                field_path=f"network.attachments.{local_key}.{name}",
            )
            previous = merged.get(name)
            overridden = (*previous.overridden, previous.provenance) if previous else ()
            merged[name] = Resolved(value=value, provenance=provenance, overridden=overridden)
    return merged


def resolve_attachment(
    *,
    owner: str,
    local_key: str,
    layers: tuple[Layer, ...],
    domains: Mapping[str, AddressDomain],
) -> ResolvedAttachment:
    """Resolve one attachment, refusing rather than guessing.

    Every refusal names the attachment and what was missing, because a resolver
    that returns a partial record hands the next stage something that looks
    complete.
    """
    merged = _merge_layers(layers, local_key)

    network_ref = merged.get("network_ref")
    if network_ref is None or not str(network_ref.value or "").strip():
        raise ResolutionError(f"{owner}.{local_key}: no network_ref in any layer; there is nothing to resolve against")

    domain = domains.get(str(network_ref.value))
    if domain is None:
        raise ResolutionError(f"{owner}.{local_key}: network_ref '{network_ref.value}' is not a modeled address domain")

    family = None
    if domain.prefix is not None:
        family = Resolved(
            value="ipv6" if domain.prefix.version == 6 else "ipv4",
            provenance=Provenance(
                origin=Origin.DERIVED,
                source_ref=domain.domain_id,
                field_path="address_family",
                rule="the version of the domain's prefix",
            ),
        )

    address = _resolve_address(owner=owner, local_key=local_key, merged=merged, domain=domain)
    gateway = _resolve_gateway(domain=domain)

    reserved = {"network_ref", "address"}
    fields = {name: resolved for name, resolved in merged.items() if name not in reserved}

    return ResolvedAttachment(
        owner=owner,
        local_key=local_key,
        network_ref=network_ref,
        address=address,
        gateway=gateway,
        address_family=family,
        fields=fields,
    )


def _resolve_address(
    *, owner: str, local_key: str, merged: Mapping[str, Resolved], domain: AddressDomain
) -> Resolved | None:
    """Derive the effective address from the domain and the requested offset.

    A dynamic or host-stack allocation resolves to no address here on purpose:
    the address exists only at runtime, and inventing one now would put a value
    into the model that nothing can honour.
    """
    request = merged.get("address")
    if request is None:
        return None
    intent = request.value
    if not isinstance(intent, Mapping):
        raise ResolutionError(f"{owner}.{local_key}: address must be an object, got {intent!r}")

    allocation = intent.get("allocation", "static")
    if allocation != "static":
        return None

    host = intent.get("host")
    if host is None:
        raise ResolutionError(f"{owner}.{local_key}: static allocation needs a host offset")
    if domain.prefix is None:
        raise ResolutionError(
            f"{owner}.{local_key}: domain '{domain.domain_id}' declares no prefix; "
            "there is nothing to resolve the offset against"
        )

    try:
        resolved = domain.resolve_host(host)
    except DomainError as exc:
        low, high = offset_range(domain.prefix)
        raise ResolutionError(
            f"{owner}.{local_key}: {exc}. Usable offsets in {domain.prefix} are {low}..{high}"
        ) from exc

    return Resolved(
        value=str(resolved),
        provenance=Provenance(
            origin=Origin.DERIVED,
            source_ref=domain.domain_id,
            field_path="address",
            rule=f"offset {host} from the network address of {domain.prefix}",
        ),
        overridden=(request.provenance, *request.overridden),
    )


def _resolve_gateway(*, domain: AddressDomain) -> Resolved | None:
    """The gateway is a property of the domain, never of an attachment.

    Absent means the domain does not declare one. It is not defaulted to the
    first usable address: the legacy path did exactly that, unconditionally, and
    produced gateways outside their own network on every shifted subnet.
    """
    if domain.gateway is None:
        return None
    return Resolved(
        value=str(domain.gateway),
        provenance=Provenance(
            origin=Origin.DERIVED,
            source_ref=domain.domain_id,
            field_path="gateway",
            rule="declared on the address domain",
        ),
    )


__all__ = [
    "Layer",
    "Origin",
    "Provenance",
    "Resolved",
    "ResolvedAttachment",
    "ResolutionError",
    "resolve_attachment",
]
