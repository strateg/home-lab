# ADR0078 Implementation Plan

**Date:** 2026-03-21
**ADR:** `adr/0078-object-module-local-template-layout.md`
**Status:** Completed (all waves including Wave 9-10)
**Amended:** 2026-03-22 (compilers/validators/generators unified rules)
**Amended:** 2026-03-22 (instance isolation, cross-object boundaries, dynamic discovery)

---

## 1. Objective

Reach ADR0078 target state for `v5`:

1. Object-specific generator code is located only in `object-modules/<object-id>/plugins`.
2. Object-specific templates are located only in `object-modules/<object-id>/templates/<generator-id>`.
3. Object-specific generator registration is owned by module manifests (`object-modules/**/plugins.yaml`).
4. Transitional shims in `v5/topology-tools/plugins/generators` are removed after compatibility gate.

Amended objective (2026-03-22):

1. Apply one architecture contract to all plugin families:
   - compilers;
   - validators;
   - generators.
2. Prepare v5 refactoring backlog and gates so unified rules are enforced in active migration work.

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

## 3. Baseline (2026-03-21)

Already implemented:

1. Object-specific generator implementations exist in:
   - `v5/topology/object-modules/mikrotik/plugins/`
   - `v5/topology/object-modules/proxmox/plugins/`
   - `v5/topology/object-modules/orangepi/plugins/`
2. Central manifest points to moved generator files:
   - `v5/topology-tools/plugins/plugins.yaml`
3. MikroTik terraform templates are already co-located:
   - `v5/topology/object-modules/mikrotik/templates/terraform/`

Open gaps:

1. `proxmox` and `orangepi` do not yet own generator registration in local `plugins.yaml`.
2. Object-specific templates still remain in `v5/topology-tools/templates` for proxmox/bootstrap flows.
3. Compatibility shims still exist for moved generators in `v5/topology-tools/plugins/generators/`.
4. Authoring/operational docs still describe central-registration-first flow.

Implementation status update (2026-03-21):

1. Wave 1 completed: object-specific templates moved to object modules.
2. Wave 2 completed: object-specific generator registration moved to module manifests.
3. Wave 3 completed: compatibility shims removed from tools generator package.
4. Wave 4 completed: docs updated and release preflight includes explicit ADR0078 ownership check.
5. Wave 5 completed: object-specific projection builders moved out of shared tools module.

Closure note:

1. ADR0078 scope in this plan is fully closed (Waves 1-5).

---

## 4. Execution Plan

### Wave 1: Complete Template Co-location

Changes:

1. Move `v5/topology-tools/templates/terraform/proxmox/*` to:
   - `v5/topology/object-modules/proxmox/templates/terraform/*`
2. Move `v5/topology-tools/templates/bootstrap/proxmox/*` to:
   - `v5/topology/object-modules/proxmox/templates/bootstrap/*`
3. Move `v5/topology-tools/templates/bootstrap/mikrotik/*` to:
   - `v5/topology/object-modules/mikrotik/templates/bootstrap/*`
4. Move `v5/topology-tools/templates/bootstrap/orangepi/*` to:
   - `v5/topology/object-modules/orangepi/templates/bootstrap/*`
5. Add/adjust generator `template_root()` resolution for proxmox/orangepi/bootstrap generators to prefer object-local templates.
6. Update `v5/topology-tools/templates/TEMPLATE-INVENTORY.md`.

Exit criteria:

1. No object-specific templates are required from `v5/topology-tools/templates`.
2. Generator integration checks pass.

### Wave 2: Move Registration Ownership to Module Manifests

Changes:

1. Extend `v5/topology/object-modules/mikrotik/plugins.yaml` with generator entries.
2. Add `v5/topology/object-modules/proxmox/plugins.yaml` with proxmox generator entries.
3. Add `v5/topology/object-modules/orangepi/plugins.yaml` with orangepi generator entry.
4. Remove object-specific generator entries from:
   - `v5/topology-tools/plugins/plugins.yaml`
5. Keep plugin IDs stable (no renames), preserve ordering/dependency semantics.

Exit criteria:

1. `discover_plugin_manifests()` remains deterministic.
2. No duplicate plugin IDs (`E4001`).
3. Compile/generate uses module-owned generator registration only.

### Wave 3: Remove Compatibility Shims

Changes:

1. Remove shim files:
   - `v5/topology-tools/plugins/generators/terraform_mikrotik_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_mikrotik_generator.py`
   - `v5/topology-tools/plugins/generators/terraform_proxmox_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_proxmox_generator.py`
   - `v5/topology-tools/plugins/generators/bootstrap_orangepi_generator.py`
2. Update tests/imports that still reference shim modules.
3. Add guard check (test or CI grep) preventing reintroduction of object-specific shims.

Exit criteria:

1. No runtime/import dependency on shim modules.
2. Projection/template/publish contract tests pass without shims.

### Wave 4: Docs and Release Alignment

Changes:

1. Update:
   - `v5/topology-tools/docs/PLUGIN_AUTHORING.md`
   - `v5/topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`
2. Update release checklists/guides with ADR0078 gates:
   - no object-specific entries in central generator manifest,
   - no object-specific templates under `topology-tools/templates`.
3. Regenerate lock:
   - `v5/projects/home-lab/framework.lock.yaml`

Exit criteria:

1. Docs reflect module-owned registration model.
2. Release preflight includes explicit ADR0078 verification.

### Wave 5: Projection Ownership Split

Goal:

1. Move object-specific projection builders out of:
   - `v5/topology-tools/plugins/generators/projections.py`

Changes:

1. Move object-specific projection builders to object-owned modules:
   - `v5/topology/object-modules/proxmox/plugins/projections.py`
   - `v5/topology/object-modules/mikrotik/plugins/projections.py`
   - `v5/topology/object-modules/_shared/plugins/bootstrap_projections.py`
2. Keep only shared/global projection builder(s) in:
   - `v5/topology-tools/plugins/generators/projections.py`
3. Add ownership guard checks so object-specific projection builders are not reintroduced in shared tools module.

Exit criteria:

1. Object generators resolve projection helpers from object-owned modules.
2. Shared `projections.py` contains only shared/global projection helpers.

---

## 5. Verification Matrix

Required after each wave batch:

1. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_mikrotik_generator.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_proxmox_generator.py -q`
3. `python -m pytest -o addopts= v5/tests/plugin_integration/test_bootstrap_generators.py -q`
4. `python -m pytest -o addopts= v5/tests/plugin_integration/test_generator_projection_contract.py -q`
5. `python -m pytest -o addopts= v5/tests/plugin_integration/test_generator_template_and_publish_contract.py -q`
6. `python -m pytest -o addopts= v5/tests/plugin_integration/test_module_manifest_discovery.py -q`
7. `python -m pytest -o addopts= v5/tests/plugin_integration/test_strict_runtime_entrypoint_audit.py -q`
8. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

Release smoke gate (mandatory):

1. Build framework distribution zip.
2. Initialize a fresh project from distribution zip.
3. Run strict compile in that initialized project.

---

## 6. Risks and Controls

1. Risk: template not found after relocation.
   - Control: wave-local test matrix + inventory update in same commit.
2. Risk: manifest split introduces duplicate IDs/load regressions.
   - Control: manifest-discovery and duplicate-ID diagnostics checks.
3. Risk: hidden dependencies on shim modules.
   - Control: explicit shim-removal wave + anti-regression guard.
4. Risk: distribution/lock drift.
   - Control: lock regeneration + distribution smoke gate.

---

## 7. Rollback

If acceptance fails in any wave:

1. Restore prior manifest ownership in `v5/topology-tools/plugins/plugins.yaml`.
2. Restore shims for failed scope.
3. Restore prior template roots for affected generators.
4. Re-run full verification matrix before retry.

---

## 8. Definition of Done (ADR0078)

All must be true:

1. Object-specific generator code exists only in `object-modules/<object-id>/plugins`.
2. Object-specific templates exist only in `object-modules/<object-id>/templates`.
3. Object-specific registration is owned by module manifests.
4. Central `v5/topology-tools/plugins/plugins.yaml` contains only shared/global plugins.
5. Object-specific compatibility shims are removed.
6. Verification matrix and release smoke gate pass.

---

## 9. Compatibility Gate Evidence (2026-03-21)

Recorded one full local release cycle after shim removal:

1. Full v5 tests:
   - `python -m pytest -o addopts= v5/tests -q`
   - Result: `317 passed, 3 skipped`
2. Framework release preflight chain:
   - strict framework gates (`verify-framework-lock`, rollback rehearsal, compatibility matrix, strict runtime audit)
   - ADR0078 ownership contract (`v5/tests/plugin_contract/test_object_generator_ownership.py`)
   - v5 lane validate (`V5_SECRETS_MODE=passthrough python v5/scripts/orchestration/lane.py validate-v5`)
   - Result: PASS
3. Framework distribution build:
   - `python v5/topology-tools/utils/build-framework-distribution.py --repo-root . --framework-manifest v5/topology/framework.yaml --output-root v5-dist/framework --version 1.0.8 --archive-format both`
   - Result: PASS (`infra-topology-framework-1.0.8.zip` / `.tar.gz`)
4. Zip bootstrap smoke:
   - `python v5/topology-tools/utils/init-project-repo.py --output-root v5-build/adr0078-cycle-project --project-id adr0078-cycle --framework-dist-zip ...infra-topology-framework-1.0.8.zip --framework-dist-version 1.0.8 --framework-submodule-path framework --force`
   - Result: `Compile check: PASS`

Conclusion:

1. Compatibility gate objective ("one full release cycle without shim-origin failures") remains satisfied; Wave 5 applies ownership hardening on top.

---

## 10. Unified v5 Refactor Preparation (2026-03-22)

Preparation goal:

1. Start next v5 refactor cycle with explicit scope for compilers/validators/generators under common ADR0078 rules.

Prepared work packages:

1. **WP1: Unified inventory**
   - Build catalog of all active plugins by family and level (core/class/object/instance).
   - Mark ownership root and manifest owner for each plugin.
2. **WP2: Violation map**
   - Detect direct cross-level coupling and high-level leakage of object/instance specifics.
   - Mark global plugins that contain specific class/object semantics and require promotion/split.
3. **WP3: Interface extraction plan**
   - Define interface contracts where global plugins orchestrate specific plugins.
   - Replace direct concrete dependencies with contract-driven integration.
4. **WP4: Execution gates**
   - Keep `v5/tests/plugin_contract/test_plugin_level_boundaries.py` mandatory.
   - Keep `task test:parity-v4-v5` mandatory for affected domains.
   - Keep full `v5/tests/plugin_integration` and strict compile in each refactor batch.
5. **WP5: Anti-regression controls**
   - Add ownership and boundary checks to prevent reintroduction of violations during migration.

Ready-to-start sequence:

1. Finalize inventory + violation map.
2. Approve batch order (core -> class -> object -> instance).
3. Execute refactor in small batches with lock refresh and cutover-readiness evidence per batch.

---

## 11. Phase 6-10 Execution Update (2026-03-22)

Status summary:

1. **Wave 6 (instance literal cleanup): completed**
   - hardcoded endpoint literals removed from object terraform generators;
   - endpoint resolution is projection/config-first.
2. **Wave 7 (cross-object import prohibition): completed**
   - added AST-based cross-object import guard in `test_plugin_level_boundaries.py`.
3. **Wave 8 (dynamic object discovery): completed**
   - replaced static projection path mapping with dynamic discovery + cache;
   - added discovery coverage in `test_object_projection_loader.py`.
4. **Wave 9 (capability-template externalization): completed**
   - added `capability_templates` config section to `mikrotik/plugins.yaml`;
   - refactored `terraform_mikrotik_generator.py` with `_get_capability_templates()` method;
   - removed hardcoded fallback mapping from generator code (manifest config is source of truth);
   - created `test_capability_template_config.py` with 3 contract tests.
5. **Wave 10 (projection ownership consolidation): completed**
   - created `test_projection_ownership_boundaries.py` with 6 contract tests;
   - verified projection ownership hierarchy (core/object/shared);
   - all modules pass ownership boundary tests.

**All waves completed. ADR0078 implementation is fully closed.**

---

## 12. Verification Matrix (Final)

All mandatory gates (all passing):

1. `python -m pytest -o addopts= v5/tests/plugin_contract/test_plugin_level_boundaries.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_object_projection_loader.py -q`
3. `python -m pytest -o addopts= v5/tests/plugin_integration/test_terraform_mikrotik_generator.py v5/tests/plugin_integration/test_terraform_proxmox_generator.py -q`
4. `python -m pytest -o addopts= v5/tests/plugin_integration -q`
5. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`
6. `python v5/topology-tools/verify-framework-lock.py --strict`
7. `python -m pytest -o addopts= v5/tests/plugin_contract/test_capability_template_config.py -q`
8. `python -m pytest -o addopts= v5/tests/plugin_contract/test_projection_ownership_boundaries.py -q`

**All gates green (2026-03-22):** 43 plugin_contract tests + 450 plugin_integration tests passing.

---

## 13. Risks and Controls (Post-Completion)

1. Risk: capability externalization changes generator output unexpectedly.
   - Control: artifact snapshot/integration tests before and after refactor.
2. Risk: projection ownership split introduces duplicate helpers or regressions.
   - Control: explicit ownership test and `_shared` helper inventory.
3. Risk: schema/config drift across module manifests.
   - Control: strict manifest validation + plugin contract suite in CI.

---

## 14. Definition of Done (Wave 9-10)

All must be true:

1. Capability-template mappings are fully externalized to module config. ✓
2. Generators consume capability-template mappings via config only. ✓
3. Projection ownership boundaries (core/object/_shared) are documented and test-enforced. ✓
4. Plugin contract suite, full integration suite, strict compile, and lock verification are green. ✓

**All criteria satisfied (2026-03-22).**
