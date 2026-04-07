# ADR 0093 CUTOVER CHECKLIST

**Last updated:** 2026-04-07

**Status:** Waves 1-3 completed, Wave 4+ pending.

## Wave 1: Schema Completeness

### Schema Definition

- [x] `schemas/artifact-plan.schema.json` exists
- [x] `schemas/artifact-generation-report.schema.json` exists
- [x] Required fields marked per D9
- [x] Enums defined: `renderer` (jinja2|structured|programmatic)
- [x] Enums defined: `obsolete.action` (retain|delete|warn)
- [x] `schema_version` field present in both schemas

### State Storage

- [x] `.state/artifact-plans/` directory created on first run
- [x] State file naming: `<plugin_id>.json`
- [x] Previous plan loadable for ownership check

### Wave 1 Sign-off

- [x] Schema validates test ArtifactPlan samples
- [x] Schema validates test ArtifactGenerationReport samples
- [x] State storage write/read works

**Approver:** _________________ **Date:** _________

---

## Wave 2: Runtime + Ownership + Rollback

### Generator Integration

- [x] Terraform MikroTik generator emits valid ArtifactPlan
- [x] Terraform Proxmox generator emits valid ArtifactPlan
- [x] `migration_mode` field added to generator manifest schema
- [x] Migration status visible in validate stage output

### Ownership Proof (D12)

- [x] Previous plan match verification implemented
- [x] Output prefix match verification implemented
- [x] Ownership marker scan (fallback) implemented
- [x] Three-method verification flow chained correctly
- [x] CI gate blocks delete without ownership proof
- [x] Ownership conflict detection (overlapping prefixes) returns hard error
- [x] Test: unproven delete fails CI
- [x] Test: ownership conflict detected

### Rollback Procedure (D14)

- [x] `migration_mode: rollback` accepted in manifest
- [x] Rollback mode skips ArtifactPlan requirement
- [x] Rollback event logged to audit/evidence trail
- [x] 7-day escalation warning implemented
- [x] Rollback procedure documented in `docs/runbooks/`
- [x] Test: rollback mode works
- [x] Test: escalation warning after 7 days

### Wave 2 Sign-off

- [x] Pilot generators produce valid plans
- [x] Ownership proof fully operational
- [x] Rollback procedure tested and documented

**Approver:** _________________ **Date:** _________

---

## Wave 3: Build Wiring + Pilot Sunset

### Metadata Consumption

- [x] Assemble stage consumes generation metadata
- [x] Build stage consumes generation metadata
- [x] `artifact-family-summary.json` published
- [x] Consistency checks: planned vs generated vs skipped

### Sunset Enforcement for Pilots (D13)

- [x] Deprecation warnings emitted for `terraform_mikrotik`
- [x] Deprecation warnings emitted for `terraform_proxmox`
- [x] 2-week grace period implemented
- [x] Hard error enforced after grace period
- [x] Sunset dates documented in CI config
- [x] Test: legacy pilot after sunset fails CI

### Wave 3 Sign-off

- [x] Metadata consumed by downstream stages
- [x] Pilot families enforced post-sunset

**Approver:** _________________ **Date:** _________

---

## Wave 4: Secondary Families + Sunset

### Secondary Family Migration

- [x] Ansible inventory generator emits ArtifactPlan
- [x] Ansible group_vars artifacts are covered by ArtifactPlan (via `base.generator.ansible_inventory`)
- [x] Bootstrap scripts generator emits ArtifactPlan
- [x] Ownership proof applies to all new families

### Sunset Schedule

- [x] Secondary family sunset dates defined
- [x] Deprecation warnings active
- [x] Grace period + hard error flow same as pilots

### Wave 4 Sign-off

- [x] All secondary families migrated
- [x] Sunset enforcement consistent

**Approver:** _________________ **Date:** _________

---

## Wave 5: Cleanup

### Compatibility Mode Removal

- [ ] Legacy generator detection code removed
- [ ] Fallback paths in validate stage removed
- [x] Compatibility shims removed
- [x] No `migration_mode: legacy` in any target family

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

- [x] CI runs clean with no legacy warnings
- [x] Ownership proof prevents accidental deletion
- [x] Sunset enforcement visible in logs
- [x] Rollback procedure documented and tested

### Monitoring

- [ ] Migration status metrics collected
- [x] Obsolete action audit available
- [x] Rollback events tracked
