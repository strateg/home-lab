"""The W07 boundary, and the debt it currently carries.

`adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md` fixes where backend
specialization lives: a compile-stage compiler plugin in the object module, not
the generator. The plan's constraint is that specialization "cannot occur only in
a generator after the relevant validator ran", and today it does.

These tests pin the measurement the decision rests on and hold the line going
forward: the existing projection may shrink, and no new specialization may appear
at generate. Recording the debt rather than fixing it in one step is deliberate -
1,565 lines whose output is pinned only by artifact parity would be replaced by an
unmeasured baseline.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTION = REPO_ROOT / "topology/object-modules/mikrotik/plugins/projections.py"
DECISION = REPO_ROOT / "adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md"

# Measured 2026-09-14 at commit 3312ca0b, lowered on 2026-09-15 when the two
# VLAN-CIDR helpers and the zone oracle left the projection for the compiler's
# channel and the parity test, lowered again on 2026-09-29 when
# _extract_security_matrix stopped re-deriving R1-R6 itself and started
# reading the compiler's composed plan (ADR 0118-analysis/
# ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md sections 5c/5d, N-07), lowered
# again the same day when W07 migration order item 1
# (_derive_mikrotik_capability_flags, _extract_capabilities) moved to
# object.mikrotik.compiler.capability_flags, lowered again the same day when
# item 4a (_extract_wireguard_tunnels) moved to object.mikrotik.compiler.
# wireguard_tunnels, lowered again the same day when item 4b
# (_extract_containers) moved to object.mikrotik.compiler.containers, and
# lowered again the same day when item 4c (_extract_wifi_config) moved to
# object.mikrotik.compiler.wifi_config, and lowered again the same day when
# item 4d (_build_routing_policy_entry) moved to object.mikrotik.compiler.
# routing_policies, and lowered again the same day when item 4e
# (_extract_mac_vlan_assignments) moved to object.mikrotik.compiler.
# mac_vlan_assignments. A budget that stays above the real figure stops
# measuring, so it is lowered whenever the debt is actually paid down.
PROJECTION_FUNCTION_BUDGET = 8
PROJECTION_LINE_BUDGET = 720


def _functions() -> list[tuple[str, int]]:
    tree = ast.parse(PROJECTION.read_text(encoding="utf-8"))
    return [
        (node.name, (node.end_lineno or node.lineno) - node.lineno)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    ]


def test_the_decision_document_exists_and_names_its_falsifier() -> None:
    """A decision with no stated falsifier is a preference."""
    text = DECISION.read_text(encoding="utf-8")

    assert "compile-stage compiler plugin in the object module" in text
    assert "would falsify this decision" in text


def test_the_generator_side_specialization_debt_does_not_grow() -> None:
    """The projection may shrink. New specialization at generate may not appear.

    A budget rather than a prohibition, because the debt is real and being paid
    per function with parity evidence. What this forbids is adding to it.
    """
    functions = _functions()
    total = sum(lines for _, lines in functions)

    assert len(functions) <= PROJECTION_FUNCTION_BUDGET, (
        f"{len(functions)} functions in the generate-stage projection, budget {PROJECTION_FUNCTION_BUDGET}. "
        "New backend specialization belongs in a compile-stage plugin; see the W07 decision."
    )
    assert total <= PROJECTION_LINE_BUDGET, f"{total} lines, budget {PROJECTION_LINE_BUDGET}. Same reason."


def test_the_budget_is_not_stale() -> None:
    """A budget far above the real figure stops measuring anything."""
    functions = _functions()
    total = sum(lines for _, lines in functions)

    assert total >= PROJECTION_LINE_BUDGET - 200, (
        f"the projection is {PROJECTION_LINE_BUDGET - total} lines under budget; "
        "lower the budget so it keeps holding a line"
    )


def test_the_backend_neutral_plan_is_available_before_validation() -> None:
    """The seam the decision relies on: a compile-stage plan a validator can see."""
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from kernel import PluginRegistry

    registry = PluginRegistry(REPO_ROOT / "topology-tools")
    registry.load_manifest(REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml")

    compiler = registry.specs["base.compiler.security_plan"]
    validator = registry.specs["base.validator.security_plan"]

    compiler_stages = [item.value if hasattr(item, "value") else str(item) for item in compiler.stages]
    validator_stages = [item.value if hasattr(item, "value") else str(item) for item in validator.stages]

    assert compiler_stages == ["compile"]
    assert validator_stages == ["validate"]
    assert validator.consumes[0]["from_plugin"] == "base.compiler.security_plan"


def test_the_migration_order_names_the_blocked_step() -> None:
    """`_extract_security_matrix` moved on 2026-09-29, after its own blocker.

    It used to diverge from the compiler (W05, zone membership) and later
    turned out to re-derive R1-R6 itself as well (N-07) - a third derivation
    the W05 baseline never named. Both had to be characterized and fixed
    first; moving the function was a behaviour change, not a refactor, which
    is why the document records what unblocked it rather than only that it
    moved.
    """
    text = DECISION.read_text(encoding="utf-8")
    names = {name for name, _ in _functions()}

    assert "_extract_security_matrix" in names, "the function was renamed; update the decision"
    assert "_extract_security_matrix" in text
    assert "W05" in text
    assert "N-07" in text


@pytest.mark.parametrize("name", [])
def test_the_first_migration_candidates_still_exist(name: str) -> None:
    """If one has moved, the order in the decision needs updating with it.

    Empty on purpose: `_derive_mikrotik_capability_flags`, the sole original
    candidate, migrated on 2026-09-29 (W07 migration order item 1) and moved
    to `test_the_migrated_helpers_are_gone_rather_than_dormant` below.
    """
    assert name in {function for function, _ in _functions()}


@pytest.mark.parametrize(
    "name",
    [
        "_build_vlan_cidr_index",
        "_resolve_vlan_refs_to_cidrs",
        "_row_class",
        "_derive_mikrotik_capability_flags",
        "_extract_capabilities",
        "_extract_wireguard_tunnels",
        "_extract_containers",
        "_extract_wifi_config",
        "_build_routing_policy_entry",
        "_extract_mac_vlan_assignments",
    ],
)
def test_the_migrated_helpers_are_gone_rather_than_dormant(name: str) -> None:
    """Migrated on 2026-09-15 and 2026-09-29. The point is the absence, not the line count.

    A helper kept "just in case" is a second derivation waiting to be reached
    for, which is what A24 forbids. `_build_vlan_cidr_index` and
    `_resolve_vlan_refs_to_cidrs` are replaced by `vlan_cidr_map` from
    `base.compiler.security_matrix`; `_row_class` served the zone oracle, which
    now lives in the parity test. `_derive_mikrotik_capability_flags` and
    `_extract_capabilities` (W07 migration order item 1, 2026-09-29) moved
    verbatim to `object.mikrotik.compiler.capability_flags`, a compile-stage
    plugin; the projection now reads `capability_flags`, a required argument,
    instead of deriving it. `_extract_wireguard_tunnels` (W07 migration order
    item 4a, 2026-09-29) moved the same way to `object.mikrotik.compiler.
    wireguard_tunnels`; the projection now reads `wireguard_tunnels`, also a
    required argument. `_extract_containers` (W07 migration order item 4b,
    2026-09-29) moved the same way to `object.mikrotik.compiler.containers`;
    the projection now reads `containers`, also a required argument.
    `_extract_wifi_config` (W07 migration order item 4c, 2026-09-29) moved
    the same way to `object.mikrotik.compiler.wifi_config`; the projection
    now reads `wifi_config`, also a required argument.
    `_build_routing_policy_entry` (W07 migration order item 4d, 2026-09-29)
    moved the same way to `object.mikrotik.compiler.routing_policies`; the
    projection now reads `routing_policies`, also a required argument.
    `_extract_mac_vlan_assignments` (W07 migration order item 4e,
    2026-09-29) moved the same way to `object.mikrotik.compiler.
    mac_vlan_assignments`; the projection now reads `mac_vlan_assignments`,
    also a required argument.
    Asserting they are gone is what stops the debt from being paid on paper
    and reinstated in the next change.
    """
    assert name not in {function for function, _ in _functions()}
    assert name not in PROJECTION.read_text(encoding="utf-8")
