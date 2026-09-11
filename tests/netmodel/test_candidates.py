"""Checks for candidate isolation — acceptance item A22.

A22: an unapproved candidate present in the model produces no permit in the
authorized set, no rendered rule and no accepted flow, and rejecting it leaves
the pipeline green.

The interesting word is *present*. Refusing to represent candidates at all would
satisfy the letter of A22 and defeat its purpose: the model holds them so a
reviewer can see what was proposed. So the tests that matter here are the
structural ones — that a candidate is a different type from a binding, that only
promotion crosses the gap, and that the authorized set is identical whether
candidates are in the model or not.
"""

from __future__ import annotations

import dataclasses

import pytest

from netmodel.candidates import ApprovalError, Candidate, Review, partition, promote
from netmodel.policy import (
    BINDING_DESTINATION,
    BINDING_SOURCE,
    Activation,
    Binding,
    Effect,
    PolicyError,
    PolicyTemplate,
    authorize,
)

LAN = frozenset({"inst.vlan.lan"})
MGMT = frozenset({"inst.vlan.management"})
GUEST = frozenset({"inst.vlan.guest"})


def template(policy_id: str = "policy.dns", *, ports=frozenset({53})) -> PolicyTemplate:
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=BINDING_SOURCE,
        destination=BINDING_DESTINATION,
        protocol="udp",
        ports=ports,
        owner="infra-admin",
        rationale="DNS for LAN clients",
    )


def candidate(candidate_id: str = "cand.dns", *, sources=LAN, proposed_by: str = "infra-admin") -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        policy_id="policy.dns",
        sources=sources,
        destinations=MGMT,
        proposed_by=proposed_by,
        rationale="observed traffic suggests this is needed",
    )


def binding(binding_id: str = "bind.dns", *, approved: bool) -> Binding:
    return Binding(binding_id=binding_id, policy_id="policy.dns", sources=LAN, destinations=MGMT, approved=approved)


# --- A22: presence changes nothing -------------------------------------------


def test_a_candidate_in_the_model_adds_nothing_to_the_authorized_set() -> None:
    templates = {"policy.dns": template()}
    approved = [binding(approved=True)]

    without = partition(bindings=approved, templates=templates)
    with_candidates = partition(
        bindings=approved, templates=templates, candidates=[candidate("cand.a"), candidate("cand.b")]
    )

    assert authorize(without.grants, {}).flows == authorize(with_candidates.grants, {}).flows
    assert len(with_candidates.candidates) == 2


def test_rejecting_a_candidate_leaves_the_authorized_set_untouched() -> None:
    """Rejection is a normal outcome and must not be an error."""
    templates = {"policy.dns": template()}
    review = partition(
        bindings=[binding(approved=True)],
        templates=templates,
        candidates=[candidate("cand.keep")],
        rejected=[("cand.drop", "the flow is already covered by an existing permit")],
    )

    assert authorize(review.grants, {}).admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)
    assert review.summary() == {"grants": 1, "candidates": 1, "rejected": 1}


def test_a_model_of_only_candidates_authorizes_nothing() -> None:
    review = partition(bindings=[], templates={"policy.dns": template()}, candidates=[candidate()])

    assert authorize(review.grants, {}).flows == ()
    assert not authorize(review.grants, {}).admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)


def test_an_unapproved_binding_becomes_a_candidate_rather_than_disappearing() -> None:
    """A binding somebody wrote and nobody approved is what a reviewer needs to see."""
    review = partition(bindings=[binding(approved=False)], templates={"policy.dns": template()})

    assert review.grants == []
    assert [item.candidate_id for item in review.candidates] == ["bind.dns"]


# --- the structural guarantee -------------------------------------------------


def test_a_candidate_has_no_approval_field_to_flip() -> None:
    """The guarantee is a type boundary, not a remembered check.

    A shared type with an `approved` boolean puts proposal and grant on one path
    with a flag between them, and a flag is one typo from being true.
    """
    names = {item.name for item in dataclasses.fields(Candidate)}

    assert "approved" not in names
    assert not (names & {"approved_by", "grant", "flow"})


def test_a_candidate_is_not_a_binding_and_cannot_be_used_as_one() -> None:
    with pytest.raises((TypeError, AttributeError, PolicyError)):
        authorize([candidate()], {})  # type: ignore[list-item]


def test_promotion_is_the_only_path_and_needs_an_approver() -> None:
    with pytest.raises(ApprovalError, match="needs an approver"):
        promote(candidate(), template(), approved_by="")


def test_the_proposer_cannot_approve_their_own_candidate() -> None:
    """Self-approval turns review into a formality with a full audit trail."""
    proposal = candidate(proposed_by="infra-admin")

    with pytest.raises(ApprovalError, match="cannot also approve"):
        promote(proposal, template(), approved_by="infra-admin")


def test_a_promoted_candidate_authorizes_exactly_what_it_proposed() -> None:
    grant = promote(candidate(), template(), approved_by="security-lead")

    authorized = authorize([grant], {})

    assert authorized.admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)
    assert not authorized.admits("inst.vlan.guest", "inst.vlan.management", "udp", 53)


def test_promotion_still_obeys_the_template_selector() -> None:
    """Approval does not widen a template; it only activates what it already says."""
    scoped = PolicyTemplate(
        policy_id="policy.dns",
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=LAN,
        destination=BINDING_DESTINATION,
        protocol="udp",
        ports=frozenset({53}),
        owner="o",
        rationale="r",
    )

    with pytest.raises(PolicyError, match="empty resolved set"):
        promote(candidate(sources=GUEST), scoped, approved_by="security-lead")


def test_a_candidate_must_name_a_proposer_and_a_reason() -> None:
    for missing in ("proposed_by", "rationale"):
        kwargs = {
            "candidate_id": "c",
            "policy_id": "policy.dns",
            "sources": LAN,
            "destinations": MGMT,
            "proposed_by": "someone",
            "rationale": "because",
            missing: "  ",
        }
        with pytest.raises(PolicyError, match=missing):
            Candidate(**kwargs)


def test_the_review_report_shows_what_was_proposed_and_what_was_dropped() -> None:
    review = partition(
        bindings=[binding(approved=True)],
        templates={"policy.dns": template()},
        candidates=[candidate("cand.a")],
        rejected=[("cand.b", "superseded")],
    )

    rendered = review.render()

    assert "grants: 1" in rendered
    assert "propose cand.a" in rendered
    assert "reject  cand.b: superseded" in rendered


def test_nothing_in_the_module_can_approve_by_itself() -> None:
    """Structural: no default approver, no auto-promotion, no metadata-as-approval.

    G2 names `metadata-as-approval` as a fallback that must not exist. The check
    is over the signature rather than the prose: `promote` takes a keyword-only
    approver with no default, so there is no call that approves implicitly.
    """
    import inspect

    signature = inspect.signature(promote)
    approver = signature.parameters["approved_by"]

    assert approver.kind is inspect.Parameter.KEYWORD_ONLY
    assert approver.default is inspect.Parameter.empty


# --- the half of A22 this module must not be mistaken for ----------------------


def test_this_module_cannot_express_a_required_flow() -> None:
    """ "Candidate rejected" must not be able to stand in for "required flow absent".

    G2 is explicit: rejecting an optional unapproved suggestion may leave the
    pipeline green, but missing mandatory intent must still block. Those are
    different facts about different things, and the way to keep them from being
    confused is that this module has no vocabulary for the second one.

    Availability is `SEC-AVAIL` and belongs to the plan compiler (`E7084`), which
    does not exist yet. Until it does, a green review here is evidence about
    proposals only, and this test is what stops that from quietly becoming a
    claim about required flows.
    """
    import dataclasses

    vocabulary = {item.name for item in dataclasses.fields(Review)} | {
        item.name for item in dataclasses.fields(Candidate)
    }
    forbidden = {"required", "mandatory", "availability", "must_admit", "obligation"}

    assert not (vocabulary & forbidden), (
        f"this module gained {sorted(vocabulary & forbidden)}; availability is SEC-AVAIL's, "
        "and merging the two lets a rejected proposal read as a satisfied requirement"
    )


def test_an_empty_review_is_not_a_statement_that_nothing_is_needed() -> None:
    """The summary reports what it partitioned, and claims nothing beyond it."""
    empty = partition(bindings=[], templates={})

    assert empty.summary() == {"grants": 0, "candidates": 0, "rejected": 0}
    assert authorize(empty.grants, {}).flows == ()
