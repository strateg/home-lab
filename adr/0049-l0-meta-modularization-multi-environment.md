# ADR 0049: L0 Meta Layer Modularization & Multi-Environment Support

**Date:** 2026-02-26
**Status:** Proposed
**Stakeholders:** Architecture team, DevOps, Infrastructure engineers

---

## Context

Current L0 (Meta) layer is **monolithic and inflexible**:

**Problems:**
1. **Monolithic structure:** All metadata, defaults, and policies in single 76-line file
2. **No policy hierarchy:** Only one `sec-baseline` policy; can't have sec-strict or sec-relaxed variants
3. **No multi-environment:** `environment: production` hardcoded; can't use same topology for staging/dev
4. **No regional policies:** No support for region-specific defaults (us-east vs eu-west vs apac)
5. **No inheritance:** Adding new policy requires duplicating all parent properties
6. **No audit trail:** Can't track who created/modified policies or when
7. **Mixed concerns:** Changelog mixed with meta, defaults scattered

**Constraints:**
- Must maintain backward compatibility of generated Terraform/Ansible/docs
- Must not break existing L1-L7 references to L0 defaults
- Must support lazy loading (avoid loading all policies if not needed)
- Must keep YAML human-readable (avoid complex templating)

---

## Decision

### 1. Modularize L0 into 9 Separate Files

**New structure:**
```
L0-meta/
├── _index.yaml                      # Entry point with all includes
├── version.yaml                     # Version info (separate concern)
├── environment-config.yaml          # Multi-env support (prod/staging/dev)
├── defaults/
│   ├── refs.yaml                   # Global refs
│   ├── compliance.yaml             # Compliance defaults
│   ├── audit.yaml                  # Audit defaults
│   └── feature-flags.yaml          # Feature toggles
├── security-policies/
│   ├── _base.yaml                  # Abstract template
│   ├── baseline.yaml               # Production baseline
│   ├── strict.yaml                 # High-security variant
│   ├── relaxed.yaml                # Development variant
│   └── policy-registry.yaml        # Inheritance map
├── regional-policies/
│   ├── us-east.yaml
│   ├── eu-west.yaml
│   └── apac.yaml
└── changelog.yaml                   # Version history
```

**Benefits:**
- ✅ Clear separation of concerns
- ✅ Each file has single responsibility
- ✅ Easier to update individual policies
- ✅ Supports policy inheritance (strict extends baseline)
- ✅ Enables multi-environment configuration
- ✅ Auditable (created_by, modified_by, created_at)

### 2. Implement Policy Inheritance

**Pattern:**
```yaml
# baseline.yaml - Base policy
id: sec-baseline
description: Production baseline

password_policy:
  min_length: 16
  max_age_days: 90

# strict.yaml - Extends baseline
id: sec-strict
parent_policy: sec-baseline

password_policy:
  min_length: 20        # Override
  max_age_days: 60      # Override
  # Inherits rest from parent
```

**Validator rule:** Ensure inheritance is acyclic and all parent policies exist.

**Benefits:**
- ✅ Policy reuse (don't duplicate 90% of baseline)
- ✅ Clear variation points (see only overrides)
- ✅ Easy to maintain (change baseline → all children reflect)

### 3. Add Multi-Environment Support

**Configuration per environment:**
```yaml
# environment-config.yaml
environments:
  production:
    security_policy_ref: sec-strict
    defaults: {backup: yes, monitoring: yes, audit: yes}
  staging:
    security_policy_ref: sec-baseline
    defaults: {backup: yes, monitoring: yes, audit: no}
  development:
    security_policy_ref: sec-relaxed
    defaults: {backup: no, monitoring: no, audit: no}

active_environment: production  # Can be overridden via CLI
```

**Usage in L1-L7:**
```yaml
# Any layer can query
security_policy_ref: ${L0.environments[active_environment].security_policy_ref}
backup_enabled: ${L0.environments[active_environment].defaults.backup_enabled}
```

**Benefits:**
- ✅ Single topology.yaml works for prod/staging/dev
- ✅ Different security policies per environment
- ✅ Different monitoring/backup requirements per environment
- ✅ Easy to test topology in staging before prod

### 4. Introduce Regional Policies

**Per-region overrides:**
```yaml
# regional-policies/eu-west.yaml
region: eu-west
gdpr_compliant: true
firewall_policy_overrides:
  - allow_geo_blocking: true
  - log_retention_days: 730  # GDPR requirement

# regional-policies/us-east.yaml
region: us-east
hipaa_compliant: false
```

**Benefits:**
- ✅ Region-specific compliance (GDPR in EU, etc.)
- ✅ Region-specific performance tuning
- ✅ Region-specific security policies

### 5. Add Auditability

**All policies track:**
```yaml
id: sec-baseline
created_at: 2026-02-16
created_by: dmitri@home-lab
last_modified_at: 2026-02-26
last_modified_by: dmitri@home-lab
version: 4.0.0
```

**Benefits:**
- ✅ Know who created/modified each policy
- ✅ Version policies independently
- ✅ Compliance audit trail

### 6. Separate Changelog from Meta

**Move from L0-meta.yaml to changelog.yaml:**
```yaml
changelog:
  - version: 4.0.0
    date: 2026-02-17
    changes: [list of changes]
    breaking_changes: [list]
    migration_guide: "See docs/..."
```

**Benefits:**
- ✅ Clear versioning history
- ✅ Easy to see what changed per version
- ✅ Separate from structural metadata

---

## Consequences

### Positive

1. **Flexibility:** Different environments use same topology with different configs
2. **Reusability:** Security policies use inheritance (no duplication)
3. **Scalability:** Modular structure scales to 10+ policies/regions without bloat
4. **Maintainability:** Each concern in separate file (easier to review/update)
5. **Auditability:** Full history of who changed what when
6. **Upper layers:** L1-L7 can reference environment-specific defaults (e.g., SLO from active env)

### Trade-offs

1. **Complexity:** More files to manage (9 instead of 1)
2. **Validation overhead:** New validators needed for inheritance + environment config
3. **Migration effort:** Need to split L0-meta.yaml and update generators
4. **Documentation:** Need to explain policy inheritance and environment selection

### Backward Compatibility

**Phase 1 (dual mode):**
- Keep old L0-meta.yaml functional
- New L0-meta/_index.yaml in parallel
- Generators try new structure first, fall back to old

**Phase 2 (migration):**
- Move all data from old to new structure
- Update all generators to use modular L0

**Phase 3 (cleanup):**
- Remove old L0-meta.yaml
- Deprecate legacy structure

---

## Implementation Plan

### Week 1: Preparation
- [ ] Create L0-meta/ directory structure
- [ ] Create version.yaml, environment-config.yaml
- [ ] Create defaults/{refs, compliance, audit, feature-flags}.yaml
- [ ] Document mapping from old L0-meta.yaml to new structure

### Week 2: Security Policies
- [ ] Create security-policies/_base.yaml (abstract template)
- [ ] Create baseline.yaml, strict.yaml, relaxed.yaml
- [ ] Create policy-registry.yaml (inheritance map)
- [ ] Test policy inheritance logic

### Week 3: Regional & Changelog
- [ ] Create regional-policies/ (us-east, eu-west, apac)
- [ ] Move changelog to separate file
- [ ] Create _index.yaml that includes everything
- [ ] Update topology loader to handle modular L0

### Week 4: Validation & Testing
- [ ] Write L0 validators (inheritance check, ref validation)
- [ ] Test multi-environment loading (--environment=staging)
- [ ] Test regional policy override
- [ ] Update docs/MIGRATION-4.1.0.md

### Week 5: Migration
- [ ] Update generators to use modular L0
- [ ] Test Terraform generation with different environments
- [ ] Test Ansible inventory with different policies
- [ ] Create migration guide for team

---

## Integration with Existing Layers (L1-L7)

### How L1 Consumes L0
```yaml
# L1 device can now reference environment-specific policy
device:
  security_policy_ref: ${L0.environments[${ENVIRONMENT}].security_policy_ref}
  ssh_port: ${L0.defaults.refs.network.ssh_port}
```

### How L2 Consumes L0
```yaml
# L2 firewall can inherit base policy
firewall_policy:
  base: ${L0.security.policies[${L0.environments[${ENVIRONMENT}].security_policy_ref}].firewall_policy}
```

### How L5 Consumes L0
```yaml
# L5 services get environment-specific defaults
service:
  audit_enabled: ${L0.environments[${ENVIRONMENT}].defaults.audit_logging}
  slo_target: ${L0.environments[${ENVIRONMENT}].constraints.require_sla}
```

### How L6 Consumes L0
```yaml
# L6 monitoring follows environment config
alert:
  log_retention_days: ${L0.security.baseline.audit_policy.log_retention_days}
  enabled_in: ${L0.environments[${ENVIRONMENT}].defaults.monitoring_enabled}
```

### How L7 Consumes L0
```yaml
# L7 operations respect environment SLA
incident_policy:
  escalation_time_min: ${L0.environments[${ENVIRONMENT}].constraints.require_sla}
```

---

## Metrics & Success Criteria

### Modularity
- [ ] L0 split into 9 files (was 1)
- [ ] Each file ≤ 100 lines (except _index.yaml)
- [ ] No duplication across files

### Environment Support
- [ ] Topology loads with `--environment=production|staging|development`
- [ ] Each environment gets correct security_policy_ref
- [ ] Each environment gets correct defaults

### Policy Inheritance
- [ ] 3 policies with inheritance (baseline, strict, relaxed)
- [ ] Inheritance validator catches circular references
- [ ] Policy overrides work (child policy overrides parent)

### Backward Compatibility
- [ ] Old L0-meta.yaml still works (dual mode)
- [ ] Generators produce identical output
- [ ] No breaking changes to L1-L7 refs

### Auditability
- [ ] All policies track created_by, created_at, modified_by, modified_at
- [ ] Changelog tracks breaking changes per version
- [ ] Migration guides provided

---

## References

- ADR 0026: L3/L4 taxonomy (inheritance patterns)
- ADR 0034: L4 modularization (template patterns)
- ADR 0047: L6 modularization (modular structure lessons)
- ADR 0048: 10x growth strategy (scalability requirements)
- L0-META-LAYER-ANALYSIS-REFACTORING.md (detailed design)

---

**Approval:** Pending architecture review

**Next steps:**
1. Review and approve this ADR
2. Begin Phase 1 implementation (Week 1)
3. Test multi-environment support
4. Document migration guide
