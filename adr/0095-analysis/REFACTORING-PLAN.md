# ADR 0095 Refactoring Plan — Current Inspection Implementation

**Status:** Proposed planning artifact  
**Date:** 2026-04-11  
**Scope:** Refactor the current `scripts/inspection/inspect_topology.py` implementation without changing the canonical CLI or `task inspect:*` public contract.

---

## 1. Objective

Refactor the current inspection implementation to:
- reduce concern concentration in one file,
- preserve the canonical CLI entrypoint,
- preserve the stable `task inspect:*` surface,
- make subsequent feature work (inheritance, unified capability inspection, JSON outputs, typed relations, compact/detailed rendering) mechanically safer.

This plan is explicitly **refactor-first for structure**, not a behavior rewrite.

---

## 1A. Tech Lead Critique of the Current Refactoring Plan

The baseline refactoring direction is valid, but in its current form it is not yet strong enough for safe execution.

Critical gaps in the original plan:
- it starts extraction work before fully locking current command behavior;
- it defines target modules, but not their allowed dependency directions;
- it assumes presenter extraction can preserve parity, but does not define what “parity” means;
- it does not identify stop conditions for unsafe refactors;
- it does not explicitly separate “structural refactor” from “surface change” PRs.

Refactoring will be safer if it is treated as:
1. contract lock,
2. mechanical extraction,
3. parity verification,
4. only then feature work.

---

## 2. Baseline

Current implementation facts:
- canonical CLI: `scripts/inspection/inspect_topology.py`
- file size: 578 lines
- top-level functions: 22
- public subcommands: `summary`, `classes`, `objects`, `instances`, `search`, `deps`, `deps-dot`, `capability-packs`
- direct dedicated inspect test coverage: 1 test (`tests/test_inspect_topology.py`)

Current concerns combined in one module:
- artifact loading
- YAML loading / manifest path resolution
- capability-pack catalog loading
- alias/index construction
- dependency extraction
- object/class binding helpers
- human-readable rendering
- DOT export
- CLI parsing / dispatch

---

## 3A. Non-Negotiable Refactoring Invariants

The refactoring track MUST preserve the following:
- same canonical CLI path;
- same task namespace;
- same default data source;
- same exit-code semantics for existing commands unless explicitly documented later;
- same human-readable baseline command availability;
- no new architectural truth outside ADR0095 artifacts.

The refactoring track MUST NOT:
- combine internal extraction with large feature expansion in the same PR;
- silently change output shape for existing commands;
- introduce helper-module cycles;
- make presenters read files directly;
- make relation extractors depend on CLI parser concerns.

---

## 3. Refactoring Constraints

Must preserve:
- `scripts/inspection/inspect_topology.py` as canonical entrypoint
- `task inspect:*` as the stable operator contract
- default input `build/effective-topology.json`
- read-only inspection behavior
- deterministic output semantics unless explicitly changed in a later feature phase

Must not do in the refactoring wave:
- replace the public CLI contract
- introduce topology model changes
- introduce generated-file edits
- mix refactoring with large untested feature expansion

---

## 4A. Target Internal Dependency Rules

Recommended internal dependency direction:

| Layer | May Depend On | Must Not Depend On |
|---|---|---|
| CLI wiring | loaders, indexes, relations, presenters, export | none of the helper layers may depend back on CLI |
| loaders | stdlib / yaml / filesystem helpers | presenters, CLI parser |
| indexes | normalized payload structures, stdlib | presenters, CLI parser, filesystem path resolution beyond loader APIs |
| relations | indexes, normalized payload structures | presenters, CLI parser |
| presenters | indexes, relations, normalized state | direct filesystem loading, CLI parser |
| export | indexes, relations, normalized state | presenters, CLI parser |

This rule set is intended to prevent the refactor from simply moving code around without reducing coupling.

---

## 4. Target Internal Layout

Recommended internal concern split under `scripts/inspection/`:

| Module / Concern | Responsibility | Source Moved From |
|---|---|---|
| `inspect_topology.py` | CLI parser, command dispatch, backwards-compatible entrypoint | current monolith |
| `inspection_loader.py` | effective-topology loading, repo-root resolution, manifest/path resolution, YAML loading | `_load_effective`, `_repo_root`, `_resolve_existing_path`, `_load_yaml`, `_load_capability_pack_catalog` |
| `inspection_indexes.py` | flattened instance index, alias maps, class/object binding indexes | `_flatten_instances`, `_source_aliases`, `_object_class_ref`, derived grouped indexes |
| `inspection_relations.py` | ref scanning, normalization, dependency extraction, unresolved relation handling | `_iter_refs`, `_normalize_ref_values`, `_build_dependency_graph`, `_resolve_instance_id` |
| `inspection_presenters.py` | human-readable compact renderers for summary/classes/objects/instances/search/deps/capability-packs | `_print_*` functions |
| `inspection_export.py` | DOT export and future JSON exports | `_write_dot` and later JSON serializers |

The exact filenames are adjustable; the concern boundaries are the important planning contract.

---

## 5A. PR-0 Contract Lock Before Refactoring

Before extraction starts, add a baseline lock PR that captures current behavior.

Required baseline lock areas:
- command smoke matrix for all existing commands,
- fixture-based tests for current dependency extraction behavior,
- fixture-based tests for current class tree / object grouping stability,
- fixture-based tests for current exit behavior when effective topology is missing,
- fixture-based tests for capability-pack inspection warnings and happy path.

Without this PR-0, later parity claims remain too weak.

---

## 5. Refactoring Sequence

### Phase R1 — Lock Baseline Contracts

Add baseline tests and smoke assertions before internal extraction.

**Expected result:** current behavior is mechanically pinned before code motion starts.

### Phase R2 — Extract Loaders and Path Resolution

Move to a dedicated loader module:
- effective JSON loading,
- repo-root resolution,
- path resolution,
- YAML loading,
- capability-pack catalog loading.

**Expected result:** CLI file no longer owns filesystem/path/catalog mechanics.

### Phase R3 — Extract Normalized Indexes

Create reusable normalized builders for:
- flattened instances,
- alias resolution,
- object→class binding,
- class→objects grouping.

**Expected result:** later views no longer recompute basic relations ad hoc.

### Phase R4 — Extract Relation Logic

Move relation mechanics into dedicated extractor layer:
- `_ref/_refs` scanning,
- normalized ref values,
- dependency graph extraction,
- unresolved ref collection,
- instance reference resolution.

**Expected result:** dependency behavior becomes testable independently of CLI rendering.

### Phase R5 — Extract Presenters / Output Formatting

Move human-readable rendering into dedicated presenters:
- overview summary
- class tree
- object grouping
- instance grouping
- search result rendering
- dependency rendering
- capability-pack rendering

**Expected result:** output changes can be evolved independently from data collection.

### Phase R6 — Reduce CLI File to Wiring Layer

Leave `inspect_topology.py` responsible for:
- argument parsing,
- loading normalized state,
- delegating to relation/presenter/export helpers,
- exit-code handling.

**Expected result:** canonical entrypoint remains stable but becomes structurally thin.

---

## 6. Refactoring PR Breakdown

| PR | Scope | Expected Size | Validation Minimum |
|---|---|---|---|
| PR-R0 | Lock baseline contracts before code motion | Medium | targeted pytest + full current inspect smoke matrix |
| PR-R1 | Extract loader/path utilities | Small | `py_compile`, loader tests, baseline smoke |
| PR-R2 | Extract indexes and binding helpers | Small | targeted pytest for indexes + baseline smoke |
| PR-R3 | Extract dependency relation logic | Medium | relation/extractor tests + baseline smoke |
| PR-R4 | Extract presenters and keep output parity | Medium | command-output contract tests + baseline smoke |
| PR-R5 | Thin CLI dispatcher cleanup | Small | full inspect command smoke matrix + targeted pytest |

---

## 7. Refactoring Validation Matrix

| Refactor Area | Required Validation |
|---|---|
| loader/path extraction | targeted pytest for loader resolution + existing inspect CLI test |
| index extraction | fixture-based index contract tests |
| relation extraction | dependency extractor contract tests |
| presenter extraction | command-output contract tests for unchanged baseline commands |
| CLI thinning | smoke run of all current commands on home-lab effective topology |

Minimum smoke matrix after each major PR:
- `summary`
- `classes`
- `objects`
- `instances`
- `search --query mikrotik`
- `deps --instance rtr-mikrotik-chateau`
- `deps-dot`
- `capability-packs`

---

## 7A. Stop Conditions

Pause the refactoring track if any of the following occurs:
- baseline command output changes without an intentional contract note;
- helper modules begin importing each other cyclically;
- presenter extraction requires filesystem loading to preserve output;
- relation logic changes are introduced in the same PR as structural extraction without dedicated tests;
- compatibility of `task inspect:*` aliases becomes unclear.

These are indicators that the track is drifting from “refactor safely” toward “rewrite without control”.

---

## 8. Refactoring Completion Criteria

The refactoring track is complete when:
- canonical CLI path is unchanged,
- `task inspect:*` contract is unchanged,
- public baseline commands still execute,
- core inspection concerns are separated into reusable internal modules,
- dependency extraction is directly testable outside CLI dispatch,
- presenter/output logic is directly testable outside extraction logic.

---

## 9. Explicit Non-Goals of Refactoring Track

This refactoring plan does **not** by itself deliver:
- new question-oriented commands,
- new JSON outputs,
- semantic relation typing,
- inheritance-focused command surface,
- unified capability inspection,
- compact/detailed UX redesign.

Those belong to the implementation roadmap built on top of this refactored baseline.
