# TUC-0001 Project Status Report (2026-03-27)

## Executive Summary

Status: **Passed and maintained**.

TUC-0001 is aligned with the current repository structure and plugin-first runtime:

- framework modules live in `topology/`
- project instances live in `projects/home-lab/topology/instances`
- acceptance validation is backed by:
  - `quality-gate.py` (current layout aware),
  - `tests/plugin_integration/test_tuc0001_router_data_link.py` (10 automated tests),
  - strict compile run evidence.

## What Was Updated

The TUC package was rewritten to remove stale paths and outdated assumptions:

- `TUC.md` rewritten for current inputs, scope, and acceptance criteria.
- `README.md` updated with current status and file map.
- `TEST-MATRIX.md` synchronized with the real automated tests (10 scenarios).
- `HOW-TO.md` rewritten with current commands and paths.
- `quality-gate.py` rewritten for:
  - `topology/` + `projects/home-lab/topology/instances` layout,
  - cable/channel contract checks,
  - endpoint device and port existence checks.
- `EVIDENCE-LOG.md` refreshed with 2026-03-27 run evidence.

## Current Verification Baseline (2026-03-27)

| Check | Command | Result |
|---|---|---|
| Quality gate | `python acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/quality-gate.py` | Passed (`0 errors`) |
| TUC integration suite | `pytest -q tests/plugin_integration/test_tuc0001_router_data_link.py` | Passed (`10 passed`) |
| Strict compile | `python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock ...` | Passed (`0 errors`) |

Latest artifacts:

- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-2026-03-27.json`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-2026-03-27.json`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-2026-03-27.txt`

## Scope Health

Validated and stable:

- L1 cable model (`obj.network.ethernet_cable`) + L2 channel model (`obj.network.ethernet_channel`).
- Cross-link contract (`creates_channel_ref` <-> `link_ref`).
- Endpoint/device/port validation with stable diagnostics.
- Preservation of cable instance properties and L1 power bindings in effective model.

Explicitly out of scope (unchanged):

- L3 routing behavior,
- deployment/runtime execution semantics,
- non-ethernet channel families.

## Recommended Next Steps

1. Keep this TUC as a regression gate in CI (quality gate + TUC pytest file).
2. Add a second TUC for another vendor pair instead of expanding TUC-0001 scope.
3. Periodically refresh `EVIDENCE-LOG.md` after major runtime/ADR changes.
