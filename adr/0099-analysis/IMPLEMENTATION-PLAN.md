# ADR 0099 Implementation Plan

**Created:** 2026-04-21
**Estimated Effort:** 15-24 hours
**Risk Level:** LOW

## Overview

This plan migrates the test architecture from legacy direct execution to ADR 0097/0099 compliant envelope-based execution, with focus on legacy code removal.

## Phase 1: Dead Code Removal (1-2 hours)

### Task 1.1: Delete SerializablePluginContext

**File:** `topology-tools/kernel/plugin_base.py`
**Action:** Delete class definition (~144 lines starting at line 977)
**Verification:** `grep -r "SerializablePluginContext" topology-tools/` returns 0

### Task 1.2: Refactor test_adr0097_parity.py

**File:** `tests/test_adr0097_parity.py`
**Actions:**
1. Delete `TestSerializablePluginContext` class (~150 lines)
2. Keep `TestExecutorSelection`, `TestNoOpLock`, `TestEventPlane`
3. Rename file to `test_adr0097_execution_model.py`

### Task 1.3: Fix REGISTER.md

**File:** `adr/REGISTER.md`
**Change:** ADR 0097 status from "Proposed" to "Implemented"

### Task 1.4: Clean up dead code references

**Files:**
- `tests/runtime/scheduler/test_no_merge_back_primary_path.py`
- `tests/runtime/scheduler/test_execution_mode_routing.py`

**Action:** Update docstrings referencing deleted code

### Gate 1: Phase 1 Complete
- [ ] Zero SerializablePluginContext references
- [ ] test_adr0097_parity.py refactored
- [ ] ADR 0097 status updated
- [ ] All tests pass

---

## Phase 2: Structure Alignment (2-4 hours)

### Task 2.1: Create Test Directory Structure

```bash
mkdir -p tests/plugins/unit
mkdir -p tests/runtime/parity
```

Create `tests/plugins/unit/README.md`:
```markdown
# Plugin Unit Tests

Tests for individual plugins following ADR 0099 envelope semantics.

## Pattern
- Use `run_plugin_isolated()` for full envelope execution
- Use `run_plugin_for_test()` for migration compatibility
- Verify envelope output, not context mutation
```

### Task 2.2: Create Test Execution Helper

**File:** `tests/helpers/__init__.py`
**File:** `tests/helpers/plugin_execution.py`

```python
"""Plugin execution helpers for envelope-based testing (ADR 0097/0099)."""

def run_plugin_for_test(plugin, ctx, stage, *, consumes_keys=None):
    """Execute plugin with proper context setup (migration helper)."""
    keys = consumes_keys if consumes_keys is not None else set()
    ctx._set_execution_context(plugin.plugin_id, keys)
    try:
        return plugin.execute(ctx, stage)
    finally:
        ctx._clear_execution_context()

def run_plugin_isolated(plugin, ctx, stage):
    """Execute plugin with full envelope isolation (target pattern)."""
    # Build snapshot, execute, return envelope
    ...
```

### Task 2.3: Create CI Legacy Guard

**File:** `.github/workflows/test-legacy-guard.yml`
- Check legacy pattern count against baseline
- Block PRs that increase count
- Check for SerializablePluginContext

**File:** `.github/legacy-baseline.txt`
- Initial value: 372

### Gate 2: Phase 2 Complete
- [ ] Directory structure exists
- [ ] Helper module created
- [ ] CI guard active
- [ ] All tests pass

---

## Phase 3: Test Migration (8-12 hours)

### Wave 1: Simple Validators (30 files, 4-6 hours)

**Criteria:** Validators without publish/consume dependencies

**Migration pattern:**
```python
# BEFORE
ctx._set_execution_context(validator.plugin_id, set())
result = validator.execute(ctx, Stage.VALIDATE)
ctx._clear_execution_context()

# AFTER
from tests.helpers.plugin_execution import run_plugin_for_test
result = run_plugin_for_test(validator, ctx, Stage.VALIDATE)
```

**Files:** See Appendix A

**Gate:** Update baseline to ~312, all tests pass

### Wave 2: Complex Validators (20 files, 3-4 hours)

**Criteria:** Validators with publish/consume dependencies
**Files:** See Appendix A
**Gate:** Update baseline to ~252, all tests pass

### Wave 3: Generators (10 files, 2-3 hours)

**Criteria:** Generator plugins with file output
**Files:** See Appendix A
**Gate:** Update baseline to ~192, all tests pass

### Wave 4: Compilers and Special Cases (6+ files, 2-3 hours)

**Criteria:** Compilers, assemblers, special cases
**Files:** See Appendix A
**Gate:** Update baseline to ~0, all tests pass

---

## Phase 4: Final Cleanup (2-4 hours)

### Task 4.1: Delete Legacy Methods

**File:** `topology-tools/kernel/plugin_base.py`
- Delete `_set_execution_context` method
- Delete `_clear_execution_context` method
- Update helper to use internal attributes directly

### Task 4.2: Resolve Skipped Tests

**Files:**
- `tests/runtime/scheduler/test_no_merge_back_primary_path.py`
- `tests/runtime/scheduler/test_execution_mode_routing.py`
- `tests/runtime/scheduler/test_worker_failure_isolation.py`

**Action:** Implement or remove 15 skipped tests

### Task 4.3: Update ADR Status

- ADR 0099: Status → Implemented
- REGISTER.md: Add ADR 0099 entry

### Task 4.4: Create Compliance Script

**File:** `scripts/validation/verify_adr0099_compliance.py`

### Gate 4: Implementation Complete
- [ ] Zero `_set_execution_context` outside helper
- [ ] Zero skipped tests in runtime/scheduler
- [ ] ADR 0099 marked Implemented
- [ ] Compliance script passes

---

## Appendix A: File Lists by Wave

### Wave 1: Simple Validators (30 files)
```
tests/plugin_integration/test_reference_validator.py
tests/plugin_integration/test_host_os_refs_validator.py
tests/plugin_integration/test_host_ref_dag_validator.py
tests/plugin_integration/test_vm_refs_validator.py
tests/plugin_integration/test_lxc_refs_validator.py
tests/plugin_integration/test_docker_refs_validator.py
tests/plugin_integration/test_dns_refs_validator.py
tests/plugin_integration/test_certificate_refs_validator.py
tests/plugin_integration/test_backup_refs_validator.py
tests/plugin_integration/test_network_core_refs_validator.py
tests/plugin_integration/test_network_ip_overlap_validator.py
tests/plugin_integration/test_network_mtu_consistency_validator.py
tests/plugin_integration/test_network_vlan_tags_validator.py
tests/plugin_integration/test_network_reserved_ranges_validator.py
tests/plugin_integration/test_security_policy_refs_validator.py
tests/plugin_integration/test_service_runtime_refs_validator.py
tests/plugin_integration/test_service_dependency_refs_validator.py
tests/plugin_integration/test_storage_device_taxonomy_validator.py
tests/plugin_integration/test_storage_l3_refs_validator.py
tests/plugin_integration/test_storage_media_inventory_validator.py
tests/plugin_integration/test_single_active_os_validator.py
tests/plugin_integration/test_embedded_in_validator.py
tests/plugin_integration/test_model_lock_validator.py
tests/plugin_integration/test_foundation_device_taxonomy_validator.py
tests/plugin_integration/test_l1_power_source_refs.py
tests/plugin_integration/test_network_firewall_addressability_validator.py
tests/plugin_integration/test_network_ip_allocation_host_os_refs_validator.py
tests/plugin_integration/test_network_runtime_reachability_validator.py
tests/plugin_integration/test_network_trust_zone_firewall_refs_validator.py
tests/plugin_integration/test_network_vlan_zone_consistency_validator.py
```

### Wave 2: Complex Validators (20 files)
```
tests/plugin_integration/test_capability_contract_validator.py
tests/plugin_integration/test_governance_contract_validator.py
tests/plugin_integration/test_hypervisor_execution_model_validator.py
tests/plugin_integration/test_vm_hypervisor_compat_validator.py
tests/plugin_integration/test_volume_format_compat_validator.py
tests/plugin_integration/test_runtime_target_os_binding_validator.py
tests/plugin_integration/test_generator_migration_status_validator.py
tests/plugin_integration/test_generator_sunset_validator.py
tests/plugin_integration/test_generator_rollback_escalation_validator.py
tests/plugin_integration/test_generator_projection_contract.py
tests/plugin_integration/test_generator_template_and_publish_contract.py
tests/plugin_integration/test_soho_product_profile_validator.py
tests/plugin_integration/test_nested_topology_scope_validator.py
tests/plugin_integration/test_initialization_contract_validator.py
tests/plugin_integration/test_foundation_include_contract_validator.py
tests/plugin_integration/test_declarative_reference_validator.py
tests/plugin_integration/test_declarative_reference_validator_parity.py
tests/plugin_integration/test_contract_warning_free.py
tests/plugin_integration/test_parity_stage_order.py
tests/plugin_integration/test_execution.py
```

### Wave 3: Generators (10 files)
```
tests/plugin_integration/test_terraform_proxmox_generator.py
tests/plugin_integration/test_terraform_mikrotik_generator.py
tests/plugin_integration/test_ansible_inventory_generator.py
tests/plugin_integration/test_docker_compose_generator.py
tests/plugin_integration/test_bootstrap_generators.py
tests/plugin_integration/test_diagram_generator.py
tests/plugin_integration/test_artifact_manifest_generator.py
tests/plugin_integration/test_tuc0002_new_terraform_generator.py
tests/plugin_integration/test_generator_readiness_evidence_builder.py
tests/plugin_integration/test_readiness_reports_builder.py
```

### Wave 4: Compilers and Special (10+ files)
```
tests/plugin_integration/test_instance_rows_compiler.py
tests/plugin_integration/test_effective_model_compiler.py
tests/plugin_integration/test_soho_profile_resolver_compiler.py
tests/plugin_integration/test_capability_contract_loader_compiler.py
tests/plugin_integration/test_artifact_contract_assembler.py
tests/plugin_integration/test_assemble_build_plugins.py
tests/plugin_integration/test_soho_readiness_builder.py
tests/plugin_integration/test_module_manifest_discovery.py
tests/test_plugin_registry.py
tests/plugin_api/test_dataclasses.py
```

---

## Appendix B: Rollback Procedures

| Phase | Rollback Command |
|-------|------------------|
| Phase 1 | `git revert <phase1-commit>` |
| Phase 2 | `rm -rf tests/helpers tests/plugins/unit tests/runtime/parity` |
| Phase 3 Wave N | `git revert <waveN-commit>` |
| Phase 4 | `git revert <phase4-commit>` |

All rollbacks are safe with zero data loss risk.
