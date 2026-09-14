"""SEC-TRANSITION: every intermediate state admits only the approved set.

Both the old plan and the new one can be correct while a particular way of
getting between them is not. Drop a mandatory deny first and, for as long as the
apply takes, every permit it used to constrain is live. The final state looks
perfect afterwards and records nothing about the window.

So the tests that matter are the ones where the endpoints are fine and a state in
between is not. A checker that only looks at the endpoints passes all of them.
"""

from __future__ import annotations

import pytest

from netmodel.interpret import FlowEvent, Verdict, interpret
from netmodel.lower import lower
from netmodel.plan import ExecutionContext
from netmodel.policy import (
    BINDING_DESTINATION,
    BINDING_SOURCE,
    Activation,
    Binding,
    Effect,
    PolicyTemplate,
    resolve_grant,
)
from netmodel.transition import (
    UNMATCHED,
    Envelope,
    Mutation,
    Step,
    TransitionError,
    build_sequence,
    check_sequence,
    diff,
    plan_transition,
    safe_order,
    simulate,
    state_digest,
)

CONTEXT = ExecutionContext(
    enforcer="rtr-chateau", routing_domain="main", family="ipv4", hook="forward", chain="managed"
)
ENDPOINTS = ("zone.lan", "zone.guest", "zone.mgmt")
PORTS = (22, 443)


def event(source: str, destination: str, port: int) -> FlowEvent:
    return FlowEvent(
        source=source,
        destination=destination,
        protocol="tcp",
        port=port,
        enforcer=CONTEXT.enforcer,
        routing_domain=CONTEXT.routing_domain,
        family=CONTEXT.family,
        hook=CONTEXT.hook,
        chain=CONTEXT.chain,
    )


def flow_space() -> list[FlowEvent]:
    return [event(source, destination, port) for source in ENDPOINTS for destination in ENDPOINTS for port in PORTS]


def permit(policy_id: str, *, source: str, destination: str, port: int):
    template = PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=BINDING_SOURCE,
        destination=BINDING_DESTINATION,
        protocol="tcp",
        ports=frozenset({port}),
        owner="infra-admin",
        rationale="declared need",
    )
    return resolve_grant(
        template,
        Binding(
            binding_id=f"bind.{policy_id}",
            policy_id=policy_id,
            sources=frozenset({source}),
            destinations=frozenset({destination}),
            approved=True,
        ),
    )


def guard(policy_id: str, *, sources, destinations, ports):
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.DENY,
        activation=Activation.SCOPE_GUARD,
        direction="transit",
        source=frozenset(sources),
        destination=frozenset(destinations),
        protocol="tcp",
        ports=frozenset(ports),
        owner="security",
        rationale="mandatory",
    )


def plan_for(grants, guards):
    return lower(grants=grants, guards=guards, context=CONTEXT, endpoints=ENDPOINTS, protocols=("tcp",))


def _guards_out_first(old, new) -> list[Mutation]:
    """A plausible and unsafe strategy: tear the denies down first.

    It returns mutations, so `simulate` builds the states its order actually
    produces. An earlier version of this test reordered finished steps instead,
    which shuffled labels over states the safe order had already built - the
    dangerous sequence it claimed to model never existed, and the test that
    expected a violation correctly found none.
    """
    additions, removals = diff(old, new)
    guards_first = sorted(removals, key=lambda item: (not item.is_guard, item.rule.canonical_key()))
    return additions + guards_first


AS_OF = "2026-09-11T00:00:00Z"
EXPIRY = "2026-09-12T00:00:00Z"


def envelope_of(*flows, old="sha256-old", new="sha256-new", expiry=EXPIRY) -> Envelope:
    return Envelope(
        old_digest=old,
        new_digest=new,
        allowed=frozenset(flows),
        expiry=expiry,
    )


def envelope_for(old_plan, new_plan, *flows, expiry=EXPIRY) -> Envelope:
    """An envelope actually tied to these two plans.

    Hand-written digest strings were accepted before, so an envelope authorizing
    some other transition proved this one. The digests are computed from the
    plans here, which is what the precondition compares against.
    """
    return Envelope(
        old_digest=state_digest(old_plan),
        new_digest=state_digest(new_plan),
        allowed=frozenset(flows),
        expiry=expiry,
    )


def accepted_by(plan) -> frozenset:
    """`A_new` over the probe space - what the plan actually admits."""
    return frozenset(
        item.authorizing.key() for item in flow_space() if interpret(plan, item).verdict is Verdict.ACCEPT
    )


def apply_plan(old_plan, new_plan, envelope, **overrides):
    """`plan_transition` with the context every caller has to supply."""
    arguments = {
        "old": old_plan,
        "new": new_plan,
        "envelope": envelope,
        "flow_space": flow_space(),
        "as_of": AS_OF,
        "new_allowed": accepted_by(new_plan),
    }
    arguments.update(overrides)
    return plan_transition(**arguments)


# --- the envelope is tied to something ------------------------------------------


@pytest.mark.parametrize("missing", ["old_digest", "new_digest", "expiry"])
def test_an_envelope_must_be_tied_to_digests_and_an_expiry(missing: str) -> None:
    values = {
        "old_digest": "sha256-old",
        "new_digest": "sha256-new",
        "allowed": frozenset(),
        "expiry": "2026-09-12T00:00:00Z",
        missing: "  " if missing != "allowed" else frozenset(),
    }
    with pytest.raises(TransitionError, match=missing):
        Envelope(**values)


def test_an_envelope_between_identical_digests_is_refused() -> None:
    with pytest.raises(TransitionError, match="no transition to authorize"):
        Envelope(old_digest="x", new_digest="x", allowed=frozenset(), expiry="t")


# --- the property, over states rather than endpoints ------------------------------


def test_a_safe_sequence_keeps_every_state_inside_the_envelope() -> None:
    old_guard = {"guard.no_guest_to_mgmt": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}
    ssh = permit("ssh", source="zone.lan", destination="zone.mgmt", port=22)
    web = permit("web", source="zone.lan", destination="zone.mgmt", port=443)

    old = plan_for([ssh], old_guard)
    new = plan_for([ssh, web], old_guard)
    envelope = envelope_for(
        old,
        new,
        ("zone.lan", "zone.mgmt", "tcp", 22),
        ("zone.lan", "zone.mgmt", "tcp", 443),
    )

    steps = apply_plan(old, new, envelope, required_flows=frozenset({("zone.lan", "zone.mgmt", "tcp", 22)}))

    assert steps, "a transition that changes something must have steps"
    assert check_sequence(steps, envelope, flow_space()) == []
    assert state_digest(steps[-1].state) == state_digest(new), "the sequence must arrive at the new plan"


def test_removing_a_guard_before_its_permits_is_refused() -> None:
    """The window the obligation exists for, and the endpoints are both fine.

    Old: guest cannot reach management, and a permit exists that the guard
    constrains. New: both are gone. A sequence that removes the guard first makes
    the permit live against guest for the length of the apply.
    """
    constrained = permit("ssh", source="zone.guest", destination="zone.mgmt", port=22)
    guards = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}

    old = plan_for([constrained], guards)
    new = plan_for([], {})
    envelope = envelope_for(old, new)  # neither epoch authorizes guest to management

    with pytest.raises(TransitionError, match="no safe sequence"):
        apply_plan(old, new, envelope, strategy=_guards_out_first)


def test_both_endpoints_can_be_safe_while_a_state_between_them_is_not() -> None:
    """Stated directly, because it is the whole reason to check states."""
    constrained = permit("ssh", source="zone.guest", destination="zone.mgmt", port=22)
    guards = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}
    old = plan_for([constrained], guards)
    new = plan_for([], {})
    envelope = envelope_for(old, new)

    for endpoint in (old, new):
        accepted = [item for item in flow_space() if interpret(endpoint, item).verdict is Verdict.ACCEPT]
        assert all(envelope.admits(item) for item in accepted), "an endpoint is already outside the envelope"

    unsafe = simulate(old, _guards_out_first(old, new))

    assert check_sequence(unsafe, envelope, flow_space()), "the unsafe state between two safe endpoints must be found"


def test_the_default_strategy_adds_denies_before_permits() -> None:
    """No moment where a new permit is live without the guard that constrains it."""
    new_guard = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}
    risky = permit("ssh", source="zone.guest", destination="zone.mgmt", port=22)

    old = plan_for([], {})
    new = plan_for([risky], new_guard)

    mutations = [item for item in safe_order(old, new) if item.action == "add"]
    guard_at = next(index for index, item in enumerate(mutations) if "guard" in item.rule.origin)
    permit_at = next(index for index, item in enumerate(mutations) if "binding" in item.rule.origin)

    assert guard_at < permit_at


def test_the_default_strategy_removes_permits_before_guards() -> None:
    """And no moment where an old permit outlives the guard that constrained it."""
    constrained = permit("ssh", source="zone.guest", destination="zone.mgmt", port=22)
    guards = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}

    mutations = [
        item for item in safe_order(plan_for([constrained], guards), plan_for([], {})) if item.action == "remove"
    ]
    permit_at = next(index for index, item in enumerate(mutations) if "binding" in item.rule.origin)
    guard_at = next(index for index, item in enumerate(mutations) if "guard" in item.rule.origin)

    assert permit_at < guard_at


# --- not vacuous ------------------------------------------------------------------


def test_the_sequence_actually_passes_through_states() -> None:
    """A check over no steps passes and proves nothing."""
    ssh = permit("ssh", source="zone.lan", destination="zone.mgmt", port=22)
    web = permit("web", source="zone.lan", destination="zone.mgmt", port=443)
    steps = build_sequence(plan_for([ssh], {}), plan_for([ssh, web], {}))

    assert len(steps) >= 1
    assert all(step.state for step in steps), "an intermediate state must contain rules"
    assert len(flow_space()) >= 18


def test_an_unchanged_plan_needs_no_steps() -> None:
    ssh = permit("ssh", source="zone.lan", destination="zone.mgmt", port=22)
    plan = plan_for([ssh], {})

    assert build_sequence(plan, plan) == []


def test_a_violation_names_the_step_the_flow_and_the_rule() -> None:
    """A refusal an operator cannot act on is only an obstruction."""
    constrained = permit("ssh", source="zone.guest", destination="zone.mgmt", port=22)
    guards = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}
    old = plan_for([constrained], guards)
    envelope = envelope_of()

    new = plan_for([], {})
    violations = check_sequence(simulate(old, _guards_out_first(old, new)), envelope, flow_space())

    assert violations
    rendered = str(violations[0])
    assert "step " in rendered and "zone.guest" in rendered and "via " in rendered


# --- proving a sequence is more than checking its middle ------------------------


def _changed_plans():
    """Two plans that genuinely differ, for the precondition tests below."""
    ssh = permit("ssh", source="zone.lan", destination="zone.mgmt", port=22)
    web = permit("web", source="zone.lan", destination="zone.mgmt", port=443)
    guards = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}
    return plan_for([ssh], guards), plan_for([ssh, web], guards)


def test_the_probe_that_proved_nothing_is_now_refused() -> None:
    """The review's counterexample: empty flow space, expired envelope, arbitrary digests.

    It returned `[]` and `[]` read as proof. Every one of those three is now a
    refusal on its own, and this asserts the combination that was reported.
    """
    old, new = _changed_plans()

    with pytest.raises(TransitionError):
        plan_transition(
            old=old,
            new=new,
            envelope=envelope_of(expiry="2020-01-01T00:00:00Z"),
            flow_space=[],
            as_of=AS_OF,
            new_allowed=frozenset(),
        )


def test_an_expired_envelope_is_not_a_narrower_one() -> None:
    old, new = _changed_plans()
    envelope = envelope_for(old, new, *accepted_by(new), expiry="2020-01-01T00:00:00Z")

    with pytest.raises(TransitionError, match="expired"):
        apply_plan(old, new, envelope)


def test_a_proof_needs_the_moment_it_is_valid_at() -> None:
    old, new = _changed_plans()

    with pytest.raises(TransitionError, match="valid at no stated time"):
        apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), as_of="")


@pytest.mark.parametrize("end", ["old", "new"])
def test_an_envelope_for_another_transition_does_not_authorize_this_one(end: str) -> None:
    """Digest strings were accepted as labels; they are compared with the plans now."""
    old, new = _changed_plans()
    digests = {"old": state_digest(old), "new": state_digest(new)}
    digests[end] = "sha256-" + "0" * 64

    envelope = Envelope(
        old_digest=digests["old"],
        new_digest=digests["new"],
        allowed=accepted_by(new),
        expiry=EXPIRY,
    )

    with pytest.raises(TransitionError, match="authorizes a transition"):
        apply_plan(old, new, envelope)


def test_an_empty_flow_space_proves_the_probe_set_and_not_the_transition() -> None:
    old, new = _changed_plans()

    with pytest.raises(TransitionError, match="empty probe set|flow space is empty"):
        apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), flow_space=[])


def test_a_flow_space_omitting_what_the_envelope_admits_is_refused() -> None:
    """Nothing was asked about those flows, so nothing was shown about them."""
    old, new = _changed_plans()
    envelope = envelope_for(old, new, *accepted_by(new), ("zone.lan", "zone.guest", "udp", 53))

    with pytest.raises(TransitionError, match="omits"):
        apply_plan(old, new, envelope)


def test_a_strategy_that_performs_nothing_proves_nothing() -> None:
    """The defect underneath the probe: no steps produced no violations.

    A strategy returning an empty list was simulated into zero states, and zero
    states have no state outside the envelope. The transition was reported safe
    without being attempted.
    """
    old, new = _changed_plans()

    with pytest.raises(TransitionError, match="never performed"):
        apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), strategy=lambda *_: [])


def test_a_strategy_that_skips_one_mutation_is_refused() -> None:
    old, new = _changed_plans()

    def incomplete(old_plan, new_plan):
        return safe_order(old_plan, new_plan)[:-1]

    with pytest.raises(TransitionError, match="never performed"):
        apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), strategy=incomplete)


def test_a_strategy_that_invents_a_mutation_is_refused() -> None:
    old, new = _changed_plans()
    stray = Mutation("remove", old[0].rule)

    def inventive(old_plan, new_plan):
        return [*safe_order(old_plan, new_plan), stray]

    with pytest.raises(TransitionError, match="not required"):
        apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), strategy=inventive)


def test_a_sequence_that_stops_somewhere_safe_has_not_applied_the_plan() -> None:
    """Arrival is its own question. A safe state is not necessarily the target."""
    old, new = _changed_plans()

    # A sequence that performs the whole diff necessarily arrives, so the
    # interesting case is the one where it does not: a strategy applying only
    # part of it. That is refused by the replay check first, which is the right
    # order - the arrival check is the backstop, asserted here on a real run.
    steps = apply_plan(old, new, envelope_for(old, new, *accepted_by(new)))

    additions, removals = diff(old, new)
    assert len(steps) == len(additions) + len(removals), "every mutation produced a state"
    assert state_digest(steps[-1].state) == state_digest(new)


def test_an_unmatched_flow_is_reported_rather_than_skipped_with_denies() -> None:
    """`DENY` and `UNSUPPORTED` are opposites, and both were being ignored.

    A state with no terminal leaves flows matching nothing at all. On a
    default-allow backend that is an open flow, and it is exactly what the window
    between removing a terminal and adding the next one looks like.
    """
    ssh = permit("ssh", source="zone.lan", destination="zone.mgmt", port=22)
    full = plan_for([ssh], {})
    without_terminal = tuple(entry for entry in full if not entry.rule.terminal)

    steps = [Step(index=0, action="remove", rule_origin="plan:terminal", state=without_terminal)]
    violations = check_sequence(steps, envelope_of(*accepted_by(full)), flow_space())

    assert violations, "a state matching nothing must not read as a state denying everything"
    assert {item.kind for item in violations} == {UNMATCHED}
    assert "matching no rule at all" in str(violations[0])


def test_the_final_state_must_not_accept_what_the_new_plan_does_not_authorize() -> None:
    old, new = _changed_plans()

    with pytest.raises(TransitionError, match="does not authorize"):
        apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), new_allowed=frozenset())


def test_what_has_to_keep_working_must_be_working_at_the_end() -> None:
    """SEC-AVAIL at the end of the apply, which nothing checked before."""
    old, new = _changed_plans()
    must_work = frozenset({("zone.guest", "zone.mgmt", "tcp", 22)})

    with pytest.raises(TransitionError, match="outside what the new plan authorizes"):
        apply_plan(
            old, new, envelope_for(old, new, *accepted_by(new), *must_work), required_flows=must_work
        )


def test_a_required_flow_the_new_plan_carries_passes() -> None:
    """Not vacuous: the same argument returns a refusal above."""
    old, new = _changed_plans()
    must_work = frozenset({("zone.lan", "zone.mgmt", "tcp", 443)})

    steps = apply_plan(old, new, envelope_for(old, new, *accepted_by(new)), required_flows=must_work)

    assert steps
