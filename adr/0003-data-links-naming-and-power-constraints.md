# ADR 0003: Rename L1 Physical Links to Data Links and Constrain Data-Link Power

- Status: Accepted
- Date: 2026-02-20
- Supersedes: -

## Context

After introducing explicit `power_links`, the L1 key `physical_links` remained ambiguous.
The project needs explicit naming for data connectivity and clear rules for when power can be carried over a data connection.
There is also a valid cableless power case (inductive wireless charging) that should be represented without a data cable.

## Decision

1. Rename L1 connectivity key and module path:
   - `L1_foundation.physical_links` -> `L1_foundation.data_links`
   - `topology/L1-foundation/links/` -> `topology/L1-foundation/data-links/`
2. Keep data-link media broad (`ethernet`, `wifi`, `fiber/optical`, etc.).
3. Constrain in-band data-link power:
   - Data-link `power_delivery` is valid only on `medium: ethernet`.
   - Data-link `power_delivery.mode` is `poe` only.
4. Model cableless charging in `power_links`:
   - Add `power_links.mode: wireless-inductive`.
   - `wireless-inductive` must not reference a data link.

## Consequences

Benefits:

- Better semantic clarity in L1: data paths vs power paths.
- PoE behavior is explicit and constrained.
- Supports real-world non-cabled charging as pure power topology.

Trade-offs:

- Breaking model rename for consumers expecting `physical_links`.
- Validators/generators must align to `data_links`.

## References

- Files:
  - `topology/L1-foundation.yaml`
  - `topology/L1-foundation/data-links/`
  - `topology/L1-foundation/power-links/README.md`
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology-tools/schemas/validator-policy.yaml`
