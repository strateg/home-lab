# ADR 0040: L0-L5 Canonical Ownership and Refactoring Plan

- Status: Accepted
- Date: 2026-02-23

## Context

Topology `v4.0.0` is structurally valid and passes strict validation, but architecture review showed
drift risks across `L0-L5`:

1. Layer ownership leaks:
   - non-physical service hints in `L1` device modules.
2. Duplicate source-of-truth fields:
   - service runtime data duplicated between legacy keys and `runtime`.
3. Partial runtime migration:
   - generators/templates still consume compatibility fields, which encourages backsliding.
4. Governance quality issues:
   - metadata freshness and migration intent are not formalized into a phased refactor contract.

Without an explicit contract, changes remain locally valid but globally inconsistent.

## Decision

Adopt the following canonical ownership contract and phased migration:

1. `L1` is strictly physical:
   - keep only physical inventory, links, slot/media attachment, and hardware capability.
   - remove service/runtime semantics from device modules.
2. `L5.services[].runtime` is canonical for placement:
   - canonical fields: `type`, `target_ref`, `network_binding_ref`, `image` (for docker runtime).
   - legacy placement/image fields are compatibility-only and must not be authored in topology data.
3. Generators may keep compatibility projection:
   - projection happens in tooling, not in source topology authoring.
4. Refactor by priority:
   - `P0`: remove active duplication/leaks that create immediate drift risk.
   - `P1`: reduce modeling ambiguity (typed network intent, security intent consistency).
   - `P2`: tighten governance and complete cleanup.

## Consequences

Benefits:

- Lower drift risk between declared intent and generated artifacts.
- Clear per-layer ownership aligned with `topology/MODULAR-GUIDE.md`.
- Safer future migrations due to explicit phased contract.

Trade-offs:

- Transitional updates in generators/templates are required while compatibility fields are phased out.
- Some existing docs views still depend on compatibility projections.

Migration impact:

- Backward compatibility is preserved by generator-side projection.
- Source topology authoring is tightened around canonical runtime and physical-only L1 model.

## References

- Contracts:
  - `topology/MODULAR-GUIDE.md`
- Topology modules:
  - `topology/L1-foundation/`
  - `topology/L5-application/services.yaml`
- Validators and generators:
  - `topology-tools/scripts/validators/checks/references.py`
  - `topology-tools/scripts/generators/docs/generator.py`
  - `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- Execution plan:
  - `docs/architecture/L0-L5-REFACTORING-PLAN.md`
