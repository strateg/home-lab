# Acceptance Testing

This directory stores Testing Use Cases (TUC) and all related artifacts.

## Rules

1. Each use case must have its own folder:
   - `acceptance-testing/TUC-XXXX-short-name/`
2. Everything for the use case stays inside that folder:
   - TUC definition
   - implementation plan
   - test matrix
   - evidence log
   - generated artifacts and reports
3. Use `acceptance-testing/TUC-TEMPLATE/` as the baseline.

## Naming

- `TUC-XXXX` is a zero-padded sequence (`TUC-0001`, `TUC-0002`, ...).
- `short-name` is lowercase kebab-case.

## Current TUCs

- `TUC-0001-router-data-channel-mikrotik-glinet`

## Task Commands

- Run all TUC tests: `task acceptance:tests-all`
- Run one TUC file: `task acceptance:test TUC_TEST=tests/plugin_integration/test_tuc0001_router_data_link.py`
- Run one test case: `task acceptance:test-case PYTEST_NODE='tests/plugin_integration/test_tuc0001_router_data_link.py::test_tuc0001_network_validator_accepts_valid_cable_and_channel'`
- Run one quality gate: `task acceptance:quality TUC_SLUG=TUC-0001-router-data-channel-mikrotik-glinet`
- Run all quality gates: `task acceptance:quality-all`
