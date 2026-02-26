# TODO

Short task tracker. Architecture decisions live in ADR files.

Primary reference:
- `adr/0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md`

## Current State

- ADR-0026 phases 1-6: completed.
- Main topology: strict validation passes.
- CI matrix: `legacy-only`, `mixed`, `new-only` fixtures is in place.

## Active Tasks

- [x] ✅ Test generators refactoring: integration smoke test **PASSED 26 февраля 2026**
- [ ] Run full unit test suite: `pytest tests/unit/generators/ -v`
- [ ] Add unit tests for new DataResolver doc-friendly methods
- [ ] Raise test coverage to 80%+ (terraform generators + error paths)

## Done Recently (26 февраля 2026)

- [x] **Generators refactoring Phase 2 complete**: extracted diagrams and data modules
- [x] `docs/generator.py` simplified: 517 → 404 LOC (21.8% reduction)
- [x] Created `docs/diagrams/` package with `DiagramDocumentationGenerator` (972 LOC)
- [x] Enhanced `docs/data/` with 3 doc-friendly methods (`resolve_lxc_resources_for_docs`, `resolve_services_inventory_for_docs`, `resolve_devices_inventory_for_docs`)
- [x] Moved `generate_network_diagram()` to diagrams module
- [x] Backward compatibility maintained via shim for old imports
- [x] Fixed CLI to work when run as direct script (absolute imports with path handling)
- [x] Removed unused `copy` import from generator.py
- [x] **Bug fix**: Data assets в storage-topology (добавлена трансформация wrapper-формата)

## Done Recently (26 февраля 2026)

- [x] **Generators refactoring Phase 2 complete**: extracted diagrams and data modules
- [x] `docs/generator.py` simplified: 517 → 404 LOC (21.8% reduction)
- [x] Created `docs/diagrams/` package with `DiagramDocumentationGenerator` (972 LOC)
- [x] Enhanced `docs/data/` with 3 doc-friendly methods (`resolve_lxc_resources_for_docs`, `resolve_services_inventory_for_docs`, `resolve_devices_inventory_for_docs`)
- [x] Moved `generate_network_diagram()` to diagrams module
- [x] Backward compatibility maintained via shim for old imports
- [x] Fixed CLI to work when run as direct script (absolute imports with path handling)
- [x] Removed unused `copy` import from generator.py

## Done Previously

- [x] Strict-by-default validation in `topology-tools/validate-topology.py`.
- [x] Strict-by-default regeneration in `topology-tools/regenerate-all.py`.
- [x] Fixture matrix runner: `topology-tools/run-fixture-matrix.py`.
- [x] Fixture matrix baseline guardrails (`legacy-only=62`, `mixed=6`, `new-only=0`) with optional drift override flag.
- [x] CI workflow: `.github/workflows/topology-matrix.yml`.
- [x] Runtime/data-asset/resource-profile cross-layer validation hardening.
- [x] L5/L6 layer modularization via `!include`.
- [x] Main topology switched to explicit L3 storage chain (`partitions -> volume_groups -> logical_volumes -> filesystems -> mount_points -> storage_endpoints`).
- [x] `rootfs.data_asset_ref` support added for LXC governance mapping.
- [x] ADR authoring policy updated to prefer domain ADR updates over micro-ADRs.
