#!/usr/bin/env python3
"""The independent check over the published plan.

*Independently* is the requirement, not a description. A validator that called
the compiler's sort would compare the sort with itself and report agreement,
which is precisely what G3 forbids: do not make the generator and the oracle
share the same decision code and call the agreement a proof.

So the tests that matter are the ones where a deliberately wrong plan is handed
in and the validator has to say so. A checker that has only ever seen correct
plans has demonstrated nothing.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402

from tests.helpers.plugin_execution import publish_for_test  # noqa: E402

PLUGIN_ID = "base.validator.security_plan"
PLAN_PLUGIN_ID = "base.compiler.security_plan"
SCOPE = "inst.security_matrix.m"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def rule(origin: str, effect: str, position: int, *, terminal: bool = False, scope: str = SCOPE) -> dict:
    return {
        "origin": origin,
        "effect": effect,
        "terminal": terminal,
        "scope": scope,
        "sources": ["zone.a"],
        "destinations": ["zone.b"],
        "protocol": "tcp",
        "ports": [443],
        "position": position,
    }


def _run(rules: list[dict]):
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(
        ctx,
        PLAN_PLUGIN_ID,
        "security_plan",
        {"schema_version": 1, "rules": copy.deepcopy(rules), "scopes": [SCOPE], "unlowerable": []},
    )
    # Empty source rows: these tests are about order and termination, and an
    # empty source states no obligations, so the completeness check has nothing
    # to say. Omitting them entirely would instead report that the check did not
    # run, which is true and is a different test's subject.
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])
    return registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)


def _codes(result) -> list[str]:
    return [diag.code for diag in result.diagnostics]


def _errors(result) -> list[str]:
    return [diag.code for diag in result.diagnostics if diag.severity == "error"]


def _only_unverified_availability(result) -> bool:
    """No errors, and nothing beyond the SEC-AVAIL "unverified" warning.

    An empty source states no availability requirement for the scopes the plan
    carries, and that is `W7002` by definition: SEC-AVAIL is unverified rather
    than satisfied. These tests are about order and termination, so they assert
    the absence of everything else instead of the absence of diagnostics.
    """
    return _errors(result) == [] and set(_codes(result)) <= {"W7002"}


# --- it runs, and it is independent -------------------------------------------------


def test_the_plugin_is_registered_and_consumes_the_plan() -> None:
    registry = _registry()

    assert PLUGIN_ID in registry.specs
    assert registry.specs[PLUGIN_ID].consumes[0]["from_plugin"] == PLAN_PLUGIN_ID


def test_the_validator_shares_no_ordering_code_with_the_compiler() -> None:
    """It must be able to disagree, or its agreement means nothing."""
    import ast

    module = V5_TOOLS / "plugins" / "validators" / "security_plan_validator.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any("security_plan_compiler" in name for name in imported)

    # The precise claim: it reads `position`, it never produces one. A crude
    # search for `sorted(` was the first attempt and it flagged `sorted(by_scope)`,
    # which iterates scope names deterministically and orders no rules - a
    # substring test cannot tell an ordering from a stable iteration.
    produces_position = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "position":
                    produces_position = True
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            parent_is_assignment = isinstance(getattr(node, "ctx", None), ast.Store)
            if node.slice.value == "position" and parent_is_assignment:
                produces_position = True

    assert not produces_position, "the validator assigns positions; it must only check the ones it was given"


def test_a_correct_plan_produces_no_diagnostics() -> None:
    result = _run(
        [
            rule("guard:g", "deny", 0),
            rule("binding:p", "permit", 1),
            rule("plan:terminal-default-deny", "deny", 2, terminal=True),
        ]
    )

    # PARTIAL, not SUCCESS: the warning is the SEC-AVAIL one, and a check that
    # reports "unverified" has not returned a clean bill of health.
    assert result.status == PluginStatus.PARTIAL
    assert _only_unverified_availability(result)


def test_a_declared_scope_with_no_rules_is_an_error() -> None:
    """It used to pass, and that was the gap.

    Returning early on an empty rule list meant a plan declaring scopes and
    emitting nothing was accepted - and a scope with no rules has no terminal
    either, so the omission hid itself behind the same early return.
    """
    result = _run([])

    assert "E7082" in _codes(result)


def test_a_plan_declaring_no_scopes_and_no_rules_is_not_an_error() -> None:
    """A topology with no matrices produces nothing, and that is not a defect."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(
        ctx, PLAN_PLUGIN_ID, "security_plan", {"schema_version": 1, "rules": [], "scopes": [], "unlowerable": []}
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])

    assert registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE).diagnostics == []



def test_a_terminal_that_accepts_is_refused() -> None:
    """It closes nothing and shadows every rule after it."""
    result = _run(
        [
            rule("binding:p", "permit", 0),
            rule("plan:terminal-default-deny", "permit", 1, terminal=True),
        ]
    )

    assert "E7082" in _codes(result)
    assert any("closes nothing" in diag.message for diag in result.diagnostics)


def test_two_rules_on_one_position_are_refused() -> None:
    """No defined order, only the appearance of one - and no edge sees it."""
    result = _run(
        [
            rule("binding:a", "permit", 0),
            rule("binding:b", "permit", 0),
            rule("plan:terminal-default-deny", "deny", 1, terminal=True),
        ]
    )

    assert "E7081" in _codes(result)
    assert any("used more than once" in diag.message for diag in result.diagnostics)


def test_a_gap_in_the_positions_is_refused() -> None:
    """A gap invites someone to fill it and changes what "after" means."""
    result = _run(
        [
            rule("binding:a", "permit", 0),
            rule("plan:terminal-default-deny", "deny", 5, terminal=True),
        ]
    )

    assert "E7081" in _codes(result)


def test_two_terminals_in_one_scope_are_refused() -> None:
    result = _run(
        [
            rule("plan:terminal-a", "deny", 0, terminal=True),
            rule("plan:terminal-b", "deny", 1, terminal=True),
        ]
    )

    assert "E7082" in _codes(result)
    assert any("only one can be last" in diag.message for diag in result.diagnostics)


# --- the wrong plans it has to catch ------------------------------------------------


def test_a_permit_before_the_deny_that_constrains_it_is_caught() -> None:
    """The order defect that a rule list reads past without noticing."""
    result = _run(
        [
            rule("binding:p", "permit", 0),
            rule("guard:g", "deny", 1),
            rule("plan:terminal-default-deny", "deny", 2, terminal=True),
        ]
    )

    assert "E7081" in _codes(result)
    assert any("must precede" in diag.message for diag in result.diagnostics)


def test_a_rule_after_the_terminal_is_caught() -> None:
    result = _run(
        [
            rule("plan:terminal-default-deny", "deny", 0, terminal=True),
            rule("binding:p", "permit", 1),
        ]
    )

    assert "E7081" in _codes(result)


def test_a_scope_without_a_terminal_is_caught() -> None:
    """On a default-allow backend an unterminated scope is an open one."""
    result = _run([rule("binding:p", "permit", 0)])

    assert "E7082" in _codes(result)
    assert any("leaves the scope open" in diag.message for diag in result.diagnostics)


def test_each_scope_is_checked_on_its_own() -> None:
    """A terminal closing one scope says nothing about another."""
    result = _run(
        [
            rule("binding:a", "permit", 0, scope="scope.a"),
            rule("plan:terminal-default-deny", "deny", 1, terminal=True, scope="scope.a"),
            rule("binding:b", "permit", 0, scope="scope.b"),
        ]
    )

    reported = {diag.message.split("'")[1] for diag in result.diagnostics if diag.code == "E7082"}
    assert "scope.b" in reported
    assert "scope.a" not in reported


def test_duplicate_positions_are_caught_as_an_order_violation() -> None:
    """Two rules on one position have no defined order, only the look of one."""
    result = _run(
        [
            rule("guard:g", "deny", 0),
            rule("binding:p", "permit", 0),
            rule("plan:terminal-default-deny", "deny", 1, terminal=True),
        ]
    )

    assert "E7081" in _codes(result)


# --- the terminal is a role, not an effect --------------------------------------------


def test_a_terminal_is_not_treated_as_one_more_deny() -> None:
    """Counting it among the denies makes every plan a cycle.

    It would have to precede every permit and follow every rule at once, so the
    validator would report a defect it invented. A correct plan must stay clean.
    """
    result = _run(
        [
            rule("guard:g", "deny", 0),
            rule("binding:p", "permit", 1),
            rule("plan:terminal-default-deny", "deny", 2, terminal=True),
        ]
    )

    assert "E7080" not in _codes(result)
    assert _only_unverified_availability(result)


def test_a_genuine_cycle_is_reported_with_the_rules_that_form_it() -> None:
    """Two terminals in one scope: each must follow the other."""
    result = _run(
        [
            rule("plan:terminal-a", "deny", 0, terminal=True),
            rule("plan:terminal-b", "deny", 1, terminal=True),
            rule("binding:p", "permit", 2),
        ]
    )

    codes = _codes(result)
    assert "E7081" in codes or "E7080" in codes


def test_a_long_chain_does_not_exhaust_the_stack() -> None:
    """Recursive cycle detection fails here; the search is iterative."""
    rules = [rule(f"guard:g{index}", "deny", index) for index in range(400)]
    rules.append(rule("binding:p", "permit", 400))
    rules.append(rule("plan:terminal-default-deny", "deny", 401, terminal=True))

    result = _run(rules)

    # PARTIAL, not SUCCESS: the warning is the SEC-AVAIL one, and a check that
    # reports "unverified" has not returned a clean bill of health.
    assert result.status == PluginStatus.PARTIAL
    assert _only_unverified_availability(result)


# --- the independent source-side check ------------------------------------------------


MATRIX_SCOPE = "inst.security_matrix.m"


def _matrix_row(*overrides: dict) -> dict:
    return {
        "group": "network",
        "instance": MATRIX_SCOPE,
        "class_ref": "class.network.security_matrix",
        "layer": "L2",
        "extensions": {"policy_overrides": list(overrides)},
    }


def _src(name: str, *, action="accept", src="z.a", dst="z.b", ports=None) -> dict:
    entry = {"name": name, "from_zone_ref": src, "to_zone_ref": dst, "action": action}
    if ports is not None:
        entry["ports"] = ports
    return entry


def _run_with_source(plan_payload: dict, rows: list[dict]):
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, PLAN_PLUGIN_ID, "security_plan", copy.deepcopy(plan_payload))
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    return registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)


def _compile_plan(rows: list[dict]) -> dict:
    """Build the plan with the real compiler, so the mutants start from a true one."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    result = registry.execute_plugin("base.compiler.security_plan", ctx, Stage.COMPILE)
    return result.output_data["security_plan"]


SOURCE_ROWS = [
    _matrix_row(
        _src("dns", ports={"tcp": [53], "udp": [53]}),
        _src("no-b-to-a", action="drop", src="z.b", dst="z.a"),
    )
]


def test_the_validator_reads_the_source_independently() -> None:
    registry = _registry()
    consumed = {item["from_plugin"] for item in registry.specs[PLUGIN_ID].consumes}

    assert consumed == {"base.compiler.security_plan", "base.compiler.instance_rows"}


def test_a_faithful_plan_raises_no_error_and_says_avail_is_unverified() -> None:
    """No error, and an honest warning: nothing declares what has to keep working.

    Reporting SEC-AVAIL as satisfied here would be a claim about an objective
    nobody stated.
    """
    result = _run_with_source(_compile_plan(SOURCE_ROWS), SOURCE_ROWS)

    assert [diag.code for diag in result.diagnostics if diag.severity == "error"] == []
    assert "W7002" in _codes(result)


def test_removing_a_protocol_from_the_plan_and_its_metadata_is_caught() -> None:
    """The mutant that matters: delete the rule *and* the compiler's record of it.

    `expected_overrides` cannot catch this, because the compiler that lost the
    rule would lose the count with it. Only a check reading the source can see
    that a UDP restriction the sources state is not in the plan.
    """
    plan = _compile_plan(SOURCE_ROWS)
    plan["rules"] = [
        rule
        for rule in plan["rules"]
        if not (rule["origin"] == "binding:dns" and rule["transport"].get("protocol") == "udp")
    ]
    plan["expected_overrides"] = {MATRIX_SCOPE: 1}
    for index, rule in enumerate(sorted(plan["rules"], key=lambda item: item["position"])):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    # Not E7084: nothing declares that UDP/53 has to keep working, so its absence
    # is a lowering-completeness question and not an availability failure. The
    # loss is still caught - by the coverage check, against the source.
    assert "E7084" not in codes, "an undeclared permit must not be reported as an availability failure"
    assert "E7093" in codes, f"the lost UDP permit went unreported: {codes}"


def test_removing_a_guard_from_the_plan_and_its_metadata_is_caught() -> None:
    """Behavioural equivalence would miss this: the terminal denies it anyway.

    The verdict for every flow is identical with and without the guard, because
    what the guard denied the terminal denies too. The obligation is still gone,
    and coverage is traced rather than inferred.
    """
    plan = _compile_plan(SOURCE_ROWS)
    plan["rules"] = [rule for rule in plan["rules"] if rule["origin"] != "guard:no-b-to-a"]
    plan["expected_overrides"] = {MATRIX_SCOPE: 1}
    for index, rule in enumerate(sorted(plan["rules"], key=lambda item: item["position"])):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7090" in codes, f"the lost mandatory deny was not detected: {codes}"


def test_removing_a_whole_scope_from_the_plan_and_its_metadata_is_caught() -> None:
    plan = _compile_plan(SOURCE_ROWS)
    plan["rules"] = []
    plan["scopes"] = []
    plan["expected_overrides"] = {}
    plan["matrices"] = []

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7091" in codes, f"the lost scope was not detected: {codes}"


def test_an_empty_plan_does_not_satisfy_the_comparison_by_permitting_nothing() -> None:
    """One-way inclusion is not enough, which is why both directions are asked.

    An empty plan accepts nothing outside the authorized set and would satisfy
    SEC-AUTH perfectly while carrying none of the intent.
    """
    plan = _compile_plan(SOURCE_ROWS)
    plan["rules"] = [rule for rule in plan["rules"] if rule["terminal"]]
    for index, rule in enumerate(plan["rules"]):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    # Qualified, as it had to be: the plan carries nothing, and that is reported
    # through coverage. It is *not* E7084, because no applicable non-empty Q
    # exists - an empty plan fails availability only when something required it.
    assert "E7090" in codes and "E7093" in codes, f"the empty plan hid a loss: {codes}"
    assert "E7084" not in codes


def test_an_extra_permit_the_source_never_stated_is_caught() -> None:
    plan = _compile_plan(SOURCE_ROWS)
    smuggled = dict(plan["rules"][0])
    smuggled.update(
        {
            "origin": "binding:smuggled",
            "effect": "permit",
            "terminal": False,
            "sources": ["z.b"],
            "destinations": ["z.a"],
            "transport": {"kind": "ports", "protocol": "tcp", "ports": [22]},
        }
    )
    plan["rules"] = [smuggled, *plan["rules"]]
    for index, rule in enumerate(plan["rules"]):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7083" in codes


def test_the_probed_flows_come_from_the_source_not_from_the_plan() -> None:
    """Otherwise a deleted rule disappears from the check along with itself.

    Deleting the UDP rule leaves no UDP anywhere in the plan; if the space were
    built from the plan's rules there would be no UDP flow to ask about, and the
    loss would be invisible. It is detected, so the space is not the plan's.
    """
    plan = _compile_plan(SOURCE_ROWS)
    plan["rules"] = [
        rule
        for rule in plan["rules"]
        if not (rule["origin"] == "binding:dns" and rule["transport"].get("protocol") == "udp")
    ]
    for index, rule in enumerate(sorted(plan["rules"], key=lambda item: item["position"])):
        rule["position"] = index

    assert not any(
        (rule.get("transport") or {}).get("protocol") == "udp" for rule in plan["rules"]
    ), "the mutant must leave no UDP in the plan for this to mean anything"

    # With a declared requirement for it, the loss is an availability failure and
    # the probe for UDP/53 must still exist - which it only can if the space came
    # from the source.
    rows = copy.deepcopy(SOURCE_ROWS)
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns-udp", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"udp": [53]}}
    ]

    assert "E7084" in _codes(_run_with_source(plan, rows))


def test_a_missing_source_intent_is_reported_rather_than_skipped() -> None:
    """"The check did not run" is a fact, and a silent pass is not it."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(
        ctx,
        PLAN_PLUGIN_ID,
        "security_plan",
        {"schema_version": 1, "rules": [], "scopes": [], "unlowerable": []},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)

    assert "E7008" in [diag.code for diag in result.diagnostics]
    assert any("did not run" in diag.message for diag in result.diagnostics)


# --- the probe set has to reach beyond what anyone enumerated -------------------------


def test_a_wildcard_permit_beyond_the_enumerated_values_is_caught() -> None:
    """Union of intent and plan coordinates is necessary and not sufficient.

    A permit that accepts every port agrees with the authorization on every value
    anyone listed and permits more beyond them. Without a probe outside the
    enumeration, "matches on all probes" would be a property of the probe set.
    """
    plan = _compile_plan(SOURCE_ROWS)
    wildcard = dict(plan["rules"][0])
    wildcard.update(
        {
            "origin": "binding:wildcard",
            "effect": "permit",
            "terminal": False,
            "sources": ["z.a"],
            "destinations": ["z.b"],
            "transport": {"kind": "any"},
        }
    )
    plan["rules"] = [wildcard, *plan["rules"]]
    for index, rule in enumerate(plan["rules"]):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7083" in codes, "a wildcard permit beyond the listed ports went unnoticed"


def test_the_representatives_are_derived_and_never_land_inside() -> None:
    """Constants were wrong, and one fixture could not have shown it.

    A source that happened to list 64999 or `sctp` put the representative back
    inside the enumeration, and a wildcard permit passed again. They are chosen
    relative to what is present now, so this checks the property over
    enumerations that deliberately contain the old constants.
    """
    import sys as _sys

    _sys.path.insert(0, str(V5_TOOLS))
    from plugins.validators.security_plan_validator import _port_outside, _protocol_outside

    for ports in ({64999}, {1, 64999, 65535}, set(range(65000, 65536)), set()):
        assert _port_outside(ports) not in ports

    for protocols in ({"sctp"}, {"tcp", "udp", "sctp", "probe"}, {"probe", "probex"}, set()):
        assert _protocol_outside(protocols) not in protocols


def test_a_wildcard_permit_is_caught_even_when_the_source_lists_the_old_constant() -> None:
    """The counterexample the constants allowed through."""
    rows = [_matrix_row(_src("odd", ports={"sctp": [64999]}))]
    plan = _compile_plan(rows)
    wildcard = dict(plan["rules"][0])
    wildcard.update(
        {
            "origin": "binding:wildcard",
            "effect": "permit",
            "terminal": False,
            "sources": ["z.a"],
            "destinations": ["z.b"],
            "transport": {"kind": "any"},
        }
    )
    plan["rules"] = [wildcard, *plan["rules"]]
    for index, rule in enumerate(plan["rules"]):
        rule["position"] = index

    assert "E7083" in _codes(_run_with_source(plan, rows))


# --- availability is declared, never inferred from permits ------------------------------


def test_a_permit_does_not_create_an_availability_obligation() -> None:
    """Permission is not an objective, and turning one into the other invents a claim."""
    plan = _compile_plan(SOURCE_ROWS)
    plan["rules"] = [rule for rule in plan["rules"] if rule["terminal"]]
    for index, rule in enumerate(plan["rules"]):
        rule["position"] = index

    result = _run_with_source(plan, SOURCE_ROWS)
    codes = _codes(result)

    # The guard is gone, and that is reported. The permits are gone too, and that
    # is *not* reported as an availability failure, because nothing declared one.
    assert "E7090" in codes
    assert "E7084" not in codes
    assert "W7002" in codes


def test_a_declared_availability_requirement_is_checked() -> None:
    """When something does state an objective, dropping it is a failure."""
    rows = [
        _matrix_row(
            _src("dns", ports={"tcp": [53]}),
        )
    ]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": [53]}}
    ]

    plan = _compile_plan(rows)
    plan["rules"] = [rule for rule in plan["rules"] if rule["terminal"]]
    for index, rule in enumerate(plan["rules"]):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, rows))

    assert "E7084" in codes
    assert "W7002" not in codes


def test_a_satisfied_availability_requirement_reports_nothing() -> None:
    rows = [_matrix_row(_src("dns", ports={"tcp": [53]}))]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": [53]}}
    ]

    result = _run_with_source(_compile_plan(rows), rows)

    assert [diag.code for diag in result.diagnostics] == []


def test_a_scope_stating_only_q_is_checked(review: str = "5e02bf70 S4") -> None:
    """The scope with no policy at all, which used to be skipped twice over.

    `_source_obligations` moved to the next row when a scope declared no
    `policy_overrides`, so its requirements were never read; and `_check_semantics`
    returned before the loop when the whole source had no permits and no guards.
    A scope that says only "TCP/53 must work" and a plan that carries nothing but
    a terminal therefore came out at errors=0, complete=True - and admission took
    that as a pass.
    """
    rows = [
        {
            "group": "network",
            "instance": MATRIX_SCOPE,
            "class_ref": "class.network.security_matrix",
            "layer": "L2",
            "extensions": {
                "availability_requirements": [
                    {
                        "name": "dns-must-work",
                        "from_zone_ref": "z.a",
                        "to_zone_ref": "z.b",
                        "ports": {"tcp": [53]},
                    }
                ]
            },
        }
    ]

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    # Q is not a subset of A when A is empty. The contradiction is between two
    # source statements and is reported as such, not as the plan's failure.
    assert "E7092" in codes, f"a scope stating only Q went unchecked: {codes}"


def test_a_requirement_beside_an_empty_override_list_is_still_read() -> None:
    """`policy_overrides: []` is a value, and it must not swallow the next key."""
    rows = [_matrix_row()]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": [53]}}
    ]

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    assert "E7092" in codes
    assert "W7002" not in codes, "the scope declared a requirement; it is not undeclared"


def test_a_permit_naming_every_port_does_not_crash_the_probe_builder() -> None:
    """The finite-port contract admits 1-65535, and an empty complement is normal.

    `_port_outside` raised `AssertionError` when every port was enumerated, so a
    legal source took the validator down instead of producing a probe set with
    nothing to add outside it.
    """
    rows = [_matrix_row(_src("everything", ports={"tcp": list(range(1, 65536))}))]

    result = _run_with_source(_compile_plan(rows), rows)

    assert _errors(result) == [], f"a full port enumeration is a source, not a defect: {_codes(result)}"


@pytest.mark.parametrize(
    ("label", "ports"),
    [("omitted", None), ("null", None), ("an empty mapping", {})],
)
def test_an_unbounded_availability_requirement_is_refused_not_discharged(label: str, ports) -> None:
    """The requirement the parser accepted and both Q checks then skipped.

    A requirement with no transport meant "every port must keep working". That
    reached `_required`, which skipped any-transport entries, and
    `_check_requirements_are_permitted`, which iterated an empty port tuple - so
    the plan came back errors 0, warnings 0, SEC-AVAIL pass, with the requirement
    examined by nobody. `W7002` did not fire either, because the list was not
    empty.
    """
    rows = [_matrix_row(_src("dns", ports={"tcp": [53]}))]
    requirement = {"name": "everything-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b"}
    if label != "omitted":
        requirement["ports"] = ports
    rows[0]["extensions"]["availability_requirements"] = [requirement]

    result = _run_with_source(_compile_plan(rows), rows)
    codes = _codes(result)

    assert "E7094" in codes, f"an unbounded requirement passed as {label}: {codes}"
    assert any("bounded transport" in diag.message for diag in result.diagnostics)


def test_a_refused_requirement_leaves_availability_unverified() -> None:
    """And therefore blocks admission, rather than reading as a satisfied objective."""
    rows = [_matrix_row(_src("dns", ports={"tcp": [53]}))]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "everything-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b"}
    ]

    record = _run_with_source(_compile_plan(rows), rows).output_data["security_plan_verification"]

    assert record["errors"] >= 1
    statuses = record["obligations"][MATRIX_SCOPE]
    assert statuses["SEC-AVAIL"] != "pass", statuses


def test_a_bounded_requirement_beside_a_refused_one_is_still_read() -> None:
    """The refusal is per statement; it does not erase the ones that parse."""
    rows = [_matrix_row(_src("dns", ports={"tcp": [53]}))]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": [53]}},
        {"name": "unbounded", "from_zone_ref": "z.a", "to_zone_ref": "z.b"},
    ]

    result = _run_with_source(_compile_plan(rows), rows)

    assert "E7094" in _codes(result)
    assert "W7002" not in _codes(result), "one requirement did parse; the scope is not undeclared"


def test_an_override_naming_no_transport_is_still_every_transport() -> None:
    """The two grammars differ, and only for requirements.

    A portless *override* is the only mandatory deny in the real topology, and it
    constrains every transport. Refusing it here would have removed the strongest
    restriction the sources contain.
    """
    rows = [_matrix_row(_src("no-b-to-a", action="drop", src="z.b", dst="z.a"))]

    result = _run_with_source(_compile_plan(rows), rows)

    assert "E7094" not in _codes(result)
    assert _errors(result) == []


def test_the_port_reduction_separates_exactly_what_the_rules_separate() -> None:
    """The probe set is smaller; it is not blinder.

    Two ports are merged only when every listed set contains both, which is the
    condition under which no rule and no obligation here can tell them apart.
    A set that names one and not the other splits them again.
    """
    from plugins.validators.security_plan_validator import SecurityPlanValidator as V

    together = V._port_representatives([frozenset({53, 443})])
    assert len({53, 443} & together) == 1, "indistinguishable ports need one witness between them"

    apart = V._port_representatives([frozenset({53, 443}), frozenset({53})])
    assert {53, 443} <= apart, "a set naming one of them makes them distinguishable"

    everything = V._port_representatives([frozenset(range(1, 65536))])
    assert everything == {1}, "no class outside a full enumeration, and one witness inside it"

    assert V._port_representatives([]) != set(), "with nothing listed, every port is the outside class"


def test_a_required_flow_a_guard_forbids_is_a_contradiction_not_a_permit() -> None:
    """`Q subseteq A`. Two source statements disagree; neither is weakened here."""
    rows = [
        _matrix_row(
            _src("dns", ports={"tcp": [53]}),
            _src("no-a-to-b", action="drop", src="z.a", dst="z.b", ports={"tcp": [53]}),
        )
    ]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": [53]}}
    ]

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    assert "E7092" in codes
    assert "E7084" not in codes, "a contradiction must not also be reported as the plan's failure"


def test_an_empty_requirement_list_is_a_value_and_not_yet_a_claim() -> None:
    """"Nothing here has to keep working" is a decision, and a list is not one.

    An earlier version of this test treated the empty list as sufficient. It is
    an explicit value, which is more than absence, and it is still not evidence
    that anybody decided anything - for strict admission the difference is the
    provenance behind it.
    """
    rows = copy.deepcopy(SOURCE_ROWS)
    rows[0]["extensions"]["availability_requirements"] = []

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    assert "W7002" in codes
    assert "E7084" not in codes


def test_an_attested_empty_requirement_set_is_a_claim() -> None:
    """With an owner and a reason it is a decision somebody signed."""
    rows = copy.deepcopy(SOURCE_ROWS)
    rows[0]["extensions"]["availability_requirements"] = []
    rows[0]["extensions"]["availability_waiver"] = {
        "owner": "security-lead",
        "rationale": "this matrix carries no service anyone depends on",
    }

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    assert "W7002" not in codes
    assert "E7084" not in codes


@pytest.mark.parametrize("missing", ["owner", "rationale"])
def test_a_waiver_needs_both_an_owner_and_a_reason(missing: str) -> None:
    """One without the other is a label, not an attestation."""
    rows = copy.deepcopy(SOURCE_ROWS)
    rows[0]["extensions"]["availability_requirements"] = []
    waiver = {"owner": "security-lead", "rationale": "nothing depends on it"}
    waiver[missing] = "  "
    rows[0]["extensions"]["availability_waiver"] = waiver

    assert "W7002" in _codes(_run_with_source(_compile_plan(rows), rows))


# --- the endpoint set is closed by contract ------------------------------------------


def test_a_rule_naming_an_endpoint_no_source_declares_is_refused() -> None:
    """Not merely undeclared: outside every check the probe space can perform."""
    plan = _compile_plan(SOURCE_ROWS)
    stray = dict(plan["rules"][0])
    stray.update(
        {
            "origin": "binding:stray",
            "effect": "permit",
            "terminal": False,
            "sources": ["z.a"],
            "destinations": ["z.nowhere"],
            "transport": {"kind": "ports", "protocol": "tcp", "ports": [443]},
        }
    )
    plan["rules"] = [*plan["rules"], stray]
    for index, rule in enumerate(sorted(plan["rules"], key=lambda item: item["position"])):
        rule["position"] = index

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7095" in codes
    assert any("z.nowhere" in diag.message for diag in _run_with_source(plan, SOURCE_ROWS).diagnostics)


def test_the_terminal_is_exempt_from_the_endpoint_closure() -> None:
    """It names the whole scope, which is a different kind of statement."""
    result = _run_with_source(_compile_plan(SOURCE_ROWS), SOURCE_ROWS)

    assert "E7095" not in _codes(result)


# --- unsupported predicate semantics are refused, not approximated -------------------


@pytest.mark.parametrize(
    ("label", "ports"),
    [
        ("a port range", {"tcp": ["1000-2000"]}),
        ("a negated protocol", {"!tcp": [22]}),
        ("a conditional port", {"tcp": [{"port": 80, "src": "10.0.0.0/8"}]}),
        ("a port outside the range", {"tcp": [70000]}),
        ("an unknown protocol", {"gre": [0]}),
    ],
)
def test_an_unsupported_selector_blocks_its_scope(label: str, ports: dict) -> None:
    """The probe classes come from the shapes the algebra supports.

    Measured before this check existed: a port range raised a TypeError the
    registry turned into a plugin with no output, and `!tcp` was accepted as a
    protocol literally named "!tcp" - two rules emitted, nothing reported. A
    shape lowered as if understood produces a plan the checks cannot see past,
    and they would then call it clean.
    """
    rows = [_matrix_row(_src("x", ports=ports))]

    plan = _compile_plan(rows)

    assert plan["blocked_scopes"] == [MATRIX_SCOPE], f"{label} did not block its scope"
    assert plan["unlowerable"], f"{label} was lowered without a word"
    assert plan["lowering_complete"] == []


# --- regressions from the 12f4e836 code review ------------------------------------------


def test_a_required_flow_with_no_permit_covering_it_is_caught() -> None:
    """`Q subseteq A` has two halves and only one was checked.

    A requirement no permit covers is outside A just as surely as one a guard
    forbids. UDP/53 required with only TCP/443 permitted passed silently.
    """
    rows = [_matrix_row(_src("web", ports={"tcp": [443]}))]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"udp": [53]}}
    ]

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    assert "E7092" in codes


def test_a_requirement_under_an_any_permit_is_probed_when_the_permit_becomes_a_deny() -> None:
    """The probe space must carry the requirement's own coordinates.

    Source allows any transport and requires TCP/53. Turning that permit into a
    deny left no probe for TCP/53 at all, and the validator returned SUCCESS.
    """
    rows = [_matrix_row(_src("all", action="drop"))]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "dns", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": [53]}}
    ]

    codes = _codes(_run_with_source(_compile_plan(rows), rows))

    assert codes, "the unmet requirement produced no diagnostic at all"
    assert "E7092" in codes or "E7084" in codes


def test_changing_a_guards_destination_is_caught() -> None:
    """The coverage key lacked endpoints, so the loss hid behind the terminal.

    The terminal denies the flow either way, so behaviour is identical - and the
    restriction the source states is gone.
    """
    plan = _compile_plan(SOURCE_ROWS)
    for rule in plan["rules"]:
        if rule["origin"] == "guard:no-b-to-a":
            rule["destinations"] = ["z.elsewhere"]

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7090" in codes, f"a moved guard went unreported: {codes}"


def test_changing_a_guards_effect_to_permit_is_caught() -> None:
    plan = _compile_plan(SOURCE_ROWS)
    for rule in plan["rules"]:
        if rule["origin"] == "guard:no-b-to-a":
            rule["effect"] = "permit"

    assert "E7090" in _codes(_run_with_source(plan, SOURCE_ROWS))


def test_a_scope_the_plan_invents_is_still_checked() -> None:
    """The semantic check iterated the source's scopes and skipped the rest.

    An undeclared scope with an any-transport permit and a correct terminal is
    exactly where an unauthorized permit would hide.
    """
    plan = _compile_plan(SOURCE_ROWS)
    invented = [
        {
            "origin": "binding:invented",
            "effect": "permit",
            "terminal": False,
            "scope": "scope.invented",
            "sources": ["z.a"],
            "destinations": ["z.b"],
            "transport": {"kind": "any"},
            "position": 0,
        },
        {
            "origin": "plan:terminal-default-deny",
            "effect": "deny",
            "terminal": True,
            "scope": "scope.invented",
            "sources": [],
            "destinations": [],
            "transport": {"kind": "any"},
            "position": 1,
        },
    ]
    plan["rules"] = [*plan["rules"], *invented]

    codes = _codes(_run_with_source(plan, SOURCE_ROWS))

    assert "E7083" in codes, f"an invented scope's permit was not checked: {codes}"


@pytest.mark.parametrize(
    ("label", "ports"),
    [
        ("a port range", {"tcp": ["1000-2000"]}),
        ("a negated protocol", {"!tcp": [22]}),
        ("a string instead of a mapping", "tcp:443"),
    ],
)
def test_an_unsupported_selector_does_not_crash_or_widen_the_validator(label: str, ports) -> None:
    """Three separate failures, one shape: a malformed selector is not a missing one.

    The range crashed the validator with E4102 rather than reporting E7094,
    `!tcp` was still read as a protocol token, and a string `ports` became an
    any-transport permit - turning a typo into the broadest rule expressible.
    """
    rows = [_matrix_row(_src("x", ports=ports))]
    plan = _compile_plan(rows)

    result = _run_with_source(plan, rows)

    assert result.status in (PluginStatus.SUCCESS, PluginStatus.FAILED), f"{label} crashed the validator"
    assert "E4102" not in _codes(result), f"{label} crashed rather than reporting"
    assert plan["blocked_scopes"] == [MATRIX_SCOPE], f"{label} did not block its scope"


def test_the_two_implementations_agree_on_what_is_supported() -> None:
    """Written twice on purpose; a test keeps them from drifting."""
    import sys as _sys

    _sys.path.insert(0, str(V5_TOOLS))
    from plugins.compilers.security_plan_compiler import _SUPPORTED_PROTOCOLS as compiler_set
    from plugins.validators.security_plan_validator import _SUPPORTED_PROTOCOLS as validator_set

    assert compiler_set == validator_set


def test_an_unsupported_selector_is_reported_as_a_diagnostic_not_only_blocked() -> None:
    """Found by my own review: E7094 was registered and raised by nobody.

    The compiler refused the selector and recorded the reason in `unlowerable`,
    and the validator's source reader returned None silently - so the scope was
    blocked in a channel and the operator running the compile saw nothing at all.
    A code with no raiser is a claim nobody checks.
    """
    rows = [_matrix_row(_src("bad", ports={"tcp": ["1000-2000"]}))]

    result = _run_with_source(_compile_plan(rows), rows)
    codes = _codes(result)

    assert "E7094" in codes
    assert any("cannot read" in diag.message for diag in result.diagnostics)


@pytest.mark.parametrize(
    ("label", "ports"),
    [
        ("a negated protocol", {"!tcp": [22]}),
        ("a string where a mapping belongs", "tcp:443"),
        ("a conditional port", {"tcp": [{"port": 80}]}),
        ("a port outside the range", {"tcp": [70000]}),
    ],
)
def test_every_refused_selector_shape_reaches_a_diagnostic(label: str, ports) -> None:
    rows = [_matrix_row(_src("bad", ports=ports))]

    assert "E7094" in _codes(_run_with_source(_compile_plan(rows), rows)), label


def test_an_unsupported_availability_requirement_is_reported_too() -> None:
    """The second call site, which the first fix missed and a crash revealed."""
    rows = [_matrix_row(_src("web", ports={"tcp": [443]}))]
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "bad", "from_zone_ref": "z.a", "to_zone_ref": "z.b", "ports": {"tcp": ["1-2"]}}
    ]

    assert "E7094" in _codes(_run_with_source(_compile_plan(rows), rows))
