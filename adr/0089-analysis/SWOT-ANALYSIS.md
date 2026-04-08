# SWOT Analysis: ADR 0089-0091 SOHO Product Contracts

**Analysis Date:** 2026-04-08
**Scope:** Post-remediation assessment of SOHO product profile, operator lifecycle, and readiness evidence contracts
**Status:** Based on corrected ADR versions (all P0+P1 issues resolved)

---

## Executive Summary

**Overall Assessment:** ✅ **Strong foundation with manageable risks**

ADR 0089-0091 establish a solid contractual basis for SOHO productization with clear governance, deterministic bundle resolution, and evidence-backed readiness. Key strengths are machine-validatable contracts and operator-first UX. Main risks center on implementation complexity and migration friction.

**Strategic Recommendation:** Proceed with implementation, prioritizing Wave 1 validators and migration tooling.

---

## Strengths

### S1. **Deterministic Contract-First Architecture**

**Description:**
All three ADRs are built on explicit, machine-validatable contracts (product profile, bundle resolution, evidence schemas).

**Evidence:**
- Bundle resolution formula: `effective_bundles = core ∪ class_specific` (ADR 0089 D4)
- JSON schemas for all evidence reports (ADR 0091 D6)
- Migration state enforcement table (ADR 0089 D7)

**Strategic Value:**
- ✅ Eliminates operator interpretation drift
- ✅ Enables automated validation and release gates
- ✅ Supports CI/CD integration
- ✅ Reduces support burden through predictable behavior

**Exploitability:** **High** — Framework already has plugin-based validation runtime (ADR 0063, 0086)

---

### S2. **Gradual Migration Path with Safety Gates**

**Description:**
Three-tier migration state model (`legacy → migrated-soft → migrated-hard`) allows phased adoption without breaking existing projects.

**Evidence:**
- Migration states with explicit transition rules (ADR 0089 D7, D9)
- Advisory-only diagnostics for legacy projects
- Sunset policy with explicit end date

**Strategic Value:**
- ✅ Minimizes cutover risk
- ✅ Allows incremental validation improvement
- ✅ Provides rollback path (soft → hard failure = stay in soft)
- ✅ Forces eventual compliance via sunset

**Exploitability:** **High** — Clear upgrade path reduces adoption friction

---

### S3. **Operator-Centric UX with Single Status Entrypoint**

**Description:**
Unified `product:*` task namespace with `product:doctor` as single-point status aggregator (ADR 0090 D6).

**Evidence:**
- Normalized status model: green/yellow/red (ADR 0091 D4)
- Single entrypoint aggregates: preconditions, profile compatibility, evidence completeness
- No framework internals knowledge required

**Strategic Value:**
- ✅ Lower onboarding cost
- ✅ Better handover experience
- ✅ Reduced support complexity
- ✅ Consistent troubleshooting flow

**Exploitability:** **Medium-High** — Requires orchestration layer implementation but clear design

---

### S4. **Evidence-Backed Readiness with Objective Criteria**

**Description:**
Evidence completeness states have time-bound, quality-gated criteria (ADR 0091 D4).

**Evidence:**
- Backup < 7 days + restore drill < 30 days = complete
- Secret rotation < 90 days = complete
- No subjective "ready when operator says so"

**Strategic Value:**
- ✅ Supports compliance/audit requirements
- ✅ Makes readiness mechanically checkable
- ✅ Prevents premature handover
- ✅ Creates institutional knowledge baseline

**Exploitability:** **High** — Criteria are already specified, implementation is straightforward

---

### S5. **Finite, Testable Deployment Classes**

**Description:**
Only 3 deployment classes (starter, managed-soho, advanced-soho) with explicit bundle sets (ADR 0089 D3, D4).

**Evidence:**
- Starter: 5 bundles
- Managed-SOHO: 8 bundles
- Advanced-SOHO: 10 bundles
- No arbitrary custom class creation

**Strategic Value:**
- ✅ Limits support matrix to manageable size
- ✅ Enables exhaustive integration testing (3 × hardware matrix)
- ✅ Prevents feature creep
- ✅ Simplifies documentation and training

**Exploitability:** **High** — Constraint is enforced by design

---

### S6. **Comprehensive E2E Documentation**

**Description:**
Full end-to-end scenario from project init to green status documented in `E2E-SCENARIO.md`.

**Evidence:**
- Complete operator timeline (70 min active time over 14 hours)
- All tasks with preconditions and outcomes
- Evidence state progression table
- Integration points between all three ADRs

**Strategic Value:**
- ✅ Reduces implementation uncertainty
- ✅ Provides acceptance test blueprint
- ✅ Serves as operator training material
- ✅ Enables dogfooding/validation

**Exploitability:** **Medium** — Requires implementation first, then validation

---

## Weaknesses

### W1. **Implementation Complexity for product:* Wrappers**

**Description:**
Thin orchestration wrappers (`product:*`) must coordinate multiple subsystems without creating behavior fork.

**Evidence:**
- `product:init` must integrate: profile validation, workspace creation, Terraform init, secrets check, bundle resolution (ADR 0090 D4)
- `product:doctor` must aggregate: lifecycle state, profile compat, bundle graph, evidence domains (ADR 0090 D6)

**Risk:**
- ⚠️ Wrapper drift from real runtime behavior
- ⚠️ Hidden side effects in "read-only" tasks
- ⚠️ Maintenance burden increases with framework evolution

**Mitigation Exists:** ADR 0090 D3 explicitly prohibits parallel execution plane, forces reuse of existing contracts

**Severity:** **Medium** — Manageable with strict testing but requires discipline

---

### W2. **Migration State Enforcement Not Yet Implemented**

**Description:**
Pipeline enforcement table (ADR 0089 D7) defines behavior but requires validator plugins to read and enforce migration state.

**Evidence:**
- No existing `migration_state`-aware validators
- Table specifies diagnostic severity adjustment, but mechanism not built
- State transition authority undefined (which component advances state?)

**Risk:**
- ⚠️ Legacy projects may be blocked if validators don't respect `advisory-only` mode
- ⚠️ Accidental downgrades if state storage not immutable

**Mitigation Path:** Implement in discover/validate plugins (ADR 0089 D6), add state transition governance

**Severity:** **Medium-High** — Blocking for migration path, but well-specified

---

### W3. **Evidence Collection Automation Gap**

**Description:**
Evidence criteria are explicit (ADR 0091 D4), but collection mechanism not specified.

**Evidence:**
- "Last restore drill date" — who records this? Where?
- "Secret rotation timestamp" — manual log or automated tracker?
- Evidence state derivation algorithm not implemented

**Risk:**
- ⚠️ Manual evidence logging → drift and forgetfulness
- ⚠️ Inconsistent timestamp formats
- ⚠️ Evidence falsification risk (manual editing)

**Mitigation Path:** Generate evidence artifacts during lifecycle tasks (`product:backup` writes `backup-status.json`)

**Severity:** **Medium** — Quality issue, not blocking

---

### W4. **Hardware Matrix Drift Risk**

**Description:**
Profile contract references `hardware_compatibility` (example profile) but matrix update process undefined.

**Evidence:**
- What happens when Proxmox VE 9 → VE 10?
- What if MikroTik Chateau becomes EOL?
- No versioning strategy for hardware matrix

**Risk:**
- ⚠️ False support claims (profile says "supported" but untested)
- ⚠️ Deployment failures on new hardware
- ⚠️ Profile staleness

**Mitigation Path:** Add hardware matrix versioning + compatibility testing in CI

**Severity:** **Low-Medium** — Long-term maintenance concern

---

### W5. **No Rollback Semantics for product:apply**

**Description:**
ADR 0090 D4 specifies `product:update` requires rollback semantics, but `product:apply` (initial deployment) has no rollback defined.

**Evidence:**
- `product:apply` failure mid-deployment → partial state
- No automatic cleanup or rollback to pre-apply state
- Operator must manually recover

**Risk:**
- ⚠️ Failed first deployment leaves environment dirty
- ⚠️ No "reset to zero" command
- ⚠️ Operator confusion on how to recover

**Mitigation Path:** Add `product:destroy` task or `--rollback-on-failure` flag

**Severity:** **Low-Medium** — Operational quality issue

---

### W6. **Bundle Dependency Graph Not Validated**

**Description:**
Bundle contracts specify `requires.bundles` (example: `bundle.backup-restore` requires `bundle.secrets-governance`), but cycle detection and ordering not addressed.

**Evidence:**
- Example bundle shows dependencies (ADR 0089 analysis examples)
- No topological sort requirement
- No cycle detection mentioned

**Risk:**
- ⚠️ Circular bundle dependencies → validation failure
- ⚠️ Ordering issues during generation
- ⚠️ Missing transitive dependencies

**Mitigation Path:** Add bundle graph validator (similar to plugin dependency validation ADR 0086)

**Severity:** **Medium** — Likely to surface during implementation

---

## Opportunities

### O1. **Extend to Multi-Site SOHO**

**Description:**
Current profile is `site_class: single-site` only, but architecture supports future multi-site.

**Evidence:**
- Profile contract has `site_class` field (ADR 0089 D1)
- Deployment classes are site-agnostic
- Bundle architecture is composable

**Potential:**
- 💡 Add `site_class: multi-site` with inter-site VPN bundle
- 💡 Reuse 80% of existing contracts
- 💡 Capture larger SOHO market segment

**Effort:** Medium (new bundles + inter-site networking)

**Value:** **High** — Market expansion without redesign

---

### O2. **Product Profile Marketplace / Templates**

**Description:**
Profile contract is portable — can be packaged and shared.

**Evidence:**
- Profile is YAML file with deterministic bundle resolution
- Hardware compatibility is explicit
- Profile ID is namespaced (`soho.standard.v1`)

**Potential:**
- 💡 Community-contributed profiles (e.g., `soho.media-server.v1`, `soho.home-office.v1`)
- 💡 Profile versioning and upgrades
- 💡 Profile compatibility testing as service

**Effort:** Low (just packaging + docs)

**Value:** **Medium-High** — Ecosystem growth

---

### O3. **Automated Evidence Collection via Observability Bundle**

**Description:**
`bundle.observability` (required for managed-soho) could auto-generate evidence reports.

**Evidence:**
- Evidence state is timestamp-based (ADR 0091 D4)
- Reports are JSON schemas (ADR 0091 D6)
- Observability bundle already tracks service health

**Potential:**
- 💡 Auto-update `health-report.json` on every monitoring run
- 💡 Alert when evidence goes from complete → partial (e.g., backup > 7 days)
- 💡 Dashboard showing evidence freshness

**Effort:** Low (add evidence writers to existing monitoring)

**Value:** **High** — Eliminates manual evidence tracking (W3)

---

### O4. **Compliance/Audit Export**

**Description:**
Evidence artifacts are already machine-readable and timestamped (ADR 0091 D1, D6).

**Evidence:**
- All evidence has provenance (timestamp, project_id, schema_version)
- Handover package is immutable (signed tar.gz)
- Audit trail in `.work/deploy-state/<project>/logs/`

**Potential:**
- 💡 Export compliance report for ISO 27001, SOC 2
- 💡 Generate audit-ready evidence package
- 💡 Automated compliance dashboard

**Effort:** Low (report template + export script)

**Value:** **Medium** — Useful for enterprise/commercial deployments

---

### O5. **CI/CD Integration for Profile Validation**

**Description:**
Profile validation is deterministic → can run in CI.

**Evidence:**
- Profile resolution is pure function (ADR 0089 D4)
- JSON schemas exist for all contracts
- No runtime dependencies for validation

**Potential:**
- 💡 GitHub Actions: validate profile on every commit
- 💡 Pre-commit hook: block invalid profile changes
- 💡 PR preview: show effective bundle set diff

**Effort:** Low (CI config + validation scripts)

**Value:** **High** — Prevents contract drift at source

---

### O6. **Declarative Restore Testing**

**Description:**
Restore drill is formalized (`product:restore --mode=drill`, ADR 0090 D4), enabling scheduled testing.

**Evidence:**
- Drill mode is non-destructive
- Evidence tracks last drill date (ADR 0091 D4)
- Yellow → green transition requires drill < 30 days

**Potential:**
- 💡 Scheduled monthly restore drill (automated)
- 💡 Chaos engineering: random restore testing
- 💡 Restore time SLA tracking

**Effort:** Low (cron job + drill automation)

**Value:** **High** — Ensures disaster recovery capability always valid

---

## Threats

### T1. **Bundle Proliferation (Scope Creep)**

**Description:**
If bundle creation becomes too easy, deployment classes may inflate beyond manageable support matrix.

**Evidence:**
- Bundle architecture is composable (ADR 0089)
- No explicit limit on bundle count
- Community/operator pressure for "just one more bundle"

**Impact:**
- 🔥 Support matrix explodes (3 classes × N bundles × M hardware)
- 🔥 Integration testing becomes infeasible
- 🔥 Profile compatibility matrix becomes unmanageable

**Likelihood:** **Medium-High** — Natural evolution pressure

**Mitigation:**
- ✅ Maintain finite deployment class constraint (ADR 0089 D3)
- ✅ Require ADR for new bundles
- ✅ Sunset unused bundles aggressively
- ⚠️ **Risk remains:** Weak governance can't resist feature requests

**Severity:** **High** if uncontrolled

---

### T2. **Migration State Lock-In**

**Description:**
Projects may get stuck in `migrated-soft` indefinitely if warnings are tolerable but hard to fix.

**Evidence:**
- Soft mode allows warnings (ADR 0089 D7)
- No automatic promotion to `migrated-hard`
- No forcing function besides sunset policy

**Impact:**
- 🔥 Long-term technical debt accumulation
- 🔥 Operator complacency ("yellow is good enough")
- 🔥 Release quality degradation

**Likelihood:** **High** — Observed in all gradual migration systems

**Mitigation:**
- ✅ Sunset policy forces eventual compliance (ADR 0089 D9)
- ✅ Make `migrated-hard` required for production handover
- ⚠️ **Requires discipline:** Governance must enforce promotion

**Severity:** **Medium-High** — Quality erosion over time

---

### T3. **Hardware Obsolescence Faster Than Profile Updates**

**Description:**
Home lab hardware (MikroTik, Orange Pi) evolves faster than enterprise gear, risking profile staleness.

**Evidence:**
- MikroTik product cycles: ~2 years
- Orange Pi SBC updates: ~1-2 years
- Profile update process undefined (W4)

**Impact:**
- 🔥 Profile claims compatibility with discontinued hardware
- 🔥 Operators deploy to unsupported new hardware
- 🔥 Support requests for untested configurations

**Likelihood:** **High** — Hardware refresh is inevitable

**Mitigation:**
- ⚠️ Add hardware matrix CI testing (update on new releases)
- ⚠️ Profile versioning with EOL dates
- ⚠️ Community-driven compatibility reports

**Severity:** **Medium** — Operational burden, not architectural failure

---

### T4. **Evidence Timestamp Manipulation**

**Description:**
If evidence is stored as editable JSON files, timestamps can be manually altered to fake readiness.

**Evidence:**
- Evidence files are JSON in `generated/<project>/product/reports/`
- No signature/integrity check mentioned (ADR 0091 D7 mentions provenance but not signing)
- Operator has write access to generated files

**Impact:**
- 🔥 False readiness claims
- 🔥 Untested disaster recovery
- 🔥 Compliance violations

**Likelihood:** **Low-Medium** — Requires malicious/negligent operator

**Mitigation:**
- ✅ ADR 0091 D7 requires provenance
- ⚠️ **Add:** Cryptographic signing of evidence reports
- ⚠️ **Add:** Immutable evidence storage (append-only log)

**Severity:** **Medium** — Trust issue, mitigable

---

### T5. **Operator Skill Gap for product:doctor Interpretation**

**Description:**
Even with normalized status (green/yellow/red), operators may misinterpret diagnostics or ignore warnings.

**Evidence:**
- `product:doctor` aggregates complex state (ADR 0090 D6)
- Diagnostics are code + message (E7941, W7943, etc.)
- No operator training materials yet

**Impact:**
- 🔥 Operators ignore yellow status → deploy to production anyway
- 🔥 Misunderstand diagnostic codes → wrong remediation
- 🔥 Support burden from preventable issues

**Likelihood:** **Medium** — Depends on operator onboarding quality

**Mitigation:**
- ✅ E2E-SCENARIO.md provides walkthrough
- ⚠️ **Add:** Diagnostic code reference documentation
- ⚠️ **Add:** Interactive `product:doctor --explain E7941` command

**Severity:** **Low-Medium** — Training/UX issue

---

### T6. **Framework Churn Breaks product:* Wrapper Assumptions**

**Description:**
`product:*` wrappers depend on stable framework contracts (deploy bundles, Terraform, Ansible), but framework evolves per ADR rhythm.

**Evidence:**
- ADR 0090 D3 prohibits parallel execution plane (wrappers delegate to framework)
- Framework already has 95+ ADRs, active evolution
- Wrapper contracts assume current runtime behavior

**Impact:**
- 🔥 Framework breaking change → product:* tasks silently misbehave
- 🔥 Wrapper maintenance becomes unsustainable
- 🔥 Operator UX degrades as wrappers lag behind framework

**Likelihood:** **Medium** — Framework stability improving but not frozen

**Mitigation:**
- ✅ ADR 0090 D3 forces delegation (reduces fork risk)
- ⚠️ **Add:** Integration tests for product:* against framework contracts
- ⚠️ **Add:** Versioned wrapper contract compatibility matrix

**Severity:** **Medium-High** — Long-term maintainability concern

---

## SWOT Matrix Summary

| Dimension | Count | Top Impact |
|---|---|---|
| **Strengths** | 6 | S1 (Deterministic contracts), S2 (Gradual migration), S4 (Evidence-backed readiness) |
| **Weaknesses** | 6 | W2 (Migration enforcement not implemented), W3 (Evidence automation gap), W6 (Bundle dep validation) |
| **Opportunities** | 6 | O1 (Multi-site expansion), O3 (Auto evidence collection), O6 (Declarative restore testing) |
| **Threats** | 6 | T1 (Bundle proliferation), T2 (Migration lock-in), T6 (Framework churn) |

---

## Strategic Recommendations

### Immediate Actions (Before Implementation)

1. **Implement migration state enforcement** (W2 → mitigates T2)
   - Add `migration_state`-aware validators
   - Test legacy/soft/hard behavior in all pipeline stages
   - Define state transition governance

2. **Add bundle dependency validation** (W6 → prevents future issues)
   - Cycle detection
   - Topological sort
   - Transitive dependency resolution

3. **Create diagnostic code reference** (T5 mitigation)
   - Document all E7941-E7949 codes
   - Provide remediation steps
   - Add to handover package

### Short-Term (First 3 Months)

4. **Automate evidence collection** (O3 → eliminates W3)
   - Integrate with observability bundle
   - Auto-generate JSON reports during lifecycle tasks
   - Alert on evidence expiration

5. **Sign evidence reports** (T4 mitigation)
   - Cryptographic signatures on all evidence JSON
   - Verify signatures in `product:doctor`
   - Reject tampered evidence

6. **CI/CD integration** (O5 → quality gate)
   - Profile validation in CI
   - Schema validation for all contracts
   - Evidence completeness checks

### Medium-Term (6-12 Months)

7. **Hardware matrix versioning** (W4 + T3 mitigation)
   - Automated compatibility testing
   - Profile EOL policy
   - Community hardware reports

8. **Bundle governance process** (T1 mitigation)
   - Require ADR for new bundles
   - Quarterly bundle review
   - Sunset unused bundles

9. **Expand to multi-site** (O1 → market growth)
   - New profile: `soho.standard.multi-site.v1`
   - Inter-site VPN bundle
   - Site failover testing

### Long-Term (12+ Months)

10. **Profile marketplace** (O2 → ecosystem)
    - Community profile repository
    - Profile compatibility testing service
    - Profile upgrade tooling

11. **Compliance export** (O4 → enterprise readiness)
    - ISO 27001 / SOC 2 report templates
    - Audit trail export
    - Compliance dashboard

---

## Risk Prioritization

**Critical Path Risks** (must address before implementation):

| Risk | Type | Mitigation | Owner |
|---|---|---|---|
| W2: Migration state not enforced | Weakness | Implement state-aware validators | Validator team |
| W6: Bundle dep validation missing | Weakness | Add cycle detection | Compiler team |
| T1: Bundle proliferation | Threat | Strict governance + ADR requirement | Architecture team |

**Monitor Closely** (likely to emerge during operations):

| Risk | Type | Watch For | Mitigation Trigger |
|---|---|---|---|
| T2: Migration lock-in | Threat | >50% projects stuck in `soft` after 6 months | Force `hard` for production |
| T3: Hardware obsolescence | Threat | Profile references EOL hardware | Update profile within 30 days |
| T6: Framework churn | Threat | Wrapper tests fail after framework update | Add compatibility matrix |

---

## Opportunity Prioritization

**High ROI, Low Effort** (quick wins):

1. **O5: CI/CD integration** — Effort: 1 week, Value: High (prevents drift)
2. **O3: Auto evidence collection** — Effort: 2 weeks, Value: High (eliminates manual tracking)
3. **O6: Declarative restore testing** — Effort: 1 week, Value: High (validates DR capability)

**High ROI, Medium Effort** (strategic investments):

4. **O1: Multi-site expansion** — Effort: 1-2 months, Value: High (market growth)
5. **O4: Compliance export** — Effort: 3-4 weeks, Value: Medium (enterprise readiness)

**Medium ROI** (defer until demand validated):

6. **O2: Profile marketplace** — Effort: 2-3 months, Value: Medium (ecosystem growth)

---

## Conclusion

**Overall Position:** ✅ **Strong with Manageable Risks**

**Key Findings:**

1. **Strengths outweigh weaknesses** — Deterministic contracts, gradual migration, and evidence-backed readiness provide solid foundation
2. **Opportunities align with strengths** — Auto evidence collection, CI/CD integration, and multi-site expansion are natural extensions
3. **Threats are mitigable** — Bundle proliferation and migration lock-in require governance discipline, not redesign
4. **Weaknesses are implementation gaps** — Not architectural flaws; addressed via standard dev practices

**Go/No-Go Assessment:** ✅ **GO**

Recommend proceeding with implementation, prioritizing:
- Migration state enforcement (W2)
- Bundle dependency validation (W6)
- Auto evidence collection (O3)
- CI/CD integration (O5)

With these foundations, ADR 0089-0091 provide a robust, extensible productization framework for SOHO deployments.

---

## Appendix: SWOT Scoring Matrix

| Factor | Impact (1-5) | Likelihood (1-5) | Priority Score |
|---|---|---|---|
| **Strengths** |
| S1: Deterministic contracts | 5 | 5 | 25 |
| S2: Gradual migration | 4 | 5 | 20 |
| S3: Operator UX | 4 | 4 | 16 |
| S4: Evidence-backed readiness | 5 | 4 | 20 |
| S5: Finite deployment classes | 4 | 5 | 20 |
| S6: E2E documentation | 3 | 5 | 15 |
| **Weaknesses** |
| W1: Wrapper complexity | 3 | 4 | 12 |
| W2: Migration not enforced | 4 | 5 | 20 ⚠️ |
| W3: Evidence automation gap | 3 | 4 | 12 |
| W4: Hardware matrix drift | 2 | 3 | 6 |
| W5: No rollback semantics | 3 | 3 | 9 |
| W6: Bundle dep validation | 4 | 4 | 16 ⚠️ |
| **Opportunities** |
| O1: Multi-site expansion | 4 | 3 | 12 |
| O2: Profile marketplace | 3 | 2 | 6 |
| O3: Auto evidence | 4 | 4 | 16 💡 |
| O4: Compliance export | 3 | 3 | 9 |
| O5: CI/CD integration | 5 | 5 | 25 💡 |
| O6: Restore testing | 4 | 4 | 16 💡 |
| **Threats** |
| T1: Bundle proliferation | 4 | 4 | 16 ⚠️ |
| T2: Migration lock-in | 4 | 4 | 16 ⚠️ |
| T3: Hardware obsolescence | 3 | 4 | 12 |
| T4: Evidence tampering | 3 | 2 | 6 |
| T5: Skill gap | 2 | 3 | 6 |
| T6: Framework churn | 4 | 3 | 12 |

**Legend:**
- ⚠️ High-priority risk (score ≥ 16)
- 💡 High-value opportunity (score ≥ 16)

**Risk/Opportunity Balance:** Balanced — High-value opportunities offset high-priority risks when mitigations applied.
