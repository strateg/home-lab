# TODO

Short task tracker. Architecture decisions live in ADR files.

Primary reference:
- `adr/0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md`

## Current State

- ADR-0026 phases 1-6: completed.
- Main topology: strict validation passes.
- CI matrix: `legacy-only`, `mixed`, `new-only` fixtures is in place.

## Active Tasks

- [ ] **L3 chain stance (High)**
  Decide and document one of:
  1. Keep shorthand-first (`storage_endpoints[].infer_from`) as default for home-lab scale.
  2. Implement full explicit chain authoring (`partitions` -> `volume_groups` -> `logical_volumes` -> `filesystems` -> `mount_points`) in main topology.

- [ ] **L5 modularization (Medium)**
  Split `topology/L5-application.yaml` into:
  - `topology/L5-application/_index.yaml`
  - `topology/L5-application/services/`
  - `topology/L5-application/certificates/`
  - `topology/L5-application/dns/`

- [ ] **L6 modularization (Medium)**
  Split `topology/L6-observability.yaml` into:
  - `topology/L6-observability/_index.yaml`
  - `topology/L6-observability/healthchecks/`
  - `topology/L6-observability/alerts/`
  - `topology/L6-observability/channels/`
  - `topology/L6-observability/dashboard/`

- [ ] **ADR consolidation policy (Low)**
  Define when to create a new ADR vs update an existing domain ADR.

## Done Recently

- [x] Strict-by-default validation in `topology-tools/validate-topology.py`.
- [x] Strict-by-default regeneration in `topology-tools/regenerate-all.py`.
- [x] Fixture matrix runner: `topology-tools/run-fixture-matrix.py`.
- [x] CI workflow: `.github/workflows/topology-matrix.yml`.
- [x] Runtime/data-asset/resource-profile cross-layer validation hardening.
