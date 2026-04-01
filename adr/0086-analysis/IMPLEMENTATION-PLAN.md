# ADR 0086 — Implementation Plan

## Overview

Flatten the 4-level plugin hierarchy into a single-level model, consolidate
structurally identical plugins via declarative rules and strategy patterns,
and introduce `contributes_to` protocol for vendor strategy extensibility.

**Goal:** 67 → ~37 standalone plugins + 5 strategy entries, 4 → 1 level for
standalone plugins, simplified manifests, zero visibility rules.

**Constraint:** Each phase MUST pass all existing regression tests before proceeding.

**Extensibility constraint:** Multi-slot manifest discovery chain
(`plugin_manifest_discovery.py`) and project plugin root MUST remain operational
throughout all phases (ADR 0081 §3.3–3.4 compliance).

---

## Phase 0: Kernel Extension — `contributes_to` Support (Prerequisite)

**Scope:** Add `contributes_to` field to plugin spec and registry query.

### Steps

0.1. **Add `contributes_to` to `PluginSpec`** — optional `str` field, default `""`.
     Update `PluginSpec.from_dict()` to read it from manifest data.

0.2. **Add `get_contributors()` to `PluginRegistry`:**
     ```python
     def get_contributors(self, host_plugin_id: str) -> list[PluginSpec]:
         return [
             spec for spec in self.specs.values()
             if spec.contributes_to == host_plugin_id
         ]
     ```

0.3. **Add validation rules** to `_validate_spec()`:
     - `contributes_to` target must exist in registry (deferred check in
       `resolve_dependencies()` since target may load later)
     - Contributor must share at least one stage with host plugin
     - Contributor must not appear in other plugins' `depends_on`

0.4. **Update `schemas/plugin-manifest.schema.json`** — add `contributes_to` as
     optional string field.

0.5. **Write unit tests** for `get_contributors()`, validation rules, schema.

### Verification Gate
- `pytest tests/test_plugin_registry.py` — all pass
- New tests for `contributes_to` pass
- Existing manifests load without errors (field is optional, default empty)

---

## Phase 1: Declarative Reference Validator (Low Risk, High Impact)

**Scope:** Merge 11 reference validators into 1 declarative plugin.

### Steps

1.1. **Catalogue reference rules** — extract field names, diagnostic codes, layer
     constraints, and target-class filters from each of the 11 validators:
     - `backup_refs_validator.py`
     - `certificate_refs_validator.py`
     - `dns_refs_validator.py`
     - `host_os_refs_validator.py`
     - `lxc_refs_validator.py`
     - `network_core_refs_validator.py`
     - `power_source_refs_validator.py`
     - `service_dependency_refs_validator.py`
     - `service_runtime_refs_validator.py`
     - `storage_l3_refs_validator.py`
     - `vm_refs_validator.py`

1.2. **Create `ReferenceRule` dataclass** and `DeclarativeReferenceValidator` in
     `topology-tools/plugins/validators/declarative_reference_validator.py`.

1.3. **Migrate rules** — populate `RULES` list from catalogued data.

1.4. **Run regression tests** — validate identical diagnostics output.

1.5. **Remove old files** — delete 11 validator files, update `plugins.yaml` (11 entries → 1).

1.6. **Update dependency graph** — any plugin with `depends_on` pointing to removed IDs
     must be updated to point to the new consolidated ID.

### Verification Gate
- `pytest tests/` — all pass
- Diagnostic parity: same codes, same messages, same severity for all reference checks

---

## Phase 2: Consolidate Port Validators (Low Risk, Small Scope)

**Scope:** Merge 3 port validator files into 1.

### Steps

2.1. **Create `RouterPortValidator`** in
     `topology-tools/plugins/validators/router_port_validator.py` with vendor rules dict.

2.2. **Migrate logic** from `router_port_validator_base.py` into the new plugin.
     Add vendor entries for MikroTik (E7302) and GL.iNet (E7303).

2.3. **Update manifest** — 3 entries → 1, update depends_on references.

2.4. **Remove old files:**
     - `topology/class-modules/router/plugins/router_port_validator_base.py`
     - `topology/class-modules/router/plugins/validators/router_data_channel_interface_validator.py`
       — assess: migrate to global validators or merge into RouterPortValidator
     - `topology/object-modules/mikrotik/plugins/validators/mikrotik_router_ports_validator.py`
     - `topology/object-modules/glinet/plugins/validators/glinet_router_ports_validator.py`

2.5. **Remove class/object manifest files** if they become empty:
     - `topology/class-modules/router/plugins.yaml`
     - `topology/object-modules/glinet/plugins.yaml`
     - `topology/object-modules/network/plugins.yaml` (move ethernet_cable_endpoint to global)

### Verification Gate
- `pytest tests/` — all pass
- Port validation diagnostics parity

---

## Phase 3: Vendor Generator Strategy Migration (Medium Risk)

**Scope:** Convert 5 vendor generators into `contributes_to` strategy entries
dispatched by 2 host generators. **No `lib/` for strategies.**

### Steps

3.1. **Create host generators:**
     - `topology-tools/plugins/generators/terraform_generator.py` — `TerraformGenerator`
     - `topology-tools/plugins/generators/bootstrap_generator.py` — `BootstrapGenerator`
     Both use `registry.get_contributors(self.plugin_id)` to discover strategies.

3.2. **Register host generators** in `topology-tools/plugins/plugins.yaml`:
     - `generator.terraform` (order: 210)
     - `generator.bootstrap` (order: 310)

3.3. **Refactor existing vendor generators** to strategy interface:
     - `terraform_proxmox_generator.py` → implements `TerraformVendorStrategy` protocol
     - `terraform_mikrotik_generator.py` → implements `TerraformVendorStrategy` protocol
     - `bootstrap_proxmox_generator.py` → implements `BootstrapVendorStrategy` protocol
     - `bootstrap_mikrotik_generator.py` → implements `BootstrapVendorStrategy` protocol
     - `bootstrap_orangepi_generator.py` → implements `BootstrapVendorStrategy` protocol

     Strategy files stay in their object-module directories:
     `topology/object-modules/<vendor>/plugins/generators/`.
     **They are NOT moved to `lib/`.**

3.4. **Update object-module manifests** with `contributes_to`:
     - `topology/object-modules/proxmox/plugins.yaml` — change 2 entries to strategy format
     - `topology/object-modules/mikrotik/plugins.yaml` — change 2 entries to strategy format
     - `topology/object-modules/orangepi/plugins.yaml` — change 1 entry to strategy format

3.5. **Move projection builders** to `lib/` directories (these are non-extensible helpers):
     - Rename `object-modules/*/plugins/projections.py` → `object-modules/*/lib/projection.py`
     - Update imports in strategy modules

3.6. **Move shared helpers** to `object-modules/_shared/lib/`:
     - `bootstrap_helpers.py`, `bootstrap_projections.py`
     - `capability_helpers.py`, `terraform_helpers.py`

3.7. **Update main manifest** — add host generator entries, update depends_on/consumes for
     assembler/builder plugins that depended on old vendor generator IDs.

3.8. **Remove old standalone generator manifest entries** from object-module manifests
     (replaced by `contributes_to` strategy entries).

### Verification Gate
- `pytest tests/` — all pass
- Generated artifact parity: `diff -r` against pre-refactor output
- Terraform validate, ansible-inventory --list pass
- Project plugin discovery still works (regression test for `project_plugins_root`)

---

## Phase 4: Flatten Plugin Directories (Medium Risk)

**Scope:** Move remaining class/object-level standalone plugins to global directories.

### Steps

4.1. **Audit remaining standalone plugins** in class-modules/object-modules after Phases 1–3.
     Expected remaining:
     - `topology/class-modules/router/plugins/validators/router_data_channel_interface_validator.py`
       (if not already handled in Phase 2)
     - `topology/object-modules/network/plugins/validators/ethernet_cable_endpoint_validator.py`

4.2. **Move to global directory:**
     - → `topology-tools/plugins/validators/router_data_channel_interface_validator.py`
     - → `topology-tools/plugins/validators/ethernet_cable_endpoint_validator.py`

4.3. **Verify object-module manifests** only contain `contributes_to` strategy entries.
     Remove empty manifest files (glinet, network — if all entries were standalone plugins).

4.4. **Update main manifest** with moved validators.

### Verification Gate
- `pytest tests/` — all pass
- `Get-ChildItem -Recurse topology/class-modules/*/plugins` returns nothing OR only strategy files
- Object-module `plugins.yaml` files contain only `contributes_to` entries
- Multi-slot discovery chain still works (test project_plugins_root slot)

---

## Phase 5: Unify IDs and Update Documentation (High Risk, Coordinated)

**Scope:** Rename plugin IDs, update all references, finalize documentation.

### Steps

5.1. **Create ID mapping table** — old ID → new ID for all ~37 remaining plugins +
     5 strategy entries.
     Convention: `<role>.<domain_name>` (e.g., `validator.reference_refs`,
     `compiler.module_loader`, `generator.terraform`, `strategy.mikrotik.terraform`).

5.2. **Update plugins.yaml files** — apply new IDs, update all `depends_on`,
     `consumes.from_plugin`, and `contributes_to` references.

5.3. **Update test fixtures** — any test that references plugin IDs by name.

5.4. **Update documentation** — ADR 0063, 0065, 0066, 0074, 0080, 0081 cross-references.

5.5. **Remove boundary test** — `test_plugin_level_boundaries.py`.

5.6. **Add architectural tests:**
     - Verify no standalone plugin entries exist outside `topology-tools/plugins/`
     - Verify all object-module manifest entries have `contributes_to` field
     - Verify `project_plugins_root` slot remains functional
     - Verify `contributes_to` targets exist in registry

### Verification Gate
- `pytest tests/` — all pass
- Full pipeline run: compile → validate → generate produces identical output
- CI green

---

## Phase 6: Documentation and Cleanup

### Steps

6.1. **Update CLAUDE.md, AGENTS.md, copilot-instructions.md** — remove 4-level boundary
     rules, update directory structure, update plugin conventions, document
     `contributes_to` protocol.

6.2. **Update ADR 0063** — add "Superseded by ADR 0086 Section 4B" note.

6.3. **Clean up empty directories** — remove any leftover empty plugin dirs.

6.4. **Update README** if it references plugin boundaries.

6.5. **Document `contributes_to` protocol** for project developers:
     - How to add a vendor strategy to a standalone project
     - Where to place strategy files and manifests
     - ID naming convention for project-contributed strategies

---

## Risk Matrix

| Phase | Risk   | Blast Radius | Rollback |
|-------|--------|-------------|----------|
| 0     | Low    | Kernel only (additive) | Git revert |
| 1     | Low    | Validators only | Git revert, restore 11 files |
| 2     | Low    | 3 validators | Git revert |
| 3     | Medium | Generators, generated output | Git revert, regenerate |
| 4     | Medium | Plugin discovery, all plugins | Git revert |
| 5     | High   | All plugin IDs, all tests | Git revert (coordinated) |
| 6     | None   | Documentation only | Git revert |

## Success Criteria

- [ ] Plugin count ≤ 40 (standalone)
- [ ] `contributes_to` protocol implemented in kernel
- [ ] Host generators discover strategy entries at runtime
- [ ] Single framework plugins.yaml for standalone plugins
- [ ] Object-module manifests contain only `contributes_to` strategy entries
- [ ] No standalone plugins/ directories in class-modules
- [ ] Multi-slot discovery chain preserved (slot #0–#3)
- [ ] Project plugin root (`project_plugins_root`) remains functional
- [ ] All existing tests pass
- [ ] Generated artifacts identical to pre-refactor baseline
- [ ] AI agent instructions simplified (no 4-level boundary rules)
- [ ] Extensibility test: mock project can register custom vendor strategy
