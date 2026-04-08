# Implementation Plan: ADR 0089-0091 SOHO Product Contracts

**Plan Version:** 1.0
**Date:** 2026-04-08
**Scope:** Resolve critical and high-priority gaps identified in GAP-ANALYSIS.md
**Owner:** Architecture team
**Target Completion:** TBD (after user approval)

---

## Execution Strategy

**Approach:** Phased implementation in 3 waves with validation gates.

| Wave | Scope | Blocking | Duration Estimate |
|---|---|---|---|
| Wave 1 | P0 Critical Fixes (C1-C3) | Yes | 2 days |
| Wave 2 | P1 Important Fixes (I1-I3) | Yes | 1-2 days |
| Wave 3 | P2 Quality Improvements (M1-M8) | No | 1 day |

**Total Effort Estimate:** 4-5 days

---

## Wave 1: Critical Fixes (Blocking)

**Gate:** Wave 1 must be complete before any implementation work begins.

### Task 1.1: Fix Bundle Resolution Ambiguity (C1)

**File:** `adr/0089-soho-product-profile-and-bundle-contract.md`
**Location:** D4 "SOHO bundle resolution is profile-driven"

**Change Required:**

Replace current text:

```markdown
### D4. SOHO bundle resolution is profile-driven

`soho.standard.v1` defines deterministic bundle resolution as:

Core bundles (all deployment classes):
- bundle.edge-routing
- bundle.network-segmentation
- bundle.secrets-governance

Class overlays:
- starter:
  - bundle.remote-access
  - bundle.operator-workflows
...
```

With explicit effective sets:

```markdown
### D4. SOHO bundle resolution is profile-driven

`soho.standard.v1` defines deterministic bundle resolution as **additive composition** of core bundles + deployment-class-specific bundles.

#### Core bundles (required for all deployment classes):

- `bundle.edge-routing`
- `bundle.network-segmentation`
- `bundle.secrets-governance`

#### Deployment-class-specific bundles:

**starter:**
- `bundle.remote-access`
- `bundle.operator-workflows`

**managed-soho:**
- `bundle.remote-access`
- `bundle.backup-restore`
- `bundle.observability`
- `bundle.operator-workflows`
- `bundle.update-management`

**advanced-soho:**
- `bundle.remote-access`
- `bundle.backup-restore`
- `bundle.observability`
- `bundle.operator-workflows`
- `bundle.update-management`
- `bundle.incident-response`
- `bundle.multi-uplink-resilience`

#### Effective bundle resolution (deterministic):

The effective bundle set for a given deployment class is computed as:

```
effective_bundles = core_bundles ∪ class_specific_bundles
```

**Examples:**

For `deployment_class: managed-soho`, the effective bundle set is:

```yaml
effective_bundles:
  - bundle.edge-routing              # core
  - bundle.network-segmentation      # core
  - bundle.secrets-governance        # core
  - bundle.remote-access             # class-specific
  - bundle.backup-restore            # class-specific
  - bundle.observability             # class-specific
  - bundle.operator-workflows        # class-specific
  - bundle.update-management         # class-specific
```

Total: **8 required bundles** for managed-soho.

For `deployment_class: starter`, the effective bundle set is:

```yaml
effective_bundles:
  - bundle.edge-routing              # core
  - bundle.network-segmentation      # core
  - bundle.secrets-governance        # core
  - bundle.remote-access             # class-specific
  - bundle.operator-workflows        # class-specific
```

Total: **5 required bundles** for starter.

Bundle resolution must be deterministic and derived mechanically from the profile and deployment_class, not manually assembled ad hoc per project.
```

**Acceptance Criteria:**
- [ ] Effective bundle set is unambiguous for each deployment class
- [ ] Resolution algorithm is explicit (additive composition)
- [ ] Examples show concrete bundle counts
- [ ] No manual interpretation required

**Effort:** 1 hour

---

### Task 1.2: Create Contract File Examples (C2)

**Directory:** `adr/0089-analysis/examples/`

**Files to Create:**

#### 1.2.1: `product-profile-soho-standard-v1.yaml`

```yaml
# Example product profile contract for SOHO standard v1
# Location: topology/product-profiles/soho.standard.v1.yaml

profile_id: soho.standard.v1
profile_version: "1.0.0"
schema_version: "1.0"

description: |
  Canonical SOHO product profile for single-site, single-operator deployments
  with user counts between 1-25.

supported_deployment_classes:
  - id: starter
    description: Entry-level SOHO with basic routing and remote access
    min_user_band: 1
    max_user_band: 10
    required_bundles:
      - bundle.edge-routing
      - bundle.network-segmentation
      - bundle.secrets-governance
      - bundle.remote-access
      - bundle.operator-workflows

  - id: managed-soho
    description: Standard managed SOHO with backup, observability, updates
    min_user_band: 5
    max_user_band: 25
    required_bundles:
      - bundle.edge-routing
      - bundle.network-segmentation
      - bundle.secrets-governance
      - bundle.remote-access
      - bundle.backup-restore
      - bundle.observability
      - bundle.operator-workflows
      - bundle.update-management

  - id: advanced-soho
    description: Advanced SOHO with incident response and multi-uplink
    min_user_band: 10
    max_user_band: 25
    required_bundles:
      - bundle.edge-routing
      - bundle.network-segmentation
      - bundle.secrets-governance
      - bundle.remote-access
      - bundle.backup-restore
      - bundle.observability
      - bundle.operator-workflows
      - bundle.update-management
      - bundle.incident-response
      - bundle.multi-uplink-resilience

site_class: single-site
operator_mode: single-operator
release_channel: stable

hardware_compatibility:
  supported_routers:
    - mikrotik.chateau.lte7ax
  supported_hypervisors:
    - proxmox.ve.8
    - proxmox.ve.9
  supported_sbcs:
    - orangepi.5.16gb

bundle_resolution_mode: additive  # core + class-specific

migration_states:
  - legacy           # no product_profile, advisory-only
  - migrated-soft    # product_profile present, warnings tolerated
  - migrated-hard    # full blocking enforcement

sunset_policy:
  legacy_end_date: "2026-12-31"  # After this, legacy becomes blocking
```

**Acceptance Criteria:**
- [ ] All deployment classes have explicit required_bundles lists
- [ ] Hardware compatibility matrix present
- [ ] Schema version tracked
- [ ] File is valid YAML

**Effort:** 2 hours

#### 1.2.2: `product-bundle-example.yaml`

```yaml
# Example product bundle contract
# Location: topology/product-bundles/bundle.backup-restore.yaml

bundle_id: bundle.backup-restore
bundle_version: "1.0.0"
schema_version: "1.0"

description: |
  Backup and restore capability bundle for SOHO deployments.
  Provides scheduled backups, restore workflows, and evidence tracking.

category: lifecycle-management

requires:
  bundles:
    - bundle.secrets-governance    # For encrypted backup storage
    - bundle.operator-workflows    # For restore orchestration

provides:
  capabilities:
    - scheduled-backup
    - on-demand-backup
    - restore-from-backup
    - backup-integrity-check
    - restore-readiness-drill

  artifacts:
    - generated/<project>/product/reports/backup-status.json
    - generated/<project>/product/handover/BACKUP-RUNBOOK.md
    - generated/<project>/product/handover/RESTORE-RUNBOOK.md

  runtime_requirements:
    - backup_target_reachable: true
    - secrets_mode: decrypt
    - min_disk_space_gb: 50

deployment_class_support:
  - managed-soho
  - advanced-soho

lifecycle_phases:
  - backup
  - restore

evidence_requirements:
  - backup_exists_within_7_days
  - restore_drill_passed_within_30_days

diagnostics:
  errors:
    - E7943  # backup policy missing
    - E7944  # restore evidence missing
  warnings:
    - W7943  # backup older than 7 days

validation_rules:
  - name: backup_policy_defined
    check: project.yaml contains backup_schedule
    severity: error
    diagnostic_code: E7943

  - name: restore_tested_recently
    check: last_restore_drill < 30 days
    severity: warning
    diagnostic_code: W7944
```

**Acceptance Criteria:**
- [ ] Bundle dependencies explicit
- [ ] Capabilities list concrete
- [ ] Artifacts with paths
- [ ] Diagnostic codes mapped

**Effort:** 2 hours

#### 1.2.3: `product-profile.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://home-lab.local/schemas/product-profile.schema.json",
  "title": "SOHO Product Profile Contract",
  "description": "Schema for SOHO product profile definitions (ADR 0089)",
  "type": "object",
  "required": ["profile_id", "deployment_class", "site_class", "user_band", "operator_mode", "release_channel"],
  "properties": {
    "profile_id": {
      "type": "string",
      "enum": ["soho.standard.v1"],
      "description": "Canonical profile identifier"
    },
    "deployment_class": {
      "type": "string",
      "enum": ["starter", "managed-soho", "advanced-soho"],
      "description": "Deployment class selection"
    },
    "site_class": {
      "type": "string",
      "enum": ["single-site"],
      "description": "Site topology class"
    },
    "user_band": {
      "type": "string",
      "pattern": "^\\d+-\\d+$",
      "description": "User count range (e.g., '1-25')"
    },
    "operator_mode": {
      "type": "string",
      "enum": ["single-operator"],
      "description": "Operator model"
    },
    "release_channel": {
      "type": "string",
      "enum": ["stable", "beta", "dev"],
      "description": "Release channel selection"
    },
    "migration_state": {
      "type": "string",
      "enum": ["legacy", "migrated-soft", "migrated-hard"],
      "description": "Migration state (ADR 0089 D9)"
    }
  },
  "additionalProperties": false
}
```

**Acceptance Criteria:**
- [ ] All D1 fields present in schema
- [ ] Enum values match ADR text
- [ ] Schema validates example project.yaml

**Effort:** 1 hour

**Total Task 1.2 Effort:** 5 hours

---

### Task 1.3: Fix TUC Definition (C3)

**File:** `adr/0091-soho-readiness-evidence-and-handover-artifacts.md`
**Location:** D5 "Release gate is normative"

**Change Required:**

Replace line with TUC:

```markdown
- required TUC evidence set is missing.
```

With explicit reference:

```markdown
- required acceptance evidence (ADR 0091 D3) is incomplete.
```

Add clarification to D3:

```markdown
### D3. Acceptance evidence is mandatory

SOHO readiness requires documented evidence for the following acceptance scenarios:

- **greenfield-first-install** — initial deployment to new hardware
- **brownfield-adoption** — migration from existing network
- **router-replacement** — hardware swap without topology change
- **secret-rotation** — key/password rotation procedure
- **scheduled-update** — routine update workflow
- **failed-update-rollback** — rollback after failed update
- **backup-and-restore** — backup creation and restore drill
- **operator-handover** — knowledge transfer and runbook validation

Each evidence domain must have:
- procedure documentation
- execution logs or artifacts
- validation checkpoints
- last-execution timestamp

Evidence domains map to lifecycle phases (ADR 0090 D1) and must cover all operator-facing workflows.
```

**Acceptance Criteria:**
- [ ] No undefined acronyms
- [ ] Evidence set traceable to lifecycle phases
- [ ] Each domain has clear artifacts

**Effort:** 30 minutes

---

**Wave 1 Total Effort:** ~6.5 hours (1 day)

**Wave 1 Gate Criteria:**
- [ ] All P0 issues resolved
- [ ] Contract examples created and validated
- [ ] ADR changes reviewed and approved

---

## Wave 2: Important Fixes (High Priority)

**Gate:** Wave 2 must be complete before profile validation implementation.

### Task 2.1: Add Migration State → Pipeline Binding (I1)

**File:** `adr/0089-soho-product-profile-and-bundle-contract.md`
**Location:** After D7

**Change Required:**

Add new subsection to D7:

```markdown
### D7. Validation behavior and migration states

Projects are classified as:
- `legacy` — no `product_profile`
- `migrated-soft` — `product_profile` present, warnings may still be tolerated during cutover
- `migrated-hard` — `product_profile` present and all profile requirements are blocking

#### Migration state pipeline enforcement

Pipeline stage behavior is conditional on migration state:

| Migration State | Discover Stage | Compile Stage | Validate Stage |
|---|---|---|---|
| **legacy** | Profile resolution **advisory only**<br/>Diagnostic: INFO | Bundle resolution **advisory only**<br/>Diagnostic: INFO | Compatibility checks **advisory only**<br/>Diagnostic: WARN |
| **migrated-soft** | Profile resolution **required**<br/>Missing profile → ERROR | Bundle resolution **required**<br/>Missing bundles → ERROR | **Warnings allowed**, only critical blocking<br/>Example: backup policy missing → WARN |
| **migrated-hard** | Profile resolution **required**<br/>Missing profile → ERROR, pipeline halt | Bundle resolution **required**<br/>Missing bundles → ERROR, pipeline halt | **All profile requirements blocking**<br/>Any WARN → ERROR, pipeline halt |

**Enforcement mechanism:**

Pipeline stages must:
1. Read `project.yaml → product_profile.migration_state`
2. Adjust diagnostic severity based on state
3. Block or allow pipeline continuation per table above

**State transition rules:**

- `legacy → migrated-soft`: Manual opt-in via `project.yaml` update + validation passes with warnings
- `migrated-soft → migrated-hard`: All warnings resolved + validation passes clean
- Downgrades (e.g., `migrated-hard → legacy`) are **invalid** and rejected by validation

**Sunset enforcement:**

After `sunset_policy.legacy_end_date` (defined in profile contract), `legacy` projects are automatically treated as `migrated-hard` for blocking purposes.

Cutover policy must define when a project moves from `legacy` to `migrated-soft` to `migrated-hard`.
```

**Acceptance Criteria:**
- [ ] Behavior deterministic from migration_state
- [ ] State transitions have explicit gates
- [ ] Sunset policy enforcement clear

**Effort:** 2 hours

---

### Task 2.2: Clarify `product:init` Semantics (I2)

**File:** `adr/0090-soho-operator-lifecycle-and-task-ux-contract.md`
**Location:** After D4 table

**Change Required:**

Add new subsection after D4:

```markdown
### D4. Task semantics are explicit

[existing table remains]

#### Detailed semantics: `product:init`

**Purpose:** Initialize project workspace and validate deployment preconditions without creating infrastructure.

**Side Effects (explicit):**

1. Validates `project.yaml` contains valid `product_profile` (ADR 0089)
2. Creates workspace state directory: `.work/deploy/state/<project>/`
3. Writes initialization state: `.work/deploy/state/<project>/init-state.json`
4. Runs `terraform init` for required providers (downloads provider plugins only, no remote state access)
5. Verifies secrets access: checks age key availability at `~/.config/sops/age/keys.txt` (does **not** decrypt secrets)
6. Validates bundle graph completeness (all required bundles resolvable)

**Side Effects (prohibited):**

- ❌ Does **NOT** create VMs or LXC containers
- ❌ Does **NOT** apply Terraform configurations
- ❌ Does **NOT** modify remote state (Proxmox, MikroTik)
- ❌ Does **NOT** decrypt or write secrets to disk

**Idempotency:** Safe to rerun. Re-validates preconditions and updates `init-state.json` timestamp. Existing workspace preserved.

**Preconditions:**

- Valid `project.yaml` with `product_profile` field
- Age encryption keys present: `~/.config/sops/age/keys.txt`
- Network access to Terraform provider registry (for plugin download)

**Postconditions:**

- `.work/deploy/state/<project>/init-state.json` exists with:
  ```json
  {
    "status": "initialized",
    "timestamp": "2026-04-08T10:30:00Z",
    "profile_id": "soho.standard.v1",
    "deployment_class": "managed-soho",
    "validated_bundles": ["bundle.edge-routing", "..."],
    "terraform_providers": ["bpg/proxmox", "terraform-routeros/routeros"]
  }
  ```
- Terraform providers downloaded to `.terraform/providers/`
- Operator can proceed to `product:plan`

**Failure modes:**

| Failure | Exit Code | Operator Action |
|---|---|---|
| Invalid product_profile | 1 | Fix project.yaml |
| Missing age keys | 2 | Run age-keygen or restore keys |
| Bundle resolution failed | 3 | Check profile/class compatibility |
| Terraform provider download failed | 4 | Check network connectivity |

**Rerun safety:** Operator can rerun `product:init` after fixing precondition failures without risk of state corruption.
```

**Acceptance Criteria:**
- [ ] All side effects explicit (what it does)
- [ ] All prohibited actions explicit (what it doesn't do)
- [ ] Idempotency guarantee clear
- [ ] Failure modes documented

**Effort:** 1.5 hours

---

### Task 2.3: Define "Partial" Evidence States (I3)

**File:** `adr/0091-soho-readiness-evidence-and-handover-artifacts.md`
**Location:** After D4

**Change Required:**

Replace existing D4 with expanded version:

```markdown
### D4. Evidence completeness state is normalized

Each required evidence domain is classified as:

- `missing` — no evidence artifacts exist
- `partial` — evidence exists but fails quality/recency criteria
- `complete` — evidence exists and meets all quality/recency criteria

#### Evidence state criteria (deterministic)

| Evidence Domain | Missing | Partial | Complete |
|---|---|---|---|
| **greenfield-first-install** | No installation logs/artifacts | Install evidence > 90 days old OR missing validation checkpoints | Fresh install evidence < 90 days + all checkpoints passed |
| **brownfield-adoption** | No migration evidence | Migration evidence > 90 days old OR incomplete cutover checklist | Migration evidence < 90 days + cutover checklist 100% |
| **router-replacement** | No replacement procedure docs | Procedure exists but not tested OR last test > 180 days | Procedure tested < 180 days + runbook validated |
| **secret-rotation** | No rotation logs | Last rotation > 180 days OR incomplete rotation checklist | Last rotation < 90 days + all secrets rotated |
| **scheduled-update** | No update logs | Last successful update > 90 days OR update failed | Last successful update < 60 days + release notes archived |
| **failed-update-rollback** | No rollback evidence | Rollback procedure exists but not tested OR test > 180 days | Rollback drill passed < 180 days + runbook validated |
| **backup-and-restore** | No backup exists | Backup > 7 days old OR no restore drill OR drill > 30 days | Valid backup < 7 days + restore drill passed < 30 days |
| **operator-handover** | No handover package | Package exists but missing ≥1 required artifact (ADR 0091 D1) | All D1 artifacts present + schema-validated + reviewed |

**Quality criteria:**

- **Recency**: Time-based thresholds ensure evidence is current
- **Completeness**: All required artifacts/checkpoints present
- **Validation**: Evidence has been tested/verified (not just documented)

**Machine readability:**

Evidence state must be derivable from:
- File timestamps (for recency checks)
- JSON report fields (for validation status)
- Artifact inventory (for completeness checks)

No subjective operator interpretation required.

#### Readiness status derivation (unchanged from original D4)

Readiness status is derived as:

- `green` — no critical diagnostics, all required evidence complete
- `yellow` — no critical diagnostics, but one or more evidence domains partial
- `red` — one or more critical diagnostics or mandatory evidence missing
```

**Acceptance Criteria:**
- [ ] Each domain has objective criteria
- [ ] Time bounds explicit
- [ ] Quality gates (e.g., "drill passed") clear
- [ ] Machine-derivable (no human judgment)

**Effort:** 2 hours

---

**Wave 2 Total Effort:** ~5.5 hours (1 day)

**Wave 2 Gate Criteria:**
- [ ] All P1 issues resolved
- [ ] Pipeline enforcement table added
- [ ] Task semantics expanded
- [ ] Evidence criteria deterministic

---

## Wave 3: Quality Improvements (Non-Blocking)

### Task 3.1: Fix Circular Out-of-Scope (M1)

**Files:** All three ADRs

**Change Required:**

**ADR 0089:** Remove entire "Out of scope" section (base contract should not reference derived contracts)

**ADR 0090:** Keep "Out of scope" as-is (correctly references 0089, 0091)

**ADR 0091:** Keep "Out of scope" as-is (correctly references 0089, 0090)

**Acceptance Criteria:**
- [ ] Dependency graph is acyclic
- [ ] ADR reading order: 0089 → 0090 → 0091

**Effort:** 15 minutes

---

### Task 3.2: Create E2E Scenario (M2)

**File:** `adr/0089-analysis/E2E-SCENARIO.md`

See separate file (next in implementation queue).

**Effort:** 2 hours

---

### Task 3.3: Add Dry-Run Mode (M4)

**File:** `adr/0090-soho-operator-lifecycle-and-task-ux-contract.md`
**Location:** Expand D4 table

**Change Required:**

Add column to D4 table:

| Task | Side effects | Expected mode | Dry-run support | Notes |
|---|---|---|---|---|
| product:apply | yes | controlled execution | `--dry-run` → plan-only | Must depend on valid plan/preconditions |
| product:restore | yes | controlled execution / drill | `--dry-run` → validation-only | Checks restore source integrity without applying |
| product:update | yes | controlled execution | `--dry-run` → preflight-only | Validates update package, does not apply |
| product:backup | yes | controlled execution | `--dry-run` → connectivity check | Verifies backup targets reachable without creating backup |

All tasks with side effects must support `--dry-run` flag for safe preview mode.

**Acceptance Criteria:**
- [ ] Dry-run semantics explicit per task
- [ ] No state mutations in dry-run mode

**Effort:** 30 minutes

---

### Task 3.4: Expand Precondition Table (M5)

**File:** `adr/0090-soho-operator-lifecycle-and-task-ux-contract.md`
**Location:** Expand D7

**Change Required:**

Replace minimal precondition list with table:

| Task | Precondition | How Verified | Failure Diagnostic |
|---|---|---|---|
| `product:plan` | Topology validates clean | `compile-topology.py --validate` exit code 0 | E7941 if profile invalid |
| `product:plan` | Profile/bundle set resolved | `project.yaml` contains `product_profile` + all required bundles exist in graph | E7942 if bundles missing |
| `product:apply` | Valid plan snapshot exists | `.work/deploy/bundles/<id>/plan-snapshot.json` exists + checksum valid | Error if plan missing/stale |
| `product:apply` | Maintenance window active | Current time within `project.yaml → maintenance_window` OR `--force` flag | Warn if outside window |
| `product:backup` | Backup targets reachable | SSH/rsync connectivity test to all backup_targets | E7943 if unreachable |
| `product:backup` | Secrets access validated | Age keys available + test decrypt of sample secret | E7940 if secrets inaccessible |
| `product:restore` | Restore source integrity | Checksum validation of backup archive | E7944 if integrity check fails |
| `product:restore` | Explicit restore mode set | `--mode={drill|recovery}` flag required | Error if mode not specified |
| `product:update` | Preflight validation passes | Update package signature valid + compatibility checks pass | Error if preflight fails |
| `product:update` | Rollback target available | Previous known-good snapshot exists | Warn if no rollback available |
| `product:handover` | Readiness evidence complete | All D3 evidence domains in "complete" state | E7945 if incomplete |

**Acceptance Criteria:**
- [ ] Verification method mechanical
- [ ] Diagnostic codes mapped
- [ ] Failure actions clear

**Effort:** 1 hour

---

### Task 3.5: Create Schema Stubs (M6)

**Directory:** `schemas/`

**Files to Create:**

```bash
# Create stub schemas (minimal valid JSON Schema)
touch schemas/operator-readiness.schema.json
touch schemas/backup-status.schema.json
touch schemas/restore-readiness.schema.json
touch schemas/support-bundle-manifest.schema.json
```

**Example stub (all four):**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://home-lab.local/schemas/operator-readiness.schema.json",
  "title": "Operator Readiness Report",
  "description": "Schema for SOHO readiness evidence reports (ADR 0091 D6)",
  "type": "object",
  "required": ["schema_version", "timestamp", "readiness_status"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "readiness_status": {
      "type": "string",
      "enum": ["green", "yellow", "red"]
    },
    "evidence_domains": {
      "type": "object",
      "description": "Evidence completeness by domain (ADR 0091 D3)"
    }
  }
}
```

**Acceptance Criteria:**
- [ ] All four schemas exist
- [ ] Valid JSON Schema syntax
- [ ] Version tracked

**Effort:** 1 hour

---

### Task 3.6: Clarify MD/CSV Validation (M7)

**File:** `adr/0091-soho-readiness-evidence-and-handover-artifacts.md`
**Location:** Add note after D1

**Change Required:**

Add after D1 artifact list:

```markdown
**Artifact validation scope:**

- **JSON reports** (`reports/*.json`): Schema-validated per ADR 0091 D6
- **Markdown artifacts** (`handover/*.md`): Operator-facing documentation, not schema-validated
- **CSV artifacts** (`handover/*.csv`): Column structure validated via header check, not full schema

Handover completeness check (ADR 0091 D5) verifies:
1. All required files present (filename check)
2. JSON reports pass schema validation
3. Markdown/CSV files are non-empty and have expected structure (header/frontmatter presence)

Quality assurance for Markdown/CSV is operator responsibility during handover review.
```

**Acceptance Criteria:**
- [ ] Validation scope explicit per format
- [ ] Completeness check covers all formats

**Effort:** 20 minutes

---

### Task 3.7: Reference Secret Sanitization Rules (M8)

**File:** `adr/0091-soho-readiness-evidence-and-handover-artifacts.md`
**Location:** Expand D8

**Change Required:**

Replace D8 with:

```markdown
### D8. Secret hygiene is mandatory

Operator artifacts must satisfy ADR 0072 secret hygiene discipline:

- No plaintext tracked secrets in handover outputs
- Deterministic redaction/sanitization in summaries, reports, and manifests
- No unsafe leakage through logs or diagnostic artifacts

**Sanitization rules (ADR 0072 compliance):**

| Secret Type | Sanitization Rule | Example |
|---|---|---|
| Passwords / Passphrases | Full redaction | `[REDACTED]` |
| API tokens / keys | First 4 chars + ellipsis | `sk_test...` (from `sk_test_abc123xyz`) |
| IP addresses (internal) | Preserve subnet, mask host | `10.0.10.xxx` (from `10.0.10.42`) |
| SSH keys | Key type + fingerprint only | `ssh-ed25519 SHA256:abc...` |
| Age keys | Public key only | `age1abc...` (never show private key) |

**Enforcement:**

- Sanitization must be applied during artifact generation, not as post-processing
- Handover package completeness check (ADR 0091 D5) must verify no plaintext secrets leaked
- Violation of secret hygiene blocks release (same severity as missing evidence)

**Reference:** ADR 0072 for full secret management discipline.
```

**Acceptance Criteria:**
- [ ] Sanitization rules explicit
- [ ] References ADR 0072
- [ ] Enforcement mechanism clear

**Effort:** 30 minutes

---

**Wave 3 Total Effort:** ~5 hours (1 day)

**Wave 3 Gate Criteria:**
- [ ] All P2 issues resolved
- [ ] Documentation quality improved
- [ ] Schemas stubbed for future implementation

---

## Summary of Deliverables

### Wave 1 Deliverables (Blocking)
- [ ] ADR 0089 updated with explicit bundle resolution
- [ ] Contract examples created (3 files)
- [ ] ADR 0091 TUC reference fixed

### Wave 2 Deliverables (Blocking)
- [ ] ADR 0089 migration state enforcement table added
- [ ] ADR 0090 product:init semantics expanded
- [ ] ADR 0091 evidence state criteria table added

### Wave 3 Deliverables (Quality)
- [ ] Circular out-of-scope fixed
- [ ] E2E scenario documented
- [ ] Dry-run mode added
- [ ] Precondition table expanded
- [ ] Schema stubs created
- [ ] MD/CSV validation clarified
- [ ] Secret sanitization rules added

### Analysis Artifacts
- [x] `adr/0089-analysis/GAP-ANALYSIS.md` (created)
- [ ] `adr/0089-analysis/IMPLEMENTATION-PLAN.md` (this file)
- [ ] `adr/0089-analysis/E2E-SCENARIO.md`
- [ ] `adr/0089-analysis/examples/product-profile-soho-standard-v1.yaml`
- [ ] `adr/0089-analysis/examples/product-bundle-example.yaml`
- [ ] `adr/0089-analysis/examples/product-profile.schema.json`

---

## Execution Checkpoints

### Before Wave 1
- [ ] User approval of implementation plan
- [ ] Git branch created: `fix/adr-0089-0091-critical-gaps`

### After Wave 1
- [ ] All P0 fixes committed
- [ ] Contract examples validated (YAML/JSON syntax)
- [ ] Peer review of ADR changes

### After Wave 2
- [ ] All P1 fixes committed
- [ ] Tables rendered correctly in Markdown
- [ ] Cross-references between ADRs checked

### After Wave 3
- [ ] All P2 fixes committed
- [ ] Schema stubs pass JSON Schema validation
- [ ] Final review against CLAUDE.md ADR policy

### Final Gate
- [ ] Update `adr/REGISTER.md` with change summary
- [ ] Create PR for review
- [ ] Mark ADRs as "Accepted" (update Status field)

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Contract examples don't match real usage | Medium | High | Validate examples against existing topology files |
| Schema changes break existing code | Low | High | Keep schemas as stubs until validation implementation ready |
| Migration state enforcement too strict | Medium | Medium | Start with migrated-soft as default, document upgrade path |
| Evidence criteria too rigid | Low | Medium | Allow override via project.yaml for exceptional cases |

---

## Post-Implementation Validation

After all waves complete:

1. **Contract validation:**
   - [ ] All YAML examples parse without errors
   - [ ] All JSON schemas validate with jsonschema tool
   - [ ] Cross-references between ADRs resolve correctly

2. **Completeness check:**
   - [ ] All GAP-ANALYSIS issues addressed
   - [ ] No new ambiguities introduced
   - [ ] CLAUDE.md ADR policy compliance verified

3. **Readability review:**
   - [ ] Tables render correctly
   - [ ] Examples are clear and copy-pasteable
   - [ ] No broken internal links

4. **Handover:**
   - [ ] Implementation team briefed on changes
   - [ ] Validator/generator plugin teams notified
   - [ ] Operator documentation updated

---

## Approval Required

**Before proceeding with Wave 1 execution, confirm:**
- [ ] Gap analysis findings are accurate
- [ ] Implementation plan waves are appropriately scoped
- [ ] Effort estimates are reasonable
- [ ] Deliverables match project needs

**Next Step:** Await user approval to begin Wave 1 execution.
