# Instance Rows Bottleneck Analysis

**Date:** 2026-05-31
**Status:** Documented
**Related ADRs:** ADR 0063 (Plugin Microkernel), ADR 0069 (Instance Compilation), ADR 0072 (Secrets)

---

## Summary

`base.compiler.instance_rows` is an **intentional architectural bottleneck** in the plugin dependency graph. With 37+ direct dependents and 89 total references, it represents a deliberate data funnel pattern that normalizes all instance data before downstream processing.

## Architecture

### Compiler Chain

```
base.compiler.annotation_resolver
         ↓
base.compiler.instance_rows_secret_resolve
         ↓
base.compiler.instance_rows_resolve
         ↓
base.compiler.instance_rows_prepare
         ↓
base.compiler.instance_rows_validate
         ↓
base.compiler.instance_rows  ← BOTTLENECK (37+ dependents)
         ↓
    ┌────┴────┬────────┬────────┬────────┐
    ↓         ↓        ↓        ↓        ↓
validators  generators  assemblers  builders  ...
```

### Why This Is Intentional

1. **Single Source of Truth**: All downstream plugins consume normalized, validated instance data from one source. This prevents divergent interpretations of raw topology data.

2. **Validation Guarantee**: By the time `instance_rows` publishes, all data has been:
   - Secret-resolved (SOPS decryption)
   - Reference-resolved (object/class inheritance)
   - Prepared (field normalization)
   - Validated (schema compliance)

3. **Parallelization Boundary**: Validators can run in parallel because they all depend on the same completed data set. The bottleneck enables fan-out parallelism.

4. **Debuggability**: All instance data flows through one checkpoint, making it easy to inspect state and diagnose issues.

## Dependents by Category

| Category | Count | Examples |
|----------|-------|----------|
| JSON Validators | 37 | `reference_validator`, `network_*_validator`, `vm_refs_validator` |
| Generators | 4 | `docker_compose_generator`, `effective_model_compiler` |
| Other Compilers | 3 | `capability_derivation`, `layer_derivation` |

## Produced Data Contract

```yaml
produces:
  - key: instance_rows
    scope: pipeline_shared
    schema:
      type: object
      properties:
        devices: { type: array }
        lxc: { type: array }
        vms: { type: array }
        services: { type: array }
        network: { type: array }
        storage: { type: array }
        # ... other instance groups
```

## Performance Considerations

- **Serialization Point**: All 37+ validators must wait for instance_rows to complete
- **Memory Footprint**: Full instance data held in memory during compile stage
- **Mitigation**: Subinterpreter parallelism for validators after this point

## Alternatives Considered

### 1. Per-Group Compilers
**Rejected**: Would require validators to depend on multiple sources, increasing complexity and risk of inconsistent data.

### 2. Streaming/Incremental
**Future Consideration**: Event plane (ADR 0097) could enable streaming, but current batch model is simpler and sufficient for home-lab scale.

### 3. Checkpoint Plugins
**Planned (Phase 6)**: Breaking the chain with checkpoint plugins could reduce depth without sacrificing the funnel pattern.

## Recommendations

1. **Do Not Remove**: The bottleneck is architectural, not accidental
2. **Monitor Depth**: Current depth is 19 (from instance_rows to release_manifest). Target: ≤6
3. **Consider Checkpoints**: Evaluate checkpoint plugins in Phase 6 to reduce depth while preserving the funnel pattern

---

*This document explains an intentional architectural decision. The bottleneck pattern is a feature, not a bug.*
