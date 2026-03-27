# ADR 0080 Gap Analysis

**ADR:** `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
**Date:** 2026-03-26
**Status:** Historical baseline (resolved by 2026-03-27 cutover closure)

---

## Purpose

Evaluate ADR 0080 against the current implementation (AS-IS) and identify gaps,
risks, and missing specification that must be addressed before or during implementation.

> Note (2026-03-27): this document is preserved as the pre-cutover gap snapshot.
> Closure evidence is tracked in:
> - `adr/0080-analysis/CUTOVER-CHECKLIST.md`
> - `adr/0080-analysis/CUTOVER-PLAN.md`
> - `adr/plan/0078-cutover-checklist.md`

---

## AS-IS Baseline (Confirmed from Code)

Confirmed in `topology-tools/kernel/plugin_base.py` and `topology-tools/plugins/plugins.yaml`:

1. **Stages in kernel:** `COMPILE`, `VALIDATE`, `GENERATE` — three values only.
2. **No `Phase` concept in runtime.** Execution order is: stage boundary → `depends_on` DAG → numeric `order` field.
3. **Publish/subscribe works** (`ctx.publish(key, value)` / `ctx.subscribe(plugin_id, key)`) but all keys are implicit runtime conventions — no `produces`/`consumes` manifest contract.
4. **Registered plugin count:** 47 (7 compile, 35 validate, 5 generate). ADR states 57 — the gap is unresolved object/class-module plugins not yet in scope.
5. **`discover_plugin_manifests()`** is a bare function in `compiler_runtime.py` — outside plugin lifecycle.
6. **No `assemble` or `build` stages** anywhere in the codebase.

---

## Strengths of ADR 0080

1. **Stage split is well-motivated.** Separating `generate` (baseline) from `assemble` (execution views) from `build` (release/trust) maps directly to the artifact ownership rules in ADR 0050/0056.
2. **`finalize` guarantee** is architecturally correct — cleanup and manifests must run even after stage failure.
3. **Data bus formalization** closes a real fragility: publish/subscribe keys are undiscoverable, untested, and can silently break cross-stage coupling.
4. **Section 4 phase assignment** is concrete enough to start Wave D immediately.
5. **Dependencies listed** (ADR 0005, 0027, 0028, 0050-0056, 0063, 0065, 0069, 0071, 0074-0076, 0078) are all relevant and correctly cited.

---

## Gaps and Issues

### G1 — `discover` stage has no plugin assignment (High)

**Section 4 covers compile, validate, generate, assemble, build — but not `discover`.**

The `discover` stage is first in the global order. Currently
`compiler_runtime.discover_plugin_manifests()` performs manifest loading, framework/project
context resolution, and capability preflight outside the plugin lifecycle. ADR 0080 does not
specify which plugins own this or what data they publish.

**Impact:** Wave F/G will still depend on a non-pluginized discovery path. The `discover` stage
would be an empty stage in the runtime, defeating its purpose.

**Required addition:** Section 4.0 defining initial `discover` plugin assignments.

---

### G2 — `PluginContext` not extended for `assemble` / `build` (High)

`PluginContext` in `plugin_base.py` has fields for compile/validate/generate workloads
(`topology_path`, `compiled_json`, `output_dir`, etc.) but nothing for:

- `workspace_root` — `.work/native/` path needed by assemble plugins
- `dist_root` — `dist/` path needed by assemble plugins
- `signing_backend`, `release_tag`, `sbom_output_dir` — needed by build plugins
- `assembly_manifest` — output from `assemble.finalize` consumed by `build.init`

**Impact:** `assemble` and `build` plugins cannot be implemented until these fields exist.
Wave F and Wave G are blocked by this.

**Required addition:** Section in ADR describing `PluginContext` extensions per new stage.

---

### G3 — `when` predicate not covered by any Wave (Medium)

Section 5 (Smart Plugin Model) introduces optional `when` predicate fields:
`profiles`, `pipeline_modes`, `capabilities`, `changed_input_scopes`.

None of the Waves A–H include implementation of this predicate evaluation. Wave C
covers phase-aware execution, but not conditional execution.

**Impact:** Predicate-gated plugins in assemble/build stages are unimplementable until
Wave C is extended.

**Required addition:** `when` predicate evaluation task in Wave C.

---

### G4 — Diagnostic code ranges not allocated (Medium)

ADR 0065 requires non-overlapping diagnostic code ranges per domain. Current allocations
in `topology-tools/data/error-catalog.yaml` cover E60xx–E97xx. ADR 0080 introduces three
new execution contexts (`discover`, `assemble`, `build`) but allocates no diagnostic ranges.

**Impact:** Build plugins cannot emit typed diagnostics conforming to ADR 0065.

**Required addition:** Section 6.4 allocating diagnostic code ranges for new stages.

---

### G5 — Order ranges not defined for new stages (Medium)

ADR 0074 defines explicit `order` ranges for the `generate` stage (190–399). New stages
(`discover`, `assemble`, `build`) have no defined order ranges, which will create conflicts
when plugin authors register new plugins.

**Required addition:** Normative table of `order` ranges per stage in section 3 or 8.

---

### G6 — `base.generator.artifact_manifest` introduced but not Waved (Medium)

Section 4.3 lists `base.generator.artifact_manifest` as a new `generate/finalize` plugin.
No Wave covers its implementation or its `produces`/`consumes` contract.

**Required addition:** Wave E.1 for `artifact_manifest` plugin implementation.

---

### G7 — Wave D depends on Wave C unnecessarily (Low — blocks parallelism)

Phase annotations (`phase: run`) in plugin manifests are a new optional field with
a default value. The manifest schema and `PluginSpec` can accept them after Wave B alone.
Wave D does not require the new executor from Wave C.

**Recommended fix:** Allow Wave D to run in parallel with Wave B, not sequentially after Wave C.
This shortens the critical path by one full wave.

---

### G8 — ADR 0079 coordination not mentioned (Medium)

ADR 0079 (V5 Documentation and Diagram Generation Migration, Proposed) is actively
changing `base.generator.docs` and `base.generator.diagrams`. Wave D annotates these
same plugins with `phase:` values. If ADR 0079 replaces or restructures these plugins
concurrently, Wave D annotations could be applied to plugins that are about to be deleted.

**Required addition:** Explicit coordination note between Wave D and ADR 0079 work.

---

### G9 — Rollback strategy absent for Wave C (Low)

Wave C changes execution ordering. A subtle regression in phase execution sequence would
produce the same final output but change intermediate plugin context state. The baseline
snapshot from Wave A may not catch this.

**Recommended addition:** Canary mode flag that runs both old and new executor and compares
plugin execution traces before hard cutover in Wave C.

---

### G10 — Plugin count in context is stale (Low)

ADR states 57 plugins in 7 manifests. Code shows 47 in the base manifest. The gap is
likely unresolved object/class module plugins per ADR 0078. Wave D must recount against
actual discovered manifests, not the ADR estimate.

---

### G11 — Schema/runtime stage-phase vocabulary drift (High)

Manifest schema allows `build` stage and `finished` phase token, but runtime `Stage` enum
has no `BUILD` value and no `Phase` concept. Runtime would silently ignore or reject plugins
declaring these values.

**Resolution:** Wave B aligns both enums; schema replaces `finished` → `finalize`.

---

### G12 — `effective_json/yaml` init phase violates mutation rule (Medium)

These plugins were initially assigned to `generate/init`, but they produce business
artifacts (JSON/YAML files). The `init` phase contract states "no artifact mutation".

**Resolution:** Reassigned to `generate/run` in Section 4.3 of ADR.

---

### G13 — `PluginKind` missing assembler/builder (Medium)

`PluginKind` enum has only `compiler`, `validator_yaml`, `validator_json`, `generator`.
Plugins for new `assemble`/`build` stages have no `kind` affinity.

**Resolution:** Section 5.2 adds `assembler` and `builder` to `PluginKind`.

---

### G14 — Phase handler protocol breaks backward compat (High)

Adding `on_<phase>()` methods to `BasePlugin` would change the interface contract.
All existing plugins implement only `execute(ctx)`.

**Resolution:** Section 5.3 defines backward-compat dispatch: `execute(ctx)` is
preferred for `run` phase; `on_<phase>` methods are additive/optional.

---

### G15 — `profile_restrictions` duplicates `when.profiles` (Low)

Both fields exist with overlapping semantics. No migration path was defined.

**Resolution:** Section 5.4 defines Wave D conversion and Wave H removal of deprecated field.

---

### G16 — Discovery bootstrap circular dependency (High)

No specification for how base manifest is loaded before the discover stage starts.
Discover plugins reside in a manifest that must be discovered first.

**Resolution:** Section 5.5 defines the bootstrap contract: base manifest is the only
pre-lifecycle load; discover plugins must reside in base manifest only.

---

### G17 — Partial `--stages` + finalize guarantee interaction (Medium)

`--stages` flag allows partial execution, but no rule specifies whether `finalize`
runs for started stages only, for requested stages only, or for all stages.

**Resolution:** Section 5.6 defines: finalize runs for started stages only; skipped
stages never start and never emit finalize.

---

### G18 — `stage_local` scope enforcement rules missing (Medium)

Data bus `scope` field was defined (`stage_local`/`pipeline_shared`) but had no
enforcement semantics. Cross-stage subscriptions to `stage_local` keys could silently succeed.

**Resolution:** Section 6.1 and 6.2 define hard error for cross-stage `stage_local` subscriptions.

---

### G19 — Shared `_current_plugin_id` blocks parallelism (Critical)

`PluginContext._current_plugin_id` is a mutable field overwritten before each plugin call.
Two concurrent plugins corrupt each other's identity, causing `publish()` to store
data under the wrong plugin key.

**Resolution:** ADR Section 9.2 Blocker 1 — `PluginExecutionScope` per-invocation value object.

---

### G20 — Shared `_allowed_dependencies` blocks parallelism (Critical)

Same pattern as G19 — mutable field on shared `PluginContext` overwritten before each call.
Concurrent plugins see each other's dependency sets.

**Resolution:** ADR Section 9.2 Blocker 1 — included in `PluginExecutionScope`.

---

### G21 — `_published_data` has no concurrency protection (High)

Nested `dict[str, dict[str, Any]]` with no synchronization. Concurrent `publish()` calls
can produce corrupted data structures or lose writes.

**Resolution:** ADR Section 9.2 Blocker 2 — `threading.Lock()` on `_published_data` access.

---

### G22 — `compiled_json` mutation race (High)

Multiple compiler plugins can assign `ctx.compiled_json = new_value` directly.
Under parallelism, simultaneous writes produce last-write-wins corruption.

**Resolution:** ADR Section 9.2 Blocker 3 — `compiled_json_owner` manifest field with
at-most-one-owner-per-phase load-time validation. Deep-copy frozen snapshot at stage boundary.

---

### G23 — Per-plugin config injection via shared field (Medium)

`execute_plugin()` replaces `ctx.config` before each call. Concurrent plugins
see stale or interleaved configuration.

**Resolution:** ADR Section 9.2 Blocker 4 — config injected via `PluginExecutionScope`.

---

### G24 — Plugin instance cache TOCTOU (Medium)

`PluginRegistry.instances` dict has check-then-insert pattern. Two threads loading
the same plugin concurrently can create duplicate instances.

**Resolution:** ADR Section 9.2 Blocker 5 — pre-load all instances before execution,
or protect with `threading.Lock()`.

---

## Risk Summary

| Risk | Wave | Severity | Mitigation |
|------|------|----------|------------|
| Lifecycle refactor silently changes execution order | C | High | Execution trace comparison canary |
| assemble/build plugins blocked on missing PluginContext fields | F/G | High | Add to Wave B scope |
| discover stage remains non-pluginized | F | High | Define Section 4.0 and Wave B task |
| Missing diagnostic ranges cause ADR 0065 violations | F/G | Medium | Allocate in Wave B |
| Undeclared data bus coupling survives into assemble stage | E/F | Medium | Backward-compat W80xx warning before hard error |
| ADR 0079 restructures generator plugins during Wave D | D | Medium | Coordinate sequencing or add explicit exclusion |
| Schema/runtime vocabulary drift causes silent plugin failures | B | High | Align enums and add CI conformance test |
| Phase handler rewrite breaks all existing plugins | B/C | High | Backward-compat dispatch: execute(ctx) preserved |
| Discovery bootstrap circular dependency | B/F | High | Base manifest pre-lifecycle contract |
| Shared mutable context fields corrupt data under parallelism | C+ | Critical | PluginExecutionScope per-invocation + locks |
| `compiled_json` mutation race under parallel compilers | C+ | High | Owner field + frozen snapshot at stage boundary |
| Non-deterministic output ordering under parallel execution | C+/H | Medium | order-based submission + byte-identical parity tests |
| GIL limits parallelism benefit for CPU-bound plugins | C+ | Low | ThreadPoolExecutor sufficient for I/O-bound; future ProcessPoolExecutor ADR |

---

## References

- `topology-tools/kernel/plugin_base.py` — `Stage` enum, `PluginContext`, publish/subscribe
- `topology-tools/kernel/plugin_registry.py` — executor, DAG resolution
- `topology-tools/plugins/plugins.yaml` — registered plugin inventory
- `topology-tools/data/error-catalog.yaml` — diagnostic code allocations
- `adr/0065-plugin-api-contract-specification.md` — diagnostic code contract
- `adr/0074-v5-generator-architecture.md` — order ranges for generate stage
- `adr/0079-v5-documentation-and-diagram-generation-migration.md` — concurrent generator work
