"""Permits, guards and the algebra that decides what is authorized.

The accepted model says authorization comes from an explicit, bound, approved
permit and from nothing else. A network, an address, a route, a NAT rule, an open
listener and an established connection all fail to create one. This module is
where that claim stops being prose.

Two shapes exist in the baseline profile and no others:

* `permit` with `binding_only` activation - inert until a binding names a subject
  and a target, so a reusable template on its own grants nothing;
* `deny` with `scope_guard` activation - activated by the scope it is attached
  to, independent of any publication, and not bypassable by a narrower permit.

The authorized set is `A = (P and C) minus D`. Set subtraction defines the
meaning; it is not a licence to trim an author's mistake. A permit that overlaps
a mandatory guard is a conflict the author has to resolve, reported with a
concrete flow that both match, because "your permit overlaps a deny somewhere" is
not actionable.

The flow language is deliberately small: endpoint sets, a protocol, and a port
set. Anything it cannot express is refused rather than approximated, which is the
difference between an unsupported case and a silently wrong one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class PolicyError(ValueError):
    """Raised when a policy, binding or guard is malformed or in conflict."""


class Effect(Enum):
    PERMIT = "permit"
    DENY = "deny"


class Activation(Enum):
    BINDING_ONLY = "binding_only"
    SCOPE_GUARD = "scope_guard"


# The baseline profile admits exactly these pairings. Any other combination has
# no defined meaning, so it is refused rather than interpreted.
_ALLOWED_MODES = {
    (Effect.PERMIT, Activation.BINDING_ONLY),
    (Effect.DENY, Activation.SCOPE_GUARD),
}

# A placeholder is a parameter a binding fills, never a wildcard. It must resolve
# to a non-empty bounded set before it means anything.
BINDING_SOURCE = "{binding: source}"
BINDING_DESTINATION = "{binding: destination}"


@dataclass(frozen=True, slots=True)
class Flow:
    """A bounded set of flows: who, to whom, over what.

    Endpoints are opaque atoms - a network, a zone, an address domain, an
    attachment endpoint. The algebra never interprets them, so it cannot invent a
    containment relation it has not been told about.
    """

    sources: frozenset[str]
    destinations: frozenset[str]
    protocol: str
    ports: frozenset[int]

    def __post_init__(self) -> None:
        if not self.sources:
            raise PolicyError("flow has no source; an empty selector is an error, not 'any'")
        if not self.destinations:
            raise PolicyError("flow has no destination; an empty selector is an error, not 'any'")
        if not str(self.protocol or "").strip():
            raise PolicyError("flow has no protocol")
        if not self.ports:
            raise PolicyError("flow has no ports; a typed non-port constraint is a separate shape")

    def intersect(self, other: Flow) -> Flow | None:
        if self.protocol != other.protocol:
            return None
        sources = self.sources & other.sources
        destinations = self.destinations & other.destinations
        ports = self.ports & other.ports
        if not (sources and destinations and ports):
            return None
        return Flow(sources=sources, destinations=destinations, protocol=self.protocol, ports=ports)

    def witness(self) -> tuple[str, str, str, int]:
        """One concrete flow from this set, for a message an author can act on."""
        return (min(self.sources), min(self.destinations), self.protocol, min(self.ports))


@dataclass(frozen=True, slots=True)
class PolicyTemplate:
    """A reusable constraint. On its own it authorizes nothing."""

    policy_id: str
    effect: Effect
    activation: Activation
    direction: str
    source: str | frozenset[str]
    destination: str | frozenset[str]
    protocol: str
    ports: frozenset[int]
    owner: str
    rationale: str

    def __post_init__(self) -> None:
        if (self.effect, self.activation) not in _ALLOWED_MODES:
            raise PolicyError(
                f"{self.policy_id}: {self.effect.value}/{self.activation.value} is not a baseline mode; "
                "the baseline admits permit/binding_only and deny/scope_guard"
            )
        for field_name in ("direction", "owner", "rationale"):
            if not str(getattr(self, field_name) or "").strip():
                raise PolicyError(f"{self.policy_id}: {field_name} is required")
        if not self.ports:
            raise PolicyError(f"{self.policy_id}: ports must be bounded and non-empty")
        if self.effect is Effect.DENY:
            for side, value in (("source", self.source), ("destination", self.destination)):
                if isinstance(value, str):
                    raise PolicyError(
                        f"{self.policy_id}: a scope guard needs concrete {side} selectors, "
                        f"not the unbound parameter {value!r}"
                    )


@dataclass(frozen=True, slots=True)
class Binding:
    """What turns a template into a grant: a subject, a target, an approver."""

    binding_id: str
    policy_id: str
    sources: frozenset[str]
    destinations: frozenset[str]
    approved: bool = False

    def __post_init__(self) -> None:
        if not self.sources or not self.destinations:
            raise PolicyError(f"{self.binding_id}: a binding must name a non-empty source and destination")


@dataclass(frozen=True, slots=True)
class Grant:
    """An approved, bound permit: the only thing that authorizes a flow."""

    binding_id: str
    policy_id: str
    flow: Flow


@dataclass(frozen=True, slots=True)
class Conflict:
    """A permit and a guard that both match a concrete flow."""

    binding_id: str
    policy_id: str
    guard_id: str
    witness: tuple[str, str, str, int]

    def __str__(self) -> str:
        source, destination, protocol, port = self.witness
        return (
            f"binding {self.binding_id} (policy {self.policy_id}) overlaps mandatory deny {self.guard_id}: "
            f"{source} -> {destination} {protocol}/{port} matches both"
        )


def _resolve_side(
    declared: str | frozenset[str], supplied: frozenset[str], *, placeholder: str, policy_id: str
) -> frozenset[str]:
    if isinstance(declared, str):
        if declared != placeholder:
            raise PolicyError(f"{policy_id}: unknown selector parameter {declared!r}")
        return supplied
    resolved = declared & supplied
    if not resolved:
        raise PolicyError(
            f"{policy_id}: the binding does not intersect the template selector; "
            "an empty resolved set is an error, not a permissive default"
        )
    return resolved


def resolve_grant(template: PolicyTemplate, binding: Binding) -> Grant:
    """Bind a template to concrete endpoints.

    Refuses an unapproved binding: owner and rationale on the template are review
    material, not approval, and a candidate is not a grant.
    """
    if template.effect is not Effect.PERMIT:
        raise PolicyError(f"{template.policy_id}: only a permit can be bound into a grant")
    if template.policy_id != binding.policy_id:
        raise PolicyError(f"{binding.binding_id}: refers to {binding.policy_id}, not {template.policy_id}")
    if not binding.approved:
        raise PolicyError(f"{binding.binding_id}: not approved; an unapproved candidate never authorizes traffic")

    sources = _resolve_side(template.source, binding.sources, placeholder=BINDING_SOURCE, policy_id=template.policy_id)
    destinations = _resolve_side(
        template.destination, binding.destinations, placeholder=BINDING_DESTINATION, policy_id=template.policy_id
    )
    return Grant(
        binding_id=binding.binding_id,
        policy_id=template.policy_id,
        flow=Flow(sources=sources, destinations=destinations, protocol=template.protocol, ports=template.ports),
    )


def guard_flow(template: PolicyTemplate) -> Flow:
    if template.effect is not Effect.DENY:
        raise PolicyError(f"{template.policy_id}: not a guard")
    assert not isinstance(template.source, str) and not isinstance(template.destination, str)
    return Flow(
        sources=template.source,
        destinations=template.destination,
        protocol=template.protocol,
        ports=template.ports,
    )


def _guard_index(guards: Mapping[str, PolicyTemplate]) -> dict[tuple[str, str], set[str]]:
    """Guards keyed by protocol and by each source endpoint they name.

    An overlap needs the protocol to match and the source sets to intersect, so a
    guard that shares neither cannot conflict with a grant and does not need to
    be examined. Checking every pair instead costs grants x guards comparisons -
    320,000 for 800 grants against 400 guards - most of them decided by the first
    field.

    Endpoints are opaque atoms, which is what makes this index exact rather than
    a heuristic: two endpoint sets intersect only if they share a literal member,
    so a lookup by member misses nothing. The algebra never infers containment
    between endpoints, and this must not start.
    """
    index: dict[tuple[str, str], set[str]] = {}
    for guard_id, guard in guards.items():
        assert not isinstance(guard.source, str)
        for source in guard.source:
            index.setdefault((guard.protocol, source), set()).add(guard_id)
    return index


def find_conflicts(grants: Iterable[Grant], guards: Mapping[str, PolicyTemplate]) -> list[Conflict]:
    """Every permit that overlaps a mandatory deny, with a flow that shows it.

    Candidates come from the index; the verdict still comes from `intersect`, so
    the index narrows what is examined and never decides anything.
    """
    index = _guard_index(guards)
    conflicts: list[Conflict] = []

    for grant in grants:
        candidates: set[str] = set()
        for source in grant.flow.sources:
            candidates |= index.get((grant.flow.protocol, source), frozenset())

        for guard_id in sorted(candidates):
            overlap = grant.flow.intersect(guard_flow(guards[guard_id]))
            if overlap is not None:
                conflicts.append(
                    Conflict(
                        binding_id=grant.binding_id,
                        policy_id=grant.policy_id,
                        guard_id=guard_id,
                        witness=overlap.witness(),
                    )
                )
    return conflicts


@dataclass(frozen=True, slots=True)
class AuthorizedSet:
    """`A = (P and C) minus D`, and the grants that produced it."""

    flows: tuple[Flow, ...] = field(default_factory=tuple)

    def admits(self, source: str, destination: str, protocol: str, port: int) -> bool:
        return any(
            source in flow.sources
            and destination in flow.destinations
            and protocol == flow.protocol
            and port in flow.ports
            for flow in self.flows
        )


def authorize(grants: Iterable[Grant], guards: Mapping[str, PolicyTemplate]) -> AuthorizedSet:
    """Compute the authorized set, refusing to resolve an authoring conflict.

    A permit overlapping a mandatory deny is not trimmed to fit. Subtraction says
    what authorization means; it does not decide which of two contradictory
    statements the author meant.
    """
    grants = list(grants)
    conflicts = find_conflicts(grants, guards)
    if conflicts:
        raise PolicyError("; ".join(str(conflict) for conflict in conflicts))
    return AuthorizedSet(flows=tuple(grant.flow for grant in grants))
