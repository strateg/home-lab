# ADR 0078: Object-Module Local Templates and Generator Plugins Layout

**Date:** 2026-03-21
**Status:** Accepted
**Depends on:** ADR 0062, ADR 0074, ADR 0076, ADR 0077

---

## Context

In v5, object behavior is defined in `topology/object-modules/*`, but object-scoped generation implementation was split across `topology-tools`:

1. templates in `topology-tools/templates/*`;
2. generator plugin code in `topology-tools/plugins/generators/*`.

This caused practical issues:

1. object implementation, templates, and generator code were split across different roots;
2. framework distribution/build flow had to preserve extra object-specific paths from tools domain;
3. module portability to external projects was weaker because object assets were not self-contained.

For object-scoped generators (for example MikroTik/Proxmox/OrangePi), templates and plugin implementation are part of object module implementation, not global tooling infrastructure.

An object-scoped generator in this ADR means a generator whose templates and plugin logic are owned by one object module and are not intended as cross-object shared infrastructure.

---

## Decision Drivers

1. Keep object implementation assets colocated under one ownership root.
2. Improve framework/project portability by reducing hidden tool-domain coupling.
3. Make packaging and extraction deterministic for generated project consumption.
4. Preserve compatibility for shared/global generators and templates.

---

## Decision

Move object-specific templates and generator plugin code into corresponding object modules.

Classification rule (normative):

1. A generator is **object-scoped** when both are true:
   - it targets one object namespace (`obj.<vendor_or_object>.*`);
   - its templates are not reused as cross-object shared infrastructure.
2. A generator is **shared/global** when it emits cross-object artifacts (for example effective model exports or inventory aggregation) and does not belong to one object module ownership root.

### Normative layout

1. Object templates MUST be stored under:
   - `v5/topology/object-modules/<object-id>/templates/<generator-id>/`
2. Object-scoped generator plugins MUST be stored under:
   - `v5/topology/object-modules/<object-id>/plugins/`
3. Plugin manifest entrypoints for object-scoped generators MUST point to object-module plugin paths.
4. Shared, cross-object templates MAY remain under:
   - `v5/topology-tools/templates/`
5. Shared, cross-object generator plugins MAY remain under:
   - `v5/topology-tools/plugins/generators/`

### Object migrations in scope

1. MikroTik Terraform templates:
   - old: `v5/topology-tools/templates/terraform/mikrotik/*`
   - new: `v5/topology/object-modules/mikrotik/templates/terraform/*`
2. Generator plugins:
   - `terraform_mikrotik_generator.py` -> `object-modules/mikrotik/plugins/`
   - `bootstrap_mikrotik_generator.py` -> `object-modules/mikrotik/plugins/`
   - `terraform_proxmox_generator.py` -> `object-modules/proxmox/plugins/`
   - `bootstrap_proxmox_generator.py` -> `object-modules/proxmox/plugins/`
   - `bootstrap_orangepi_generator.py` -> `object-modules/orangepi/plugins/`

### Generator template resolution policy

Generators MUST resolve templates in this order:

1. explicit override via `generator_templates_root` (if provided);
2. object-local templates (`object-modules/<object-id>/templates`);
3. legacy/shared tool templates (`topology-tools/templates`) as fallback for shared assets.

### Distribution contract

Framework distribution packaging MUST include object-local templates and object-local generator plugins together with object modules, so generated projects can run without hidden dependencies on tool-internal paths.

### Plugin manifest policy

1. During transition, central `v5/topology-tools/plugins/plugins.yaml` MAY reference object-module plugin paths.
2. Target end-state: object-module `plugins.yaml` manifests own object-scoped plugin registration.
3. Duplicate plugin IDs across central and module manifests are forbidden and treated as hard manifest load errors.

---

## Alternatives Considered

1. Keep all object templates/plugins in `topology-tools/*`.
   - Rejected: keeps ownership split and increases packaging coupling to tool internals.
2. Keep physical files in `topology-tools/*` and map ownership only via plugin registry metadata.
   - Rejected: improves discoverability but does not solve self-contained module portability.
3. Chosen approach: move object assets physically into object modules and keep shared/global assets in tools domain.
   - Accepted: best alignment with ownership boundaries and distribution portability.

---

## Non-Goals

1. Changing generator business logic or output format.
2. Moving cross-object/shared templates that are intentionally framework-global.
3. Moving cross-object/shared generator plugins that are intentionally framework-global.
4. Revising plugin API contracts from ADR 0065/0074.

---

## Consequences

### Positive

1. Object modules become more self-contained and portable.
2. Framework distribution structure aligns with implementation ownership.
3. Lower risk of path drift between local repo and extracted/project consumption.
4. Plugin entrypoints are aligned with module ownership boundaries.

### Trade-offs

1. Need to maintain template resolution compatibility during migration.
2. Some generators require explicit import path handling for shared runtime helpers.
3. Transitional compatibility shims may be needed for legacy imports/tests.

---

## Risks and Mitigations

1. Risk: import/entrypoint regressions after plugin relocation.
   - Mitigation: plugin manifest validation and strict compile/integration checks in CI.
2. Risk: template duplication or stale copies across old/new roots.
   - Mitigation: inventory diff checks and migration checklist gate before release.
3. Risk: framework lock/distribution drift from runtime resolution behavior.
   - Mitigation: rebuild lock, validate packaged artifact structure, and run smoke generation from distribution layout.
4. Risk: migration stalls with permanent compatibility shims.
   - Mitigation: define shim sunset policy with objective removal gate and owner.

---

## Compatibility Strategy (Shim Sunset)

Compatibility shims in `v5/topology-tools/plugins/generators/*` are transitional only.

Removal gate (all required):

1. One full release cycle passes with no shim-origin failures in CI.
2. Repository grep shows no runtime imports that require shim modules.
3. Plugin loading/integration tests pass against object-module plugin paths.
4. Distribution smoke test from zip-based project bootstrap passes.

Ownership:

1. Runtime maintainers own shim removal readiness evidence.
2. Release owner signs off shim removal in release notes/checklist.

---

## Rollout and Rollback

### Rollout

1. Migrate object modules in bounded batches (for example: MikroTik -> Proxmox -> OrangePi).
2. After each batch, update plugin manifest entrypoints and regenerate framework lock.
3. Keep compatibility shims only for validated transition window.

### Rollback

1. Trigger rollback if strict compile or plugin integration tests fail for migrated objects.
2. Rollback action: restore previous plugin manifest entrypoints and retain legacy template root resolution.
3. Re-run validation gates before re-attempting migration.

---

## Implementation Plan (Phase-Gated)

### Phase 0: Inventory and Baseline

1. Build a complete inventory of object-scoped generators, templates, and plugin entrypoints in scope.
2. Capture baseline validation status (strict compile, plugin integration tests, and distribution smoke generation).
3. Produce a migration checklist artifact for tracked execution.

**Go/No-Go:** proceed only when inventory is complete and baseline validations are green.

**Exit artifacts:**
- inventory/checklist document for ADR 0078 migration scope;
- baseline validation report snapshot.

### Phase 1: Physical Move (No Manifest Cutover)

1. Move object templates to `v5/topology/object-modules/<object-id>/templates/<generator-id>/`.
2. Move object-scoped plugins to `v5/topology/object-modules/<object-id>/plugins/`.
3. Keep legacy resolution/fallback active while validating moved layout.

**Go/No-Go:** proceed only if moved paths compile and test with fallback still enabled.

**Exit artifacts:**
- migrated files under object-module paths;
- updated inventory showing new canonical locations.

### Phase 2: Manifest Cutover and Lock Regeneration

1. Update `v5/topology-tools/plugins/plugins.yaml` entrypoints to object-module plugin paths.
2. Regenerate `v5/projects/home-lab/framework.lock.yaml`.
3. Run strict compile, plugin integration tests, and distribution smoke generation.

**Go/No-Go:** proceed only if all validations pass without object-specific path overrides.

**Exit artifacts:**
- plugin manifest entrypoints switched to object-module plugins;
- regenerated framework lock aligned with runtime resolution.

### Phase 3: Compatibility Window (One Release Cycle)

1. Keep temporary compatibility shims/fallback for migrated objects for one validated release cycle.
2. Track fallback usage in CI/tests and treat any fallback hit for migrated objects as a blocking signal.
3. Fix residual path/import issues before legacy removal.

**Go/No-Go:** proceed only after one full release cycle with zero fallback hits for migrated objects.

**Exit artifacts:**
- CI evidence of zero fallback hits;
- closure note for compatibility window.

### Phase 4: Legacy Cleanup and Finalization

1. Remove object-specific legacy templates/plugins from `topology-tools/*` roots.
2. Remove temporary shims used only for migration compatibility.
3. Update inventories/references and rerun full validation pipeline.

**Go/No-Go:** finalize only when post-cleanup validations are green.

**Exit artifacts:**
- legacy object-specific assets removed from tools domain;
- final migration completion record.

---

## Migration Notes

1. Move template files physically to object module `templates/` subtree.
2. Move object-scoped generator plugin files to object module `plugins/` subtree.
3. Update generator template names/roots to object-local paths.
4. Update plugin manifest entrypoints to object-module plugin files.
5. Rebuild framework lock and run strict compile/validation gates.
6. Keep compatibility shims only as temporary layer for legacy imports/tests.

---

## Verification Matrix

Minimum verification set per migration batch:

1. Unit/integration generators:
   - `v5/tests/plugin_integration/test_terraform_mikrotik_generator.py`
   - `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`
   - `v5/tests/plugin_integration/test_bootstrap_generators.py`
2. Projection-contract enforcement:
   - `v5/tests/plugin_integration/test_generator_projection_contract.py`
3. Template/publish contract:
   - `v5/tests/plugin_integration/test_generator_template_and_publish_contract.py`
4. Runtime strict audit:
   - `v5/tests/plugin_integration/test_strict_runtime_entrypoint_audit.py`
5. Strict compile gate:
   - `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

---

## Acceptance Criteria

1. Object-specific templates are no longer required from `topology-tools/templates` for migrated objects.
2. Object-specific generator plugin entrypoints resolve from `object-modules/<object-id>/plugins`.
3. Strict compile and plugin integration tests pass with object-local templates/plugins.
4. Framework distribution includes migrated templates/plugins under object module paths.
5. Compatibility shims for migrated objects are removed after one validated release cycle with no fallback hits in CI/tests.
6. For each migration batch, an inventory/checklist artifact and validation evidence exist before and after manifest cutover.
7. Post-cleanup validation passes after removing legacy object-specific assets from `topology-tools/*`.

---

## Implementation Status (2026-03-21)

1. Wave 1 complete: object-specific templates moved from `topology-tools/templates` to object modules.
2. Wave 2 complete: object-specific generator registration moved to module manifests.
3. Wave 3 complete: object-specific compatibility shims removed from `v5/topology-tools/plugins/generators/`.
4. Wave 4 complete: docs and release preflight updated with ADR0078 ownership checks.
5. Wave 5 deferred: projection ownership split remains optional hardening.

---

## References

- `v5/topology/object-modules/mikrotik/templates/terraform/`
- `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`
- `v5/topology/object-modules/mikrotik/plugins/bootstrap_mikrotik_generator.py`
- `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- `v5/topology/object-modules/proxmox/plugins/bootstrap_proxmox_generator.py`
- `v5/topology/object-modules/orangepi/plugins/bootstrap_orangepi_generator.py`
- `v5/topology-tools/plugins/plugins.yaml`
- `v5/topology-tools/templates/TEMPLATE-INVENTORY.md`
- `v5/projects/home-lab/framework.lock.yaml`
- `v5/tests/plugin_integration/test_generator_projection_contract.py`
- `v5/tests/plugin_integration/test_generator_template_and_publish_contract.py`
- `adr/0078-analysis/IMPLEMENTATION-PLAN.md`
