# ADR 0086 — Master Board

Unified execution board for:
- `adr/0086-analysis/WAVE1-ISSUES.md`
- `adr/0086-analysis/WAVE2-ISSUES.md`
- `adr/0086-analysis/WAVE3-ISSUES.md`

---

## 1) Program Objectives

- Reduce plugin-system complexity without breaking runtime contracts.
- Preserve deterministic discovery chain and project extensibility.
- Consolidate duplicated validators with diagnostic parity.
- Simplify standalone plugin layout and normalize IDs.

---

## 2) Critical Path

1. **W1-01** ADR/analysis consistency
2. **W1-03** discovery order invariants
3. **W1-04** boundary guard hardening
4. **W1-02** boundary tests migration
5. **W1-05** manifest ID policy test
6. **W1-07** Wave 1 final gate
7. **W2-01 -> W2-04** reference validator consolidation + parity harness
8. **W2-05 -> W2-06** router-port consolidation + manifest rewiring
9. **W2-08** Wave 2 final gate
10. **W3-01 -> W3-06** layout cleanup + ID normalization + architecture tests
11. **W3-07 -> W3-08** final parity and cutover sign-off

---

## 3) Status Tracker

Legend: `TODO` | `IN-PROGRESS` | `BLOCKED` | `DONE`

### Wave 1

| Issue | Title | Owner | Status | Notes |
|------|-------|-------|--------|-------|
| W1-01 | ADR/Analysis Consistency | - | DONE | Contract-boundary model aligned in ADR + analysis set |
| W1-02 | Boundary Tests Refactor | - | DONE | Runtime contract checks supersede legacy visibility assumptions |
| W1-03 | Discovery Order Invariants | - | DONE | Discovery/root-order tests active in contract + integration suites |
| W1-04 | Boundary Guard Hardening | - | DONE | Forbidden-path diagnostics enforced by discover boundary tests |
| W1-05 | Manifest ID Policy Lint | - | DONE | `test_manifest_id_policy.py` active and passing |
| W1-06 | Baseline Capture | - | DONE | Baseline/rollback evidence anchored in wave boundary commits |
| W1-07 | Wave 1 Final Gate | - | DONE | Re-run on 2026-04-03: plugin_contract + plugin_integration + validate-v5 + compile parity |

### Wave 2

| Issue | Title | Owner | Status | Notes |
|------|-------|-------|--------|-------|
| W2-01 | Ref Rule Catalog | - | DONE | `REFERENCE-RULE-CATALOG.md` published |
| W2-02 | Declarative Ref Validator | - | DONE | `declarative_reference_validator.py` added |
| W2-03 | Manifest Wiring (Refs) | - | DONE | Refs entries rewired to declarative validator |
| W2-04 | Diagnostic Parity Harness | - | DONE | `test_declarative_reference_validator_parity.py` added |
| W2-05 | Router Port Consolidation | - | DONE | `router_port_validator.py` added |
| W2-06 | Manifest Rewire (Ports) | - | DONE | Router class/object manifests rewired |
| W2-07 | ID Mapping Notes | - | DONE | `WAVE2-ID-MAPPING.md` published |
| W2-08 | Wave 2 Final Gate | - | DONE | `plugin_contract`, focused `plugin_integration`, `validate-v5` passed |

### Wave 3

| Issue | Title | Owner | Status | Notes |
|------|-------|-------|--------|-------|
| W3-01 | Standalone Inventory | - | DONE | `WAVE3-STANDALONE-INVENTORY.md` published |
| W3-02 | Standalone Relocation | - | DONE | Redundant router wrapper validators removed; framework-shared generator helpers/projections relocated from `object-modules/_shared` to `topology-tools/plugins/generators` |
| W3-03 | Manifest Rewire Post-Move | - | DONE | Router/GL.iNet/MikroTik module manifests rewired; no legacy wrapper entries remain |
| W3-04 | Manifest Minimization | - | DONE | Empty router/glinet manifests removed; service directory `topology/object-modules/_shared` removed |
| W3-05 | ID Normalization | - | DONE | `WAVE3-ID-MAPPING.md` published; network validator ID normalized to dot-style namespace |
| W3-06 | Layout Policy Tests | - | DONE | `test_plugin_layout_policy.py` enforces removed-empty-manifest + ID normalization policy |
| W3-07 | Compile Parity Gate | - | DONE | `compile-topology.py` passed in parallel and `--no-parallel-plugins` modes |
| W3-08 | Final Validation + Sign-off | - | DONE | `plugin_contract`, full `plugin_integration`, `validate-v5` passed; recovery dry-run docs added |

---

## 4) Wave Gates (Definition of Done)

### Wave 1 DoD

- Discovery chain tests pass.
- Boundary model tests aligned to contract-based semantics.
- ID policy lint/test introduced.
- `validate-v5` passes with `V5_SECRETS_MODE=passthrough`.

### Wave 2 DoD

- Refs validators consolidated with parity guarantees.
- Router-port validators consolidated.
- Manifest graph valid after rewiring.
- `validate-v5` and focused integration tests green.

### Wave 3 DoD

- Standalone plugins relocated to framework plugin families.
- Module manifests minimized to required extension points.
- ID normalization complete and consistent.
- Full compile parity (`parallel` + `--no-parallel-plugins`) passes.
- Final cutover checklist completed.

---

## 5) Rollback Boundaries

### Wave 1

- `adr0086-wave1-block-a` (W1-01..W1-03)
- `adr0086-wave1-block-b` (W1-04..W1-05)
- `adr0086-wave1-done` (W1-06..W1-07)

### Wave 2

- `adr0086-wave2-block-a` (W2-01..W2-03)
- `adr0086-wave2-block-b` (W2-04)
- `adr0086-wave2-block-c` (W2-05..W2-06)
- `adr0086-wave2-done` (W2-07..W2-08)

### Wave 3

- `adr0086-wave3-block-a` (W3-01..W3-03)
- `adr0086-wave3-block-b` (W3-04..W3-05)
- `adr0086-wave3-block-c` (W3-06)
- `adr0086-wave3-done` (W3-07..W3-08)

---

## 6) KPI / Metrics Board

Track before/after per wave:

1. Plugin count by family.
2. Validator file count.
3. Stage runtimes (`discover`, `compile`, `validate`, `generate`).
4. Test suite duration (`plugin_contract`, `plugin_integration`).
5. Discovery invariant pass rate.
6. Diagnostic drift count (approved vs unapproved).

---

## 7) Weekly Update Template

```markdown
## ADR0086 Weekly Update (YYYY-MM-DD)

### Completed
- [ ] W?-?? ...

### In Progress
- [ ] W?-?? ...

### Blockers
- [ ] ...

### Metrics Snapshot
- plugin_count_total:
- validator_file_count:
- discover_stage_ms:
- validate_stage_ms:
- plugin_contract_tests_s:
- plugin_integration_tests_s:

### Next Week Plan
- [ ] ...
```

---

## 8) Command Pack (Quick Gates)

```bat
python -m pytest tests\plugin_contract -q
python -m pytest tests\plugin_integration\test_module_manifest_discovery.py -q
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
python topology-tools\compile-topology.py
python topology-tools\compile-topology.py --no-parallel-plugins
```
