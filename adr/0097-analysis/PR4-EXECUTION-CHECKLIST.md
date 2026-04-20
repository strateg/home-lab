# ADR 0097 PR4+ Execution Checklist — Fleet Migration & Legacy Cleanup

Date: 2026-04-20
Status: **IN PROGRESS**
Purpose: Migrate remaining plugins to subinterpreter mode and clean up legacy code.

## PR4 Objective

1. Analyze and migrate plugins currently using `main_interpreter` to `subinterpreter` where possible
2. Remove deprecated `subinterpreter_compatible` field from manifests
3. Clean up legacy runtime code no longer needed after migration

---

## A. Current Fleet Status

### A1. Plugin execution mode distribution (updated 2026-04-20)

| Mode | Count | Status |
|------|-------|--------|
| `subinterpreter` | 67 | Ready for parallel execution |
| `main_interpreter` | 22 | Remaining (assemblers, builders, discoverers, compilers) |
| `thread_legacy` | 0 | Not used |

**Migrated in PR4:**
- `base.generator.effective_yaml` (57 → 58)
- `base.generator.docker_compose` (58 → 59)
- 8 validators (59 → 67):
  - `base.validator.foundation_file_placement`
  - `base.validator.foundation_include_contract`
  - `base.validator.foundation_layout`
  - `base.validator.generator_rollback_escalation`
  - `base.validator.generator_sunset`
  - `base.validator.governance_contract`
  - `base.validator.instance_placeholders`
  - `base.validator.soho_product_profile`

### A2. Breakdown of `main_interpreter` plugins

| Category | Count | Notes |
|----------|-------|-------|
| `subinterpreter_compatible: false` | 10 | Explicitly marked incompatible |
| No specification (default) | 22 | Uses default main_interpreter |

---

## B. Plugins Marked `subinterpreter_compatible: false`

These 10 plugins were explicitly marked as not compatible with subinterpreters.

### B1. Validators (7 plugins)

| Plugin ID | Reason for Incompatibility | Can Migrate? |
|-----------|---------------------------|--------------|
| `base.validator.foundation_file_placement` | File system validation | TBD |
| `base.validator.foundation_include_contract` | File include resolution | TBD |
| `base.validator.foundation_layout` | Directory structure validation | TBD |
| `base.validator.generator_rollback_escalation` | Generator state inspection | TBD |
| `base.validator.generator_sunset` | Generator state inspection | TBD |
| `base.validator.governance_contract` | Complex contract validation | TBD |
| `base.validator.instance_placeholders` | Field format validation | TBD |
| `base.validator.soho_product_profile` | Profile validation | TBD |

### B2. Generators (2 plugins)

| Plugin ID | Reason for Incompatibility | Can Migrate? |
|-----------|---------------------------|--------------|
| `base.generator.docker_compose` | File I/O, template rendering | YES (file I/O works in subinterpreters) |
| `base.generator.effective_yaml` | File I/O | YES (file I/O works in subinterpreters) |

---

## C. Plugins Using Default `main_interpreter`

These 22 plugins have no `subinterpreter_compatible` field and use default `main_interpreter`.

### C1. Assemblers (6 plugins)

| Plugin ID | Stage | Notes |
|-----------|-------|-------|
| `base.assembler.artifact_contract_guard` | assemble | Contract validation |
| `base.assembler.changed_scopes` | assemble | Scope tracking |
| `base.assembler.deploy_bundle` | assemble | Bundle creation |
| `base.assembler.manifest` | assemble | Manifest generation |
| `base.assembler.verify` | assemble | Verification |
| `base.assembler.workspace` | assemble | Workspace setup |

### C2. Builders (6 plugins)

| Plugin ID | Stage | Notes |
|-----------|-------|-------|
| `base.builder.artifact_family_summary` | build | Summary generation |
| `base.builder.bundle` | build | Bundle packaging |
| `base.builder.generator_readiness_evidence` | build | Evidence collection |
| `base.builder.readiness_reports` | build | Report generation |
| `base.builder.release_manifest` | build | Release manifest |
| `base.builder.sbom` | build | SBOM generation |
| `base.builder.soho_readiness_package` | build | Package creation |

### C3. Compilers (5 plugins)

| Plugin ID | Stage | Notes |
|-----------|-------|-------|
| `base.compiler.annotation_resolver` | compile | Annotation resolution |
| `base.compiler.capabilities` | compile | Capability derivation |
| `base.compiler.capability_contract_loader` | compile | Contract loading |
| `base.compiler.model_lock_loader` | compile | Lock file loading |
| `base.compiler.soho_profile_resolver` | compile | Profile resolution |

### C4. Discoverers (4 plugins)

| Plugin ID | Stage | Notes |
|-----------|-------|-------|
| `base.discover.boundary` | discover | Boundary detection |
| `base.discover.capability_preflight` | discover | Preflight checks |
| `base.discover.inventory` | discover | Inventory loading |
| `base.discover.manifest_loader` | discover | Manifest loading |

---

## D. Migration Analysis Criteria

### D1. Criteria for `subinterpreter` compatibility

A plugin can run in `subinterpreter` mode if:
- [ ] Does not access global mutable state
- [ ] Does not use non-serializable objects across interpreter boundary
- [ ] File I/O is acceptable (works in Python 3.14 subinterpreters)
- [ ] Template rendering is acceptable (Jinja2 works in subinterpreters)
- [ ] Does not spawn threads or processes internally

### D2. Criteria for staying in `main_interpreter` mode

A plugin should stay in `main_interpreter` mode if:
- Requires access to main interpreter global state
- Uses C extensions that don't support subinterpreters
- Needs to coordinate with other plugins during execution

---

## E. Phase 1: Quick Wins — Generators

### E1. Migrate `base.generator.effective_yaml` — COMPLETE

File: `topology-tools/plugins/generators/effective_yaml_generator.py`

Analysis:
- Reads `ctx.compiled_json` (snapshot input)
- Writes YAML file to disk (file I/O works)
- Publishes `generated_files`, `effective_yaml_path`
- No global state access

Decision: **MIGRATED** to `subinterpreter`

- [x] Update manifest: `execution_mode: subinterpreter`
- [x] Test in parallel execution
- [x] Verify output matches baseline (427KB effective-topology.yaml generated)

### E2. Migrate `base.generator.docker_compose` — COMPLETE

File: `topology-tools/plugins/generators/docker_compose_generator.py`

Analysis:
- Uses `BaseGenerator.write_text_atomic()` (standard file I/O)
- Reads `ctx.compiled_json` or subscribes to `normalized_rows`
- No global state access, uses yaml.dump()

Decision: **MIGRATED** to `subinterpreter`

- [x] Analyze plugin code
- [x] Check for subinterpreter compatibility (uses standard file I/O, yaml library)
- [x] Update manifest: `execution_mode: subinterpreter`
- [x] Test migration (compile successful, all tests pass)

---

## F. Phase 2: Validators — COMPLETE

### F1. All validators migrated to subinterpreter mode

Analysis showed all 8 validators are compatible:
- Only file system reads (no writes)
- Use ctx.config, ctx.raw_yaml, ctx.objects (snapshot inputs)
- Use ctx.publish() for outputs (envelope outbox)
- No global state mutation

All migrated:
1. [x] `base.validator.foundation_file_placement` — file system reads only
2. [x] `base.validator.foundation_include_contract` — directory checks only
3. [x] `base.validator.foundation_layout` — path validation only
4. [x] `base.validator.generator_rollback_escalation` — policy file reads only
5. [x] `base.validator.generator_sunset` — policy file reads only
6. [x] `base.validator.governance_contract` — raw_yaml validation only
7. [x] `base.validator.instance_placeholders` — format registry reads only
8. [x] `base.validator.soho_product_profile` — manifest validation only

---

## G. Phase 3: Assemblers & Builders

These plugins run in later stages and may have specific requirements.

### G1. Assembler analysis

- [ ] Review assembler stage requirements
- [ ] Determine if subinterpreter isolation is beneficial
- [ ] Note: assemblers often coordinate outputs, may benefit from main_interpreter

### G2. Builder analysis

- [ ] Review builder stage requirements
- [ ] Determine if subinterpreter isolation is beneficial
- [ ] Note: builders package artifacts, file I/O intensive

---

## H. Legacy Cleanup Tasks

### H1. Deprecate `subinterpreter_compatible` field

- [ ] Add deprecation warning when field is present without `execution_mode`
- [ ] Update schema to mark field as deprecated
- [ ] Create migration script to convert `subinterpreter_compatible` to `execution_mode`
- [ ] Remove field from all manifests (after migration verified)

### H2. Clean up legacy code paths

- [ ] Remove `_mirror_context_into_pipeline_state()` calls for non-legacy plugins
- [ ] Remove `SerializablePluginContext` usage in primary path
- [ ] Consolidate envelope path as the only execution model

### H3. Update documentation

- [ ] Update plugin development guide for envelope model
- [ ] Document `execution_mode` field usage
- [ ] Remove references to deprecated `subinterpreter_compatible`

---

## I. Validation Commands

### Per-plugin migration

```bash
# Test specific plugin in subinterpreter mode
V5_SECRETS_MODE=passthrough .venv/bin/python topology-tools/compile-topology.py --plugin-filter <plugin_id> -v
```

### Full validation

```bash
# Run all tests
pytest tests/ -v

# Full compile
V5_SECRETS_MODE=passthrough .venv/bin/python topology-tools/compile-topology.py

# Compare outputs
diff -r generated/home-lab build/baseline/generated/
```

---

## J. Definition of Done

PR4+ is complete when:

- [ ] All compatible plugins migrated to `subinterpreter` mode
- [ ] Plugins requiring `main_interpreter` are documented with reasons
- [ ] `subinterpreter_compatible` field removed from all manifests
- [ ] Legacy runtime code paths marked for removal or removed
- [ ] Documentation updated
- [ ] All tests pass
- [ ] Generated outputs match baseline

---

## K. Risk Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Plugin breaks in subinterpreter | MEDIUM | Test each migration individually |
| Performance regression | LOW | Benchmark parallel execution |
| State isolation issues | MEDIUM | Verify envelope commit works |

### Rollback Plan

For each plugin migration:
1. Revert `execution_mode` to `main_interpreter`
2. Keep plugin code unchanged
3. Investigate failure
4. Fix and retry

---

**PR4 Status: IN PROGRESS** — Fleet analysis complete, starting quick wins migration.

