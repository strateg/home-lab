# End-to-End Scenario: ADR 0089-0091 SOHO Product Contracts

**Document Version:** 1.0
**Date:** 2026-04-08
**Purpose:** Demonstrate how ADR 0089 (Product Profile), ADR 0090 (Operator Lifecycle), and ADR 0091 (Readiness Evidence) work together in practice.

---

## Scenario Overview

**Operator Goal:** Deploy a managed SOHO network from scratch with full backup/restore capability and operator handover readiness.

**Deployment Target:**
- **Hardware:** MikroTik Chateau LTE7 ax (router), Proxmox VE 9 on Dell XPS (hypervisor), Orange Pi 5 (SBC)
- **Deployment Class:** `managed-soho` (supports 5-25 users)
- **Profile:** `soho.standard.v1`
- **Migration State:** `migrated-hard` (full validation enforcement)

**Success Criteria:**
- Infrastructure deployed and operational
- Backup/restore tested and validated
- Handover package complete
- Readiness status: `green`

---

## Phase 1: Project Initialization (ADR 0089 + ADR 0090)

### Step 1.1: Create Project with Product Profile

**Operator Action:**

```bash
# Create new project directory
mkdir projects/home-lab-prod
cd projects/home-lab-prod

# Create project.yaml with product profile (ADR 0089 D1)
cat > project.yaml <<EOF
project:
  name: home-lab-prod
  version: "1.0.0"

# ADR 0089: Product profile is mandatory for migrated projects
product_profile:
  profile_id: soho.standard.v1
  deployment_class: managed-soho
  site_class: single-site
  user_band: 5-25
  operator_mode: single-operator
  release_channel: stable
  migration_state: migrated-hard    # Full enforcement (ADR 0089 D9)

# Project-specific overrides
backup_schedule: "0 2 * * *"  # Daily at 2 AM
maintenance_window:
  start: "22:00"
  end: "06:00"
  timezone: "UTC"
EOF
```

**System Behavior:**

1. **Profile Resolution (ADR 0089 D4):**
   - Profile ID `soho.standard.v1` is loaded from `topology/product-profiles/soho.standard.v1.yaml`
   - Deployment class `managed-soho` triggers bundle resolution:
     - Core bundles: `edge-routing`, `network-segmentation`, `secrets-governance`
     - Class-specific bundles: `remote-access`, `backup-restore`, `observability`, `operator-workflows`, `update-management`
     - **Effective bundle set: 8 bundles**

2. **Migration State Enforcement (ADR 0089 D7 + D9):**
   - `migrated-hard` state → **all validation is blocking**
   - Missing profile or incompatible deployment class → pipeline halts

**Outcome:**
- ✅ Valid `project.yaml` with product profile
- ✅ Migration state set to `migrated-hard`

---

### Step 1.2: Run `product:init`

**Operator Action:**

```bash
# ADR 0090 D2: Use canonical operator task
task product:init
```

**System Behavior (ADR 0090 D4 expanded semantics):**

1. **Validates product profile:**
   - Checks `project.yaml` contains valid `product_profile`
   - Validates against `schemas/product-profile.schema.json`
   - ✅ Profile valid: `soho.standard.v1` + `managed-soho`

2. **Creates workspace state:**
   - Creates `.work/deploy/state/home-lab-prod/`
   - Writes `init-state.json`:
     ```json
     {
       "status": "initialized",
       "timestamp": "2026-04-08T10:00:00Z",
       "profile_id": "soho.standard.v1",
       "deployment_class": "managed-soho",
       "validated_bundles": [
         "bundle.edge-routing",
         "bundle.network-segmentation",
         "bundle.secrets-governance",
         "bundle.remote-access",
         "bundle.backup-restore",
         "bundle.observability",
         "bundle.operator-workflows",
         "bundle.update-management"
       ],
       "terraform_providers": ["bpg/proxmox", "terraform-routeros/routeros"]
     }
     ```

3. **Initializes Terraform:**
   - Runs `terraform init` → downloads provider plugins
   - **Does NOT create infrastructure** (ADR 0090 D4 prohibited side effects)

4. **Verifies secrets access:**
   - Checks age keys at `~/.config/sops/age/keys.txt`
   - ✅ Keys available (does not decrypt yet)

**Outcome:**
- ✅ Workspace initialized
- ✅ Provider plugins downloaded
- ✅ Bundle graph validated
- ✅ Operator can proceed to planning

---

### Step 1.3: Check Status with `product:doctor`

**Operator Action:**

```bash
# ADR 0090 D6: Single operator-ready status entrypoint
task product:doctor
```

**System Output:**

```
SOHO Product Status - home-lab-prod
====================================

Product Profile:     soho.standard.v1
Deployment Class:    managed-soho
Migration State:     migrated-hard (full enforcement)

Lifecycle Preconditions:
  [✓] Project initialized (init-state.json valid)
  [✓] Product profile compatible
  [✓] Bundle graph complete (8/8 bundles resolved)
  [✓] Secrets access validated
  [✓] Terraform providers ready

Readiness Evidence (ADR 0091):
  [!] greenfield-first-install: MISSING
  [!] backup-and-restore: MISSING
  [!] operator-handover: MISSING

Overall Status: YELLOW
  - Ready for planning and deployment
  - Evidence will be collected during lifecycle execution
  - Handover readiness will improve as tasks complete
```

**Outcome:**
- ✅ Status: YELLOW (expected for new project)
- ✅ Infrastructure preconditions met
- ⚠️ Evidence missing (will be created during lifecycle)

---

## Phase 2: Planning and Deployment (ADR 0090)

### Step 2.1: Generate Deployment Plan

**Operator Action:**

```bash
# ADR 0090 D2: Canonical plan task
task product:plan
```

**System Behavior (ADR 0090 D7 preconditions):**

1. **Validates preconditions:**
   - Topology validates clean: `compile-topology.py --validate` → exit 0 ✅
   - Profile/bundle set resolved ✅
   - Migration state `migrated-hard` → full validation blocking

2. **Compiles topology:**
   - Runs plugin pipeline (ADR 0089 D6):
     - **Discover:** Resolves profile, deployment class, hardware compatibility
     - **Compile:** Materializes effective bundle graph (8 bundles)
     - **Validate:** Enforces required bundles, profile/class compatibility (blocking mode)

3. **Generates artifacts:**
   - Creates `generated/home-lab-prod/terraform/proxmox/` (VMs, LXC, networks)
   - Creates `generated/home-lab-prod/terraform/mikrotik/` (firewall, VLANs, VPN)
   - Creates `generated/home-lab-prod/ansible/inventory.yaml`
   - Creates handover artifacts (ADR 0091 D1):
     - `generated/home-lab-prod/product/handover/SYSTEM-SUMMARY.md`
     - `generated/home-lab-prod/product/handover/NETWORK-SUMMARY.md`
     - `generated/home-lab-prod/product/handover/BACKUP-RUNBOOK.md`

4. **Creates deploy bundle (ADR 0085):**
   - Bundles all artifacts into `.work/deploy/bundles/bundle-20260408-100530/`
   - Writes `bundle-manifest.json` with checksums

5. **Runs Terraform plan:**
   - `terraform plan -out=tfplan` for both Proxmox and MikroTik
   - Saves plan snapshot to bundle directory

**Outcome:**
- ✅ Deploy bundle created
- ✅ Terraform plan saved
- ✅ Handover artifacts generated (partial)
- ✅ Operator can review changes before apply

---

### Step 2.2: Apply Deployment

**Operator Action:**

```bash
# ADR 0090 D2: Canonical apply task
# ADR 0090 D7: Requires valid plan snapshot
task product:apply -- BUNDLE=bundle-20260408-100530
```

**System Behavior:**

1. **Validates preconditions (ADR 0090 D7):**
   - Valid plan snapshot exists ✅
   - Plan checksum matches ✅
   - Maintenance window active OR `--force` flag (check current time) ✅

2. **Applies Terraform:**
   - Runs `terraform apply tfplan` for Proxmox → creates VMs, LXC containers, networks
   - Runs `terraform apply tfplan` for MikroTik → configures firewall, VLANs, VPN

3. **Runs Ansible:**
   - Configures LXC containers with services
   - Sets up monitoring (observability bundle)
   - Configures backup targets (backup-restore bundle)

4. **Records evidence (ADR 0091 D3):**
   - Logs deployment to `.work/deploy-state/home-lab-prod/logs/deploy-20260408.jsonl`
   - Creates evidence: `greenfield-first-install` → COMPLETE
   - Updates `generated/home-lab-prod/product/reports/health-report.json`

**Outcome:**
- ✅ Infrastructure deployed
- ✅ Services running
- ✅ First evidence domain complete: `greenfield-first-install`

---

## Phase 3: Backup and Restore Validation (ADR 0091)

### Step 3.1: Create Backup

**Operator Action:**

```bash
# ADR 0090 D2: Canonical backup task
task product:backup
```

**System Behavior:**

1. **Validates preconditions (ADR 0090 D7):**
   - Backup targets reachable (SSH connectivity test) ✅
   - Secrets access validated (age keys available) ✅

2. **Creates backup:**
   - Backs up Proxmox VM/LXC configs
   - Backs up MikroTik router config export
   - Backs up Terraform state files
   - Backs up topology YAML files
   - Encrypts backup with SOPS/age

3. **Generates backup evidence (ADR 0091 D4):**
   - Writes `generated/home-lab-prod/product/reports/backup-status.json`:
     ```json
     {
       "schema_version": "1.0",
       "timestamp": "2026-04-08T12:00:00Z",
       "last_backup_date": "2026-04-08T12:00:00Z",
       "backup_size_mb": 450,
       "backup_targets": ["rsync://backup.local/home-lab-prod"],
       "backup_integrity": "verified",
       "completeness_state": "partial"  // No restore drill yet
     }
     ```
   - Evidence domain: `backup-and-restore` → **PARTIAL** (backup exists, no drill yet)

**Outcome:**
- ✅ Backup created and encrypted
- ✅ Backup integrity verified
- ⚠️ Evidence still PARTIAL (restore drill required per ADR 0091 D4 criteria)

---

### Step 3.2: Run Restore Drill

**Operator Action:**

```bash
# ADR 0090 D2: Canonical restore task
# ADR 0090 D7: Requires explicit restore mode
task product:restore -- MODE=drill BUNDLE=bundle-20260408-100530
```

**System Behavior:**

1. **Validates preconditions (ADR 0090 D7):**
   - Restore source integrity: checksum validation ✅
   - Explicit restore mode set: `--mode=drill` ✅

2. **Runs restore drill (non-destructive):**
   - Decrypts backup archive
   - Validates all files present
   - Checks topology YAML integrity
   - Validates Terraform state consistency
   - **Does NOT apply restore** (drill mode)

3. **Updates evidence (ADR 0091 D4):**
   - Writes `generated/home-lab-prod/product/reports/restore-readiness.json`:
     ```json
     {
       "schema_version": "1.0",
       "timestamp": "2026-04-08T13:00:00Z",
       "last_restore_drill_date": "2026-04-08T13:00:00Z",
       "drill_result": "passed",
       "restore_time_estimate_minutes": 15,
       "completeness_state": "complete"
     }
     ```
   - Evidence domain: `backup-and-restore` → **COMPLETE**
     - Backup < 7 days old ✅
     - Restore drill passed < 30 days ✅

**Outcome:**
- ✅ Restore drill passed
- ✅ Evidence domain `backup-and-restore` now COMPLETE

---

## Phase 4: Handover Readiness (ADR 0091)

### Step 4.1: Generate Handover Package

**Operator Action:**

```bash
# ADR 0090 D2: Canonical handover task
task product:handover
```

**System Behavior:**

1. **Validates preconditions (ADR 0090 D7):**
   - Readiness evidence completeness check (ADR 0091 D3)
   - Checks all required evidence domains

2. **Assembles handover artifacts (ADR 0091 D1):**

   Generated artifacts in `generated/home-lab-prod/product/handover/`:

   - `SYSTEM-SUMMARY.md` — Infrastructure overview, hardware specs
   - `NETWORK-SUMMARY.md` — VLAN layout, firewall rules, VPN config
   - `ACCESS-RUNBOOK.md` — SSH keys, web UI URLs, admin credentials location
   - `BACKUP-RUNBOOK.md` — Backup schedule, restore procedure
   - `RESTORE-RUNBOOK.md` — Step-by-step restore instructions
   - `UPDATE-RUNBOOK.md` — Update workflow, rollback procedure
   - `INCIDENT-CHECKLIST.md` — Troubleshooting guide
   - `ASSET-INVENTORY.csv` — All devices, IPs, MAC addresses
   - `CHANGELOG-SNAPSHOT.md` — Recent changes, deployment history

   **Secret sanitization (ADR 0091 D8):**
   - Passwords → `[REDACTED]`
   - IP addresses → `10.0.10.xxx`
   - SSH keys → fingerprints only

3. **Generates readiness reports (ADR 0091 D1):**

   `generated/home-lab-prod/product/reports/`:

   - `health-report.json` — Service status, connectivity checks
   - `drift-report.json` — Configuration drift detection results
   - `backup-status.json` — Backup age, integrity (from Step 3.1)
   - `restore-readiness.json` — Restore drill results (from Step 3.2)
   - `support-bundle-manifest.json` — Package completeness manifest

4. **Validates handover completeness (ADR 0091 D5):**
   - All D1 artifacts present ✅
   - JSON reports pass schema validation ✅
   - Evidence domains checked:
     - `greenfield-first-install`: COMPLETE ✅
     - `backup-and-restore`: COMPLETE ✅
     - `operator-handover`: COMPLETE ✅ (all artifacts present)

5. **Creates immutable handover package:**
   - Archives to `.work/deploy/handover/home-lab-prod-20260408.tar.gz`
   - Signs with age key
   - Writes `handover-manifest.json` with checksums

**Outcome:**
- ✅ Handover package complete
- ✅ All required artifacts present
- ✅ Secret hygiene validated
- ✅ Evidence domain `operator-handover` → COMPLETE

---

### Step 4.2: Final Readiness Check

**Operator Action:**

```bash
# ADR 0090 D6: Check final status
task product:doctor
```

**System Output:**

```
SOHO Product Status - home-lab-prod
====================================

Product Profile:     soho.standard.v1
Deployment Class:    managed-soho
Migration State:     migrated-hard (full enforcement)

Lifecycle Preconditions:
  [✓] Project initialized
  [✓] Product profile compatible
  [✓] Bundle graph complete (8/8 bundles)
  [✓] Infrastructure deployed
  [✓] Services operational

Readiness Evidence (ADR 0091 D4):
  [✓] greenfield-first-install: COMPLETE (2026-04-08, < 90 days)
  [✓] backup-and-restore: COMPLETE
      - Last backup: 2026-04-08 (< 7 days)
      - Restore drill: PASSED (2026-04-08, < 30 days)
  [✓] operator-handover: COMPLETE
      - All 9 handover artifacts present
      - JSON reports schema-validated
      - Secret sanitization verified

Diagnostics:
  [✓] No critical diagnostics (E7941-E7949)
  [✓] No warnings

Overall Status: GREEN (ADR 0091 D4)
  - All required evidence complete
  - No critical diagnostics
  - Ready for production handover

Handover Package:
  Location: .work/deploy/handover/home-lab-prod-20260408.tar.gz
  Size: 12 MB
  Checksum: sha256:abc123...
```

**Outcome:**
- ✅ **Readiness Status: GREEN**
- ✅ All evidence domains COMPLETE
- ✅ Release gate passed (ADR 0091 D5)
- ✅ Handover package ready for operator transfer

---

## Phase 5: Release Gate Validation (ADR 0091 D5)

### Step 5.1: Automated Release Gate Check

**System Behavior (ADR 0091 D5):**

Release gate checks:

1. **Handover package completeness:**
   - ✅ All 9 required artifacts present
   - ✅ JSON reports schema-validated
   - ✅ Manifest checksums valid

2. **Backup/restore evidence:**
   - ✅ Backup exists and < 7 days old
   - ✅ Restore drill passed < 30 days

3. **Critical diagnostics:**
   - ✅ No E7941-E7949 errors
   - ✅ No blocking warnings

4. **Acceptance evidence (ADR 0091 D3):**
   - ✅ `greenfield-first-install`: COMPLETE
   - ✅ `backup-and-restore`: COMPLETE
   - ✅ `operator-handover`: COMPLETE
   - ⚠️ Other domains (update, rollback, secret-rotation) not yet applicable (new deployment)

**Release Decision:**

```
Release Gate: PASSED

Readiness: GREEN
Evidence: 3/3 required domains COMPLETE
Blocking Issues: 0
Handover Package: VALID

Status: APPROVED FOR PRODUCTION HANDOVER
```

**Outcome:**
- ✅ **Release approved**
- ✅ Operator can receive handover package
- ✅ Deployment considered production-ready

---

## Summary: ADR Integration

### How ADR 0089 (Product Profile) Was Used

1. **Profile Definition:** `soho.standard.v1` defined support boundary
2. **Deployment Class:** `managed-soho` selected → 8 required bundles resolved
3. **Migration State:** `migrated-hard` enforced blocking validation
4. **Pipeline Stages:** Discover → Compile → Validate with full enforcement
5. **Bundle Resolution:** Deterministic (core + class-specific bundles)

### How ADR 0090 (Operator Lifecycle) Was Used

1. **Init Phase:** `product:init` validated profile and initialized workspace
2. **Plan Phase:** `product:plan` generated deployment plan and bundle
3. **Apply Phase:** `product:apply` deployed infrastructure with precondition checks
4. **Backup Phase:** `product:backup` created encrypted backup
5. **Restore Phase:** `product:restore --mode=drill` validated restore capability
6. **Handover Phase:** `product:handover` assembled operator package
7. **Status Check:** `product:doctor` provided normalized readiness status

### How ADR 0091 (Readiness Evidence) Was Used

1. **Evidence Domains:** Tracked `greenfield-first-install`, `backup-and-restore`, `operator-handover`
2. **Completeness States:** Transitioned from MISSING → PARTIAL → COMPLETE
3. **Handover Artifacts:** Generated all 9 required MD/CSV/JSON artifacts
4. **Readiness Reports:** Created schema-validated JSON reports
5. **Release Gate:** Enforced blocking release criteria (all passed)
6. **Secret Hygiene:** Applied deterministic sanitization rules

---

## Key Takeaways

1. **Product Profile is source of truth:** All bundle resolution, validation enforcement, and support boundaries derive from `product_profile` in `project.yaml`

2. **Lifecycle tasks are thin wrappers:** `product:*` tasks delegate to existing framework contracts (deploy bundles, Terraform, Ansible) without creating parallel execution planes

3. **Evidence drives readiness:** Readiness state transitions from RED → YELLOW → GREEN based on objective evidence criteria (timestamps, drill results, artifact completeness)

4. **Release gate is non-negotiable:** Missing evidence or critical diagnostics block handover, ensuring operator receives production-ready deployment

5. **Migration state controls strictness:** `migrated-hard` enforces full blocking validation, preventing drift from product contract

---

## Operator Experience Timeline

| Time | Phase | Task | Duration | Outcome |
|---|---|---|---|---|
| T+0h | Init | `product:init` | 2 min | Workspace ready |
| T+0h | Status | `product:doctor` | 30 sec | Status: YELLOW |
| T+1h | Plan | `product:plan` | 15 min | Deploy bundle created |
| T+2h | Deploy | `product:apply` | 30 min | Infrastructure live |
| T+12h | Backup | `product:backup` (scheduled) | 5 min | Backup created |
| T+13h | Drill | `product:restore --mode=drill` | 10 min | Restore validated |
| T+14h | Handover | `product:handover` | 5 min | Package ready |
| T+14h | Final Check | `product:doctor` | 30 sec | Status: GREEN ✅ |

**Total Active Operator Time:** ~70 minutes
**Total Elapsed Time:** ~14 hours (mostly automated/scheduled)

---

## Appendix: Full Evidence State Progression

| Evidence Domain | After Init | After Apply | After Backup | After Restore Drill | After Handover |
|---|---|---|---|---|---|
| greenfield-first-install | MISSING | **COMPLETE** | COMPLETE | COMPLETE | COMPLETE |
| backup-and-restore | MISSING | MISSING | **PARTIAL** | **COMPLETE** | COMPLETE |
| operator-handover | MISSING | MISSING | MISSING | MISSING | **COMPLETE** |
| **Readiness Status** | **YELLOW** | **YELLOW** | **YELLOW** | **YELLOW** | **GREEN** |

Final state achieves GREEN when all required domains transition to COMPLETE.
