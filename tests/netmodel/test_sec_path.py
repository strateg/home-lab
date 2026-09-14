"""SEC-PATH: every feasible path crosses a gate or is demonstrably disabled.

The check is easy; the inventory is the problem. `complete(R_g, Omega_g)` is
unfalsifiable while `Omega_g` is whatever the resolver enumerated - a resolver
that forgets a path class reports full coverage of the classes it remembered. So
the tests that matter are about where the inventory comes from and what silence
means, not about the set arithmetic.
"""

from __future__ import annotations

import pytest

from netmodel.path import (
    CaseStatus,
    Exclusion,
    PathCase,
    PathClass,
    PathError,
    coverage_gaps,
    required_cases,
    unanchored_claims,
)

SUBJECT = "rtr-chateau"
FAMILIES = ("ipv4", "ipv6")
EPOCHS = ("epoch.current",)


def scope(*, subjects=(SUBJECT,), families=FAMILIES, epochs=EPOCHS):
    return required_cases(subjects=subjects, families=families, epochs=epochs)


def evidence_for(cases, reference="tuc/0031"):
    return {case.key(): reference for case in cases}


# --- the lower bound is normative, not chosen here --------------------------------


def test_the_lower_bound_covers_every_class_the_contract_names() -> None:
    """L2, routed, host input and output, tunnel, direct backend, offload."""
    named = {item.value for item in PathClass}

    assert named == {
        "l2_same_bridge",
        "routed",
        "host_input",
        "host_output",
        "tunnel",
        "direct_backend",
        "offload",
    }


def test_ipv6_is_carried_by_the_family_axis_not_a_separate_class() -> None:
    """A departure from the literal text, made deliberately and visibly.

    The contract lists IPv6 among the classes and also crosses the classes with
    the families. Literally that yields "the IPv6 path class under the IPv4
    family", which means nothing. IPv6 produces a real case for every class
    through the family axis instead.
    """
    assert "ipv6" not in {item.value for item in PathClass}

    cases = scope()
    ipv6_cases = [case for case in cases if case.family == "ipv6"]

    assert len(ipv6_cases) == len(PathClass), "every class must have an IPv6 case"


def test_the_scope_is_crossed_across_subjects_families_and_epochs() -> None:
    cases = scope(subjects=("a", "b"), families=("ipv4", "ipv6"), epochs=("e1", "e2"))

    assert len(cases) == 2 * len(PathClass) * 2 * 2
    assert len({case.key() for case in cases}) == len(cases), "cases must be distinct"


def test_an_empty_scope_requires_nothing_and_says_so() -> None:
    """Rather than returning an empty list that would read as full coverage."""
    for missing in ({"subjects": ()}, {"families": ()}, {"epochs": ()}):
        with pytest.raises(PathError, match="at least one"):
            scope(**missing)


# --- absence is unverified by construction -----------------------------------------


def test_a_case_with_no_evidence_is_unverified_not_covered() -> None:
    """The sentence that makes the whole check falsifiable."""
    cases = scope()

    gaps = coverage_gaps(required=cases, demonstrated={})

    assert len(gaps) == len(cases)
    assert {item.status for item in gaps} == {CaseStatus.UNVERIFIED}
    assert "absent means unverified" in str(gaps[0])


def test_full_evidence_leaves_no_gap() -> None:
    cases = scope()

    assert coverage_gaps(required=cases, demonstrated=evidence_for(cases)) == []


def test_one_forgotten_class_is_reported_and_not_averaged_away() -> None:
    """A resolver that forgets a class must not report coverage of the rest."""
    cases = scope()
    partial = [case for case in cases if case.path_class is not PathClass.OFFLOAD]

    gaps = coverage_gaps(required=cases, demonstrated=evidence_for(partial))

    assert gaps
    assert {item.case.path_class for item in gaps} == {PathClass.OFFLOAD}


def test_an_evidence_entry_citing_nothing_is_a_claim_not_evidence() -> None:
    cases = scope()
    hollow = {case.key(): "   " for case in cases}

    gaps = coverage_gaps(required=cases, demonstrated=hollow)

    assert len(gaps) == len(cases)
    assert "cites nothing" in str(gaps[0])


# --- an exclusion has to be signed ---------------------------------------------------


def test_an_exclusion_needs_an_owner_and_a_reason() -> None:
    """The contract: a scope decision naming no owner and no reason closes nothing."""
    case = scope()[0]

    for missing in ("owner", "reason"):
        values = {"case": case, "owner": "security-lead", "reason": "no bridge on this subject", missing: "  "}
        with pytest.raises(PathError, match=missing):
            Exclusion(**values)


def test_a_signed_exclusion_closes_its_case_and_only_its_case() -> None:
    cases = scope()
    excluded = cases[0]
    exclusion = Exclusion(case=excluded, owner="security-lead", reason="the subject has no bridge")

    gaps = coverage_gaps(required=cases, demonstrated={}, exclusions=[exclusion])

    assert len(gaps) == len(cases) - 1
    assert excluded.key() not in {item.case.key() for item in gaps}


def test_an_exclusion_for_a_different_family_does_not_close_the_other() -> None:
    """Scoping IPv6 out of one class says nothing about IPv4, or any other class."""
    cases = scope()
    target = next(case for case in cases if case.family == "ipv6" and case.path_class is PathClass.TUNNEL)
    exclusion = Exclusion(case=target, owner="security-lead", reason="no IPv6 on the tunnel yet")

    gaps = coverage_gaps(required=cases, demonstrated={}, exclusions=[exclusion])
    remaining = {(item.case.path_class, item.case.family) for item in gaps}

    assert (PathClass.TUNNEL, "ipv4") in remaining
    assert (PathClass.TUNNEL, "ipv6") not in remaining


# --- the inventory comes from outside -------------------------------------------------


def test_evidence_for_a_case_nobody_required_is_reported() -> None:
    """Otherwise an inventory could shrink while the reported percentage rose."""
    cases = scope()
    stray = PathCase(subject="other-router", path_class=PathClass.ROUTED, family="ipv4", epoch_id="epoch.current")
    demonstrated = evidence_for(cases) | {stray.key(): "tuc/0099"}

    unanchored = unanchored_claims(required=cases, demonstrated=demonstrated)

    assert len(unanchored) == 1
    assert "other-router" in unanchored[0]


def test_the_module_does_not_produce_the_evidence_it_checks() -> None:
    """Marking one's own homework, prevented structurally.

    `required_cases` enumerates what must be covered. Nothing here enumerates
    what *is* covered - that comes in as an argument from evidence, so a defect
    in the resolver cannot silently supply both halves of the comparison.
    """
    import inspect

    from netmodel import path as module

    producers = [
        name
        for name, value in vars(module).items()
        if inspect.isfunction(value) and name.startswith(("demonstrate", "collect_evidence", "observe"))
    ]

    assert producers == []
    assert "demonstrated" in inspect.signature(coverage_gaps).parameters


# --- not vacuous -------------------------------------------------------------------------


def test_the_gap_check_can_report_and_can_stay_silent() -> None:
    cases = scope()

    assert coverage_gaps(required=cases, demonstrated={})
    assert coverage_gaps(required=cases, demonstrated=evidence_for(cases)) == []
    assert len(cases) >= 14, "the scope is too small to distinguish anything"
