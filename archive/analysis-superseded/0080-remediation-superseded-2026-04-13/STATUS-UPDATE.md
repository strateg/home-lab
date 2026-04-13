# ADR 0080 Status Update

**Date**: 2026-04-13
**Reason**: Architectural improvement analysis identified implementation gaps
**Previous Status**: Accepted (2026-03-26)
**New Status**: Partially Implemented

---

## Status Change Justification

### Original ADR 0080 Acceptance Criteria

ADR 0080 defined:
1. 6-stage global model: `discover -> compile -> validate -> generate -> assemble -> build`
2. Universal phase model: `init -> pre -> run -> post -> verify -> finalize`
3. Plugin assignment to all 6 stages (Section 4.0-4.5)
4. Contractual plugin data bus with `produces`/`consumes` validation
5. Phase-aware execution lifecycle
6. Parallel execution safety

### Current Implementation Reality (2026-04-13)

**Implemented ✅**:
- Stage enum extended: `DISCOVER`, `COMPILE`, `VALIDATE`, `GENERATE`, `ASSEMBLE`, `BUILD`
- Phase enum defined: `INIT`, `PRE`, `RUN`, `POST`, `VERIFY`, `FINALIZE`
- Plugin kinds extended: `DISCOVERER`, `ASSEMBLER`, `BUILDER`
- Data bus (publish/subscribe) operational

**NOT Implemented ❌**:
- Phase-aware executor (runtime only uses DAG/order, not phases)
- Discover stage plugins (procedural `discover_plugin_manifests()` function)
- Assemble/build stage execution (runtime hardcoded to 3 stages only)
- PluginContext extensions for workspace_root, dist_root, assembly_manifest
- Smart plugin predicates (`when` evaluation)
- Parallel execution safety (race conditions in G19-G24)
- Artifact manifest plugin
- Diagnostic code ranges for new stages

### Gap Summary

**Total Implementation Debt**: 20+ components across 6 remediation waves

See `adr/0080-remediation/REMEDIATION-PLAN.md` for detailed gap analysis and implementation plan.

---

## Proposed ADR 0080 Status Update

### Current ADR Text (Lines 1-6)

```markdown
# ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus

- Status: Accepted
- Date: 2026-03-26
- Depends on: ADR 0005, ADR 0027, ADR 0028, ADR 0050, ADR 0051, ADR 0052, ADR 0055, ADR 0056, ADR 0063, ADR 0065, ADR 0066, ADR 0069, ADR 0071, ADR 0072, ADR 0074, ADR 0075, ADR 0076, ADR 0078, ADR 0079
```

### Proposed Update

```markdown
# ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus

- Status: Partially Implemented
- Date: 2026-03-26 (Accepted), 2026-04-13 (Status Update)
- Depends on: ADR 0005, ADR 0027, ADR 0028, ADR 0050, ADR 0051, ADR 0052, ADR 0055, ADR 0056, ADR 0063, ADR 0065, ADR 0066, ADR 0069, ADR 0071, ADR 0072, ADR 0074, ADR 0075, ADR 0076, ADR 0078, ADR 0079
- Implementation: See `adr/0080-remediation/REMEDIATION-PLAN.md` for completion plan
```

### Add New Section at End of ADR 0080

```markdown
---

## Implementation Status (2026-04-13)

**Status**: Partially Implemented

### Completed Components ✅

1. Stage enum extended to 6 stages (DISCOVER, COMPILE, VALIDATE, GENERATE, ASSEMBLE, BUILD)
2. Phase enum defined (INIT, PRE, RUN, POST, VERIFY, FINALIZE)
3. Plugin kinds extended (DISCOVERER, ASSEMBLER, BUILDER)
4. Data bus (publish/subscribe) operational

### Outstanding Components ❌

| Gap ID | Component | Wave | Priority |
|--------|-----------|------|----------|
| G1 | Discover stage plugins | Wave 3 | MEDIUM |
| G2 | PluginContext extensions | Wave 2 | HIGH |
| G3 | Phase-aware executor | Wave 1 | CRITICAL |
| G4 | `when` predicate evaluation | Wave 5 | MEDIUM |
| G5 | Diagnostic code ranges | Wave 6 | LOW |
| G6 | `base.generator.artifact_manifest` | Wave 6 | LOW |
| G19-G24 | Parallel execution safety | Wave 4 | CRITICAL |

**Total**: 20+ components across 6 remediation waves

### Remediation Plan

See `adr/0080-remediation/REMEDIATION-PLAN.md` for:
- Detailed gap analysis
- 6-wave implementation plan
- Validation strategy
- Risk mitigation
- Success criteria

**Timeline**: 6 weeks (30 working days)

**Critical Path**: Wave 1 (phase executor) → Wave 4 (parallel safety) → Wave 3 (discover plugins) → Wave 6 (finalization)

### Risk Assessment

**Production Blocker**: Parallel execution race conditions (G19-G24) pose reliability risk in current default parallel mode.

**Mitigation**: Wave 4 implementation prioritized alongside Wave 1.

**Safe to Use**: Current 3-stage pipeline (compile/validate/generate) is production-ready for SOHO deployment.

**Not Safe**: Assemble/build stages should not be used until Waves 1-2 complete.

---
```

---

## Proposed ADR REGISTER Update

### Current Entry (Line 83)

```markdown
| [0080](0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md) | Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus | Accepted | 2026-03-26 | - | - |
```

### Proposed Update

```markdown
| [0080](0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md) | Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus | Partially Implemented (see remediation/) | 2026-03-26 | - | - |
```

---

## Implementation Verification Checklist

Before marking ADR 0080 as "Implemented":

- [ ] **Wave 1**: Phase-aware executor operational
  - [ ] Runtime executes phases within each stage
  - [ ] Plugin `phase:` manifest field respected
  - [ ] `finalize` phase runs even on failure
  - [ ] Phase transition logging in diagnostics

- [ ] **Wave 2**: PluginContext extended
  - [ ] `workspace_root`, `dist_root` fields added
  - [ ] `assembly_manifest` consumed by build stage
  - [ ] Assemble/build plugins functional

- [ ] **Wave 3**: Discover stage plugins
  - [ ] Framework/project manifest loading pluginized
  - [ ] Plugin discovery via plugins, not procedural function
  - [ ] Capability preflight as plugin

- [ ] **Wave 4**: Parallel execution safe
  - [ ] Thread-safe data bus implemented
  - [ ] No race conditions in 1000+ iteration stress test
  - [ ] Diagnostic ordering deterministic

- [ ] **Wave 5**: Smart plugin predicates
  - [ ] `when.profiles`, `when.capabilities` evaluated
  - [ ] Predicate skip logged in diagnostics

- [ ] **Wave 6**: Finalization
  - [ ] Diagnostic ranges allocated (E80xx)
  - [ ] Artifact manifest plugin implemented
  - [ ] Order ranges documented for all 6 stages

- [ ] **Integration Validation**:
  - [ ] Full 6-stage pipeline executes end-to-end
  - [ ] Acceptance TUC passing
  - [ ] Golden snapshot parity maintained
  - [ ] CI execution time <10min (no regression)

- [ ] **Documentation**:
  - [ ] Plugin development guide updated
  - [ ] Operator runbook includes assemble/build stages
  - [ ] Migration notes for affected workflows

- [ ] **Governance**:
  - [ ] ADR 0080 status updated to "Implemented"
  - [ ] `adr/0080-remediation/COMPLETION-REPORT.md` created
  - [ ] ADR REGISTER updated

---

## Review and Approval

### Proposed by
- **AI-Agent**: Claude Code (claude-sonnet-4-5-20250929)
- **Date**: 2026-04-13
- **Context**: Architectural improvement analysis post-ADR 0095/0096

### Human Review Required
- [ ] Project lead review of status change rationale
- [ ] Verification that current 3-stage pipeline remains production-safe
- [ ] Approval of 6-wave remediation plan timeline
- [ ] Commitment of resources for implementation

### Approval Criteria
1. Acknowledgment that ADR 0080 is partially implemented (not fully accepted)
2. Agreement on 6-week remediation timeline
3. Prioritization of Wave 1 and Wave 4 (CRITICAL)
4. Risk acceptance for current parallel execution issues until Wave 4 complete

---

## Next Actions

1. **Immediate**:
   - [ ] Update ADR 0080 status field to "Partially Implemented"
   - [ ] Add "Implementation Status" section to ADR 0080
   - [ ] Update ADR REGISTER.md entry

2. **Week 1**:
   - [ ] Create `adr/0080-remediation/WAVE-1-PHASE-EXECUTOR.md`
   - [ ] Create `adr/0080-remediation/WAVE-4-PARALLEL-SAFETY.md`
   - [ ] Begin Wave 1 implementation

3. **Week 2-6**:
   - [ ] Execute remediation waves 1-6
   - [ ] Weekly status updates in `adr/0080-remediation/STATUS-UPDATES.md`
   - [ ] Validation per wave acceptance criteria

---

**Status Update Owner**: Project Lead (TBD)
**Review Date**: 2026-04-13
**Target Completion**: 6 weeks from remediation start
