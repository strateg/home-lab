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


# --- presence is not proof ----------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "field", "value", "extensions"),
    [
        (
            "a session carrying a revoked epoch",
            "state",
            {"tracked": True},
            {"sessions": [{"id": "s1", "epoch": "epoch.old", "revoked": True}]},
        ),
        (
            "a previous plan with no rules and an envelope",
            "transition",
            {"allowed": [["z.a", "z.b", "tcp", 53]]},
            {"previous_plan": {"rules": []}},
        ),
        (
            "a plan asserting its own demonstrated list",
            "path",
            {"cases": ["a", "b"], "demonstrated": ["a", "b"]},
            {},
        ),
        (
            "a disabled offer with no evidence",
            "capability",
            {"cap.firewall.stateful": {}},
            {"capability_offers": {"cap.firewall.stateful": {"enabled": False, "evidence": []}}},
        ),
    ],
)
def test_an_input_that_merely_exists_does_not_discharge_an_obligation(
    label: str, field: str, value, extensions: dict
) -> None:
    """The 2026-09-15 finding: four checks tested presence, not the property.

    Each of these came back `pass`, admission granted, marker written. A session
    with a revoked epoch is not a session inside one; a previous plan with no
    rules is not a replayed sequence; a plan listing its own `demonstrated` cases
    is marking its own homework; and a disabled offer with no evidence is not a
    witness.
    """
    rows = _rows(**extensions)
    result = _run(_with_field(_plan(rows), field, value), rows)
    obligation = next(name for name, spec in OBLIGATIONS.items() if spec["field"] == field)

    assert _statuses(result)[obligation] == UNVERIFIED, f"{label} was read as proof"
    assert "W7003" in _codes(result)


def test_no_obligation_here_can_report_pass() -> None:
    """Stated as a property of the module, not of one fixture.

    Four of the five have no solver, and the fifth can demonstrate a failure but
    not a success. A `pass` appearing anywhere in this producer would mean a
    solver landed without its negative controls.
    """
    import inspect

    from plugins.validators import security_obligations_validator as module

    for name in OBLIGATIONS:
        checker = getattr(module.SecurityObligationsValidator, f"_check_{name.lower().replace('-', '_')}")
        source = inspect.getsource(checker)
        assert "return PASS" not in source, f"{name} claims a pass; where is its negative control?"


# --- SEC-NAT: a failure it can demonstrate, a success it cannot ----------------------


def test_sec_nat_reports_a_collision_and_not_a_pass_otherwise() -> None:
    """Collision freedom over this key is necessary and not sufficient.

    The composition proof ADR 0119 asks for is about an approved frontend against
    an unauthorized direct or backend flow, over original and current tuples with
    their context. Counting distinct originals per target is not that, so a clean
    scope is `unverified` rather than satisfied.
    """
    clean = _run(_with_field(_plan(_rows()), "nat", {"to": "10.0.0.5"}))

    assert _statuses(clean)["SEC-NAT"] == UNVERIFIED
    assert "necessary and not sufficient" in str(
        clean.output_data["security_obligation_statuses"]["reasons"][SCOPE]["SEC-NAT"]
    )


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
    result = _run(_with_field(_plan(rows), "nat", {"to": "10.0.0.5"}), rows)

    assert _statuses(result)["SEC-NAT"] == "fail"
    assert "E7086" in _codes(result)


def test_one_unreadable_transform_decides_the_whole_scope() -> None:
    """No partial success. A subset of the transforms checked is not all of them.

    A readable transform beside an unsupported string used to give the scope an
    overall `pass`, because only the mappings were selected and the rest vanished
    from the check.
    """
    plan = _with_field(_plan(_rows()), "nat", {"to": "10.0.0.5"})
    plan["rules"].append(
        {
            "origin": "binding:other",
            "effect": "permit",
            "terminal": False,
            "scope": SCOPE,
            "sources": ["z.c"],
            "destinations": ["z.d"],
            "transport": {"kind": "ports", "protocol": "tcp", "ports": [8080]},
            "position": 99,
            "nat": "unsupported-transform",
        }
    )

    result = _run(plan)

    assert _statuses(result)["SEC-NAT"] == UNVERIFIED
    assert any("cannot read decides the scope" in diag.message for diag in result.diagnostics)


@pytest.mark.parametrize(
    "nat",
    [
        "unsupported-transform",
        {"to": ""},
        {"to": None},
        {"translated": "10.0.0.5"},
        {"to": "10.0.0.5", "mode": "netmap"},
    ],
)
def test_every_transform_declaration_is_parsed_under_a_closed_form(nat) -> None:
    result = _run(_with_field(_plan(_rows()), "nat", nat))

    assert _statuses(result)["SEC-NAT"] == UNVERIFIED


def test_original_identity_separates_authorizations_endpoints_alone_would_merge() -> None:
    """A permit on 53 and a deny on 443 between one pair are two authorizations.

    Keyed on endpoints alone they looked like one original, so a collapse onto a
    single target went unseen.
    """
    from plugins.validators.security_obligations_validator import SecurityObligationsValidator as V

    base = {
        "sources": ["z.a"],
        "destinations": ["z.b"],
        "transport": {"kind": "ports", "protocol": "tcp", "ports": [53]},
    }
    permit = V._original_identity({**base, "effect": "permit"})
    deny = V._original_identity({**base, "effect": "deny"})
    other_port = V._original_identity(
        {**base, "effect": "permit", "transport": {"kind": "ports", "protocol": "tcp", "ports": [443]}}
    )

    assert permit != deny, "effect is part of what authorized the flow"
    assert permit != other_port, "transport is part of it too"


def test_two_authorizations_collapsing_onto_one_target_are_caught() -> None:
    """The case the endpoint-only key hid, end to end."""
    plan = _plan(_rows())
    permit = next(rule for rule in plan["rules"] if not rule["terminal"])
    permit["nat"] = {"to": "10.0.0.5"}
    plan["rules"].append(
        {
            **copy.deepcopy(permit),
            "origin": "guard:same-endpoints",
            "effect": "deny",
            "transport": {"kind": "ports", "protocol": "tcp", "ports": [443]},
            "position": 99,
        }
    )

    result = _run(plan)

    assert _statuses(result)["SEC-NAT"] == "fail"
    assert "E7086" in _codes(result)


# --- the record names the plan it is about ------------------------------------------


def test_the_record_carries_the_identity_of_the_plan_it_examined() -> None:
    from plugins.validators.strict_admission import content_digest

    plan = _plan(_rows())
    record = _run(plan).output_data["security_obligation_statuses"]

    assert record["plan_digest"] == content_digest(plan)
    assert record["schema_version"] == 1
    assert set(record["obligations"]) == set(OBLIGATIONS)


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


def test_only_the_obligation_that_can_fail_names_a_code() -> None:
    """A number in a table inside an emitting module looks raised and is not.

    Four of the five cannot demonstrate a failure, so they name no code and their
    numbers stay reserved in the catalog and on the registry's waiting list. The
    number comes back when a solver can produce the failure - which is what
    `E7086` did.
    """
    assert {name: spec["code"] for name, spec in OBLIGATIONS.items()} == {
        "SEC-NAT": "E7086",
        "SEC-PATH": None,
        "SEC-STATE": None,
        "SEC-TRANSITION": None,
        "SEC-CAP": None,
    }

    source = (
        REPO_ROOT / "topology-tools/plugins/validators/security_obligations_validator.py"
    ).read_text(encoding="utf-8")
    for reserved in ("E7085", "E7087", "E7088", "E7089"):
        assert source.count(reserved) <= 1, (
            f"{reserved} appears more than once in a comment; a literal here reads as a raiser"
        )


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
