# ADR 0103: Runtime Reconciliation Status Replaces Static Instance Status

- Status: Partially Implemented (Wave 3 only, Waves 1/2/4 Cancelled)
- Date: 2026-06-07
- Revised: 2026-06-18 (Wave 3 complete; Waves 1/2/4 cancelled)
- SWOT Analysis: `adr/0103-analysis/SWOT-ANALYSIS.md`

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

### D9. Reconciliation Report Schema

Pipeline mode produces `generated/{project}/reports/reconciliation-terraform.json` with formal schema:

```json
{
  "type": "object",
  "properties": {
    "generated_at": { "type": "string", "format": "date-time" },
    "state_sources": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "modified_at": { "type": "string", "format": "date-time" },
          "terraform_version": { "type": "string" },
          "resource_count": { "type": "integer" }
        }
      }
    },
    "reconciliation": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "instance_id": { "type": "string" },
          "resource_address": { "type": "string" },
          "status": { "enum": ["synced", "drift", "missing", "extra", "no_state"] },
          "topology_value": { "type": "object" },
          "state_value": { "type": "object" },
          "diff": { "type": "array" }
        }
      }
    },
    "summary": {
      "type": "object",
      "properties": {
        "total": { "type": "integer" },
        "synced": { "type": "integer" },
        "drift": { "type": "integer" },
        "missing": { "type": "integer" },
        "extra": { "type": "integer" },
        "no_state": { "type": "integer" }
      }
    }
  }
}
```

### D10. Diagnostic Code Allocation

**Note:** E81xx is reserved for assembly stage (ADR 0080). Reconciliation uses E83xx.

| Range | Domain | Examples |
|-------|--------|----------|
| E8300-E8309 | State file errors | E8300: State file not found, E8301: State file unreadable |
| E8310-E8319 | Parse errors | E8310: Invalid tfstate JSON, E8311: Unsupported TF version |
| E8320-E8329 | Mapping errors | E8320: No resource match for instance, E8321: Ambiguous match |
| W8350-W8359 | Warnings | W8350: State file older than 24h, W8351: Partial coverage |
| I8380-I8389 | Info | I8380: Reconciliation complete, I8381: N resources matched |

### D11. Convention-Based Resource Discovery

When `managed_by` is not specified, the reconciler uses naming conventions:

| Instance Pattern | Terraform Resource Pattern | Example |
|------------------|---------------------------|---------|
| `inst.vlan.{name}` | `routeros_interface_vlan.{name}` | inst.vlan.servers → routeros_interface_vlan.servers |
| `lxc-{name}` | `proxmox_lxc.{name}` | lxc-grafana → proxmox_lxc.grafana |
| `docker-{name}` | `docker_container.{name}` | docker-nginx → docker_container.nginx |
| `rtr-{name}` | `routeros_system_identity.{name}` | rtr-mikrotik-chateau → routeros_system_identity.main |

Fallback: If no match found, status = `no_state` with diagnostic hint to add `managed_by`.

### D12. State Source Expansion Roadmap

Current coverage is ~15% of instances. Expansion phases:

| Phase | State Source | Coverage Delta | Total Coverage | Prerequisite |
|-------|--------------|----------------|----------------|--------------|
| Current | MikroTik tfstate | baseline | ~5% | None |
| Phase 1 | + OCI tfstate | +5% | ~10% | None (exists) |
| Phase 2 | + Proxmox tfstate | +30% | ~40% | Create Proxmox TF config |
| Phase 3 | + Docker snapshots | +20% | ~60% | Snapshot capture script |
| Phase 4 | + Ansible fact cache | +20% | ~80% | Fact gathering playbook |

This roadmap is informational; each phase requires separate implementation effort.

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

> **Decision 2026-06-18:** Waves 1, 2, and 4 are **cancelled**. Wave 3 (status field removal) delivered the core architectural value. `terraform plan` already solves drift detection for this single-operator home-lab. 63h of additional implementation does not justify the complexity for a non-production environment.

**Total estimated effort: 39h** (Phases 0-2) + 24h (Wave 4, future)

### Phase 0: Pre-flight (5h)

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| 0.1 | Verify build stage runtime readiness | 2h | Pending |
| 0.2 | Allocate E81xx diagnostic codes in error-catalog.yaml | 1h | Pending |
| 0.3 | Create reconciliation report JSON schema file | 2h | Pending |

### Wave 1: Terraform State Reconciler Plugin (17h)

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| 1.1 | Create `base.builder.terraform_state_reconciler` skeleton | 2h | Pending |
| 1.2 | Implement tfstate JSON parser | 3h | Pending |
| 1.3 | Implement instance-to-resource matcher (D11 conventions) | 4h | Pending |
| 1.4 | Generate reconciliation report (D9 schema) | 3h | Pending |
| 1.5 | Add plugin contract tests | 3h | Pending |
| 1.6 | Integration test with real tfstate | 2h | Pending |

### Wave 2: CLI Reconcile Command (17h)

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| 2.1 | Add `reconcile` subcommand to lane.py | 2h | Pending |
| 2.2 | Implement MikroTik REST client (or use routeros-api) | 4h | Pending |
| 2.3 | Implement comparison logic (topology vs state vs device) | 4h | Pending |
| 2.4 | Implement table/json output formatters | 2h | Pending |
| 2.5 | Integrate SOPS credential decryption | 2h | Pending |
| 2.6 | Add CLI tests | 3h | Pending |

### Wave 3: Migration ✅ COMPLETE

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| 3.1 | Script to remove `status` field from 151 instance files | - | ✅ Done (2026-06-18) |
| 3.2 | Update any code referencing `status` field | - | ✅ N/A (zero refs) |
| 3.3 | Update documentation | - | ✅ Done |

### Wave 4: State Source Expansion (24h, Future)

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| 4.1 | Create Proxmox Terraform configuration | 8h | Future |
| 4.2 | Docker inspect snapshot script | 4h | Future |
| 4.3 | Ansible fact cache integration | 6h | Future |
| 4.4 | Proxmox API live reconciler | 6h | Future |

### Dependency Graph

```
Phase 0 (Pre-flight) ──┬── 0.1 Verify build stage
                       ├── 0.2 Allocate E81xx
                       └── 0.3 Report schema
                              │
                              ▼
Wave 1 (Plugin) ───────────────────────┐
       │                               │
       ├── 1.1 Plugin skeleton         │
       ├── 1.2 tfstate parser          │
       ├── 1.3 Instance matcher ◄──────┤ Uses D11
       ├── 1.4 Report generator ◄──────┤ Uses D9
       ├── 1.5 Contract tests          │
       └── 1.6 Integration tests       │
              │                        │
              ▼                        │
Wave 2 (CLI) ◄─────────────────────────┘ Shares core logic
       │
       ├── 2.1 CLI skeleton
       ├── 2.2 MikroTik client
       ├── 2.3 Comparison logic
       ├── 2.4 Formatters
       ├── 2.5 SOPS integration
       └── 2.6 CLI tests
              │
              ▼
Wave 4 (Expansion) ── Future scope
```

## Compliance Matrix

| Constraint | Source | How Satisfied | Decision |
|------------|--------|---------------|----------|
| Stage affinity | ADR 0080, 0086 | Plugin in build stage (not validate) | D2.1 |
| Determinism | ADR 0074 D2 | Terraform state parsing (not live queries) | D2.1 |
| Plugin timeout | ADR 0097 | State file parsing < 1 second | D2.1 |
| CI compatibility | Infrastructure | No device connectivity required in pipeline | D6 |
| Plugin contract | ADR 0063 | Valid `consumes`/`produces` references | D2.1, D9 |
| Topology = intent | This ADR | No status field in instance YAML | D1 |
| Credentials | ADR 0072, 0073 | SOPS/age integration for CLI mode | D7 |
| Diagnostics | ADR 0065 | E81xx range allocated | D10 |

## SWOT Summary

| Category | Key Points |
|----------|------------|
| **Strengths** | Dual-mode architecture; deterministic pipeline; SOPS reuse; Wave 3 complete |
| **Weaknesses** | 15% tfstate coverage; no Proxmox state; dual-mode complexity |
| **Opportunities** | Proxmox TF provider; Docker snapshots; unified dashboards; Ansible facts |
| **Threats** | Stale state files; TF version changes; out-of-band changes invisible |

Full analysis: `adr/0103-analysis/SWOT-ANALYSIS.md`

---

## Cancellation Record (2026-06-18)

**Cancelled: Waves 1, 2, 4 (Phase 0 + ~63h of implementation work)**

### Decision

Waves 1 (Terraform State Reconciler Plugin), 2 (CLI Reconcile Command), and 4 (State Source Expansion) are permanently cancelled. Wave 3 is the sole deliverable of this ADR.

### Rationale

1. **Core goal achieved.** The primary motivation was removing stale `status:` fields from instance YAML to make topology purely declarative. Wave 3 completed this. The remaining waves address a separate concern (state visibility) that was not the original architectural problem.

2. **Terraform is the reconciliation engine.** `terraform plan` already computes drift between topology intent and Terraform state. `terraform show` exposes current applied state. Building a custom reconciliation layer duplicates mature tooling already in the stack.

3. **Economics do not justify the cost.** 63h of development produces a JSON report with ~5% instance coverage (MikroTik tfstate only) for a single operator who knows what is deployed because they deployed it. Raising coverage to ~40% first requires creating Proxmox Terraform configuration — a separate large effort outside this ADR's scope.

4. **Dual-mode architecture is overengineered for home-lab.** Build-stage plugin + CLI command = two independent execution paths, two test suites, two failure modes. This is appropriate for multi-operator production systems, not a single-operator home laboratory.

5. **No risk from cancellation.** No SLA, no audit trail requirement, no dashboard consumers. The only missing artifact (`generated/home-lab/reports/reconciliation-terraform.json`) provides no value that `terraform plan` does not already provide in a more readable form.

### What Remains Valid

- **D1** (Remove `status` from instance YAML) — implemented, permanent, correct.
- The architectural principle: topology = intent only; Terraform state = actual state.
- Native workflow: `terraform plan` for drift detection, `terraform show` for state inspection.

### Decisions Cancelled

D2 through D12 are cancelled. No implementation required.

---

## References

- Original ADR 0103: `adr/0103-analysis/ORIGINAL-ADR-0103.md`
- SPC Analysis: `adr/0103-analysis/SPC-ANALYSIS.md`
- Terraform state management: https://developer.hashicorp.com/terraform/language/state
- ADR 0063: Plugin microkernel architecture
- ADR 0074: Generator determinism
- ADR 0080: Unified build pipeline
- ADR 0097: Subinterpreter execution
