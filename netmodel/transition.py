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

**Proving a sequence is more than checking its middle.** The first version
simulated whatever a strategy returned and asked one question of each state, so a
strategy that mutated nothing proved a transition it never performed: no steps, no
violations, `[]` returned as success. A review supplied the probe - an empty flow
space and an expired envelope carrying arbitrary digests - and got a clean answer.
Five things are checked now, and each of them was a way to pass without proving
anything:

* **Preconditions.** The envelope's digests must be the digests of *these* plans,
  and the envelope must not have expired as of a moment the caller supplies.
* **A flow space that could show a failure.** An empty one cannot, and neither can
  one that omits flows the envelope admits or the new plan must carry.
* **A complete replay.** The mutations a strategy returns must be exactly the diff
  between the two plans - no rule left behind, none invented, none applied twice.
* **Arrival.** The final state must *be* the new plan, not merely a safe one.
* **Postconditions.** `Accept(R_final) subseteq A_new`, and every flow the new
  plan is required to carry is carried at the end.

**An unmatched flow is not a safe one.** `UNSUPPORTED` was skipped alongside
`DENY`, and they are opposites: `DENY` is a rule saying no, `UNSUPPORTED` is no
rule at all. On a default-allow backend that is an open flow, and the transition
window where a terminal deny has been removed and not yet replaced is exactly
where it appears.

What this still does not prove is the concrete device sequence. The simulator
re-derives canonical order at every step, so it reasons about rule *sets*, not
about the RouterOS or Terraform operations that realise them. That is a
backend-level test contract and it is deliberately out of scope here.
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


OUTSIDE_ENVELOPE = "outside_envelope"
UNMATCHED = "unmatched"


@dataclass(frozen=True, slots=True)
class Violation:
    """A flow an intermediate state gets wrong: accepted too widely, or unmatched."""

    step: int
    action: str
    rule_origin: str
    flow: tuple[str, str, str, int]
    matched: str | None
    kind: str = OUTSIDE_ENVELOPE

    def __str__(self) -> str:
        source, destination, protocol, port = self.flow
        where = f"step {self.step} ({self.action} {self.rule_origin})"
        if self.kind == UNMATCHED:
            return (
                f"{where} leaves {source} -> {destination} {protocol}/{port} matching no rule at all; "
                "on a default-allow backend that is an open flow, and `no rule said no` is not `a rule said no`"
            )
        return (
            f"{where} accepts {source} -> {destination} {protocol}/{port} via {self.matched}, "
            "which the envelope does not admit"
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

            if decision.verdict is Verdict.UNSUPPORTED:
                # Not skipped alongside DENY any more. They are opposites: a deny
                # is a rule saying no, and this is no rule at all. The window
                # where a terminal has been removed and not yet replaced is
                # exactly where it shows up.
                violations.append(
                    Violation(
                        step=step.index,
                        action=step.action,
                        rule_origin=step.rule_origin,
                        flow=event.authorizing.key(),
                        matched=None,
                        kind=UNMATCHED,
                    )
                )
                continue

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
                    kind=OUTSIDE_ENVELOPE,
                )
            )
    return violations


def state_digest(ordered: Sequence[OrderedRule]) -> str:
    """The identity of a rule set, for tying an envelope to the plans it names.

    `plan_digest` also carries the profile and the intent it lowers, which a
    transition envelope has no opinion about. This is the structural half: the
    canonical keys in their canonical order.
    """
    import hashlib
    import json

    payload = [
        [entry.position, [str(item) for item in entry.rule.canonical_key()]] for entry in ordered
    ]
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _check_preconditions(
    *,
    old: Sequence[OrderedRule],
    new: Sequence[OrderedRule],
    envelope: Envelope,
    flow_space: Sequence[FlowEvent],
    as_of: str,
    new_allowed: frozenset[tuple[str, str, str, int]],
    required_flows: frozenset[tuple[str, str, str, int]],
) -> None:
    """Everything that must hold before a simulation can mean anything."""
    if not str(as_of or "").strip():
        raise TransitionError(
            "no moment was supplied, so the envelope's expiry cannot be checked; a proof valid at "
            "no stated time is valid at none"
        )
    if envelope.expiry < as_of:
        raise TransitionError(
            f"the envelope expired at {envelope.expiry} and this is {as_of}; an expired authorization "
            "is not a narrower one"
        )

    actual_old, actual_new = state_digest(old), state_digest(new)
    if envelope.old_digest != actual_old:
        raise TransitionError(
            f"the envelope authorizes a transition from {envelope.old_digest[:19]} and this one starts "
            f"at {actual_old[:19]}"
        )
    if envelope.new_digest != actual_new:
        raise TransitionError(
            f"the envelope authorizes a transition to {envelope.new_digest[:19]} and this one arrives "
            f"at {actual_new[:19]}"
        )

    if not flow_space:
        raise TransitionError(
            "the flow space is empty, so every state accepts nothing and every check passes; "
            "an empty probe set proves the probe set, not the transition"
        )

    probed = {event.authorizing.key() for event in flow_space}
    unprobed = sorted((envelope.allowed | required_flows) - probed)
    if unprobed:
        raise TransitionError(
            f"the flow space omits {len(unprobed)} flow(s) the envelope admits or the new plan must "
            f"carry, so nothing was asked about them: {unprobed[:3]}"
        )
    if not (new_allowed >= required_flows):
        raise TransitionError(
            f"flows required to keep working are outside what the new plan authorizes: "
            f"{sorted(required_flows - new_allowed)[:3]}"
        )


def _check_replay(
    *, old: Sequence[OrderedRule], new: Sequence[OrderedRule], mutations: Sequence[Mutation]
) -> None:
    """The strategy must perform exactly the transition, not a subset of it.

    A strategy returning nothing produced no steps, and no steps produced no
    violations - a transition proved safe by never being attempted. Comparing the
    multiset also catches a rule applied twice, which a set comparison would call
    equal.
    """
    additions, removals = diff(old, new)
    expected = sorted(
        (mutation.action, str(mutation.rule.canonical_key())) for mutation in (*additions, *removals)
    )
    performed = sorted((mutation.action, str(mutation.rule.canonical_key())) for mutation in mutations)

    if performed == expected:
        return

    missing = [item for item in expected if performed.count(item) < expected.count(item)]
    extra = [item for item in performed if expected.count(item) < performed.count(item)]
    detail = []
    if missing:
        detail.append(f"never performed: {sorted({item[0] + ' ' + item[1] for item in missing})[:3]}")
    if extra:
        detail.append(f"performed but not required: {sorted({item[0] + ' ' + item[1] for item in extra})[:3]}")
    raise TransitionError(
        "the proposed sequence is not this transition - " + "; ".join(detail or ["the mutations differ"])
    )


def _check_arrival(
    *, steps: Sequence[Step], new: Sequence[OrderedRule], envelope: Envelope
) -> tuple[OrderedRule, ...]:
    """The final state must be the new plan, not merely a safe one."""
    final = steps[-1].state if steps else ()
    reached = state_digest(final)
    if reached != envelope.new_digest:
        raise TransitionError(
            f"the sequence ends at {reached[:19]} and the new plan is {envelope.new_digest[:19]}; "
            "a sequence that stops somewhere safe has not applied the plan"
        )
    return final


def _check_postconditions(
    *,
    final: Sequence[OrderedRule],
    flow_space: Sequence[FlowEvent],
    new_allowed: frozenset[tuple[str, str, str, int]],
    required_flows: frozenset[tuple[str, str, str, int]],
) -> None:
    """`Accept(R_final) subseteq A_new`, and what has to keep working still does."""
    accepted: set[tuple[str, str, str, int]] = set()
    unmatched: list[tuple[str, str, str, int]] = []
    for event in flow_space:
        decision = interpret(final, event)
        if decision.verdict is Verdict.ACCEPT:
            accepted.add(event.authorizing.key())
        elif decision.verdict is Verdict.UNSUPPORTED:
            unmatched.append(event.authorizing.key())

    if unmatched:
        raise TransitionError(
            f"the final state leaves {len(unmatched)} flow(s) matching no rule: {sorted(unmatched)[:3]}"
        )

    unauthorized = sorted(accepted - new_allowed)
    if unauthorized:
        raise TransitionError(
            f"the final state accepts what the new plan does not authorize: {unauthorized[:3]}"
        )

    dropped = sorted(required_flows - accepted)
    if dropped:
        raise TransitionError(
            f"the final state does not carry {len(dropped)} flow(s) the new plan must keep working: "
            f"{dropped[:3]}"
        )


def plan_transition(
    *,
    old: Sequence[OrderedRule],
    new: Sequence[OrderedRule],
    envelope: Envelope,
    flow_space: Sequence[FlowEvent],
    as_of: str,
    new_allowed: frozenset[tuple[str, str, str, int]],
    required_flows: frozenset[tuple[str, str, str, int]] = frozenset(),
    strategy: Callable[[Sequence[OrderedRule], Sequence[OrderedRule]], list[Mutation]] = safe_order,
) -> list[Step]:
    """Propose an order, simulate it, and refuse it unless the whole thing holds.

    Refusal is the useful outcome here. A transition that cannot be shown safe is
    not one to perform carefully; the contract says it blocks deploy.

    `new_allowed` is `A_new`, computed by the caller for the same reason the
    envelope's `allowed` is: deriving authorization here would decide it in a
    third place. `required_flows` is the availability objective - what has to be
    working when the apply finishes - and an empty one is a statement that
    nothing does.
    """
    _check_preconditions(
        old=old,
        new=new,
        envelope=envelope,
        flow_space=flow_space,
        as_of=as_of,
        new_allowed=new_allowed,
        required_flows=required_flows,
    )

    mutations = strategy(old, new)
    _check_replay(old=old, new=new, mutations=mutations)

    steps = simulate(old, mutations)
    violations = check_sequence(steps, envelope, flow_space)
    if violations:
        raise TransitionError("no safe sequence: " + "; ".join(str(violation) for violation in violations[:5]))

    final = _check_arrival(steps=steps, new=new, envelope=envelope)
    _check_postconditions(
        final=final,
        flow_space=flow_space,
        new_allowed=new_allowed,
        required_flows=required_flows,
    )
    return steps


__all__ = [
    "OUTSIDE_ENVELOPE",
    "UNMATCHED",
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
    "state_digest",
]
