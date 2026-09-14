"""Checks for capability satisfaction — SEC-CAP.

The contract's central claim is a chain of inequalities: declared support is not
effective support is not evidence is not permission. Most of these tests are
about places where one of those four could stand in for another, because that
substitution is what makes a capability system read as a security guarantee when
it is only a dispatch table.
"""

from __future__ import annotations

import pytest

from netmodel.capability import (
    UNKNOWN,
    CapabilityError,
    Context,
    EvidenceLevel,
    NotApplicable,
    Offer,
    Requirement,
    Resolution,
    Status,
    check_offer_identity,
    coverage,
    resolve,
)

FORWARD = Context(family="ipv4", routing_domain="main", hook="forward")
INPUT = Context(family="ipv4", routing_domain="main", hook="input")
V6 = Context(family="ipv6", routing_domain="main", hook="forward")


def requirement(**overrides) -> Requirement:
    values = {
        "requirement_id": "req.stateful",
        "obligation": "SEC-STATE",
        "capability_ref": "cap.firewall.stateful",
        "context": FORWARD,
        "evidence_required": EvidenceLevel.OFFLINE_VALIDATED,
        "origin": "inst.firewall_policy.main",
    }
    values.update(overrides)
    return Requirement(**values)


def offer(**overrides) -> Offer:
    values = {
        "offer_id": "offer.routeros.firewall",
        "version": "7.14",
        "content_digest": "sha256-aaa",
        "capability_ref": "cap.firewall.stateful",
        "contexts": (FORWARD,),
        "evidence": frozenset({EvidenceLevel.OFFLINE_VALIDATED}),
    }
    values.update(overrides)
    return Offer(**values)


# --- an empty loop is not proof ------------------------------------------------


def test_no_applicable_offer_is_unverified_not_satisfied() -> None:
    """The failure mode this exists to prevent.

    A loop over no applicable offers finds no incompatibility, which reads
    exactly like a loop that checked everything and found none.
    """
    result = resolve(requirement(), [])

    assert result.status is Status.UNVERIFIED
    assert "no offer applies" in result.reason
    assert result.blocks_activation


def test_an_offer_in_another_context_is_not_evidence() -> None:
    result = resolve(requirement(context=FORWARD), [offer(contexts=(INPUT,))])

    assert result.status is Status.UNVERIFIED


def test_an_offer_for_another_family_is_not_evidence() -> None:
    """Support for one address family says nothing about the other."""
    result = resolve(requirement(context=V6), [offer(contexts=(FORWARD,))])

    assert result.status is Status.UNVERIFIED


def test_an_offer_for_another_capability_is_not_evidence() -> None:
    result = resolve(requirement(), [offer(capability_ref="cap.firewall.logging")])

    assert result.status is Status.UNVERIFIED


def test_an_offer_with_no_context_cannot_be_constructed() -> None:
    with pytest.raises(CapabilityError, match="applies to nothing"):
        offer(contexts=())


# --- unknown is not unlimited ---------------------------------------------------


def test_an_unknown_limit_is_unverified_not_satisfied() -> None:
    result = resolve(requirement(bounds={"sessions": 1000}), [offer(limits={"sessions": UNKNOWN})])

    assert result.status is Status.UNVERIFIED
    assert "unknown" in result.reason


def test_an_unstated_limit_is_unverified_not_unlimited() -> None:
    """A bound the offer never mentions is not thereby met."""
    result = resolve(requirement(bounds={"sessions": 1000}), [offer(limits={})])

    assert result.status is Status.UNVERIFIED
    assert "states no limit" in result.reason


def test_an_unknown_value_has_no_truth_value() -> None:
    """`if limit:` must not quietly decide anything about an unknown."""
    with pytest.raises(CapabilityError, match="no truth value"):
        bool(UNKNOWN)


def test_a_stated_limit_below_the_bound_is_unsatisfied_not_unverified() -> None:
    """A demonstrated incompatibility is a different fact from missing evidence."""
    result = resolve(requirement(bounds={"sessions": 1000}), [offer(limits={"sessions": 500})])

    assert result.status is Status.UNSATISFIED
    assert "needs 1000, offer provides 500" in result.reason


def test_a_stated_limit_at_or_above_the_bound_satisfies() -> None:
    result = resolve(requirement(bounds={"sessions": 1000}), [offer(limits={"sessions": 1000})])

    assert result.status is Status.SATISFIED


# --- declared support is not evidence -------------------------------------------


def test_a_declaration_without_the_required_evidence_does_not_satisfy() -> None:
    """The heart of it: an offer can declare support and still prove nothing."""
    result = resolve(
        requirement(evidence_required=EvidenceLevel.LIVE_OBSERVED),
        [offer(evidence=frozenset({EvidenceLevel.DESIGN}))],
    )

    assert result.status is Status.UNVERIFIED
    assert "claim needs live_observed" in result.reason


def test_a_live_observation_does_not_discharge_an_offline_requirement() -> None:
    """Evidence is a kind, not a rung. The contract says so in one sentence.

    *A live packet sample does not replace independent model checks or all-path
    coverage.* An earlier version of this model compared levels numerically, so
    live evidence satisfied an offline-validated claim - a substitution that
    reads as strength and is really a change of subject: the two answer different
    questions and neither subsumes the other.
    """
    result = resolve(
        requirement(evidence_required=EvidenceLevel.OFFLINE_VALIDATED),
        [offer(evidence=frozenset({EvidenceLevel.LIVE_OBSERVED}))],
    )

    assert result.status is Status.UNVERIFIED
    assert "holds live_observed" in result.reason


def test_an_offline_check_does_not_discharge_a_live_requirement_either() -> None:
    """Symmetric, and for the same reason."""
    result = resolve(
        requirement(evidence_required=EvidenceLevel.LIVE_OBSERVED),
        [offer(evidence=frozenset({EvidenceLevel.OFFLINE_VALIDATED}))],
    )

    assert result.status is Status.UNVERIFIED


def test_an_offer_may_hold_several_kinds_at_once() -> None:
    """Being backend-tested does not stop something also being model-checked."""
    both = frozenset({EvidenceLevel.OFFLINE_VALIDATED, EvidenceLevel.BACKEND_TESTED})

    assert (
        resolve(requirement(evidence_required=EvidenceLevel.OFFLINE_VALIDATED), [offer(evidence=both)]).status
        is Status.SATISFIED
    )
    assert (
        resolve(requirement(evidence_required=EvidenceLevel.BACKEND_TESTED), [offer(evidence=both)]).status
        is Status.SATISFIED
    )
    assert (
        resolve(requirement(evidence_required=EvidenceLevel.LIVE_OBSERVED), [offer(evidence=both)]).status
        is Status.UNVERIFIED
    )


def test_an_offer_with_no_evidence_at_all_satisfies_nothing() -> None:
    for level in EvidenceLevel:
        assert resolve(requirement(evidence_required=level), [offer(evidence=frozenset())]).status is Status.UNVERIFIED


def test_a_witness_records_what_it_relied_on() -> None:
    """Identity, version and digest: a label alone cannot be checked later."""
    result = resolve(requirement(), [offer()])

    assert result.witnesses == (("offer.routeros.firewall", "7.14", "sha256-aaa"),)


# --- a version label is not trust ------------------------------------------------


def test_two_bodies_for_one_identity_and_version_is_an_error() -> None:
    with pytest.raises(CapabilityError, match="a version label is not trust"):
        check_offer_identity([offer(content_digest="sha256-aaa"), offer(content_digest="sha256-bbb")])


def test_the_same_body_twice_is_not_an_error() -> None:
    check_offer_identity([offer(), offer()])


def test_an_offer_without_a_digest_cannot_be_constructed() -> None:
    with pytest.raises(CapabilityError, match="a label, not a contract"):
        offer(content_digest="")


# --- there is no fourth status ---------------------------------------------------


def test_exactly_three_statuses_exist() -> None:
    assert {item.value for item in Status} == {"satisfied", "unsatisfied", "unverified"}


def test_not_applicable_is_not_a_status() -> None:
    """The contract says it is a scope decision, not a fourth way to pass."""
    assert not isinstance(NotApplicable("req.x", "out of profile scope"), Status)
    assert NotApplicable not in set(Status)


def test_scoping_something_out_requires_a_justification() -> None:
    with pytest.raises(CapabilityError, match="justification"):
        NotApplicable("req.x", "   ")


def test_both_non_satisfied_statuses_block_but_stay_distinguishable() -> None:
    """Collapsing them would lose the only actionable difference.

    `unsatisfied` has a source-level remedy; `unverified` means nobody knows.
    """
    demonstrated = resolve(requirement(bounds={"sessions": 1000}), [offer(limits={"sessions": 1})])
    unknown = resolve(requirement(), [])

    assert demonstrated.blocks_activation and unknown.blocks_activation
    assert demonstrated.status is not unknown.status


# --- coverage over a set ----------------------------------------------------------


def test_inactive_requirements_are_not_resolved_and_not_deleted() -> None:
    """Planned intent stays visible without becoming an activation requirement."""
    results = coverage([requirement(), requirement(requirement_id="req.planned", active=False)], [offer()])

    assert set(results) == {"req.stateful"}


def test_coverage_refuses_conflicting_offer_bodies_before_resolving_anything() -> None:
    with pytest.raises(CapabilityError):
        coverage([requirement()], [offer(content_digest="sha256-aaa"), offer(content_digest="sha256-bbb")])


def test_an_empty_requirement_set_yields_no_claim() -> None:
    """Nothing to resolve is not the same as everything satisfied."""
    assert coverage([], [offer()]) == {}


def test_a_requirement_must_name_its_obligation_and_origin() -> None:
    for missing in ("obligation", "origin", "capability_ref"):
        with pytest.raises(CapabilityError, match=missing):
            requirement(**{missing: "  "})


# --- structural ---------------------------------------------------------------------


def test_a_resolution_cannot_claim_support_without_a_witness() -> None:
    """Satisfied and witness-free would be exactly 'flag as proof'."""
    satisfied = resolve(requirement(), [offer()])
    assert satisfied.status is Status.SATISFIED and satisfied.witnesses

    for result in (resolve(requirement(), []), resolve(requirement(bounds={"x": 5}), [offer(limits={"x": 1})])):
        assert result.status is not Status.SATISFIED
        assert result.witnesses == ()


def test_the_module_has_no_vocabulary_for_permission() -> None:
    """Capability satisfaction is necessary and never sufficient.

    SEC-CAP cannot discharge SEC-AUTH, AVAIL, PATH, NAT, STATE or TRANSITION by
    itself, and the way to keep a later reader from treating a satisfied
    requirement as a permit is to leave nowhere for one to appear.
    """
    import ast
    from pathlib import Path

    module = Path(__file__).resolve().parents[2] / "netmodel" / "capability.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))

    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id.lower())
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            identifiers.add(node.name.lower())
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg.lower())

    segments = {part for name in identifiers for part in name.split("_")}
    forbidden = {"permit", "grant", "authorize", "allow", "accept"}

    assert not (
        segments & forbidden
    ), f"capability satisfaction gained {sorted(segments & forbidden)}; it is necessary, never sufficient"


# --- what the topology actually has today ---------------------------------------


def test_the_capability_catalog_holds_flags_not_offers() -> None:
    """Why E7042 is not implemented, stated as a measurement.

    `E7042` is "publication mechanism unsupported by the enforcing capability".
    Checking a mechanism against the catalog would compare it to a membership
    set, and the contract is explicit that set membership alone cannot prove
    network semantics - that comparison is precisely the flag-as-proof that
    A26-A29 block.

    An offer needs a version, context selectors, limits, conditions, evidence
    references and a content digest. The catalog entries have none of those. So
    the requirement stands unimplemented with a reason, and this test is what
    tells us the day the reason stops holding.
    """
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "topology-tools"))
    from yaml_loader import load_yaml_file

    catalog = load_yaml_file(repo_root / "topology/class-modules/capability-catalog.yaml") or {}
    entries = catalog.get("capabilities") or []
    assert entries, "the capability catalog is empty; this test is measuring nothing"

    fields: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict):
            fields |= set(entry)

    offer_fields = {"version", "contexts", "limits", "conditions", "evidence", "content_digest", "applies_to"}
    present = fields & offer_fields

    assert not present, (
        f"the catalog gained offer fields {sorted(present)}. Capability satisfaction can now be "
        "checked against something real: implement E7042 and the SEC-CAP resolution against it, "
        "and see adr/0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md for what an offer must carry."
    )


# --- composition: witnesses must hold together, not one at a time ----------------


from netmodel.capability import (  # noqa: E402
    Conflict,
    check_joint_feasibility,
    prerequisite_order,
    self_proving,
)

AS_OF = "2026-09-14T00:00:00Z"


def offers(*items: Offer) -> dict[str, Offer]:
    return {item.offer_id: item for item in items}


def test_two_adequate_offers_can_still_be_unusable_together() -> None:
    """The contract's point: effective support is not the union of capabilities.

    Each of these resolves on its own. Together they demand mutually exclusive
    modes, and no plan can hold both.
    """
    fast = offer(offer_id="offer.offload", mode="hardware-offload")
    inspecting = offer(offer_id="offer.inspect", mode="software-conntrack")

    assert resolve(requirement(), [fast]).status is Status.SATISFIED
    assert resolve(requirement(), [inspecting]).status is Status.SATISFIED

    conflicts = check_joint_feasibility(
        selection={"a": fast, "b": inspecting}, catalogue=offers(fast, inspecting), as_of=AS_OF
    )

    assert [item.kind for item in conflicts] == ["mode"]


def test_one_mode_across_witnesses_is_feasible() -> None:
    left = offer(offer_id="offer.a", mode="software-conntrack")
    right = offer(offer_id="offer.b", mode="software-conntrack")

    assert check_joint_feasibility(selection={"a": left, "b": right}, catalogue=offers(left, right), as_of=AS_OF) == []


def test_witnesses_owned_by_different_operators_are_refused() -> None:
    """One plan needs consistent ownership, not each offer owned by someone."""
    terraform = offer(offer_id="offer.tf", owner="terraform")
    ansible = offer(offer_id="offer.ansible", owner="ansible")

    conflicts = check_joint_feasibility(
        selection={"a": terraform, "b": ansible}, catalogue=offers(terraform, ansible), as_of=AS_OF
    )

    assert [item.kind for item in conflicts] == ["ownership"]


def test_a_mutating_offer_without_delegation_is_refused() -> None:
    writer = offer(offer_id="offer.writer", mutating=True, delegated=False)

    conflicts = check_joint_feasibility(selection={"a": writer}, catalogue=offers(writer), as_of=AS_OF)

    assert [item.kind for item in conflicts] == ["delegation"]


def test_a_mutating_offer_with_delegation_is_accepted() -> None:
    writer = offer(offer_id="offer.writer", mutating=True, delegated=True)

    assert check_joint_feasibility(selection={"a": writer}, catalogue=offers(writer), as_of=AS_OF) == []


# --- freshness ---------------------------------------------------------------------


def test_expired_evidence_makes_a_selection_infeasible() -> None:
    stale = offer(offer_id="offer.stale", evidence_expiry="2026-01-01T00:00:00Z")

    conflicts = check_joint_feasibility(selection={"a": stale}, catalogue=offers(stale), as_of=AS_OF)

    assert [item.kind for item in conflicts] == ["freshness"]


def test_evidence_inside_its_window_is_fresh() -> None:
    current = offer(offer_id="offer.fresh", evidence_expiry="2027-01-01T00:00:00Z")

    assert check_joint_feasibility(selection={"a": current}, catalogue=offers(current), as_of=AS_OF) == []


def test_an_offer_with_no_expiry_does_not_expire() -> None:
    """A statement the offer makes, not an omission the checker fills in."""
    permanent = offer(offer_id="offer.permanent", evidence_expiry=None)

    assert check_joint_feasibility(selection={"a": permanent}, catalogue=offers(permanent), as_of=AS_OF) == []


def test_freshness_needs_an_explicit_moment_and_reads_no_clock() -> None:
    """Otherwise the same inputs give different answers on different days.

    The contract wants timestamps out of semantic decisions and forbids one
    universal timeout. `as_of` is required, and the module imports nothing that
    could tell the time.
    """
    import ast
    import inspect
    from pathlib import Path

    signature = inspect.signature(check_joint_feasibility)
    assert signature.parameters["as_of"].default is inspect.Parameter.empty

    module = Path(__file__).resolve().parents[2] / "netmodel" / "capability.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not (imported & {"time", "datetime", "calendar"}), "a clock in here makes decisions non-deterministic"


# --- the prerequisite graph -----------------------------------------------------------


def test_prerequisites_are_ordered_dependencies_first() -> None:
    base = offer(offer_id="offer.base")
    middle = offer(offer_id="offer.middle", requires=("offer.base",))
    top = offer(offer_id="offer.top", requires=("offer.middle",))

    order = prerequisite_order(offers(base, middle, top))

    assert order.index("offer.base") < order.index("offer.middle") < order.index("offer.top")


def test_a_prerequisite_cycle_is_refused_with_the_path() -> None:
    """Broken at an arbitrary edge, the answer would depend on iteration order."""
    left = offer(offer_id="offer.left", requires=("offer.right",))
    right = offer(offer_id="offer.right", requires=("offer.left",))

    with pytest.raises(CapabilityError, match="prerequisite cycle"):
        prerequisite_order(offers(left, right))


def test_a_prerequisite_nobody_offers_is_refused() -> None:
    dependent = offer(offer_id="offer.dependent", requires=("offer.absent",))

    with pytest.raises(CapabilityError, match="unresolved prerequisite"):
        prerequisite_order(offers(dependent))


def test_a_cycle_in_the_selection_blocks_it() -> None:
    left = offer(offer_id="offer.left", requires=("offer.right",))
    right = offer(offer_id="offer.right", requires=("offer.left",))

    conflicts = check_joint_feasibility(selection={"a": left, "b": right}, catalogue=offers(left, right), as_of=AS_OF)

    assert [item.kind for item in conflicts] == ["prerequisite"]


def test_an_offer_cannot_prove_itself() -> None:
    """A strategy whose only prerequisite is the property it must prove.

    Circular in a way neither end shows: the offer looks like it has a
    dependency, and the dependency looks like it has a witness.
    """
    circular = offer(offer_id="offer.circular", requires=("cap.firewall.stateful",))

    assert self_proving(requirement(), circular)
    assert not self_proving(requirement(), offer(requires=("cap.other",)))
    assert not self_proving(requirement(), offer(requires=("cap.firewall.stateful", "cap.other")))


# --- aggregate capacity -----------------------------------------------------------------


def test_shared_capacity_is_checked_across_the_selection() -> None:
    """Each witness is adequate alone; the plan needs more than the tightest gives."""
    roomy = offer(offer_id="offer.roomy", limits={"sessions": 5000})
    tight = offer(offer_id="offer.tight", limits={"sessions": 100})

    conflicts = check_joint_feasibility(
        selection={"a": roomy, "b": tight},
        catalogue=offers(roomy, tight),
        as_of=AS_OF,
        aggregate_bounds={"sessions": 1000},
    )

    assert [item.kind for item in conflicts] == ["capacity"]
    assert "tightest witness provides 100" in str(conflicts[0])


def test_an_unknown_limit_does_not_count_as_capacity() -> None:
    """It also does not fail the aggregate check by itself; it is simply not evidence."""
    unknown = offer(offer_id="offer.unknown", limits={"sessions": UNKNOWN})

    conflicts = check_joint_feasibility(
        selection={"a": unknown},
        catalogue=offers(unknown),
        as_of=AS_OF,
        aggregate_bounds={"sessions": 1000},
    )

    assert conflicts == []


def test_a_feasible_selection_reports_nothing() -> None:
    """Not vacuous: the same call shape returns conflicts elsewhere in this file."""
    base = offer(offer_id="offer.base", mode="software-conntrack", owner="terraform")
    dependent = offer(
        offer_id="offer.dependent",
        mode="software-conntrack",
        owner="terraform",
        requires=("offer.base",),
        limits={"sessions": 5000},
    )

    conflicts = check_joint_feasibility(
        selection={"a": base, "b": dependent},
        catalogue=offers(base, dependent),
        as_of=AS_OF,
        aggregate_bounds={"sessions": 1000},
    )

    assert conflicts == []
