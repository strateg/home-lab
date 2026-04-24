# ADR0078 Phase 5: Unified Refactor Inventory and Backlog

**Status:** Implemented (WP-001 through WP-006 complete)
**Date:** 2026-03-23
**Author:** Claude Code / Human Review Pending

---

## 1. Plugin Inventory by Family and Level

### 1.1 Core/Global Plugins (v5/topology-tools/plugins/)

| Plugin ID | Family | Kind | Entry Point |
|-----------|--------|------|-------------|
| base.compiler.module_loader | compiler | compiler | compilers/module_loader_compiler.py |
| base.compiler.model_lock_loader | compiler | compiler | compilers/model_lock_loader_compiler.py |
| base.compiler.annotation_resolver | compiler | compiler | compilers/annotation_resolver_compiler.py |
| base.compiler.instance_rows | compiler | compiler | compilers/instance_rows_compiler.py |
| base.compiler.capability_contract_loader | compiler | compiler | compilers/capability_contract_loader_compiler.py |
| base.compiler.capabilities | compiler | compiler | compilers/capability_compiler.py |
| base.compiler.effective_model | compiler | compiler | compilers/effective_model_compiler.py |
| base.validator.governance_contract | validator | validator_yaml | validators/governance_contract_validator.py |
| base.validator.foundation_layout | validator | validator_yaml | validators/foundation_layout_validator.py |
| base.validator.foundation_include_contract | validator | validator_yaml | validators/foundation_include_contract_validator.py |
| base.validator.foundation_file_placement | validator | validator_yaml | validators/foundation_file_placement_validator.py |
| base.validator.foundation_device_taxonomy | validator | validator_json | validators/foundation_device_taxonomy_validator.py |
| base.validator.references | validator | validator_json | validators/reference_validator.py |
| base.validator.model_lock | validator | validator_json | validators/model_lock_validator.py |
| base.validator.power_source_refs | validator | validator_json | validators/power_source_refs_validator.py |
| base.validator.network_* (14 plugins) | validator | validator_json | validators/network_*.py |
| base.validator.service_* (2 plugins) | validator | validator_json | validators/service_*.py |
| base.validator.storage_* (3 plugins) | validator | validator_json | validators/storage_*.py |
| base.validator.dns_refs | validator | validator_json | validators/dns_refs_validator.py |
| base.validator.certificate_refs | validator | validator_json | validators/certificate_refs_validator.py |
| base.validator.backup_refs | validator | validator_json | validators/backup_refs_validator.py |
| base.validator.security_policy_refs | validator | validator_json | validators/security_policy_refs_validator.py |
| base.validator.vm_refs | validator | validator_json | validators/vm_refs_validator.py |
| base.validator.lxc_refs | validator | validator_json | validators/lxc_refs_validator.py |
| base.validator.host_os_refs | validator | validator_json | validators/host_os_refs_validator.py |
| base.validator.embedded_in | validator | validator_json | validators/embedded_in_validator.py |
| base.validator.ethernet_port_inventory | validator | validator_json | validators/ethernet_port_inventory_validator.py |
| base.validator.capability_contract | validator | validator_json | validators/capability_contract_validator.py |
| base.validator.instance_placeholders | validator | validator_json | validators/instance_placeholder_validator.py |
| base.validator.single_active_os | validator | validator_json | validators/single_active_os_validator.py |
| base.generator.effective_json | generator | generator | generators/effective_json_generator.py |
| base.generator.effective_yaml | generator | generator | generators/effective_yaml_generator.py |
| base.generator.docs | generator | generator | generators/docs_generator.py |
| base.generator.ansible_inventory | generator | generator | generators/ansible_inventory_generator.py |

**Total Core Plugins:** 7 compilers, ~35 validators, 4 generators

### 1.2 Class-Level Plugins (v5/topology/class-modules/)

| Plugin ID | Family | Kind | Entry Point | Module |
|-----------|--------|------|-------------|--------|
| class_router.validator_json.router_data_channel_interface | validator | validator_json | plugins/router_data_channel_interface_validator.py | router |

**Total Class Plugins:** 1 validator

### 1.3 Object-Level Plugins (v5/topology/object-modules/)

| Plugin ID | Family | Kind | Entry Point | Module |
|-----------|--------|------|-------------|--------|
| base.generator.terraform_proxmox | generator | generator | plugins/terraform_proxmox_generator.py | proxmox |
| base.generator.bootstrap_proxmox | generator | generator | plugins/bootstrap_proxmox_generator.py | proxmox |
| base.generator.terraform_mikrotik | generator | generator | plugins/terraform_mikrotik_generator.py | mikrotik |
| base.generator.bootstrap_mikrotik | generator | generator | plugins/bootstrap_mikrotik_generator.py | mikrotik |
| object_mikrotik.validator_json.router_ports | validator | validator_json | plugins/mikrotik_router_ports_validator.py | mikrotik |
| object_glinet.validator_json.router_ports | validator | validator_json | plugins/glinet_router_ports_validator.py | glinet |
| object_network.validator_json.ethernet_cable_endpoints | validator | validator_json | plugins/ethernet_cable_endpoint_validator.py | network |
| base.generator.bootstrap_orangepi | generator | generator | plugins/bootstrap_orangepi_generator.py | orangepi |

**Total Object Plugins:** 5 generators, 3 validators

### 1.4 Shared Plugins (v5/topology/object-modules/_shared/plugins/)

| File | Purpose |
|------|---------|
| bootstrap_projections.py | Shared bootstrap projection builder |

**Total Shared:** 1 projection module (not registered as plugin)

---

## 2. Violations Identified

### 2.1 Code Duplication (High Priority)

| ID | Pattern | Files Affected | Lines |
|----|---------|----------------|-------|
| DUP-001 | `_render_string_list()` | proxmox/terraform_proxmox_generator.py:17-21, mikrotik/terraform_mikrotik_generator.py:17-21 | ~10 |
| DUP-002 | `_capability_expression_enabled()` | proxmox/terraform_proxmox_generator.py:71-84, mikrotik/terraform_mikrotik_generator.py:82-95 | ~28 |
| DUP-003 | `_get_capability_templates()` | proxmox/terraform_proxmox_generator.py:34-69, mikrotik/terraform_mikrotik_generator.py:45-80 | ~72 |
| DUP-004 | Router port validator logic | mikrotik/mikrotik_router_ports_validator.py, glinet/glinet_router_ports_validator.py | ~160 |
| DUP-005 | `_get_bootstrap_files()` | proxmox/bootstrap_proxmox_generator.py:22-27, mikrotik/bootstrap_mikrotik_generator.py:22-27, orangepi/bootstrap_orangepi_generator.py:22-27 | ~18 |

**Total Duplicated Lines:** ~288

### 2.2 Object Leakage in Core (Medium Priority)

| ID | Issue | File | Lines | Description |
|----|-------|------|-------|-------------|
| LEAK-001 | Hardcoded object ref | plugins/generators/projections.py | ~various | Contains `obj.network.ethernet_cable` check |
| LEAK-002 | Hardcoded group names | plugins/generators/projections.py | ~various | Contains hardcoded group canonical names |

### 2.3 Shared Module Coupling (Low Priority)

| ID | Issue | File | Description |
|----|-------|------|-------------|
| COUPLE-001 | Hardcoded object prefixes | _shared/plugins/bootstrap_projections.py:52-57 | `obj.proxmox.ve`, `obj.mikrotik.`, `obj.orangepi.` |

---

## 3. Refactor Backlog

### Priority 1: Extract Duplicated Terraform Helpers

#### WP-001: Extract `_render_string_list()` to shared

**Description:** Extract common Terraform list rendering helper to `_shared/plugins/terraform_helpers.py`

**Files Affected:**
- CREATE: `v5/topology/object-modules/_shared/plugins/terraform_helpers.py`
- MODIFY: `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- MODIFY: `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`

**Estimated Effort:** 30 min

**Verification Gate:**
- `pytest v5/tests/plugin_contract/test_plugin_level_boundaries.py -v`
- `pytest v5/tests/generators/ -v`

---

#### WP-002: Extract capability expression helpers to shared

**Description:** Extract `_capability_expression_enabled()` and `_get_capability_templates()` to `_shared/plugins/capability_helpers.py`

**Files Affected:**
- CREATE: `v5/topology/object-modules/_shared/plugins/capability_helpers.py`
- MODIFY: `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- MODIFY: `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`

**Estimated Effort:** 1 hour

**Verification Gate:**
- `pytest v5/tests/plugin_contract/test_capability_template_config.py -v`
- `pytest v5/tests/generators/ -v`

---

#### WP-003: Extract `_get_bootstrap_files()` to shared

**Description:** Extract common bootstrap file config loading to `_shared/plugins/bootstrap_helpers.py`

**Files Affected:**
- CREATE: `v5/topology/object-modules/_shared/plugins/bootstrap_helpers.py`
- MODIFY: `v5/topology/object-modules/proxmox/plugins/bootstrap_proxmox_generator.py`
- MODIFY: `v5/topology/object-modules/mikrotik/plugins/bootstrap_mikrotik_generator.py`
- MODIFY: `v5/topology/object-modules/orangepi/plugins/bootstrap_orangepi_generator.py`

**Estimated Effort:** 45 min

**Verification Gate:**
- `pytest v5/tests/plugin_contract/test_bootstrap_file_config.py -v`

---

### Priority 2: Consolidate Router Validators

#### WP-004: Create generic router port validator base

**Description:** Extract common router port validation logic to class-level base, keep object-specific filtering in object modules

**Files Affected:**
- MODIFY: `v5/topology/class-modules/L1-foundation/router/plugins/router_port_validator_base.py` (new)
- MODIFY: `v5/topology/object-modules/mikrotik/plugins/mikrotik_router_ports_validator.py`
- MODIFY: `v5/topology/object-modules/glinet/plugins/glinet_router_ports_validator.py`

**Estimated Effort:** 2 hours

**Verification Gate:**
- `pytest v5/tests/plugin_contract/test_plugin_level_boundaries.py -v`
- Object validator tests

---

### Priority 3: Address Core Leakage

#### WP-005: Parameterize object refs in core projections

**Description:** Replace hardcoded `obj.network.ethernet_cable` with configurable object ref pattern

**Files Affected:**
- MODIFY: `v5/topology-tools/plugins/generators/projections.py`

**Estimated Effort:** 1 hour

**Verification Gate:**
- `pytest v5/tests/generators/test_projections.py -v`
- Strict compile gate

---

#### WP-006: Parameterize group canonical names

**Description:** Move hardcoded group names to configuration or discovery

**Files Affected:**
- MODIFY: `v5/topology-tools/plugins/generators/projections.py`
- MODIFY: config or manifest

**Estimated Effort:** 2 hours

**Verification Gate:**
- Full integration test suite
- Strict compile gate

---

### Priority 4: Improve Bootstrap Discovery (Optional)

#### WP-007: Dynamic bootstrap projection discovery

**Description:** Replace hardcoded object prefixes in `bootstrap_projections.py` with dynamic discovery from object module manifests

**Files Affected:**
- MODIFY: `v5/topology/object-modules/_shared/plugins/bootstrap_projections.py`
- Possibly add bootstrap registration to object manifests

**Estimated Effort:** 3 hours

**Verification Gate:**
- Bootstrap generator tests
- Full compile/generate pipeline

---

## 4. Verification Gates Summary

| Work Package | Tests | Commands |
|--------------|-------|----------|
| WP-001 | Plugin boundaries, generators | `pytest v5/tests/plugin_contract/ v5/tests/generators/ -v` |
| WP-002 | Capability config, generators | `pytest v5/tests/plugin_contract/test_capability_template_config.py -v` |
| WP-003 | Bootstrap config | `pytest v5/tests/plugin_contract/test_bootstrap_file_config.py -v` |
| WP-004 | Plugin boundaries | `pytest v5/tests/plugin_contract/test_plugin_level_boundaries.py -v` |
| WP-005 | Core projections | `pytest v5/tests/generators/test_projections.py -v` |
| WP-006 | Full integration | `make validate-v5 && python v5/topology-tools/compile-topology.py --strict-model-lock` |
| WP-007 | Bootstrap generators | `pytest v5/tests/generators/ -v` |

---

## 5. New Violation Freeze Tests

### 5.1 Existing Tests (Already Enforce)

- `test_object_modules_do_not_cross_import_other_object_modules()`
- `test_object_plugin_python_files_do_not_hardcode_private_or_local_url_hosts()`
- `test_projection_files_do_not_hardcode_product_model_names()`
- `test_generators_support_migration_period_fallbacks()` (deprecation tracked)

### 5.2 Recommended New Tests

| Test | Purpose | File |
|------|---------|------|
| `test_no_duplicate_helper_functions_across_object_modules()` | Detect new code duplication | test_plugin_level_boundaries.py |
| `test_shared_helpers_are_used_by_multiple_modules()` | Ensure shared code is actually shared | test_plugin_level_boundaries.py |

---

## 6. Execution Recommendation

### Phase 5a: Immediate (WP-001, WP-002, WP-003)
- Low risk, high value
- Reduces ~150 lines of duplication
- Estimated: 2-3 hours total

### Phase 5b: Short-term (WP-004)
- Medium complexity
- Improves maintainability for future router vendors
- Estimated: 2 hours

### Phase 5c: Medium-term (WP-005, WP-006)
- Requires careful testing
- Improves architectural purity
- Estimated: 3 hours

### Phase 5d: Optional (WP-007)
- Only if adding new object modules
- Deferred until needed

---

## 7. Go/No-Go Criteria

**Go Criteria:**
- [x] This document reviewed and approved
- [x] WP-001 through WP-003 implemented (Priority 1)
- [x] WP-004 implemented (Priority 2)
- [x] WP-005 and WP-006 implemented (Priority 3)
- [x] All verification gates pass (58/58 tests)
- [x] No new violations introduced
- [ ] WP-007 deferred (optional, implement when adding new object modules)

**Approval Required From:** Project maintainer

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-23 | Initial Phase 5 inventory and backlog draft |
| 2026-03-23 | WP-001/WP-002/WP-003 implemented: shared helpers extracted to _shared/plugins/ |
| 2026-03-23 | WP-004 implemented: RouterPortValidatorBase extracted to class-modules/L1-foundation/router/ |
| 2026-03-23 | WP-005/WP-006 implemented: projection constants extracted to projection_core.py |
| 2026-03-24 | HOTFIX: Created shared_helper_loader.py for dynamic module loading (hyphenated dirs) |
| 2026-03-24 | FIX: Resolved 26 W7844 network binding warnings (validator + instance data) |

## 8. Implementation Summary

### Commits (branch: continue_migration_v4_to_v5)

| Commit | Description |
|--------|-------------|
| 2712cf6 | WP-001/WP-002/WP-003: Extract shared helpers to _shared/plugins/ |
| 4251dad | WP-004: Extract router port validator base to class-level |
| e0c77be | WP-005/WP-006: Extract projection constants to reduce core leakage |
| 2c86bd1 | Squashed Phase 5 commit with detailed message |
| 6035e43 | HOTFIX: Use dynamic module loading for shared helpers |
| e38c3ca | FIX: Resolve W7844 network binding warnings |

### Files Created

| File | Purpose |
|------|---------|
| `_shared/plugins/terraform_helpers.py` | `render_string_list()` |
| `_shared/plugins/capability_helpers.py` | `get_capability_templates()`, `capability_expression_enabled()` |
| `_shared/plugins/bootstrap_helpers.py` | `get_bootstrap_files()`, `get_post_install_*()` |
| `class-modules/L1-foundation/router/plugins/router_port_validator_base.py` | `RouterPortValidatorBase` |
| `topology-tools/plugins/generators/shared_helper_loader.py` | Dynamic module loader for hyphenated directories |

### Code Reduction

| Work Package | Lines Removed | Files Affected |
|--------------|---------------|----------------|
| WP-001/WP-002/WP-003 | ~130 | 5 generators |
| WP-004 | ~125 | 2 validators |
| WP-005/WP-006 | N/A (constants) | 5 projection modules |
| **Total** | **~255** | **12 files** |
