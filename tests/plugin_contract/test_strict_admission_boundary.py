#!/usr/bin/env python3
"""The strict admission boundary, and the control that keeps it honest.

Nothing renders the security plan yet. That prevents application; it is not a
boundary, and a boundary written after the first consumer arrives is written
around it.

Two things shape these tests.

**A positive control.** An implementation that refuses everything passes every
negative test ever written. So a purpose-built strict fixture must be *admitted*,
and it is the first test here rather than an afterthought.

**Absence of artifacts, not absence of a return value.** Refusal is checked by
looking at what the pipeline left on disk, because a function that says no while
something else writes the file is exactly the failure this guards.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.validators.strict_admission import (  # noqa: E402
    CHECKED_OBLIGATIONS,
    PASS,
    admitted_projection,
    RECORD_VERSION,
    STRICT_PROVENANCE,
    Admission,
    applicable_obligations,
    content_digest,
    evaluate,
    strict_artifacts,
)

# The identity of the intent the verifier checked. The approval names the same
# one; that equality is the link the 2026-09-14 review found missing, where an
# approval issued for an unrelated scope admitted this plan because `approved`
# was read for its truthiness alone.
INTENT_DIGEST = "sha256-" + "1" * 64


def strict_plan(**overrides) -> dict:
    """A plan that should be admitted. The control for every refusal below."""
    plan = {
        "schema_version": 1,
        "provenance": STRICT_PROVENANCE,
        "scopes": ["scope.a"],
        "lowering_complete": ["scope.a"],
        "strict_eligible": ["scope.a"],
        "blocked_scopes": [],
        "unlowerable": [],
        "rules": [
            {
                "origin": "binding:web",
                "effect": "permit",
                "terminal": False,
                "scope": "scope.a",
                "sources": ["z.a"],
                "destinations": ["z.b"],
                "transport": {"kind": "ports", "protocol": "tcp", "ports": [443]},
                "position": 0,
            },
            {
                "origin": "plan:terminal-default-deny",
                "effect": "deny",
                "terminal": True,
                "scope": "scope.a",
                "sources": [],
                "destinations": [],
                "transport": {"kind": "any"},
                "position": 1,
            },
        ],
        "digest": "sha256-whatever-the-payload-claims",
    }
    plan.update(overrides)
    return plan


def verification_for(plan: dict, **overrides) -> dict:
    """A complete record: every field the contract requires, and a status per obligation.

    `complete: True` used to be the whole of it, and it meant only that the
    source input had been readable - so a record reporting SEC-AVAIL unverified
    was admitted as a pass.
    """
    scopes = [str(item) for item in plan.get("scopes") or []]
    record = {
        "schema_version": RECORD_VERSION,
        "plan_digest": content_digest(plan),
        "intent_digest": INTENT_DIGEST,
        "errors": 0,
        "warnings": 0,
        "source_available": True,
        "checked_scopes": scopes,
        "obligations": {
            scope: {obligation: PASS for obligation in applicable_obligations(plan)} for scope in scopes
        },
    }
    record.update(overrides)
    return record


def approval(**overrides) -> dict:
    record = {
        "approved": True,
        "approved_by": "security-lead",
        "intent_digest": INTENT_DIGEST,
        "scopes": ["scope.a"],
        "epoch": "2026-09-14T00:00:00Z",
    }
    record.update(overrides)
    return record


APPROVED = approval()


# --- the positive control ------------------------------------------------------------


def test_a_prepared_strict_plan_is_admitted() -> None:
    """First, because an always-refusing implementation passes every other test."""
    plan = strict_plan()

    admission = evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED)

    assert admission.admitted, admission.reasons
    assert admission.plan_digest == content_digest(plan)


def test_the_control_fails_when_any_single_condition_is_removed() -> None:
    """Each condition is load-bearing, checked one at a time against the control."""
    plan = strict_plan()
    cases = {
        "provenance": dict(plan=strict_plan(provenance="legacy_shadow"), verification=None, approved_intent=APPROVED),
        "verification": dict(plan=plan, verification=None, approved_intent=APPROVED),
        "approval": dict(plan=plan, verification=verification_for(plan), approved_intent=None),
        "blocked": dict(
            plan=strict_plan(blocked_scopes=["scope.b"]),
            verification=None,
            approved_intent=APPROVED,
        ),
        "eligibility": dict(plan=strict_plan(strict_eligible=[]), verification=None, approved_intent=APPROVED),
    }
    for label, kwargs in cases.items():
        if kwargs["verification"] is None and label not in ("verification",):
            kwargs["verification"] = verification_for(kwargs["plan"])
        assert not evaluate(**kwargs).admitted, f"{label} was not load-bearing"


# --- condition 1: legacy_shadow is refused whatever else is true -----------------------


def test_a_fully_lowered_verified_legacy_plan_is_still_refused() -> None:
    """The main negative test. Everything is right except that nobody approved it."""
    plan = strict_plan(provenance="legacy_shadow")

    admission = evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED)

    assert not admission.admitted
    assert any("legacy" in reason or "strict" in reason for reason in admission.reasons)


def test_lowering_completeness_does_not_admit_a_legacy_plan() -> None:
    plan = strict_plan(provenance="legacy_shadow", lowering_complete=["scope.a"], unlowerable=[])

    assert not evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED).admitted


def test_shadow_analysis_stays_available_after_refusal() -> None:
    """A refusal withholds admission; it does not withdraw the plan."""
    plan = strict_plan(provenance="legacy_shadow")

    admission = evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED)

    assert not admission.admitted
    assert plan["rules"], "the plan is still there to analyse"


# --- condition 2: a provenance swap is not approval -------------------------------------


def test_swapping_provenance_alone_does_not_admit() -> None:
    plan = strict_plan()

    assert not evaluate(plan=plan, verification=verification_for(plan), approved_intent=None).admitted
    assert not evaluate(plan=plan, verification=None, approved_intent=APPROVED).admitted


def test_an_unapproved_intent_object_is_not_approval() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=approval(approved=False)
    )

    assert not admission.admitted


# --- condition 4: the approval names the intent that was checked -------------------------


def test_an_approval_of_other_inputs_does_not_admit_this_plan() -> None:
    """`UNRELATED_APPROVAL`, reproduced from the 2026-09-14 review.

    The approval was read for `approved` alone, so one issued against a different
    scope and a different binding admitted this plan. The digest it names must be
    the digest the verifier recorded.
    """
    plan = strict_plan()

    admission = evaluate(
        plan=plan,
        verification=verification_for(plan),
        approved_intent=approval(intent_digest="sha256-" + "9" * 64),
    )

    assert not admission.admitted
    assert any("approval of other inputs" in reason for reason in admission.reasons)


def test_an_approval_that_does_not_cover_the_scope_refuses() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=approval(scopes=["scope.other"])
    )

    assert not admission.admitted
    assert any("does not cover" in reason for reason in admission.reasons)


def test_a_bare_boolean_approves_nothing_in_particular() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan), approved_intent={"approved": True}
    )

    assert not admission.admitted
    assert any("missing" in reason for reason in admission.reasons)


def test_an_approval_without_an_approver_or_an_epoch_refuses() -> None:
    plan = strict_plan()

    assert not evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=approval(approved_by="  ")
    ).admitted
    assert not evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=approval(epoch="")
    ).admitted


def test_a_verification_naming_no_intent_cannot_be_bound_to_an_approval() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan, intent_digest=""), approved_intent=APPROVED
    )

    assert not admission.admitted


# --- condition 4: the record must be complete in shape ------------------------------------


def test_a_record_missing_a_field_is_refused_rather_than_defaulted() -> None:
    """`MISSING_RECORD_FIELDS`: absence read as zero errors and nothing to disagree with."""
    plan = strict_plan()
    record = verification_for(plan)
    del record["errors"]
    del record["checked_scopes"]

    admission = evaluate(plan=plan, verification=record, approved_intent=APPROVED)

    assert not admission.admitted
    assert any("unanswered question" in reason for reason in admission.reasons)


def test_a_record_of_an_unknown_version_is_refused() -> None:
    plan = strict_plan()

    assert not evaluate(
        plan=plan, verification=verification_for(plan, schema_version=99), approved_intent=APPROVED
    ).admitted


def test_a_scope_the_verifier_never_saw_is_refused() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan, checked_scopes=["scope.other"]), approved_intent=APPROVED
    )

    assert not admission.admitted
    assert any("never checked" in reason for reason in admission.reasons)


# --- condition 5: every applicable obligation must have passed ----------------------------


def test_an_unverified_obligation_is_not_a_pass() -> None:
    """`MISSING_AVAILABILITY`: a real record carrying `W7002` used to be admitted."""
    plan = strict_plan()
    record = verification_for(plan)
    record["obligations"]["scope.a"]["SEC-AVAIL"] = "unverified"

    admission = evaluate(plan=plan, verification=record, approved_intent=APPROVED)

    assert not admission.admitted
    assert any("SEC-AVAIL" in reason for reason in admission.reasons)


def test_a_missing_obligation_status_is_not_a_pass() -> None:
    plan = strict_plan()
    record = verification_for(plan)
    del record["obligations"]["scope.a"]["SEC-AUTH"]

    admission = evaluate(plan=plan, verification=record, approved_intent=APPROVED)

    assert not admission.admitted
    assert any("no status" in reason for reason in admission.reasons)


def test_every_checked_obligation_is_load_bearing() -> None:
    plan = strict_plan()
    for obligation in CHECKED_OBLIGATIONS:
        record = verification_for(plan)
        record["obligations"]["scope.a"][obligation] = "fail"

        assert not evaluate(
            plan=plan, verification=record, approved_intent=APPROVED
        ).admitted, f"{obligation} was not load-bearing"


def test_a_plan_containing_a_deferred_construct_needs_its_obligation() -> None:
    """The deferral has a trigger, so it is a claim that can come due.

    SEC-NAT and the other four are implemented in `netmodel` and not mounted. A
    plan containing none of the constructs they govern cannot violate them. A
    plan that grows one is refused here rather than admitted unchecked.
    """
    plan = strict_plan()
    plan["rules"][0]["nat"] = {"to": "10.0.0.5"}

    assert "SEC-NAT" in applicable_obligations(plan)

    # A record that answers only the four the framework checks - which is what
    # the mounted validator produces today.
    unanswered = verification_for(plan)
    del unanswered["obligations"]["scope.a"]["SEC-NAT"]
    admission = evaluate(plan=plan, verification=unanswered, approved_intent=APPROVED)

    assert not admission.admitted
    assert any("SEC-NAT" in reason for reason in admission.reasons)
    # And the same plan with the obligation actually answered is admissible, so
    # the refusal is about the missing check rather than about the construct.
    assert evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED).admitted


def test_a_plan_without_those_constructs_needs_only_the_checked_four() -> None:
    assert applicable_obligations(strict_plan()) == CHECKED_OBLIGATIONS


# --- condition 5: the plan's own scope lists must agree -----------------------------------


def test_scope_lists_that_contradict_each_other_refuse() -> None:
    """`INCONSISTENT_SCOPES`: eligible elsewhere, nothing lowering-complete, unlowerable intent."""
    plan = strict_plan(
        strict_eligible=["scope.a"],
        lowering_complete=[],
        unlowerable=[{"matrix_ref": "scope.a", "name": "x", "reason": "unsupported"}],
        blocked_scopes=[],
    )

    admission = evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED)

    assert not admission.admitted
    assert any("lowering-complete" in reason for reason in admission.reasons)
    assert any("could not lower" in reason for reason in admission.reasons)
    assert any("disagree" in reason for reason in admission.reasons)


def test_a_scope_outside_the_eligible_list_cannot_be_requested() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=APPROVED, scopes=["scope.b"]
    )

    assert not admission.admitted
    assert any("cannot be requested" in reason for reason in admission.reasons)


def test_a_refusal_has_no_projection_to_render() -> None:
    plan = strict_plan()
    refused = evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=approval(approved=False)
    )

    assert admitted_projection(plan, refused) == {}


def test_the_projection_carries_only_the_admitted_scopes() -> None:
    """A renderer takes its rules from here, not from the plan it passed in."""
    plan = strict_plan()
    plan["scopes"] = ["scope.a", "scope.b"]
    plan["lowering_complete"] = ["scope.a", "scope.b"]
    plan["rules"].append(
        {
            "origin": "binding:other",
            "effect": "permit",
            "terminal": False,
            "scope": "scope.b",
            "sources": ["z.c"],
            "destinations": ["z.d"],
            "transport": {"kind": "ports", "protocol": "tcp", "ports": [22]},
            "position": 2,
        }
    )

    admission = evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED)
    assert admission.admitted, admission.reasons

    projection = admitted_projection(plan, admission)

    assert projection["scopes"] == ["scope.a"]
    assert {rule["scope"] for rule in projection["rules"]} == {"scope.a"}
    assert len(plan["rules"]) == 3, "the plan itself is not modified"


def test_admission_names_the_scopes_it_admitted() -> None:
    """A renderer must receive the projection that was admitted, not the whole plan."""
    plan = strict_plan()

    admission = evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED)

    assert admission.admitted
    assert admission.scopes == ("scope.a",)
    assert evaluate(
        plan=plan, verification=verification_for(plan), approved_intent=approval(approved=False)
    ).scopes == ()


# --- condition 3: a plan changed after checking loses admission ---------------------------


def test_a_plan_edited_after_verification_is_refused() -> None:
    plan = strict_plan()
    record = verification_for(plan)

    mutated = copy.deepcopy(plan)
    mutated["rules"][0]["transport"]["ports"] = [443, 22]

    admission = evaluate(plan=mutated, verification=record, approved_intent=APPROVED)

    assert not admission.admitted
    assert any("changed after checking" in reason for reason in admission.reasons)


def test_recomputing_the_plans_own_digest_does_not_restore_admission() -> None:
    """The detail that matters: admission computes the digest, never accepts one.

    A mutated payload that also updates its own `digest` field is self-consistent
    and still not the plan that was verified. Trusting the presented hash would
    let a changed plan certify itself.
    """
    plan = strict_plan()
    record = verification_for(plan)

    mutated = copy.deepcopy(plan)
    mutated["rules"][0]["transport"]["ports"] = [443, 22]
    mutated["digest"] = content_digest(mutated)  # made self-consistent on purpose

    admission = evaluate(plan=mutated, verification=record, approved_intent=APPROVED)

    assert not admission.admitted
    assert any("changed after checking" in reason for reason in admission.reasons)


def test_the_digest_ignores_the_payloads_own_digest_field() -> None:
    """Otherwise editing that field alone would change the plan's identity."""
    plan = strict_plan()
    relabelled = strict_plan(digest="sha256-a-completely-different-claim")

    assert content_digest(plan) == content_digest(relabelled)


# --- condition 4: incomplete checks and blocked scopes forbid rendering --------------------


def test_an_unreadable_source_is_not_a_pass() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan, source_available=False), approved_intent=APPROVED
    )

    assert not admission.admitted
    assert any("did not run" in reason for reason in admission.reasons)


def test_a_check_that_reported_errors_refuses() -> None:
    plan = strict_plan()

    admission = evaluate(plan=plan, verification=verification_for(plan, errors=2), approved_intent=APPROVED)

    assert not admission.admitted


def test_a_blocked_scope_refuses_the_whole_plan() -> None:
    plan = strict_plan(blocked_scopes=["scope.b"])

    assert not evaluate(plan=plan, verification=verification_for(plan), approved_intent=APPROVED).admitted


def test_a_missing_plan_refuses() -> None:
    assert not evaluate(plan=None, verification=None, approved_intent=APPROVED).admitted


# --- condition 5: a refusal never enables a fallback ----------------------------------------


def test_a_refusal_never_permits_a_legacy_fallback() -> None:
    """Falling back turns the boundary into a preference, and the plan runs anyway."""
    refused = evaluate(plan=strict_plan(provenance="legacy_shadow"), verification=None, approved_intent=None)
    admitted = evaluate(
        plan=strict_plan(), verification=verification_for(strict_plan()), approved_intent=APPROVED
    )

    assert refused.legacy_fallback_permitted is False
    assert admitted.legacy_fallback_permitted is False


def test_the_fallback_flag_cannot_be_set_by_a_caller() -> None:
    """A field a consumer could pass in would be one a consumer could pass true."""
    import dataclasses

    field_map = {item.name: item for item in dataclasses.fields(Admission)}

    assert field_map["legacy_fallback_permitted"].init is False
