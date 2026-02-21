# TODO

Short task tracker. Architecture decisions live in ADR files.

Primary reference:
- `adr/0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md`

## Current State

- ADR-0026 phases 1-6: completed.
- Main topology: strict validation passes.
- CI matrix: `legacy-only`, `mixed`, `new-only` fixtures is in place.

## Active Tasks

- [ ] No open migration tasks. New work should start from fresh review findings.

## Done Recently

- [x] Strict-by-default validation in `topology-tools/validate-topology.py`.
- [x] Strict-by-default regeneration in `topology-tools/regenerate-all.py`.
- [x] Fixture matrix runner: `topology-tools/run-fixture-matrix.py`.
- [x] CI workflow: `.github/workflows/topology-matrix.yml`.
- [x] Runtime/data-asset/resource-profile cross-layer validation hardening.
- [x] L5/L6 layer modularization via `!include`.
- [x] Main topology switched to explicit L3 storage chain (`partitions -> volume_groups -> logical_volumes -> filesystems -> mount_points -> storage_endpoints`).
- [x] `rootfs.data_asset_ref` support added for LXC governance mapping.
- [x] ADR authoring policy updated to prefer domain ADR updates over micro-ADRs.
