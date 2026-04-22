# Implementation Plan

**Date:** 2026-04-22
**Source:** SPC Analysis `PROJECT-STATE-ASSESSMENT-2026-04-22.md`
**Status:** Approved
**Analyst:** Claude Code (claude-opus-4-5-20251101)

---

## Approved Roadmap

```
PHASE 1: HOUSEKEEPING (Track A) .............. APPROVED
PHASE 2: QUALITY IMPROVEMENTS (Track B) ...... APPROVED
PHASE 3: HARDWARE ACTIVATION ................. PENDING DECISION
```

---

## Phase 1: Housekeeping (Track A)

**Status:** Approved
**Dependency:** None
**Effort:** Low

| ID | Action | Description | Verification |
|----|--------|-------------|--------------|
| A1 | Commit staged changes | Commit `.state/artifact-plans/*.json` with AI metadata | `git status` clean |
| A2 | Merge branch | Merge `implementation_imprvement` to `main` | Branch deleted |
| A3 | Investigate skipped tests | Analyze 4 skipped tests, fix or document | `pytest` 0 skipped or documented |
| A4 | Document plugin modes | Document rationale for 10 main_interpreter plugins | Documentation exists |

### A1: Commit Staged Changes

```bash
# Required commit message format (C-G04 compliance):
git commit -m "$(cat <<'EOF'
chore(state): update artifact plans for orangepi and proxmox bootstrap

Update artifact plan state files after generator execution.

AI-Agent: Claude Code (claude-opus-4-5-20251101)
AI-Tokens: <insert_actual_tokens>
EOF
)"
```

### A2: Merge Branch

```bash
git checkout main
git merge implementation_imprvement
git branch -d implementation_imprvement
git push origin main
git push origin --delete implementation_imprvement  # if remote exists
```

### A3: Investigate Skipped Tests

1. Run: `pytest tests -v --collect-only | grep -i skip`
2. For each skipped test:
   - If fixable → fix
   - If intentional → add `reason` parameter
   - If obsolete → remove

### A4: Document Plugin Modes

Create or update: `docs/guides/PLUGIN-EXECUTION-MODES.md`

Content outline:
- Why some plugins require `main_interpreter`
- List of 10 main_interpreter plugins with rationale
- Migration criteria for future plugins

---

## Phase 2: Quality Improvements (Track B)

**Status:** Approved
**Dependency:** Phase 1 complete (recommended, not blocking)
**Effort:** Medium

| ID | Action | Description | Verification |
|----|--------|-------------|--------------|
| B1 | Artifact cleanup task | Add `task build:cleanup-obsolete` | Task exists, runs clean |
| B2 | Coverage improvements | Add tests for low-coverage modules | Coverage increase |
| B3 | CI coverage threshold | Add coverage gate to CI | CI fails below threshold |

### B1: Artifact Cleanup Task

Add to `taskfiles/build.yml`:

```yaml
cleanup-obsolete:
  desc: Remove obsolete artifacts identified by artifact plans
  cmds:
    - "{{.PYTHON}} scripts/orchestration/cleanup_obsolete_artifacts.py"
```

Implementation approach:
1. Read `.state/artifact-plans/*.json`
2. Collect entries with `action: warn` and `reason: obsolete-shadowed`
3. Prompt for confirmation
4. Remove confirmed files

### B2: Coverage Improvements

Priority modules (current coverage < 50%):
- `topology-tools/utils/cutover-readiness-report.py` (37%)
- `topology-tools/utils/run-split-rehearsal.py` (35%)
- `topology-tools/utils/discover-hardware-identity.py` (46%)
- `topology-tools/verify-framework-lock.py` (0%)

### B3: CI Coverage Threshold

Add to `taskfiles/ci.yml` or pytest config:

```yaml
test:coverage-gate:
  desc: Fail if coverage drops below threshold
  cmds:
    - "{{.PYTHON}} -m pytest tests --cov --cov-fail-under=75"
```

---

## Phase 3: Hardware Activation (Pending Decision)

**Status:** Pending user decision
**Decision required:** Hardware availability

### Track C: Hardware E2E (if hardware available)

| ID | Action | Description | Effort |
|----|--------|-------------|--------|
| C1 | Obtain hardware access | Physical or remote access to devices | External |
| C2 | Implement NetinstallAdapter.execute() | MikroTik bootstrap automation | Medium |
| C3 | Implement UnattendedAdapter.execute() | Proxmox unattended install | Medium |
| C4 | Implement CloudInitAdapter.execute() | Orange Pi cloud-init | Medium |
| C5 | Hardware E2E validation | Run full bootstrap tests | High |
| C6 | Promote ADR0083 | Status: Proposed → Implemented | Low |
| C7 | Update project status | migration → operational | Low |

**Completion criteria:**
- All adapters execute without E9730
- Hardware E2E tests pass
- ADR0083 status = Implemented
- `topology.yaml` meta.status = operational

### Track D: Software-Only (if hardware unavailable)

| ID | Action | Description | Effort |
|----|--------|-------------|--------|
| D1 | Document deferral | Update ADR0083 with explicit deferral reason | Low |
| D2 | Virtualized environment | Create nested/emulated test environment | High |
| D3 | Partial validation | Run software-only validation tests | Medium |
| D4 | Update status | migration → validated-software | Low |

**Completion criteria:**
- ADR0083 deferral documented
- Virtualized tests pass where applicable
- `topology.yaml` meta.status = validated-software

---

## Decision Matrix for Phase 3

```
                     Hardware Available?
                    /                   \
                  YES                    NO
                   |                      |
              Track C                 Track D
                   |                      |
         ┌─────────┴─────────┐    ┌───────┴───────┐
         │ C1: Get access    │    │ D1: Document  │
         │ C2: Netinstall    │    │ D2: Virtualize│
         │ C3: Unattended    │    │ D3: Partial   │
         │ C4: CloudInit     │    │ D4: Status    │
         │ C5: E2E tests     │    └───────────────┘
         │ C6: ADR0083       │
         │ C7: Status        │
         └───────────────────┘
                   |                      |
              operational         validated-software
```

---

## Execution Checklist

### Phase 1 Checklist

- [ ] A1: `.state/` changes committed with AI metadata
- [ ] A2: Branch merged to main
- [ ] A3: Skipped tests investigated
- [ ] A4: Plugin modes documented

### Phase 2 Checklist

- [ ] B1: Cleanup task created and tested
- [ ] B2: Coverage increased for priority modules
- [ ] B3: CI coverage threshold configured

### Phase 3 Checklist (Track C)

- [ ] C1: Hardware access obtained
- [ ] C2: NetinstallAdapter.execute() implemented
- [ ] C3: UnattendedAdapter.execute() implemented
- [ ] C4: CloudInitAdapter.execute() implemented
- [ ] C5: Hardware E2E tests pass
- [ ] C6: ADR0083 promoted to Implemented
- [ ] C7: Project status updated to operational

### Phase 3 Checklist (Track D)

- [ ] D1: ADR0083 deferral documented
- [ ] D2: Virtualized environment created
- [ ] D3: Software-only validation complete
- [ ] D4: Project status updated to validated-software

---

## Validation Gates

| Gate | Trigger | Validation Command |
|------|---------|-------------------|
| Phase 1 Complete | All A* done | `task ci:local` |
| Phase 2 Complete | All B* done | `task ci:local` + coverage check |
| Phase 3 Complete | All C* or D* done | Full E2E or documented deferral |

---

## References

- Assessment: `docs/analysis/PROJECT-STATE-ASSESSMENT-2026-04-22.md`
- ADR0083 Analysis: `adr/0083-analysis/`
- ADR0097 (Subinterpreter): `adr/0097-subinterpreter-parallel-plugin-execution.md`
- Deploy Bundle Guide: `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`

---

## Metadata

```yaml
plan_date: 2026-04-22
plan_status: approved
phases:
  - id: 1
    name: Housekeeping
    track: A
    status: approved
    items: 4
  - id: 2
    name: Quality Improvements
    track: B
    status: approved
    items: 3
  - id: 3
    name: Hardware Activation
    track: C or D
    status: pending_decision
    items: 7 (C) or 4 (D)
```
