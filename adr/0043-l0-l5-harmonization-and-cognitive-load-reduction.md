---
adr: "0043"
layer: "L0-L5"
scope: "harmonization-cognitive-load"
status: "Accepted"
date: "2026-02-24"
public_api:
  - "L1 devices[].id prefix convention"
  - "L5 services[].data_asset_refs"
  - "L2 trust_zones cleanup"
breaking_changes: false
related:
  - "0040"
  - "0042"
---

# ADR 0043: L0-L5 Harmonization and Cognitive Load Reduction

- Status: Accepted
- Date: 2026-02-24

## Context

Cross-layer analysis of L0-L5 revealed several inconsistencies and cognitive load issues:

### Findings Summary

| Category | Issue | Impact |
|----------|-------|--------|
| L1 ID naming | No consistent prefix for devices | Hard to identify layer from ref |
| L5 hardcoded IPs | 20+ IPs duplicated from L2 | Maintenance burden |
| Data asset gaps | 7 services without data_asset_refs | Incomplete governance |
| Orphaned assets | 2 data_assets not referenced | Dead code |
| Unused trust zones | `guest`, `untrusted` defined but unused | Noise |
| Mono-policy | All services use `sec-baseline` | Redundant field |
| Zone overload | 13/19 services in `servers` zone | Security granularity loss |

### Design Principles Violated

1. **DRY**: IPs defined in L2, duplicated in L5
2. **Consistency**: L1 IDs lack prefix pattern used in L2-L5
3. **Completeness**: Services without data governance
4. **Minimalism**: Unused zones/redundant fields add noise

## Decision

### Phase 0: Quick Cleanup (No Breaking Changes)

#### P0.1: Add missing data_asset_refs

Create data assets and add refs for stateless-looking but actually stateful services:

| Service | Data Asset | Type |
|---------|------------|------|
| svc-loki | data-loki | volume |
| svc-alertmanager | data-alertmanager | volume |
| svc-adguard-secondary | data-adguard-secondary | volume |
| svc-proxmox-ui | (native, covered by data-mikrotik-config pattern) | - |

Native RouterOS services (svc-snmp, svc-syslog-forward, svc-ntp) are stateless; no data asset needed.

#### P0.2: Remove orphaned data assets

Delete unused data assets:
- `data-postgresql-rootfs` - LXC rootfs managed by Proxmox, not app data
- `data-redis-rootfs` - LXC rootfs managed by Proxmox, not app data

These are infrastructure, not application data assets.

#### P0.3: Clean up unused trust zones

Options:
- **A**: Delete `guest` and `untrusted` from definitions
- **B**: Keep for future use, add `# reserved` comment

Decision: **B** - Keep with comment. Zones are part of security model.

#### P0.4: Remove redundant security_policy_ref

If all services use `sec-baseline`:
- Move to L5 defaults
- Remove from individual services

Decision: Keep explicit refs. Different services may need different policies in future.

### Phase 1: Naming Harmonization

#### P1.1: Standardize L1 device ID prefixes

Adopt prefix convention matching device class:

| Class | Prefix | Example |
|-------|--------|---------|
| compute | `srv-` | `srv-gamayun`, `srv-orangepi5` |
| network | `rtr-` | `rtr-mikrotik-chateau` |
| power | `ups-`, `pdu-` | `ups-main` (already OK) |

**Breaking change scope**: All refs to devices must update.

Migration:
1. Update L1 device IDs
2. Update all `device_ref`, `target_ref` in L2-L5
3. Update `host_os[].device_ref` in L4
4. Validate

#### P1.2: Split overloaded `servers` trust zone

Current: 13 services in `servers`

Proposed split:
| Zone | Services | Purpose |
|------|----------|---------|
| `servers-data` | postgresql, redis | Database tier |
| `servers-app` | nextcloud, jellyfin, homeassistant | Application tier |
| `servers-mon` | prometheus, alertmanager, loki, grafana, adguard-secondary | Monitoring tier |

**Breaking change scope**: All `trust_zone_ref: servers` must update.

### Phase 2: IP Derivation (Future)

#### P2.1: Remove hardcoded IPs from L5

Current pattern (bad):
```yaml
config:
  POSTGRES_HOST: 10.0.30.10
```

Target pattern:
```yaml
config:
  POSTGRES_HOST_REF: lxc-postgresql  # Generator resolves to IP
```

Requires generator changes to resolve refs to IPs at generation time.

Deferred to separate ADR.

## Consequences

### Benefits

- Consistent naming across all layers
- Complete data governance coverage
- Reduced cognitive load (fewer exceptions to remember)
- Cleaner trust zone model

### Trade-offs

- P1 requires coordinated ref updates (breaking)
- P2 requires generator changes

### Migration Risk

| Phase | Risk | Mitigation |
|-------|------|------------|
| P0 | Low | Additive/cleanup only |
| P1 | Medium | Run validator after each step |
| P2 | High | Separate ADR, incremental rollout |

## Execution Plan

See: `docs/architecture/L0-L5-HARMONIZATION-PLAN.md`

## Success Criteria

### P0 Complete When ✅

- [x] All stateful services have data_asset_refs
- [x] No orphaned data_assets
- [x] Unused trust zones marked as reserved

### P1 Complete When

- [ ] All L1 devices have class-based prefix
- [ ] servers zone split into 3 sub-zones
- [ ] Validation passes

### P2 Complete When

- [ ] Zero hardcoded IPs in L5 services
- [ ] Generators resolve refs to IPs

## References

- [ADR 0040](0040-l0-l5-canonical-ownership-and-refactoring-plan.md) - Prior L0-L5 refactoring
- [ADR 0042](0042-l5-services-modularization.md) - L5 modularization
- `topology/L1-foundation/devices/` - Device definitions
- `topology/L2-network/trust-zones/` - Trust zone definitions
- `topology/L5-application/services/` - Service definitions
