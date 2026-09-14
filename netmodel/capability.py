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
    """What a claim rests on. A kind of evidence, **not a rung on a ladder**.

    The first version of this compared levels numerically, so `live_observed`
    discharged a requirement for `offline_validated`. The contract forbids that
    in one sentence - *a live packet sample does not replace independent model
    checks or all-path coverage* - and its section 4 table gives each claim its
    own required evidence rather than a threshold: offline validation wants
    compatible versioned offers and independent model checks, live observation
    wants a fresh preflight and a post-apply read-back. Neither answers the
    other's question, so neither substitutes for it.

    An offer therefore holds a *set* of levels: it can be design-reviewed and
    backend-tested without being either of the other two.
    """

    DESIGN = "design"
    OFFLINE_VALIDATED = "offline_validated"
    BACKEND_TESTED = "backend_tested"
    LIVE_OBSERVED = "live_observed"


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
    evidence: frozenset[EvidenceLevel] = field(default_factory=frozenset)
    mode: str | None = None
    requires: tuple[str, ...] = ()
    owner: str | None = None
    evidence_expiry: str | None = None
    mutating: bool = False
    delegated: bool = False

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
        if requirement.evidence_required not in offer.evidence:
            held = ", ".join(sorted(level.value for level in offer.evidence)) or "none"
            unverified.append(f"{offer.offer_id}: holds {held}, claim needs {requirement.evidence_required.value}")
            continue
        witnesses.append((offer.offer_id, offer.version, offer.content_digest))

    if witnesses:
        return Resolution(
            requirement_id=requirement.requirement_id,
            status=Status.SATISFIED,
            reason=f"{len(witnesses)} witness(es) holding {requirement.evidence_required.value}",
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
    "Conflict",
    "Context",
    "EvidenceLevel",
    "NotApplicable",
    "Offer",
    "Requirement",
    "Resolution",
    "Status",
    "Unknown",
    "check_joint_feasibility",
    "check_offer_identity",
    "coverage",
    "prerequisite_order",
    "resolve",
    "self_proving",
]


# --- composition: witnesses have to hold together, not one at a time ------------


@dataclass(frozen=True, slots=True)
class Conflict:
    """One reason a set of witnesses cannot be used in a single plan."""

    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"


def _stale(offer: Offer, as_of: str) -> bool:
    """Whether the offer's evidence has expired as of the given moment.

    `as_of` is required and has no default. Reading a clock here would put a
    timestamp inside a decision the contract wants deterministic, and would make
    the same inputs give different answers on different days. An offer with no
    expiry does not expire; that is a statement the offer makes, not an omission
    this function fills in.
    """
    if offer.evidence_expiry is None:
        return False
    return offer.evidence_expiry < as_of


def prerequisite_order(offers: Mapping[str, Offer]) -> list[str]:
    """A canonical order over the prerequisite graph, or an error.

    Bounded and acyclic, as the contract requires. A cycle is refused rather than
    broken at an arbitrary edge: which offer would then come first depends on
    iteration order, and a resolution that changes with dictionary ordering is
    not a resolution.
    """
    state: dict[str, int] = {}
    order: list[str] = []

    def visit(offer_id: str, path: tuple[str, ...]) -> None:
        if state.get(offer_id) == 2:
            return
        if state.get(offer_id) == 1:
            cycle = " -> ".join((*path[path.index(offer_id) :], offer_id))
            raise CapabilityError(f"prerequisite cycle: {cycle}")
        offer = offers.get(offer_id)
        if offer is None:
            raise CapabilityError(f"unresolved prerequisite: {offer_id} is required but not offered")
        state[offer_id] = 1
        for prerequisite in offer.requires:
            visit(prerequisite, (*path, offer_id))
        state[offer_id] = 2
        order.append(offer_id)

    for offer_id in sorted(offers):
        visit(offer_id, ())
    return order


def check_joint_feasibility(
    *,
    selection: Mapping[str, Offer],
    catalogue: Mapping[str, Offer],
    as_of: str,
    aggregate_bounds: Mapping[str, int] | None = None,
) -> list[Conflict]:
    """Whether these witnesses can be used together in one plan.

    The contract is explicit that effective support is *not* the union of
    capabilities on all devices: two offers can each be adequate and still be
    unusable together. So this checks the things that only appear in
    combination - mutually exclusive modes, shared capacity, one owner across
    requirements - plus the prerequisite graph and evidence freshness, which are
    per-offer but block the whole selection.
    """
    conflicts: list[Conflict] = []
    chosen = {offer.offer_id: offer for offer in selection.values()}

    modes = {offer.mode for offer in chosen.values() if offer.mode is not None}
    if len(modes) > 1:
        conflicts.append(Conflict("mode", f"witnesses require mutually exclusive modes {sorted(modes)}"))

    owners = {offer.owner for offer in chosen.values() if offer.owner is not None}
    if len(owners) > 1:
        conflicts.append(
            Conflict("ownership", f"witnesses are owned by {sorted(owners)}; one plan needs consistent ownership")
        )

    for offer in sorted(chosen.values(), key=lambda item: item.offer_id):
        if offer.mutating and not offer.delegated:
            conflicts.append(
                Conflict(
                    "delegation",
                    f"{offer.offer_id} mutates state without a delegated owner operation",
                )
            )
        if _stale(offer, as_of):
            conflicts.append(
                Conflict("freshness", f"{offer.offer_id} evidence expired at {offer.evidence_expiry}, now {as_of}")
            )

    reachable = dict(chosen)
    for offer in chosen.values():
        for prerequisite in offer.requires:
            candidate = catalogue.get(prerequisite)
            if candidate is not None:
                reachable[prerequisite] = candidate
    try:
        prerequisite_order(reachable)
    except CapabilityError as exc:
        conflicts.append(Conflict("prerequisite", str(exc)))

    if aggregate_bounds:
        for name, capacity in sorted(aggregate_bounds.items()):
            stated = [
                offer.limits[name]
                for offer in chosen.values()
                if name in offer.limits and not isinstance(offer.limits[name], Unknown)
            ]
            if stated and min(stated) < capacity:
                conflicts.append(
                    Conflict(
                        "capacity",
                        f"{name}: the plan needs {capacity}, the tightest witness provides {min(stated)}",
                    )
                )

    return conflicts


def self_proving(requirement: Requirement, offer: Offer) -> bool:
    """Whether an offer's only prerequisite is the property it is meant to prove.

    The contract names this directly: a strategy cannot use the property it is
    supposed to prove as its only prerequisite. It is circular in a way that is
    hard to see from either end alone - the offer looks like it has a dependency,
    and the dependency looks like it has a witness.
    """
    return tuple(offer.requires) == (requirement.capability_ref,)
