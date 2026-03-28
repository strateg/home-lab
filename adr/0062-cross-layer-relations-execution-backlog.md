# ADR 0062 Cross-Layer Relations Execution Backlog

- Date: 2026-03-12
- Revised: 2026-03-28
- Source ADR: `adr/0062-modular-topology-architecture-consolidation.md`
- Scope: execution tracker for enforced ADR0062 cross-layer dependency relations

## Purpose

Keep relation ownership, diagnostics, and acceptance evidence explicit and auditable.

## Backlog

| Relation | Source -> Target | Primary Validator Owner | Diagnostic Seed | Acceptance Test Target | Status |
|---|---|---|---|---|---|
| `storage.pool_ref` | `L4 -> L3` | `topology-tools/plugins/validators/reference_validator.py` (`base.validator.references`) | `E74xx` | `tests/plugin_integration/test_reference_validator.py` | enforced (evidence locked 2026-03-28) |
| `storage.volume_ref` | `L5 -> L3` | `topology-tools/plugins/validators/reference_validator.py` (`base.validator.references`) | `E74xx` | `tests/plugin_integration/test_reference_validator.py` | enforced (evidence locked 2026-03-28) |
| `network.bridge_ref` | `L4 -> L2` | `topology-tools/plugins/validators/reference_validator.py` (`base.validator.references`) | `E75xx` | `tests/plugin_integration/test_reference_validator.py` | enforced (evidence locked 2026-03-28) |
| `network.vlan_ref` | `L1/L4 -> L2` | `topology-tools/plugins/validators/reference_validator.py` (`base.validator.references`) | `E75xx` | `tests/plugin_integration/test_reference_validator.py` | enforced (evidence locked 2026-03-28) |
| `observability.target_ref` | `L6 -> L1/L4/L5` | `topology-tools/plugins/validators/reference_validator.py` (`base.validator.references`) | `E76xx` | `tests/plugin_integration/test_reference_validator.py` | enforced (evidence locked 2026-03-28) |
| `operations.target_ref` | `L7 -> L1/L4/L5/L6` | `topology-tools/plugins/validators/reference_validator.py` (`base.validator.references`) | `E77xx` | `tests/plugin_integration/test_reference_validator.py` | enforced (evidence locked 2026-03-28) |
| `power.source_ref` | `L1 -> L1` | `topology-tools/plugins/validators/power_source_refs_validator.py` (`base.validator.power_source_refs`) | `E78xx` | `tests/plugin_integration/test_l1_power_source_refs.py` | enforced (evidence locked 2026-03-28) |

## Sequencing

1. `storage.pool_ref` and `storage.volume_ref` (closed).
2. `network.bridge_ref` and `network.vlan_ref` (closed).
3. `observability.target_ref` and `operations.target_ref` (closed).
4. `power.source_ref` relation and occupancy/constraint checks (closed).

## Definition of Done Per Relation

1. Validator rule implemented with deterministic diagnostics.
2. Error codes registered in `v5/topology-tools/data/error-catalog.yaml`.
3. Positive and negative integration tests added and green.
4. ADR0062 relation status remains `enforced` and is contract-guarded.

## Contract Guard

- `tests/plugin_contract/test_adr0062_cross_layer_relation_contract.py` locks:
  - manifest owner plugins for all 7 relations,
  - error catalog codes (`E74xx`-`E78xx`) for relation diagnostics,
  - acceptance target test files for references and power-source relations.
