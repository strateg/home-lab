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

# Measured 2026-09-14 at commit 3312ca0b. This may shrink as functions move to a
# compile-stage specializer; it must not grow.
PROJECTION_FUNCTION_BUDGET = 17
PROJECTION_LINE_BUDGET = 1565


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
    assert total <= PROJECTION_LINE_BUDGET, (
        f"{total} lines, budget {PROJECTION_LINE_BUDGET}. Same reason."
    )


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
    """`_extract_security_matrix` cannot move until W05 is resolved.

    It diverges from the compiler today, so moving it is a behaviour change and
    not a refactor. The document has to keep saying so, because it is the step
    anyone would reach for first.
    """
    text = DECISION.read_text(encoding="utf-8")
    names = {name for name, _ in _functions()}

    assert "_extract_security_matrix" in names, "the function was renamed; update the decision"
    assert "_extract_security_matrix" in text
    assert "W05" in text


@pytest.mark.parametrize("name", ["_derive_mikrotik_capability_flags", "_build_vlan_cidr_index"])
def test_the_first_migration_candidates_still_exist(name: str) -> None:
    """If one has moved, the order in the decision needs updating with it."""
    assert name in {function for function, _ in _functions()}
