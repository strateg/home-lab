# Risks and Mitigation Strategies

**Date:** 2026-03-06
**Focus:** Risk assessment and mitigation strategies for v4 to v5 migration

---

## Executive Summary

This analysis identifies risks associated with the topology v4 to v5 migration and proposes mitigation strategies. Risks are categorized by impact and likelihood, with focus on high-priority mitigations.

**Overall Risk Level:** MEDIUM-HIGH (manageable with proper execution)

**Critical Risks:** 3
**High Risks:** 8
**Medium Risks:** 12
**Low Risks:** 7

---

## Critical Risks

### CR-1: Phase 0 Not Executed, Blocking All Work

**Category:** Schedule / Process
**Impact:** CRITICAL
**Likelihood:** HIGH (current reality)

**Description:**
Phase 0 (workspace split) has not been executed. All subsequent migration work is blocked until v4/ and v5/ directories exist.

**Impact Analysis:**
- Entire migration timeline delayed
- Cannot start class/object module work
- Cannot test dual-lane CI
- Team confusion about where to work

**Root Cause:**
- Inertia / prioritization
- Perceived complexity of file moves

**Mitigation Strategy:**

1. **Immediate Execution (Week 1)**
   - Dedicate 2-3 days for Phase 0
   - Create detailed execution checklist
   - Test in branch before merging

2. **Risk Reduction**
   - Automated scripts for file moves
   - Comprehensive path update grep/sed
   - Rollback plan if issues found

3. **Validation**
   - Run all existing CI checks
   - Verify output paths
   - Manual smoke tests

**Residual Risk:** LOW (if executed carefully)

**Owner:** Platform team lead

---

### CR-2: V5 Regression in Production After Cutover

**Category:** Technical / Operations
**Impact:** CRITICAL
**Likelihood:** MEDIUM

**Description:**
After cutover to v5 (Phase 8), unexpected regressions could cause production issues (e.g., incorrect Terraform configs, broken Ansible inventory, network misconfigurations).

**Impact Analysis:**
- Service downtime
- Network outages
- Data loss (worst case)
- Rollback required under pressure

**Root Cause Scenarios:**
- Incomplete parity in Phase 6
- Generator bugs in v5
- Missed edge cases in testing
- Model mismatches (class/object/instance)

**Mitigation Strategy:**

1. **Gradual Cutover (Phase 8)**
   - Start with low-risk artifacts (docs)
   - Then Ansible inventory (non-destructive)
   - Finally Terraform (critical path)
   - Monitor each stage before proceeding

2. **Extensive Parity Testing (Phase 6)**
   - Automated diff tools
   - Side-by-side comparison
   - Manual review of critical configs
   - Accept/document expected differences

3. **Parallel Running**
   - Run v4 and v5 generators in parallel for 1-2 weeks
   - Compare outputs before cutover
   - Identify discrepancies

4. **Rollback Readiness**
   - Keep v4 lane functional
   - Document rollback procedure
   - Test rollback in dev environment
   - Have rollback triggers defined

5. **Production Validation**
   - Canary deployments
   - Monitoring and alerting
   - Quick rollback capability

**Residual Risk:** MEDIUM (cannot eliminate entirely)

**Owner:** DevOps team + Migration lead

---

### CR-3: Capability Model Explosion

**Category:** Architecture / Technical Debt
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
Without strict governance, the capability model could explode into hundreds of capabilities with inconsistent semantics, making the system unmaintainable.

**Impact Analysis:**
- Cognitive overload for developers
- Inconsistent capability definitions
- Difficult to understand class/object relationships
- Increased maintenance burden

**Root Causes:**
- No clear promotion criteria
- Vendor-specific capabilities leak into class
- Duplicate capabilities with different names
- No capability review process

**Mitigation Strategy:**

1. **Strict Promotion Rules (ADR 0062)**
   - Object-local capability → class pack only when reused 2+ times
   - Vendor-only stays in `vendor.*` namespace
   - Require justification for new class capabilities

2. **Capability Review Board**
   - Weekly review of new capability requests
   - Check for duplicates
   - Ensure consistent semantics
   - Approve class-level additions

3. **Capability Linting**
   - Automated checks for `vendor.*` prefix
   - Detect potential duplicates (similar names)
   - Flag capabilities used by only 1 object

4. **Documentation**
   - Capability catalog with clear semantics
   - Examples for each capability
   - When to use vs. when to create new

**Residual Risk:** LOW (with governance)

**Owner:** Architecture team

---

## High Risks

### HR-1: Incomplete v4 to v5 Entity Mapping

**Category:** Data / Migration
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
Phase 1 inventory may miss entities or misclassify them, leading to incomplete migration.

**Mitigation:**
- Automated inventory script (reduces human error)
- Manual review by domain experts
- Cross-check with existing topology
- Validation scripts to detect unmapped entities

**Residual Risk:** LOW

---

### HR-2: Class/Object Modules Don't Cover All Use Cases

**Category:** Architecture / Scope
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
Defined class/object modules may not cover all entity types in topology, requiring rework.

**Mitigation:**
- Comprehensive inventory first (Phase 1)
- Iterative class/object definition
- Buffer for edge cases (15-20 classes, add 5 buffer)
- Allow object-local capabilities temporarily

**Residual Risk:** LOW

---

### HR-3: Migration Script Data Loss or Corruption

**Category:** Technical / Data Integrity
**Impact:** HIGH
**Likelihood:** LOW

**Description:**
Migration script could corrupt topology data or lose information during transformation.

**Mitigation:**
- Always run in dry-run mode first
- Version control (git) for rollback
- Comprehensive unit tests
- Manual review of migration output
- Backup before migration

**Residual Risk:** VERY LOW

---

### HR-4: Compiler Implementation Incomplete

**Category:** Technical / Implementation
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
Current `compile-topology.py` may not implement all 5 stages or may lack class/object resolution.

**Mitigation:**
- Audit compiler early (Week 1)
- Identify gaps
- Implement missing stages iteratively
- Test with example topology

**Residual Risk:** LOW

---

### HR-5: Generator Refactoring Breaks v4

**Category:** Technical / Regression
**Impact:** HIGH
**Likelihood:** LOW

**Description:**
Refactoring generators for v5 could accidentally break v4 generators.

**Mitigation:**
- Keep v4 and v5 generators completely separate
- No shared code until after cutover
- Freeze v4 generators (no changes)
- Separate test suites

**Residual Risk:** VERY LOW

---

### HR-6: Profile Substitution Logic Bugs

**Category:** Technical / Logic Error
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
Profile system (production/modeled/test-real) could have bugs causing incorrect substitutions.

**Mitigation:**
- Extensive test cases for all three profiles
- Validation of capability signature matching
- Manual review of profile maps
- Start with simple substitutions, add complexity gradually

**Residual Risk:** MEDIUM

---

### HR-7: Model Lock Drift

**Category:** Governance / Versioning
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
`model.lock.yaml` could drift from actual class/object usage, causing validation failures or incorrect pinning.

**Mitigation:**
- Automated lock generation script
- CI check for lock file freshness
- Fail build if lock out of date
- Document manual lock update process

**Residual Risk:** LOW

---

### HR-8: Timeline Underestimation

**Category:** Schedule / Planning
**Impact:** HIGH
**Likelihood:** MEDIUM

**Description:**
Estimated 14-21 weeks may be optimistic, especially if unforeseen issues arise.

**Mitigation:**
- Build in 25% contingency buffer (17-26 weeks)
- Prioritize critical path items
- Allow parallel work where possible
- Regular checkpoint reviews
- Adjust timeline based on actual progress

**Residual Risk:** MEDIUM

---

## Medium Risks

### MR-1: CI Path Guards Not Enforced

**Category:** Process / Governance
**Impact:** MEDIUM
**Likelihood:** LOW

**Description:**
Without CI enforcement, developers might accidentally commit v5 changes to v4 or vice versa.

**Mitigation:**
- Implement CI path guards in Phase 0
- Pre-commit hooks
- PR template with lane selection
- Code review checklist

**Residual Risk:** LOW

---

### MR-2: Team Confusion About Which Lane to Use

**Category:** Process / Training
**Impact:** MEDIUM
**Likelihood:** MEDIUM

**Description:**
Developers unsure whether to work in v4 or v5 lane for a given change.

**Mitigation:**
- Clear documentation in PR template
- Team training after Phase 0
- Decision tree diagram
- Default: v5 for new work, v4 only for critical fixes

**Residual Risk:** LOW

---

### MR-3: Parity Criteria Too Strict

**Category:** Process / Quality
**Impact:** MEDIUM
**Likelihood:** MEDIUM

**Description:**
If parity criteria are too strict (exact byte-for-byte match), Phase 6 may never complete.

**Mitigation:**
- Define parity as "semantic equivalence" not "exact match"
- Document acceptable differences
- Focus on production-critical artifacts
- Accept non-functional differences (formatting, comments)

**Residual Risk:** LOW

---

### MR-4: ADR 0063 Not Accepted, Blocking Phase 7

**Category:** Governance / Dependencies
**Impact:** MEDIUM
**Likelihood:** LOW

**Description:**
If ADR 0063 (plugin microkernel) is not accepted, Phase 7 is blocked or needs redesign.

**Mitigation:**
- Push for ADR 0063 acceptance early
- If rejected, have fallback plan (keep hardcoded generators)
- Phase 7 is late in timeline, gives time to resolve

**Residual Risk:** LOW

---

### MR-5: Capability Checker Bugs

**Category:** Technical / Validation
**Impact:** MEDIUM
**Likelihood:** LOW

**Description:**
`check-capability-contract.py` may have bugs, causing false positives/negatives.

**Mitigation:**
- Test capability checker with examples
- Add unit tests
- Manual review of capability definitions
- Iterate based on usage

**Residual Risk:** LOW

---

### MR-6: Incomplete Legacy Field Deprecation

**Category:** Technical Debt / Cleanup
**Impact:** MEDIUM
**Likelihood:** MEDIUM

**Description:**
Legacy fields (`type`, `model`, etc.) may persist longer than timeline, causing confusion.

**Mitigation:**
- Track legacy field usage in spreadsheet
- Automated detection in CI
- Gradual removal per timeline
- Clear warnings in compiler

**Residual Risk:** MEDIUM

---

### MR-7: Object-Class Impedance Mismatch

**Category:** Architecture / Design
**Impact:** MEDIUM
**Likelihood:** LOW

**Description:**
Objects may not fit cleanly into class contracts, requiring rework.

**Mitigation:**
- Iterative class/object design (Phase 2-3 together)
- Allow object-local capabilities temporarily
- Review board for edge cases
- Refine class contracts based on object needs

**Residual Risk:** LOW

---

### MR-8: Test Coverage Insufficient

**Category:** Quality / Testing
**Impact:** MEDIUM
**Likelihood:** MEDIUM

**Description:**
v5 tests may not cover all edge cases, leading to production issues.

**Mitigation:**
- Test-driven development for v5
- Reuse v4 test patterns
- Add new tests for class/object/profile logic
- Coverage metrics in CI

**Residual Risk:** MEDIUM

---

### MR-9: Documentation Lags Implementation

**Category:** Documentation / Knowledge Transfer
**Impact:** MEDIUM
**Likelihood:** HIGH

**Description:**
Documentation may not keep up with implementation changes, causing confusion.

**Mitigation:**
- Incremental documentation per phase
- Require docs in PR (definition of done)
- Review documentation alongside code
- Templates for common tasks

**Residual Risk:** MEDIUM

---

### MR-10: Vendor-Specific Logic Leaks

**Category:** Architecture / Abstraction
**Impact:** MEDIUM
**Likelihood:** MEDIUM

**Description:**
Vendor-specific logic (MikroTik, Proxmox) may leak into core layer.

**Mitigation:**
- Strict namespace enforcement (`vendor.*`)
- Code review for core layer changes
- Architectural reviews
- Refactoring when leaks detected

**Residual Risk:** LOW

---

### MR-11: Rollback Procedure Not Tested

**Category:** Operations / Disaster Recovery
**Impact:** MEDIUM
**Likelihood:** LOW

**Description:**
Rollback from v5 to v4 may fail when needed if not tested beforehand.

**Mitigation:**
- Document rollback procedure
- Test rollback in dev/staging
- Define rollback triggers
- Keep v4 lane functional during stabilization

**Residual Risk:** LOW

---

### MR-12: Plugin API Instability

**Category:** Technical / Architecture
**Impact:** MEDIUM
**Likelihood:** MEDIUM

**Description:**
Plugin API may change frequently in early phases, breaking plugins.

**Mitigation:**
- Version plugin API explicitly
- Maintain backward compatibility
- Deprecation policy for API changes
- Gradual migration (Phase 7 late in timeline)

**Residual Risk:** MEDIUM

---

## Low Risks

### LR-1: Repository Size Growth

**Category:** Infrastructure / Scale
**Impact:** LOW
**Likelihood:** HIGH

**Description:**
Dual-track structure temporarily increases repository size.

**Mitigation:**
- Git LFS for large artifacts
- Temporary duplication (v4 removed after cutover)
- Monitor repo size

**Residual Risk:** NEGLIGIBLE

---

### LR-2: Class Naming Inconsistency

**Category:** Governance / Convention
**Impact:** LOW
**Likelihood:** LOW

**Description:**
Class naming may be inconsistent (e.g., `class.router` vs. `class.network.router`).

**Mitigation:**
- Naming convention document
- Review board for new classes
- Refactor early if issues found

**Residual Risk:** NEGLIGIBLE

---

### LR-3: Object Naming Inconsistency

**Category:** Governance / Convention
**Impact:** LOW
**Likelihood:** LOW

**Description:**
Object naming may be inconsistent.

**Mitigation:**
- Naming convention document
- Review board for new objects

**Residual Risk:** NEGLIGIBLE

---

### LR-4: CI Runtime Increase

**Category:** Infrastructure / Performance
**Impact:** LOW
**Likelihood:** MEDIUM

**Description:**
Dual-lane CI may double CI runtime.

**Mitigation:**
- Parallel CI lanes
- Selective execution (path-based)
- Optimize slow tests

**Residual Risk:** NEGLIGIBLE

---

### LR-5: Example File Proliferation

**Category:** Maintenance / Documentation
**Impact:** LOW
**Likelihood:** MEDIUM

**Description:**
Many `.example.yaml` files may clutter repository.

**Mitigation:**
- Move examples to docs/ or separate examples/
- Clear naming convention
- Regular cleanup

**Residual Risk:** NEGLIGIBLE

---

### LR-6: Semantic Versioning Confusion

**Category:** Governance / Versioning
**Impact:** LOW
**Likelihood:** LOW

**Description:**
Class/object versioning scheme may confuse contributors.

**Mitigation:**
- Clear versioning guide
- Tooling to bump versions
- CI checks for version consistency

**Residual Risk:** NEGLIGIBLE

---

### LR-7: Diff Tool Limitations

**Category:** Tooling / Quality
**Impact:** LOW
**Likelihood:** LOW

**Description:**
Parity comparison tools may not detect semantic differences.

**Mitigation:**
- Multiple comparison strategies (byte diff, semantic diff)
- Manual review for critical artifacts
- Continuous improvement of tooling

**Residual Risk:** NEGLIGIBLE

---

## Risk Mitigation Timeline

### Phase 0 (Weeks 1-2)
- ✅ **CR-1:** Execute Phase 0 immediately
- ✅ **MR-1:** Implement CI path guards
- ✅ **MR-2:** Team training on dual-track

### Phase 1 (Weeks 2-3)
- ✅ **HR-1:** Automated inventory + manual review
- ✅ **HR-4:** Audit compiler implementation

### Phase 2-3 (Weeks 4-8)
- ✅ **HR-2:** Buffer classes/objects for edge cases
- ✅ **CR-3:** Implement capability governance
- ✅ **MR-7:** Iterative class/object design

### Phase 4 (Weeks 9-10)
- ✅ **HR-3:** Migration script testing and backup

### Phase 5 (Week 11)
- ✅ **HR-6:** Test profile substitution logic
- ✅ **HR-7:** Automated model lock generation

### Phase 6 (Weeks 12-15)
- ✅ **HR-5:** Keep v4/v5 generators separate
- ✅ **MR-3:** Define acceptable parity differences

### Phase 7 (Weeks 16-19)
- ✅ **MR-4:** Ensure ADR 0063 accepted
- ✅ **MR-12:** Version plugin API

### Phase 8 (Weeks 20-21)
- ✅ **CR-2:** Gradual cutover with rollback readiness
- ✅ **MR-11:** Test rollback procedure

---

## Risk Response Plan

### Critical Risk Triggers

| Trigger | Response |
|---------|----------|
| Phase 0 not started by Week 2 | Escalate to management, dedicate resources |
| v5 compilation fails in production | Immediate rollback to v4, incident review |
| Capability count > 200 | Freeze new capabilities, audit and consolidate |

### High Risk Triggers

| Trigger | Response |
|---------|----------|
| >10% entities unmapped after Phase 1 | Extend inventory phase, manual classification |
| Compiler audit shows major gaps | Adjust timeline, prioritize compiler work |
| Generator refactoring touches v4 code | Reject PR, enforce separation |
| Parity comparison shows >5% critical diffs | Investigate root cause, may delay cutover |

### Escalation Path

1. **Team Lead:** Handles low/medium risks
2. **Architecture Team:** Handles architecture risks (capability explosion, class/object mismatch)
3. **Management:** Handles critical risks (timeline, resource allocation)

---

## Risk Monitoring

### Weekly Risk Review

During migration, conduct weekly risk review:

1. Review risk register
2. Update likelihood/impact based on progress
3. Identify new risks
4. Adjust mitigations

### Risk Metrics

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Phase 0 delay | 0 weeks | >1 week | >2 weeks |
| Unmapped entities | <5% | 5-10% | >10% |
| Capability count | <100 | 100-150 | >150 |
| Parity differences (critical) | <1% | 1-5% | >5% |
| Timeline variance | <10% | 10-25% | >25% |

---

## Contingency Plans

### Contingency 1: Phase 0 Takes Too Long

**Trigger:** Phase 0 exceeds 1 week

**Response:**
- Simplify initial split (move directories only, defer CI)
- Add resources (pair programming)
- Document blockers for management

### Contingency 2: Timeline Slips Beyond Buffer

**Trigger:** Timeline slips >25%

**Response:**
- Reassess scope (can any phases be simplified?)
- Add resources
- Consider partial cutover (e.g., docs only)

### Contingency 3: Capability Explosion

**Trigger:** Capability count >150

**Response:**
- Immediate capability audit
- Consolidate duplicates
- Promote object-local to class packs
- Stricter review process

### Contingency 4: Parity Cannot Be Achieved

**Trigger:** Critical diffs >5% after extensive work

**Response:**
- Assess if differences are acceptable
- Document all differences
- Get stakeholder approval
- May need model changes

### Contingency 5: Rollback Needed Post-Cutover

**Trigger:** Production issue caused by v5

**Response:**
- Activate rollback procedure
- Switch CI back to v4
- Incident post-mortem
- Fix v5 issues before retry

---

## Success Criteria

Migration is considered successful when:

1. ✅ All 13 ADR 0062 completion criteria met
2. ✅ No critical risks materialized
3. ✅ Timeline variance <25%
4. ✅ v5 operational for 1+ stabilization cycle
5. ✅ Team confident in v5 architecture

---

## Conclusion

**Overall Risk Assessment:** MEDIUM-HIGH (manageable)

**Critical Risks:** 3, all mitigable with proper execution

**Key Risk Mitigation Strategies:**
1. Execute Phase 0 immediately (addresses CR-1)
2. Gradual cutover (addresses CR-2)
3. Strict capability governance (addresses CR-3)
4. Automated tooling and validation throughout
5. Comprehensive testing and rollback readiness

**Risk Monitoring:** Weekly reviews during migration

**Confidence Level:** HIGH that risks can be managed with proposed mitigations

**Recommendation:** Proceed with migration, execute Phase 0 immediately, establish risk monitoring cadence.
