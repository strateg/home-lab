# ADR 0103: Runtime Reconciliation Status Replaces Static Instance Status

- Status: Proposed (Revised after SPC Analysis)
- Date: 2026-06-07
- Revised: 2026-06-07 (SPC Review)

## Context

### Current Problem

Instance YAML files contain a static `status` field with values like `mapped`, `modeled`, or `deployed`:

```yaml
# projects/home-lab/topology/instances/network/inst.vlan.servers.yaml
@instance: inst.vlan.servers
@extends: obj.network.vlan.servers
status: modeled  # <-- Static, manually maintained
```

This approach has fundamental problems:

1. **Stale data**: Status becomes outdated after deployments. VLANs marked `modeled` are actually deployed on the device.

2. **Manual maintenance burden**: Operators must remember to update status after every `terraform apply`.

3. **Single source of truth violation**: Topology should declare *intent* (desired state), not *reality* (actual state). Reality should be queried from devices.

4. **No drift detection**: Static status cannot detect when device state diverges from topology.

### Historical Context

In v4 architecture, topology was "documentation of reality" — manual records of what already exists. The `status: mapped` convention meant "this is documented from the real device."

During v4 → v5 migration, files were ported as-is without rethinking the status model. This created architectural debt.

### Desired Model

Infrastructure-as-Code tools (Terraform, Ansible, Kubernetes) follow a different model:

```
Desired State (declarative) + Actual State (queried) → Computed Status (runtime)
```

Terraform never stores "is this deployed?" in `.tf` files. It computes drift by comparing `.tf` (desired) with `.tfstate` (actual).

### Architectural Constraints (from SPC Analysis)

The solution must respect established framework constraints:

| Constraint | Source | Implication |
|------------|--------|-------------|
| Stage affinity | ADR 0080, 0086 | Reconciliation ≠ validation |
| Determinism | ADR 0074 D2 | Pipeline outputs must be reproducible |
| CI compatibility | Infrastructure | CI cannot reach production devices |
| Plugin timeout | ADR 0097 | 30 second default limit |
| Fixed stages | ADR 0080 | discover→compile→validate→generate→assemble→build |

## Decision

### D1. Remove `status` field from instance YAML files

The `status` field will be removed from all instance files. Topology defines *intent only*.

**Before:**
```yaml
@instance: inst.vlan.servers
@extends: obj.network.vlan.servers
status: modeled  # Remove this
vlan_id: 30
cidr: 10.0.30.0/24
```

**After:**
```yaml
@instance: inst.vlan.servers
@extends: obj.network.vlan.servers
vlan_id: 30
cidr: 10.0.30.0/24
```

**Migration:** Scripted removal of `status:` line from 151 instance files.

### D2. Dual-Mode Reconciliation Architecture

Reconciliation operates in two distinct modes to satisfy both determinism and drift detection requirements:

#### D2.1 Pipeline Mode: Terraform State Reconciler (Deterministic)

A build-stage plugin computes status by parsing Terraform `.tfstate` files — deterministic, offline-capable, CI-safe.

**Plugin contract:**
```yaml
id: base.builder.terraform_state_reconciler
kind: builder
stage: build
phase: verify
order: 520
execution_mode: subinterpreter
consumes:
  - from_plugin: base.compiler.instance_rows_prepare
    key: normalized_rows
    required: true
produces:
  - key: terraform_reconciliation_report
    scope: pipeline_shared
config:
  state_paths:
    mikrotik: generated/home-lab/terraform/mikrotik/terraform.tfstate
    proxmox: generated/home-lab/terraform/proxmox/terraform.tfstate
  on_missing_state: warn  # warn | error | skip
```

**Why build stage (not validate):**
- Validate stage = structural/domain validation of *source* data
- Build stage = produce artifacts and reports from *compiled* data
- Reconciliation produces a report artifact → build stage

**Determinism guarantee:** Terraform state files are artifacts with known content. Same input → same output.

#### D2.2 CLI Mode: Live Device Reconciler (On-Demand)

A standalone CLI command queries live devices via REST API — non-deterministic, requires connectivity, operator-initiated.

```bash
# Live device reconciliation (not part of compile pipeline)
./scripts/orchestration/lane.py reconcile --target rtr-mikrotik-chateau
./scripts/orchestration/lane.py reconcile --all --format json
```

**Why separate from pipeline:**
- Live queries are non-deterministic (violates ADR 0074)
- Requires device connectivity (fails in CI)
- May exceed plugin timeout (30s) for many devices
- Operator should explicitly choose when to query devices

### D3. Define computed status values

| Status | Definition | Action |
|--------|------------|--------|
| `synced` | Topology = State source | None needed |
| `drift` | Topology ≠ State source | Review and apply |
| `missing` | In topology, not in state | Apply to create |
| `extra` | In state, not in topology | Import or remove |
| `unreachable` | Device not accessible (CLI mode only) | Check connectivity |
| `no_state` | No Terraform state file found | Run terraform apply |

### D4. State Source Precedence

When multiple state sources exist, explicit precedence:

| Priority | Source | Role |
|----------|--------|------|
| 1 | Topology YAML | **Intent** — what operator wants |
| 2 | Terraform state | **Planned** — what Terraform last applied |
| 3 | Device API | **Actual** — what exists on device |

Reconciliation reports show discrepancies between these layers.

### D5. Reconciliation Report Format

**Pipeline mode output (build artifact):**
```
generated/home-lab/reports/reconciliation-terraform.json
```

**CLI mode output:**
```
Reconciliation Report: rtr-mikrotik-chateau
═══════════════════════════════════════════

Resource                    Topology    TF State    Device      Status
──────────────────────────────────────────────────────────────────────────
inst.vlan.servers           10.0.30.1   10.0.30.1   10.0.30.1   synced
inst.vlan.iot               192.168.40.1 192.168.40.1 192.168.40.1 synced
bridge.internal             -           -           172.18.0.1  extra
container.app-transmission  -           -           running     extra

Summary: 4 synced, 0 drift, 0 missing, 2 extra, 0 unreachable
```

### D6. CI/Production Mode Selection

| Environment | Pipeline Plugin | CLI Command |
|-------------|-----------------|-------------|
| CI | ✅ Terraform state only | ❌ Skipped (no device access) |
| Local dev | ✅ Terraform state | ✅ Available (optional) |
| Production | ✅ Terraform state | ✅ Available |

**Profile-based configuration:**
```yaml
# In plugin config
when:
  profiles: [production, development]  # Skip in CI profile
```

### D7. Credential Integration (CLI Mode)

Live device queries use existing SOPS/age secrets infrastructure:

```python
# scripts/orchestration/reconcile.py
from scripts.secrets.sops_decrypt import decrypt_secret

credentials = decrypt_secret("projects/home-lab/secrets/terraform/mikrotik.yaml")
```

No new credential paths — reuses existing `secrets/terraform/*.yaml` files.

### D8. Optional `managed_by` hint field

For instances requiring explicit state source mapping:

```yaml
@instance: inst.vlan.servers
@extends: obj.network.vlan.servers
managed_by:
  tool: terraform
  state_path: generated/home-lab/terraform/mikrotik
  resource_type: routeros_interface_vlan
  resource_name: vlan30
```

Auto-discovery is preferred; this field is for edge cases.

## Consequences

### Positive

1. **Single source of truth**: Topology = intent, state files = planned, device = actual
2. **Deterministic pipeline**: Terraform state parsing is reproducible
3. **CI compatibility**: No device connectivity required in CI
4. **Drift detection**: Both state-based (fast) and live (accurate) options
5. **Reduced maintenance**: No manual status field updates
6. **Alignment with IaC**: Follows Terraform model

### Negative

1. **Dual-mode complexity**: Two reconciliation paths to understand
2. **State file dependency**: Requires `terraform apply` to have run
3. **Delayed live detection**: Out-of-band changes only visible in CLI mode
4. **Implementation effort**: Plugin + CLI + migration

### Trade-offs vs Original ADR 0103

| Aspect | Original | Revised |
|--------|----------|---------|
| Stage | validate | build |
| Mode | Single (live) | Dual (state + live) |
| CI | Would fail | Works |
| Determinism | Violated | Preserved |
| Drift detection | Full | Partial (state) + Full (CLI) |

## Implementation Plan

### Wave 1: Foundation
- [ ] Create `base.builder.terraform_state_reconciler` plugin
- [ ] Implement Terraform state JSON parser
- [ ] Add reconciliation report schema

### Wave 2: CLI Tool
- [ ] Add `lane.py reconcile` subcommand
- [ ] Implement MikroTik REST API fetcher
- [ ] Integrate SOPS credential decryption
- [ ] Create comparison logic (topology vs state vs device)

### Wave 3: Migration
- [ ] Script to remove `status` field from 151 instance files
- [ ] Update any code referencing `status` field (currently zero)
- [ ] Update documentation

### Wave 4: Extended Sources (Future)
- [ ] Proxmox API state fetcher
- [ ] Docker API state fetcher
- [ ] Generic SSH probe

## Compliance Matrix

| Constraint | How Satisfied |
|------------|---------------|
| ADR 0080 stage affinity | Plugin in build stage (not validate) |
| ADR 0074 determinism | Terraform state parsing (not live queries) |
| ADR 0097 timeout | State file parsing < 1 second |
| CI compatibility | No device connectivity required |
| ADR 0063 plugin contract | Valid `consumes`/`produces` references |

## References

- Original ADR 0103: `adr/0103-analysis/ORIGINAL-ADR-0103.md`
- SPC Analysis: `adr/0103-analysis/SPC-ANALYSIS.md`
- Terraform state management: https://developer.hashicorp.com/terraform/language/state
- ADR 0063: Plugin microkernel architecture
- ADR 0074: Generator determinism
- ADR 0080: Unified build pipeline
- ADR 0097: Subinterpreter execution
