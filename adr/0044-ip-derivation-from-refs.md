---
adr: "0044"
layer: "L5"
scope: "ip-derivation"
status: "Accepted"
date: "2026-02-24"
public_api:
  - "L5 services config IP refs"
  - "Generator IP resolution"
breaking_changes: false
related:
  - "0043"
  - "0040"
---

# ADR 0044: IP Derivation from Refs

- Status: Accepted
- Date: 2026-02-24

## Context

L5 services contain 21+ hardcoded IP addresses that duplicate information from L2 (ip_allocations) and L4 (LXC networks). This violates DRY and creates maintenance burden when IPs change.

### Current State

```yaml
# L5 service - hardcoded IP
config:
  POSTGRES_HOST: 10.0.30.10   # Duplicates L4 lxc-postgresql.networks[0].ip

# L4 workload - canonical source
networks:
- ip: 10.0.30.10/24
  network_ref: net-servers
```

### IP Distribution in L5

| IP | Count | Source | Entity |
|----|-------|--------|--------|
| 10.0.30.50 | 7 | L2 | hos-srv-orangepi5-ubuntu |
| 10.0.30.10 | 3 | L4 | lxc-postgresql |
| 10.0.30.20 | 3 | L4 | lxc-redis |
| 192.168.88.1 | 3 | L2 | hos-rtr-mikrotik-routeros |
| 192.168.88.2 | 2 | L2 | hos-srv-gamayun-proxmox |
| 10.0.99.1 | 1 | L2 | hos-rtr-mikrotik-routeros |
| 10.0.99.2 | 1 | L2 | hos-srv-gamayun-proxmox |

### Use Cases

1. **Service config** - `POSTGRES_HOST: <ip>` in environment
2. **Service URL** - `url: http://<ip>:port`
3. **Scrape targets** - Prometheus target IPs
4. **ACL rules** - pg_hba allow-from addresses
5. **Remote addresses** - syslog forwarding destination

## Decision

### D1. Introduce `ip_ref` pattern for service configs

New field `ip_ref` resolves to IP at generator time:

```yaml
# L5 service - new pattern
config:
  postgres_ip_ref:
    lxc_ref: lxc-postgresql
    network_ref: net-servers
  # Generator outputs: POSTGRES_HOST: 10.0.30.10
```

### D2. Resolution algorithm

IP resolution follows this lookup order:

1. **LXC workload**: `lxc_ref` + `network_ref` → L4 `lxc.networks[].ip`
2. **VM workload**: `vm_ref` + `network_ref` → L4 `vm.networks[].ip`
3. **Host OS**: `host_os_ref` + `network_ref` → L2 `networks[].ip_allocations[].ip`
4. **Service**: `service_ref` → resolve runtime target, then apply above

### D3. Schema additions

```yaml
IpRef:
  type: object
  properties:
    lxc_ref: { $ref: "#/definitions/LxcRef" }
    vm_ref: { $ref: "#/definitions/VmRef" }
    host_os_ref: { $ref: "#/definitions/HostOsRef" }
    service_ref: { $ref: "#/definitions/ServiceRef" }
    network_ref: { $ref: "#/definitions/NetworkRef" }
  oneOf:
    - required: [lxc_ref, network_ref]
    - required: [vm_ref, network_ref]
    - required: [host_os_ref, network_ref]
    - required: [service_ref]
```

### D4. Backward compatibility

- Existing hardcoded IPs continue to work
- New `*_ip_ref` fields are optional
- Migration is incremental, one service at a time
- Generators check for `*_ip_ref` fields, fallback to hardcoded

### D5. URL derivation (optional extension)

For service URLs, derive from runtime:

```yaml
# Current
url: http://10.0.30.50:9090

# New - generator constructs URL from runtime
url_derived: true  # Generator builds: http://<runtime_ip>:<port>
```

### D6. Scrape target derivation

For Prometheus scrape_targets:

```yaml
scrape_targets:
- name: postgresql
  type: postgres_exporter
  target_ref:
    lxc_ref: lxc-postgresql
    network_ref: net-servers
  port: 9187
  # Generator outputs: target: 10.0.30.10:9187
```

## Implementation Phases

### Phase 1: Schema and validator

1. Add `IpRef` definition to schema
2. Add IP resolution validator check
3. No generator changes yet

### Phase 2: Generator IP resolution

1. Implement `resolve_ip(ref, topology)` function
2. Process `*_ip_ref` fields in service configs
3. Generate resolved IPs in output

### Phase 3: Migrate L5 services

1. Replace hardcoded IPs with refs incrementally
2. Validate each service after migration
3. Remove hardcoded IPs when all refs work

### Phase 4: URL and target derivation

1. Implement `url_derived` pattern
2. Implement `target_ref` for scrape targets
3. Full derivation coverage

## Consequences

### Benefits

- Single source of truth for IPs
- Automatic propagation of IP changes
- Reduced cognitive load (no manual IP tracking)
- Better validation (refs checked at validate time)

### Trade-offs

- More complex generator logic
- Learning curve for ref syntax
- Debugging may require understanding resolution

### Migration Risk

Low - incremental migration with fallback to hardcoded values.

## Examples

### Before

```yaml
- id: svc-nextcloud
  config:
    POSTGRES_HOST: 10.0.30.10
    REDIS_HOST: 10.0.30.20
```

### After

```yaml
- id: svc-nextcloud
  config:
    postgres_ip_ref:
      lxc_ref: lxc-postgresql
      network_ref: net-servers
    redis_ip_ref:
      lxc_ref: lxc-redis
      network_ref: net-servers
```

### Generator output (Ansible vars)

```yaml
nextcloud_postgres_host: 10.0.30.10
nextcloud_redis_host: 10.0.30.20
```

## References

- [ADR 0043](0043-l0-l5-harmonization-and-cognitive-load-reduction.md) - L0-L5 harmonization
- [ADR 0040](0040-l0-l5-canonical-ownership-and-refactoring-plan.md) - Canonical ownership
- `topology/L2-network/networks/` - IP allocations
- `topology/L4-platform/workloads/` - Workload IPs
- `topology/L5-application/services/` - Service configs
