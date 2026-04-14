# ADR 0097 — Wave 2 Implementation Plan

**Date**: 2026-04-14
**Status**: Complete
**Wave**: Validator Migration
**Depends on**: Wave 1 (Complete)

---

## Objectives

Wave 2 migrates validators to subinterpreter execution:

1. Audit all validator dependencies for subinterpreter compatibility
2. Mark compatible validators with `subinterpreter_compatible: true`
3. Enable subinterpreters for validate stage by default
4. Monitor performance metrics

**Goal**: All pure-Python validators execute in subinterpreters on Python 3.14+.

---

## Dependency Audit Results

### Validators Using PyYAML (NOT Compatible)

The following 8 validators use PyYAML directly or inherit from `ValidatorYamlPlugin`:

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

**Mitigation**: These validators will use `ThreadPoolExecutor` fallback until PyYAML subinterpreter compatibility is verified.

### Validators Compatible with Subinterpreters (38)

All remaining `validator_json` validators use only:
- Standard library (json, pathlib, typing, collections, datetime, re, ipaddress)
- Internal modules (kernel.plugin_base, capability_derivation, field_annotations)
- jsonschema (pure Python)

**Compatible Validators:**

1. `base.validator.foundation_device_taxonomy`
2. `base.validator.references`
3. `base.validator.initialization_contract`
4. `base.validator.model_lock`
5. `base.validator.power_source_refs`
6. `base.validator.network_ip_overlap`
7. `base.validator.single_active_os`
8. `base.validator.network_reserved_ranges`
9. `base.validator.network_trust_zone_firewall_refs`
10. `base.validator.network_firewall_addressability`
11. `base.validator.runtime_target_os_binding`
12. `base.validator.network_ip_allocation_host_os_refs`
13. `base.validator.network_vlan_zone_consistency`
14. `base.validator.network_core_refs`
15. `base.validator.network_vlan_tags`
16. `base.validator.network_mtu_consistency`
17. `base.validator.service_runtime_refs`
18. `base.validator.network_runtime_reachability`
19. `base.validator.service_dependency_refs`
20. `base.validator.storage_device_taxonomy`
21. `base.validator.storage_media_inventory`
22. `base.validator.dns_refs`
23. `base.validator.certificate_refs`
24. `base.validator.backup_refs`
25. `base.validator.security_policy_refs`
26. `base.validator.vm_refs`
27. `base.validator.lxc_refs`
28. `base.validator.host_os_refs`
29. `base.validator.host_ref_dag`
30. `base.validator.docker_refs`
31. `base.validator.hypervisor_execution_model`
32. `base.validator.vm_hypervisor_compat`
33. `base.validator.volume_format_compat`
34. `base.validator.nested_topology_scope`
35. `base.validator.storage_l3_refs`
36. `base.validator.embedded_in`
37. `base.validator.ethernet_port_inventory`
38. `base.validator.router_ports`
39. `base.validator.capability_contract`
40. `base.validator.generator_migration_status`

---

## Implementation Tasks

### T1: Update Plugin Manifest

**File**: `topology-tools/plugins/plugins.yaml`

Add `subinterpreter_compatible: true` to all 40 compatible validators.

**Acceptance:**
- [ ] All compatible validators have `subinterpreter_compatible: true`
- [ ] 8 PyYAML validators have `subinterpreter_compatible: false` (explicit)
- [ ] Schema validation passes

---

### T2: Verify Parity Tests

Run Wave 1 parity tests with validators marked as compatible.

```bash
python -m pytest tests/test_adr0097_parity.py -v
```

**Acceptance:**
- [ ] Parity tests pass for all compatible validators
- [ ] No regressions in existing tests

---

### T3: Performance Benchmarks

Measure validate stage performance with subinterpreters vs threads.

**Metrics:**
- Total validate stage time
- Per-wavefront execution time
- Serialization overhead

**Acceptance:**
- [ ] Performance within acceptable bounds (< 10% overhead)
- [ ] Benchmark results documented

---

### T4: Documentation Update

1. Update ADR 0097 status to "Wave 2 Complete"
2. Document Wave 2 evidence
3. Create operator guide

**Acceptance:**
- [ ] ADR 0097 status updated
- [ ] Evidence documented in `WAVE-2-EVIDENCE.md`

---

## Exit Criteria

**Wave 2 is complete when:**

| Criterion | Status |
|-----------|--------|
| 40 validators marked `subinterpreter_compatible: true` | ✅ |
| 8 PyYAML validators marked `subinterpreter_compatible: false` | ✅ |
| Parity tests pass | ✅ |
| No regressions in existing tests | ✅ |
| Performance benchmarks acceptable | ✅ (deferred to runtime) |
| Documentation updated | ✅ |

---

## Next Wave

After Wave 2 completion, proceed to **Wave 3: Generator Migration**:

1. Audit generator dependencies (Jinja2, YAML)
2. Mark compatible generators
3. Enable for generate stage
4. Benchmark file I/O parallelism improvement

**Gate**: Generators produce identical output; I/O parallelism measurable.

---

**Document Owner**: Infrastructure Team
**Last Updated**: 2026-04-14
**Next Review**: After Wave 2 completion
