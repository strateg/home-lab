# ADR0078 Audit Fix Status — 2026-03-23

## Scope

This note records the ADR0078 compliance audit and fixes performed on 2026-03-23 for `v5` plugin/runtime code.

Normative source:
- `adr/0078-object-module-local-template-layout.md`

Primary scope reviewed:
- `v5/topology-tools/plugins/generators/`
- `v5/topology-tools/compiler_runtime.py`
- `v5/topology-tools/compile-topology.py`
- `v5/topology/class-modules/*/plugins.yaml`
- `v5/topology/object-modules/*/plugins.yaml`
- `v5/topology/object-modules/*/plugins/*.py`
- `v5/tests/plugin_contract/`
- `v5/tests/plugin_integration/`

---

## Initial Findings

### F1 — Dynamic object projection discovery included service directories

**Severity:** Major

**Problem:**
`v5/topology-tools/plugins/generators/object_projection_loader.py` discovered any object-module directory containing `plugins/projections.py`, including underscore-prefixed service/helper directories such as `_shared`.

**ADR0078 rule:**
Dynamic object discovery must ignore service/helper directories and must not treat `_shared` as a regular object module.

**Fix:**
Excluded underscore-prefixed directories in discovery.

**Changed files:**
- `v5/topology-tools/plugins/generators/object_projection_loader.py`
- `v5/tests/plugin_integration/test_object_projection_loader.py`

---

### F2 — Plugin manifest discovery had only 3 levels instead of 4

**Severity:** Major

**Problem:**
`discover_plugin_manifests()` merged only:
1. base
2. class
3. object

ADR0078 requires four levels:
1. core/global
2. class
3. object
4. instance

**Fix:**
Added optional `instance_manifests_root` to manifest discovery and wired it through compile runtime.

**Changed files:**
- `v5/topology-tools/compiler_runtime.py`
- `v5/topology-tools/compile-topology.py`
- `v5/tests/plugin_contract/test_manifest_discovery.py`

---

### F3 — `capability_templates` config did not match ADR0078 declarative format

**Severity:** Medium

**Problem:**
Object generator manifests used legacy list rows:
- `capability_key`
- `template`
- `output_file`

ADR0078 requires declarative capability-template mapping in manifest config using:
- `enabled_by`
- `template`
- `output`

**Fix:**
Migrated module manifests to ADR0078 declarative config shape and updated generator code to read the new format.

**Compatibility decision:**
Temporary backward compatibility with legacy list-based rows was retained in generator code to avoid breaking older tests/configs during transition.

**Changed files:**
- `v5/topology/object-modules/mikrotik/plugins.yaml`
- `v5/topology/object-modules/proxmox/plugins.yaml`
- `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`
- `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- `v5/tests/plugin_contract/test_capability_template_config.py`
- `v5/tests/plugin_integration/test_terraform_mikrotik_generator.py`
- `v5/tests/plugin_integration/test_mikrotik_capability_driven.py`
- `v5/tests/plugin_integration/test_generator_template_and_publish_contract.py`
- `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`

---

### F4 — Instance-literal enforcement was narrower than ADR0078

**Severity:** Medium

**Problem:**
Object-level literal scanning only caught URL literals with private IP / `.local` hostnames.
It did not catch bare deployment-specific literals such as:
- `192.168.x.x`
- `10.x.x.x`
- `172.16-31.x.x`
- `*.local`, `*.home`, `*.lan`, `*.internal`

**Fix:**
Extended contract checks to scan string constants for private IP literals and local-domain hostnames even when no URL scheme is present.

**Changed files:**
- `v5/tests/plugin_contract/test_plugin_level_boundaries.py`

---

## Residual Functional Gap Found During Second Audit

### F5 — Proxmox capability config was declarative but projection did not publish capability flags

**Severity:** Medium

**Problem:**
After converting `proxmox` manifest config to ADR0078 declarative shape, `terraform_proxmox_generator.py` expected `projection["capabilities"]`, but `build_proxmox_projection()` did not populate it.

This made capability-driven Proxmox templates effectively dead config.

**Fix:**
Added capability extraction/derivation in Proxmox projection and exposed:
- `has_ceph`
- `has_ha`
- `has_cloud_init`

**Changed files:**
- `v5/topology/object-modules/proxmox/plugins/projections.py`
- `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`

---

## Summary of Implemented Changes

### Runtime / discovery
- underscore-prefixed object-module directories are ignored by projection discovery
- manifest discovery now supports instance-level manifests
- compile runtime now passes project instance root into manifest discovery

### Object generator manifests
- MikroTik and Proxmox capability-template config migrated to ADR0078 declarative shape
- config schemas updated accordingly

### Generator implementation
- MikroTik generator supports declarative `enabled_by/template/output`
- Proxmox generator supports declarative `enabled_by/template/output`
- both retain temporary compatibility with legacy `capability_key/output_file`
- Proxmox projection now publishes capability flags required by declarative config

### Contract/integration coverage
- projection discovery ignores `_shared`/service directories
- instance-level manifest ordering is covered in contract tests
- capability-template schema/manifest contracts updated
- literal-scan contract strengthened
- Proxmox capability-flag derivation covered in integration tests

---

## Current Status

### Closed findings
- F1 — closed
- F2 — closed
- F3 — closed with transitional compatibility retained
- F4 — closed
- F5 — closed

### Remaining observations (not treated as blockers)

1. **Instance-level manifest support is implemented, but no real instance-level plugin manifests are currently present in `v5/projects/...`.**
   - This is acceptable as migration staging.
   - Runtime support exists for future adoption.

2. **Legacy compatibility branch for capability-template mapping still exists in generator code.**
   - This is intentional.
   - Recommended cleanup later: remove support for `capability_key/output_file` after one validated transition cycle.

---

## Recommended Next Step

Run a third-pass ADR0078 audit focused specifically on:
- compiler plugins
- validator plugins
- cross-level boundary adherence outside generator family

Target review areas:
- core/class/object separation
- instance leakage in validator/compiler code
- cross-object imports in object validators
- global-vs-specific plugin ownership consistency

---

## Suggested Verification Set

Targeted tests to run locally:
- `v5/tests/plugin_contract/test_manifest_discovery.py`
- `v5/tests/plugin_contract/test_capability_template_config.py`
- `v5/tests/plugin_contract/test_plugin_level_boundaries.py`
- `v5/tests/plugin_contract/test_object_generator_ownership.py`
- `v5/tests/plugin_contract/test_projection_ownership_boundaries.py`
- `v5/tests/plugin_integration/test_object_projection_loader.py`
- `v5/tests/plugin_integration/test_terraform_mikrotik_generator.py`
- `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`
- `v5/tests/plugin_integration/test_mikrotik_capability_driven.py`
- `v5/tests/plugin_integration/test_generator_template_and_publish_contract.py`

Optional broader sweep:
- `v5/tests/plugin_contract`
- `v5/tests/plugin_integration`

---

## Related Files

- `adr/0078-object-module-local-template-layout.md`
- `adr/0078-analysis/IMPLEMENTATION-PLAN.md`
- `v5/topology-tools/plugins/generators/object_projection_loader.py`
- `v5/topology-tools/compiler_runtime.py`
- `v5/topology-tools/compile-topology.py`
- `v5/topology/object-modules/mikrotik/plugins.yaml`
- `v5/topology/object-modules/proxmox/plugins.yaml`
- `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`
- `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- `v5/topology/object-modules/proxmox/plugins/projections.py`
- `v5/tests/plugin_contract/test_manifest_discovery.py`
- `v5/tests/plugin_contract/test_capability_template_config.py`
- `v5/tests/plugin_contract/test_plugin_level_boundaries.py`
- `v5/tests/plugin_integration/test_object_projection_loader.py`
- `v5/tests/plugin_integration/test_terraform_mikrotik_generator.py`
- `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`
