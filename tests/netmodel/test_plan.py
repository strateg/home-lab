"""Checks for canonical ordering and plan identity.

The property tests here matter more than the unit ones. An ordering that happens
to be right for the inputs someone tried is worth very little; what is needed is
that it cannot depend on input order, and that the digest moves when meaning
moves and only then.
"""

from __future__ import annotations

import itertools
import random

import pytest

from netmodel.plan import (
    ExecutionContext,
    OrderedRule,
    PlanError,
    PlanRule,
    assert_consecutive,
    order_rules,
    plan_digest,
    precedence_edges,
)
from netmodel.policy import Effect, Flow

FORWARD = ExecutionContext(
    enforcer="rtr-example", routing_domain="main", family="ipv4", hook="forward", chain="managed"
)
INPUT = ExecutionContext(enforcer="rtr-example", routing_domain="main", family="ipv4", hook="input", chain="managed")


def flow(source: str, destination: str, port: int, protocol: str = "tcp") -> Flow:
    return Flow(
        sources=frozenset({source}),
        destinations=frozenset({destination}),
        protocol=protocol,
        ports=frozenset({port}),
    )


def permit(origin: str, *, port: int = 443, context: ExecutionContext = FORWARD) -> PlanRule:
    return PlanRule(context=context, effect=Effect.PERMIT, flow=flow("a", "b", port), origin=origin)


def guard(origin: str, *, port: int = 22, context: ExecutionContext = FORWARD) -> PlanRule:
    return PlanRule(context=context, effect=Effect.DENY, flow=flow("c", "d", port), origin=origin)


def terminal(origin: str = "terminal", *, context: ExecutionContext = FORWARD) -> PlanRule:
    return PlanRule(
        context=context, effect=Effect.DENY, flow=flow("any_source", "any_destination", 0), origin=origin, terminal=True
    )


def test_guards_precede_permits_in_the_same_context() -> None:
    ordered = order_rules([permit("p"), guard("g")])

    positions = {entry.rule.origin: entry.position for entry in ordered}
    assert positions["g"] < positions["p"]


def test_terminal_deny_comes_last_in_its_scope() -> None:
    ordered = order_rules([terminal(), permit("p"), guard("g")])

    assert ordered[-1].rule.terminal is True


def test_rules_in_different_contexts_have_no_ordering_relation() -> None:
    rules = [permit("p_forward"), permit("p_input", context=INPUT)]

    assert precedence_edges(rules) == set()


def test_a_terminal_in_one_context_does_not_order_another_context() -> None:
    rules = [permit("p_input", context=INPUT), terminal(context=FORWARD)]

    assert precedence_edges(rules) == set()


def test_positions_are_consecutive_from_zero() -> None:
    ordered = order_rules([permit(f"p{i}", port=400 + i) for i in range(5)] + [guard("g"), terminal()])

    assert_consecutive(ordered)
    assert len({entry.position for entry in ordered}) == len(ordered)


# --- the properties --------------------------------------------------------


def _plan(rules) -> list[str]:
    return [entry.rule.origin for entry in order_rules(rules)]


def test_input_order_cannot_change_the_plan() -> None:
    """A14: permutations of unordered inputs produce identical semantic plans."""
    rules = [permit("p1", port=443), permit("p2", port=80), guard("g1"), guard("g2", port=23), terminal()]
    expected = _plan(rules)

    for permutation in itertools.permutations(rules):
        assert _plan(list(permutation)) == expected


def test_ordering_is_stable_across_shuffles_of_many_rules() -> None:
    rules = [permit(f"p{i}", port=1000 + i) for i in range(40)] + [guard(f"g{i}", port=i) for i in range(10)]
    rules.append(terminal())
    expected = _plan(rules)

    rng = random.Random(20260911)
    for _ in range(20):
        shuffled = rules[:]
        rng.shuffle(shuffled)
        assert _plan(shuffled) == expected


def test_rules_differing_only_in_a_late_field_still_order_deterministically() -> None:
    """What a truncated hash would lose.

    These two differ only in origin, the last element of the canonical key. A
    shortened key would collide and leave their order undefined.
    """
    a = PlanRule(context=FORWARD, effect=Effect.PERMIT, flow=flow("a", "b", 443), origin="alpha")
    b = PlanRule(context=FORWARD, effect=Effect.PERMIT, flow=flow("a", "b", 443), origin="beta")

    assert _plan([a, b]) == _plan([b, a]) == ["alpha", "beta"]


def test_a_cycle_is_refused_with_the_rules_that_form_it() -> None:
    rules = [permit("p1"), permit("p2", port=80)]

    with pytest.raises(PlanError, match="precedence cycle"):
        order_rules(rules, extra_edges={(0, 1), (1, 0)})


def test_the_emitted_order_is_verified_against_its_own_edges() -> None:
    ordered = order_rules([permit("p"), guard("g"), terminal()])

    # An independently computed check, not a restatement of the sort.
    positions = {entry.rule.origin: entry.position for entry in ordered}
    assert positions["g"] < positions["p"] < positions["terminal"]


def test_digest_is_stable_for_the_same_plan() -> None:
    rules = [permit("p"), guard("g"), terminal()]

    first = plan_digest(order_rules(rules), profile="strict", intent_digest="sha256-intent")
    second = plan_digest(order_rules(list(reversed(rules))), profile="strict", intent_digest="sha256-intent")

    assert first == second


@pytest.mark.parametrize(
    ("mutate", "label"),
    [
        (lambda rules: rules + [permit("extra", port=8080)], "a rule added"),
        (lambda rules: rules[:-1], "a rule removed"),
        (lambda rules: [permit("p", port=444), rules[1], rules[2]], "a port changed"),
    ],
)
def test_digest_moves_when_meaning_moves(mutate, label: str) -> None:
    rules = [permit("p"), guard("g"), terminal()]
    baseline = plan_digest(order_rules(rules), profile="strict", intent_digest="sha256-intent")

    mutated = plan_digest(order_rules(mutate(rules)), profile="strict", intent_digest="sha256-intent")

    assert mutated != baseline, label


def test_digest_covers_profile_and_intent() -> None:
    ordered = order_rules([permit("p"), terminal()])
    baseline = plan_digest(ordered, profile="strict", intent_digest="sha256-a")

    assert plan_digest(ordered, profile="legacy", intent_digest="sha256-a") != baseline
    assert plan_digest(ordered, profile="strict", intent_digest="sha256-b") != baseline


def test_digest_excludes_time_by_construction() -> None:
    """Nothing time-shaped can reach the digest, because nothing carries it.

    A digest that moved every run could not distinguish an unchanged plan from a
    changed one, which is the only thing it is for.
    """
    import dataclasses

    time_words = {"timestamp", "generated_at", "compiled_at", "now", "time", "observed_at"}
    for field in dataclasses.fields(PlanRule) + dataclasses.fields(ExecutionContext) + dataclasses.fields(OrderedRule):
        assert not (set(field.name.split("_")) & time_words), f"{field.name} would put time into plan identity"


# --- the two paths must agree --------------------------------------------------


def _random_rules(rng: random.Random, count: int, context_names: list[str]) -> list[PlanRule]:
    contexts = {
        name: ExecutionContext(enforcer=name, routing_domain="main", family="ipv4", hook="forward", chain="managed")
        for name in context_names
    }
    rules: list[PlanRule] = []
    for index in range(count):
        kind = rng.choice(["permit", "permit", "permit", "deny", "terminal"])
        rules.append(
            PlanRule(
                context=contexts[rng.choice(context_names)],
                effect=Effect.PERMIT if kind == "permit" else Effect.DENY,
                flow=Flow(
                    sources=frozenset({f"s{rng.randrange(5)}"}),
                    destinations=frozenset({f"d{rng.randrange(5)}"}),
                    protocol=rng.choice(["tcp", "udp"]),
                    ports=frozenset({rng.randrange(1, 600)}),
                ),
                origin=f"r{index}",
                terminal=(kind == "terminal"),
            )
        )
    return rules


def test_the_structural_path_reproduces_the_general_one_exactly() -> None:
    """The claim that justifies not building the edge set.

    Inside one context the required precedence is a complete bipartite graph plus
    a sink, both of which two counters describe. Replacing the edges with the
    counters is only safe if the emitted sequence is identical, tie-breaking
    included - so both paths run over random inputs and the sequences are
    compared. An argument would not be evidence here; this is.
    """
    from netmodel.plan import _order_by_edges, _order_by_structure

    rng = random.Random(20260911)
    for _ in range(300):
        count = rng.randrange(1, 40)
        names = ["a", "b", "c"][: rng.randrange(1, 4)]
        rules = _random_rules(rng, count, names)

        by_edges = [entry.rule.origin for entry in _order_by_edges(rules, precedence_edges(rules))]
        by_structure = [entry.rule.origin for entry in _order_by_structure(rules)]

        assert by_edges == by_structure, f"paths disagree for {count} rules across {names}"


def test_ordering_does_not_build_the_edge_set() -> None:
    """A guard on complexity, not on speed.

    The edge count inside one context is denies x permits plus non-terminals:
    230,400 for 1,600 rules, millions for a real firewall. This asserts the work
    stays close to linear rather than asserting a wall-clock number, which would
    make the test a machine-speed detector.
    """
    import time

    def elapsed(count: int) -> float:
        """The best of three, because the slowest of three measures the machine.

        A single sample failed this in a full-suite run while passing in
        isolation: the scheduler, not the algorithm. Taking the minimum removes
        the noise that only ever inflates a measurement, and leaves the
        complexity claim exactly as strong.
        """
        rules = [permit(f"p{i}", port=1000 + i) for i in range(count)]
        rules += [guard(f"g{i}", port=i + 1) for i in range(count // 10)]
        rules.append(terminal())

        samples = []
        for _ in range(3):
            start = time.perf_counter()
            order_rules(rules)
            samples.append(time.perf_counter() - start)
        return min(samples)

    small = elapsed(400)
    large = elapsed(1600)

    # Quadratic would be ~16x for a 4x input. Allow generous headroom for a noisy
    # machine and still fail long before the old behaviour would pass.
    assert large < small * 8, f"ordering is scaling superlinearly: {small:.4f}s -> {large:.4f}s"


def test_a_rule_after_the_terminal_is_caught_by_the_structural_check() -> None:
    """verify_structure must reject what verify_edges would have rejected."""
    from netmodel.plan import OrderedRule, verify_structure

    bad = [
        OrderedRule(rule=terminal(), position=0),
        OrderedRule(rule=permit("p"), position=1),
    ]

    with pytest.raises(PlanError, match="follows the terminal"):
        verify_structure(bad)


def test_a_deny_after_a_permit_is_caught_by_the_structural_check() -> None:
    from netmodel.plan import OrderedRule, verify_structure

    bad = [
        OrderedRule(rule=permit("p"), position=0),
        OrderedRule(rule=guard("g"), position=1),
    ]

    with pytest.raises(PlanError, match="mandatory deny follows a permit"):
        verify_structure(bad)
