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
EPOCH_ENV = "STRICT_WRITER_EPOCH"
MARKER_NAME = "strict-rules.json"
EPOCH = "2026-09-14T00:00:00Z"

# The plugins this test runs, and no others. The stage executor is the real one -
# dependency resolution, phase ordering and the envelope contract all apply - but
# running every generator in the repository would write real artifacts, which a
# test about not writing has no business doing.
PIPELINE = {
    "base.compiler.security_plan",
    "base.validator.security_obligations",
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
    monkeypatch.setenv(EPOCH_ENV, EPOCH)
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
    """The record the real validators publish for this exact plan.

    Both of them, in pipeline order: the obligations validator answers for the
    five it owns and the plan validator merges those into the one record
    admission reads. Running only the second would leave the other five with no
    status at all - which admission also refuses, but for the wrong reason.
    """
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    registry.execute_plugin("base.validator.security_obligations", ctx, Stage.VALIDATE)
    verified = registry.execute_plugin("base.validator.security_plan", ctx, Stage.VALIDATE)
    return verified.output_data["security_plan_verification"]


def _approval_for(record: dict, plan: dict, **overrides) -> dict:
    approval = {
        "approved": True,
        "approved_by": "security-lead",
        "intent_digest": record["intent_digest"],
        "evidence_digest": record["evidence_digest"],
        "scopes": list(plan["scopes"]),
        "epoch": EPOCH,
    }
    approval.update(overrides)
    return approval


def _waived_rows(owner: str, rationale: str) -> list[dict]:
    """A source whose availability is discharged by an attestation rather than by Q.

    An explicitly empty `Q` with an owner and a reason is a claim - "nothing here
    has to keep working" - and it is what makes SEC-AVAIL pass without any
    requirement to check. It is therefore the case where the identity of the
    attestation matters most.
    """
    rows = _admissible_rows()
    rows[0]["extensions"]["availability_requirements"] = []
    rows[0]["extensions"]["availability_waiver"] = {"owner": owner, "rationale": rationale}
    return rows


# --- the positive control: a real check, and a real write ------------------------------


def test_an_admitted_plan_is_actually_written(tmp_path, monkeypatch) -> None:
    """Without this, a writer that never writes would satisfy every case below."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    assert record["errors"] == 0
    # `not_applicable` beside `pass`: the plan carries none of the five
    # constructs the other obligations govern, so there is nothing there for
    # them to decide. That is a third answer, and requiring `pass` from all nine
    # would demand a verdict on questions this plan does not raise.
    assert all(
        status in ("pass", "not_applicable")
        for statuses in record["obligations"].values()
        for status in statuses.values()
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
    def always_admit(**kwargs):
        # The digest and scopes are the real ones: `admitted_projection` refuses a
        # plan that is not the admitted one, so a lazier mutant would be stopped
        # by that check rather than by the decision this test is bypassing.
        admitted_plan = kwargs["plan"]
        return contract.Admission(
            admitted=True,
            plan_digest=contract.content_digest(admitted_plan),
            scopes=tuple(sorted(admitted_plan.get("scopes") or [])),
        )

    monkeypatch.setattr(contract, "evaluate", always_admit)

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


def test_replacing_the_attestation_invalidates_the_approval_it_was_given_for(
    tmp_path, monkeypatch
) -> None:
    """The waiver is the evidence discharging SEC-AVAIL, so the approval is bound to it.

    An explicitly empty `Q` with an owner and a reason makes SEC-AVAIL pass with
    nothing to check. Replacing the owner and the rationale leaves the permission
    set identical - correctly, so `intent_digest` does not move - and used to
    leave every digest unmoved, so the previous approval discharged a claim a
    different person now signs. Evidence has its own digest for exactly this.
    """
    first_rows = _waived_rows("owner-a", "reason-a")
    plan = _as_strict(_run_pipeline(first_rows)[0])
    first_record = _record_after_validation(plan, first_rows)
    assert first_record["obligations"][plan["scopes"][0]]["SEC-AVAIL"] == "pass"

    second_rows = _waived_rows("owner-b", "reason-b")
    second_record = _record_after_validation(plan, second_rows)

    assert second_record["intent_digest"] == first_record["intent_digest"], (
        "the permission set is unchanged; semantic identity must not move"
    )
    assert second_record["evidence_digest"] != first_record["evidence_digest"], (
        "a different person now signs the claim; evidence identity must move"
    )

    marker, output = _run_with_writer(
        rows=second_rows,
        plan=plan,
        tmp_path=tmp_path,
        approval=_approval_for(first_record, plan),
        monkeypatch=monkeypatch,
    )

    assert not marker.exists()
    assert any("signed by somebody else" in reason for reason in output["refusal"]), output["refusal"]


def test_an_unbounded_availability_requirement_writes_nothing(tmp_path, monkeypatch) -> None:
    """R2 through the writer: the requirement both Q checks used to skip."""
    rows = _admissible_rows()
    rows[0]["extensions"]["availability_requirements"] = [
        {"name": "everything-must-work", "from_zone_ref": "z.a", "to_zone_ref": "z.b"}
    ]
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    assert record["errors"] >= 1, "an unbounded requirement must not verify clean"

    marker, _ = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists()


@pytest.mark.parametrize("value", ["false", 1, "true"])
def test_a_non_boolean_approval_writes_nothing(value, tmp_path, monkeypatch) -> None:
    """Checked at the writer, not only in the verdict.

    `approved: "false"` is a truthy string. A boundary that reads consent from
    truthiness fails on a type it never asked for, and what matters is that the
    file does not appear - a return value nobody acts on proves nothing.
    """
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    marker, output = _run_with_writer(
        rows=rows,
        plan=plan,
        tmp_path=tmp_path,
        approval=_approval_for(record, plan, approved=value),
        monkeypatch=monkeypatch,
    )

    assert not marker.exists(), f"approved={value!r} reached the write"
    assert any("not the boolean" in reason for reason in output["refusal"]), output["refusal"]


def test_a_transport_the_contract_cannot_act_on_writes_nothing(tmp_path, monkeypatch) -> None:
    """The grammar gap, through the writer: a kind nobody implemented."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    plan["rules"][0]["transport"] = {"kind": "not_implemented"}
    record = _record_after_validation(plan, rows)

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists()
    assert any("cannot act on" in reason for reason in output["refusal"]), output["refusal"]


def test_the_real_plan_is_inside_the_grammar_this_contract_reads() -> None:
    """A grammar stricter than the producer would refuse every real plan."""
    from plugins.validators.strict_admission import malformed_constructs, unsupported_constructs

    plan, _ = _run_pipeline(_real_rows())

    assert unsupported_constructs(plan) == []
    assert malformed_constructs(plan) == []


def test_no_expected_epoch_writes_nothing(tmp_path, monkeypatch) -> None:
    """R5: the caller must name the epoch it is deciding for."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    output_dir = tmp_path / "out"
    monkeypatch.setenv(MARKER_ENV, str(output_dir))
    monkeypatch.delenv(EPOCH_ENV, raising=False)
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(json.dumps(_approval_for(record, plan)), encoding="utf-8")
    monkeypatch.setenv(APPROVAL_ENV, str(approval_file))

    registry = _pipeline_registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))
    registry.execute_stage(Stage.VALIDATE, ctx)
    results = {item.plugin_id: item.output_data for item in registry.execute_stage(Stage.GENERATE, ctx)}

    assert not (output_dir / MARKER_NAME).exists()
    assert any("epoch-qualified" in reason for reason in results[WRITER_ID]["refusal"])


@pytest.mark.parametrize(
    ("label", "override"),
    [
        ("named sources", {"sources": ["z.a"]}),
        ("named destinations", {"destinations": ["z.b"]}),
        ("a single transport", {"transport": {"kind": "ports", "protocol": "tcp", "ports": [53]}}),
    ],
)
def test_a_narrowed_terminal_writes_nothing(label: str, override: dict, tmp_path, monkeypatch) -> None:
    """The 2026-09-15 finding, through the writer.

    A terminal narrowed to one source left `z.b -> z.a UDP/9999` reaching no rule
    at all - inside the closed endpoint set, outside `Q` - and the run came back
    errors 0, four obligations `pass`, admission granted, marker written. A
    terminal narrowed to `tcp/53` was worse than incomplete: the verifier read it
    as an unconditional deny while the projection handed the consumer the finite
    predicate, so one plan meant two things.

    The counterexample flow is deliberately outside `Q`. Inside it, the test
    would prove availability and leave termination unguarded, which is how this
    went unnoticed.
    """
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    for entry in plan["rules"]:
        if entry["terminal"]:
            entry.update(override)
    record = _record_after_validation(plan, rows)

    assert record["errors"] >= 1, f"a terminal with {label} verified clean: {record}"

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists(), f"a terminal with {label} reached the write"
    assert output["refusal"], output


def test_the_full_scope_terminal_still_writes(tmp_path, monkeypatch) -> None:
    """The positive control for the invariant, beside its three refusals."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    terminal = next(entry for entry in plan["rules"] if entry["terminal"])
    assert terminal["sources"] == [] and terminal["destinations"] == []
    assert terminal["transport"] == {"kind": "any"}

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert marker.exists(), f"the canonical terminal must still be admissible: {output}"


def test_the_admission_contract_refuses_a_narrowed_terminal_on_its_own(tmp_path, monkeypatch) -> None:
    """Two independent refusals, because one of them could be edited out.

    The validator reports the shape and the admission grammar forbids it. Either
    alone would close the finding; both means a record that somehow said `pass`
    still does not admit the plan.
    """
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    clean_record = _record_after_validation(plan, rows)

    for entry in plan["rules"]:
        if entry["terminal"]:
            entry["transport"] = {"kind": "ports", "protocol": "tcp", "ports": [53]}

    # A record that reports success for the narrowed plan, which the real
    # validator will not produce - the point is that admission refuses anyway.
    forged = {**clean_record, "plan_digest": content_digest(plan)}

    admission = evaluate(
        plan=plan,
        verification=forged,
        approved_intent=_approval_for(clean_record, plan),
        expected_epoch=EPOCH,
    )

    assert not admission.admitted
    assert any("terminal" in reason for reason in admission.reasons), admission.reasons


def test_an_obligation_that_cannot_be_decided_writes_nothing(tmp_path, monkeypatch) -> None:
    """The five that had no checker, now answering for themselves.

    A plan declaring `state` makes SEC-STATE applicable, and nothing in the
    pipeline records sessions or an epoch, so it comes back `unverified` with the
    missing input named. Everything else about the run is admissible - which is
    the point: the only thing standing between this plan and a marker is an
    obligation nobody can decide.
    """
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    for entry in plan["rules"]:
        if not entry["terminal"]:
            entry["state"] = {"tracked": True}
    record = _record_after_validation(plan, rows)

    scope = plan["scopes"][0]
    assert record["obligations"][scope]["SEC-STATE"] == "unverified", record["obligations"]

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists()
    assert any("SEC-STATE" in reason for reason in output["refusal"]), output["refusal"]


def test_an_obligation_nothing_triggers_does_not_block_the_write(tmp_path, monkeypatch) -> None:
    """`not applicable` is not `unverified`, and conflating them would refuse everything.

    The plan carries none of the five constructs, so none of those obligations
    could be violated. The positive control still writes - which is what makes
    the refusal above mean something.
    """
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    scope = plan["scopes"][0]
    assert set(record["obligations"][scope].values()) == {"pass", "not_applicable"}

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert marker.exists(), output


def test_a_decidable_obligation_that_fails_writes_nothing(tmp_path, monkeypatch) -> None:
    """SEC-NAT has its input on the rule, so it is the one that can actually fail today."""
    rows = _admissible_rows()
    rows[0]["extensions"]["policy_overrides"].append(
        {
            "name": "web",
            "from_zone_ref": "z.c",
            "to_zone_ref": "z.d",
            "action": "accept",
            "ports": {"tcp": [443]},
        }
    )
    plan = _as_strict(_run_pipeline(rows)[0])
    for entry in plan["rules"]:
        if not entry["terminal"]:
            entry["nat"] = {"to": "10.0.0.5"}
    record = _record_after_validation(plan, rows)

    assert record["errors"] >= 1, "two originals collapsing onto one target is a failure"

    marker, _ = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert not marker.exists()


def test_a_partial_result_from_another_plan_is_not_merged(tmp_path, monkeypatch) -> None:
    """R3: a stale `pass` carried under the digest of a plan nobody checked it against.

    The review's sequence, with both real validators: the obligations validator
    examines a plan and publishes its verdict; the plan changes before the plan
    validator runs; the merge stamped the old verdict with the new plan's digest.
    A fresh run of the same producer on the changed plan said `fail`.

    Recomputing the partial record's digest would not repair it. The verdict
    inside was reached about something else.
    """
    rows = _admissible_rows()
    rows[0]["extensions"]["policy_overrides"].append(
        {
            "name": "web",
            "from_zone_ref": "z.c",
            "to_zone_ref": "z.d",
            "action": "accept",
            "ports": {"tcp": [443]},
        }
    )
    plan = _as_strict(_run_pipeline(rows)[0])

    # Two transforms, two different targets: no collision for this producer.
    targets = iter(["10.0.0.5", "10.0.0.6"])
    for entry in plan["rules"]:
        if not entry["terminal"]:
            entry["nat"] = {"to": next(targets)}

    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", copy.deepcopy(plan))
    registry.execute_plugin("base.validator.security_obligations", ctx, Stage.VALIDATE)

    # The plan changes between the two validators: both transforms now collapse
    # onto one target, which a fresh obligations run would report as a failure.
    changed = copy.deepcopy(plan)
    for entry in changed["rules"]:
        if not entry["terminal"]:
            entry["nat"] = {"to": "10.0.0.5"}
    publish_for_test(ctx, "base.compiler.security_plan", "security_plan", changed)

    verified = registry.execute_plugin("base.validator.security_plan", ctx, Stage.VALIDATE)
    record = verified.output_data["security_plan_verification"]

    assert "E7097" in [diag.code for diag in verified.diagnostics], "the stale record must be named"
    assert record["errors"] >= 1
    scope = changed["scopes"][0]
    assert record["obligations"][scope].get("SEC-NAT") != "pass"

    fresh = _record_after_validation(changed, rows)
    assert fresh["errors"] >= 1, "and a fresh run of the same producer agrees"


def test_a_fresh_partial_result_for_this_plan_is_merged(tmp_path, monkeypatch) -> None:
    """The positive control beside it: same inputs, same plan, merged and admitted."""
    rows = _admissible_rows()
    plan = _as_strict(_run_pipeline(rows)[0])
    record = _record_after_validation(plan, rows)

    scope = plan["scopes"][0]
    assert record["obligations"][scope]["SEC-NAT"] == "not_applicable"
    assert record["errors"] == 0

    marker, output = _run_with_writer(
        rows=rows, plan=plan, tmp_path=tmp_path, approval=_approval_for(record, plan), monkeypatch=monkeypatch
    )

    assert marker.exists(), output


def test_the_merge_takes_only_the_obligations_that_producer_owns(tmp_path, monkeypatch) -> None:
    """Its four verdicts are its own, and an unknown name is not a status.

    `.update` with whatever arrived would let one plugin overwrite the other's
    conclusions and let an unregistered obligation into a record admission reads
    as typed.
    """
    rows = _real_rows()
    plan, _ = _run_pipeline(rows)
    record = _record_after_validation(plan, rows)

    scope = sorted(record["obligations"])[0]
    statuses = record["obligations"][scope]

    assert statuses["SEC-AVAIL"] == "unverified", "the plan validator's own verdict, not overwritten"
    assert set(statuses) == {
        "SEC-ORDER",
        "SEC-COVER",
        "SEC-AUTH",
        "SEC-AVAIL",
        "SEC-NAT",
        "SEC-STATE",
        "SEC-TRANSITION",
        "SEC-PATH",
        "SEC-CAP",
    }


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
            "evidence_digest": record["evidence_digest"],
            "scopes": list(prepared["scopes"]),
            "epoch": EPOCH,
        },
        expected_epoch=EPOCH,
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
        plan=plan,
        verification=record,
        approved_intent={"approved": True, "approved_by": "security-lead"},
        expected_epoch=EPOCH,
    )
    assert not admission.admitted, "this test assumes the real plan is refused"

    present = strict_artifacts(STRICT_ARTIFACT_PATHS)

    assert present == [], f"strict artifacts exist while admission is refused: {present}"


def test_a_refusal_does_not_enable_a_legacy_path() -> None:
    plan, record = _run_pipeline(_real_rows())

    admission = evaluate(plan=plan, verification=record, approved_intent=None, expected_epoch=EPOCH)

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
