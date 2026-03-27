# TUC-0001 Router Data Link + Data Channel

TUC-0001 verifies OSI-aligned modeling for two real router instances:

- L1 physical connectivity as `class.network.physical_link` (`obj.network.ethernet_cable`)
- L2 logical connectivity as `class.network.data_link` (`obj.network.ethernet_channel`)
- explicit cross-link contract: `creates_channel_ref` <-> `link_ref`
- L1 power wiring persistence (`power.source_ref`, `outlet_ref`)

## Current State (2026-03-27)

- Status: `passed`
- Automated suite: `tests/plugin_integration/test_tuc0001_router_data_link.py` (10 tests)
- Runtime baseline: plugin-first pipeline with ADR0080 stage/phase lifecycle
- Source topology layout:
  - framework modules: `topology/class-modules`, `topology/object-modules`
  - project instances: `projects/home-lab/topology/instances`

## Key Files

- Use case definition: `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TUC.md`
- Test matrix: `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TEST-MATRIX.md`
- Manual checks: `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/HOW-TO.md`
- Quality gate: `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/quality-gate.py`
- Analysis docs: `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/analysis/`
- Automated tests: `tests/plugin_integration/test_tuc0001_router_data_link.py`
