"""Lower authorized intent into an ordered rule plan.

This is the producing half of W06. It takes what the intent says is authorized -
approved bound permits, mandatory denies, and the scopes that need closing - and
emits rules in execution contexts, ordered by `netmodel.plan`.

It decides nothing about whether a flow is authorized. That decision was already
made by `netmodel.policy`, and re-deciding it here would put the same question in
two places that could answer differently. What this module does is *translate*: a
grant becomes a permit rule, a guard becomes a deny rule, a scope gets a terminal
default deny, and the ordering follows from execution semantics.

The terminal deny is a plan obligation, not a template flourish. ADR 0119 D4 says
the plan compiler emits it and the backend template only renders it, because a
terminal rule that a template adds is a terminal rule the plan cannot reason
about - and "is anything reachable after the drop-all" is exactly the question the
plan has to answer.

Nothing here reads the interpreter, and the interpreter does not read this. That
separation is the whole point: an oracle that shares the producer's decision code
proves the code agrees with itself.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from netmodel.plan import ExecutionContext, OrderedRule, PlanRule, order_rules
from netmodel.policy import Effect, Flow, Grant, PolicyTemplate, guard_flow

TERMINAL_ORIGIN = "plan:terminal-default-deny"


def _permit_rules(grants: Iterable[Grant], context: ExecutionContext) -> list[PlanRule]:
    return [
        PlanRule(
            context=context,
            effect=Effect.PERMIT,
            flow=grant.flow,
            origin=f"binding:{grant.binding_id}",
        )
        for grant in grants
    ]


def _guard_rules(guards: Mapping[str, PolicyTemplate], context: ExecutionContext) -> list[PlanRule]:
    return [
        PlanRule(
            context=context,
            effect=Effect.DENY,
            flow=guard_flow(template),
            origin=f"guard:{guard_id}",
        )
        for guard_id, template in sorted(guards.items())
    ]


def terminal_rule(context: ExecutionContext, *, endpoints: Sequence[str], protocols: Sequence[str]) -> PlanRule:
    """The rule that closes a scope.

    Its flow is the whole declared scope rather than a wildcard, because the
    interpreter matches on sets and a wildcard would be a second matching rule
    with different semantics from every other rule in the plan.
    """
    if not endpoints or not protocols:
        raise ValueError("a terminal deny needs a declared scope to close; an empty scope closes nothing")
    return PlanRule(
        context=context,
        effect=Effect.DENY,
        flow=Flow(
            sources=frozenset(endpoints),
            destinations=frozenset(endpoints),
            protocol=protocols[0],
            ports=frozenset({0}),
        ),
        origin=TERMINAL_ORIGIN,
        terminal=True,
    )


def lower(
    *,
    grants: Iterable[Grant],
    guards: Mapping[str, PolicyTemplate],
    context: ExecutionContext,
    endpoints: Sequence[str],
    protocols: Sequence[str] = ("tcp",),
    terminal: bool = True,
) -> list[OrderedRule]:
    """Produce the ordered plan for one execution context.

    `terminal=False` exists for tests that need a plan without a closing rule -
    on a default-deny backend the terminal is redundant, and the model must be
    able to express both without the interpreter guessing which it is looking at.
    """
    rules = _guard_rules(guards, context) + _permit_rules(grants, context)
    if terminal:
        rules.append(terminal_rule(context, endpoints=endpoints, protocols=protocols))
    return order_rules(rules)


__all__ = ["TERMINAL_ORIGIN", "lower", "terminal_rule"]
