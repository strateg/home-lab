# State Storage Architecture Proposal

**ADR Reference:** 0105 (Extension)
**Date:** 2026-06-10

---

## Problem

Git имеет commit SHA для идентификации состояния кода. Нам нужен аналог для состояния устройств:

1. **Идентификация** — как ссылаться на конкретное состояние?
2. **Хранение** — где хранить state/snapshots?
3. **Версионирование** — как отслеживать историю?
4. **Связь с Git** — как связать topology commit с device state?

---

## Proposed Solution: Dual-Layer State Model

### Layer 1: Git-Tracked Metadata (Lightweight)

```
projects/home-lab/
└── state/
    ├── current.yaml          # Pointer to current committed state
    ├── history.yaml          # Commit history log
    └── commits/
        └── <commit_id>.yaml  # Commit metadata (no secrets)
```

**В Git:** Только metadata — commit IDs, timestamps, статусы, checksums.

### Layer 2: Local/Remote State Storage (Heavy)

```
.work/deploy-state/<project>/
├── snapshots/
│   └── <snapshot_id>/
│       ├── manifest.yaml
│       ├── rtr-mikrotik-chateau/
│       │   ├── terraform.tfstate
│       │   └── backup.rsc
│       └── hv-proxmox-xps/
│           └── terraform.tfstate
└── tfstate/
    └── <device_id>/
        └── terraform.tfstate  # Current working state
```

**Не в Git:** Terraform state files, RouterOS backups, Proxmox snapshots.

---

## State Commit ID Scheme

```
Format: sc-<timestamp>-<topology_sha>-<seq>

Example: sc-20260610T1200-8f85cfe4-001

Components:
- sc          : State Commit prefix
- timestamp   : ISO8601 compact (YYYYMMDDTHHmm)
- topology_sha: First 8 chars of git commit
- seq         : Sequence number for same timestamp
```

**Преимущества:**
- Сортируемый по времени
- Связан с git commit
- Человекочитаемый
- Уникальный

---

## Storage Schema

### projects/home-lab/state/current.yaml

```yaml
# Current committed state pointer
# This file is git-tracked
schema_version: "1.0"

current_commit: "sc-20260610T1200-8f85cfe4-001"
last_updated: "2026-06-10T12:05:00Z"

devices:
  rtr-mikrotik-chateau:
    state_commit: "sc-20260610T1200-8f85cfe4-001"
    status: "committed"
    last_apply: "2026-06-10T12:05:00Z"

  hv-proxmox-xps:
    state_commit: "sc-20260610T1000-fb0e465c-001"
    status: "committed"
    last_apply: "2026-06-10T10:15:00Z"
```

### projects/home-lab/state/commits/sc-20260610T1200-8f85cfe4-001.yaml

```yaml
# State commit metadata (git-tracked)
schema_version: "1.0"

commit_id: "sc-20260610T1200-8f85cfe4-001"
created_at: "2026-06-10T12:00:00Z"
committed_at: "2026-06-10T12:05:00Z"
status: "committed"

# Link to Git
topology:
  git_commit: "8f85cfe4"
  git_branch: "main"
  bundle_id: "b-202d573bd9d0"

# What was changed
changes:
  - device_id: "rtr-mikrotik-chateau"
    type: "terraform"
    resources_added: 2
    resources_changed: 1
    resources_deleted: 0

# Snapshot reference (actual files in .work/)
snapshot:
  id: "s-abc123def456"
  checksum: "sha256:..."

# Rollback info
rollback:
  parent_commit: "sc-20260610T1000-fb0e465c-001"
  reversible: true
  warnings: []

# Validation results
validation:
  pre_apply:
    passed: true
    checks: ["terraform_validate", "connectivity"]
  post_apply:
    passed: true
    checks: ["api_reachable", "health_check"]
```

### projects/home-lab/state/history.yaml

```yaml
# State commit history (git-tracked)
schema_version: "1.0"

# Latest first
commits:
  - id: "sc-20260610T1200-8f85cfe4-001"
    topology_commit: "8f85cfe4"
    status: "committed"
    devices: ["rtr-mikrotik-chateau"]

  - id: "sc-20260610T1000-fb0e465c-001"
    topology_commit: "fb0e465c"
    status: "committed"
    devices: ["hv-proxmox-xps"]

  - id: "sc-20260609T1500-808f0e58-001"
    topology_commit: "808f0e58"
    status: "rolled_back"
    devices: ["rtr-mikrotik-chateau"]
    rollback_reason: "health_check_failed"
```

---

## CLI Commands

```bash
# Показать текущее состояние всех устройств
task state:status
# Output:
# Device                  State Commit                    Status      Last Apply
# rtr-mikrotik-chateau    sc-20260610T1200-8f85cfe4-001  committed   2h ago
# hv-proxmox-xps          sc-20260610T1000-fb0e465c-001  committed   4h ago

# Показать историю коммитов
task state:log
# Output:
# sc-20260610T1200-8f85cfe4-001  committed    rtr-mikrotik-chateau
# sc-20260610T1000-fb0e465c-001  committed    hv-proxmox-xps
# sc-20260609T1500-808f0e58-001  rolled_back  rtr-mikrotik-chateau

# Показать детали коммита
task state:show -- COMMIT=sc-20260610T1200-8f85cfe4-001

# Сравнить два состояния
task state:diff -- FROM=sc-20260609 TO=sc-20260610

# Откатить на предыдущий коммит
task state:rollback -- COMMIT=sc-20260610T1000-fb0e465c-001
```

---

## Git Workflow Integration

```bash
# 1. Изменяем topology
vim projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml

# 2. Компилируем
task compile

# 3. Git commit topology changes
git add topology/ projects/home-lab/topology/
git commit -m "feat(mikrotik): add VLAN 55 for VPN Germany"
# → git commit: 8f85cfe4

# 4. Создаём state commit (apply)
task state:commit -- DEVICE=rtr-mikrotik-chateau
# → state commit: sc-20260610T1200-8f85cfe4-001

# 5. Git commit state metadata
git add projects/home-lab/state/
git commit -m "state: apply mikrotik VLAN 55 config"

# 6. Push both
git push
```

---

## Remote State Storage (Optional)

Для синхронизации между машинами:

```yaml
# projects/home-lab/state/remote.yaml
remote:
  type: "s3"  # or "oci", "local"
  bucket: "homelab-state"
  prefix: "state/"
  encryption: "sops"

  # Credentials via SOPS
  credentials_ref: "secrets.state.remote"
```

Terraform state может храниться в remote backend (S3, OCI Object Storage), snapshots синхронизируются отдельно.

---

## Comparison with Git

| Aspect | Git | State Commits |
|--------|-----|---------------|
| ID | SHA-1 (40 chars) | sc-<timestamp>-<sha>-<seq> |
| Content | Source code | Device config snapshots |
| Storage | .git/ | .work/ + state/ metadata |
| History | git log | state:log |
| Diff | git diff | state:diff (terraform plan) |
| Rollback | git revert | state:rollback |
| Branch | git branch | N/A (linear history per device) |

---

## Security Considerations

1. **Terraform state** содержит secrets → не в git, encrypt at rest
2. **RouterOS backup.rsc** может содержать passwords → SOPS encrypt
3. **Commit metadata** (state/*.yaml) → можно в git, без secrets
4. **Snapshot manifest** — только checksums, без содержимого

---

## Implementation Priority

| Component | Priority | Effort |
|-----------|----------|--------|
| State directory structure | P1 | 1 day |
| Commit ID generation | P1 | 0.5 day |
| current.yaml management | P1 | 1 day |
| history.yaml management | P1 | 1 day |
| state:status command | P1 | 1 day |
| state:log command | P2 | 0.5 day |
| state:diff command | P3 | 2 days |
| Remote storage sync | P3 | 3 days |
