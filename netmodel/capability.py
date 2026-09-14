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
version with different bodies is an error, not a discovery-order preference. The
digest is **computed from the offer's semantic core** rather than accepted as a
string the caller supplies: a declared digest that nobody recomputes is a version
label with more characters, and two different offers could carry the same one.

The core is separated from the evidence annex on purpose. What the offer
*promises* - capability, contexts, limits, mode, prerequisites, the resource it
acts on - is its identity; what it *rests on* - evidence levels, expiry, owner,
delegation - is annexed. An offer whose evidence was re-validated yesterday is
the same offer; one whose limits changed is not.

*A shared constraint needs a shared subject.* Modes, owners and capacities were
once required to agree across the whole selection, which refuses perfectly good
independent components: two firewalls on different devices may run different
modes. They are scoped to a `resource` now, and an offer that states a mode or a
capacity without saying what it acts on leaves the constraint **unverified** -
not satisfied, and not conflicting either. "Which interface?" is a question
somebody has to answer.
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
    # What this offer acts on. Mode, ownership and capacity are properties of a
    # resource, not of a plan: two offers demanding exclusive modes conflict when
    # they drive the same thing and not otherwise. `None` is "unstated", which
    # makes those constraints unverified rather than satisfied.
    resource: str | None = None

    def __post_init__(self) -> None:
        if not self.contexts:
            raise CapabilityError(f"{self.offer_id}: an offer with no context applies to nothing")
        if not str(self.content_digest or "").strip():
            raise CapabilityError(f"{self.offer_id}: an offer without a content digest is a label, not a contract")

    def semantic_core(self) -> dict[str, object]:
        """What the offer promises. Its identity, and what the digest covers."""
        return {
            "offer_id": self.offer_id,
            "version": self.version,
            "capability_ref": self.capability_ref,
            "contexts": sorted(
                [context.family, context.routing_domain, context.hook] for context in self.contexts
            ),
            "limits": sorted(
                [name, "unknown" if isinstance(value, Unknown) else value]
                for name, value in self.limits.items()
            ),
            "mode": self.mode,
            "requires": sorted(self.requires),
            "resource": self.resource,
            "mutating": self.mutating,
        }

    def evidence_annex(self) -> dict[str, object]:
        """What the offer rests on. Re-validating evidence does not change identity."""
        return {
            "evidence": sorted(level.value for level in self.evidence),
            "evidence_expiry": self.evidence_expiry,
            "owner": self.owner,
            "delegated": self.delegated,
        }

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


def content_digest_of(core: Mapping[str, object]) -> str:
    """The canonical digest of a semantic core."""
    import hashlib
    import json

    serialized = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def declare(**fields) -> Offer:
    """An offer whose digest is computed from its own content.

    The constructor takes `content_digest` as an argument because a discovered
    offer arrives with one. This is how an offer is *authored*: the digest is
    derived, so it cannot disagree with the body it names.
    """
    fields.pop("content_digest", None)
    provisional = Offer(content_digest="sha256-pending", **fields)
    from dataclasses import replace

    return replace(provisional, content_digest=content_digest_of(provisional.semantic_core()))


def check_offer_identity(offers: Iterable[Offer]) -> None:
    """Every digest describes the offer carrying it, and one identity has one body.

    Two checks, and the first was missing. A declared digest nobody recomputes is
    a version label with more characters: two offers with different limits could
    carry the same string, and the duplicate check below would then see one body
    where there are two. So the digest is recomputed from the semantic core and
    compared.

    The second is the original: two bodies for one identity and version is an
    error, not a preference resolved by discovery order. Which one wins would
    depend on the filesystem, and a contract that changes with directory listing
    order is not a contract.
    """
    seen: dict[tuple[str, str], str] = {}
    for offer in offers:
        computed = content_digest_of(offer.semantic_core())
        if offer.content_digest != computed:
            raise CapabilityError(
                f"{offer.offer_id} {offer.version} declares {offer.content_digest} and its content "
                f"digests to {computed}; a digest nobody recomputes is a longer version label"
            )
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
    "Feasibility",
    "check_joint_feasibility",
    "check_offer_identity",
    "content_digest_of",
    "coverage",
    "declare",
    "expand",
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


@dataclass(frozen=True, slots=True)
class Feasibility:
    """Whether a selection holds together, with the three answers kept apart.

    The first version returned a list of conflicts, and an empty list was read as
    "these witnesses work together". It is not: it is "nothing I could check
    disagreed". An unstated capacity, a mode with no resource and a prerequisite
    nobody offered all produce no conflict and no knowledge, and reporting that
    as feasible is the empty-loop mistake in a different place.
    """

    conflicts: tuple[Conflict, ...] = ()
    unknowns: tuple[Conflict, ...] = ()
    examined: tuple[str, ...] = ()

    @property
    def status(self) -> Status:
        if self.conflicts:
            return Status.UNSATISFIED
        if self.unknowns:
            return Status.UNVERIFIED
        return Status.SATISFIED

    @property
    def blocks_activation(self) -> bool:
        return self.status is not Status.SATISFIED

    def __str__(self) -> str:
        parts = [f"{self.status.value} over {len(self.examined)} offer(s)"]
        parts.extend(str(item) for item in (*self.conflicts, *self.unknowns))
        return "; ".join(parts)


def expand(
    selection: Mapping[str, Offer], catalogue: Mapping[str, Offer]
) -> tuple[dict[str, Offer], list[str]]:
    """Every offer the selection depends on, to any depth, plus what is missing.

    One level was expanded before, so a chosen offer whose prerequisite depended
    in turn on an expired and undelegated one reported nothing: the third node
    was never looked at. Freshness and delegation are properties of what will
    actually run, and what will actually run is the closure.
    """
    resolved: dict[str, Offer] = {}
    missing: list[str] = []
    frontier = [offer.offer_id for offer in selection.values()]
    known = {offer.offer_id: offer for offer in selection.values()}

    while frontier:
        offer_id = frontier.pop()
        if offer_id in resolved:
            continue
        offer = known.get(offer_id) or catalogue.get(offer_id)
        if offer is None:
            missing.append(offer_id)
            continue
        resolved[offer_id] = offer
        frontier.extend(prerequisite for prerequisite in offer.requires if prerequisite not in resolved)

    return resolved, sorted(set(missing))


def _scoped_conflicts(offers: Mapping[str, Offer]) -> tuple[list[Conflict], list[Conflict]]:
    """Mode and ownership, per resource rather than across the whole plan."""
    conflicts: list[Conflict] = []
    unknowns: list[Conflict] = []

    by_resource: dict[str, list[Offer]] = {}
    for offer in sorted(offers.values(), key=lambda item: item.offer_id):
        if offer.resource is None:
            if offer.mode is not None or offer.owner is not None:
                unknowns.append(
                    Conflict(
                        "scope",
                        f"{offer.offer_id} states a mode or owner without naming the resource it acts "
                        "on, so no exclusivity can be decided for it",
                    )
                )
            continue
        by_resource.setdefault(offer.resource, []).append(offer)

    for resource, group in sorted(by_resource.items()):
        modes = {offer.mode for offer in group if offer.mode is not None}
        if len(modes) > 1:
            conflicts.append(
                Conflict("mode", f"{resource}: witnesses require mutually exclusive modes {sorted(modes)}")
            )
        owners = {offer.owner for offer in group if offer.owner is not None}
        if len(owners) > 1:
            conflicts.append(
                Conflict(
                    "ownership",
                    f"{resource}: owned by {sorted(owners)}; one resource needs consistent ownership",
                )
            )
    return conflicts, unknowns


def _capacity(
    offers: Mapping[str, Offer], aggregate_bounds: Mapping[str, int]
) -> tuple[list[Conflict], list[Conflict]]:
    """Shared capacity, per resource, with an unstated limit reported as unknown."""
    conflicts: list[Conflict] = []
    unknowns: list[Conflict] = []

    by_resource: dict[str | None, list[Offer]] = {}
    for offer in sorted(offers.values(), key=lambda item: item.offer_id):
        by_resource.setdefault(offer.resource, []).append(offer)

    for name, capacity in sorted(aggregate_bounds.items()):
        for resource, group in sorted(by_resource.items(), key=lambda item: item[0] or ""):
            where = resource or "an unnamed resource"
            stated: list[int] = []
            for offer in group:
                if name not in offer.limits:
                    unknowns.append(
                        Conflict("capacity", f"{where}: {offer.offer_id} states no {name} limit")
                    )
                    continue
                limit = offer.limits[name]
                if isinstance(limit, Unknown):
                    unknowns.append(
                        Conflict(
                            "capacity",
                            f"{where}: {offer.offer_id} states {name} as unknown ({limit.reason})",
                        )
                    )
                    continue
                stated.append(limit)
            if stated and min(stated) < capacity:
                conflicts.append(
                    Conflict(
                        "capacity",
                        f"{where}: {name} needs {capacity}, the tightest witness provides {min(stated)}",
                    )
                )
    return conflicts, unknowns


def check_joint_feasibility(
    *,
    selection: Mapping[str, Offer],
    catalogue: Mapping[str, Offer],
    as_of: str,
    aggregate_bounds: Mapping[str, int] | None = None,
) -> Feasibility:
    """Whether these witnesses can be used together in one plan.

    The contract is explicit that effective support is *not* the union of
    capabilities on all devices: two offers can each be adequate and still be
    unusable together. So this checks the things that only appear in
    combination - exclusive modes and ownership on one resource, shared capacity,
    the prerequisite graph and evidence freshness.

    Everything is checked over the **transitive closure** of the selection, not
    over the chosen offers alone. A witness whose prerequisite depends on an
    expired, undelegated one is not usable, and the expired node is two hops
    away.
    """
    conflicts: list[Conflict] = []
    unknowns: list[Conflict] = []

    chosen = {offer.offer_id: offer for offer in selection.values()}
    reachable, missing = expand(chosen, catalogue)
    for offer_id in missing:
        conflicts.append(
            Conflict("prerequisite", f"unresolved prerequisite: {offer_id} is required but not offered")
        )

    scoped, scope_unknowns = _scoped_conflicts(reachable)
    conflicts.extend(scoped)
    unknowns.extend(scope_unknowns)

    for offer in sorted(reachable.values(), key=lambda item: item.offer_id):
        role = "chosen" if offer.offer_id in chosen else "required by the selection"
        if offer.mutating and not offer.delegated:
            conflicts.append(
                Conflict(
                    "delegation",
                    f"{offer.offer_id} ({role}) mutates state without a delegated owner operation",
                )
            )
        if _stale(offer, as_of):
            conflicts.append(
                Conflict(
                    "freshness",
                    f"{offer.offer_id} ({role}) evidence expired at {offer.evidence_expiry}, now {as_of}",
                )
            )

    # Cycle detection over what was actually resolved. Edges to offers nobody
    # holds are pruned first: `expand` already reported each of those once, and
    # letting `prerequisite_order` raise on them again would report one missing
    # prerequisite as two conflicts.
    from dataclasses import replace

    graph = {
        offer_id: replace(
            offer, requires=tuple(item for item in offer.requires if item in reachable)
        )
        for offer_id, offer in reachable.items()
    }
    try:
        prerequisite_order(graph)
    except CapabilityError as exc:
        conflicts.append(Conflict("prerequisite", str(exc)))

    if aggregate_bounds:
        capacity_conflicts, capacity_unknowns = _capacity(reachable, aggregate_bounds)
        conflicts.extend(capacity_conflicts)
        unknowns.extend(capacity_unknowns)

    return Feasibility(
        conflicts=tuple(conflicts),
        unknowns=tuple(unknowns),
        examined=tuple(sorted(reachable)),
    )


def self_proving(requirement: Requirement, offer: Offer) -> bool:
    """Whether an offer's only prerequisite is the property it is meant to prove.

    The contract names this directly: a strategy cannot use the property it is
    supposed to prove as its only prerequisite. It is circular in a way that is
    hard to see from either end alone - the offer looks like it has a dependency,
    and the dependency looks like it has a witness.
    """
    return tuple(offer.requires) == (requirement.capability_ref,)
