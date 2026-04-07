# ADR 0093 IMPLEMENTATION PLAN

**Last updated:** 2026-04-07

## Wave 1 — Schema and Invariants

### 1.1 Schema Definition

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 1.1.1 | Create `schemas/artifact-plan.schema.json` | Schema validates sample plans |
| 1.1.2 | Create `schemas/artifact-generation-report.schema.json` | Schema validates sample reports |
| 1.1.3 | Define `schema_version` field and policy | Version documented |
| 1.1.4 | Mark required fields per D9 | Schema enforces required |
| 1.1.5 | Define enums: `renderer`, `obsolete.action` | Enums in schema |

### 1.2 State Storage Foundation

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 1.2.1 | Create `.state/artifact-plans/` directory structure | Directory created on first run |
| 1.2.2 | Implement state file write after generation | Plan saved as `<plugin_id>.json` |
| 1.2.3 | Implement state file read for ownership check | Previous plan loadable |

### Wave 1 Gate

- [x] Schemas exist and validate test data
- [x] State directory structure works
- [x] Schema version policy documented (`adr/0093-analysis/SCHEMA-VERSION-POLICY.md`)

## Wave 2 — Runtime Integration + Ownership Proof

### 2.1 Generator Integration

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 2.1.1 | Update Terraform MikroTik generator to emit ArtifactPlan | Valid plan published |
| 2.1.2 | Update Terraform Proxmox generator to emit ArtifactPlan | Valid plan published |
| 2.1.3 | Add `migration_mode` to generator manifest schema | Manifest accepts mode |
| 2.1.4 | Implement migration status output in validate stage | Status visible in logs |

### 2.2 Ownership Proof Implementation (D12)

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 2.2.1 | Implement previous plan match verification | State lookup works |
| 2.2.2 | Implement output prefix match verification | Prefix check works |
| 2.2.3 | Implement ownership marker scan (fallback) | Marker detected |
| 2.2.4 | Create ownership verification flow | Three methods chained |
| 2.2.5 | Add CI gate for delete without proof | CI blocks unproven delete |
| 2.2.6 | Add conflict detection for overlapping prefixes | Conflict is hard error |

### 2.3 Rollback Procedure Implementation (D14)

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 2.3.1 | Add `rollback` to migration_mode enum | Manifest accepts value |
| 2.3.2 | Implement rollback mode behavior in runtime | ArtifactPlan not required |
| 2.3.3 | Add rollback event logging | Event in audit log |
| 2.3.4 | Implement 7-day escalation warning | CI warning after 7 days |
| 2.3.5 | Document rollback procedure in runbook | Runbook in docs/ |

### Wave 2 Gate

- [x] Pilot generators emit valid ArtifactPlan
- [x] Migration status visible in CI
- [x] Ownership proof blocks unproven delete
- [x] Rollback mode works and logs events
- [x] Escalation warning after 7 days

## Wave 3 — Build/Assemble Wiring + Sunset Enforcement

### 3.1 Metadata Consumption

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 3.1.1 | Consume generation metadata in assemble stage | Metadata available |
| 3.1.2 | Consume generation metadata in build stage | Metadata in build output |
| 3.1.3 | Publish artifact-family-summary.json | Summary generated |
| 3.1.4 | Add consistency checks (planned vs generated vs skipped) | Inconsistencies flagged |

### 3.2 Sunset Enforcement for Pilots (D13)

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 3.2.1 | Enable deprecation warnings for pilot families | Warnings in CI |
| 3.2.2 | Implement 2-week grace period after sunset date | Grace period active |
| 3.2.3 | Promote missing ArtifactPlan to hard error post-grace | CI fails for legacy |
| 3.2.4 | Document sunset dates in CI config | Dates in config file |

### Wave 3 Gate

- [x] Assemble/build consume metadata
- [x] Pilot families have sunset warnings
- [x] Hard error enforced after grace period
- [x] Consistency checks work

## Wave 4 — Secondary Families + Compatibility Sunset

### 4.1 Secondary Family Migration

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 4.1.1 | Migrate Ansible inventory generator | Valid ArtifactPlan |
| 4.1.2 | Migrate Ansible group_vars generator | Valid ArtifactPlan |
| 4.1.3 | Migrate bootstrap scripts generator | Valid ArtifactPlan |
| 4.1.4 | Apply ownership proof to new families | Proof works |

### 4.2 Sunset Enforcement for Secondary

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 4.2.1 | Enable sunset warnings for secondary families | Warnings in CI |
| 4.2.2 | Apply grace period and hard error | Same as pilots |

### Wave 4 Gate

- [x] Secondary families migrated
- [x] All target families have sunset schedule
- [x] Ownership proof works for all families

## Wave 5 — Cleanup and Expansion

### 5.1 Compatibility Mode Removal

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 5.1.1 | Remove legacy generator detection code | Code removed |
| 5.1.2 | Remove fallback paths in validate stage | Fallbacks removed |
| 5.1.3 | Remove compatibility shims | Shims removed |
| 5.1.4 | Update documentation | Docs reflect new-only |

### 5.2 Expansion

| Task | Description | Acceptance |
| ---- | ----------- | ---------- |
| 5.2.1 | Roll out to documentation generators | Docs generators migrated |
| 5.2.2 | Roll out to any remaining families | All families migrated |
| 5.2.3 | Remove mixed-mode parity tests | Tests simplified |

### Wave 5 Gate

- [ ] All target families migrated
- [ ] Compatibility mode code removed
- [ ] Documentation updated
- [ ] No mixed-mode tests needed

## Timeline Summary

```
Wave 1 (Schema)
    │
    ├── schemas/artifact-plan.schema.json
    ├── schemas/artifact-generation-report.schema.json
    └── .state/artifact-plans/ structure
    │
    ▼
Wave 2 (Runtime + Ownership + Rollback)
    │
    ├── Pilot generators emit ArtifactPlan
    ├── Ownership proof implementation
    ├── Rollback procedure implementation
    └── CI gates for ownership
    │
    ▼
Wave 3 (Build Wiring + Pilot Sunset)
    │
    ├── Assemble/build consume metadata
    ├── Pilot sunset warnings → grace → hard error
    └── Consistency checks
    │
    ▼
Wave 4 (Secondary Families + Sunset)
    │
    ├── Ansible, bootstrap generators
    └── Secondary sunset schedule
    │
    ▼
Wave 5 (Cleanup)
    │
    ├── Remove compatibility mode
    └── Expand to remaining families
```
