# Plugin Runtime ADR Map

**Date:** 2026-03-11
**Purpose:** Fast navigation map for the plugin-runtime ADR stack.
**Audience:** Architects, maintainers, plugin authors, reviewers.

---

## TL;DR

If you need to understand the plugin-runtime architecture quickly, read documents in this order:

1. `adr/0063-plugin-microkernel-for-compiler-validators-generators.md` — foundational runtime architecture
2. `adr/0065-plugin-api-contract-specification.md` — plugin API and execution/result contracts
3. `adr/0066-plugin-testing-and-ci-strategy.md` — testing layers and CI expectations
4. `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md` — plugin-first cutover and thin orchestrator governance
5. `adr/0071-sharded-instance-files-and-flat-instances-root.md` — sharded instance authoring with unchanged downstream plugin boundary

---

## Responsibility Map

### `ADR 0063` — Runtime Foundation

Defines the architectural runtime model:

- microkernel responsibilities
- plugin kinds
- manifest discovery and deterministic ordering
- diagnostics aggregation
- compatibility philosophy

Read when you need to answer:
- "What is the runtime architecture?"
- "What belongs in core vs plugins?"

### `ADR 0065` — Plugin API Contract

Defines the plugin-facing contract:

- base interfaces and execution signatures
- `PluginContext`, `PluginResult`, `PluginDiagnostic`
- config injection
- manifest entry validation
- API compatibility rules

Read when you need to answer:
- "How do I implement a plugin?"
- "What data contract does kernel enforce?"

### `ADR 0066` — Testing and CI Strategy

Defines validation and enforcement model:

- unit / contract / integration / regression layers
- coverage expectations
- CI rollout and required jobs
- test tree conventions

Read when you need to answer:
- "How is plugin behavior validated?"
- "What tests and CI gates are required?"

### `ADR 0069` — Plugin-First Cutover

Defines operational governance for runtime migration:

- thin orchestrator target
- plugin-first compile/validate/generate ownership
- versioned `ctx.compiled_json` boundary
- parity rules
- rollback protocol
- cutover checklist and status promotion

Read when you need to answer:
- "How do we cut over safely?"
- "What is authoritative for parity and rollback?"

### `ADR 0071` — Sharded Instance Source Contract

Defines source storage evolution without changing plugin consumption boundary:

- `paths.instances_root`
- one-instance-per-file storage model
- shard loader and assembly rules
- deterministic discovery
- payload compatibility for downstream plugins

Read when you need to answer:
- "How are instance files authored and loaded now?"
- "Can plugins read shard files directly?" (No)

---

## Authority by Concern

| Concern | Authoritative ADR / Document |
|---|---|
| Runtime architecture | `adr/0063-plugin-microkernel-for-compiler-validators-generators.md` |
| Plugin API | `adr/0065-plugin-api-contract-specification.md` |
| Plugin tests and CI | `adr/0066-plugin-testing-and-ci-strategy.md` |
| Plugin-first cutover / rollback / parity | `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md` + `adr/0069-analysis/*` |
| Instance placeholders / explicit overrides | `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md` |
| Sharded instance source layout | `adr/0071-sharded-instance-files-and-flat-instances-root.md` + `adr/0071-analysis/*` |

---

## Non-Goals and Boundaries

- `ADR 0063` does **not** own operational cutover details anymore.
- `ADR 0069` does **not** redefine plugin API shapes; it governs cutover and stage ownership.
- `ADR 0071` does **not** change plugin ownership boundaries; it changes only instance source storage/normalization.
- `ADR 0068` defines domain compile/validate semantics, not runtime packaging architecture.

---

## Recommended Reading Paths

### For a new maintainer

1. `ADR 0063`
2. `ADR 0069`
3. `ADR 0065`
4. `ADR 0066`
5. `ADR 0071`

### For a plugin author

1. `ADR 0065`
2. `ADR 0066`
3. `ADR 0063`

### For a migration/cutover reviewer

1. `ADR 0069`
2. `adr/0069-analysis/IMPLEMENTATION-PLAN.md`
3. `adr/0069-analysis/CUTOVER-CHECKLIST.md`
4. `ADR 0063`

### For instance-model/source-contract work

1. `ADR 0068`
2. `ADR 0071`
3. `adr/0071-analysis/IMPLEMENTATION-PLAN.md`
4. `adr/0071-analysis/CUTOVER-CHECKLIST.md`

---

## Historical Notes

Some files under `adr/0063-analysis/` are retained for traceability and historical context.
They should not be treated as the primary operational source when they conflict with implemented ADR status or newer cutover documents.

Use current authoritative documents first; consult historical analysis only for background.
