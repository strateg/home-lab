# Modular Topology Guide (v4)

This guide defines how to keep topology files small, readable, and safe to evolve.

## Goals

- Keep `topology.yaml` as the single composition root.
- Split large layers into stable modules.
- Enforce strict downward dependencies (`L(N)` may reference only `L<=N`).
- Make adding new hardware a small, local change.
- Keep **underlay vs overlay** explicit:
  - L1 = physical links (`physical_links`)
  - L2 = virtual segmentation (`network_plane`, `segmentation_type`, `transport`, `volatility`)

## Dependency Rules

| Layer | Can reference |
|-------|---------------|
| L0 Meta | L0 only |
| L1 Foundation | L0 |
| L2 Network | L0, L1 |
| L3 Data | L0, L1, L2 |
| L4 Platform | L0..L3 |
| L5 Application | L0..L4 |
| L6 Observability | L0..L5 |
| L7 Operations | L0..L6 |

Rules:
- Use `*_ref` fields only (no implicit links in free text).
- Do not introduce upward references.
- Keep IDs stable after first release.

## Current Modular Layout

- `topology/L1-foundation.yaml`:
  - `topology/L1-foundation/locations/`
  - `topology/L1-foundation/devices/`
  - `topology/L1-foundation/links/`
  - `topology/L1-foundation/power/`
- `topology/L2-network.yaml`:
  - `topology/L2-network/trust-zones/`
  - `topology/L2-network/profiles/`
  - `topology/L2-network/networks/`
  - `topology/L2-network/bridges/`
  - `topology/L2-network/routing/`
  - `topology/L2-network/firewall/`
  - `topology/L2-network/firewall/policies/`
  - `topology/L2-network/qos/`
  - `topology/L2-network/ipv6/`

## Editing Conventions (AI + Human)

- One module file should represent one logical unit.
- Use predictable names: file name equals object `id` where possible.
- Keep indexes explicit: `_index.yaml` contains only ordered `!include` entries.
- Keep module size practical (target under ~200 lines).
- Preserve key order: `id`, `name`, `type`, refs, config, `description`.
- For L2 networks with `profile_ref`, keep only exception overrides in network files.

## Add New Hardware Workflow

1. Add new device file under `topology/L1-foundation/devices/<group>/<device-id>.yaml`.
2. Add include entry to `topology/L1-foundation/devices/_index.yaml`.
3. Add/update physical connectivity in `topology/L1-foundation/links/` and `links/_index.yaml`.
4. If needed, add/update virtual network in `topology/L2-network/networks/` and `_index.yaml`.
5. Prefer `profile_ref` from `topology/L2-network/profiles/default.yaml`.
6. Read profile rules in `topology/L2-network/profiles/README.md`.
7. Override explicit fields (`network_plane`, `segmentation_type`, `transport`, `volatility`) only when diverging from profile.
8. For firewall policy changes, edit `topology/L2-network/firewall/policies/*` and include from `topology/L2-network/firewall/policies/_index.yaml`.
9. Add platform/app/monitoring modules only if the device hosts workloads.
10. Validate and regenerate:
   - `python scripts/validate-topology.py`
   - `python scripts/generate-docs.py`

## Anti-Patterns

- Large monolithic layer files with mixed concerns.
- Hardcoded cross-layer values instead of `*_ref`.
- Reordering IDs frequently (breaks stable diffs and AI reasoning).
