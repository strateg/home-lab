# ADR 0095 Optimization Implementation Plan

**Status:** Completed (all waves 0-E delivered)
**Date:** 2026-04-12
**Completion Date:** 2026-04-13
**Scope:** Implement the approved ADR0095 optimization directions:
- internal modularization,
- question-oriented inspection surface,
- compact-vs-detailed output contract,
- machine-readable outputs,
- semantic relation typing.

---

## 1. Planning Objective

Deliver the next iteration of ADR0095 as a controlled sequence that:
- preserves the canonical CLI and `task inspect:*` contract,
- improves dependency, inheritance, and capability traceability,
- increases information density while keeping default human output compact,
- expands machine-readable inspection support,
- reduces implementation risk through explicit validation gates.

---

## 1A. Tech Lead Critique of the Current Optimization Plan

The original optimization plan is directionally correct, but too permissive in three places:
- it does not force a baseline contract lock before refactor + feature growth;
- it treats semantic relation typing as a single-step feature instead of a staged compatibility problem;
- it does not define compatibility rules for command names, output modes, and JSON schemas.

To make the plan executable rather than aspirational, it needs:
- a Wave 0 readiness/baseline-lock phase,
- explicit compatibility policy,
- explicit JSON versioning rules,
- explicit shadow-mode phase for typed relations,
- explicit first implementation package.

---

## 2. Implementation Workstreams

| Workstream | Goal | Depends On |
|---|---|---|
| WS1 | Refactor internal implementation boundaries | current monolith baseline |
| WS2 | Introduce question-oriented inspection surface | WS1 recommended, current CLI baseline minimum |
| WS3 | Introduce compact-vs-detailed output discipline | WS1 recommended, WS2 partial |
| WS4 | Introduce machine-readable output contracts | WS1 recommended, WS2/WS3 partial |
| WS5 | Introduce semantic relation typing | WS1 recommended, current dependency model baseline |
| WS6 | Expand validation and test coverage | all workstreams |
| WS7 | Synchronize ADR/docs/status artifacts | all workstreams |

---

## 2A. Compatibility Policy

Implementation MUST preserve:
- canonical CLI path: `scripts/inspection/inspect_topology.py`
- public task namespace: `task inspect:*`
- current baseline commands as stable commands or documented aliases

Implementation MAY add:
- new focused commands,
- explicit detail flags,
- explicit JSON mode,
- new machine-readable export paths

Implementation MUST NOT:
- silently repurpose an existing command with incompatible semantics,
- mix JSON output into default human-readable output,
- introduce typed relations as the only supported interpretation in the first rollout.

---

## 3. Wave Structure

### Wave 0 — Baseline Lock and Readiness

Primary objective:
- make the existing surface mechanically safe to change.

Tasks:
- execute PR-R0 from `REFACTORING-PLAN.md`
- record which current gates are already implemented vs still unchecked in docs
- add initial readiness checklist for the first implementation package

Acceptance:
- baseline command behavior is pinned by tests/smoke coverage
- implementation docs no longer drift from verified baseline state

---

### Wave A — Stabilize Baseline and Refactor Internals

Primary objective:
- make current implementation safer to extend without changing operator-visible contracts.

Tasks:
- execute `REFACTORING-PLAN.md` phases R1-R5
- add direct tests for loaders, indexes, and dependency extractor
- add smoke coverage for all current inspect commands

Acceptance:
- canonical CLI unchanged
- all current inspect tasks still work
- baseline output contracts preserved unless explicitly documented

---

### Wave B — Add Question-Oriented Inspection Surface

Primary objective:
- evolve from entity-dump dominant surface to question-oriented inspection.

Planned command domains:

| Domain | Intent |
|---|---|
| overview | high-signal counts and grouped summaries |
| inheritance / lineage | class parent-child and lineage traceability |
| dependency trace | outgoing/incoming/transitive relations |
| capability trace | class/object/pack capability relations |
| export | machine-readable / graph export surfaces |

Tasks:
- define which current commands remain stable as baseline compatibility commands
- add inheritance-focused inspection surface
- add unified capability inspection surface
- document compatibility/deprecation policy if aliases are introduced

Acceptance:
- inheritance becomes inspectable without relying only on `classes`
- capability traceability becomes inspectable across class/object/pack layers
- current baseline commands remain available or intentionally aliased

---

### Wave C — Compact-vs-Detailed Output Contract

Primary objective:
- make default output compact and high-signal while preserving deeper trace paths.

Tasks:
- define compact output invariants per command family
- define explicit detailed mode(s)
- separate overview output from full trace output
- ensure machine-readable outputs are not mixed into compact human output by default

Suggested compactness targets for default human-facing output:
- `summary`: remain short overview form
- `classes`: keep focused tree view
- `objects` and `instances`: move away from raw full-dump default behavior
- relation-focused commands: show highest-signal rows first and require explicit detail expansion for full dumps

Acceptance:
- default outputs prioritize significant relationships first
- large-list commands no longer rely only on raw dump-style rendering
- output contract is documented and tested

---

### Wave D — Machine-Readable Outputs

Primary objective:
- expose stable structured output contracts for automation and downstream tooling.

Priority JSON domains:
- overview summaries
- dependency traceability
- inheritance / lineage
- capability relations

Tasks:
- define JSON schemas / stable output structure
- add `--json` or equivalent explicit structured mode
- add fixture-based tests for JSON contract stability

JSON contract requirements:
- explicit schema/version field,
- deterministic field ordering where practical,
- no mixing of human-readable commentary into JSON payloads,
- command-family-specific payload structure rather than one overloaded mega-schema.

Acceptance:
- structured output is deterministic
- human-readable and machine-readable paths are explicitly separated
- JSON contracts are documented in ADR0095 analysis artifacts

---

### Wave E — Semantic Relation Typing

Primary objective:
- reduce ambiguity of current syntax-only relation extraction.

Target relation domains:
- network
- storage
- runtime / host-placement
- capability
- inheritance / binding

Tasks:
- define typed relation model
- introduce typed extraction first in shadow/parallel mode over the current heuristic baseline
- validate typed relations on current home-lab topology
- retain unresolved relation diagnostics where semantics are incomplete

Shadow-mode intent:
- keep current heuristic path available during rollout,
- compare typed vs heuristic results before any default semantic promotion,
- avoid silent traceability regressions.

Acceptance:
- semantic relation categories are documented
- typed relation extraction is validated on home-lab topology
- dependency traceability becomes less ambiguous than pure `_ref/_refs` scanning

---

## 4. Recommended Execution Order

| Order | Wave / Workstream | Reason |
|---|---|---|
| 1 | Wave 0 / readiness lock | Prevents uncontrolled refactor/feature drift |
| 2 | Wave A / WS1 + WS6 | Reduces extension risk before surface expansion |
| 3 | Wave B / inheritance and capability surfaces | Addresses the largest current coverage gaps |
| 4 | Wave C / compact-vs-detailed contract | Prevents new surfaces from defaulting to raw dumps |
| 5 | Wave D / machine-readable outputs | Stabilizes structured automation contract after surface shape is clearer |
| 6 | Wave E / semantic relation typing | Builds on refactored and better-tested extractor foundations |
| 7 | WS7 / ADR-doc synchronization after each wave | Keeps planning and implementation state aligned |

---

## 5. PR-Sized Delivery Plan

| PR | Scope | Validation Minimum |
|---|---|---|
| PR-0 | Lock current inspect command contracts and smoke matrix | targeted pytest + full current inspect smoke |
| PR-1 | Refactor loaders/indexes | targeted pytest + current inspect smoke |
| PR-2 | Refactor relation extraction | extractor tests + deps smoke matrix |
| PR-3 | Refactor presenters / CLI thinning | command contract tests + full current inspect smoke |
| PR-4 | Add inheritance-focused inspection | targeted pytest + home-lab command smoke |
| PR-5 | Add unified capability inspection | targeted pytest + home-lab command smoke |
| PR-6 | Add compact/detailed output behavior | output contract tests + smoke matrix |
| PR-7 | Add JSON output for overview/deps with versioned schema | JSON contract tests + smoke matrix |
| PR-8 | Add JSON output for inheritance/capability domains with versioned schema | JSON contract tests + smoke matrix |
| PR-9 | Add semantic relation typing in shadow mode | typed-relation tests + comparison validation on home-lab |
| PR-10 | Reconcile ADR0095 docs, status checklists, and command reference | `task validate:adr-consistency` |
| PR-11 | Add typed-shadow promotion readiness diagnostics + fail-fast gate wiring | targeted pytest + `task validate:typed-shadow-readiness` + `task validate:typed-shadow-readiness-gate` |
| PR-12 | Expand inspect smoke matrix to cover typed-shadow dependency command path | targeted pytest + `task inspect:smoke-matrix` + `task validate:inspect-smoke` |
| PR-13 | Add inspect-namespace readiness fail-fast alias and extend smoke matrix with typed-shadow JSON path | targeted pytest + `task inspect:typed-shadow-readiness-gate` + `task validate:inspect-smoke` |
| PR-14 | Promote semantic relation typing to authoritative deps contract (keep compatibility aliases) | targeted pytest + smoke matrix + readiness/ADR consistency gates |

---

## 5A. First Implementation Package

The recommended first executable package is:
- PR-0 baseline lock
- PR-1 loader/index refactor

Reason:
- it reduces risk immediately,
- it does not force public-surface redesign,
- it creates the foundation needed for inheritance/capability views and JSON outputs.

This is the preferred starting point for implementation readiness.

---

## 6. Validation Plan

### 6.1 Baseline Smoke Matrix

Run repeatedly during the rollout:
- `task inspect:default`
- `task inspect:classes`
- `task inspect:objects`
- `task inspect:instances`
- `task inspect:search QUERY='mikrotik'`
- `task inspect:deps INSTANCE='rtr-mikrotik-chateau'`
- `task inspect:deps-dot`
- `task inspect:capability-packs`

### 6.2 New Test Families

| Test Family | Purpose |
|---|---|
| loader/path tests | manifest and catalog resolution stability |
| index/binding tests | class/object/instance normalized lookup stability |
| dependency extractor tests | outgoing/incoming/unresolved relation correctness |
| inheritance tests | parent-child / lineage contract stability |
| capability relation tests | class/object/pack relation correctness |
| output contract tests | compact vs detailed behavior |
| JSON contract tests | machine-readable stability |
| semantic relation tests | typed relation classification correctness |

---

## 6A. Readiness Checklist Before Coding

- [x] baseline smoke matrix recorded and repeatable (`task inspect:smoke-matrix`, `task validate:inspect-smoke`)
- [x] current unchecked plan items reconciled between docs and actual state
- [x] compatibility policy accepted for baseline command names
- [x] JSON versioning rule accepted before first machine-readable PR
- [x] semantic relation typing rollout accepted as shadow-first, not default-first
- [x] first PR scope limited to refactor-safe work

---

## 7. Documentation / ADR Synchronization Plan

As implementation lands, keep these artifacts synchronized:
- `adr/0095-topology-inspection-and-introspection-toolkit.md`
- `adr/0095-analysis/GAP-ANALYSIS.md`
- `adr/0095-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0095-analysis/SWOT-ANALYSIS.md`
- `adr/0095-analysis/REFACTORING-PLAN.md`
- `adr/0095-analysis/OPTIMIZATION-IMPLEMENTATION-PLAN.md`

Additionally:
- update manual/operator command reference when inspect family expands
- update `adr/REGISTER.md` only if ADR0095 status wording changes

---

## 8. Completion Criteria

The optimization implementation track is complete when:
- current monolith concerns are internally modularized,
- inheritance traceability has a dedicated inspection surface,
- capability inspection spans class/object/pack descriptive layers,
- compact-vs-detailed output contract is explicit,
- machine-readable outputs exist for the stabilized priority domains,
- semantic relation typing is validated on home-lab topology,
- test coverage extends materially beyond the current single inspect test,
- ADR0095 artifacts reflect actual implemented state.

---

## 9. Explicit Non-Goals

This plan does **not** require:
- changing the source-of-truth topology model,
- changing deploy/runtime contracts outside inspection scope,
- replacing the canonical CLI path,
- dropping the public `task inspect:*` namespace,
- introducing write-capable or online inspection behavior.
