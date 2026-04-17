# ADR 0097 Implementation Ordering Matrix

Date: 2026-04-17
Purpose: Bind audited migration anchors to the direct envelope-model rollout across PR1 / PR2 / PR3.

## Ordering principle

- **PR1** creates the envelope-model runtime foundation.
- **PR2** makes scheduler/runtime ownership correct.
- **PR3** proves the model on representative compiler / validator / generator paths.

Representative plugin cutovers are intentionally deferred until the runtime path exists.

---

## PR1 — Contracts and primary path skeleton

### Goal
Introduce the runtime contracts and execution primitives required for snapshot/envelope/commit flow.

### Files / components
- `topology-tools/kernel/plugin_base.py`
- `topology-tools/kernel/plugin_runner.py` (new)
- `topology-tools/kernel/pipeline_runtime.py` (new)
- minimal bridge changes in `topology-tools/kernel/plugin_registry.py`

### Plugin migration scope in PR1
| Plugin / family | Action in PR1 | Why |
|---|---|---|
| `base.compiler.module_loader` | audit only, no behavioral cutover yet | needs runtime commit authority first |
| `base.compiler.effective_model` | audit only, no behavioral cutover yet | requires authoritative compiled-model commit path |
| `base.compiler.instance_rows` | audit only, no decomposition yet | runtime path must stabilize first |
| Representative declarative validator | optional smoke-only runner validation | good early consumer of snapshot-only path, but not mandatory for PR1 |
| `base.generator.effective_json` | optional smoke-only runner validation | useful for early generator contract sanity |

### Tests required in PR1
- `tests/plugin_api/test_snapshot_envelope_dataclasses.py`
- `tests/runtime/worker_runner/test_run_plugin_once.py`
- `tests/runtime/pipeline_state/test_commit_envelope.py`
- `tests/runtime/pipeline_state/test_stage_local_visibility.py`

### PR1 exit gate
- snapshot/envelope dataclasses exist
- `run_plugin_once()` exists
- `PipelineState.commit_envelope()` exists
- new serial path can execute without shared published-data bus semantics

---

## PR2 — Scheduler cutover and runtime ownership correction

### Goal
Replace primary-path merge-back runtime behavior with main-interpreter commit semantics.

### Files / components
- `topology-tools/kernel/plugin_registry.py`
- `topology-tools/kernel/plugin_runner.py`
- `topology-tools/kernel/pipeline_runtime.py`
- manifest loading / routing support for `execution_mode`

### Plugin migration scope in PR2
| Plugin / family | Action in PR2 | Why |
|---|---|---|
| `base.compiler.module_loader` | prepare commit target shape only | downstream consumers depend on authoritative topology maps |
| `base.compiler.effective_model` | prepare authoritative commit hook only | compiled-model authority moves to main interpreter |
| `base.compiler.instance_rows` | no decomposition yet; maintain compatibility through current output contract | keep blast radius controlled while scheduler changes |
| Representative declarative validator | use as scheduler/parity verification target if feasible | validates consume resolution and deterministic diagnostics |
| `base.generator.effective_json` | use as lightweight scheduler integration target if feasible | validates committed compiled-model consumption |

### Tests required in PR2
- `tests/runtime/scheduler/test_execution_mode_routing.py`
- `tests/runtime/scheduler/test_no_merge_back_primary_path.py`
- `tests/runtime/scheduler/test_worker_failure_isolation.py`
- `tests/runtime/parity/test_serial_vs_subinterpreter_envelope_commit.py`

### PR2 exit gate
- `_execute_plugin_isolated()` returns envelope
- `_execute_phase_parallel()` no longer uses worker merge-back as primary runtime authority
- consumes resolved before dispatch
- commit owned by main interpreter through `PipelineState`

---

## PR3 — Representative plugin cutovers

### Goal
Prove the new runtime model on critical-path plugins.

### Files / components
- representative plugins from compiler / validator / generator families
- related manifest entries
- corresponding unit/integration/parity tests

### Plugin migration scope in PR3
| Plugin / family | Action in PR3 | Why |
|---|---|---|
| `base.compiler.module_loader` | cut over from `ctx.classes/ctx.objects` mutation to candidate publication + main commit | first compiler authority-boundary proof |
| `base.compiler.effective_model` | remove `ctx.compiled_json` authority mutation; publish candidate only | canonical compiled-model boundary proof |
| `base.compiler.instance_rows` | begin decomposition (annotation/secret resolution → normalization → semantic/shape validation) | highest-value bottleneck reduction |
| Representative declarative validator (`base.validator.dns_refs` family entry) | complete snapshot-only validator migration | first “good style” validator proof |
| `base.generator.effective_json` | consume committed compiled-model snapshot; publish artifact metadata via envelope | first generator proof |
| `base.generator.ansible_inventory` | optional follow-up in late PR3 or PR3b | richer generator after simple generator succeeds |

### Tests required in PR3
- `tests/plugins/unit/` suites for migrated plugins
- `tests/runtime/parity/` committed outputs / statuses / diagnostics parity
- integration tests for committed compiled-model and normalized-rows consumers
- targeted tests for stage-local visibility where split outputs introduce scoped payloads

### PR3 exit gate
- at least one compiler path, one validator, and one generator operate through snapshot/envelope/commit flow
- authoritative compiled model commit is main-interpreter-owned
- migrated plugins no longer require ambient shared-state mutation

---

## Deferred / post-PR3 items

| Item | Reason for deferral |
|---|---|
| broad plugin fleet migration | should follow proven representative cutovers |
| `input_view` optimization rollout | should be introduced only after real snapshot hot paths are measured |
| `base.generator.ansible_inventory` full migration | better after first generator proof with `effective_json` |
| large-scale legacy test cleanup | wait until new primary runtime tests are stable |

---

## Cross-PR test policy

### Primary validation surface
- `tests/runtime/worker_runner/`
- `tests/runtime/pipeline_state/`
- `tests/runtime/scheduler/`
- `tests/runtime/parity/`
- `tests/plugins/unit/`

### Transitional validation surface
- existing context-heavy registry and plugin-context tests remain temporarily as compatibility coverage only.

## Summary

- **PR1** builds the contracts.
- **PR2** corrects the scheduler ownership model.
- **PR3** proves the architecture on representative plugins.

This ordering minimizes blast radius while keeping the project on a direct cutover path to the envelope model.
