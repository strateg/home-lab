# ADR Next Steps — April 2026

**Date:** 2026-04-03
**Scope:** ADR execution plan with `0083` explicitly paused.

---

## Constraints

- `ADR 0083` is on hold (no implementation work in this cycle).
- Focus on closure/governance for `0086`, `0082`, `0053`, `0047`.

---

## Sprint 1 (Week 1)

### S1-1: Close ADR 0086 to Accepted

**Owner:** Architecture + Runtime maintainers
**ETA:** End of week 1
**Status:** `DONE` (2026-04-03)

**Tasks**
- Sync status in `adr/0086-analysis/MASTER-BOARD.md` with real completion state.
- Run final gates:
  - `python -m pytest tests/plugin_contract -q`
  - `python -m pytest tests/plugin_integration -q`
  - `python scripts/orchestration/lane.py validate-v5`
  - `python topology-tools/compile-topology.py`
  - `python topology-tools/compile-topology.py --no-parallel-plugins`
- Update `adr/0086-flatten-plugin-hierarchy-and-reduce-granularity.md` to `Accepted`.
- Update `adr/REGISTER.md`.

**Definition of Done**
- All listed gates pass.
- ADR + register status aligned (`Accepted`).
- Evidence references added in ADR analysis docs.

### S1-2: Promote ADR 0082 from Proposed to Accepted

**Owner:** Architecture
**ETA:** End of week 1
**Status:** `DONE` (2026-04-03)

**Tasks**
- Update `adr/0082-plugin-module-pack-composition-and-index-first-discovery-analysis.md`:
  - set status to `Accepted`,
  - lock target model: `Option A+`,
  - record growth gates for optional move to `Option C/B`.
- Update `adr/REGISTER.md`.

**Definition of Done**
- Decision is explicit and immutable in ADR text.
- Register reflects `Accepted`.

---

## Sprint 2 (Week 2)

### S2-1: Implement ADR 0082 Phase 1 (Index-First Hardening)

**Owner:** Runtime + CI
**ETA:** End of week 2
**Status:** `DONE` (2026-04-03)

**Tasks**
- Enforce authoritative `module-index.yaml` in production mode.
- Add CI checks:
  - all `plugins.yaml` on disk are present in index,
  - all index entries point to existing manifests,
  - schema/version validation for index.
- Extend tests (primary targets):
  - `tests/plugin_contract/test_manifest_discovery.py`
  - `tests/plugin_contract/test_framework_distribution_boundary.py` (if needed).

**Definition of Done**
- New/updated tests pass.
- Discovery fails fast on index/filesystem drift.

### S2-2: Resolve ADR 0053 Status

**Owner:** Architecture + Deploy
**ETA:** End of week 2
**Status:** `DONE` (2026-04-03)

**Decision Options**
- `Option A` (preferred if dist-first is obsolete): mark `Superseded` by ADR 0085.
- `Option B`: keep and narrow to explicit `native|dist` mode with parity gates.

**Tasks**
- Update `adr/0053-dist-first-deploy-cutover.md`.
- Update `adr/REGISTER.md`.
- Align deploy manuals if command contracts change.

**Definition of Done**
- No ambiguous status for ADR 0053 remains.
- Register and docs are consistent.

### S2-3: Keep ADR 0047 Trigger-Based With Active Monitoring

**Owner:** Observability + Architecture
**ETA:** End of week 2
**Status:** `DONE` (2026-04-03)

**Tasks**
- Keep implementation paused until trigger thresholds are hit.
- Add lightweight trigger check procedure:
  - alerts count threshold,
  - services count threshold.
- Document escalation path to start Phase 3/4 when threshold is exceeded.

**Definition of Done**
- Trigger policy documented and referenced.
- No active refactor started before thresholds.

### S2-4: Final ADR Governance Alignment

**Owner:** Architecture governance
**ETA:** End of week 2
**Status:** `DONE` (2026-04-03)

**Tasks**
- Run ADR consistency gate (script path is implementation-dependent):
  - verify ADR statuses are aligned across `adr/REGISTER.md` and individual ADR headers.
- Sync manuals/README with final ADR statuses and decisions.
- Publish final alignment summary in commit message.

**Definition of Done**
- Consistency check passes.
- Statuses are aligned across ADRs, register, and manuals.

---

## Tracking Table

| ID | Work Item | Owner | ETA | Status |
|----|-----------|-------|-----|--------|
| S1-1 | ADR 0086 -> Accepted | Architecture + Runtime | Week 1 | DONE (2026-04-03) |
| S1-2 | ADR 0082 -> Accepted | Architecture | Week 1 | DONE (2026-04-03) |
| S2-1 | ADR 0082 Phase 1 implementation | Runtime + CI | Week 2 | DONE (2026-04-03) |
| S2-2 | ADR 0053 status resolution | Architecture + Deploy | Week 2 | DONE (2026-04-03) |
| S2-3 | ADR 0047 trigger monitoring policy | Observability + Architecture | Week 2 | DONE (2026-04-03) |
| S2-4 | Final governance alignment | Architecture governance | Week 2 | DONE (2026-04-03) |

---

## Notes

- `ADR 0083` remains paused until explicit reactivation decision.
- If any sprint gate fails, stop status promotion and record rollback notes in the corresponding `adr/*-analysis/` directory.
