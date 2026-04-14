# ADR 0097 Wave 2 Evidence

**Date**: 2026-04-14
**Status**: Complete
**Wave**: Validator Migration

---

## Summary

Wave 2 successfully migrated validators to subinterpreter execution support:

- **40 validators** marked as `subinterpreter_compatible: true`
- **8 validators** marked as `subinterpreter_compatible: false` (PyYAML dependency)

---

## Compatibility Audit

### Pure Python Validators (40) - Compatible

All `validator_json` plugins that use only:
- Standard library (json, pathlib, typing, collections, datetime, re, ipaddress)
- Internal modules (kernel.plugin_base, capability_derivation, field_annotations)
- jsonschema (pure Python)

```
base.validator.foundation_device_taxonomy
base.validator.references
base.validator.initialization_contract
base.validator.model_lock
base.validator.power_source_refs
base.validator.network_ip_overlap
base.validator.single_active_os
base.validator.network_reserved_ranges
base.validator.network_trust_zone_firewall_refs
base.validator.network_firewall_addressability
base.validator.runtime_target_os_binding
base.validator.network_ip_allocation_host_os_refs
base.validator.network_vlan_zone_consistency
base.validator.network_core_refs
base.validator.network_vlan_tags
base.validator.network_mtu_consistency
base.validator.service_runtime_refs
base.validator.network_runtime_reachability
base.validator.service_dependency_refs
base.validator.storage_device_taxonomy
base.validator.storage_media_inventory
base.validator.dns_refs
base.validator.certificate_refs
base.validator.backup_refs
base.validator.security_policy_refs
base.validator.vm_refs
base.validator.lxc_refs
base.validator.host_os_refs
base.validator.host_ref_dag
base.validator.docker_refs
base.validator.hypervisor_execution_model
base.validator.vm_hypervisor_compat
base.validator.volume_format_compat
base.validator.nested_topology_scope
base.validator.storage_l3_refs
base.validator.embedded_in
base.validator.ethernet_port_inventory
base.validator.router_ports
base.validator.capability_contract
base.validator.generator_migration_status
```

### PyYAML Validators (8) - NOT Compatible

Validators using PyYAML (C extension) or `validator_yaml` kind:

| Plugin ID | Kind | Reason |
|-----------|------|--------|
| `base.validator.governance_contract` | validator_yaml | Uses YAML source parsing |
| `base.validator.foundation_layout` | validator_yaml | Uses YAML source parsing |
| `base.validator.foundation_include_contract` | validator_yaml | Imports yaml directly |
| `base.validator.foundation_file_placement` | validator_yaml | Imports yaml directly |
| `base.validator.generator_rollback_escalation` | validator_json | Imports yaml (policy file) |
| `base.validator.generator_sunset` | validator_json | Imports yaml (policy file) |
| `base.validator.instance_placeholders` | validator_json | Imports yaml (format registry) |
| `base.validator.soho_product_profile` | validator_json | Imports yaml (policy file) |

---

## Test Results

### ADR 0097 Parity Tests

```
tests/test_adr0097_parity.py::TestSerializablePluginContext::test_roundtrip_serialization PASSED
tests/test_adr0097_parity.py::TestSerializablePluginContext::test_serialization_with_minimal_context PASSED
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_subinterpreters_disabled PASSED
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_all_compatible SKIPPED (Python 3.14 required)
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_mixed_compatibility PASSED
tests/test_adr0097_parity.py::TestPluginManifestSchema::test_manifest_parsing_compatible_true PASSED
tests/test_adr0097_parity.py::TestPluginManifestSchema::test_manifest_parsing_default_value PASSED

6 passed, 1 skipped
```

### Validation Pipeline

```
Compile summary: total=91 errors=0 warnings=0 infos=91
v5 layer contract: PASS
v5 scaffold validation: PASS
Capability contract check: OK
ADR0088 governance: PASS
```

---

## Changes Made

### Files Modified

1. `topology-tools/plugins/plugins.yaml`
   - Added `subinterpreter_compatible: true` to 40 validators
   - Added `subinterpreter_compatible: false` to 8 validators

2. `projects/home-lab/framework.lock.yaml`
   - Regenerated integrity hash after manifest changes

3. `adr/0097-analysis/WAVE-2-PLAN.md`
   - Created implementation plan

---

## Exit Criteria Verification

| Criterion | Status |
|-----------|--------|
| 40 validators marked `subinterpreter_compatible: true` | ✅ |
| 8 PyYAML validators marked `subinterpreter_compatible: false` | ✅ |
| Parity tests pass | ✅ (6/7, 1 skipped - needs Python 3.14) |
| No regressions in validation pipeline | ✅ |
| Documentation updated | ✅ |

---

## Next Steps

**Wave 3: Generator Migration**

1. Audit generator dependencies (Jinja2, YAML)
2. Mark compatible generators with `subinterpreter_compatible: true`
3. Enable for generate stage
4. Benchmark file I/O parallelism improvement

**Gate**: Generators produce identical output; I/O parallelism measurable.

---

**Evidence collected by**: Claude Code
**Verification date**: 2026-04-14
