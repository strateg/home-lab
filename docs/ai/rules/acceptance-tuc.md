---
@pack: acceptance-tuc
@version: 1.0
@tokens: ~500
@adr: [0066, 0070, 0080, 0089]
---

# AI Rule Pack: Acceptance TUC

## Quick Reference

| Rule | Key Point |
|------|-----------|
| One folder per TUC | `acceptance-testing/TUC-XXXX-short-name/` |
| Use template | Start from `TUC-TEMPLATE/` |
| Self-contained | All materials inside TUC folder |
| Pytest coverage | `tests/plugin_integration/test_tuc*.py` |
| Artifacts dir | Use `artifacts/` (not `artefacts/`) |

## Load When

- `acceptance-testing/**`
- `tests/plugin_integration/test_tuc*.py`
- `scripts/acceptance/**`
- `taskfiles/acceptance.yml`

## TUC Folder Structure

| File | Purpose |
|------|---------|
| `TUC.md` | Use case definition |
| `README.md` | Quick overview |
| `TEST-MATRIX.md` | Test scenarios |
| `HOW-TO.md` | Execution guide |
| `quality-gate.py` | Automated checks |
| `analysis/` | Supporting analysis |
| `artifacts/` | Evidence outputs |

## Evidence Contract

| Evidence Type | Contents |
|---------------|----------|
| Positive compile | topology JSON, diagnostics JSON/TXT |
| Negative validation | Invalid fixture, expected error code |
| Determinism | Repeated compile comparison, stable snapshots |
| Regression gate | pytest node, quality gate result |

## Commands

| Action | Command |
|--------|---------|
| List TUCs | `task acceptance:list` |
| Run one gate | `task acceptance:quality TUC_SLUG=TUC-XXXX-name` |
| Run all gates | `task acceptance:quality-all` |
| Run one test | `task acceptance:test TUC_TEST='test_tucXXXX_*.py'` |
| Run all tests | `task acceptance:tests-all` |
| Compile evidence | `task acceptance:compile TUC_SLUG=TUC-XXXX-name` |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Scatter evidence | Hard to find/maintain | Keep in TUC folder |
| Broaden existing TUC | Scope creep | Create new TUC number |
| Skip quality gate | Untested scenarios | Run gate before closure |
| Use `artefacts/` | Historical typo | Use `artifacts/` |

## Validation

```bash
task acceptance:quality TUC_SLUG=<slug>
task acceptance:tests-all
task acceptance:quality-all
```
