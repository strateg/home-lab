"""The admission contract every strict backend consumer must use.

Nothing renders the security plan yet, and that is precisely why this exists now.
"No renderer" prevents application; it does not constitute a boundary, and a
boundary written after the first consumer arrives is written around it.

Five conditions, each refusing something that would otherwise look like progress:

1. `legacy_shadow` is refused **regardless of lowering completeness**. Lowering
   every override says the compiler represented what was written; it says nothing
   about whether anyone approved it.
2. Swapping `provenance` to `strict` is not enough. Admission needs approved
   intent and a passing independent check, both bound to the exact inputs.
3. A plan changed after checking loses admission - including when its own digest
   is recomputed to match. Admission compares a digest **it computes** against the
   one the verifier recorded; trusting the digest a payload presents would let a
   mutated plan certify itself.
4. Missing inputs, blocked scopes and incomplete checks forbid strict rendering.
5. A refusal never enables a legacy path. Falling back on refusal turns the
   boundary into a preference, and the unapproved plan runs anyway.

`availability_waiver` with an owner and a rationale makes a statement traceable.
It is not authority: whether that person may waive it, and whether the waiver was
agreed, belong to admission and are not properties of two filled-in strings.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

STRICT_PROVENANCE = "strict"


class AdmissionError(ValueError):
    """Raised when an admission decision is asked for with malformed inputs."""


@dataclass(frozen=True, slots=True)
class Admission:
    """The verdict, and why. A refusal is a normal outcome and names its reasons."""

    admitted: bool
    reasons: tuple[str, ...] = ()
    plan_digest: str = ""
    inputs_digest: str = ""

    # Never true. A refusal that permitted a fallback would be a preference, and
    # the unapproved plan would run anyway - which is the failure this whole
    # boundary exists to prevent. It is a field rather than a comment so a
    # consumer reading the verdict has to see it.
    legacy_fallback_permitted: bool = field(default=False, init=False)

    def __str__(self) -> str:
        if self.admitted:
            return f"admitted, plan {self.plan_digest[:19]}"
        return "refused: " + "; ".join(self.reasons)


def content_digest(payload: Any) -> str:
    """A digest of what is actually here, computed rather than accepted.

    Any `digest` field the payload carries is excluded from the input, because a
    payload that supplies its own identity can be edited to agree with itself.
    """

    def strip(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: strip(item) for key, item in sorted(value.items()) if key != "digest"}
        if isinstance(value, (list, tuple)):
            return [strip(item) for item in value]
        return value

    serialized = json.dumps(strip(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def evaluate(
    *,
    plan: Mapping[str, Any] | None,
    verification: Mapping[str, Any] | None,
    approved_intent: Mapping[str, Any] | None = None,
) -> Admission:
    """Decide admission from the plan, the verification record and approved intent.

    `verification` is what an independent check recorded: the digest of the plan
    it examined, and what it found. It is not taken from the plan.
    """
    reasons: list[str] = []

    if not isinstance(plan, Mapping):
        return Admission(admitted=False, reasons=("there is no plan to admit",))

    digest = content_digest(plan)

    provenance = str(plan.get("provenance") or "")
    if provenance != STRICT_PROVENANCE:
        reasons.append(
            f"provenance is {provenance or 'unset'!r}; a strict path admits only {STRICT_PROVENANCE!r}, "
            "and completeness of lowering does not substitute for approval"
        )

    if not isinstance(verification, Mapping):
        reasons.append("no independent verification record; an unchecked plan is not admissible")
    else:
        recorded = str(verification.get("plan_digest") or "")
        if not recorded:
            reasons.append("the verification record names no plan; it cannot be bound to this one")
        elif recorded != digest:
            reasons.append(
                f"the verified plan was {recorded[:19]} and this one is {digest[:19]}; "
                "a plan changed after checking is not the plan that was checked"
            )
        if verification.get("errors"):
            reasons.append(f"the independent check reported {verification['errors']} error(s)")
        if not verification.get("complete", False):
            reasons.append("the independent check did not complete; an unfinished check is not a pass")

    blocked = plan.get("blocked_scopes")
    if blocked:
        reasons.append(f"scopes blocked by unlowerable intent: {sorted(blocked)}")

    eligible = plan.get("strict_eligible")
    if not eligible:
        reasons.append("no scope is strict-eligible")

    if not isinstance(approved_intent, Mapping) or not approved_intent.get("approved"):
        reasons.append("no approved intent; authored overrides are not approved bound permits")

    inputs_digest = content_digest(approved_intent) if isinstance(approved_intent, Mapping) else ""

    return Admission(
        admitted=not reasons,
        reasons=tuple(reasons),
        plan_digest=digest,
        inputs_digest=inputs_digest,
    )


def strict_artifacts(paths: Sequence[Any]) -> list[str]:
    """Which of these paths exist. A refusal must leave none of them behind."""
    from pathlib import Path

    return [str(item) for item in paths if Path(item).exists()]


__all__ = [
    "STRICT_PROVENANCE",
    "Admission",
    "AdmissionError",
    "content_digest",
    "evaluate",
    "strict_artifacts",
]
