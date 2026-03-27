# ADR 0078: Object-Module Local Plugin Ownership and Runtime Layout

**Date:** 2026-03-21
**Status:** Accepted
**Depends on:** ADR 0062, ADR 0074, ADR 0076, ADR 0077
**Amended:** 2026-03-22 (scope extended to compilers/validators/generators)
**Amended:** 2026-03-22 (instance isolation, cross-object import prohibition, dynamic discovery)

---

## Layout Alignment Note (2026-03-27)

This ADR remains active for ownership/boundary policy, but all repository paths are interpreted in root-layout form:

1. `topology/...` (instead of legacy `v5/topology/...`)
2. `topology-tools/...` (instead of legacy `v5/topology-tools/...`)
3. `projects/...` (instead of legacy `v5/projects/...`)
4. `tests/...` (instead of legacy `v5/tests/...`)

---

## Context

In v5, object behavior is defined in `topology/object-modules/*`, but object-scoped implementation was split across `topology-tools`:

1. templates in `topology-tools/templates/*`;
2. plugin code in `topology-tools/plugins/*`.

This caused practical issues:

1. object implementation, templates, and plugin code were split across different roots;
2. framework distribution/build flow had to preserve extra object-specific paths from tools domain;
3. module portability to external projects was weaker because object assets were not self-contained.

For object-scoped plugins (generators, validators, compilers), templates and plugin implementation are part of object module implementation, not global tooling infrastructure.

An object-scoped plugin in this ADR means a plugin whose templates/logic are owned by one object module and are not intended as cross-object shared infrastructure.

---

## Decision Drivers

1. Keep object implementation assets colocated under one ownership root.
2. Improve framework/project portability by reducing hidden tool-domain coupling.
3. Make packaging and extraction deterministic for generated project consumption.
4. Preserve compatibility for shared/global plugins and templates.
5. Enforce one architecture contract across compilers, validators, and generators.

---

## Decision

Move object-specific templates and plugin code into corresponding object modules.

Classification rule (normative):

1. A plugin is **object-scoped** when both are true:
   - it targets one object namespace (`obj.<vendor_or_object>.*`);
   - its templates are not reused as cross-object shared infrastructure.
2. A plugin is **shared/global** when it emits cross-object artifacts (for example effective model exports or inventory aggregation) and does not belong to one object module ownership root.

Scope extension (normative):

1. ADR0078 applies to all v5 plugin families:
   - discoverers;
   - compilers;
   - validators;
   - generators.
2. All plugin families MUST follow the same level-boundary contract and ownership rules.

### Unified plugin rules (normative)

All compilers/validators/generators MUST be built by common rules:

1. Four levels are mandatory:
   - global/core infrastructure level;
   - class level;
   - object level;
   - instance level (using a dedicated project plugin root, for example `projects/<project-id>/plugins`, not `instances_root` shard data directories).
2. Each level is responsible only for its own abstraction:
   - class level MUST NOT reference object/instance specifics;
   - object level MUST NOT reference instance specifics.
3. A plugin at level `N` may call only interfaces that are implemented by level `N+1` (higher/specialized level).
4. On class level there are:
   - global class-level plugins;
   - class-specific plugins.
5. On object level there are:
   - global object-level plugins;
   - object-specific plugins.
6. Global plugins that do not contain class/object-specific names MUST be moved to global/core infrastructure level.
7. Global plugins MUST orchestrate specific plugins through interfaces or equivalent design patterns.
8. Plugin design MUST remain SOLID-compliant.

### Instance isolation contract (normative)

Object-level plugins MUST NOT contain instance-specific data:

Instance-scoped plugin discovery MUST remain outside shard data roots and MUST NOT scan
`projects/<project-id>/topology/instances/**` (ADR 0071 data-only contract).

1. **Prohibited patterns in object-level code:**
   - hardcoded IP addresses (e.g., `192.168.88.1`, `10.0.10.1`);
   - hardcoded hostnames or FQDNs (e.g., `proxmox.local`, `mikrotik.home`);
   - hardcoded port numbers tied to specific deployments;
   - hardcoded filesystem paths referencing specific instance data;
   - any literal values that belong to a specific deployment instance.

2. **Allowed patterns:**
   - protocol defaults (e.g., `https://`, port `8006` for Proxmox API);
   - placeholder templates (e.g., `https://${host}:${port}`);
   - values derived from projection data at runtime;
   - configurable defaults via `ctx.config` or plugin manifest `config` section.

3. **Enforcement:**
   - CI MUST run instance-literal scan on all object-level plugin code;
   - regex patterns for IP addresses, common hostnames, and deployment-specific literals;
   - violations block merge and require explicit exception with justification.

4. **Configuration injection pattern:**
   ```python
   # WRONG - hardcoded instance data
   api_url = "https://192.168.88.1:8443"

   # CORRECT - derived from projection or config
   api_url = ctx.config.get("api_url") or f"https://{projection.host}:{projection.port}"
   ```

### Cross-object import prohibition (normative)

Object modules MUST NOT import from each other:

1. **Prohibited:**
   - `from topology.object_modules.proxmox.plugins import ...` in mikrotik module;
   - `from topology.object_modules.mikrotik.plugins import ...` in network module;
   - any direct import path crossing object module boundaries.

2. **Allowed:**
   - imports from `object_modules/_shared/` (shared utilities);
   - imports from `topology-tools/` (framework infrastructure);
   - imports from `class-modules/` (upper-level contracts);
   - standard library and external dependencies.

3. **Enforcement:**
   - `test_plugin_level_boundaries.py` MUST include cross-object import scan;
   - AST-based or regex scan of all `*.py` files under `object-modules/*/plugins/`;
   - violations are hard test failures.

4. **Rationale:**
   - object modules must be independently extractable;
   - cross-object coupling prevents module portability;
   - shared logic belongs in `_shared/` or upper levels.

### Dynamic object module discovery (normative)

Framework MUST NOT hardcode object module paths:

1. **Prohibited:**
   ```python
   OBJECT_PROJECTION_PATHS = {
       "proxmox": Path("...proxmox/plugins/projections.py"),
       "mikrotik": Path("...mikrotik/plugins/projections.py"),
   }
   ```

2. **Required pattern:**
   ```python
   def discover_object_projections(object_modules_root: Path) -> dict[str, Path]:
       """Dynamically discover projection modules from filesystem."""
       return {
           obj_dir.name: obj_dir / "plugins" / "projections.py"
           for obj_dir in object_modules_root.iterdir()
           if obj_dir.is_dir()
           and not obj_dir.name.startswith("_")
           and (obj_dir / "plugins" / "projections.py").exists()
       }
   ```

3. **Benefits:**
   - adding new object module requires no framework code changes;
   - Open-Closed Principle compliance;
   - reduced maintenance burden.

4. **Migration:**
   - replace `OBJECT_PROJECTION_PATHS` dict with discovery function;
   - add caching via `@lru_cache` for performance;
   - add test verifying discovery finds all expected modules.

### Capability-template externalization (normative)

Generator capability-to-template mappings MUST be externalized:

1. **Prohibited:**
   ```python
   if has_qos:
       templates["qos.tf"] = "terraform/qos.tf.j2"
   if has_wireguard:
       templates["vpn.tf"] = "terraform/vpn.tf.j2"
   ```

2. **Required pattern in `plugins.yaml`:**
   ```yaml
   config:
     capability_templates:
       qos:
         enabled_by: capabilities.qos
         template: terraform/qos.tf.j2
         output: qos.tf
       wireguard:
         enabled_by: capabilities.wireguard
         template: terraform/vpn.tf.j2
         output: vpn.tf
       containers:
         enabled_by: capabilities.containers
         template: terraform/containers.tf.j2
         output: containers.tf
   ```

3. **Generator implementation:**
   ```python
   def get_capability_templates(self, projection: dict, config: dict) -> dict:
       """Resolve templates based on capability flags and config."""
       templates = {}
       for cap_id, cap_config in config.get("capability_templates", {}).items():
           if self._check_capability(projection, cap_config["enabled_by"]):
               templates[cap_config["output"]] = cap_config["template"]
       return templates
   ```

4. **Benefits:**
   - adding new capability requires only config change;
   - generator code remains stable;
   - capability-template relationships are declarative and auditable.

### Projection architecture consolidation (normative)

Projection ownership MUST follow clear hierarchy:

1. **Core/shared projections** (`topology-tools/plugins/generators/projections.py`):
   - `build_ansible_projection()` - cross-object inventory;
   - `build_docs_projection()` - cross-object documentation;
   - `build_effective_model_projection()` - model export.

2. **Object-specific projections** (`object-modules/<id>/plugins/projections.py`):
   - `build_mikrotik_projection()` - MikroTik-specific;
   - `build_proxmox_projection()` - Proxmox-specific.

3. **Shared utilities** (`object-modules/_shared/plugins/`):
   - `bootstrap_projections.py` - shared bootstrap helpers;
   - `projection_helpers.py` - common transformation utilities.

4. **Prohibited:**
   - object-specific projection logic in core projections module;
   - core projection logic in object-specific modules;
   - duplicate projection builders across modules.

5. **Discovery contract:**
   - core projections are imported directly from tools;
   - object projections are discovered via `load_object_projection_module()`;
   - shared utilities are imported from `_shared`.

### Normative layout

1. Object templates MUST be stored under:
   - `topology/object-modules/<object-id>/templates/<generator-id>/`
2. Object-scoped generator plugins MUST be stored under:
   - `topology/object-modules/<object-id>/plugins/`
3. Plugin manifest entrypoints for object-scoped generators MUST point to object-module plugin paths.
4. Shared, cross-object templates MAY remain under:
   - `topology-tools/templates/`
5. Shared, cross-object plugins MAY remain under:
   - `topology-tools/plugins/`

### Object migrations in scope

1. MikroTik Terraform templates:
   - old: `topology-tools/templates/terraform/mikrotik/*`
   - new: `topology/object-modules/mikrotik/templates/terraform/*`
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

1. During transition, central `topology-tools/plugins/plugins.yaml` MAY reference object-module plugin paths.
2. Target end-state: object-module `plugins.yaml` manifests own object-scoped plugin registration.
3. Duplicate plugin IDs across central and module manifests are forbidden and treated as hard manifest load errors.
4. Registration policy is identical for compilers/validators/generators.

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
3. Moving cross-object/shared plugins that are intentionally framework-global.
4. Revising plugin API contracts from ADR 0065/0074.

---

## Consequences

### Positive

1. Object modules become more self-contained and portable.
2. Framework distribution structure aligns with implementation ownership.
3. Lower risk of path drift between local repo and extracted/project consumption.
4. Plugin entrypoints are aligned with module ownership boundaries across all plugin families.

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
5. Risk: new cross-level coupling appears during v5 refactoring of validators/compilers.
   - Mitigation: enforce plugin-level boundary tests and staged cutover parity gates.
6. Risk: instance-specific literals leak into object-level generators.
   - Mitigation: automated regex scan in CI for IP addresses, hostnames, and deployment-specific patterns.
7. Risk: cross-object imports bypass isolation boundary.
   - Mitigation: AST/regex scan in `test_plugin_level_boundaries.py` with hard test failure.
8. Risk: hardcoded object module paths break when new modules are added.
   - Mitigation: replace static mappings with dynamic discovery; add discovery coverage test.
9. Risk: capability-template coupling creates maintenance burden.
   - Mitigation: externalize mappings to plugin config; validate config schema on load.
10. Risk: projection architecture drift between core and object modules.
    - Mitigation: enforce ownership boundaries via test; document consolidation policy.

---

## Compatibility Strategy (Shim Sunset)

Compatibility shims in `topology-tools/plugins/generators/*` are transitional only.

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

1. Move object templates to `topology/object-modules/<object-id>/templates/<generator-id>/`.
2. Move object-scoped plugins to `topology/object-modules/<object-id>/plugins/`.
3. Keep legacy resolution/fallback active while validating moved layout.

**Go/No-Go:** proceed only if moved paths compile and test with fallback still enabled.

**Exit artifacts:**
- migrated files under object-module paths;
- updated inventory showing new canonical locations.

### Phase 2: Manifest Cutover and Lock Regeneration

1. Update `topology-tools/plugins/plugins.yaml` entrypoints to object-module plugin paths.
2. Regenerate `projects/home-lab/framework.lock.yaml`.
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

### Phase 5: v5 Unified Refactor Preparation (Compilers + Validators + Generators)

1. Build current-state inventory by plugin family and level:
   - core/global plugins;
   - class-level plugins;
   - object-level plugins;
   - instance-level plugins.
2. Mark violations:
   - cross-level direct calls;
   - object/instance leakage in higher levels;
   - global plugins containing class/object-specific names.
3. Produce refactor backlog with prioritized work packages:
   - interface extraction;
   - plugin relocation by ownership;
   - manifest registration normalization.
4. Define mandatory verification gates for each package:
   - plugin boundary contracts;
   - v4-v5 parity lanes;
   - integration suites and strict compile.
5. Freeze new violations:
   - add/extend tests that fail on new cross-level leakage.

**Go/No-Go:** start v5 refactor execution only after inventory/backlog/gates are documented and approved.

**Exit artifacts:**
- unified refactor inventory and backlog document;
- updated ADR0078-related implementation plan with execution waves for all plugin families.

### Phase 6: Instance Isolation and Cross-Object Boundary Enforcement

1. **Instance literal cleanup (completed 2026-03-22):**
   - audited object-level generators for hardcoded IPs/hostnames;
   - refactored endpoint resolution to projection/config-first flow;
   - added enforcement in plugin contract boundary tests.

2. **Cross-object import prohibition (completed 2026-03-22):**
   - added `test_object_modules_do_not_cross_import_other_object_modules()` to plugin contract tests;
   - added AST-based scan across `object-modules/*/plugins/*.py`;
   - violations are hard failures.

3. **Dynamic object discovery (completed 2026-03-22):**
   - replaced `OBJECT_PROJECTION_PATHS` static dict with dynamic discovery;
   - added `@lru_cache` for discovered paths;
   - added discovery integration tests.

4. **Capability-template externalization (completed 2026-03-22):**
   - move capability-template mappings from generator code to `plugins.yaml`;
   - update generators to read mappings from config;
   - add schema validation for capability config.

**Go/No-Go:** Phase 6 is closed; proceed with final Phase 7 consolidation gates.

**Exit artifacts:**
- `tests/plugin_contract/test_plugin_level_boundaries.py::test_object_plugin_python_files_do_not_hardcode_private_or_local_url_hosts` passing;
- `tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import_other_object_modules` passing;
- `tests/plugin_integration/test_object_projection_loader.py` passing;
- capability mappings externalized in all object module manifests.

### Phase 7: Projection Architecture Consolidation

1. **Audit projection ownership:**
   - document all projection builders by location and purpose;
   - identify any misplaced projections (object-specific in core, core in object).

2. **Consolidate shared utilities:**
   - move common helpers to `_shared/plugins/projection_helpers.py`;
   - update imports across all modules.

3. **Enforce ownership boundaries:**
   - add test verifying core projections don't contain object-specific logic;
   - add test verifying object projections don't duplicate core logic.

4. **Document projection discovery:**
   - formalize `load_object_projection_module()` contract;
   - document fallback and error handling semantics.

**Go/No-Go:** proceed only when projection ownership is clear and tested.

**Exit artifacts:**
- projection ownership inventory document;
- `test_projection_ownership_boundaries.py` passing;
- updated `_shared/plugins/` with consolidated helpers.

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
   - `tests/plugin_integration/test_terraform_mikrotik_generator.py`
   - `tests/plugin_integration/test_terraform_proxmox_generator.py`
   - `tests/plugin_integration/test_bootstrap_generators.py`
2. Projection-contract enforcement:
   - `tests/plugin_integration/test_generator_projection_contract.py`
3. Template/publish contract:
   - `tests/plugin_integration/test_generator_template_and_publish_contract.py`
4. Runtime strict audit:
   - `tests/plugin_integration/test_strict_runtime_entrypoint_audit.py`
5. Strict compile gate:
   - `python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

Additional verification for Phase 6-7:

6. Instance isolation enforcement:
   - `tests/plugin_contract/test_plugin_level_boundaries.py::test_object_plugin_python_files_do_not_hardcode_private_or_local_url_hosts`
   - regex scan for IP patterns: `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`
   - regex scan for hostname patterns: `\b[a-z][\w-]*\.(local|home|lan|internal)\b`
7. Cross-object import prohibition:
   - `tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import_other_object_modules`
   - AST scan for `from topology.object_modules.<other>` patterns
8. Dynamic object discovery:
   - `tests/plugin_integration/test_object_projection_loader.py`
   - verify no hardcoded object module paths in framework code
9. Capability-template externalization:
   - `tests/plugin_contract/test_capability_template_config.py`
   - verify generators read capability mappings from config, not code
10. Projection ownership boundaries:
    - `tests/plugin_contract/test_projection_ownership_boundaries.py`
    - verify no object-specific logic in core projections

---

## Acceptance Criteria

1. Object-specific templates are no longer required from `topology-tools/templates` for migrated objects.
2. Object-specific generator plugin entrypoints resolve from `object-modules/<object-id>/plugins`.
3. Strict compile and plugin integration tests pass with object-local templates/plugins.
4. Framework distribution includes migrated templates/plugins under object module paths.
5. Compatibility shims for migrated objects are removed after one validated release cycle with no fallback hits in CI/tests.
6. For each migration batch, an inventory/checklist artifact and validation evidence exist before and after manifest cutover.
7. Post-cleanup validation passes after removing legacy object-specific assets from `topology-tools/*`.
8. Compilers/validators/generators follow the same four-level contract and interface-driven orchestration model.
9. v5 refactor backlog for unified rules is prepared and linked from ADR0078 implementation artifacts.

Phase 6-7 acceptance criteria:

10. Object-level generators contain no hardcoded instance-specific literals (IPs, hostnames).
11. Object modules do not import from each other (cross-object import prohibition enforced).
12. Object module discovery is fully dynamic (no hardcoded module paths in framework).
13. Capability-template mappings are externalized to plugin config (not hardcoded in generator code).
14. Projection ownership boundaries are documented and tested (core vs object vs shared).

---

## Implementation Status (2026-03-22)

1. Generator migration waves (1-5) are complete:
   - object-specific templates/plugins moved under object modules;
   - generator ownership checks and compatibility evidence captured.
2. ADR0078 scope is extended to compilers/validators/generators with unified rules.
3. v5 unified refactor preparation is now required before next migration/refactor wave.
4. Detailed execution preparation is tracked in:
   - `adr/0078-analysis/IMPLEMENTATION-PLAN.md`
   - `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`

**Phase 6-7 status (updated 2026-03-22):**

5. Phase 6 (Instance Isolation and Cross-Object Boundary Enforcement):
   - Status: **Completed**
   - Completed:
     - removed hardcoded instance endpoints from object terraform generators;
     - switched projection loader to dynamic discovery;
     - added cross-object import and literal endpoint enforcement in plugin contract tests;
     - added discovery coverage in integration tests.
      - externalized capability-template mappings to module config and added contract tests.

6. Phase 7 (Projection Architecture Consolidation):
   - Status: **Completed**
   - Current state: hybrid architecture (core + object + _shared);
   - Result: ownership boundaries are documented and enforced by dedicated contract tests.

---

## References

- `topology/object-modules/mikrotik/templates/terraform/`
- `topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`
- `topology/object-modules/mikrotik/plugins/bootstrap_mikrotik_generator.py`
- `topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- `topology/object-modules/proxmox/plugins/bootstrap_proxmox_generator.py`
- `topology/object-modules/orangepi/plugins/bootstrap_orangepi_generator.py`
- `topology/object-modules/_shared/plugins/bootstrap_projections.py`
- `topology-tools/plugins/plugins.yaml`
- `topology-tools/plugins/generators/object_projection_loader.py`
- `topology-tools/plugins/generators/projections.py`
- `topology-tools/templates/TEMPLATE-INVENTORY.md`
- `projects/home-lab/framework.lock.yaml`
- `tests/plugin_integration/test_generator_projection_contract.py`
- `tests/plugin_integration/test_generator_template_and_publish_contract.py`
- `tests/plugin_contract/test_plugin_level_boundaries.py`
- `tests/plugin_integration/test_object_projection_loader.py` (Phase 6)
- `tests/plugin_contract/test_capability_template_config.py` (Phase 6)
- `tests/plugin_contract/test_projection_ownership_boundaries.py` (Phase 7)
- `adr/0078-analysis/IMPLEMENTATION-PLAN.md`
- `adr/plan/0078-v5-unified-plugin-refactor-prep.md`
- `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`
