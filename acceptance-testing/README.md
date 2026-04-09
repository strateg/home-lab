# Acceptance Testing

This directory stores Testing Use Cases (TUC) and all related artefacts.

## Rules

1. Each use case must have its own folder:
   - `acceptance-testing/TUC-XXXX-short-name/`
2. Use current TUC structure:
   - root docs: `TUC.md`, `README.md`, `TEST-MATRIX.md`, `HOW-TO.md`
   - quality gate script: `quality-gate.py`
   - analysis docs/scripts: `analysis/`
   - generated outputs and logs: `artefacts/`
3. Use `acceptance-testing/TUC-TEMPLATE/` as the baseline.

## Naming

- `TUC-XXXX` is a zero-padded sequence (`TUC-0001`, `TUC-0002`, ...).
- `short-name` is lowercase kebab-case.

## Current TUCs

- `TUC-0001-router-data-channel-mikrotik-glinet`
- `TUC-0002-new-terraform-generator`
- `TUC-0003-mikrotik-live-parity-drift`
- `TUC-0004-soho-readiness-evidence`

## Task Commands

- Run all TUC tests: `task acceptance:tests-all`
- Run one TUC file/pattern: `task acceptance:test TUC_TEST='tests/**/test_tuc*.py'`
- Run one test case: `task acceptance:test-case PYTEST_NODE='<path>::<test_name>'`
- Run one quality gate: `task acceptance:quality TUC_SLUG=TUC-XXXX-short-name`
- Run all quality gates: `task acceptance:quality-all`
