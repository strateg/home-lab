# ADR 0087 SWOT ANALYSIS

**Last updated:** 2026-04-06
**Status:** Post-hardening analysis

## SWOT Matrix

### Strengths (S)

| ID | Strength | Impact |
|----|----------|--------|
| S1 | Two-axis hierarchy (L1 hypervisor + L4 workload) provides clean separation | High — reduces class explosion, enables cross-platform VM support |
| S2 | Single VM class with platform_config extension bag | High — avoids N×M class matrix (5 hypervisors × M profiles) |
| S3 | Docker promotion to L4 creates uniform L5→L4→L1 chain | High — enables inventory visibility, L6/L7 targeting |
| S4 | Runtime capability model (cap + vendor) | Medium — explicit contract, validator-enforceable |
| S5 | Compile-time cross-layer validation (L1↔L3↔L4) | High — catches format/bus mismatches before deploy |
| S6 | Bounded nested topology (max depth 2) | Medium — prevents complexity explosion |
| S7 | Host-based sharding improves file organization | Medium — scales with host count |
| S8 | Comprehensive deprecation lifecycle (WARNING→ERROR→REMOVAL) | High — safe migration path |
| S9 | Phase-gated implementation with rollback | High — reduces risk per phase |
| S10 | 32 acceptance criteria provide verifiable gates | High — enables objective progress tracking |

### Weaknesses (W)

| ID | Weakness | Impact | Mitigation |
|----|----------|--------|------------|
| W1 | Topology file count grows ~30% | Medium | Inheritance + defaults merging |
| W2 | platform_config requires per-hypervisor schema maintenance | Medium | Centralized schema registry |
| W3 | Migration touches existing refs (class rename, hypervisor split) | Medium | Aliases + feature flags |
| W4 | 6 validators still in tests/scripts, not plugins | Medium | Plugin migration plan (P9) |
| W5 | Resource profiles not formalized (GAP-7 deferred) | Low | Future ADR |
| W6 | No multi-host orchestration (GAP-8 deferred) | Low | Out of scope for home lab |
| W7 | Complex dependency graph between phases | Medium | Parallel Phase 1+2 reduces critical path |
| W8 | Docker-in-LXC adds reference resolution complexity | Low | Explicit host_ref semantics (§5d) |

### Opportunities (O)

| ID | Opportunity | Potential |
|----|-------------|-----------|
| O1 | Extend to Kubernetes pods (class.compute.workload.pod) | High — future workload type |
| O2 | Docker Compose generation from topology | High — Phase 6 deliverable |
| O3 | Multi-hypervisor dev environments (VBox for dev, Proxmox for prod) | Medium — enables local testing |
| O4 | L3 data_asset governance chain enables automated backup policies | Medium — ADR 0026 integration |
| O5 | Nested topology enables complex stacks (media server, monitoring) | Medium — Phase 5+6 |
| O6 | Validator plugins can enforce custom policies per organization | Medium — extensibility |
| O7 | Schema versioning enables controlled evolution | Medium — §5k policy |
| O8 | Ownership proof pattern reusable across other ADRs | Medium — proven in ADR 0093 |

### Threats (T)

| ID | Threat | Probability | Impact | Mitigation |
|----|--------|-------------|--------|------------|
| T1 | Topology explosion if inheritance not used properly | Medium | High | Documentation, templates, code review |
| T2 | Breaking existing L4/L5 during migration | Medium | High | Comprehensive test coverage, rollback |
| T3 | Scope creep adding features beyond container ontology | Low | Medium | Explicit Out of Scope section |
| T4 | platform_config schema drift between hypervisor versions | Medium | Medium | Version pinning, schema registry |
| T5 | Prolonged rollback avoiding migration completion | Low | Medium | Escalation policy (§5j) |
| T6 | Validator plugin migration breaks existing CI | Medium | Medium | Parallel tests + plugins approach |
| T7 | Host-sharded paths confuse operators during transition | Low | Low | Clear documentation, warnings |
| T8 | Nested topology depth violations slip through | Low | High | DFS cycle detection validator |

## Risk Matrix

```
Impact
  ^
  |  T2,T8    T1
H |    *       *
  |
M |  T4,T6    T3
  |    *       *
  |
L |  T5,T7
  |    *
  +-------------------> Probability
     L    M    H
```

**High Risk (monitor closely):** T1, T2
**Medium Risk (standard mitigation):** T3, T4, T6, T8
**Low Risk (accepted):** T5, T7

## Strategic Recommendations

### Immediate (Before Phase 1)

1. **Migrate critical validators to plugins** (W4/T6)
   - `validate-container-host-capability`
   - `validate-host-ref-dag`
   - Priority: P9 from problem classification

2. **Create test suite for new classes** (S10/T2)
   - Unit tests for class.compute.workload.{lxc,docker}
   - Integration tests for L5→L4 Docker refs
   - Negative tests for cycle detection

### Short-term (Phase 1-2)

3. **Document inheritance patterns** (T1)
   - Create template objects with sensible defaults
   - Document when to create new object vs use existing

4. **Establish schema registry** (W2/T4)
   - Centralize platform_config schemas
   - Version schemas with hypervisor releases

### Mid-term (Phase 3-4)

5. **Implement ownership proof** (S8/O8)
   - Three-method verification as per §5g
   - CI gate integration

6. **Complete L3↔L4 validation chain** (S5/O4)
   - Volume format compatibility
   - data_asset_ref governance

### Long-term (Phase 5-6)

7. **Evaluate Kubernetes pod support** (O1)
   - Assess demand after Docker/VM stabilization
   - Consider separate ADR if scope significant

8. **Consider resource profile formalization** (W5)
   - Evaluate after Phase 6 completion
   - May warrant dedicated ADR

## Comparison with ADR 0092/0093/0094

| Aspect | ADR 0087 (after hardening) | ADR 0092/0093/0094 |
|--------|---------------------------|-------------------|
| Acceptance Criteria | AC-1 to AC-32 | AC-1 to AC-20 |
| Ownership Proof | §5g (3 methods) | D12 (3 methods) |
| Migration States | §5h (4 states) | D10/D14 (4 states) |
| Sunset Policy | §5i (phase-relative) | D13 (concrete dates) |
| Rollback Escalation | §5j (7/14/30 day) | D14 (7-day escalation) |
| Schema Versioning | §5k (semver) | D9 (schema_version field) |
| Out of Scope | Explicit section | Implicit |

**Alignment:** ADR 0087 now follows the same governance patterns as ADR 0092/0093/0094.

## Conclusion

After hardening, ADR 0087 addresses all Critical (P3, P5, P9) and Important (P4, P6, P7, P10) problems identified in the diagnostic analysis. The Optional/Deferred items (P1, P2, P8) are explicitly documented as out of scope.

The SWOT analysis shows:
- **10 Strengths** outweigh **8 Weaknesses**
- **8 Opportunities** for future expansion
- **8 Threats** with defined mitigations
- **2 High-risk items** (T1, T2) require monitoring

The ADR is ready for implementation with Phase 1 and Phase 2 executing in parallel.
