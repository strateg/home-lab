# ADR0078 Implementation Plan

**Date:** 2026-03-21  
**ADR:** `adr/0078-object-module-local-template-layout.md`  
**Status:** Proposed (execution-ready)

---

## 1. Objective

Complete ADR0078 end-state for `v5`:

1. Object-specific generator code lives in `object-modules/<object-id>/plugins`.
2. Object-specific templates live in `object-modules/<object-id>/templates/<generator-id>`.
3. Object-specific plugin registration is owned by module manifests (`object-modules/**/plugins.yaml`).
4. Transitional shims in `topology-tools/plugins/generators` are removed after validation window.

---

## 2. Scope

In scope (object-specific generators):

1. `base.generator.terraform_mikrotik`
2. `base.generator.bootstrap_mikrotik`
3. `base.generator.terraform_proxmox`
4. `base.generator.bootstrap_proxmox`
5. `base.generator.bootstrap_orangepi`

Out of scope (shared/global generators):

1. `base.generator.effective_json`
2. `base.generator.effective_yaml`
3. `base.generator.ansible_inventory`

---

## 3. Current State Snapshot

Implemented:

1. Generator implementations are already moved to:
   - `v5/topology/object-modules/mikrotik/plugins/`
   - `v5/topology/object-modules/proxmox/plugins/`
   - `v5/topology/object-modules/orangepi/plugins/`
2. Central manifest already points to moved generator files:
   - `v5/topology-tools/plugins/plugins.yaml`
3. MikroTik terraform templates are already local:
   - `v5/topology/object-modules/mikrotik/templates/terraform/`

Remaining gaps:

1. `proxmox` and `orangepi` do not own generator registration in their own `plugins.yaml`.
2. Object-specific templates still remain in `v5/topology-tools/templates` for proxmox/bootstrap flows.
3. Compatibility shim modules still exist in:
   - `v5/topology-tools/plugins/generators/*` (for moved object-specific generators)
4. Authoring/operational docs still describe central-registration-first flow.

---

## 4. Execution Waves

## Wave 1: Finish Template Co-location

Changes:

1. Move templates from `v5/topology-tools/templates/terraform/proxmox/*` to:
   - `v5/topology/object-modules/proxmox/templates/terraform/*`
2. Move templates from `v5/topology-tools/templates/bootstrap/proxmox/*` to:
   - `v5/topology/object-modules/proxmox/templates/bootstrap/*`
3. Move templates from `v5/topology-tools/templates/bootstrap/mikrotik/*` to:
   - `v5/topology/object-modules/mikrotik/templates/bootstrap/*`
4. Move templates from `v5/topology-tools/templates/bootstrap/orangepi/*` to:
   - `v5/topology/object-modules/orangepi/templates/bootstrap/*`
5. Add/adjust `template_root()` for proxmox/orangepi/mikrotik bootstrap generators to prefer object-local paths (same resolution policy as ADR0078).
6. Update `v5/topology-tools/templates/TEMPLATE-INVENTORY.md`.

Exit criteria:

1. Object-specific generators render successfully without object templates under `topology-tools/templates`.
2. Generator integration tests pass.

---

## Wave 2: Module-Owned Plugin Registration

Changes:

1. Extend `v5/topology/object-modules/mikrotik/plugins.yaml` with generator entries.
2. Add `v5/topology/object-modules/proxmox/plugins.yaml` with proxmox generator entries.
3. Add `v5/topology/object-modules/orangepi/plugins.yaml` with orangepi generator entry.
4. Remove object-specific generator entries from:
   - `v5/topology-tools/plugins/plugins.yaml`
5. Keep plugin IDs stable (no renames), preserve order/dependency semantics.

Exit criteria:

1. `discover_plugin_manifests()` order remains deterministic.
2. Compile + generate loads all object-specific generators only from module manifests.
3. No duplicate plugin ID diagnostics (`E4001`).

---

## Wave 3: Shim Removal and Import Hardening

Changes:

1. Remove compatibility shim files:
   - `v5/topology-tools/plugins/generators/terraform_mikrotik_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_mikrotik_generator.py`
   - `v5/topology-tools/plugins/generators/terraform_proxmox_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_proxmox_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_orangepi_generator.py`
2. Update tests/imports to use object-module generator modules directly where needed.
3. Add guard checks (test or grep-based CI check) to prevent re-introduction of object-specific generator shims.

Exit criteria:

1. No runtime dependency on shim modules.
2. Generator tests and projection-contract tests pass without shims.

---

## Wave 4: Docs and Release Workflow Alignment

Changes:

1. Update plugin authoring docs:
   - `v5/topology-tools/docs/PLUGIN_AUTHORING.md`
2. Update manual build docs:
   - `v5/topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`
3. Update release guide/checklists to include ADR0078 checks:
   - no object-specific generator entries in central manifest,
   - no object-specific templates under `topology-tools/templates`.
4. Regenerate framework lock:
   - `v5/projects/home-lab/framework.lock.yaml`

Exit criteria:

1. Documentation reflects module-owned registration model.
2. Release preflight includes ADR0078 verification steps.

---

## Wave 5 (Optional): Projection Ownership Split

Goal:

1. Reduce object-specific logic in shared projection module:
   - `v5/topology-tools/plugins/generators/projections.py`

Changes:

1. Move object-specific projection builders to object modules.
2. Keep shared projection helpers in tools domain.

Exit criteria:

1. Shared tools module contains only cross-object projection primitives.

---

## 5. Verification Matrix (Minimum)

Run for each completed wave batch:

1. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_mikrotik_generator.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_proxmox_generator.py -q`
3. `python -m pytest -o addopts= v5/tests/plugin_integration/test_bootstrap_generators.py -q`
4. `python -m pytest -o addopts= v5/tests/plugin_integration/test_generator_projection_contract.py -q`
5. `python -m pytest -o addopts= v5/tests/plugin_integration/test_generator_template_and_publish_contract.py -q`
6. `python -m pytest -o addopts= v5/tests/plugin_integration/test_module_manifest_discovery.py -q`
7. `python -m pytest -o addopts= v5/tests/plugin_integration/test_strict_runtime_entrypoint_audit.py -q`
8. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

Distribution smoke check (required before release):

1. Build framework distribution zip.
2. Init project from distribution zip.
3. Run strict compile in initialized project context.

---

## 6. Risks and Controls

1. Risk: missing templates after move.
   - Control: wave-by-wave tests + explicit template inventory update.
2. Risk: plugin load regressions from manifest split.
   - Control: deterministic manifest discovery tests + duplicate ID checks.
3. Risk: hidden dependencies on shims.
   - Control: shim-removal wave with import guard and CI check.
4. Risk: release artifact drift.
   - Control: framework lock regeneration + distribution smoke test from zip bootstrap.

---

## 7. Rollback

If a wave fails acceptance:

1. Restore previous plugin entrypoints in `v5/topology-tools/plugins/plugins.yaml`.
2. Keep/restore compatibility shims for failed scope.
3. Restore previous template roots for affected generators.
4. Re-run strict validation matrix before next attempt.

---

## 8. Definition of Done (ADR0078)

All conditions must be true:

1. Object-specific generator code is only in `object-modules/<object-id>/plugins`.
2. Object-specific templates are only in `object-modules/<object-id>/templates`.
3. Object-specific plugin registration is in module manifests.
4. Central `v5/topology-tools/plugins/plugins.yaml` contains only shared/global plugins.
5. Compatibility shims are removed.
6. Verification matrix and distribution smoke checks pass.
