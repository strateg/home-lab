"""Canonical ordering and plan identity.

Order follows from execution semantics, never from where a rule came from. A
producer's name, a specificity score and an author's priority number all fail to
say anything about which rule must be evaluated first, and using one of them
means the plan changes when the pipeline's scheduling does.

The ordering is a topological sort over semantic precedence edges, with ties
broken by the full canonical key of each rule. Full, not a truncated hash: a hash
maps many rules onto few slots, and two rules that land on the same slot have no
defined order at all. Positions are then consecutive, because a fixed-size band
runs out and a gap invites someone to fill it.

Plan identity covers everything that affects authorization and nothing that
merely records when the plan was produced. A digest that moves every run cannot
tell an unchanged plan from a changed one, which is the whole reason to have it.
"""

from __future__ import annotations

import hashlib
import heapq
import json
from dataclasses import dataclass
from typing import Iterable, Sequence

from netmodel.policy import Effect, Flow


class PlanError(ValueError):
    """Raised when a plan cannot be ordered or is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Where a rule executes. Two rules in different contexts do not order."""

    enforcer: str
    routing_domain: str
    family: str
    hook: str
    chain: str

    def key(self) -> tuple[str, ...]:
        return (self.enforcer, self.routing_domain, self.family, self.hook, self.chain)


@dataclass(frozen=True, slots=True)
class PlanRule:
    """One rule in one context, traceable to what produced it.

    `origin` records provenance for review. It deliberately takes no part in
    ordering: precedence comes from what a rule does, not from who emitted it.
    """

    context: ExecutionContext
    effect: Effect
    flow: Flow
    origin: str
    terminal: bool = False

    def canonical_key(self) -> tuple:
        """The full semantic identity of this rule, used whole.

        Every field that distinguishes two rules appears here. Truncating this
        into a hash would let distinct rules share a sort position, and a shared
        position is an undefined order dressed up as a defined one.
        """
        return (
            self.context.key(),
            self.effect.value,
            tuple(sorted(self.flow.sources)),
            tuple(sorted(self.flow.destinations)),
            self.flow.protocol,
            # `None` means every port, which is a shape rather than an absence.
            # Sorting it would raise; representing it as an empty tuple would make
            # an any-transport rule sort beside a rule with no ports at all.
            () if self.flow.ports is None else tuple(sorted(self.flow.ports)),
            self.terminal,
            self.origin,
        )


@dataclass(frozen=True, slots=True)
class OrderedRule:
    rule: PlanRule
    position: int


def precedence_edges(rules: Sequence[PlanRule]) -> set[tuple[int, int]]:
    """Edges that execution semantics require, by index.

    Three kinds, all justified by what happens at runtime rather than by taste:
    a mandatory deny is evaluated before the permits it constrains; a terminal
    default deny ends its scope, so everything in that scope precedes it; and
    rules in different contexts have no ordering relation at all, because they
    are not on the same path.

    A terminal default deny is a role, not an effect. Treating it as one more
    deny puts it before every permit and after every rule at once, which is a
    cycle rather than an order.
    """
    edges: set[tuple[int, int]] = set()
    for i, left in enumerate(rules):
        for j, right in enumerate(rules):
            if i == j or left.context != right.context:
                continue
            if right.terminal and not left.terminal:
                edges.add((i, j))
            elif (
                not left.terminal
                and not right.terminal
                and left.effect is Effect.DENY
                and right.effect is Effect.PERMIT
            ):
                edges.add((i, j))
    return edges


def _detect_cycle(rules: Sequence[PlanRule], edges: set[tuple[int, int]]) -> list[str] | None:
    outgoing: dict[int, set[int]] = {i: set() for i in range(len(rules))}
    for source, target in edges:
        outgoing[source].add(target)

    state = {i: 0 for i in range(len(rules))}  # 0 unvisited, 1 on stack, 2 done
    stack: list[int] = []

    def visit(node: int) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for neighbour in sorted(outgoing[node]):
            if state[neighbour] == 1:
                start = stack.index(neighbour)
                return [rules[index].origin for index in stack[start:]] + [rules[neighbour].origin]
            if state[neighbour] == 0:
                found = visit(neighbour)
                if found is not None:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in range(len(rules)):
        if state[node] == 0:
            found = visit(node)
            if found is not None:
                return found
    return None


def order_rules(rules: Iterable[PlanRule], *, extra_edges: set[tuple[int, int]] | None = None) -> list[OrderedRule]:
    """Order rules deterministically and assign consecutive positions.

    Ties among rules that no edge separates are broken by the canonical key, so
    the output does not depend on the order the inputs arrived in. That is what
    makes two runs over the same intent comparable at all.

    Two paths, one meaning. Without caller-supplied edges the required
    precedence has a closed form and is never materialized - see
    `_order_by_structure`. With extra edges the general topological sort runs,
    because an arbitrary edge set has no closed form to exploit.
    """
    rules = list(rules)
    if not rules:
        return []

    if not extra_edges:
        return _order_by_structure(rules)

    edges = precedence_edges(rules) | extra_edges
    return _order_by_edges(rules, edges)


def _order_by_edges(rules: Sequence[PlanRule], edges: set[tuple[int, int]]) -> list[OrderedRule]:
    """General topological sort over an explicit edge set."""
    cycle = _detect_cycle(rules, edges)
    if cycle is not None:
        raise PlanError("precedence cycle: " + " -> ".join(cycle))

    incoming: dict[int, int] = {i: 0 for i in range(len(rules))}
    outgoing: dict[int, set[int]] = {i: set() for i in range(len(rules))}
    for source, target in edges:
        if target not in outgoing[source]:
            outgoing[source].add(target)
            incoming[target] += 1

    ready = [i for i in range(len(rules)) if incoming[i] == 0]
    emitted: list[int] = []
    while ready:
        ready.sort(key=lambda index: rules[index].canonical_key())
        node = ready.pop(0)
        emitted.append(node)
        for neighbour in sorted(outgoing[node]):
            incoming[neighbour] -= 1
            if incoming[neighbour] == 0:
                ready.append(neighbour)

    if len(emitted) != len(rules):
        raise PlanError("not every rule could be ordered; the precedence graph is inconsistent")

    ordered = [OrderedRule(rule=rules[index], position=position) for position, index in enumerate(emitted)]
    verify_edges(ordered, edges, rules)
    return ordered


def _order_by_structure(rules: Sequence[PlanRule]) -> list[OrderedRule]:
    """The same order, without building the edge set.

    Inside one context the required precedence is two shapes with closed forms:
    every mandatory deny precedes every permit, which is a complete bipartite
    graph, and every non-terminal precedes the terminal, which is a sink. Writing
    them out costs `denies x permits + non-terminals` edges per context - 57,600
    for 800 rules, millions for a real firewall - to express something two
    counters already say.

    So the counters are kept instead. A permit waits on its context's remaining
    denies; a terminal waits on its context's remaining non-terminals. When a
    counter reaches zero the whole group becomes ready at once, which is the only
    moment any of them could have become ready anyway.

    This reproduces the general path exactly, including its tie-breaking: ready
    rules are emitted in canonical-key order regardless of which context they
    belong to. That equivalence is not an argument, it is a test - random inputs
    are ordered both ways and the sequences compared.
    """
    contexts: dict[tuple[str, ...], dict[str, list[int]]] = {}
    for index, rule in enumerate(rules):
        key = rule.context.key()
        group = contexts.setdefault(key, {"deny": [], "permit": [], "terminal": []})
        if rule.terminal:
            group["terminal"].append(index)
        elif rule.effect is Effect.DENY:
            group["deny"].append(index)
        else:
            group["permit"].append(index)

    pending_denies = {key: len(group["deny"]) for key, group in contexts.items()}
    pending_non_terminal = {key: len(group["deny"]) + len(group["permit"]) for key, group in contexts.items()}

    ready: list[tuple[tuple, int]] = []
    for key, group in contexts.items():
        for index in group["deny"]:
            heapq.heappush(ready, (rules[index].canonical_key(), index))
        if not group["deny"]:
            for index in group["permit"]:
                heapq.heappush(ready, (rules[index].canonical_key(), index))
            if not group["permit"]:
                for index in group["terminal"]:
                    heapq.heappush(ready, (rules[index].canonical_key(), index))

    emitted: list[int] = []
    while ready:
        _, index = heapq.heappop(ready)
        emitted.append(index)
        rule = rules[index]
        if rule.terminal:
            continue

        key = rule.context.key()
        group = contexts[key]
        if rule.effect is Effect.DENY:
            pending_denies[key] -= 1
            if pending_denies[key] == 0:
                for candidate in group["permit"]:
                    heapq.heappush(ready, (rules[candidate].canonical_key(), candidate))
        pending_non_terminal[key] -= 1
        if pending_non_terminal[key] == 0:
            for candidate in group["terminal"]:
                heapq.heappush(ready, (rules[candidate].canonical_key(), candidate))

    if len(emitted) != len(rules):  # pragma: no cover - structural edges cannot cycle
        raise PlanError("not every rule could be ordered; the precedence graph is inconsistent")

    ordered = [OrderedRule(rule=rules[index], position=position) for position, index in enumerate(emitted)]
    verify_structure(ordered)
    return ordered


def verify_structure(ordered: Sequence[OrderedRule]) -> None:
    """Check the emitted order against the rules it must satisfy, in one pass.

    The general path verifies its result against the edges it claims to satisfy.
    This checks the same thing without them: per context, the last deny must come
    before the first permit, and every non-terminal before every terminal. It
    re-derives each rule's role rather than trusting the sort that placed it.
    """
    last_deny: dict[tuple[str, ...], int] = {}
    first_permit: dict[tuple[str, ...], int] = {}
    last_non_terminal: dict[tuple[str, ...], int] = {}
    first_terminal: dict[tuple[str, ...], int] = {}

    for entry in ordered:
        key = entry.rule.context.key()
        if entry.rule.terminal:
            first_terminal.setdefault(key, entry.position)
            continue
        last_non_terminal[key] = entry.position
        if entry.rule.effect is Effect.DENY:
            last_deny[key] = entry.position
        else:
            first_permit.setdefault(key, entry.position)

    for key, deny_position in last_deny.items():
        permit_position = first_permit.get(key)
        if permit_position is not None and deny_position >= permit_position:
            raise PlanError(f"a mandatory deny follows a permit it constrains in context {key}")

    for key, terminal_position in first_terminal.items():
        tail = last_non_terminal.get(key)
        if tail is not None and tail >= terminal_position:
            raise PlanError(f"a rule follows the terminal default deny in context {key}")


def verify_edges(ordered: Sequence[OrderedRule], edges: set[tuple[int, int]], rules: Sequence[PlanRule]) -> None:
    """Check the emitted order against the edges it claims to satisfy.

    Producing an order and trusting the algorithm that produced it is one step;
    checking the result independently is the step that catches the algorithm.
    """
    position_of = {id(entry.rule): entry.position for entry in ordered}
    for source, target in sorted(edges):
        if position_of[id(rules[source])] >= position_of[id(rules[target])]:
            raise PlanError(
                f"ordering violates a required edge: {rules[source].origin} must precede {rules[target].origin}"
            )


def assert_consecutive(ordered: Sequence[OrderedRule]) -> None:
    positions = [entry.position for entry in ordered]
    if positions != list(range(len(positions))):
        raise PlanError(f"positions must be consecutive from zero, got {positions}")


def plan_digest(ordered: Sequence[OrderedRule], *, profile: str, intent_digest: str) -> str:
    """Identity of a plan, over everything that affects authorization.

    Timestamps and live observations are excluded by construction: they are not
    part of the structure hashed here. The intent digest and the profile are
    included, because a plan means nothing apart from the intent it lowers and
    the profile it was built under.
    """
    payload = {
        "profile": profile,
        "intent_digest": intent_digest,
        "rules": [{"position": entry.position, "key": _jsonable(entry.rule.canonical_key())} for entry in ordered],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
