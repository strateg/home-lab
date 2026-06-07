# ADR 0103: Runtime Reconciliation Status Replaces Static Instance Status

- Status: Proposed
- Date: 2026-06-07

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

### D2. Introduce reconciliation plugin

A new plugin `base.validator.device_reconciler` will compute status at runtime by comparing topology with actual device state.

**Plugin contract:**
```yaml
id: base.validator.device_reconciler
stage: validate
consumes:
  - from_plugin: base.compile.instance_index
    field: instances
produces:
  - field: reconciliation_report
    scope: pipeline
```

**Reconciliation sources:**
| Device Type | State Source |
|-------------|--------------|
| MikroTik | REST API (`/rest/*`) |
| Proxmox | Terraform state + API |
| Docker hosts | Docker API / SSH |
| Generic | SSH probes |

### D3. Define computed status values

| Status | Definition | Action |
|--------|------------|--------|
| `synced` | Topology = Device state | None needed |
| `drift` | Topology ≠ Device state | Review and apply |
| `missing` | In topology, not on device | Apply to create |
| `extra` | On device, not in topology | Import or remove |
| `unreachable` | Device not accessible | Check connectivity |
| `unmanaged` | No state source configured | Configure or ignore |

### D4. Add reconciliation CLI command

```bash
# Check all devices
./scripts/orchestration/lane.py reconcile

# Check specific device
./scripts/orchestration/lane.py reconcile --target rtr-mikrotik-chateau

# Output formats
./scripts/orchestration/lane.py reconcile --format table
./scripts/orchestration/lane.py reconcile --format json
./scripts/orchestration/lane.py reconcile --format summary
```

**Example output:**
```
Reconciliation Report: rtr-mikrotik-chateau
═══════════════════════════════════════════

Resource                    Topology    Device      Status
────────────────────────────────────────────────────────────
inst.vlan.servers           10.0.30.1   10.0.30.1   synced
inst.vlan.iot               192.168.40.1 192.168.40.1 synced
inst.vlan.guest             192.168.30.1 192.168.30.1 synced
inst.vlan.management        10.0.99.1   10.0.99.1   synced
bridge.internal             -           172.18.0.1  extra
container.app-transmission  -           running     extra

Summary: 4 synced, 0 drift, 0 missing, 2 extra
```

### D5. Optional: `managed_by` field for state source hints

For instances that need explicit state source configuration:

```yaml
@instance: inst.vlan.servers
@extends: obj.network.vlan.servers
managed_by:
  tool: terraform
  state_path: generated/home-lab/terraform/mikrotik
  resource_address: routeros_interface_vlan.vlan30
```

This is optional — the reconciler should auto-discover state sources when possible.

### D6. Deprecation period for `status` field

1. **Phase 1 (immediate)**: Add deprecation warning when `status` field is present
2. **Phase 2 (30 days)**: Stop reading `status` field, use reconciler only
3. **Phase 3 (60 days)**: Remove `status` field from all instance files

## Consequences

### Positive

1. **Single source of truth**: Topology = intent, device = reality, status = computed
2. **Always accurate**: Status reflects actual device state, not stale manual entries
3. **Drift detection**: Operators can see divergence before it causes problems
4. **Reduced maintenance**: No manual status updates after deployments
5. **Alignment with IaC principles**: Follows Terraform/Kubernetes model

### Negative

1. **Requires connectivity**: Reconciliation needs device access (REST API, SSH, etc.)
2. **Performance overhead**: Querying devices adds latency to status checks
3. **Complexity**: New plugin and CLI command to implement and maintain
4. **Credential management**: Reconciler needs device credentials

### Migration Impact

1. **~130 instance files** need `status` field removed
2. **Validators** that check `status` field need updates
3. **Documentation** referencing `status: mapped/modeled` needs updates
4. **CI/CD pipelines** may need reconciliation step added

### Risks

1. **Device unavailability**: Reconciler must handle offline devices gracefully
2. **API rate limits**: Batch queries to avoid overwhelming device APIs
3. **State source ambiguity**: Some resources may have multiple potential state sources

## Implementation Plan

### Wave 1: Foundation (Week 1-2)
- [ ] Create `base.validator.device_reconciler` plugin skeleton
- [ ] Implement MikroTik REST API state fetcher
- [ ] Add `reconcile` subcommand to `lane.py`

### Wave 2: Core Reconciliation (Week 3-4)
- [ ] Implement topology-to-device comparison logic
- [ ] Add Terraform state reader for managed resources
- [ ] Create reconciliation report format

### Wave 3: Deprecation (Week 5-6)
- [ ] Add deprecation warnings for `status` field
- [ ] Update validators to ignore `status` field
- [ ] Remove `status` from instance files (scripted migration)

### Wave 4: Extended Sources (Future)
- [ ] Proxmox API state fetcher
- [ ] Docker API state fetcher
- [ ] SSH probe fallback for generic devices

## References

- Terraform state management: https://developer.hashicorp.com/terraform/language/state
- Kubernetes reconciliation loop: https://kubernetes.io/docs/concepts/architecture/controller/
- ADR 0063: Plugin microkernel architecture
- ADR 0080: Unified build pipeline
- MikroTik REST API: https://help.mikrotik.com/docs/display/ROS/REST+API
