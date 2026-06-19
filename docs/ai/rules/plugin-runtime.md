---
@pack: plugin-runtime
@version: 1.0
@tokens: ~450
@adr: [0063, 0065, 0080, 0097]
---

# AI Rule Pack: Plugin Runtime

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Lifecycle | `discover → compile → validate → generate → assemble → build` |
| Stage affinity | Plugin family must match stage (e.g., generators → generate) |
| Manifests | Declare `depends_on`, `consumes`, `produces` explicitly |
| Execution mode | Use `subinterpreter` by default (84/85 plugins) |
| Workers | Must not mutate pipeline-global state |

## Load When

- `topology-tools/plugins/**`
- `topology-tools/kernel/**`
- `topology/**/plugins.yaml`
- Plugin manifest discovery or stage ordering

## Stage Affinity Matrix

| Stage | Plugin Family | Purpose |
|-------|---------------|---------|
| discover | discoverers | Read manifests, populate registry |
| compile | compilers | Transform topology, resolve references |
| validate | validators | Check constraints, emit diagnostics |
| generate | generators | Produce artifacts to `generated/` |
| assemble | assemblers | Combine artifacts into bundles |
| build | builders | Create deployable packages |

## Discovery Order

| Priority | Scope | Location |
|----------|-------|----------|
| 1 | Framework | `topology-tools/plugins/` |
| 2 | Class | `topology/class-modules/**/plugins.yaml` |
| 3 | Object | `topology/object-modules/**/plugins.yaml` |
| 4 | Project | `projects/*/plugins/` |

## Execution Mode (ADR0097)

| Mode | Use When | Constraints |
|------|----------|-------------|
| `subinterpreter` | Default for all new plugins | Read from snapshot, write to outbox only |
| `main_interpreter` | Mutates `ctx` fields, accesses `plugin_registry` | Required for bootstrap plugins |
| `thread_legacy` | Migration only | Deprecated, do not use for new plugins |

### Subinterpreter Rules

| Must | Must Not |
|------|----------|
| Read from `ctx.subscribe()`, `ctx.config`, `ctx.objects` | Mutate `ctx` fields directly |
| Write to `ctx.publish()`, `ctx.emit()` | Access `ctx.config.get("plugin_registry")` |
| Return `PluginExecutionEnvelope` | Use `importlib.util` dynamic loading |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Hidden filesystem reads | Bypasses manifest contracts | Use `consumes` declaration |
| Missing `depends_on` | Non-deterministic execution order | Declare dependencies |
| `thread_legacy` for new plugins | Deprecated mode | Use `subinterpreter` |

## Validation

```bash
task validate:plugin-manifests
task test:plugin-contract
```
