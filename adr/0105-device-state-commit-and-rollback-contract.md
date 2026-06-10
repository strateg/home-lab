# ADR 0105: Device State Management Using Industry Best Practices

**Date:** 2026-06-10
**Status:** Draft
**Related:** ADR 0083, ADR 0084, ADR 0085

> **Note:** Status changed from Proposed to Draft pending Critical issue resolution (C1-C3).
> See `adr/0105-analysis/TECH-LEAD-REVIEW.md` for full critique.

---

## Context

### Problem

The v5 pipeline generates topology-derived artifacts (Terraform, Ansible) that can be applied to infrastructure devices. We need:

1. Controlled state application with validation
2. Rollback capability on failure
3. Audit trail linking topology commits to device states

### Rejected Approach

Initial analysis proposed a custom "State Commit System" with new state machines, snapshot services, and rollback coordinators. This was rejected as over-engineering — **we should not reinvent wheels**.

### Chosen Approach

Use proven industry patterns from each tool:

| Tool | State Management | Rollback Mechanism |
|------|------------------|-------------------|
| **Terraform** | Remote backend with versioning | VCS revert + re-apply |
| **Ansible** | Git + block/rescue/always | Re-apply previous playbook |
| **MikroTik** | RouterOS safe-mode | Auto-revert on disconnect |
| **Proxmox** | Terraform state + VM snapshots | State/snapshot restore |

---

## Decision

### D1. Use Terraform Remote Backend for State

Choose one backend per environment:

**Home Lab (recommended):** GitLab Managed State or local with manual backup

```hcl
# Option A: GitLab managed state
terraform {
  backend "http" {
    address = "https://gitlab.com/api/v4/projects/<ID>/terraform/state/mikrotik"
    # ... lock_address, unlock_address
  }
}

# Option B: Local with backup discipline
terraform {
  backend "local" {
    path = ".work/terraform-state/mikrotik/terraform.tfstate"
  }
}
```

**Benefits:**
- Versioning (rollback to previous state version)
- Locking (prevent concurrent modifications)
- Encryption at rest

### D2. Separate State Per Device

Reduce blast radius by isolating state files:

```
generated/home-lab/terraform/
├── mikrotik/terraform.tfstate
├── proxmox/terraform.tfstate
└── oracle/terraform.tfstate
```

One device failure does not corrupt state for others.

### D3. Use MikroTik Safe-Mode for Network Changes

MikroTik RouterOS has **built-in automatic rollback**:

```bash
# 1. Enter safe-mode (all changes tracked)
# 2. Apply changes via Terraform/API
# 3. If connection lost → auto-revert after 9 minutes
# 4. If connection OK → exit safe-mode with save
```

**Integration script:**
```bash
# Enter safe-mode
curl -k -X POST "https://192.168.88.1/rest/system/safe-mode"

# Apply Terraform
terraform apply

# Health check
curl -k "https://192.168.88.1/rest/system/resource"

# Exit safe-mode (save changes)
curl -k -X POST "https://192.168.88.1/rest/system/safe-mode" -d '{"action":"release"}'
```

### D4. Use Ansible block/rescue/always for Rollback

```yaml
- name: Apply with rollback
  block:
    - name: Apply configuration
      include_tasks: apply-config.yml
    - name: Verify health
      wait_for:
        host: "{{ target_host }}"
        port: 443
  rescue:
    - name: Rollback on failure
      include_tasks: rollback.yml
  always:
    - name: Log result
      debug:
        msg: "{{ 'Applied' if not ansible_failed_task else 'Rolled back' }}"
```

### D5. Export Backup Before Apply (Encrypted + Transferred)

Backups MUST be:
1. Exported from device
2. Transferred to deploy machine
3. Encrypted with SOPS/age
4. Plaintext deleted (on device and locally)

**Workflow:**

```bash
#!/bin/bash
# scripts/backup-before-apply.sh

DEVICE=$1
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=".work/backups/$DEVICE"
mkdir -p "$BACKUP_DIR"

case "$DEVICE" in
  mikrotik)
    # 1. Export on device
    ssh admin@192.168.88.1 "/export file=backup-$TIMESTAMP"

    # 2. Transfer to deploy machine
    scp admin@192.168.88.1:/backup-$TIMESTAMP.rsc "$BACKUP_DIR/"

    # 3. Encrypt with SOPS/age
    sops --encrypt --age $(cat ~/.age/recipient.txt) \
      "$BACKUP_DIR/backup-$TIMESTAMP.rsc" > "$BACKUP_DIR/backup-$TIMESTAMP.rsc.enc"

    # 4. Delete plaintext
    rm "$BACKUP_DIR/backup-$TIMESTAMP.rsc"
    ssh admin@192.168.88.1 "/file/remove backup-$TIMESTAMP.rsc"
    ;;

  proxmox)
    # 1. Create vzdump on Proxmox
    ssh root@proxmox "vzdump $VMID --storage local --compress zstd"

    # 2. Transfer
    scp root@proxmox:/var/lib/vz/dump/vzdump-*-$TIMESTAMP.* "$BACKUP_DIR/"

    # 3. Encrypt
    for f in "$BACKUP_DIR"/vzdump-*-$TIMESTAMP.*; do
      sops --encrypt --age $(cat ~/.age/recipient.txt) "$f" > "$f.enc"
      rm "$f"
    done

    # 4. Cleanup on Proxmox (optional, per retention policy)
    ;;
esac

echo "Encrypted backup stored: $BACKUP_DIR"
```

**Storage structure:**
```
.work/backups/           # gitignored
├── mikrotik/
│   └── backup-20260610-120000.rsc.enc    # SOPS encrypted
├── proxmox/
│   └── vzdump-100-20260610.tar.zst.enc   # SOPS encrypted
└── .sops.yaml                             # SOPS config (age recipient)
```

**Decryption (for restore):**
```bash
sops --decrypt backup.rsc.enc > backup.rsc
```

### D6. Git as Rollback Source

Terraform configuration lives in Git. Rollback = revert + re-apply:

```bash
# 1. Find last good commit
git log --oneline generated/home-lab/terraform/mikrotik/

# 2. Revert
git revert <bad_commit>

# 3. Plan and apply
terraform plan
terraform apply
```

### D7. Audit Trail with Rollback Points

**ADR 0085 Alignment:** Deploy state lives in `.work/deploy-state/<project>/` per ADR 0085 D6.

Track applies in simple YAML (metadata only, no secrets):

```yaml
# .work/deploy-state/home-lab/history.yaml (aligned with ADR 0085)
applies:
  # Latest apply - NOT YET CONFIRMED (not a rollback point)
  - timestamp: "2026-06-10T14:00:00Z"
    device: "rtr-mikrotik-chateau"
    git_commit: "abc12345..."
    git_commit_short: "abc12345"
    bundle_id: "b-xyz789"
    status: "success"
    rollback_point: false   # <-- NOT confirmed yet, cannot rollback to this

  # Previous apply - CONFIRMED by operator (valid rollback point)
  - timestamp: "2026-06-10T12:00:00Z"
    device: "rtr-mikrotik-chateau"
    git_commit: "8f85cfe4a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    git_commit_short: "8f85cfe4"
    bundle_id: "b-202d573bd9d0"
    status: "success"
    rollback_point: true    # <-- CONFIRMED by operator
    confirmed_by: "operator"
    confirmed_at: "2026-06-10T12:05:00Z"

  # Even older - also confirmed
  - timestamp: "2026-06-10T10:00:00Z"
    device: "hv-proxmox-xps"
    git_commit: "fb0e465c..."
    git_commit_short: "fb0e465c"
    status: "success"
    rollback_point: true
    confirmed_by: "operator"
    confirmed_at: "2026-06-10T10:15:00Z"
```

**Rollback Point Definition:**

A **rollback point** is a topology snapshot (git commit SHA) where:
1. Generated artifacts were successfully applied (`status: success`)
2. Health checks passed OR operator acknowledged success
3. `rollback_point: true` is set in history.yaml

**Mental Model:**

```
topology.yaml (git SHA) ──► compile ──► generate ──► apply ──► verify
                                                         │
                                                         ▼
                                              rollback_point: true
                                              (last known good state)
```

**Key principle:** Topology state is idempotent. Re-apply same snapshot = no change. Reset device + apply snapshot = same result. Rollback = checkout previous rollback_point + compile + apply.

**Operator Confirmation Command (MANDATORY):**

Deployment is NOT a rollback point until operator explicitly confirms:

```bash
# After successful apply and manual verification, operator confirms:
task deploy:confirm -- DEVICE=mikrotik

# This command:
# 1. Queries device for current snapshot (D10 verification)
# 2. Compares with last applied git SHA
# 3. If match: sets rollback_point: true in history.yaml
# 4. If mismatch: warns and exits without confirmation
```

**Confirmation script:**

```bash
#!/bin/bash
# scripts/deploy-confirm.sh

DEVICE=$1
EXPECTED_SHA=$(git rev-parse HEAD)

# 1. Verify device has expected snapshot
./scripts/confirm-deployment.sh "$EXPECTED_SHA" "$DEVICE"
if [ $? -ne 0 ]; then
  echo "ERROR: Device snapshot mismatch. Cannot confirm."
  exit 1
fi

# 2. Update history.yaml with rollback_point: true
yq -i "(.applies[] | select(.device == \"$DEVICE\" and .git_commit == \"$EXPECTED_SHA\")) .rollback_point = true" \
  .work/deploy-state/home-lab/history.yaml

yq -i "(.applies[] | select(.device == \"$DEVICE\" and .git_commit == \"$EXPECTED_SHA\")) .confirmed_by = \"operator\"" \
  .work/deploy-state/home-lab/history.yaml

yq -i "(.applies[] | select(.device == \"$DEVICE\" and .git_commit == \"$EXPECTED_SHA\")) .confirmed_at = \"$(date -Iseconds)\"" \
  .work/deploy-state/home-lab/history.yaml

echo "CONFIRMED: $DEVICE @ ${EXPECTED_SHA:0:8} is now a rollback point"
```

**Workflow:**

```
1. task compile                          # Generate from topology
2. task deploy:backup DEVICE=mikrotik    # Encrypted backup (D5)
3. task deploy:apply DEVICE=mikrotik     # Apply with safe-mode (D3)
4. <operator verifies functionality>     # Manual testing
5. task deploy:confirm DEVICE=mikrotik   # ← MANDATORY confirmation
                                         # Only NOW it's a rollback point
```

**Without confirmation:** Apply is recorded in history.yaml with `rollback_point: false`. It is NOT a valid rollback target.

**Find last confirmed rollback point:**

```bash
# Query history.yaml for confirmed rollback points only
yq '.applies[] | select(.rollback_point == true) | .git_commit_short' \
  .work/deploy-state/home-lab/history.yaml | head -1
```

**Rollback to last confirmed point:**

```bash
# Get last rollback point
ROLLBACK_SHA=$(yq '.applies[] | select(.rollback_point == true) | .git_commit' \
  .work/deploy-state/home-lab/history.yaml | head -1)

# Checkout, compile, apply
git checkout $ROLLBACK_SHA
task compile
task deploy:apply DEVICE=mikrotik
```

### D8. Snapshot Propagation per Device Type

Each device class stores topology snapshot ID using its native metadata mechanism:

| Device Class | Mechanism | Resource/Field |
|--------------|-----------|----------------|
| **MikroTik** | Script as metadata store | `routeros_system_script.topology_metadata` |
| **Proxmox VM/LXC** | Tags | `tags = ["snapshot-XXXXXXXX"]` |
| **Oracle OCI** | Freeform tags | `freeform_tags.topology-snapshot` |

All mechanisms are:
- Native to each platform (no custom systems, satisfies C19)
- Queryable via platform API
- Managed by Terraform
- Visible in platform UI

**MikroTik example:**
```hcl
resource "routeros_system_script" "topology_metadata" {
  name   = "topology-metadata"
  source = <<-EOT
    # Topology Snapshot Metadata
    # snapshot_sha:     ${var.topology_snapshot_sha}
    # deploy_timestamp: ${timestamp()}
  EOT
  comment = "Topology snapshot metadata - managed by topology"
}
```

**Proxmox example:**
```hcl
resource "proxmox_virtual_environment_vm" "example" {
  tags = ["topology", "snapshot-${substr(var.topology_snapshot_sha, 0, 8)}"]
}
```

**Oracle OCI example:**
```hcl
resource "oci_core_instance" "example" {
  freeform_tags = {
    "topology-snapshot" = var.topology_snapshot_sha
  }
}
```

### D9. Unified Snapshot Variable Contract

All generated Terraform configurations must accept:

```hcl
variable "topology_snapshot_sha" {
  description = "Git commit SHA of topology used to generate this configuration"
  type        = string

  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.topology_snapshot_sha))
    error_message = "Must be a valid 40-character git SHA"
  }
}
```

Generators embed this variable in platform-appropriate metadata resources.
Deploy scripts inject the current git SHA at apply time:

```bash
terraform apply -var="topology_snapshot_sha=$(git rev-parse HEAD)"
```

### D10. Snapshot Verification Workflow

Pre-deploy and post-deploy scripts query each device API to:

1. **Pre-deploy check**: Report current snapshot per device, compare against deploying snapshot
2. **Post-deploy confirm**: Verify device metadata matches expected snapshot

Scripts use only native platform APIs:
- MikroTik: REST API query to `/rest/system/script`
- Proxmox: API query to `/api2/json/nodes/{node}/qemu`
- OCI: `oci compute instance list` with tag filter

See `adr/0105-analysis/SNAPSHOT-PROPAGATION-DESIGN.md` for detailed implementation.

### D11. Multi-Device Consistency Groups (C3 Resolution)

When multiple devices are changed in the same deploy operation, they form a **consistency group**. This addresses the scenario where rollback of one device requires rollback of related devices.

**Consistency group tracking:**

```yaml
# .work/deploy-state/home-lab/history.yaml
applies:
  - timestamp: "2026-06-10T14:00:00Z"
    consistency_group: "cg-20260610-140000"  # Group ID for multi-device deploys
    devices:
      - device: "rtr-mikrotik-chateau"
        git_commit: "abc12345..."
        status: "success"
      - device: "hv-proxmox-xps"
        git_commit: "abc12345..."
        status: "success"
    rollback_point: true
    confirmed_at: "2026-06-10T14:05:00Z"
```

**Rollback behavior:**

1. **Single device rollback**: Operator acknowledges dependency warning if device is part of a consistency group
2. **Group rollback**: `task deploy:rollback -- GROUP=cg-20260610-140000` rolls back all devices in group
3. **Partial rollback**: Explicitly allowed with `--partial` flag, operator accepts inconsistency risk

**Consistency group creation:**

```bash
# Multi-device apply creates consistency group
task deploy:apply -- DEVICES="mikrotik,proxmox"

# Or explicit group
task deploy:apply -- GROUP=network-refresh DEVICES="mikrotik,proxmox"
```

**Warning on inconsistent rollback:**

```
WARNING: Device rtr-mikrotik-chateau is part of consistency group cg-20260610-140000
  Other devices in group: hv-proxmox-xps

  Rolling back only rtr-mikrotik-chateau may cause:
  - Network connectivity issues between devices
  - Configuration drift between related devices

  Options:
  1. Use --group to rollback entire consistency group
  2. Use --force to rollback single device (accept risk)
```

### D12. Partial Apply Failure Recovery (C2 Resolution)

Terraform apply can fail mid-operation, leaving state partially applied. This decision documents the recovery procedure.

**Failure modes:**

| Failure Point | State | Recovery |
|---------------|-------|----------|
| Before any resource | Clean | Fix issue, re-apply |
| Mid-apply, some resources | Partial | See recovery procedure |
| After all resources, hook failed | Applied but unhealthy | Run health checks, decide |
| Network lost during apply | Depends on safe-mode | MikroTik auto-reverts; others manual |

**Recovery procedure for partial Terraform failure:**

```bash
# 1. Check current state
terraform state list
terraform show

# 2. Option A: Complete the apply (if fixable)
#    - Fix the issue causing failure
#    - Re-run terraform apply

# 3. Option B: Rollback to previous state
#    - If remote backend: terraform state pull (get version history)
#    - GitLab: Use state version UI to restore
#    - S3: Use bucket versioning to restore

# 4. Option C: Manual cleanup
#    - terraform state rm <resource> to remove failed resources
#    - terraform import <resource> to re-import if needed
#    - terraform apply to reconcile
```

**MikroTik-specific recovery (safe-mode active):**

```bash
# If connection maintained:
#   - Exit safe-mode WITHOUT save: changes discarded
#   - curl -k -X POST "https://192.168.88.1/rest/system/safe-mode" -d '{"action":"undo"}'

# If connection lost:
#   - Wait 9 minutes for auto-revert
#   - Reconnect and verify state

# Post-recovery:
terraform refresh  # Sync state with device
terraform plan     # Verify no drift
```

**History entry for failed apply:**

```yaml
applies:
  - timestamp: "2026-06-10T15:00:00Z"
    device: "rtr-mikrotik-chateau"
    git_commit: "def67890..."
    status: "failed"           # Not "success"
    failure_reason: "API timeout at routeros_interface_vlan.servers"
    partial_resources_applied: 3
    partial_resources_failed: 1
    recovery_action: "safe_mode_revert"
    rollback_point: false      # Never a rollback point
```

**Critical rule:** Failed applies are NEVER rollback points, regardless of how many resources succeeded.

---

## Implementation

### Phase 1: Foundation (D1-D5)

| Task | Deliverable |
|------|-------------|
| Configure remote backend | `backend.tf` per device |
| Create encrypted backup script | `scripts/backup-before-apply.sh` (with SOPS/age) |
| Create safe-apply script | `scripts/mikrotik-safe-apply.sh` |
| Setup age recipient | `~/.age/recipient.txt`, `.work/backups/.sops.yaml` |

### Phase 2: Automation (D6-D7)

| Task | Deliverable |
|------|-------------|
| Taskfile integration | `task deploy:apply DEVICE=mikrotik` |
| Health check script | `scripts/health-check.sh` |
| Apply history logging | `.work/deploy-state/home-lab/history.yaml` |
| **Operator confirmation script** | `scripts/deploy-confirm.sh` |
| **Confirmation task** | `task deploy:confirm DEVICE=mikrotik` |
| Rollback point query | `task deploy:rollback-point` |
| Rollback task | `task deploy:rollback DEVICE=mikrotik` |

### Phase 3: Snapshot Propagation (D8-D10)

| Task | Deliverable |
|------|-------------|
| Add `topology_snapshot_sha` variable | All `variables.tf.j2` templates |
| Create MikroTik metadata template | `topology_metadata.tf.j2` |
| Add tags to Proxmox VM/LXC | Update `vms.tf.j2`, `lxc.tf.j2` |
| Add freeform_tags to OCI | Update `instance.tf.j2` |
| Update generator render contexts | Pass `topology_snapshot_sha` |
| Create verification script | `scripts/verify-snapshot-consistency.sh` |
| Create confirmation script | `scripts/confirm-deployment.sh` |
| Update safe-apply to pass snapshot | `scripts/mikrotik-safe-apply.sh` |

### Phase 4: Multi-Device and Recovery (D11-D12)

| Task | Deliverable |
|------|-------------|
| Consistency group schema | Update `history.yaml` schema |
| Multi-device apply command | `task deploy:apply -- DEVICES=...` |
| Group rollback command | `task deploy:rollback -- GROUP=...` |
| Partial failure detection | Update apply script with failure tracking |
| Recovery runbook | `docs/guides/DEPLOY-RECOVERY.md` |

---

## Consequences

### Positive

1. **No custom systems** — uses proven Terraform/Ansible/RouterOS patterns (C19)
2. **Per-tool expertise** — follows each tool's best practices
3. **Simple implementation** — bash scripts + existing tools
4. **MikroTik safe-mode** — automatic hardware-level rollback
5. **Unified snapshot ID** — git SHA propagated to all devices via native metadata (D8)
6. **Verifiable deployments** — can query any device for its topology lineage (D10)
7. **Explicit rollback points** — `rollback_point: true` marks confirmed working states (D7)
8. **Secure backups** — SOPS/age encryption, transferred to deploy machine (D5)
9. **Idempotent reproducibility** — topology snapshot = reproducible device state

### Negative

1. **Manual coordination** — no single orchestrator
2. **Tool-specific knowledge required** — operators must know each tool
3. **Per-device verification** — must query each device API (no central registry)

### Trade-offs Accepted

- Git commit SHA used as unified snapshot ID (propagated to all devices via D8)
- Consistency groups provide coordination hints, not automatic cross-device rollback (D11)
- No snapshot service — use tool-native mechanisms (export, vzdump)
- Snapshot verification requires querying each device API (no central registry)
- Partial apply recovery requires operator judgment (D12)

### Mental Model Alignment

This ADR implements the project's Infrastructure-as-Data philosophy:

```
Topology Snapshot (git SHA) ──► Deterministic Generation ──► Idempotent Apply
         │                              │                           │
         │                              │                           ▼
         │                              │                   Device knows its
         │                              │                   snapshot (D8)
         │                              │
         └───────────── Rollback Point (D7) ◄─── Acknowledged Success
```

**Key principle:** Topology state is the source of truth. Each device carries its lineage (snapshot SHA). Rollback = checkout previous rollback point + compile + apply.

---

## References

- [Terraform State Rollback Guide](https://spacelift.io/blog/terraform-state-rollback)
- [MikroTik Safe Mode](https://help.mikrotik.com/docs/spaces/ROS/pages/328155/Configuration+Management)
- [Ansible Block/Rescue/Always](https://www.ansiblepilot.com/articles/ansible-block-rescue-always-error-handling-complete-guide/)
- [bpg/proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Terraform RouterOS Provider](https://registry.terraform.io/providers/terraform-routeros/routeros/latest/docs)
- [OCI Tagging Best Practices](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/terraformbestpractices_topic-Tagging_Resources.htm)
- `adr/0105-analysis/SIMPLIFIED-BEST-PRACTICES.md` — detailed patterns
- `adr/0105-analysis/SNAPSHOT-PROPAGATION-DESIGN.md` — D8/D9/D10 implementation details
- `adr/0105-analysis/SWOT-ANALYSIS-SIMPLIFIED.md` — current SWOT analysis
- `adr/0105-analysis/SWOT-ANALYSIS.md` — original analysis (archived)
- `adr/0105-analysis/TECH-LEAD-REVIEW.md` — tech-lead-architect critique and recommendations
