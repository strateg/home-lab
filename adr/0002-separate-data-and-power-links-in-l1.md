# ADR 0002: Separate Data Links and Power Links in L1

- Status: Accepted
- Date: 2026-02-20
- Supersedes: -

## Context

Power sources were modeled in device attributes (`devices[*].power.upstream_power_ref`), but physical power cabling was implicit.
Data cabling already had explicit link modeling via `L1_foundation.physical_links`.
This asymmetry made physical topology incomplete and reduced traceability for outage impact analysis.

PoE is a special case where one physical cable carries both data and power.

## Decision

Introduce explicit physical power cabling in L1:

- Keep `L1_foundation.physical_links` as data links.
- Add `L1_foundation.power_links` for electrical connectivity.
- Keep operational/outage behavior in `L7_operations.power_resilience`.

For PoE:

- Model both a data link (`physical_links`) and a power link (`power_links`).
- The power link uses `mode: poe` and references the data link via `data_link_ref`.

## Consequences

Benefits:

- Complete physical topology representation in L1 for both data and power.
- Clear separation between physical layer (L1) and operational policy layer (L7).
- Better support for real-world mixed links (PoE as data+power).

Trade-offs:

- Slightly larger topology model and validation surface.
- Requires keeping link pairs consistent for PoE scenarios.

## References

- Files:
  - `topology/L1-foundation.yaml`
  - `topology/L1-foundation/power-links/_index.yaml`
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology-tools/schemas/validator-policy.yaml`
