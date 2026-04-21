# AI Rule Pack: Plugin Runtime

Load when changing:

- `topology-tools/plugins/**`
- `topology/**/plugins.yaml`
- `topology-tools/kernel/**`
- plugin manifest discovery or stage ordering

## Rules

1. Preserve lifecycle order: `discover -> compile -> validate -> generate -> assemble -> build`.
2. Preserve stage affinity:
   - discoverers -> discover
   - compilers -> compile
   - validators -> validate
   - generators -> generate
   - assemblers -> assemble
   - builders -> build
3. Declare dependencies and data exchange through manifests:
   - `depends_on`
   - `consumes`
   - `produces`
4. Respect discovery order:
   - framework
   - class
   - object
   - project
5. Treat class/object module placement as ownership convention, not runtime ACL.
6. Shared standalone plugins belong in `topology-tools/plugins/<family>/`.
7. Do not add hidden coupling through filesystem reads when `ctx` or manifest exchange is the intended contract.

## Execution Mode (ADR 0097)

8. Declare `execution_mode` explicitly in plugin manifests:
   - `subinterpreter`: Default for new plugins. Isolated parallel execution on Python 3.14 subinterpreters.
   - `main_interpreter`: Required for plugins that mutate context fields or access plugin_registry.
   - `thread_legacy`: Deprecated. Migration-only compatibility mode (do not use for new plugins).

9. Follow envelope semantics for plugin execution:
   - Plugins receive immutable `PluginInputSnapshot` with resolved consumes.
   - Plugins return `PluginExecutionEnvelope` with proposed outputs.
   - Main interpreter validates and commits envelope contents to pipeline state.
   - Workers must not directly mutate pipeline-global state.

10. Use `subinterpreter` mode unless plugin requires:
    - Direct `ctx` field mutation (e.g., `ctx.model_lock`, `ctx.workspace_root`, `ctx.config`)
    - Access to `ctx.config.get("plugin_registry")`
    - Dynamic module loading with `importlib.util`

11. Plugins in `subinterpreter` mode must:
    - Read only from snapshot inputs (`ctx.subscribe()`, `ctx.config`, `ctx.objects`)
    - Write only to local outbox (`ctx.publish()`, `ctx.emit()`)
    - Not assume shared mutable state with other plugins

## Validation

- `task validate:plugin-manifests`
- `task test:plugin-contract`
- targeted plugin integration tests

## ADR Sources

- ADR0063 — Plugin-based compiler architecture
- ADR0065 — Plugin manifest contracts
- ADR0066 — Plugin discovery order
- ADR0069 — Plugin stage affinity
- ADR0078 — Plugin validation contracts
- ADR0080 — Plugin migration patterns
- ADR0086 — Plugin safety enforcement
- ADR0097 — Actor-style dataflow execution (subinterpreters)
