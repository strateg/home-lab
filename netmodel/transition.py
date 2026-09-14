"""Getting from one plan to another without opening something on the way.

The formal contract's section 5 asks for a transition authorization envelope
`T(t)` and one property over it: for every intermediate ruleset `R_t` reached
during an apply, `Accept(R_t) subseteq T(t)`, and at completion
`Accept(R_final) subseteq A_new`. Failure to prove a safe sequence blocks deploy.

The part that is easy to miss is that **the order rules are applied in is part of
the security argument**. Both the old plan and the new one can be correct while a
particular way of getting between them is not: drop a mandatory deny first and,
for as long as the apply takes, every permit it used to constrain is live. The
final state looks perfect afterwards, and nothing in it records that the window
existed.

So this module does not check a plan. It checks a *sequence*, and refuses to
propose one it cannot prove.

Two things it deliberately does not do. It does not invent a universal timeout -
the contract says not to, and an expiry belongs to a deployment profile. And it
does not widen the envelope to make a sequence fit: an envelope is no broader
than the approved old and new grants with the current mandatory denies removed,
and a transition that needs more than that needs separate review, not an implicit
union.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from netmodel.interpret import FlowEvent, Verdict, interpret
from netmodel.plan import OrderedRule, PlanRule, assert_consecutive, order_rules


class TransitionError(ValueError):
    """Raised when a transition cannot be shown safe."""


@dataclass(frozen=True, slots=True)
class Envelope:
    """What may be accepted at any moment during the transition.

    `allowed` is the flow set, computed by the caller as the approved old and new
    grants with the new mandatory denies removed. It is passed in rather than
    derived here, because deriving it would mean re-deciding authorization in a
    third place.
    """

    old_digest: str
    new_digest: str
    allowed: frozenset[tuple[str, str, str, int]]
    expiry: str

    def __post_init__(self) -> None:
        for name in ("old_digest", "new_digest", "expiry"):
            if not str(getattr(self, name) or "").strip():
                raise TransitionError(f"an envelope without {name} is not tied to anything")
        if self.old_digest == self.new_digest:
            raise TransitionError("old and new digests are equal; there is no transition to authorize")

    def admits(self, event: FlowEvent) -> bool:
        return event.authorizing.key() in self.allowed


@dataclass(frozen=True, slots=True)
class Mutation:
    """One rule going in or out. A strategy orders these; it does not build states."""

    action: str
    rule: PlanRule

    def __post_init__(self) -> None:
        if self.action not in ("add", "remove"):
            raise TransitionError(f"unknown mutation {self.action!r}")

    @property
    def is_guard(self) -> bool:
        return self.rule.effect.value == "deny" or self.rule.terminal


@dataclass(frozen=True, slots=True)
class Step:
    """One mutation in the sequence, and the state it produces."""

    index: int
    action: str
    rule_origin: str
    state: tuple[OrderedRule, ...]


@dataclass(frozen=True, slots=True)
class Violation:
    """A flow some intermediate state accepts that the envelope does not admit."""

    step: int
    action: str
    rule_origin: str
    flow: tuple[str, str, str, int]
    matched: str | None

    def __str__(self) -> str:
        source, destination, protocol, port = self.flow
        return (
            f"step {self.step} ({self.action} {self.rule_origin}) accepts "
            f"{source} -> {destination} {protocol}/{port} via {self.matched}, which the envelope does not admit"
        )


def _renumber(rules: Iterable[PlanRule]) -> tuple[OrderedRule, ...]:
    ordered = order_rules(rules)
    assert_consecutive(ordered)
    return tuple(ordered)


def diff(old: Sequence[OrderedRule], new: Sequence[OrderedRule]) -> tuple[list[Mutation], list[Mutation]]:
    """What has to be added, and what has to be removed, in canonical order."""
    old_rules = {entry.rule.canonical_key(): entry.rule for entry in old}
    new_rules = {entry.rule.canonical_key(): entry.rule for entry in new}

    additions = [Mutation("add", rule) for key, rule in sorted(new_rules.items()) if key not in old_rules]
    removals = [Mutation("remove", rule) for key, rule in sorted(old_rules.items()) if key not in new_rules]
    return additions, removals


def safe_order(old: Sequence[OrderedRule], new: Sequence[OrderedRule]) -> list[Mutation]:
    """Denies in before permits; permits out before denies.

    The order is not a preference. Adding every new mandatory deny before any new
    permit means no moment exists where a new permit is live without its guard.
    Removing permits before the denies that constrained them means no moment
    exists where an old permit outlives its guard either. Together they make the
    window the contract asks about empty rather than short.

    A strategy returns *mutations*, not states. That separation was a defect
    before it was a design: the first version handed back finished steps with
    their states already computed, so an alternative strategy that reordered them
    shuffled the labels while every state stayed as the default order had built
    it - the unsafe sequence it was supposed to model never existed, and the test
    that expected a violation found none. States are now computed from whatever
    order a strategy returns, so a strategy can actually be wrong.
    """
    additions, removals = diff(old, new)
    guards_first = sorted(additions, key=lambda item: (not item.is_guard, item.rule.canonical_key()))
    permits_first = sorted(removals, key=lambda item: (item.is_guard, item.rule.canonical_key()))
    return guards_first + permits_first


def simulate(old: Sequence[OrderedRule], mutations: Sequence[Mutation]) -> list[Step]:
    """Apply mutations in the given order and record the state after each.

    This is the only place a state is built, so every strategy is simulated the
    same way and none can present a state its own order would not have produced.
    """
    current = {entry.rule.canonical_key(): entry.rule for entry in old}
    steps: list[Step] = []

    for mutation in mutations:
        key = mutation.rule.canonical_key()
        if mutation.action == "add":
            current[key] = mutation.rule
        else:
            current.pop(key, None)
        steps.append(
            Step(
                index=len(steps),
                action=mutation.action,
                rule_origin=mutation.rule.origin,
                state=_renumber(current.values()),
            )
        )
    return steps


def build_sequence(old: Sequence[OrderedRule], new: Sequence[OrderedRule]) -> list[Step]:
    """The default strategy, simulated."""
    return simulate(old, safe_order(old, new))


def check_sequence(steps: Sequence[Step], envelope: Envelope, flow_space: Sequence[FlowEvent]) -> list[Violation]:
    """Every intermediate state, against the envelope. `Accept(R_t) subseteq T(t)`.

    Checking only the endpoints would miss the whole class of defect this exists
    for: both ends can be correct while a state between them is not.
    """
    violations: list[Violation] = []
    for step in steps:
        for event in flow_space:
            decision = interpret(step.state, event)
            if decision.verdict is not Verdict.ACCEPT:
                continue
            if envelope.admits(event):
                continue
            violations.append(
                Violation(
                    step=step.index,
                    action=step.action,
                    rule_origin=step.rule_origin,
                    flow=event.authorizing.key(),
                    matched=decision.matched,
                )
            )
    return violations


def plan_transition(
    *,
    old: Sequence[OrderedRule],
    new: Sequence[OrderedRule],
    envelope: Envelope,
    flow_space: Sequence[FlowEvent],
    strategy: Callable[[Sequence[OrderedRule], Sequence[OrderedRule]], list[Mutation]] = safe_order,
) -> list[Step]:
    """Propose an order, simulate it, and refuse it unless every state holds.

    Refusal is the useful outcome here. A transition that cannot be shown safe is
    not one to perform carefully; the contract says it blocks deploy.
    """
    steps = simulate(old, strategy(old, new))
    violations = check_sequence(steps, envelope, flow_space)
    if violations:
        raise TransitionError("no safe sequence: " + "; ".join(str(violation) for violation in violations[:5]))
    return steps


__all__ = [
    "Envelope",
    "Mutation",
    "Step",
    "TransitionError",
    "Violation",
    "build_sequence",
    "check_sequence",
    "diff",
    "plan_transition",
    "safe_order",
    "simulate",
]
