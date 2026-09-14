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
    Envelope,
    Mutation,
    TransitionError,
    build_sequence,
    check_sequence,
    diff,
    plan_transition,
    safe_order,
    simulate,
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


def envelope_of(*flows, old="sha256-old", new="sha256-new") -> Envelope:
    return Envelope(
        old_digest=old,
        new_digest=new,
        allowed=frozenset(flows),
        expiry="2026-09-12T00:00:00Z",
    )


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
    envelope = envelope_of(
        ("zone.lan", "zone.mgmt", "tcp", 22),
        ("zone.lan", "zone.mgmt", "tcp", 443),
    )

    steps = plan_transition(old=old, new=new, envelope=envelope, flow_space=flow_space())

    assert steps, "a transition that changes something must have steps"
    assert check_sequence(steps, envelope, flow_space()) == []


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
    envelope = envelope_of()  # neither epoch authorizes guest to management

    with pytest.raises(TransitionError, match="no safe sequence"):
        plan_transition(old=old, new=new, envelope=envelope, flow_space=flow_space(), strategy=_guards_out_first)


def test_both_endpoints_can_be_safe_while_a_state_between_them_is_not() -> None:
    """Stated directly, because it is the whole reason to check states."""
    constrained = permit("ssh", source="zone.guest", destination="zone.mgmt", port=22)
    guards = {"g": guard("g", sources={"zone.guest"}, destinations={"zone.mgmt"}, ports=PORTS)}
    old = plan_for([constrained], guards)
    new = plan_for([], {})
    envelope = envelope_of()

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
