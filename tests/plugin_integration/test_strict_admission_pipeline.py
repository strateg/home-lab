#!/usr/bin/env python3
"""The strict boundary, exercised through the pipeline rather than in isolation.

The unit tests in `tests/plugin_contract/test_strict_admission_boundary.py` check
the decision function. These check what the pipeline actually leaves behind,
because a function that says no while something else writes the file is the
failure the boundary exists to prevent - and it is invisible to a test that only
reads a return value.

**A writer runs here.** The first version of this file asserted that two
directories did not exist after running a compiler and a validator, and no
generator was ever executed - so it passed whether or not any control over
writing existed. The 2026-09-14 review recorded that as S3. A test-only
generator now runs in the generate stage, uses the same consumer contract a real
renderer will have to use, and writes exactly one marker file when - and only
when - admission says yes.

**The positive control is a real check of the exact plan.** The record is not
hand-written and not edited after the fact: the real validator examines the
prepared strict plan and publishes its own record, and the approval names the
intent digest that record carries. The only synthetic part is the plan's
provenance, because no approved bindings exist anywhere in the topology yet.
"""

from __future__ import annotations

import copy
import json
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

FIXTURE_MANIFEST = REPO_ROOT / "tests" / "fixtures" / "strict_writer" / "plugins.yaml"
WRITER_ID = "test.generator.strict_marker"
MARKER_ENV = "STRICT_WRITER_OUTPUT_DIR"
APPROVAL_ENV = "STRICT_WRITER_APPROVAL_FILE"
MARKER_NAME = "strict-rules.json"

# The plugins this test runs, and no others. The stage executor is the real one -
# dependency resolution, phase ordering and the envelope contract all apply - but
# running every generator in the repository would write real artifacts, which a
# test about not writing has no business doing.
PIPELINE = {
    "base.compiler.security_plan",
    "base.validator.security_plan",
    WRITER_ID,
}

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


def _pipeline_registry() -> PluginRegistry:
    registry = _registry()
    registry.load_manifest(FIXTURE_MANIFEST)
    assert WRITER_ID in registry.specs, "the test writer did not register"

    # In place: the planner and the resolver hold this same dict object.
    for plugin_id in list(registry.specs):
        if plugin_id not in PIPELINE:
            del registry.specs[plugin_id]

    # Dependency resolution is global and refuses a spec that names an absent
    # one, so the edges leaving this subset are pruned with it. What is being
    # tested is the ordering *between these three* and the write at the end of
    # it, not the whole repository's graph.
    for spec in registry.specs.values():
        spec.depends_on = [item for item in spec.depends_on if item in PIPELINE]
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


def _admissible_rows() -> list[dict]:
    """A source whose every obligation can actually pass.

    The real topology declares no availability requirements, so SEC-AVAIL comes
    back `unverified` there and nothing can be admitted - correctly. A positive
    control needs a source that states what has to keep working, or it would be
    testing the refusal again.
    """
    return [
        {
            "group": "network",
            "instance": "inst.security_matrix.fixture",
            "class_ref": "class.network.security_matrix",
            "layer": "L2",
            "extensions": {
                "policy_overrides": [
                    {
                        "name": "dns",
                        "from_zone_ref": "z.a",
                        "to_zone_ref": "z.b",
                        "action": "accept",
                        "ports": {"tcp": [53]},
                    }
                ],
                "availability_requirements": [
                    {
                        "name": "dns-must-work",
                        "from_zone_ref": "z.a",
                        "to_zone_ref": "z.b",
                        "ports": {"tcp": [53]},
                    }
                ],
            },
        }
    ]


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


def _as_strict(plan: dict) -> dict:
    """The one synthetic step: no approved bindings exist, so no plan is strict yet."""
    prepared = copy.deepcopy(plan)
    prepared["provenance"] = STRICT_PROVENANCE
    prepared["strict_eligible"] = list(prepared["scopes"])
    return prepared


def _run_with_writer(
    *, rows: list[dict], plan: dict | None, tmp_path: Path, approval: dict | None, monkeypatch
) -> tuple[Path, dict]:
    """Run compile, validate and generate as stages, and report what was written.

    When `plan` is given it is published in place of the compiler's output, which
    is how a strict-provenance plan reaches the real validator at all. The
    validator then checks *that* plan and publishes its own record; nothing here
    edits a record after it was produced.
    """
    output_dir = tmp_path / "out"
    monkeypatch.setenv(MARKER_ENV, str(output_dir))
    if approval is None:
        monkeypatch.delenv(APPROVAL_ENV, raising=False)
    else:
        approval_file = tmp_path / "approval.json"
        approval_file.write_text(json.dumps(approval), encoding="utf-8")
        monkeypatch.setenv(APPROVAL_ENV, str(approval_file))

    registry = _pipeline_registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    if plan is None:
        registry.execute_stage(Stage.COMPILE, ctx)
    else:
        publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))

    registry.execute_stage(Stage.VALIDATE, ctx)
    results = registry.execute_stage(Stage.GENERATE, ctx)

    written = {item.plugin_id: item.output_data for item in results}
    assert WRITER_ID in written, "the writer did not execute; this test would prove nothing"
    return output_dir / MARKER_NAME, written[WRITER_ID]


def _record_after_validation(plan: dict, rows: list[dict]) -> dict:
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    verified = registry.execute_plugin("base.validator.security_plan", ctx, Stage.VALIDATE)
    return verified.output_data["security_plan_verification"]


def _approval_for(record: dict, plan: dict, **overrides) -> dict:
    approval = {
        "approved": True,
        "approved_by": "security-lead",
        "intent_digest": record["intent_digest"],
        "scopes": list(plan["scopes"]),
        "epoch": "2026-09-14T00:00:00Z",
    }
    approval.update(overrides)
    return approval


# --- the positive control: a real check, and a real write ------------------------------


def test_an_admitted_plan_is_actually_written(tmp_path, monkeypatch) -> None:
    """Without this, a writer that never writes would satisfy every case below."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    assert record["errors"] == 0
    assert all(
        status == "pass" for statuses in record["obligations"].values() for status in statuses.values()
    ), record["obligations"]

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert marker.exists(), f"an admitted plan was not written: {output}"
    written = json.loads(marker.read_text(encoding="utf-8"))
    assert written["plan_digest"] == content_digest(plan)
    assert written["intent_digest"] == record["intent_digest"]
    assert written["scopes"] == sorted(plan["scopes"])
    # What reached disk is the admitted projection, not the plan the writer was
    # handed: a renderer must not write scopes no approval covered.
    assert {rule["scope"] for rule in written["rules"]} == set(plan["scopes"])


def test_the_marker_is_controlled_by_admission_and_nothing_else(tmp_path, monkeypatch) -> None:
    """The mutant the review asked for: bypass the decision, and the write happens.

    If the negative cases below passed for some other reason - a missing
    environment variable, a writer that never runs - this would not write either.
    It does, which is what makes their silence meaningful.
    """
    rows = _real_rows()
    plan, _ = _run_pipeline(rows)
    assert plan["provenance"] == "legacy_shadow", "this mutant needs a plan that is refused"

    import plugins.validators.strict_admission as contract

    # Patched at the source rather than on the loaded plugin module: the loader
    # re-executes the plugin file for each registry, and a patch applied to that
    # module object is overwritten by the next load.
    monkeypatch.setattr(
        contract,
        "evaluate",
        lambda **kwargs: contract.Admission(admitted=True, plan_digest="bypassed", scopes=("scope.a",)),
    )

    marker, _ = _run_with_writer(
        rows=rows, plan=None, tmp_path=tmp_path, approval=None, monkeypatch=monkeypatch
    )

    assert marker.exists(), "bypassing admission did not reach the write; the control proves nothing"


# --- the refusals, each one checked by the absence of that same file ---------------------


def test_the_real_plan_is_refused_and_nothing_is_written(tmp_path, monkeypatch) -> None:
    """Every override lowers, the check passes, and it is still not admissible."""
    rows = _real_rows()
    plan, record = _run_pipeline(rows)

    assert plan["blocked_scopes"] == [], "the real plan should lower completely"
    assert plan["lowering_complete"] == plan["scopes"]
    assert record["errors"] == 0, "the real plan should verify without errors"

    marker, output = _run_with_writer(
        rows=rows, plan=None, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists()
    assert any("legacy_shadow" in reason for reason in output["refusal"]), output["refusal"]


def test_an_approval_for_other_inputs_writes_nothing(tmp_path, monkeypatch) -> None:
    """`UNRELATED_APPROVAL` from the review, through the writer this time."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    marker, output = _run_with_writer(
        rows=rows,
        plan=plan,
        tmp_path=tmp_path,
        approval=_approval_for(record, plan, intent_digest="sha256-" + "9" * 64),
        monkeypatch=monkeypatch,
    )

    assert not marker.exists()
    assert any("approval of other inputs" in reason for reason in output["refusal"])


def test_an_unverified_obligation_writes_nothing(tmp_path, monkeypatch) -> None:
    """`MISSING_AVAILABILITY`: the real source declares no Q, so SEC-AVAIL is unverified.

    Everything else about this run is admissible - strict provenance, a real
    check with no errors, an approval naming the right intent and scopes. The
    only thing missing is that nobody said what has to keep working.
    """
    rows = _real_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    assert any(
        statuses.get("SEC-AVAIL") == "unverified" for statuses in record["obligations"].values()
    ), record["obligations"]

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists()
    assert any("SEC-AVAIL" in reason for reason in output["refusal"]), output["refusal"]


def test_no_approval_at_all_writes_nothing(tmp_path, monkeypatch) -> None:
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=None, monkeypatch=monkeypatch
    )

    assert not marker.exists()
    assert any("no approved intent" in reason for reason in output["refusal"])


def test_a_plan_edited_after_validation_writes_nothing(tmp_path, monkeypatch) -> None:
    """The validator checked one plan; the writer is handed another.

    The record is the genuine one the validator published for the original plan,
    and the plan reaching the generate stage has had its terminal deny removed -
    the edit that leaves a scope open. Its `digest` is recomputed to agree with
    itself on purpose: a payload that certifies its own identity is still not the
    plan that was checked.
    """
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    output_dir = tmp_path / "out"
    monkeypatch.setenv(MARKER_ENV, str(output_dir))
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(json.dumps(_approval_for(record, plan)), encoding="utf-8")
    monkeypatch.setenv(APPROVAL_ENV, str(approval_file))

    mutated = copy.deepcopy(plan)
    mutated["rules"] = [rule for rule in mutated["rules"] if not rule["terminal"]]
    mutated["digest"] = content_digest(mutated)

    registry = _pipeline_registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", mutated)
    publish_for_test(ctx, "base.validator.security_plan", "security_plan_verification", record)

    results = {item.plugin_id: item.output_data for item in registry.execute_stage(Stage.GENERATE, ctx)}

    assert not (output_dir / MARKER_NAME).exists()
    assert any("changed after checking" in reason for reason in results[WRITER_ID]["refusal"])


# --- the inputs the boundary needs, and what their absence means -------------------------


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

    assert record["source_available"] is False, "the check must record that it could not read the source"
    assert record["intent_digest"] == "", "there is no intent to name; an approval must not bind to one"
    assert "E7008" in [diag.code for diag in verified.diagnostics]

    prepared = _as_strict(plan)
    admission = evaluate(
        plan=prepared,
        verification={**record, "plan_digest": content_digest(prepared)},
        approved_intent={
            "approved": True,
            "approved_by": "security-lead",
            "intent_digest": record["intent_digest"],
            "scopes": list(prepared["scopes"]),
            "epoch": "2026-09-14T00:00:00Z",
        },
    )

    assert not admission.admitted
    assert any("did not run" in reason for reason in admission.reasons)


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


# --- no strict artifacts anywhere, and no fallback ---------------------------------------


def test_the_pipeline_leaves_no_strict_artifact_while_admission_is_refused() -> None:
    """Checked on disk after the run, not from the decision function's answer."""
    plan, record = _run_pipeline(_real_rows())
    admission = evaluate(
        plan=plan, verification=record, approved_intent={"approved": True, "approved_by": "security-lead"}
    )
    assert not admission.admitted, "this test assumes the real plan is refused"

    present = strict_artifacts(STRICT_ARTIFACT_PATHS)

    assert present == [], f"strict artifacts exist while admission is refused: {present}"


def test_a_refusal_does_not_enable_a_legacy_path() -> None:
    plan, record = _run_pipeline(_real_rows())

    admission = evaluate(plan=plan, verification=record, approved_intent=None)

    assert not admission.admitted
    assert admission.legacy_fallback_permitted is False


def test_the_real_plan_needs_only_the_obligations_the_framework_checks() -> None:
    """The deferral of the other five is a claim about this plan, so it is checked.

    SEC-PATH, SEC-NAT, SEC-STATE, SEC-TRANSITION and SEC-CAP are implemented in
    `netmodel` and mounted nowhere. That is safe only while no plan contains a
    construct they govern - and this asserts the current one does not, rather
    than assuming it.
    """
    from plugins.validators.strict_admission import CHECKED_OBLIGATIONS, applicable_obligations

    plan, _ = _run_pipeline(_real_rows())

    assert applicable_obligations(plan) == CHECKED_OBLIGATIONS


def test_the_real_topology_cannot_be_admitted_because_nobody_stated_q() -> None:
    """Measured rather than asserted: what the boundary says about the real sources."""
    rows = _real_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    unverified = {
        scope: statuses["SEC-AVAIL"]
        for scope, statuses in record["obligations"].items()
        if statuses["SEC-AVAIL"] != "pass"
    }

    assert unverified, "every scope now attests availability; this test describes the wrong topology"
    assert record["errors"] == 0, "the refusal is about an unstated objective, not about a defect"


def test_the_declared_artifact_paths_are_the_ones_a_renderer_would_use() -> None:
    """A guard over paths nobody writes to would pass forever and mean nothing.

    There is no strict renderer yet, so this asserts the list is explicit and
    non-empty rather than that it currently matches a producer. When the first
    renderer lands its output path joins this list, and the guard starts biting.
    """
    assert STRICT_ARTIFACT_PATHS
    assert all(isinstance(path, Path) for path in STRICT_ARTIFACT_PATHS)
