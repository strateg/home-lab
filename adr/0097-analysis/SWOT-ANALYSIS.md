# ADR 0097 SWOT Analysis — Actor-Style Dataflow Runtime

Date: 2026-04-17
Status: Current-state SWOT after ADR rewrite and project scan
Scope: ADR 0097 viability, migration readiness, and project-state fit

## Project State Snapshot

Observed in current codebase at analysis time:

- `PluginContext` still owns `_published_data`, metadata, publish/subscribe events, event subscriptions, queues, and history in `topology-tools/kernel/plugin_base.py`.
- `SerializablePluginContext` still transports compiled model, plugin config, and published data into isolated execution.
- `_execute_plugin_isolated()` returns `(PluginResult, published_data)` and `_execute_phase_parallel()` merges worker-produced `_published_data` back into the main context.
- `module_loader_compiler.py` still mutates `ctx.classes` and `ctx.objects`.
- `effective_model_compiler.py` still mutates `ctx.compiled_json` after publishing candidate output.
- `instance_rows_compiler.py` remains a large multi-responsibility compiler and central downstream dependency.
- Manifest inventory still favors legacy routing contract shape:
  - `subinterpreter_compatible`: 55 occurrences
  - `execution_mode`: 3 occurrences
  - `input_view`: 0 occurrences
- Test suite still heavily references legacy context internals:
  - `_set_execution_context(...)`: 142 matches across 49 test files
  - `get_published_data(...)`: 7 matches across 6 test files
  - `PipelineState`, `PluginExecutionEnvelope`, `PluginInputSnapshot`, `run_plugin_once()`: 0 matches in tests at analysis time

## Strengths

1. **Strong plugin ecosystem foundation**
   - Stage-based runtime, manifest contracts, and deterministic discovery order already exist.
   - `depends_on`, `consumes`, and `produces` provide a good base for snapshot building and commit validation.

2. **High existing coverage density**
   - Even though many tests are legacy-shaped, the project already has broad behavioral safety nets for plugin runtime and orchestration.

3. **Subinterpreter path already exists**
   - The project has real execution plumbing for isolated worker execution, reducing adoption risk compared to a greenfield rewrite.

4. **Some plugins already fit the target mental model reasonably well**
   - Declarative validators that consume resolved payloads and compute diagnostics locally are close to the future SDK style.

5. **Architecture governance is active**
   - ADR workflow, register consistency checks, and analysis directories are in place and functioning.

## Weaknesses

1. **Legacy context ownership is still architectural reality in code**
   - `PluginContext` still acts as worker-local API and pipeline-visible state carrier simultaneously.

2. **Transport boundary is still context-shaped**
   - `SerializablePluginContext` preserves the old execution model and leaks mutable bus semantics across interpreters.

3. **Parallel scheduler still relies on merge-back semantics**
   - `_execute_phase_parallel()` still reconstructs published data in the main context from worker-returned payloads.

4. **Plugin portfolio is unevenly prepared**
   - Some plugins are nearly snapshot-friendly; others still mutate `ctx.classes`, `ctx.objects`, or `ctx.compiled_json`.

5. **Tests lag behind the target runtime architecture**
   - Primary assertions are still mostly context-centric rather than envelope/pipeline-state-centric.

6. **Manifest routing contract is mid-transition**
   - `execution_mode` is not yet the dominant runtime contract and `input_view` is not in use.

## Opportunities

1. **Convert runtime complexity into ownership clarity**
   - Replacing live-context transport with snapshot/envelope contracts will make scheduler behavior easier to reason about and verify.

2. **Improve determinism and replayability**
   - Commit-based PipelineState opens cleaner paths for parity testing, caching, replay, and failure isolation.

3. **Decompose oversized compilers**
   - `InstanceRowsCompiler` can be split into smaller, better-bounded units, improving locality of failures and snapshot shaping.

4. **Reduce serialization overhead over time**
   - `input_view` can become a targeted optimization after contract correctness is established.

5. **Use plugin exemplars to drive SDK migration**
   - Declarative validators can anchor author guidance for the future plugin SDK.

## Threats

1. **Dual-semantics drift during migration**
   - If both shared-context and envelope-commit models remain first-class too long, the codebase may become harder to simplify.

2. **Compatibility layers may harden into permanent runtime behavior**
   - Legacy context APIs can become de facto source of truth unless explicitly fenced off as transitional only.

3. **Central plugin bottlenecks can slow the whole migration**
   - `InstanceRowsCompiler` and `EffectiveModelCompiler` sit on critical paths and can block downstream adoption if not addressed early.

4. **Builder/generator consumers may preserve ambient-registry assumptions**
   - Continued reliance on `ctx.get_published_data()` keeps the pipeline coupled to a live shared registry model.

5. **Event-plane expansion could reintroduce hidden shared semantics**
   - Worker-side event bus features are easy to overgrow before main-interpreter ownership is stabilized.

## SWOT Conclusion

ADR 0097 is strategically strong and well-aligned with the repository's direction, but the project is still in an early-to-mid migration state.

The main conclusion is:

- **the architecture direction is correct;**
- **the current implementation baseline still materially reflects the legacy context model;**
- **the migration must be governed by explicit anti-drift rules and early representative plugin cutovers.**

## Recommended ADR Reinforcements

1. Mark legacy context-owned data/event bus mechanics as **compatibility-only**, not extensible architecture.
2. Make removal of worker merge-back semantics an explicit acceptance target.
3. Promote representative plugin migration as a formal success criterion, not just an implementation note.
4. Keep worker event handling envelope-only until main-interpreter routing ownership is fully established.
5. Tie test migration to runtime waves so parity/isolation gates close each migration step.
