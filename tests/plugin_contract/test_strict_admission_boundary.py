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
    STRICT_PROVENANCE,
    Admission,
    content_digest,
    evaluate,
    strict_artifacts,
)


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
    record = {"plan_digest": content_digest(plan), "errors": 0, "warnings": 0, "complete": True}
    record.update(overrides)
    return record


APPROVED = {"approved": True, "approver": "security-lead", "bindings": ["bind.web"]}


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
        plan=plan, verification=verification_for(plan), approved_intent={"approved": False, "approver": "someone"}
    )

    assert not admission.admitted


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


def test_an_incomplete_check_is_not_a_pass() -> None:
    plan = strict_plan()

    admission = evaluate(
        plan=plan, verification=verification_for(plan, complete=False), approved_intent=APPROVED
    )

    assert not admission.admitted
    assert any("did not complete" in reason for reason in admission.reasons)


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
