#!/usr/bin/env python3
"""The plan compiler, and the differential that keeps it honest.

This is G3's join: the plan every obligation is checked against is now produced
by the pipeline rather than derived in a test. Executed through the registry,
which is also the only proof it loads - an empty channel from a plugin that never
ran looks exactly like one from sources with no matrices.

The algebra now exists twice, in `netmodel` and here, because the framework
cannot import a package outside its own distribution. A differential runs both
over the same overrides and requires the same ordered plan; without it the copies
drift and each keeps passing its own tests.
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

PLUGIN_ID = "base.compiler.security_plan"
CHANNEL = "security_plan"
TERMINAL = "plan:terminal-default-deny"


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


def matrix(instance: str, *overrides: dict) -> dict:
    return {
        "group": "network",
        "instance": instance,
        "class_ref": "class.network.security_matrix",
        "layer": "L2",
        "extensions": {"policy_overrides": list(overrides)},
    }


def override(name: str, *, action="accept", src="zone.a", dst="zone.b", ports=None) -> dict:
    entry = {"name": name, "from_zone_ref": src, "to_zone_ref": dst, "action": action}
    if ports is not None:
        entry["ports"] = ports
    return entry


def _run(rows: list[dict]):
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    # Read the plugin's own result. `subscribe` needs an active execution scope
    # that is gone by assertion time, and reaching into the publish registry is
    # banned by contract - it couples a test to a private structure the envelope
    # contract exists to replace.
    return result.output_data[CHANNEL]


# --- it exists and runs ------------------------------------------------------------


def test_the_plugin_is_registered_and_publishes_its_channel() -> None:
    registry = _registry()

    assert PLUGIN_ID in registry.specs
    assert registry.specs[PLUGIN_ID].produces[0]["key"] == CHANNEL

    published = _run([])
    assert published["rules"] == [] and published["scopes"] == []


def test_a_topology_with_no_matrices_produces_an_empty_plan_not_an_error() -> None:
    rows = [{"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.lxc", "layer": "L4"}]

    assert _run(rows)["rules"] == []


# --- ordering ------------------------------------------------------------------------


def test_denies_precede_permits_and_the_terminal_is_last() -> None:
    rows = [
        matrix(
            "inst.security_matrix.m",
            override("allow-web", ports={"tcp": [443]}),
            override("block-ssh", action="drop", ports={"tcp": [22]}),
        )
    ]

    rules = _run(rows)["rules"]
    positions = {rule["origin"]: rule["position"] for rule in rules}

    assert positions["guard:block-ssh"] < positions["binding:allow-web"] < positions[TERMINAL]


def test_every_scope_gets_its_own_terminal() -> None:
    """A drop-all closing one matrix says nothing about another."""
    rows = [
        matrix("inst.security_matrix.a", override("x", ports={"tcp": [1]})),
        matrix("inst.security_matrix.b", override("y", ports={"tcp": [2]})),
    ]

    plan = _run(rows)
    terminals = {rule["scope"] for rule in plan["rules"] if rule["terminal"]}

    assert terminals == {"inst.security_matrix.a", "inst.security_matrix.b"}


def test_nothing_executable_follows_a_terminal_in_its_own_scope() -> None:
    rows = [
        matrix(
            "inst.security_matrix.m",
            override("a", ports={"tcp": [1]}),
            override("b", action="drop", ports={"tcp": [2]}),
        )
    ]

    rules = _run(rows)["rules"]
    terminal_at = next(rule["position"] for rule in rules if rule["terminal"])
    same_scope = [rule["position"] for rule in rules if rule["scope"] == "inst.security_matrix.m"]

    assert max(same_scope) == terminal_at


def test_the_order_does_not_depend_on_declaration_order() -> None:
    """Otherwise the plan changes when someone reorders a source file."""
    forward = matrix(
        "inst.security_matrix.m",
        override("a", ports={"tcp": [1]}),
        override("b", action="drop", ports={"tcp": [2]}),
        override("c", ports={"tcp": [3]}),
    )
    reversed_rows = matrix(
        "inst.security_matrix.m",
        override("c", ports={"tcp": [3]}),
        override("b", action="drop", ports={"tcp": [2]}),
        override("a", ports={"tcp": [1]}),
    )

    assert _run([forward])["rules"] == _run([reversed_rows])["rules"]


# --- the digest -------------------------------------------------------------------------


def test_the_digest_is_stable_for_the_same_plan() -> None:
    rows = [matrix("inst.security_matrix.m", override("a", ports={"tcp": [1]}))]

    assert _run(rows)["digest"] == _run(rows)["digest"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda: [matrix("inst.security_matrix.m", override("a", ports={"tcp": [2]}))],
        lambda: [matrix("inst.security_matrix.m", override("a", action="drop", ports={"tcp": [1]}))],
        lambda: [
            matrix(
                "inst.security_matrix.m",
                override("a", ports={"tcp": [1]}),
                override("b", ports={"tcp": [9]}),
            )
        ],
    ],
    ids=["port", "effect", "extra-rule"],
)
def test_the_digest_moves_when_meaning_moves(mutate) -> None:
    baseline = _run([matrix("inst.security_matrix.m", override("a", ports={"tcp": [1]}))])["digest"]

    assert _run(mutate())["digest"] != baseline


def test_the_digest_ignores_declaration_order() -> None:
    a = matrix("inst.security_matrix.m", override("a", ports={"tcp": [1]}), override("b", ports={"tcp": [2]}))
    b = matrix("inst.security_matrix.m", override("b", ports={"tcp": [2]}), override("a", ports={"tcp": [1]}))

    assert _run([a])["digest"] == _run([b])["digest"]


# --- what cannot be lowered is published, not dropped ---------------------------------------


def test_a_portless_override_becomes_an_any_transport_rule() -> None:
    """The sources' only mandatory deny is portless, and it is now expressible.

    It used to go to `unlowerable`, which was honest but left the strongest
    restriction in the topology outside the plan. An override naming no transport
    constrains every transport, and that is now its own kind - not an empty port
    list, which reads as "nothing", and not an enumeration of well-known service
    ports, which would narrow a deny to the ones somebody thought of.
    """
    rows = [matrix("inst.security_matrix.m", override("deny-all", action="drop"))]

    plan = _run(rows)

    assert plan["unlowerable"] == []
    guard = next(rule for rule in plan["rules"] if rule["origin"] == "guard:deny-all")
    assert guard["transport"] == {"kind": "any"}
    assert guard["effect"] == "deny"


def test_an_any_transport_rule_is_not_an_empty_port_list() -> None:
    """The distinction the review asked for, asserted rather than described."""
    rows = [
        matrix(
            "inst.security_matrix.m",
            override("deny-all", action="drop"),
            override("web", ports={"tcp": [443]}),
        )
    ]

    kinds = {rule["origin"]: rule["transport"]["kind"] for rule in _run(rows)["rules"]}

    assert kinds["guard:deny-all"] == "any"
    assert kinds["binding:web"] == "ports"


def test_both_protocols_survive_a_two_protocol_override() -> None:
    """F1: `sorted(ports.items())[0]` kept TCP and dropped UDP without a word."""
    for action, prefix in (("accept", "binding"), ("drop", "guard")):
        rows = [matrix("inst.security_matrix.m", override("dns", action=action, ports={"tcp": [53], "udp": [53]}))]

        plan = _run(rows)
        protocols = {
            rule["transport"]["protocol"]
            for rule in plan["rules"]
            if rule["origin"] == f"{prefix}:dns"
        }

        assert protocols == {"tcp", "udp"}, f"{action}: lost a protocol"
        assert plan["unlowerable"] == []


def test_a_scope_with_an_unlowerable_override_is_blocked_entirely() -> None:
    """No partial success: a subset of a restriction is a weaker restriction."""
    rows = [
        matrix(
            "inst.security_matrix.good",
            override("ok", ports={"tcp": [443]}),
        ),
        matrix(
            "inst.security_matrix.bad",
            override("ok", ports={"tcp": [443]}),
            override("broken", ports={"tcp": []}),
        ),
    ]

    plan = _run(rows)

    assert plan["blocked_scopes"] == ["inst.security_matrix.bad"]
    assert plan["lowering_complete"] == ["inst.security_matrix.good"]


def test_lowering_complete_is_not_strict_eligible() -> None:
    """Two claims, and conflating them was the mistake.

    Lowering every legacy override says the compiler represented what was
    written. It says nothing about whether those overrides were approved, or
    whether an independent check has passed. Nothing is strict-eligible while the
    plan's provenance is legacy_shadow, and the field says so instead of
    inheriting a completeness result.
    """
    plan = _run([matrix("inst.security_matrix.m", override("web", ports={"tcp": [443]}))])

    assert plan["lowering_complete"] == ["inst.security_matrix.m"]
    assert plan["strict_eligible"] == []
    assert "not approved bound" in plan["strict_blocked_reason"]


def test_the_plan_declares_itself_legacy_until_approved_bindings_exist() -> None:
    """An authored override is not an approved bound permit, and says so."""
    plan = _run([matrix("inst.security_matrix.m", override("web", ports={"tcp": [443]}))])

    assert plan["provenance"] == "legacy_shadow"


def test_the_expected_override_count_is_published_for_completeness_checking() -> None:
    """So a consumer can check the plan against the intent, not against itself."""
    rows = [
        matrix(
            "inst.security_matrix.m",
            override("a", ports={"tcp": [1]}),
            override("b", ports={"tcp": [2]}),
        )
    ]

    assert _run(rows)["expected_overrides"] == {"inst.security_matrix.m": 2}


@pytest.mark.parametrize(
    ("bad", "fragment"),
    [
        (override("", ports={"tcp": [1]}), "no name"),
        ({"name": "x", "action": "accept", "ports": {"tcp": [1]}}, "both zones"),
        (override("x", action="wat", ports={"tcp": [1]}), "unknown action"),
        (override("x", ports={"tcp": []}), "is empty"),
    ],
)
def test_a_malformed_override_is_reported_not_silently_skipped(bad, fragment: str) -> None:
    plan = _run([matrix("inst.security_matrix.m", bad)])

    assert len(plan["unlowerable"]) == 1
    assert fragment in plan["unlowerable"][0]["reason"]


# --- the differential ------------------------------------------------------------------------


def test_the_framework_plan_matches_the_reference_model() -> None:
    """Two implementations of one lowering, required to agree.

    The framework cannot import netmodel - it sits outside distribution - so the
    ordering rules are written twice. This runs both over the same overrides and
    compares the emitted sequence, which is the only thing stopping the copies
    from drifting while each passes its own suite.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from netmodel.lower import lower
    from netmodel.plan import ExecutionContext
    from netmodel.policy import (
        BINDING_DESTINATION,
        BINDING_SOURCE,
        Activation,
        Binding,
        Effect,
        PolicyTemplate,
        resolve_grant,
    )

    overrides = [
        override("allow-web", ports={"tcp": [443]}),
        override("allow-db", src="zone.c", dst="zone.b", ports={"tcp": [5432]}),
        override("block-ssh", action="drop", src="zone.a", dst="zone.b", ports={"tcp": [22]}),
    ]
    framework = _run([matrix("inst.security_matrix.m", *overrides)])

    grants = []
    guards = {}
    for entry in overrides:
        accept = entry["action"] == "accept"
        template = PolicyTemplate(
            policy_id=f"policy.{entry['name']}",
            effect=Effect.PERMIT if accept else Effect.DENY,
            activation=Activation.BINDING_ONLY if accept else Activation.SCOPE_GUARD,
            direction="transit",
            source=BINDING_SOURCE if accept else frozenset({entry["from_zone_ref"]}),
            destination=BINDING_DESTINATION if accept else frozenset({entry["to_zone_ref"]}),
            protocol="tcp",
            ports=frozenset(entry["ports"]["tcp"]),
            owner="inst.security_matrix.m",
            rationale="differential",
        )
        if accept:
            grants.append(
                resolve_grant(
                    template,
                    Binding(
                        binding_id=f"bind.{entry['name']}",
                        policy_id=template.policy_id,
                        sources=frozenset({entry["from_zone_ref"]}),
                        destinations=frozenset({entry["to_zone_ref"]}),
                        approved=True,
                    ),
                )
            )
        else:
            guards[f"guard.{entry['name']}"] = template

    context = ExecutionContext(
        enforcer="inst.security_matrix.m",
        routing_domain="main",
        family="ipv4",
        hook="forward",
        chain="managed",
    )
    reference = lower(
        grants=grants,
        guards=guards,
        context=context,
        endpoints=("zone.a", "zone.b", "zone.c"),
        protocols=("tcp",),
    )

    framework_sequence = [rule["origin"] for rule in framework["rules"]]
    reference_sequence = [
        entry.rule.origin.replace("guard:guard.", "guard:").replace("binding:bind.", "binding:")
        for entry in reference
    ]

    assert framework_sequence == reference_sequence, (
        f"the two lowerings disagree:\n  framework: {framework_sequence}\n  reference: {reference_sequence}"
    )


def test_positions_are_per_scope_and_consecutive_from_zero() -> None:
    """Each scope is an independent rule list; numbering them as one is an invitation.

    A global counter looked harmless on a two-matrix topology and produced a
    terminal at position 1 with five rules after it. Correct per scope, and a
    list that drops everything after position 1 the moment a consumer flattens
    it. Found by reading the compiler's output on the real topology, not by a
    fixture.
    """
    rows = [
        matrix("inst.security_matrix.a", override("a1", ports={"tcp": [1]}), override("a2", ports={"tcp": [2]})),
        matrix("inst.security_matrix.b", override("b1", ports={"tcp": [3]})),
    ]

    rules = _run(rows)["rules"]
    by_scope: dict[str, list[int]] = {}
    for rule in rules:
        by_scope.setdefault(rule["scope"], []).append(rule["position"])

    for scope, positions in by_scope.items():
        assert sorted(positions) == list(range(len(positions))), f"{scope} is not consecutive from zero"

    for scope, positions in by_scope.items():
        terminal = next(rule["position"] for rule in rules if rule["scope"] == scope and rule["terminal"])
        assert terminal == max(positions), f"{scope} has a rule after its terminal"
