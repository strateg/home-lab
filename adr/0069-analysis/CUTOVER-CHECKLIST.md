# ADR 0069 Cutover Checklist

**ADR:** `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
**Date:** 2026-03-10
**Status:** Ready for use during cutover

---

## Purpose

Gate final switch to plugin-first pipeline and retirement of legacy in-core compile/validate/emit branches.

---

## A. Stage and Ownership

- [ ] Runtime executes `compile -> validate -> generate` stages in this exact order.
- [ ] `ctx.compiled_json` is produced by compiler plugins before validator/generator stages.
- [ ] Core `compile-topology.py` does not contain domain-specific validation rules.
- [ ] Artifact emission is performed by generator plugins, not legacy core emit branches.

## B. Parity Gates

- [ ] Effective JSON parity passed for `production`.
- [ ] Effective JSON parity passed for `modeled`.
- [ ] Effective JSON parity passed for `test-real`.
- [ ] Diagnostics parity (codes + severities) passed on baseline fixtures.

## C. Early ADR Guardrails

### ADR 0005 (Determinism)
- [ ] Generated artifact ordering is deterministic across repeated runs.
- [ ] No noisy diffs on stable inputs.

### ADR 0027 (Quality Gates)
- [ ] Render/validation quality gates remain enabled by default in plugin-first path.
- [ ] Existing explicit opt-out behavior remains explicit and documented.

### ADR 0028 (Stable Entrypoints)
- [ ] Top-level CLI entrypoint remains stable for existing workflows.
- [ ] Internals are modularized without breaking CLI contract.

### ADR 0046 (Generator Architecture)
- [ ] Generator plugins keep separated concerns (rendering, data prep, IO).
- [ ] Generator plugin tests exist and pass.

### ADR 0050 (Artifact Layout Contract)
- [ ] Output paths/layout remain compatible with accepted generated artifact structure.
- [ ] Ownership boundaries for generated artifacts are unchanged.

## D. Test and CI

- [ ] `v5/tests/plugin_contract/*` green.
- [ ] `v5/tests/plugin_integration/*` green.
- [ ] Compiler/generator parity tests green.
- [ ] CI default path validates plugin-first execution.

## E. Cleanup Readiness

- [ ] Legacy core branches are either deleted or hard-disabled.
- [ ] Documentation updated to plugin-first architecture.
- [ ] ADR0069 status can be promoted from `Proposed` to `Accepted`.

---

## F. Evidence Requirements (Mandatory)

For every checked item above, provide at least one linked evidence artifact:

- Test report path (CI job URL or stored report file)
- Command/output snapshot
- Diff/parity report
- Runtime log excerpt proving stage execution path

Minimum evidence bundle for cutover approval:

1. Effective model parity reports for `production`, `modeled`, `test-real`.
2. Diagnostics parity report (codes + severities + targets).
3. Determinism proof (at least two repeated runs with no noisy diffs).
4. CLI compatibility run log for baseline command matrix.
5. Rollback drill result (legacy mode restore tested) per `adr/0069-analysis/IMPLEMENTATION-PLAN.md` (`Rollback Protocol (Normative)`).

---

## G. KPI and Threshold Gates

Cutover is blocked if any threshold is violated on baseline fixtures.

### Performance

- Plugin-first wall-clock time regression: <= 10% vs legacy baseline.
- Peak memory regression: <= 15% vs legacy baseline.

### Stability

- Determinism: 0 noisy diffs across repeated runs on unchanged input.
- Critical diagnostics drift: 0 missing/extra critical diagnostic codes.

### Quality

- Render/validation quality gates required by ADR0027: 100% pass on baseline suite.

---

## H. CLI Compatibility Matrix

Validate baseline workflows under plugin-first and legacy fallback.

| Command / Flow | Expected Result | Plugin-first | Legacy fallback |
|---|---|---|---|
| Default compile command | Success, expected artifacts, stable exit code | [ ] | [ ] |
| Compile with explicit output path | Artifacts in expected layout (ADR0050) | [ ] | [ ] |
| Compile with diagnostics/report options | Report produced, code/severity stable | [ ] | [ ] |
| Compile with quality gate enabled (default) | Gate executes and enforces policy | [ ] | [ ] |
| Compile with documented opt-out behavior | Opt-out remains explicit and documented | [ ] | [ ] |

Add links to evidence beside each row in review notes.

---

## I. GO / NO-GO Decision

### GO if all conditions are true

1. Sections A-E fully checked with evidence.
2. Section G thresholds are met.
3. Section H compatibility matrix is fully green.
4. Rollback path (`--pipeline-mode=legacy|plugin-first` or equivalent) is tested and documented according to `adr/0069-analysis/IMPLEMENTATION-PLAN.md` (`Rollback Protocol (Normative)`).

### NO-GO if any condition is true

1. Any parity mismatch without approved exception.
2. Any deterministic ordering regression.
3. Any critical CLI contract regression.
4. Any missing evidence for checked checklist items.

If NO-GO: keep default in legacy mode, open blocking incident, and track re-cutover date.
