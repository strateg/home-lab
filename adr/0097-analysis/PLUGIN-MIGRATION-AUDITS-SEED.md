# ADR 0097 Seed Plugin Migration Audits

Date: 2026-04-17
Purpose: Initial filled audits for the first high-priority migration anchors.

---

## Audit 1 — `base.compiler.module_loader`

### 1. Plugin identity
- Plugin ID: `base.compiler.module_loader`
- File: `topology-tools/plugins/compilers/module_loader_compiler.py`
- Family: compiler
- Stage: compile
- Phase: init
- Current manifest routing fields:
  - `subinterpreter_compatible`: not declared
  - `execution_mode`: not declared
  - `consumes`: none
  - `produces`: `class_map`, `object_map`, `class_module_paths`, `object_module_paths`

### 2. Current runtime behavior
- Reads from `ctx.subscribe(...)`: no
- Reads from ambient context: config-driven roots, topology metadata already present in context
- Writes via `ctx.publish(...)`: yes
- Directly mutates ambient context: yes (`ctx.classes`, `ctx.objects`)
- Uses legacy live-registry APIs: no
- File / external IO performed: yes, loads class/object module maps from filesystem

### 3. Classification
- Snapshot-friendly now?: partial
- Uses shared-state authority semantics?: yes
- Requires main-interpreter commit authority?: yes
- Suitable as representative migration anchor? Why?: yes; it is the clearest early proof that authoritative topology maps must stop being worker-owned mutable context state.

### 4. Target snapshot contract
- Minimal required input payloads:
  - module roots / semantic keyword registry paths / manifest-level compile metadata
- Required `consumes` keys: none
- Candidate `input_view`: `module_roots`
- Data that must NOT be passed through snapshot:
  - mutable `ctx.classes`
  - mutable `ctx.objects`
  - live published registry

### 5. Target envelope contract
- Published messages expected in envelope:
  - `class_map`
  - `object_map`
  - `class_module_paths`
  - `object_module_paths`
- Emitted events expected in envelope: none required initially
- `PluginResult.output_data` that should remain semantic-only:
  - optional summary mirrors only
- Which payloads require main-interpreter validation before commit:
  - class/object map structure
  - typed extends integrity outputs if promoted to committed state

### 6. Migration actions
- Replace ambient mutation of `ctx.classes` / `ctx.objects` with published candidate payloads only
- Commit authoritative topology maps in main interpreter (`PipelineState` / dedicated commit logic)
- Keep filesystem reads local to worker execution
- Manifest/schema changes needed?: later adopt `execution_mode`; possible `input_view=module_roots`

### 7. Test plan
- Plugin unit tests:
  - snapshot with roots in, envelope with published module payloads out
- Worker runner tests:
  - module-loader envelope round-trip
- Pipeline state tests:
  - commit of class/object maps to authoritative runtime state
- Scheduler/integration tests:
  - downstream compiler sees committed maps without worker-owned ambient mutation
- Serial vs subinterpreter parity tests:
  - equal committed module maps

### 8. Exit criteria
- No direct mutation of `ctx.classes` / `ctx.objects`
- Module maps become authoritative only after main-interpreter commit
- Downstream compilers consume committed payloads, not worker-owned mutable context state

### Quick risk rubric
- Ambient state mutation risk: High
- Snapshot size risk: Low
- IO coupling risk: Medium
- Downstream contract blast radius: High
- Test migration effort: Medium
- Recommended rollout order: Wave 3A

---

## Audit 2 — `base.compiler.effective_model`

### 1. Plugin identity
- Plugin ID: `base.compiler.effective_model`
- File: `topology-tools/plugins/compilers/effective_model_compiler.py`
- Family: compiler
- Stage: compile
- Phase: finalize
- Current manifest routing fields:
  - `subinterpreter_compatible`: not declared
  - `execution_mode`: not declared
  - `consumes`: `base.compiler.instance_rows.normalized_rows` (optional)
  - `produces`: `effective_model_candidate`
  - `compiled_json_owner`: true

### 2. Current runtime behavior
- Reads from `ctx.subscribe(...)`: yes
- Reads from ambient context: yes (`ctx.classes`, `ctx.objects`)
- Writes via `ctx.publish(...)`: yes (`effective_model_candidate`)
- Directly mutates ambient context: yes (`ctx.compiled_json = candidate`)
- Uses legacy live-registry APIs: no
- File / external IO performed: no major direct IO beyond in-memory assembly

### 3. Classification
- Snapshot-friendly now?: partial
- Uses shared-state authority semantics?: yes
- Requires main-interpreter commit authority?: yes, critically
- Suitable as representative migration anchor? Why?: yes; this is the clearest proof point for separating candidate construction from authoritative compiled-model ownership.

### 4. Target snapshot contract
- Minimal required input payloads:
  - committed class map / object map or equivalent authoritative topology view
  - normalized rows
  - other resolved compile-stage inputs needed for effective model derivation
- Required `consumes` keys:
  - `normalized_rows`
  - committed topology maps / committed capability payloads as needed
- Candidate `input_view`: `effective_model_inputs`
- Data that must NOT be passed through snapshot:
  - authoritative compiled model as mutable live state

### 5. Target envelope contract
- Published messages expected in envelope:
  - `effective_model_candidate`
- Emitted events expected in envelope: optional diagnostics-oriented events only, if any
- `PluginResult.output_data` that should remain semantic-only:
  - compiler summary / candidate mirror
- Which payloads require main-interpreter validation before commit:
  - compiled model schema
  - authoritative compiled-json assignment

### 6. Migration actions
- Keep candidate construction local
- Remove `ctx.compiled_json = candidate` from worker path
- Commit authoritative compiled model only in main interpreter after envelope validation
- Possibly replace ambient `ctx.classes` / `ctx.objects` reads with committed snapshot view
- Manifest/schema changes needed?: later adopt `execution_mode`, maybe `input_view`

### 7. Test plan
- Plugin unit tests:
  - snapshot in → envelope with `effective_model_candidate`
- Worker runner tests:
  - envelope contains candidate but does not imply commit
- Pipeline state tests:
  - candidate commit becomes authoritative compiled model only after validation
- Scheduler/integration tests:
  - downstream generators consume committed compiled model
- Serial vs subinterpreter parity tests:
  - identical committed compiled model and diagnostics

### 8. Exit criteria
- Worker plugin no longer mutates `ctx.compiled_json`
- Authoritative compiled model exists only after main-interpreter commit
- Candidate payload remains proposal-only envelope output

### Quick risk rubric
- Ambient state mutation risk: High
- Snapshot size risk: Medium
- IO coupling risk: Low
- Downstream contract blast radius: Very High
- Test migration effort: Medium/High
- Recommended rollout order: Wave 3A

---

## Audit 3 — `base.compiler.instance_rows`

### 1. Plugin identity
- Plugin ID: `base.compiler.instance_rows`
- File: `topology-tools/plugins/compilers/instance_rows_compiler.py`
- Family: compiler
- Stage: compile
- Phase: run
- Current manifest routing fields:
  - `subinterpreter_compatible`: not declared
  - `execution_mode`: not declared
  - `consumes`: annotation resolver outputs (`annotation_formats`, `object_secret_annotations`, `row_annotations_by_instance`)
  - `produces`: `normalized_rows`

### 2. Current runtime behavior
- Reads from `ctx.subscribe(...)`: yes
- Reads from ambient context: yes (`ctx.objects`, `ctx.classes`, `ctx.instance_bindings`, config, model state)
- Writes via `ctx.publish(...)`: yes (`normalized_rows`)
- Directly mutates ambient context: not the primary issue; complexity is concentrated in one plugin
- Uses legacy live-registry APIs: no direct `get_published_data()` observed in core execute path
- File / external IO performed: secrets/annotation related IO and policy handling

### 3. Classification
- Snapshot-friendly now?: no (too broad as-is)
- Uses shared-state authority semantics?: indirectly, through oversized ambient context dependency
- Requires main-interpreter commit authority?: yes for `normalized_rows` visibility
- Suitable as representative migration anchor? Why?: yes; it is the central compile-stage bottleneck and highest-value decomposition target.

### 4. Target snapshot contract
- Minimal required input payloads:
  - instance bindings
  - committed object/class views needed for row shaping
  - annotation resolver outputs
  - secrets/config policy inputs
- Required `consumes` keys:
  - `row_annotations_by_instance`
  - `object_secret_annotations`
  - `annotation_formats`
- Candidate `input_view`: separate views per decomposed plugin, not one giant snapshot
- Data that must NOT be passed through snapshot:
  - unrelated full context payloads not needed by the active sub-step

### 5. Target envelope contract
- Published messages expected in envelope:
  - eventually one or more of:
    - resolved annotations / secrets output
    - normalized rows
    - semantic/shape validation payloads or summaries
- Emitted events expected in envelope: optional only
- `PluginResult.output_data` that should remain semantic-only:
  - diagnostic summaries
- Which payloads require main-interpreter validation before commit:
  - `normalized_rows` shape and schema
  - stage-local vs pipeline-shared scope if intermediate split outputs are introduced

### 6. Migration actions
- Decompose into at least three plugins:
  1. annotation/secret resolution
  2. row normalization
  3. semantic/shape validation
- Narrow each sub-plugin snapshot contract
- Keep `normalized_rows` as committed output of the normalization step only
- Reduce dependence on large ambient context slices
- Manifest/schema changes needed?: likely yes, with explicit `consumes`/`produces` per sub-step; `input_view` likely valuable here first

### 7. Test plan
- Plugin unit tests:
  - one suite per decomposed sub-plugin
- Worker runner tests:
  - normalization and validation envelopes serialize correctly
- Pipeline state tests:
  - committed `normalized_rows` visibility and stage-local cleanup if applicable
- Scheduler/integration tests:
  - downstream validators receive committed rows through consume resolution
- Serial vs subinterpreter parity tests:
  - same committed rows / same diagnostics

### 8. Exit criteria
- Responsibilities split across smaller plugins
- `normalized_rows` committed through main interpreter, not ambient shared context
- Snapshot size reduced relative to current monolith
- Downstream validators consume committed outputs only

### Quick risk rubric
- Ambient state mutation risk: Medium
- Snapshot size risk: Very High
- IO coupling risk: High
- Downstream contract blast radius: Very High
- Test migration effort: High
- Recommended rollout order: Wave 3B


---

## Audit 4 — Representative declarative validator (`base.validator.dns_refs` via `DeclarativeReferenceValidator`)

### 1. Plugin identity
- Plugin ID: representative family entry `base.validator.dns_refs` (same implementation also used by `base.validator.certificate_refs`, `base.validator.backup_refs`, `base.validator.network_core_refs`, `base.validator.service_dependency_refs`, `base.validator.power_source_refs`)
- File: `topology-tools/plugins/validators/declarative_reference_validator.py`
- Family: validator_json
- Stage: validate
- Phase: run
- Current manifest routing fields:
  - `subinterpreter_compatible`: true for representative entries
  - `execution_mode`: not declared
  - `consumes`: `base.compiler.instance_rows.normalized_rows`
  - `produces`: none

### 2. Current runtime behavior
- Reads from `ctx.subscribe(...)`: yes (`normalized_rows`)
- Reads from ambient context: yes, but limited (`ctx.objects` for some rule resolution)
- Writes via `ctx.publish(...)`: no
- Directly mutates ambient context: no
- Uses legacy live-registry APIs: no
- File / external IO performed: none significant in execute path

### 3. Classification
- Snapshot-friendly now?: yes/partial
- Uses shared-state authority semantics?: no meaningful authority mutation
- Requires main-interpreter commit authority?: mostly no, except for diagnostics/result aggregation as standard runtime behavior
- Suitable as representative migration anchor? Why?: yes; this is the best current exemplar of the target plugin mental model: resolved input, local indexes, deterministic diagnostics.

### 4. Target snapshot contract
- Minimal required input payloads:
  - `normalized_rows`
  - object lookup view for rules that require object/property fallback
  - validator config / enabled rules
- Required `consumes` keys:
  - `base.compiler.instance_rows.normalized_rows`
- Candidate `input_view`: `normalized_rows_plus_object_index`
- Data that must NOT be passed through snapshot:
  - live published registry
  - unrelated compile/generate state

### 5. Target envelope contract
- Published messages expected in envelope: none required
- Emitted events expected in envelope: none required initially
- `PluginResult.output_data` that should remain semantic-only:
  - diagnostics/result summary only
- Which payloads require main-interpreter validation before commit:
  - no special published payload validation needed because validator is result-centric

### 6. Migration actions
- Replace ambient `ctx.objects` dependency with explicit object-view snapshot where needed
- Keep validator result purely diagnostic and deterministic
- Use as reference implementation for future validator SDK migration
- Manifest/schema changes needed?: eventually adopt `execution_mode`; `input_view` may be useful for keeping snapshots narrow

### 7. Test plan
- Plugin unit tests:
  - snapshot-driven rule execution with envelope/result assertions
- Worker runner tests:
  - serial/subinterpreter identical diagnostics for same snapshot
- Pipeline state tests:
  - minimal/no commit expectations beyond result handling
- Scheduler/integration tests:
  - consume resolution for `normalized_rows`
- Serial vs subinterpreter parity tests:
  - same diagnostics / same status

### 8. Exit criteria
- No reliance on ambient `PluginContext` beyond snapshot-backed facade
- Validator can run from snapshot-only inputs
- Acts as canonical “good style” validator for future migrations

### Quick risk rubric
- Ambient state mutation risk: Low
- Snapshot size risk: Low/Medium
- IO coupling risk: Low
- Downstream contract blast radius: Medium
- Test migration effort: Low/Medium
- Recommended rollout order: Wave 3A

---

## Audit 5 — Representative generator (`base.generator.effective_json`)

### 1. Plugin identity
- Plugin ID: `base.generator.effective_json`
- File: `topology-tools/plugins/generators/effective_json_generator.py`
- Family: generator
- Stage: generate
- Phase: run (family contract)
- Current manifest routing fields:
  - `subinterpreter_compatible`: not confirmed in extracted snippet, but generator family is already treated as subinterpreter-ready in parts of manifest
  - `execution_mode`: not declared
  - `consumes`: implicit via `ctx.compiled_json`
  - `produces`: generated artifact path keys via `ctx.publish(...)`

### 2. Current runtime behavior
- Reads from `ctx.subscribe(...)`: no
- Reads from ambient context: yes (`ctx.compiled_json`, `ctx.compiled_file`, `ctx.output_dir`)
- Writes via `ctx.publish(...)`: yes (`generated_files`, `effective_json_path`)
- Directly mutates ambient context: no
- Uses legacy live-registry APIs: no
- File / external IO performed: yes, writes JSON artifact to filesystem

### 3. Classification
- Snapshot-friendly now?: yes/partial
- Uses shared-state authority semantics?: indirectly through ambient authoritative `ctx.compiled_json`
- Requires main-interpreter commit authority?: yes for artifact publication metadata, but not for file write computation itself
- Suitable as representative migration anchor? Why?: yes; it is the simplest generator proving that generators can consume committed compiled-model snapshot and return artifact publications through envelope.

### 4. Target snapshot contract
- Minimal required input payloads:
  - committed compiled model payload
  - output path metadata
  - generator config
- Required `consumes` keys:
  - committed compiled model (either explicit consume or committed snapshot view)
- Candidate `input_view`: `compiled_model_generation_view`
- Data that must NOT be passed through snapshot:
  - unrelated publish registry
  - unrelated topology views

### 5. Target envelope contract
- Published messages expected in envelope:
  - `generated_files`
  - `effective_json_path`
- Emitted events expected in envelope: optional generation telemetry only
- `PluginResult.output_data` that should remain semantic-only:
  - path summary
- Which payloads require main-interpreter validation before commit:
  - artifact publication keys / generated-files payload contract

### 6. Migration actions
- Replace ambient `ctx.compiled_json` dependency with committed snapshot input
- Keep filesystem write in local execution
- Commit published artifact metadata only through envelope + `PipelineState`
- Use as first generator reference before migrating richer generators such as `ansible_inventory`
- Manifest/schema changes needed?: eventually explicit `execution_mode`; possible explicit compiled-model consume declaration if not already represented elsewhere

### 7. Test plan
- Plugin unit tests:
  - snapshot with compiled model -> envelope with artifact path publications
- Worker runner tests:
  - generator envelope survives serial/subinterpreter path
- Pipeline state tests:
  - artifact publication metadata committed only after envelope validation
- Scheduler/integration tests:
  - downstream consumers can resolve committed artifact path publications
- Serial vs subinterpreter parity tests:
  - identical generated metadata and successful status

### 8. Exit criteria
- Generator consumes committed compiled-model snapshot only
- Published artifact metadata is committed by main interpreter, not exposed via worker-owned live registry
- Acts as first generator proof for snapshot/envelope/commit runtime

### Quick risk rubric
- Ambient state mutation risk: Low
- Snapshot size risk: Medium
- IO coupling risk: Medium
- Downstream contract blast radius: Medium
- Test migration effort: Low/Medium
- Recommended rollout order: Wave 3A

