# ADR 0093 CUTOVER CHECKLIST

**Last updated:** 2026-04-06

## Wave 1: Schema Completeness

### Schema Definition

- [ ] `schemas/artifact-plan.schema.json` exists
- [ ] `schemas/artifact-generation-report.schema.json` exists
- [ ] Required fields marked per D9
- [ ] Enums defined: `renderer` (jinja2|structured|programmatic)
- [ ] Enums defined: `obsolete.action` (retain|delete|warn)
- [ ] `schema_version` field present in both schemas

### State Storage

- [ ] `.state/artifact-plans/` directory created on first run
- [ ] State file naming: `<plugin_id>.json`
- [ ] Previous plan loadable for ownership check

### Wave 1 Sign-off

- [ ] Schema validates test ArtifactPlan samples
- [ ] Schema validates test ArtifactGenerationReport samples
- [ ] State storage write/read works

**Approver:** _________________ **Date:** _________

---

## Wave 2: Runtime + Ownership + Rollback

### Generator Integration

- [ ] Terraform MikroTik generator emits valid ArtifactPlan
- [ ] Terraform Proxmox generator emits valid ArtifactPlan
- [ ] `migration_mode` field added to generator manifest schema
- [ ] Migration status visible in validate stage output

### Ownership Proof (D12)

- [ ] Previous plan match verification implemented
- [ ] Output prefix match verification implemented
- [ ] Ownership marker scan (fallback) implemented
- [ ] Three-method verification flow chained correctly
- [ ] CI gate blocks delete without ownership proof
- [ ] Ownership conflict detection (overlapping prefixes) returns hard error
- [ ] Test: unproven delete fails CI
- [ ] Test: ownership conflict detected

### Rollback Procedure (D14)

- [ ] `migration_mode: rollback` accepted in manifest
- [ ] Rollback mode skips ArtifactPlan requirement
- [ ] Rollback event logged to audit
- [ ] 7-day escalation warning implemented
- [ ] Rollback procedure documented in `docs/runbooks/`
- [ ] Test: rollback mode works
- [ ] Test: escalation warning after 7 days

### Wave 2 Sign-off

- [ ] Pilot generators produce valid plans
- [ ] Ownership proof fully operational
- [ ] Rollback procedure tested and documented

**Approver:** _________________ **Date:** _________

---

## Wave 3: Build Wiring + Pilot Sunset

### Metadata Consumption

- [ ] Assemble stage consumes generation metadata
- [ ] Build stage consumes generation metadata
- [ ] `artifact-family-summary.json` published
- [ ] Consistency checks: planned vs generated vs skipped

### Sunset Enforcement for Pilots (D13)

- [ ] Deprecation warnings emitted for `terraform_mikrotik`
- [ ] Deprecation warnings emitted for `terraform_proxmox`
- [ ] 2-week grace period implemented
- [ ] Hard error enforced after grace period
- [ ] Sunset dates documented in CI config
- [ ] Test: legacy pilot after sunset fails CI

### Wave 3 Sign-off

- [ ] Metadata consumed by downstream stages
- [ ] Pilot families enforced post-sunset

**Approver:** _________________ **Date:** _________

---

## Wave 4: Secondary Families + Sunset

### Secondary Family Migration

- [ ] Ansible inventory generator emits ArtifactPlan
- [ ] Ansible group_vars generator emits ArtifactPlan
- [ ] Bootstrap scripts generator emits ArtifactPlan
- [ ] Ownership proof applies to all new families

### Sunset Schedule

- [ ] Secondary family sunset dates defined
- [ ] Deprecation warnings active
- [ ] Grace period + hard error flow same as pilots

### Wave 4 Sign-off

- [ ] All secondary families migrated
- [ ] Sunset enforcement consistent

**Approver:** _________________ **Date:** _________

---

## Wave 5: Cleanup

### Compatibility Mode Removal

- [ ] Legacy generator detection code removed
- [ ] Fallback paths in validate stage removed
- [ ] Compatibility shims removed
- [ ] No `migration_mode: legacy` in any target family

### Documentation

- [ ] ADR 0093 marked as Implemented
- [ ] Runbook updated to remove legacy references
- [ ] Developer guide updated

### Final Sign-off

- [ ] All target families fully migrated
- [ ] Compatibility mode code eliminated
- [ ] Tests simplified (no mixed-mode parity)

**Approver:** _________________ **Date:** _________

---

## Post-Cutover Verification

### Operational

- [ ] CI runs clean with no legacy warnings
- [ ] Ownership proof prevents accidental deletion
- [ ] Sunset enforcement visible in logs
- [ ] Rollback procedure documented and tested

### Monitoring

- [ ] Migration status metrics collected
- [ ] Obsolete action audit available
- [ ] Rollback events tracked
