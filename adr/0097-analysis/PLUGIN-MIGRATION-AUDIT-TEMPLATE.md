# ADR 0097 Plugin Migration Audit Template

Date: 2026-04-17
Purpose: Standard audit form for migrating plugins from legacy shared-context semantics to the ADR 0097 snapshot/envelope/commit model.

## How to use

For each candidate plugin, fill the template below before implementation work begins.

---

## 1. Plugin identity

- Plugin ID:
- File:
- Family:
- Stage:
- Phase:
- Current manifest routing fields:
  - `subinterpreter_compatible`:
  - `execution_mode`:
  - `consumes`:
  - `produces`:

## 2. Current runtime behavior

- Reads from `ctx.subscribe(...)`:
- Reads from ambient context (`ctx.classes`, `ctx.objects`, `ctx.compiled_json`, etc.):
- Writes via `ctx.publish(...)`:
- Directly mutates ambient context (`ctx.classes`, `ctx.objects`, `ctx.compiled_json`, etc.):
- Uses legacy live-registry APIs (`ctx.get_published_data()`, event polling, etc.):
- File / external IO performed:

## 3. Classification

- Snapshot-friendly now? (`yes` / `partial` / `no`):
- Uses shared-state authority semantics?:
- Requires main-interpreter commit authority?:
- Suitable as representative migration anchor? Why?:

## 4. Target snapshot contract

- Minimal required input payloads:
- Required `consumes` keys:
- Candidate `input_view` (if useful):
- Data that must NOT be passed through snapshot:

## 5. Target envelope contract

- Published messages expected in envelope:
- Emitted events expected in envelope:
- `PluginResult.output_data` that should remain semantic-only:
- Which payloads require main-interpreter validation before commit:

## 6. Migration actions

- Replace ambient reads with snapshot fields:
- Replace ambient mutations with envelope publication:
- Remove live-registry/event-bus assumptions:
- Additional decomposition needed?:
- Manifest/schema changes needed?:

## 7. Test plan

- Plugin unit tests:
- Worker runner tests:
- Pipeline state tests:
- Scheduler/integration tests:
- Serial vs subinterpreter parity tests:

## 8. Exit criteria

- No direct mutation of ambient shared runtime state.
- Plugin can run from `PluginInputSnapshot` only.
- Plugin returns envelope-compatible outputs.
- Committed outputs are owned by `PipelineState`, not worker context.
- New tests exist and legacy assumptions are not the primary validation surface.

---

## Quick risk rubric

Score each area as Low / Medium / High:

- Ambient state mutation risk:
- Snapshot size risk:
- IO coupling risk:
- Downstream contract blast radius:
- Test migration effort:
- Recommended rollout order:
