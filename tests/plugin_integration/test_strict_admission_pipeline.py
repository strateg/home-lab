#!/usr/bin/env python3
"""The strict boundary, exercised through the pipeline rather than in isolation.

The unit tests in `tests/plugin_contract/test_strict_admission_boundary.py` check
the decision function. These check what the pipeline actually leaves behind,
because a function that says no while something else writes the file is the
failure the boundary exists to prevent - and it is invisible to a test that only
reads a return value.

The positive control lives here too: a prepared strict plan must be admitted, or
an implementation that refuses everything would satisfy every case below.
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
from plugins.validators.strict_admission import (  # noqa: E402
    STRICT_PROVENANCE,
    content_digest,
    evaluate,
    strict_artifacts,
)

from tests.helpers.plugin_execution import publish_for_test  # noqa: E402

# Where strict rendering would put things. None of these may exist while
# admission is refused, and listing them is what makes their absence checkable
# rather than incidental.
STRICT_ARTIFACT_PATHS = [
    REPO_ROOT / "generated" / "home-lab" / "strict",
    REPO_ROOT / "build" / "strict",
]


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


def _real_rows() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT))
    from netmodel.snapshot import DEFAULT_SNAPSHOT, SnapshotMissing, load_snapshot

    try:
        model = load_snapshot()
    except SnapshotMissing:
        pytest.skip(f"{DEFAULT_SNAPSHOT} absent; run `task netmodel:snapshot` first")

    rows = []
    for group, items in model.get("instances", {}).items():
        if not isinstance(items, list):
            continue
        for row in items:
            lineage = (row.get("class") or {}).get("lineage") or []
            rows.append(
                {
                    "group": group,
                    "instance": row.get("instance_id"),
                    "class_ref": lineage[-1] if lineage else None,
                    "layer": row.get("layer"),
                    "extensions": row.get("instance_data") or {},
                }
            )
    return rows


def _run_pipeline(rows: list[dict] | None) -> tuple[dict, dict]:
    """Compile the plan and verify it, the way the pipeline does."""
    registry = _registry()
    ctx = _context()
    if rows is not None:
        publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))

    compiled = registry.execute_plugin("base.compiler.security_plan", ctx, Stage.COMPILE)
    plan = compiled.output_data["security_plan"]

    verified = registry.execute_plugin("base.validator.security_plan", ctx, Stage.VALIDATE)
    record = verified.output_data.get("security_plan_verification", {})
    return plan, record


# --- the positive control, through the pipeline shape --------------------------------


def test_a_prepared_strict_plan_is_admitted() -> None:
    """Without this, refusing everything would satisfy every test below."""
    rows = _real_rows()
    plan, record = _run_pipeline(rows)

    prepared = copy.deepcopy(plan)
    prepared["provenance"] = STRICT_PROVENANCE
    prepared["strict_eligible"] = prepared["scopes"]
    prepared["blocked_scopes"] = []
    prepared_record = {**record, "plan_digest": content_digest(prepared), "errors": 0, "complete": True}

    admission = evaluate(
        plan=prepared,
        verification=prepared_record,
        approved_intent={"approved": True, "approver": "security-lead"},
    )

    assert admission.admitted, admission.reasons


# --- condition 1: the real plan, fully lowered and verified, is refused ----------------


def test_the_real_plan_is_refused_despite_lowering_completely() -> None:
    """Every override lowers, the check passes, and it is still not admissible."""
    plan, record = _run_pipeline(_real_rows())

    assert plan["blocked_scopes"] == [], "the real plan should lower completely"
    assert plan["lowering_complete"] == plan["scopes"]
    assert record["errors"] == 0, "the real plan should verify without errors"

    admission = evaluate(
        plan=plan, verification=record, approved_intent={"approved": True, "approver": "security-lead"}
    )

    assert not admission.admitted
    assert any("legacy_shadow" in reason for reason in admission.reasons)


# --- condition 2: a missing input blocks the strict path -------------------------------


def test_a_missing_source_input_blocks_admission() -> None:
    """E7008 is reported, and the boundary acts on it rather than noting it.

    The compiler declares `normalized_rows` as required, so without them the
    registry does not run it at all - the missing-input case belongs to the
    validator, which declares the same input as optional precisely so that its
    absence becomes a diagnostic rather than a plugin nobody executed.
    """
    plan, _ = _run_pipeline(_real_rows())

    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))
    verified = registry.execute_plugin("base.validator.security_plan", ctx, Stage.VALIDATE)
    record = verified.output_data["security_plan_verification"]

    assert record["complete"] is False, "the check must record that it did not complete"
    assert "E7008" in [diag.code for diag in verified.diagnostics]

    prepared = copy.deepcopy(plan)
    prepared["provenance"] = STRICT_PROVENANCE
    prepared["strict_eligible"] = prepared["scopes"]
    admission = evaluate(
        plan=prepared,
        verification={**record, "plan_digest": content_digest(prepared)},
        approved_intent={"approved": True, "approver": "security-lead"},
    )

    assert not admission.admitted
    assert any("did not complete" in reason for reason in admission.reasons)


def test_the_missing_input_is_reported_as_e7008_in_the_same_run() -> None:
    registry = _registry()
    ctx = _context()
    publish_for_test(
        ctx,
        "base.compiler.security_plan",
        "security_plan",
        {"schema_version": 1, "rules": [], "scopes": ["scope.a"], "unlowerable": []},
    )

    result = registry.execute_plugin("base.validator.security_plan", ctx, Stage.VALIDATE)

    assert "E7008" in [diag.code for diag in result.diagnostics]


# --- condition 3: a plan edited after the pipeline verified it loses admission ------------


def test_editing_the_plan_after_the_pipeline_verified_it_loses_admission() -> None:
    plan, record = _run_pipeline(_real_rows())

    mutated = copy.deepcopy(plan)
    mutated["provenance"] = STRICT_PROVENANCE
    mutated["strict_eligible"] = mutated["scopes"]
    mutated["rules"] = [rule for rule in mutated["rules"] if not rule["origin"].startswith("guard:")]
    mutated["digest"] = content_digest(mutated)  # self-consistent on purpose

    admission = evaluate(
        plan=mutated, verification=record, approved_intent={"approved": True, "approver": "security-lead"}
    )

    assert not admission.admitted
    assert any("changed after checking" in reason for reason in admission.reasons)


# --- condition 4: no strict artifacts, and no fallback ---------------------------------------


def test_the_pipeline_leaves_no_strict_artifact_while_admission_is_refused() -> None:
    """Checked on disk after the run, not from the decision function's answer.

    A function that says no while something else writes the file is exactly the
    failure this guards, and it is invisible to a test that reads a return value.
    """
    plan, record = _run_pipeline(_real_rows())
    admission = evaluate(
        plan=plan, verification=record, approved_intent={"approved": True, "approver": "security-lead"}
    )
    assert not admission.admitted, "this test assumes the real plan is refused"

    present = strict_artifacts(STRICT_ARTIFACT_PATHS)

    assert present == [], f"strict artifacts exist while admission is refused: {present}"


def test_a_refusal_does_not_enable_a_legacy_path() -> None:
    plan, record = _run_pipeline(_real_rows())

    admission = evaluate(plan=plan, verification=record, approved_intent=None)

    assert not admission.admitted
    assert admission.legacy_fallback_permitted is False


def test_the_declared_artifact_paths_are_the_ones_a_renderer_would_use() -> None:
    """A guard over paths nobody writes to would pass forever and mean nothing.

    There is no strict renderer yet, so this asserts the list is explicit and
    non-empty rather than that it currently matches a producer. When the first
    renderer lands its output path joins this list, and the guard starts biting.
    """
    assert STRICT_ARTIFACT_PATHS
    assert all(isinstance(path, Path) for path in STRICT_ARTIFACT_PATHS)
