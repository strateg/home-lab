"""SEC-AUTH and SEC-AVAIL over a bounded flow space, with mutants.

The formal contract asks for two properties and names the mutants that must break
them: an accept-all plan must fail SEC-AUTH, an all-drop plan must fail SEC-AVAIL,
deleting a permit must not enlarge the authorized set, and adding a deny must not
enlarge it either.

The mutants are the load-bearing part. A checker that cannot fail an accept-all
plan proves nothing about a correct one, and the only way to know it can is to
hand it a plan that is definitely wrong and watch it say so.

The oracle is independent by construction: `netmodel.interpret` imports neither
`netmodel.policy` nor `netmodel.lower`, so when it agrees with the algebra that is
two implementations agreeing rather than one answering twice. A test asserts the
imports are absent, because the separation is the evidence.
"""

from __future__ import annotations

import itertools

import pytest

from netmodel.interpret import Decision, FlowEvent, Verdict, accepted_flows, interpret
from netmodel.lower import TERMINAL_ORIGIN, lower
from netmodel.plan import ExecutionContext, OrderedRule, PlanRule
from netmodel.policy import (
    BINDING_DESTINATION,
    BINDING_SOURCE,
    Activation,
    Binding,
    Effect,
    Flow,
    PolicyTemplate,
    authorize,
    resolve_grant,
)

CONTEXT = ExecutionContext(
    enforcer="rtr-chateau", routing_domain="main", family="ipv4", hook="forward", chain="managed"
)

ENDPOINTS = ("zone.lan", "zone.guest", "zone.mgmt")
PROTOCOLS = ("tcp", "udp")
PORTS = (22, 53, 443)


def event(source: str, destination: str, protocol: str, port: int) -> FlowEvent:
    return FlowEvent(
        source=source,
        destination=destination,
        protocol=protocol,
        port=port,
        enforcer=CONTEXT.enforcer,
        routing_domain=CONTEXT.routing_domain,
        family=CONTEXT.family,
        hook=CONTEXT.hook,
        chain=CONTEXT.chain,
    )


def flow_space() -> list[FlowEvent]:
    """Every flow the model is asked about. Bounded, and enumerated on purpose."""
    return [
        event(source, destination, protocol, port)
        for source, destination, protocol, port in itertools.product(ENDPOINTS, ENDPOINTS, PROTOCOLS, PORTS)
    ]


def permit_template(policy_id: str, protocol: str, ports: frozenset[int]) -> PolicyTemplate:
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=BINDING_SOURCE,
        destination=BINDING_DESTINATION,
        protocol=protocol,
        ports=ports,
        owner="infra-admin",
        rationale="declared need",
    )


def guard_template(policy_id: str, *, sources, destinations, protocol: str, ports: frozenset[int]) -> PolicyTemplate:
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.DENY,
        activation=Activation.SCOPE_GUARD,
        direction="transit",
        source=frozenset(sources),
        destination=frozenset(destinations),
        protocol=protocol,
        ports=ports,
        owner="security",
        rationale="mandatory",
    )


def _intent():
    """One permit, one guard that does not overlap it, and the scope."""
    dns = permit_template("policy.dns", "udp", frozenset({53}))
    grant = resolve_grant(
        dns,
        Binding(
            binding_id="bind.dns",
            policy_id="policy.dns",
            sources=frozenset({"zone.lan"}),
            destinations=frozenset({"zone.mgmt"}),
            approved=True,
        ),
    )
    guards = {
        "guard.no_guest_to_mgmt": guard_template(
            "guard.no_guest_to_mgmt",
            sources={"zone.guest"},
            destinations={"zone.mgmt"},
            protocol="tcp",
            ports=frozenset({22, 443}),
        )
    }
    return [grant], guards


def _plan(grants, guards, **kwargs):
    return lower(grants=grants, guards=guards, context=CONTEXT, endpoints=ENDPOINTS, protocols=PROTOCOLS, **kwargs)


def _authorized(grants, guards):
    authorized = authorize(grants, guards)
    return {
        (item.source, item.destination, item.protocol, item.port)
        for item in flow_space()
        if authorized.admits(item.source, item.destination, item.protocol, item.port)
    }


def _accepted(plan):
    return {(item.source, item.destination, item.protocol, item.port) for item in accepted_flows(plan, flow_space())}


# --- the independence that makes the rest evidence ------------------------------


def test_the_interpreter_shares_no_decision_code_with_the_producer() -> None:
    """G3: an oracle that imports the producer proves the code agrees with itself."""
    import ast
    from pathlib import Path

    module = Path(__file__).resolve().parents[2] / "netmodel" / "interpret.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = {"netmodel.policy", "netmodel.lower", "netmodel.candidates"}
    assert not (
        imported & forbidden
    ), f"the interpreter imports {sorted(imported & forbidden)}; it must decide from the plan alone"


# --- SEC-AUTH -------------------------------------------------------------------


def test_the_property_checks_are_not_vacuous() -> None:
    """A subset assertion over an empty set passes and proves nothing.

    Both SEC-AUTH and SEC-AVAIL are subset claims, and the cheapest way for them
    to be wrong is for one side to be empty. This is the same guard the address
    differential needed after it compared nothing for reading one field name
    wrong, and it is the rule for every property here.
    """
    grants, guards = _intent()
    plan = _plan(grants, guards)

    accepted = _accepted(plan)
    authorized = _authorized(grants, guards)

    assert len(flow_space()) >= 50, "the bounded space is too small to distinguish anything"
    assert accepted, "the plan accepts nothing; SEC-AUTH would hold vacuously"
    assert authorized, "the intent authorizes nothing; SEC-AVAIL would have nothing to require"
    assert len(accepted) < len(flow_space()), "the plan accepts everything; the space is not discriminating"


def test_sec_auth_every_accepted_flow_is_authorized() -> None:
    """`Accept(R) subseteq A_e`, checked over the whole bounded space."""
    grants, guards = _intent()
    plan = _plan(grants, guards)

    accepted = _accepted(plan)
    assert accepted, "nothing accepted; the subset claim below would be vacuous"

    unauthorized = accepted - _authorized(grants, guards)

    assert not unauthorized, f"the plan accepts flows the intent does not authorize: {sorted(unauthorized)}"


def test_sec_auth_fails_for_an_accept_all_mutant() -> None:
    """The mutant the contract names. If this passes, the check is worthless."""
    grants, guards = _intent()
    accept_all = [
        OrderedRule(
            rule=PlanRule(
                context=CONTEXT,
                effect=Effect.PERMIT,
                flow=Flow(
                    sources=frozenset(ENDPOINTS),
                    destinations=frozenset(ENDPOINTS),
                    protocol="tcp",
                    ports=frozenset(PORTS),
                ),
                origin="mutant:accept-all",
            ),
            position=0,
        )
    ]

    accepted = _accepted(accept_all)
    assert len(accepted) > len(_accepted(_plan(grants, guards))), "the mutant accepts no more than the real plan"

    unauthorized = accepted - _authorized(grants, guards)

    assert unauthorized, "an accept-all plan must violate SEC-AUTH; the checker cannot see it"


# --- SEC-AVAIL --------------------------------------------------------------------


def test_sec_avail_every_required_flow_is_accepted() -> None:
    """`Q_e subseteq Accept(R)`: what the intent requires, the plan delivers."""
    grants, guards = _intent()
    plan = _plan(grants, guards)
    required = {("zone.lan", "zone.mgmt", "udp", 53)}

    missing = required - _accepted(plan)

    assert not missing, f"the plan does not carry required flows: {sorted(missing)}"


def test_sec_avail_fails_for_an_all_drop_mutant() -> None:
    """An all-drop plan is not safe. It is broken, and differently so."""
    grants, guards = _intent()
    all_drop = _plan([], guards)
    required = {("zone.lan", "zone.mgmt", "udp", 53)}

    assert required - _accepted(all_drop), "an all-drop plan must violate SEC-AVAIL"
    assert not (_accepted(all_drop) - _authorized(grants, guards)), "and must still satisfy SEC-AUTH"


# --- monotonicity -------------------------------------------------------------------


def test_deleting_a_permit_cannot_enlarge_the_accepted_set() -> None:
    grants, guards = _intent()
    full = _accepted(_plan(grants, guards))
    reduced = _accepted(_plan([], guards))

    assert reduced <= full


def test_adding_a_deny_cannot_enlarge_the_accepted_set() -> None:
    grants, guards = _intent()
    before = _accepted(_plan(grants, {}))
    after = _accepted(_plan(grants, guards))

    assert after <= before


# --- the terminal rule ----------------------------------------------------------------


def test_nothing_executable_follows_the_terminal_deny() -> None:
    """ADR 0119 D4: the plan compiler owns its placement, so the plan can check it."""
    grants, guards = _intent()
    plan = _plan(grants, guards)

    terminal_positions = [entry.position for entry in plan if entry.rule.origin == TERMINAL_ORIGIN]
    assert terminal_positions, "the plan emitted no terminal deny"
    assert max(entry.position for entry in plan) == terminal_positions[-1]


def test_the_terminal_deny_closes_ports_no_rule_mentions() -> None:
    """A terminal that matched like an ordinary rule would leave the scope open."""
    grants, guards = _intent()
    plan = _plan(grants, guards)

    decision = interpret(plan, event("zone.guest", "zone.lan", "tcp", 443))

    assert decision.verdict is Verdict.DENY
    assert decision.matched == TERMINAL_ORIGIN


def test_without_a_terminal_an_unmatched_flow_is_unsupported_not_denied() -> None:
    """Default-deny is a property of a backend, and the plan must not assume one."""
    grants, guards = _intent()
    plan = _plan(grants, guards, terminal=False)

    decision = interpret(plan, event("zone.guest", "zone.lan", "tcp", 443))

    assert decision.verdict is Verdict.UNSUPPORTED


def test_a_terminal_needs_a_scope_to_close() -> None:
    grants, guards = _intent()

    with pytest.raises(ValueError, match="empty scope closes nothing"):
        lower(grants=grants, guards=guards, context=CONTEXT, endpoints=(), protocols=PROTOCOLS)


# --- guards beat permits, in the plan as in the algebra -----------------------------


def test_a_guard_denies_before_a_permit_that_would_accept() -> None:
    """The ordering exists for this; here it is observed through the interpreter."""
    overlapping = permit_template("policy.ssh", "tcp", frozenset({22}))
    grant = resolve_grant(
        overlapping,
        Binding(
            binding_id="bind.ssh",
            policy_id="policy.ssh",
            sources=frozenset({"zone.guest"}),
            destinations=frozenset({"zone.mgmt"}),
            approved=True,
        ),
    )
    _, guards = _intent()
    plan = _plan([grant], guards)

    decision = interpret(plan, event("zone.guest", "zone.mgmt", "tcp", 22))

    assert decision.verdict is Verdict.DENY
    assert decision.matched == "guard:guard.no_guest_to_mgmt"


def test_a_flow_in_another_context_is_not_decided_by_this_plan() -> None:
    grants, guards = _intent()
    plan = _plan(grants, guards)
    import dataclasses

    elsewhere = dataclasses.replace(event("zone.lan", "zone.mgmt", "udp", 53), hook="input")

    assert interpret(plan, elsewhere).verdict is Verdict.UNSUPPORTED


def test_an_empty_plan_decides_nothing() -> None:
    """Not an accept, and not a deny: there is nothing there to decide with."""
    assert interpret([], event("zone.lan", "zone.mgmt", "udp", 53)).verdict is Verdict.UNSUPPORTED
