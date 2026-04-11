# ADR 0095 IMPLEMENTATION PLAN

**Last updated:** 2026-04-11

## Wave 1 — Baseline Toolkit

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 1.1 | Add `scripts/inspection/inspect_topology.py` | Script returns summary on valid effective JSON |
| 1.2 | Implement class/object/instance views | Commands print deterministic tree/group output |
| 1.3 | Implement search mode | Regex query returns matching instances |
| 1.4 | Implement dependency extraction | `deps` shows direct/incoming/transitive refs |
| 1.5 | Implement DOT export | `deps-dot` writes graph under `build/diagnostics/` |
| 1.6 | Implement capability-pack inspection | `capability-packs` shows `class -> packs -> objects` matrix and contract warnings |

### Wave 1 Gate

- [x] `task inspect:default` works
- [x] `task inspect:classes` works
- [x] `task inspect:objects` works
- [x] `task inspect:instances` works
- [x] `task inspect:search QUERY='mikrotik'` works
- [x] `task inspect:deps INSTANCE='rtr-mikrotik-chateau'` works
- [x] `task inspect:deps-dot` generates DOT file
- [x] `task inspect:capability-packs` shows pack catalog + class/object dependency bindings

## Wave 2 — Task UX and Docs

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 2.1 | Add `taskfiles/inspect.yml` namespace | Commands available via `task --list` |
| 2.2 | Wire include in root `Taskfile.yml` | `task inspect:default` resolves in root |
| 2.3 | Update command reference manual | Inspect command family documented |
| 2.4 | Register ADR0095 | `adr/REGISTER.md` has canonical row |

### Wave 2 Gate

- [x] Manual includes inspect command section
- [x] ADR register updated

## Wave 3 — Hardening (Execution in progress)

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 3.0 | Reconcile ADR0095 analysis/status with actual v1 baseline | ADR, gap analysis, plan, and SWOT reflect current implemented surface |
| 3.1 | Add `--json` machine-readable output | Structured output contract stabilized (`summary`, `deps`, `inheritance`, `capabilities`) |
| 3.2 | Add layer/group filters | Scoped inspection for large projects (`summary`, `instances`, `search`, `deps`, `deps-dot`) |
| 3.3 | Add semantic edge typing | Shadow-mode typed relation classification for `deps` without replacing baseline extractor |
| 3.4 | Add tests for dependency extractor | Stable behavior on known fixtures |
| 3.5 | Add inheritance-focused inspection surface | Dedicated lineage/inheritance questions are inspectable without relying only on `classes` tree |
| 3.6 | Add unified capability inspection surface | Class/object/pack capability relations become inspectable through one coherent domain surface |
| 3.7 | Introduce compact-vs-detailed output contract | Default output remains compact while detailed and machine-readable paths stay explicit |
| 3.8 | Refactor internal inspection code into reusable concerns | Canonical CLI remains stable while loaders/indexes/extractors/formatters are separated internally |
| 3.9 | Add typed-shadow diagnostics artifacts and threshold gate | `typed-shadow-report.{json,txt}` artifacts are generated and gate mode can fail on threshold mismatch |

### Wave 3 Gate

- [x] ADR0095 docs reflect actual v1 baseline and v2 optimization direction
- [x] JSON output contract documented
- [x] Layer/group filters validated on home-lab topology
- [x] Semantic edge typing shadow-mode validated on home-lab topology
- [x] Inheritance-focused inspection validated on home-lab topology
- [x] Unified capability inspection validated on home-lab topology
- [x] Compact-vs-detailed output behavior documented and covered by tests
- [x] Internal modularization preserves canonical CLI and `task inspect:*` contracts
- [x] Typed-shadow diagnostics artifacts and threshold gate are wired (`task inspect:typed-shadow-report`, `task inspect:typed-shadow-gate`)

## Current Execution Snapshot (2026-04-11)

Completed waves/PR-sized slices:
- PR-0 baseline command contract lock + error paths.
- PR-1 loader/index extraction.
- PR-2 relation extraction.
- PR-3 presenter/export extraction.
- PR-4 inheritance-focused inspection surface.
- PR-5 unified capability inspection surface.
- PR-6 compact vs detailed output contract (`objects`, `instances`).
- PR-7 JSON contracts for `summary` and `deps`.
- PR-8 JSON contracts for `inheritance` and `capabilities`.
- PR-9 semantic typed relation shadow for `deps` (`--typed-shadow`).
- PR-10 typed-shadow diagnostics artifacts + threshold gate (`task inspect:typed-shadow-report`, `task inspect:typed-shadow-gate`).
- PR-11 semantic typing heuristic expansion (network/runtime/storage/binding coverage) with G2 gate pass on current home-lab topology (`coverage=100.0`, `generic_ref_share=0.72`).
- PR-12 typed-shadow parity guard tests ensuring baseline `deps` edge sets remain unchanged when typed shadow is enabled.

Outstanding from Wave 3:
- semantic typing promotion decision beyond shadow mode (keep as non-authoritative shadow until promotion criteria are approved).

Promotion criteria artifact:
- `adr/0095-analysis/SEMANTIC-TYPING-PROMOTION-CRITERIA.md`
