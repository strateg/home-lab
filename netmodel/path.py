"""Path coverage — SEC-PATH.

*Every feasible in-scope path crosses adequate verified gates or is demonstrably
disabled.* The counterexample is a same-bridge, direct, IPv6 or offload path that
bypasses the enforcer nobody thought to check.

The hard part is not the check, it is the inventory. `complete(R_g, Omega_g)` is
unfalsifiable while `Omega_g` is whatever the resolver enumerated: a resolver that
forgets a path class reports full coverage of the classes it remembered. So the
contract anchors the inventory externally and this module refuses to build one -
`required_cases` takes the scope and returns what must be covered, and the cases
actually demonstrated are supplied by the caller from evidence.

The lower bound is normative, not invented here: for any in-scope enforcement
subject, a case for each path class ADR 0118 D6 requires to be demonstrated or
verifiably disabled - L2, routed, host input and output, tunnel, direct backend
and offload - crossed with the address families and policy epochs in scope.

One editorial decision, stated because it is a departure from the literal text.
The contract lists IPv6 among the path classes *and* says the classes are crossed
with the address families. Taken literally that yields cases like "the IPv6 path
class under the IPv4 family", which mean nothing. IPv6 is carried by the family
axis, where it produces a real case for every class; listing it separately reads
as emphasis rather than a ninth class.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class PathError(ValueError):
    """Raised when a coverage claim is malformed."""


class PathClass(Enum):
    """The lower bound. A profile that adds paths adds cases; none may be removed."""

    L2_SAME_BRIDGE = "l2_same_bridge"
    ROUTED = "routed"
    HOST_INPUT = "host_input"
    HOST_OUTPUT = "host_output"
    TUNNEL = "tunnel"
    DIRECT_BACKEND = "direct_backend"
    OFFLOAD = "offload"


class CaseStatus(Enum):
    """What is known about one path case. Mirrors the capability statuses."""

    DEMONSTRATED = "demonstrated"
    DISABLED = "disabled"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class PathCase:
    """One path class, in one family, under one epoch, for one subject."""

    subject: str
    path_class: PathClass
    family: str
    epoch_id: str

    def key(self) -> tuple[str, str, str, str]:
        return (self.subject, self.path_class.value, self.family, self.epoch_id)

    def __str__(self) -> str:
        return f"{self.subject}/{self.path_class.value}/{self.family}@{self.epoch_id}"


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A path class scoped out, with the two things that make it reviewable.

    The contract: a path class absent from the inventory cannot be closed by a
    scope decision that names no owner and no reason. Both are required here, so
    an exclusion is something a person signed rather than a gap that acquired a
    label.
    """

    case: PathCase
    owner: str
    reason: str

    def __post_init__(self) -> None:
        for name in ("owner", "reason"):
            if not str(getattr(self, name) or "").strip():
                raise PathError(f"{self.case}: an exclusion without {name} closes nothing")


@dataclass(frozen=True, slots=True)
class Finding:
    """A case that is not covered, and what would cover it."""

    case: PathCase
    status: CaseStatus
    detail: str

    def __str__(self) -> str:
        return f"{self.case}: {self.status.value} - {self.detail}"


def required_cases(*, subjects: Iterable[str], families: Iterable[str], epochs: Iterable[str]) -> list[PathCase]:
    """The lower bound for a scope. Every class, family and epoch, crossed.

    This enumerates what must be *covered*; it does not enumerate what has been
    covered, and the distinction is the whole point. A resolver that produced
    both would be marking its own homework.
    """
    subjects = sorted(set(subjects))
    families = sorted(set(families))
    epochs = sorted(set(epochs))
    if not (subjects and families and epochs):
        raise PathError("a scope needs at least one subject, family and epoch to require anything")

    return [
        PathCase(subject=subject, path_class=path_class, family=family, epoch_id=epoch)
        for subject in subjects
        for path_class in PathClass
        for family in families
        for epoch in epochs
    ]


def coverage_gaps(
    *,
    required: Iterable[PathCase],
    demonstrated: Mapping[tuple[str, str, str, str], str],
    exclusions: Iterable[Exclusion] = (),
) -> list[Finding]:
    """Cases neither demonstrated nor properly excluded.

    `demonstrated` maps a case key to the evidence reference that demonstrated
    it. A key with an empty reference is not demonstrated: an entry that cites
    nothing is a claim, and the obligation is about evidence.

    Absence is `unverified` by construction, which is the sentence that makes the
    check falsifiable. Nothing here can conclude "covered" from silence.
    """
    excluded = {item.case.key(): item for item in exclusions}
    findings: list[Finding] = []

    for case in sorted(required, key=lambda item: item.key()):
        key = case.key()
        reference = demonstrated.get(key)
        if isinstance(reference, str) and reference.strip():
            continue
        if key in excluded:
            continue
        if key in demonstrated:
            findings.append(Finding(case, CaseStatus.UNVERIFIED, "an evidence entry that cites nothing is a claim"))
            continue
        findings.append(
            Finding(case, CaseStatus.UNVERIFIED, "no evidence and no signed exclusion; absent means unverified")
        )
    return findings


def unanchored_claims(
    *, required: Iterable[PathCase], demonstrated: Mapping[tuple[str, str, str, str], str]
) -> list[str]:
    """Evidence for cases the scope never required.

    Not harmless. It usually means the inventory and the evidence disagree about
    what the scope is, and the direction of the disagreement matters: a claim
    about a case nobody required is not coverage, and counting it would let an
    inventory shrink while the reported percentage rose.
    """
    wanted = {case.key() for case in required}
    return sorted(str(key) for key in demonstrated if key not in wanted)


__all__ = [
    "CaseStatus",
    "Exclusion",
    "Finding",
    "PathCase",
    "PathClass",
    "PathError",
    "coverage_gaps",
    "required_cases",
    "unanchored_claims",
]
