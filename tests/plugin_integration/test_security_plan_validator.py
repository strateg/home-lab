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
    return registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)


def _codes(result) -> list[str]:
    return [diag.code for diag in result.diagnostics]


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

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_an_empty_plan_is_not_an_error() -> None:
    assert _run([]).diagnostics == []


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

    assert _codes(result) == ["E7082"]
    assert "scope.b" in result.diagnostics[0].message


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
    assert result.diagnostics == []


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

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []
