# ADR 0001: Keep Physical Power in L1 and Outage Policies in L7

- Status: Accepted
- Date: 2026-02-20

## Context

Power modeling was split between:

- physical power devices in `L1_foundation.devices`
- operational outage/policy behavior in `L1_foundation.power` (legacy)

This mixed physical inventory and operational orchestration in the same layer.
It reduced layer clarity and made ownership boundaries less explicit.

## Decision

Adopt strict separation:

- `L1_foundation` stores only physical power inventory and physical relationships.
- `L7_operations.power_resilience.policies` stores runtime/outage orchestration and policy logic.

Additionally:

- Remove legacy fallback paths in tooling for `L1_foundation.power_policies` and `L1_foundation.ups`.
- Validate power policies only from `L7_operations.power_resilience.policies`.
- Keep `upstream_power_ref` in L1 constrained to existing `class: power` devices.

## Consequences

Benefits:

- Clear layer responsibility: physical vs operational behavior.
- Better compatibility with dependency direction (`L7 -> L1`, never `L1 -> L7`).
- Lower ambiguity for future schema and generator changes.

Trade-offs:

- Existing legacy topology shape is no longer accepted by tooling.
- Any future outage policy must be added in L7, not L1.

## References

- Commit: `146b00d`
- Files:
  - `topology/L1-foundation.yaml`
  - `topology/L7-operations.yaml`
  - `topology/L7-operations/power/_index.yaml`
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology-tools/generate-docs.py`
