# ADR 0062 Cross-Layer Relations Execution Backlog

- Date: 2026-03-12
- Source ADR: `adr/0062-modular-topology-architecture-consolidation.md`
- Scope: relations still marked as `planned` in ADR0062 cross-layer dependency table

## Purpose

Turn planned cross-layer relations into executable implementation units with ownership, diagnostics, and acceptance tests.

## Backlog

| Relation | Source -> Target | Primary Validator Owner | Diagnostic Seed | Acceptance Test Target | Status |
|---|---|---|---|---|---|
| `storage.pool_ref` | `L4 -> L3` | `v5/topology-tools/plugins/validators/reference_validator.py` (split to dedicated validator when rules exceed generic ref checks) | `E74xx` | `v5/tests/plugin_integration/test_reference_validator.py` | implemented (phase-1) |
| `storage.volume_ref` | `L5 -> L3` | `v5/topology-tools/plugins/validators/reference_validator.py` (split to dedicated validator when rules exceed generic ref checks) | `E74xx` | `v5/tests/plugin_integration/test_reference_validator.py` | implemented (phase-1) |
| `network.bridge_ref` | `L4 -> L2` | `v5/topology-tools/plugins/validators/reference_validator.py` (current); optional split to dedicated plugin later | `E75xx` | `v5/tests/plugin_integration/test_reference_validator.py` | implemented (phase-1) |
| `network.vlan_ref` | `L1/L4 -> L2` | `v5/topology-tools/plugins/validators/reference_validator.py` (current); optional split to dedicated plugin later | `E75xx` | `v5/tests/plugin_integration/test_reference_validator.py` | implemented (phase-1) |
| `observability.target_ref` | `L6 -> L1/L4/L5` | new validator plugin `base.validator.observability_targets` | `E76xx` | `v5/tests/plugin_integration/test_l6_observability_targets.py` | planned |
| `operations.target_ref` | `L7 -> L1/L4/L5/L6` | new validator plugin `base.validator.operations_targets` | `E77xx` | `v5/tests/plugin_integration/test_l7_operations_targets.py` | planned |
| `power.source_ref` | `L1 -> L1` | new validator plugin `base.validator.power_source_refs` | `E78xx` | `v5/tests/plugin_integration/test_l1_power_source_refs.py` | planned |

## Sequencing

1. `storage.pool_ref` and `storage.volume_ref` (reuse existing reference validator path first).
2. `network.bridge_ref` and `network.vlan_ref`.
3. `observability.target_ref` and `operations.target_ref`.
4. `power.source_ref` relation and occupancy/constraint checks.

## Definition of Done Per Relation

1. Validator rule implemented with deterministic diagnostics.
2. Error codes registered in `v5/topology-tools/data/error-catalog.yaml`.
3. Positive and negative integration tests added and green.
4. ADR0062 relation status updated from `planned` to `enforced`.
