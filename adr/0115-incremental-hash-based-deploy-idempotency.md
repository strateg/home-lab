# ADR 0115: Incremental Hash-Based Deploy Idempotency Contract

- Status: Proposed
- Date: 2026-08-02
- Extends: ADR 0105 (Device State Management)
- Related: ADR 0080, ADR 0085, ADR 0104
- Prerequisite: ADR 0105 must transition from Deferred to Proposed

## Context

### Problem Statement

ADR 0105 establishes device state management using git commit SHA as a whole-snapshot identifier. While this provides rollback capability, it lacks:

1. **Granular drift detection** — cannot identify which specific configuration changed
2. **Incremental idempotency** — cannot verify individual feature application
3. **Selective re-apply** — must reapply entire configuration on any drift

### Current State

| Tool | Idempotency | Drift Detection | State Tracking |
|------|-------------|-----------------|----------------|
| Terraform | Native (plan→apply) | Native (`terraform plan`) | State file |
| Ansible | Task-level (when correct) | None | None |

Ansible-driven configuration lacks a verification mechanism to ensure idempotency at the feature level.

### User Requirement

The system requires hash-based idempotency where:

- Each configuration feature has its own hash
- Hash is stored on the device after successful deploy
- Pipeline compares local vs device hash before deploy
- Manual device changes are forbidden (pipeline-only)

### Relationship to ADR 0105

This ADR **extends** ADR 0105 by adding a per-feature hash layer on top of the existing snapshot model:

| ADR 0105 | This ADR |
|----------|----------|
| Snapshot (git SHA) | Snapshot + Feature hashes |
| Whole-device rollback | Snapshot rollback (feature rollback deferred) |
| Snapshot drift detection | Feature-level drift detection |

ADR 0105 blockers (C1-C3) must be resolved as prerequisites.

### Industry Comparison

This ADR adapts proven industry patterns for hash-based idempotency to heterogeneous infrastructure.

#### Comparison with Industry Solutions

| Solution | Approach | Hash-based | Drift Detection | ADR 0115 Alignment |
|----------|----------|------------|-----------------|-------------------|
| **NixOS** | Declarative + Immutable | ✅ Per-package hash paths | Built-in (hash mismatch) | Closest analog — adapted for multi-platform |
| **Terraform** | Declarative + State file | State checksum | `terraform plan` | Complements — fills Ansible gap |
| **Pulumi** | IaC + Cloud state | State diff | `pulumi refresh` + scheduled | Similar goals — self-hosted alternative |
| **Ansible** | Idempotent playbooks | ❌ None | Check mode only | **Gap this ADR fills** |
| **GitOps** | Git as source of truth | Git SHA | Continuous reconciliation | Applies GitOps to non-K8s infra |
| **mgmt** | Reactive graph-based | Graph-based | Real-time | More revolutionary; ADR 0115 is evolutionary |

#### Key Industry Insights Applied

| Best Practice | Industry Source | ADR 0115 Implementation |
|---------------|-----------------|------------------------|
| *"Hashing configs (SHA256) for quick pre-checks"* | Ansible community | D1: SHA256 truncated to 16 chars |
| *"State files should be isolated to reduce blast radius"* | Terraform best practices | D2: Per-device feature registry |
| *"Each package in unique hashed path"* | NixOS philosophy | D3: Per-feature hash on device |
| *"Scheduled drift detection catches changes within 6 hours"* | Pulumi/Spacelift | Deferred to Phase 5 |
| *"Use config-driven state changes"* | Terraform guidance | D4: Topology-driven hash computation |

#### Unique Differentiators

1. **Multi-platform device storage** — No competitor supports MikroTik/Proxmox native metadata storage
2. **Per-feature granularity** — More granular than Terraform (per-resource) or GitOps (whole-repo SHA)
3. **Pipeline-native** — Built into existing 6-stage pipeline, no external orchestration needed
4. **Network device first-class** — Unlike cloud-focused tools, supports edge devices (MikroTik RouterOS)

#### Trade-offs Accepted

| Industry Feature | Status | Rationale |
|------------------|--------|-----------|
| Continuous reconciliation | Deferred | Batch deploy sufficient for home-lab scale |
| Auto-remediation | Deferred | Requires explicit operator control |
| Visual dashboard | Out of scope | CLI-first approach matches project philosophy |
| Feature-level rollback | Phase 5 | Snapshot rollback covers critical recovery |

---

## Decision

### D1. Feature Hash Model

Configuration is decomposed into **features** — discrete units of configuration that can be independently hashed and tracked.

**Feature Definition:**

| Feature Type | Hash Input | Example |
|--------------|------------|---------|
| Capability config | Generated host_vars for capability | `cap.network.vpn_gateway` |
| Role variables | Ansible role defaults + vars | `wireguard_gateway` |
| Service definition | Service instance YAML | `svc-wireguard` |

**Hash Computation:**

```python
import hashlib
import json

def compute_feature_hash(feature_config: dict) -> str:
    """Compute deterministic SHA256 hash of feature configuration."""
    canonical = json.dumps(feature_config, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

Hash is truncated to 16 hex characters (64 bits) for storage efficiency while maintaining collision resistance.

### D2. Feature Registry Schema

Each device maintains a feature registry in deploy state:

```yaml
# .work/deploy-state/home-lab/features/<device-id>.yaml
device_id: rtr-mikrotik-chateau
snapshot_sha: abc12345...
snapshot_short: abc12345
updated_at: "2026-08-02T14:00:00Z"
features:
  - feature_id: cap.network.vpn_gateway
    hash: a1b2c3d4e5f6g7h8
    applied_at: "2026-08-02T14:00:00Z"
    source: generated/home-lab/ansible/inventory/production/host_vars/...
  - feature_id: role.wireguard_gateway
    hash: b2c3d4e5f6g7h8i9
    applied_at: "2026-08-02T14:00:00Z"
    source: projects/home-lab/ansible/roles/wireguard_gateway/defaults/main.yml
```

This registry is the local source of truth for expected device state.

### D3. Device Hash Storage

Feature hashes are stored on devices using platform-native mechanisms:

| Platform | Storage Mechanism | Format | Size Limit |
|----------|-------------------|--------|------------|
| MikroTik RouterOS | `/system/script` named `topology-features` | JSON in script source | ~64KB |
| Proxmox VE | VM/LXC description field | JSON blob | 8KB |
| Oracle OCI | `freeform_tags.topology-features` | JSON string | 256 chars |
| Linux VM/LXC | `/etc/topology/features.json` | JSON file | Unlimited |

**MikroTik Example:**

```routeros
/system script
add name=topology-features comment="TOPOLOGY MANAGED" source="{\"snapshot\":\"abc12345\",\"features\":{\"cap.network.vpn_gateway\":\"a1b2c3d4\",\"role.wireguard_gateway\":\"b2c3d4e5\"}}"
```

**Terraform Resource (MikroTik):**

```hcl
resource "routeros_system_script" "topology_features" {
  name    = "topology-features"
  comment = "TOPOLOGY MANAGED - DO NOT EDIT"
  source  = jsonencode({
    snapshot = var.topology_snapshot_sha
    features = var.feature_hashes
  })
}
```

### D4. Pipeline Integration

Hash computation occurs in the **assemble** stage, `verify` phase:

```yaml
# Plugin manifest entry
- id: base.assembler.feature_hash
  family: assemblers
  stage: assemble
  phase: verify
  order: 450
  execution_mode: subinterpreter
  depends_on:
    - base.assembler.ansible_runtime
  consumes:
    - from_plugin: base.generator.ansible_role
      keys: [ansible_role_host_vars]
  publishes:
    - feature_hash_registry
```

**Pipeline Flow:**

```
compile → generate → assemble
                        │
                        ├── assemble.run: bundle creation
                        └── assemble.verify: feature hash computation ◄── NEW
```

### D5. Pre-Deploy Hash Comparison

Before deploy, pipeline queries device and compares hashes:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Local     │     │   Compare    │     │   Device    │
│   Registry  │────▶│   Hashes     │◀────│   Query     │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
       [MATCH]        [MISMATCH]      [MISSING]
       Skip apply     Apply feature   Apply feature
```

**Comparison Result Actions:**

| Result | Action | Log Level |
|--------|--------|-----------|
| All MATCH | Skip deploy (idempotent) | INFO: "Device up-to-date, nothing to apply" |
| Some MISMATCH | Apply changed features | WARN: "N features changed, applying" |
| MISSING on device | Apply all features | INFO: "First deploy, applying all features" |
| Extra on device | DRIFT WARNING | ERROR: "Unknown features on device, investigation required" |

### D6. Deploy Workflow

**Standard Workflow:**

```bash
# 1. Check current state (non-destructive)
task deploy:check DEVICE=mikrotik

# 2. Apply changes (only changed features)
task deploy:apply DEVICE=mikrotik

# 3. Confirm as rollback point (ADR 0105 D7)
task deploy:confirm DEVICE=mikrotik
```

**Selective Apply:**

```bash
# Apply specific feature only
task deploy:apply DEVICE=mikrotik FEATURE=cap.network.vpn_gateway

# Apply multiple features
task deploy:apply DEVICE=mikrotik FEATURES="cap.network.vpn_gateway,role.wireguard_gateway"
```

**Force Full Apply:**

```bash
# Skip hash comparison, apply everything
task deploy:apply DEVICE=mikrotik FORCE=true
```

### D7. Drift Detection

Drift is detected when device hash ≠ expected hash:

| Drift Type | Cause | Detection | Resolution |
|------------|-------|-----------|------------|
| **Config Drift** | Manual change on device | Hash mismatch | Re-apply from pipeline |
| **Version Drift** | Topology updated, device stale | Hash mismatch | Normal deploy |
| **Unknown Feature** | Feature on device not in registry | Extra hash | Investigation required |
| **Missing Feature** | Feature in registry not on device | Missing hash | Re-apply feature |

**Drift Report Format:**

```yaml
# .work/deploy-state/home-lab/drift/<device-id>-<timestamp>.yaml
device_id: rtr-mikrotik-chateau
checked_at: "2026-08-02T15:00:00Z"
snapshot_expected: abc12345
snapshot_device: abc12345
status: DRIFT_DETECTED
summary:
  total_features: 5
  matched: 3
  mismatched: 1
  missing: 1
features:
  - feature_id: cap.network.vpn_gateway
    expected: a1b2c3d4
    device: a1b2c3d4
    status: match
  - feature_id: role.wireguard_gateway
    expected: b2c3d4e5
    device: x9y8z7w6
    status: DRIFT
    action_required: re-apply
  - feature_id: role.firewall_zones
    expected: c3d4e5f6
    device: null
    status: MISSING
    action_required: apply
```

**Drift Check Command:**

```bash
# Check single device
task deploy:check-drift DEVICE=mikrotik

# Check all devices
task deploy:check-drift-all

# Output: .work/deploy-state/home-lab/drift/
```

### D8. Rollback Model

**Phase 1 (MVP):** Snapshot-level rollback only (per ADR 0105 D7)

```bash
# Rollback to last confirmed snapshot
task deploy:rollback DEVICE=mikrotik

# Internally executes:
# 1. Find last rollback_point in history.yaml
# 2. git checkout <rollback_sha>
# 3. task compile
# 4. task deploy:apply DEVICE=mikrotik FORCE=true
```

**Phase 2 (Deferred):** Feature-level rollback

```bash
# Rollback specific feature to previous version
task deploy:rollback DEVICE=mikrotik FEATURE=cap.network.vpn_gateway

# Requires: feature version history (not in MVP)
```

**Rationale for deferral:** Feature-level rollback requires maintaining version history per feature, significantly increasing storage and complexity. Snapshot rollback covers the critical recovery use case.

### D9. Constraint: No Manual Changes

This contract assumes **pipeline-only configuration**:

1. All device configuration flows through topology → generate → deploy
2. Manual changes invalidate idempotency guarantee
3. Drift detection will flag manual changes as errors
4. Operators must re-apply from pipeline to restore consistency

**Enforcement via Deploy Profile:**

```yaml
# projects/home-lab/deploy/deploy-profile.yaml
deploy_policy:
  manual_changes: forbidden  # warn | forbidden | ignore
  drift_action: block        # block | warn | auto-fix
  require_confirmation: true # Require task deploy:confirm
```

**Policy Behavior:**

| Setting | manual_changes | drift_action | Behavior |
|---------|----------------|--------------|----------|
| Strict | forbidden | block | Fail deploy if drift detected |
| Warning | warn | warn | Log warning, proceed with deploy |
| Permissive | ignore | auto-fix | Silently overwrite device state |

---

## Implementation

### Phase 1: Foundation (18h)

| Task | Component | Effort | Deliverable |
|------|-----------|--------|-------------|
| 1.1 | Feature hash schema | 4h | `schemas/feature-hash.schema.json` |
| 1.2 | Hash computation utility | 4h | `topology-tools/utils/feature_hash.py` |
| 1.3 | Feature registry format | 2h | `.work/deploy-state/` structure |
| 1.4 | Hash assembler plugin | 8h | `plugins/assemblers/feature_hash_assembler.py` |

### Phase 2: Device Adapters (22h)

| Task | Platform | Effort | Deliverable |
|------|----------|--------|-------------|
| 2.1 | MikroTik hash writer | 4h | Terraform `routeros_system_script` |
| 2.2 | MikroTik hash reader | 4h | REST API query in `scripts/deploy/` |
| 2.3 | Proxmox hash writer | 3h | Terraform description field |
| 2.4 | Proxmox hash reader | 3h | Proxmox API query |
| 2.5 | OCI hash writer | 2h | Terraform freeform_tags |
| 2.6 | OCI hash reader | 2h | OCI CLI query wrapper |
| 2.7 | Linux hash writer | 2h | Ansible task for `/etc/topology/` |
| 2.8 | Linux hash reader | 2h | SSH file read |

### Phase 3: Pipeline Integration (18h)

| Task | Component | Effort | Deliverable |
|------|-----------|--------|-------------|
| 3.1 | Pre-deploy check command | 4h | `task deploy:check` |
| 3.2 | Hash comparison logic | 4h | `scripts/orchestration/deploy/hash_compare.py` |
| 3.3 | Selective apply logic | 6h | Feature-filtered playbook execution |
| 3.4 | Drift report generator | 4h | YAML drift report output |

### Phase 4: Operational (16h)

| Task | Component | Effort | Deliverable |
|------|-----------|--------|-------------|
| 4.1 | Taskfile commands | 4h | `taskfiles/deploy.yml` updates |
| 4.2 | Documentation | 4h | `docs/guides/HASH-BASED-DEPLOY.md` |
| 4.3 | Integration tests | 8h | `tests/integration/deploy/test_feature_hash.py` |

### Total Effort

| Phase | Hours | Cumulative |
|-------|-------|------------|
| Phase 1: Foundation | 18h | 18h |
| Phase 2: Device Adapters | 22h | 40h |
| Phase 3: Pipeline Integration | 18h | 58h |
| Phase 4: Operational | 16h | 74h |
| **TOTAL MVP** | **74h** | ~2 weeks full-time |

### Deferred (Phase 5+)

| Task | Effort | Rationale |
|------|--------|-----------|
| Feature-level rollback | 20h | Complexity; MVP uses snapshot |
| Scheduled drift scan | 8h | Nice-to-have for automation |
| Auto-fix drift mode | 12h | Risk of unintended changes |
| Feature version history | 16h | Required for feature rollback |

---

## Consequences

### Positive

1. **Granular idempotency** — each feature verified independently before apply
2. **Efficient deploys** — skip unchanged features, reduce apply time
3. **Drift detection** — identify exactly which configuration changed
4. **Audit trail** — feature-level history with timestamps
5. **Platform-native storage** — no external dependencies, uses existing APIs

### Negative / Trade-offs

1. **Complexity increase** — more components to maintain (plugin, adapters, comparator)
2. **Platform adapters** — 4 implementations required and must be maintained
3. **No manual changes** — strict pipeline-only workflow enforced
4. **MVP limitation** — rollback is snapshot-level only until Phase 5

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Hash collision | Negligible | High | SHA256 truncated to 16 chars (2^64 space) |
| Platform API changes | Low | Medium | Version-pin adapters, integration tests |
| Feature boundary drift | Low | Medium | Explicit capability→feature mapping in schema |
| Storage limit exceeded | Low | Medium | Monitor feature count, compress if needed |

### Migration Path

1. **No breaking changes** — ADR 0105 snapshot model remains valid
2. **Additive layer** — feature hashes layer on top of snapshot
3. **Gradual adoption** — can enable per-device via deploy profile
4. **Backward compatible** — devices without feature hashes treated as "first deploy"

---

## Validation

### Acceptance Criteria

| Criterion | Validation Method |
|-----------|-------------------|
| Hash computation deterministic | Unit test with fixed input |
| Device storage works (all 4 platforms) | Integration test per platform |
| Pre-deploy comparison accurate | Integration test with known state |
| Drift detection correct | Test with simulated manual change |
| Selective apply works | Apply single feature, verify others unchanged |
| Snapshot rollback works | End-to-end rollback test |

### Quality Gates

```bash
# Must pass before implementation complete
task test:unit -- tests/unit/deploy/test_feature_hash.py
task test:integration -- tests/integration/deploy/
task validate:plugin-manifests
task ci
```

---

## References

### Internal ADRs

- ADR 0105: Device State Management Using Industry Best Practices (Deferred)
- ADR 0085: Deploy Bundle and Runner Workspace Contract
- ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle
- ADR 0104: Ansible Role Generation from Topology
- ADR 0072: Unified Secrets Management with SOPS and age
- ADR 0083: Unified Node Initialization Contract

### Implementation Paths

- `scripts/orchestration/deploy/` — Deploy domain implementation
- `topology-tools/plugins/assemblers/` — Assembler plugin location
- `adr/0115-analysis/` — SPC analysis artifacts

### Industry Sources

- [How Nix Works](https://nixos.org/guides/how-nix-works/) — Hash-based package management philosophy
- [Ansible Configuration Drift Management](https://spacelift.io/blog/ansible-configuration-drift-management) — Drift detection patterns
- [Terraform State Best Practices](https://spacelift.io/blog/terraform-state) — State isolation and versioning
- [Pulumi vs Terraform Comparison](https://www.pulumi.com/docs/iac/comparisons/terraform/) — Drift detection features
- [GitOps & IaC in 2025](https://medium.com/codetodeploy/gitops-infrastructure-as-code-iac-why-theyre-game-changers-in-2025-e89d8c426fea) — Continuous reconciliation
- [mgmt config](https://mgmtconfig.com/) — Reactive configuration management
- [NixOS for Immutable Infrastructure](https://www.gocodeo.com/post/using-nixos-for-immutable-infrastructure-and-declarative-configuration) — Declarative systems
- [Network Automation Guide 2026](https://calmops.com/network/network-automation-ansible-terraform-guide/) — Terraform + Ansible integration
