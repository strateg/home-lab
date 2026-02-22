# ADR 0033: Toolchain Contract Rebaseline After Modularization

- Status: Proposed
- Date: 2026-02-22

## Context

ADR 0031 defined a broad "toolchain contract alignment" scope across validators, generators, and deploy flows.
After ADR 0032 rollout, part of this scope is already implemented and should be treated as baseline, not open work:

1. Deterministic include loading is implemented (`!include_dir_sorted`) in topology loader.
2. L3 modular include contract and duplicate-ID checks are implemented in validator.
3. High-churn L1/L2 domains (`devices`, `media*`, `links`, `networks`) are migrated to deterministic include mode.
4. L1/L2 include contract checks are implemented in validator.

At the same time, ADR 0031 still contains open items and one schema mismatch:

1. MikroTik firewall address-lists remain template-hardcoded instead of derived from topology.
2. Deploy phase still has implicit fallback to legacy inventory path.
3. Docs generator still uses runtime-to-legacy compatibility mapping for service fields.
4. L6/L7 semantic validation remains incomplete (alerts/workflow/runbook contracts).
5. ADR 0031 requires backup `storage_ref` semantics, but current `BackupPolicy` schema does not define this field.

Without rebaseline, ADR 0031 mixes completed and pending work, reducing traceability and planning quality.

## Decision

Adopt a phased closure contract for remaining ADR 0031 scope and treat implemented ADR 0032 outcomes as current baseline.

### Baseline (already implemented)

1. Deterministic include model is canonical for migrated order-insensitive domains.
2. Manual `_index.yaml` remains only for order-sensitive domains (for example firewall policy order).
3. Validator enforces include contracts for:
   - L3 modular domains,
   - migrated L1/L2 high-churn domains.

### Remaining scope (phased)

1. Phase A: MikroTik topology-derived firewall inputs
   - Generate address-lists from L2 networks/trust-zones referenced by firewall policies.
   - Replace hardcoded RouterOS interface assumptions with explicit topology-to-interface mapping.
2. Phase B: Deployment inventory contract hardening
   - Make generated inventory path mandatory by default.
   - Keep legacy inventory only behind explicit compatibility flag.
3. Phase C: Runtime-first docs model
   - Remove runtime-to-legacy compatibility mutation from docs generator.
   - Render service endpoints from canonical endpoint model (`endpoints[]`) with compatibility read-path only where needed.
4. Phase D: L6/L7 semantic validator extensions
   - Validate alert trigger references to known observability entities.
   - Validate workflow/runbook command/script path contracts and working-directory assumptions.
5. Phase E: Backup storage destination contract
   - Align ADR and schema by introducing explicit backup destination reference to `storage_endpoints` (new schema field).
   - Deprecate ambiguous/legacy backup destination modeling with transition policy.

### Acceptance policy

1. Each phase must add strict-mode checks before generator/deploy behavior switches.
2. No silent fallback in strict mode for canonical contract paths.
3. Schema and ADR language must match exactly for backup destination fields.

## Consequences

Benefits:

- Clear separation between delivered baseline and pending changes.
- Reduced cognitive load for architecture reviews and rollout planning.
- Lower risk of accidental regressions from implicit fallback behavior.
- Traceable completion path for ADR 0031 remaining scope.

Trade-offs:

- Additional phased implementation and migration work across multiple modules.
- Short-term coexistence of compatibility behavior until phase cutovers complete.
- Stricter validation may fail existing non-canonical topology/deploy flows.

Migration impact:

1. Keep current deterministic modular baseline unchanged.
2. Implement phases A-E incrementally with validator-first guardrails.
3. Update ADR 0031 status/scope after phase completion review.

## References

- Prior ADRs:
  - [0031](0031-layered-topology-toolchain-contract-alignment.md)
  - [0032](0032-l3-data-modularization-and-layer-contracts.md)
- Implemented baseline commits:
  - `6a61f32` (L3 modularization + deterministic include discovery)
  - `01e1aeb` (L1/L2 high-churn domains switched to `!include_dir_sorted`)
  - `f5a2789` (validator include-contract checks for migrated L1/L2 domains)
- Key implementation files:
  - `topology-tools/topology_loader.py`
  - `topology-tools/scripts/validators/checks/storage.py`
  - `topology-tools/scripts/validators/checks/foundation.py`
  - `topology-tools/validate-topology.py`
  - `topology/L1-foundation.yaml`
  - `topology/L2-network.yaml`
  - `topology/L3-data.yaml`
