"""Separate what is proposed from what is authorized, structurally.

Acceptance item A22: an unapproved candidate present in the model must produce no
permit in the authorized set, no rendered rule and no accepted flow, and rejecting
it must leave the pipeline green. The interesting word is *present*. It is easy to
satisfy A22 by refusing to represent candidates at all; the model is supposed to
hold them, so a reviewer can see what was proposed, and still be unable to act on
them.

The guarantee here is not "the code remembers to check `approved`". It is that a
candidate and a grant are different types, that only `promote` turns one into the
other, and that promotion needs an approver who is not the proposer. A function
that took an approval flag would put the two on one path with a boolean between
them, and a boolean is one typo from being true.

Rejecting a candidate is a normal outcome, not an error. What must still block is
a *missing* mandatory intent, which is a different fact and is not this module's
to soften: "candidate rejected" cannot stand in for "required flow absent".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from netmodel.policy import Binding, Grant, PolicyError, PolicyTemplate, resolve_grant


class ApprovalError(PolicyError):
    """Raised when a promotion is attempted without a valid, distinct approver."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """A proposed binding. It is not a `Binding`, and that is the point.

    There is no `approved` field. A candidate cannot be flipped into a grant by
    setting an attribute, because the attribute does not exist; it has to be
    promoted, and promotion is refused without an approver distinct from whoever
    proposed it.
    """

    candidate_id: str
    policy_id: str
    sources: frozenset[str]
    destinations: frozenset[str]
    proposed_by: str
    rationale: str

    def __post_init__(self) -> None:
        if not self.sources or not self.destinations:
            raise PolicyError(f"{self.candidate_id}: a candidate must name a non-empty source and destination")
        for name in ("proposed_by", "rationale"):
            if not str(getattr(self, name) or "").strip():
                raise PolicyError(
                    f"{self.candidate_id}: {name} is required; an unattributed proposal is not reviewable"
                )

    def describe(self) -> str:
        sources = ", ".join(sorted(self.sources))
        destinations = ", ".join(sorted(self.destinations))
        return f"{self.candidate_id}: {sources} -> {destinations} (proposed by {self.proposed_by}: {self.rationale})"


@dataclass
class Review:
    """The partition a human is asked to look at."""

    grants: list[Grant] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "grants": len(self.grants),
            "candidates": len(self.candidates),
            "rejected": len(self.rejected),
        }

    def render(self) -> str:
        lines = [f"grants: {len(self.grants)}", f"candidates awaiting review: {len(self.candidates)}"]
        for candidate in sorted(self.candidates, key=lambda item: item.candidate_id):
            lines.append(f"  propose {candidate.describe()}")
        for candidate_id, reason in sorted(self.rejected):
            lines.append(f"  reject  {candidate_id}: {reason}")
        return "\n".join(lines)


def promote(
    candidate: Candidate,
    template: PolicyTemplate,
    *,
    approved_by: str,
) -> Grant:
    """Turn a reviewed candidate into a grant. The only such path.

    The approver must not be the proposer. Self-approval is the failure mode this
    check exists for: it turns review into a formality that leaves a full audit
    trail of nobody having looked.
    """
    approver = str(approved_by or "").strip()
    if not approver:
        raise ApprovalError(f"{candidate.candidate_id}: promotion needs an approver")
    if approver == candidate.proposed_by:
        raise ApprovalError(f"{candidate.candidate_id}: {approver} proposed this and cannot also approve it")

    return resolve_grant(
        template,
        Binding(
            binding_id=candidate.candidate_id,
            policy_id=candidate.policy_id,
            sources=candidate.sources,
            destinations=candidate.destinations,
            approved=True,
        ),
    )


def partition(
    *,
    bindings: Iterable[Binding],
    templates: Mapping[str, PolicyTemplate],
    candidates: Iterable[Candidate] = (),
    rejected: Sequence[tuple[str, str]] = (),
) -> Review:
    """Split what authorizes from what is merely proposed.

    An unapproved `Binding` is not silently discarded: it is reported as a
    candidate, because a binding somebody wrote and nobody approved is exactly
    what a reviewer needs to see. It still authorizes nothing.
    """
    review = Review(candidates=list(candidates), rejected=list(rejected))

    for binding in bindings:
        template = templates.get(binding.policy_id)
        if template is None:
            raise PolicyError(f"{binding.binding_id}: no template {binding.policy_id}")
        if not binding.approved:
            review.candidates.append(
                Candidate(
                    candidate_id=binding.binding_id,
                    policy_id=binding.policy_id,
                    sources=binding.sources,
                    destinations=binding.destinations,
                    proposed_by=template.owner,
                    rationale=template.rationale,
                )
            )
            continue
        review.grants.append(resolve_grant(template, binding))

    return review


__all__ = ["ApprovalError", "Candidate", "Review", "partition", "promote"]
