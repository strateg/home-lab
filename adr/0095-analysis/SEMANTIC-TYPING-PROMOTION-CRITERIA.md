# ADR 0095 Semantic Typing Promotion Criteria

**Status:** Promoted to authoritative mode  
**Promotion Date:** 2026-04-12  
**Scope:** Governance criteria and promotion record for `deps` semantic relation typing.

---

## 1. Current State (post-promotion)

- `deps` and `deps-json` use **authoritative semantic relation typing**.
- Direct dependency rows now include semantic relation categories in the primary contract.
- Compatibility aliases are preserved for migration stability:
  - `task inspect:deps-typed-shadow`
  - `task inspect:deps-json-typed-shadow`
  - `--typed-shadow` CLI flag (compatibility alias path)
- Active relation categories:
  - `network`
  - `storage`
  - `runtime`
  - `capability`
  - `binding`
  - `generic_ref`

---

## 2. Promotion Gate (authoritative switch prerequisites)

### G1 — Contract Stability

Required:
- typed relation output remains stable across CLI + JSON paths,
- compatibility aliases exist during transition.

Evidence:
- `tests/test_inspection_relations.py`
- `tests/test_inspection_json.py`
- `tests/test_inspect_topology.py`
- smoke evidence:
  - `task inspect:smoke-matrix`
  - `task validate:inspect-smoke`

### G2 — Coverage of Meaningful Edges

Required:
- typed relation classification covers at least **95%** of direct `deps` edges,
- `generic_ref` share does not exceed **40%**.

Evidence:
- `build/diagnostics/typed-shadow-report.json`
- `build/diagnostics/typed-shadow-report.txt`
- gate commands:
  - `task inspect:typed-shadow-gate`
  - `task validate:typed-shadow-gate`

Promotion snapshot:
- `coverage_percent=100.0`
- `generic_ref_share_percent=0.72`
- G2 gate PASS.

### G3 — Error/Drift Safety

Required:
- unresolved diagnostics preserved,
- resolved edge identity preserved under compatibility alias flow.

Evidence:
- `tests/test_inspection_json.py::test_deps_payload_typed_shadow_preserves_baseline_edge_contract`
- `tests/test_inspect_topology.py::test_deps_command_json_typed_shadow_preserves_baseline_edges`

### G4 — Operator Usability

Required:
- command reference documents authoritative typing mode and compatibility aliases,
- `generic_ref` interpretation is documented.

Evidence:
- `manuals/dev-plane/DEV-COMMAND-REFERENCE.md`

### G5 — ADR/Analysis Synchronization

Required:
- ADR0095 artifacts explicitly record authoritative status and compatibility implications.

Evidence:
- `adr/0095-topology-inspection-and-introspection-toolkit.md`
- `adr/0095-analysis/IMPLEMENTATION-PLAN.md`
- this file
- readiness/compliance evidence paths:
  - `task inspect:typed-shadow-readiness`
  - `task inspect:typed-shadow-readiness-gate`
  - `task validate:typed-shadow-readiness`
  - `task validate:typed-shadow-readiness-gate`

---

## 3. Promotion Decision Rule

Semantic typing can be authoritative only when:

1. `G1..G5` are PASS,
2. ADR0095 artifacts record the contract switch,
3. compatibility implications are documented for operators and CI.

If any gate regresses, keep authoritative contract but treat regression as a release blocker.

---

## 4. Promotion Record

**Decision:** Promote semantic relation typing from shadow/advisory mode to authoritative `deps` contract.

**Recorded in:** 2026-04-12 change set.

**Contract implications:**
- `deps` human-readable output includes semantic types inline.
- `deps-json` includes authoritative semantic relation metadata/fields.
- `--typed-shadow` remains supported as a compatibility alias.
- `deps-typed-shadow` and `deps-json-typed-shadow` task aliases remain during transition.

---

## 5. Post-Promotion Follow-up

1. Keep compatibility aliases for at least one release cycle.
2. Track alias usage before any removal/deprecation ADR update.
3. Keep `typed-shadow-gate` and readiness evidence tasks active for drift detection.
