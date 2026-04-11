# ADR 0095 Semantic Typing Promotion Criteria

**Status:** Active (shadow-first phase)  
**Date:** 2026-04-11  
**Scope:** Criteria for promoting `deps` semantic relation typing from shadow mode to authoritative runtime interpretation.

---

## 1. Current State

- Authoritative dependency extraction remains the baseline `_ref/_refs` model.
- Semantic typing is currently available as **non-authoritative shadow**:
  - human output: `task inspect:deps-typed-shadow INSTANCE=<id>`
  - JSON output: `task inspect:deps-json-typed-shadow INSTANCE=<id>`
- Shadow classification domains:
  - `network`
  - `storage`
  - `runtime`
  - `capability`
  - `generic_ref`

Promotion is blocked until criteria below are satisfied.

---

## 2. Promotion Gate (all MUST pass)

### G1 — Contract Stability

Required:
- typed-shadow outputs remain backward-compatible for at least one release cycle,
- no breaking change to existing `deps` baseline output contracts.

Evidence:
- `tests/test_inspection_relations.py`
- `tests/test_inspection_json.py`
- `tests/test_inspect_topology.py`

### G2 — Coverage of Meaningful Edges

Required:
- on current home-lab topology, typed-shadow classifies at least **95%** of direct `deps` edges with a non-empty type list,
- `generic_ref` share does not exceed **40%** of classified labels (signals acceptable domain specificity).

Evidence:
- dedicated typed-shadow comparison report artifact in `build/diagnostics/` (to be added in next wave).

### G3 — Error/Drift Safety

Required:
- no regression in unresolved ref diagnostics vs baseline `deps`,
- no change in resolved edge set caused by enabling typed-shadow mode.

Evidence:
- parity tests comparing baseline `deps` vs `deps --typed-shadow` edge identity.

### G4 — Operator Usability

Required:
- manual command reference documents shadow semantics and non-authoritative status,
- troubleshooting guidance explains interpretation of `generic_ref`.

Evidence:
- `manuals/dev-plane/DEV-COMMAND-REFERENCE.md`
- follow-up update in troubleshooting/operator docs (if needed).

### G5 — ADR/Analysis Synchronization

Required:
- ADR0095 and analysis artifacts explicitly state shadow status and promotion rule.

Evidence:
- `adr/0095-topology-inspection-and-introspection-toolkit.md`
- `adr/0095-analysis/IMPLEMENTATION-PLAN.md`
- this file

---

## 3. Promotion Decision Rule

Semantic typing can be promoted from shadow to authoritative only when:

1. `G1..G5` are all **PASS**, and
2. promotion decision is recorded in ADR0095 artifacts with explicit contract changes, and
3. task/CLI compatibility implications are documented before switching defaults.

If any gate fails, keep shadow mode and treat typed output as advisory only.

---

## 4. Immediate Follow-up Work (implementation prep)

1. Add typed-shadow comparison report utility (`build/diagnostics/typed-shadow-report.{json,txt}`).
2. Add CI-friendly contract test for typed-shadow coverage thresholds.
3. Add explicit troubleshooting note for interpreting `generic_ref`.

These items are implementation prep and do not alter authoritative dependency behavior by themselves.
