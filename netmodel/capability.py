"""Requirements, offers, and what counts as a witness — SEC-CAP.

The capability satisfaction contract turns capabilities from dispatch flags into
requirements-to-evidence contracts, and its central sentence is a chain of
inequalities: **declared support is not effective support is not evidence is not
permission**. Every shortcut this module refuses is a place where one of those
four was allowed to stand in for another.

Four such refusals are structural rather than checked:

*There is no fourth status.* `satisfied`, `unsatisfied`, `unverified` and nothing
else. "Not applicable" is a scope decision with its own type, so it cannot be
returned where a status is expected and read as a pass.

*Unknown is not unlimited.* A bound the offer does not state is `Unknown`, a
distinct value; it does not compare as satisfying anything. A `None` that
silently means "no limit" is how an unstated capacity becomes an infinite one.

*An empty loop is not proof.* Resolving a requirement against no applicable offer
is `unverified`, never `satisfied`. A loop that never executed its body returns
the same "no failures" as one that checked everything.

*A version label is not trust.* An offer carries the digest of its content, and a
witness records the digest it relied on. Two offers claiming one identity and
version with different bodies is an error, not a discovery-order preference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class CapabilityError(ValueError):
    """Raised when a requirement, offer or resolution is malformed."""


class EvidenceLevel(Enum):
    """What a claim rests on. Ordered: a claim needs its level or better."""

    DESIGN = 0
    OFFLINE_VALIDATED = 1
    BACKEND_TESTED = 2
    LIVE_OBSERVED = 3

    def satisfies(self, required: EvidenceLevel) -> bool:
        return self.value >= required.value


class Status(Enum):
    """The three outcomes, and there is no fourth."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class Unknown:
    """A value the offer does not state.

    Deliberately not `None`. `None` reads as "no limit" at every call site that
    forgets to check, and an unstated capacity that behaves as an infinite one is
    the most expensive kind of wrong.
    """

    reason: str = "not stated by the offer"

    def __bool__(self) -> bool:  # pragma: no cover - guarded by tests
        raise CapabilityError("an unknown value has no truth value; decide explicitly")


UNKNOWN = Unknown()


@dataclass(frozen=True, slots=True)
class Context:
    """Where a requirement applies, or where an offer holds."""

    family: str
    routing_domain: str
    hook: str

    def matches(self, other: Context) -> bool:
        return (self.family, self.routing_domain, self.hook) == (
            other.family,
            other.routing_domain,
            other.hook,
        )


@dataclass(frozen=True, slots=True)
class Requirement:
    """What the intent needs, traced to the obligation it serves."""

    requirement_id: str
    obligation: str
    capability_ref: str
    context: Context
    evidence_required: EvidenceLevel
    origin: str
    bounds: Mapping[str, int] = field(default_factory=dict)
    active: bool = True

    def __post_init__(self) -> None:
        for name in ("requirement_id", "obligation", "capability_ref", "origin"):
            if not str(getattr(self, name) or "").strip():
                raise CapabilityError(f"requirement is missing {name}")


@dataclass(frozen=True, slots=True)
class Offer:
    """What a component declares it supports, and under what conditions."""

    offer_id: str
    version: str
    content_digest: str
    capability_ref: str
    contexts: tuple[Context, ...]
    limits: Mapping[str, int | Unknown] = field(default_factory=dict)
    evidence: EvidenceLevel = EvidenceLevel.DESIGN

    def __post_init__(self) -> None:
        if not self.contexts:
            raise CapabilityError(f"{self.offer_id}: an offer with no context applies to nothing")
        if not str(self.content_digest or "").strip():
            raise CapabilityError(f"{self.offer_id}: an offer without a content digest is a label, not a contract")

    def applies_to(self, requirement: Requirement) -> bool:
        if self.capability_ref != requirement.capability_ref:
            return False
        return any(context.matches(requirement.context) for context in self.contexts)


@dataclass(frozen=True, slots=True)
class NotApplicable:
    """A justified scope decision. Deliberately not a `Status`.

    The contract is explicit that not-applicable is not a fourth way to pass a
    failed requirement, so it is a different type: it cannot be returned where a
    status is expected, and a caller has to handle it on purpose.
    """

    requirement_id: str
    justification: str

    def __post_init__(self) -> None:
        if not str(self.justification or "").strip():
            raise CapabilityError(f"{self.requirement_id}: scoping something out needs a justification")


@dataclass(frozen=True, slots=True)
class Resolution:
    """One requirement's verdict, with what it rests on and what it lacks."""

    requirement_id: str
    status: Status
    reason: str
    witnesses: tuple[tuple[str, str, str], ...] = ()  # (offer_id, version, digest)
    missing: tuple[str, ...] = ()

    @property
    def blocks_activation(self) -> bool:
        """Both non-satisfied statuses block; they differ in what to do next.

        `unsatisfied` is a demonstrated incompatibility with a source-level
        remedy. `unverified` means nobody knows. Neither may be reported as
        support, and collapsing them would lose the only actionable difference.
        """
        return self.status is not Status.SATISFIED


def _check_bounds(requirement: Requirement, offer: Offer) -> list[str]:
    """Bounds the offer fails or does not state."""
    problems: list[str] = []
    for name, needed in sorted(requirement.bounds.items()):
        if name not in offer.limits:
            problems.append(f"{name}: the offer states no limit")
            continue
        limit = offer.limits[name]
        if isinstance(limit, Unknown):
            problems.append(f"{name}: the offer states the limit as unknown ({limit.reason})")
            continue
        if limit < needed:
            problems.append(f"{name}: needs {needed}, offer provides {limit}")
    return problems


def resolve(requirement: Requirement, offers: Iterable[Offer]) -> Resolution:
    """Decide one requirement against the offers that apply to it.

    An offer that does not apply is not a failure and not a pass; it is simply
    not evidence. When nothing applies the answer is `unverified`, because "no
    applicable offer" and "no incompatibility found" are the same silence and
    only one of them means anything.
    """
    applicable = [offer for offer in offers if offer.applies_to(requirement)]
    if not applicable:
        return Resolution(
            requirement_id=requirement.requirement_id,
            status=Status.UNVERIFIED,
            reason=(
                f"no offer applies to {requirement.capability_ref} in "
                f"{requirement.context.family}/{requirement.context.routing_domain}/{requirement.context.hook}"
            ),
            missing=("an applicable offer",),
        )

    failures: list[str] = []
    unverified: list[str] = []
    witnesses: list[tuple[str, str, str]] = []

    for offer in sorted(applicable, key=lambda item: (item.offer_id, item.version)):
        problems = _check_bounds(requirement, offer)
        demonstrated = [item for item in problems if "unknown" not in item and "states no limit" not in item]
        if demonstrated:
            failures.extend(f"{offer.offer_id}: {item}" for item in demonstrated)
            continue
        if problems:
            unverified.extend(f"{offer.offer_id}: {item}" for item in problems)
            continue
        if not offer.evidence.satisfies(requirement.evidence_required):
            unverified.append(
                f"{offer.offer_id}: evidence is {offer.evidence.name.lower()}, "
                f"claim needs {requirement.evidence_required.name.lower()}"
            )
            continue
        witnesses.append((offer.offer_id, offer.version, offer.content_digest))

    if witnesses:
        return Resolution(
            requirement_id=requirement.requirement_id,
            status=Status.SATISFIED,
            reason=f"{len(witnesses)} witness(es) at or above {requirement.evidence_required.name.lower()}",
            witnesses=tuple(witnesses),
        )
    if failures:
        return Resolution(
            requirement_id=requirement.requirement_id,
            status=Status.UNSATISFIED,
            reason="; ".join(failures),
            missing=tuple(failures),
        )
    return Resolution(
        requirement_id=requirement.requirement_id,
        status=Status.UNVERIFIED,
        reason="; ".join(unverified) or "no adequate witness",
        missing=tuple(unverified),
    )


def check_offer_identity(offers: Iterable[Offer]) -> None:
    """Two bodies for one identity and version is an error.

    Not a preference resolved by discovery order: which one wins would then
    depend on the filesystem, and a contract that changes with directory listing
    order is not a contract.
    """
    seen: dict[tuple[str, str], str] = {}
    for offer in offers:
        key = (offer.offer_id, offer.version)
        previous = seen.get(key)
        if previous is not None and previous != offer.content_digest:
            raise CapabilityError(
                f"{offer.offer_id} {offer.version} has two different bodies "
                f"({previous} and {offer.content_digest}); a version label is not trust"
            )
        seen[key] = offer.content_digest


def coverage(requirements: Iterable[Requirement], offers: Iterable[Offer]) -> dict[str, Resolution]:
    """Resolve every active requirement. Inactive ones stay visible and unresolved.

    Disabled or planned intent remains in the model; it is not an activation
    requirement until selected, and it is not deleted either.
    """
    offers = list(offers)
    check_offer_identity(offers)
    return {
        requirement.requirement_id: resolve(requirement, offers) for requirement in requirements if requirement.active
    }


__all__ = [
    "UNKNOWN",
    "CapabilityError",
    "Context",
    "EvidenceLevel",
    "NotApplicable",
    "Offer",
    "Requirement",
    "Resolution",
    "Status",
    "Unknown",
    "check_offer_identity",
    "coverage",
    "resolve",
]
