# Plugin Execution Modes

**Date:** 2026-04-22
**Source:** ADR 0097 PR4+ Final Status
**Purpose:** Document rationale for plugin execution mode assignments

---

## Overview

The plugin runtime supports three execution modes per ADR 0097:

| Mode | Usage | Count | Percentage |
|------|-------|-------|------------|
| `subinterpreter` | Isolated parallel execution (default) | 74 | 88.1% |
| `main_interpreter` | Main interpreter execution (restricted) | 10 | 11.9% |
| `thread_legacy` | Deprecated migration mode | 0 | 0% |

**Total active plugins:** 84

---

## main_interpreter Plugins (10)

These plugins **require** main interpreter execution due to technical constraints that prevent subinterpreter isolation:

### Discoverers (1)

#### base.discover.manifest_loader
**Reason:** Mutates `ctx.config` field and uses callable objects
- Loads plugin manifests during bootstrap
- Populates shared runtime configuration
- Cannot be isolated without refactoring config ownership

### Compilers (1)

#### base.compiler.model_lock_loader
**Reason:** Mutates `ctx.model_lock` field
- Loads and validates framework lock file
- Populates pipeline-global lock state
- Lock state is consumed by multiple downstream plugins

### Assemblers (5)

#### base.assembler.changed_scopes
**Reason:** Mutates `ctx.changed_input_scopes` and `ctx.config`
- Detects changes between compilation runs
- Writes incremental build metadata to shared state

#### base.assembler.workspace
**Reason:** Mutates `ctx.workspace_root` field
- Establishes workspace directory structure
- Sets global workspace paths for other plugins

#### base.assembler.manifest
**Reason:** Mutates `ctx.assembly_manifest` field
- Builds final assembly manifest
- Aggregates outputs from all generators

#### base.assembler.deploy_bundle
**Reason:** Dynamic module loading via `importlib.util`
- Loads deploy runner modules dynamically
- Subinterpreters restrict dynamic imports

#### base.assembler.artifact_contract_guard
**Reason:** Accesses `ctx.config.get("plugin_registry")`
- Validates artifact contracts against plugin registry
- Requires direct registry access

### Builders (3)

#### base.builder.bundle
**Reason:** Mutates `ctx.dist_root` field
- Prepares distribution bundle structure
- Sets global distribution paths

#### base.builder.sbom
**Reason:** Mutates `ctx.sbom_output_dir` field
- Generates Software Bill of Materials
- Writes SBOM metadata to shared location

#### base.builder.artifact_family_summary
**Reason:** Accesses `ctx.config.get("plugin_registry")`
- Generates artifact family summary
- Requires direct registry access for metadata

---

## Common Incompatibility Patterns

| Pattern | Count | Examples |
|---------|-------|----------|
| Direct `ctx` field mutation | 7 | `ctx.model_lock`, `ctx.workspace_root`, `ctx.dist_root` |
| Plugin registry access | 2 | `ctx.config.get("plugin_registry")` |
| Dynamic module loading | 1 | `importlib.util` |

---

## Migration Criteria

A plugin **can** be migrated to `subinterpreter` mode if:

1. ✅ Only reads from input snapshot
2. ✅ Only writes via `publish()` to local outbox
3. ✅ Does not mutate `ctx` fields directly
4. ✅ Does not access plugin registry
5. ✅ Does not use dynamic imports

A plugin **must** remain in `main_interpreter` mode if:

1. ❌ Mutates pipeline-global `ctx` fields
2. ❌ Requires direct plugin registry access
3. ❌ Uses dynamic module loading (`importlib.util`)
4. ❌ Coordinates pipeline-level orchestration concerns

---

## Future Improvements

Potential architectural changes to reduce main_interpreter dependency:

1. **Config ownership refactor:** Move `ctx.config` mutation to pipeline-owned builder
2. **Registry access abstraction:** Provide registry data via snapshot instead of direct access
3. **Workspace initialization:** Move workspace setup to pre-plugin orchestration phase
4. **Dynamic loading elimination:** Pre-load all required modules during manifest discovery

**Note:** These are design considerations, not immediate action items.

---

## References

- ADR 0097: Actor-Style Dataflow Execution
- ADR 0097 PR4+ Final Status: `adr/0097-analysis/PR4-FINAL-STATUS.md`
- Plugin manifest: `topology-tools/plugins/plugins.yaml`
- Envelope model guide: `docs/guides/PLUGIN-ENVELOPE-MODEL.md`

---

## Metadata

```yaml
execution_mode_distribution:
  subinterpreter: 74
  main_interpreter: 10
  thread_legacy: 0
  total: 84

migration_status:
  fleet_coverage: 88.1%
  incompatible_documented: yes
  pr4_complete: yes
  pr5_documentation: yes
```
