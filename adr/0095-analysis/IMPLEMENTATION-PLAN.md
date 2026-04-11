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

- [ ] `task inspect:default` works
- [ ] `task inspect:classes` works
- [ ] `task inspect:objects` works
- [ ] `task inspect:instances` works
- [ ] `task inspect:search QUERY='mikrotik'` works
- [ ] `task inspect:deps INSTANCE='rtr-mikrotik-chateau'` works
- [ ] `task inspect:deps-dot` generates DOT file
- [ ] `task inspect:capability-packs` shows pack catalog + class/object dependency bindings

## Wave 2 — Task UX and Docs

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 2.1 | Add `taskfiles/inspect.yml` namespace | Commands available via `task --list` |
| 2.2 | Wire include in root `Taskfile.yml` | `task inspect:default` resolves in root |
| 2.3 | Update command reference manual | Inspect command family documented |
| 2.4 | Register ADR0095 | `adr/REGISTER.md` has canonical row |

### Wave 2 Gate

- [ ] Manual includes inspect command section
- [ ] ADR register updated

## Wave 3 — Hardening (Next Iteration)

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 3.1 | Add `--json` machine-readable output | Structured output contract stabilized |
| 3.2 | Add layer/group filters | Scoped inspection for large projects |
| 3.3 | Add semantic edge typing | Reduced false positives/negatives |
| 3.4 | Add tests for dependency extractor | Stable behavior on known fixtures |

### Wave 3 Gate

- [ ] JSON output contract documented
- [ ] Filters and semantic edges validated on home-lab topology
