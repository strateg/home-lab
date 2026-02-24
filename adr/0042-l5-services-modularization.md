---
adr: "0042"
layer: "L5"
scope: "services-modularization"
status: "Accepted"
date: "2026-02-24"
public_api:
  - "L5 services[].id"
  - "L5 services[].runtime.target_ref"
breaking_changes: false
related:
  - "0040"
  - "0041"
---

# ADR 0042: L5 Services Modularization

- Status: Accepted
- Date: 2026-02-24

## Context

L5 `services.yaml` grew to 531 lines containing 19 services across 4 runtime targets. This created several issues:

1. **Navigation difficulty**: Finding a specific service required scrolling through unrelated services
2. **Merge conflicts**: Multiple changes to the same file increased conflict risk
3. **Cognitive load**: Understanding service relationships required mental grouping
4. **Inconsistency**: L1-L4 layers already use modular `!include_dir_sorted` pattern

### Current State

```
topology/L5-application/
├── services.yaml      # 531 lines, 19 services
├── dns.yaml           # 169 lines
└── certificates.yaml  # 90 lines
```

### Service Distribution

| Runtime Target | Services | Functional Groups |
|----------------|----------|-------------------|
| mikrotik-chateau | 8 | network, monitoring, iot, ui |
| orangepi5 | 8 | apps, monitoring |
| gamayun | 1 | ui |
| lxc-* | 2 | data |

## Decision

### D1. Adopt hybrid modularization (host + function)

Split services by runtime target (host), then by functional domain within each host:

```
topology/L5-application/
├── services/
│   ├── mikrotik/
│   │   ├── network.yaml      # adguard, wireguard, tailscale, ntp
│   │   ├── monitoring.yaml   # snmp, syslog-forward
│   │   ├── iot.yaml          # mosquitto
│   │   └── ui.yaml           # mikrotik-ui
│   ├── orangepi5/
│   │   ├── apps.yaml         # nextcloud, jellyfin, homeassistant
│   │   └── monitoring.yaml   # prometheus, alertmanager, loki, grafana, adguard-secondary
│   ├── proxmox/
│   │   └── ui.yaml           # proxmox-ui
│   └── lxc/
│       └── data.yaml         # postgresql, redis
├── dns/
│   └── zones.yaml
└── certificates/
    └── certs.yaml
```

### D2. Use `!include_dir_sorted` for services

The loader recursively collects all YAML files from `services/` directory into a flat array, maintaining the same data model.

```yaml
# L5-application.yaml
services: !include_dir_sorted L5-application/services
dns: !include L5-application/dns/zones.yaml
certificates: !include L5-application/certificates/certs.yaml
```

### D3. File structure is informational only

The directory and file names exist for human navigation. The canonical model is defined by:
- `id` field in each service
- `*_ref` fields for cross-references

Moving a service between files does not change its identity or relationships.

### D4. Target file size: 50-120 lines

Each module file should contain related services that fit on ~2 screens. Split further if a file exceeds ~150 lines.

## Consequences

### Benefits

- **Faster navigation**: Find services by host/function path
- **Reduced conflicts**: Independent files for independent changes
- **Clear ownership**: MikroTik services in `mikrotik/`, OrangePi5 in `orangepi5/`
- **Consistent pattern**: Matches L1-L4 modular structure

### Trade-offs

- More files to manage (10 vs 3)
- Need to know which host runs a service to find its file

### Migration

No data migration required. Services retain their `id` values. Only file organization changes.

### File Size Comparison

| Metric | Before | After |
|--------|--------|-------|
| Files | 1 | 10 |
| Max lines | 531 | 113 |
| Avg lines | 531 | 65 |

## References

- [ADR 0040](0040-l0-l5-canonical-ownership-and-refactoring-plan.md) - L0-L5 refactoring plan
- [ADR 0041](0041-l4-workload-network-attachment-typing.md) - L4 network typing
- `topology/L1-foundation.yaml` - Example of `!include_dir_sorted` pattern
- `topology/L5-application/services/` - New modular structure
