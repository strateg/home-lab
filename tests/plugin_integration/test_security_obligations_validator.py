#!/usr/bin/env python3
"""The five obligations that had no checker in the framework.

`base.validator.security_plan` decides SEC-ORDER, SEC-COVER, SEC-AUTH and
SEC-AVAIL. These are the other five from ADR 0119, which existed only in
`netmodel` - a root package the framework cannot import.

What makes mounting them worth doing rather than vacuous is the middle answer.
None of the five has its inputs in the pipeline today, and a checker with no
input finds nothing; reporting that as a pass is the empty-loop mistake. So each
obligation says *not applicable* when the plan carries no construct it governs,
*unverified* with the missing input named when it does and cannot be decided, and
pass or fail when it can.

The tests below are mostly about the difference between those three, because
collapsing any two of them is how a check stops meaning anything.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402
from plugins.validators.security_obligations_validator import (  # noqa: E402
    NOT_APPLICABLE,
    OBLIGATIONS,
    PASS,
    UNVERIFIED,
)

from tests.helpers.plugin_execution import publish_for_test  # noqa: E402

PLUGIN_ID = "base.validator.security_obligations"
SCOPE = "inst.security_matrix.fixture"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _rows(**extensions) -> list[dict]:
    payload = {
        "policy_overrides": [
            {
                "name": "dns",
                "from_zone_ref": "z.a",
                "to_zone_ref": "z.b",
                "action": "accept",
                "ports": {"tcp": [53]},
            }
        ]
    }
    payload.update(extensions)
    return [
        {
            "group": "network",
            "instance": SCOPE,
            "class_ref": "class.network.security_matrix",
            "layer": "L2",
            "extensions": payload,
        }
    ]


def _plan(rows: list[dict]) -> dict:
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    return registry.execute_plugin("base.compiler.security_plan", ctx, Stage.COMPILE).output_data[
        "security_plan"
    ]


def _run(plan: dict, rows: list[dict] | None = None):
    registry = _registry()
    ctx = _context()
    if rows is not None:
        publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))
    return registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)


def _statuses(result) -> dict[str, str]:
    return result.output_data["security_obligation_statuses"]["statuses"][SCOPE]


def _codes(result) -> list[str]:
    return [diag.code for diag in result.diagnostics]


def _with_field(plan: dict, field: str, value) -> dict:
    changed = copy.deepcopy(plan)
    for rule in changed["rules"]:
        if not rule["terminal"]:
            rule[field] = value
    return changed


# --- it runs, and it answers for all five ------------------------------------------


def test_the_plugin_is_registered_and_decides_every_obligation() -> None:
    registry = _registry()

    assert PLUGIN_ID in registry.specs

    result = _run(_plan(_rows()))

    assert set(_statuses(result)) == set(OBLIGATIONS), "an obligation with no answer is not mounted"


def test_an_obligation_no_construct_triggers_is_not_applicable_rather_than_passing() -> None:
    """Nothing here could violate it, which is a different statement from "it holds"."""
    result = _run(_plan(_rows()))

    assert set(_statuses(result).values()) == {NOT_APPLICABLE}
    assert _codes(result) == [], "an inapplicable obligation is not news"

    reasons = result.output_data["security_obligation_statuses"]["reasons"][SCOPE]
    for name, spec in OBLIGATIONS.items():
        assert f"`{spec['field']}`" in reasons[name], "the reason must name the field that was absent"


# --- applicable and undecidable is the answer that matters --------------------------


@pytest.mark.parametrize(
    ("obligation", "field"),
    [(name, spec["field"]) for name, spec in sorted(OBLIGATIONS.items()) if name != "SEC-NAT"],
)
def test_an_applicable_obligation_with_no_input_is_unverified_and_names_it(
    obligation: str, field: str
) -> None:
    """`W7003`, and the missing input in the message.

    This is the whole reason these five can be mounted at all. Without it a
    checker with no input reports nothing and the plan looks checked.
    """
    result = _run(_with_field(_plan(_rows()), field, {"declared": True}))

    assert _statuses(result)[obligation] == UNVERIFIED
    assert "W7003" in _codes(result)
    assert any(obligation in diag.message for diag in result.diagnostics)


def test_the_unverified_message_says_what_is_missing_rather_than_that_it_failed() -> None:
    result = _run(_with_field(_plan(_rows()), "state", {"declared": True}))

    message = next(diag.message for diag in result.diagnostics if "SEC-STATE" in diag.message)

    assert "cannot be decided" in message
    assert "session inventory" in message
    assert "unverified rather than satisfied" in message


# --- and when the input is there, it decides ----------------------------------------


def test_sec_nat_passes_when_each_transform_has_one_original() -> None:
    """Not a stub: the input is on the rule, so this one actually runs today."""
    result = _run(_with_field(_plan(_rows()), "nat", {"to": "10.0.0.5"}))

    assert _statuses(result)["SEC-NAT"] == PASS
    assert "W7003" not in _codes(result)


def test_sec_nat_fails_when_two_originals_collapse_onto_one_target() -> None:
    """The failure the obligation exists for, reported as `E7086`."""
    rows = _rows(
        policy_overrides=[
            {
                "name": "dns",
                "from_zone_ref": "z.a",
                "to_zone_ref": "z.b",
                "action": "accept",
                "ports": {"tcp": [53]},
            },
            {
                "name": "web",
                "from_zone_ref": "z.c",
                "to_zone_ref": "z.d",
                "action": "accept",
                "ports": {"tcp": [443]},
            },
        ]
    )
    plan = _with_field(_plan(rows), "nat", {"to": "10.0.0.5"})

    result = _run(plan, rows)

    assert _statuses(result)["SEC-NAT"] == "fail"
    assert "E7086" in _codes(result)
    assert any("collapse differently authorized originals" in diag.message for diag in result.diagnostics)


def test_sec_nat_without_a_translated_target_is_unverified_not_a_pass() -> None:
    result = _run(_with_field(_plan(_rows()), "nat", {"comment": "no target"}))

    assert _statuses(result)["SEC-NAT"] == UNVERIFIED


def test_sec_path_decides_when_the_inventory_and_the_evidence_are_both_there() -> None:
    covered = _with_field(_plan(_rows()), "path", {"cases": ["a", "b"], "demonstrated": ["a", "b"]})
    gap = _with_field(_plan(_rows()), "path", {"cases": ["a", "b"], "demonstrated": ["a"]})

    assert _statuses(_run(covered))["SEC-PATH"] == PASS
    assert _statuses(_run(gap))["SEC-PATH"] == "fail"
    assert "E7085" in _codes(_run(gap))


def test_sec_path_with_an_inventory_and_no_evidence_is_unverified() -> None:
    """Evidence is an argument, never something the checker fills in."""
    result = _run(_with_field(_plan(_rows()), "path", {"cases": ["a"]}))

    assert _statuses(result)["SEC-PATH"] == UNVERIFIED
    assert any("which cases were demonstrated" in diag.message for diag in result.diagnostics)


def test_sec_cap_decides_against_offers_the_sources_carry() -> None:
    rows = _rows(capability_offers={"cap.firewall.stateful": {"version": "7.14"}})
    met = _with_field(_plan(rows), "capability", {"cap.firewall.stateful": {}})
    unmet = _with_field(_plan(rows), "capability", {"cap.firewall.offload": {}})

    assert _statuses(_run(met, rows))["SEC-CAP"] == PASS
    assert _statuses(_run(unmet, rows))["SEC-CAP"] == "fail"
    assert "E7089" in _codes(_run(unmet, rows))


def test_sec_transition_needs_both_a_previous_plan_and_an_envelope() -> None:
    plan = _with_field(_plan(_rows()), "transition", {"declared": True})
    rows_with_previous = _rows(previous_plan={"rules": []})

    assert _statuses(_run(plan))["SEC-TRANSITION"] == UNVERIFIED
    assert _statuses(_run(plan, rows_with_previous))["SEC-TRANSITION"] == UNVERIFIED

    with_envelope = copy.deepcopy(plan)
    with_envelope["transition"] = {"allowed": [["z.a", "z.b", "tcp", 53]]}

    assert _statuses(_run(with_envelope, rows_with_previous))["SEC-TRANSITION"] == PASS


# --- the two sides of applicability have to agree -----------------------------------


def test_the_fields_here_are_the_ones_admission_reserves() -> None:
    """Two lists, one meaning.

    `strict_admission` refuses a plan field it does not recognise and treats
    these five as reserved. If the sets drifted apart, a construct would either
    be refused as unknown while this plugin decided it, or decided here and
    invisible there.
    """
    from plugins.validators.strict_admission import DEFERRED_OBLIGATION_FIELDS

    mine = {spec["field"]: name for name, spec in OBLIGATIONS.items()}

    assert mine == DEFERRED_OBLIGATION_FIELDS


def test_every_code_this_plugin_can_raise_is_the_one_its_obligation_owns() -> None:
    expected = {
        "SEC-PATH": "E7085",
        "SEC-NAT": "E7086",
        "SEC-STATE": "E7087",
        "SEC-TRANSITION": "E7088",
        "SEC-CAP": "E7089",
    }

    assert {name: spec["code"] for name, spec in OBLIGATIONS.items()} == expected


def test_without_a_plan_the_registry_declines_to_run_this_at_all() -> None:
    """The plan is a required input, so its absence is the registry's answer.

    The plugin keeps its own guard for a direct call, but the contract-level
    behaviour is what matters: nothing publishes obligation statuses for a plan
    that does not exist, so admission finds no status and refuses rather than
    reading an empty record as a clean one.
    """
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)

    assert result.status.value == "FAILED"
    assert "E8003" in _codes(result), "the missing required input must be the reported reason"
    assert not (result.output_data or {}).get("security_obligation_statuses")
