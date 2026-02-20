# Modular Topology Guide (v4)

This guide defines how to keep topology files small, readable, and safe to evolve.

## Goals

- Keep `topology.yaml` as the single composition root.
- Split large layers into stable modules.
- Enforce strict downward dependencies (`L(N)` may reference only `L<=N`).
- Make adding new hardware a small, local change.
- Keep **underlay vs overlay** explicit:
  - L1 = data links (`data_links`) and power links (`power_links`)
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
- Every architecture decision must be recorded as a new ADR file in `adr/`.

## Current Modular Layout

- Modularized layers:
  - `topology/L1-foundation.yaml`:
  - `topology/L1-foundation/locations/`
  - `topology/L1-foundation/devices/owned/<class>/`
  - `topology/L1-foundation/devices/provider/<class>/`
  - `topology/L1-foundation/data-links/` (data links)
  - `topology/L1-foundation/power-links/` (power links)
  - `topology/L7-operations.yaml`:
  - `topology/L7-operations/power/`
  - `topology/L2-network.yaml`:
  - `topology/L2-network/trust-zones/`
  - `topology/L2-network/profiles/`
  - `topology/L2-network/networks/`
  - `topology/L2-network/bridges/`
  - `topology/L2-network/routing/`
  - `topology/L2-network/firewall/policies/`
  - `topology/L2-network/firewall/templates.yaml`
  - `topology/L2-network/qos/`
  - `topology/L2-network/ipv6/`
- Single-file layers (not yet modularized into subfolders):
  - `topology/L0-meta.yaml`
  - `topology/L3-data.yaml`
  - `topology/L4-platform.yaml`
  - `topology/L5-application.yaml`
  - `topology/L6-observability.yaml`

## Editing Conventions (AI + Human)

- One module file should represent one logical unit.
- Use predictable names: file name equals object `id` where possible.
- Keep indexes explicit: `_index.yaml` contains only ordered `!include` entries.
- Keep module size practical (target under ~200 lines).
- Preserve key order: `id`, `name`, `type`, `role`, `class`, `substrate`, `access`, refs, config, `description`.
- Model is defined by fields inside files; folders are validated against model.
- Validator reports placement lints (warnings) and suggests expected paths when files are moved/copied incorrectly.
- In L1 devices, always set taxonomy explicitly: `class` + `substrate` + `access`.
- `data_links` can reference only owned/colo substrate devices (no `provider-instance`).
- `power_links` can reference only owned/colo substrate devices (no `provider-instance`).
- For PoE, model both links: one data link + one power link with `data_link_ref`.
- VM/LXC remain in `L4_platform` (compute module), not in `L1_foundation`.
- In L2 networks, `managed_by_ref` should point to `class: network` device.
- For L2 networks with `profile_ref`, keep only exception overrides in network files.

## Add New Hardware Workflow

1. Add new device file under `topology/L1-foundation/devices/<substrate-group>/<class>/<device-id>.yaml`.
2. Add include entry to `topology/L1-foundation/devices/_index.yaml`.
3. Set `class`/`substrate`/`access`.
4. Add/update data connectivity in `topology/L1-foundation/data-links/` and `data-links/_index.yaml` only for non-provider substrates.
5. Add/update power cabling in `topology/L1-foundation/power-links/` and `power-links/_index.yaml`.
6. If needed, add/update virtual network in `topology/L2-network/networks/` and `_index.yaml`.
7. Prefer `profile_ref` from `topology/L2-network/profiles/default.yaml`.
8. Read profile rules in `topology/L2-network/profiles/README.md`.
9. Override explicit fields (`network_plane`, `segmentation_type`, `transport`, `volatility`) only when diverging from profile.
10. For firewall policy changes, edit `topology/L2-network/firewall/policies/*` and include from `topology/L2-network/firewall/policies/_index.yaml`.
11. Add VM/LXC workloads in `topology/L4-platform.yaml` only.
12. Add platform/app/monitoring modules only if the device hosts workloads.
13. Validate and regenerate:
   - `python topology-tools/validate-topology.py`
   - `python topology-tools/generate-docs.py`
14. If architecture changed, add a new ADR in `adr/NNNN-*.md`.

## Anti-Patterns

- Large monolithic layer files with mixed concerns.
- Hardcoded cross-layer values instead of `*_ref`.
- Reordering IDs frequently (breaks stable diffs and AI reasoning).
