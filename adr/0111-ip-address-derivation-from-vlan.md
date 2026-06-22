# ADR 0111: IP Address Derivation from VLAN Instances

- Status: Implemented
- Date: 2026-06-22
- Related: ADR-0110 (Security Matrix), ADR-0044 (Instance References), ADR-0109 (Network Segmentation)
- Implementation: [Network Security Implementation Plan](../docs/plans/network-security-implementation-plan.md)

## Context

IP addresses in workload instances (LXC, VM, container) are currently hardcoded:

```yaml
# Current pattern (problematic)
network:
  ip: 10.0.30.10/24
  gateway: 10.0.30.1
```

**Problems identified:**

| ID | Problem | Impact |
|----|---------|--------|
| P1 | Subnet change requires editing every workload file | High maintenance burden |
| P2 | No validation of IP within VLAN range | Silent misconfiguration |
| P3 | Gateway hardcoded separately from VLAN | Drift risk |
| P4 | Host number duplicates not detected | IP conflicts |
| P5 | VLAN CIDR is source of truth but not referenced | Inconsistency |

**Current state (servers zone):**

| Workload | Hardcoded IP | Should Reference |
|----------|--------------|------------------|
| lxc-postgresql | 10.0.30.10/24 | inst.vlan.servers + host: 10 |
| lxc-redis | 10.0.30.20/24 | inst.vlan.servers + host: 20 |
| lxc-nextcloud | 10.0.30.30/24 | inst.vlan.servers + host: 30 |
| lxc-gitea | 10.0.30.40/24 | inst.vlan.servers + host: 40 |
| lxc-grafana | 10.0.30.60/24 | inst.vlan.servers + host: 60 |
| lxc-prometheus | 10.0.30.70/24 | inst.vlan.servers + host: 70 |
| lxc-nginx-proxy | 10.0.30.80/24 | inst.vlan.servers + host: 80 |
| lxc-docker | 10.0.30.90/24 | inst.vlan.servers + host: 90 |
| lxc-homeassistant | 10.0.30.100/24 | inst.vlan.servers + host: 100 |

## Decision

### 1. IP Derivation Pattern

IP addresses are derived from `vlan_ref + host` at compile time. The VLAN instance
CIDR is the single source of truth.

**New pattern:**

```yaml
# ADR-0111 canonical pattern
network:
  vlan_ref: inst.vlan.servers
  host: 10
# Compiler resolves: inst.vlan.servers.cidr = 10.0.30.0/24 → 10.0.30.10/24
# Gateway derived: 10.0.30.1 (always host 1)
```

**Resolution algorithm (compiler):**

```
1. Resolve vlan_ref → VLAN instance
2. Read instance.cidr (e.g., "10.0.30.0/24")
3. Parse CIDR: network = "10.0.30.0", prefix = 24
4. Extract network base: "10.0.30"
5. Compose host IP: base + "." + host = "10.0.30.10"
6. Append prefix: "10.0.30.10/24"
7. Gateway = base + ".1" (convention: host 1 = gateway)
```

### 2. Compiled Output

The compiler produces resolved IP addresses in `compiled.json`:

```json
{
  "instances": {
    "inst.lxc.postgresql": {
      "network": {
        "vlan_ref": "inst.vlan.servers",
        "host": 10,
        "_resolved_ip": "10.0.30.10/24",
        "_resolved_gateway": "10.0.30.1"
      }
    }
  }
}
```

Generators consume `_resolved_ip` and `_resolved_gateway` for output artifacts.

### 3. Backward Compatibility

Both patterns are supported during migration:

| Pattern | Status | Behavior |
|---------|--------|----------|
| `{vlan_ref, host}` | Preferred | Compiler derives IP |
| `{ip, gateway}` | Deprecated | Warning W7864 emitted |
| Mixed | Error | E7865: Cannot mix patterns |

### 4. Centralization Guarantee

To renumber the entire servers subnet from `10.0.30.0/24` to `10.0.50.0/24`:

1. Change **one field** in `inst.vlan.servers.cidr`
2. Run `task build`
3. All derived host IPs follow automatically

**Before:**
```yaml
# inst.vlan.servers.yaml
cidr: 10.0.30.0/24
```

**After:**
```yaml
# inst.vlan.servers.yaml
cidr: 10.0.50.0/24
```

**Result:** All 9 LXC containers get new IPs (10.0.50.10, 10.0.50.20, ...) without
editing any workload files.

### 5. Host Number Conventions

| Host Range | Purpose | Example |
|------------|---------|---------|
| 1 | Gateway (reserved) | 10.0.30.1 |
| 2-9 | Infrastructure | srv-orangepi5 = 5 |
| 10-99 | Static workloads | lxc-postgresql = 10 |
| 100-199 | DHCP pool | Dynamic assignment |
| 200-254 | Reserved | Future use |

### 6. Validation Rules

| Code | Severity | Rule |
|------|----------|------|
| E7861 | Error | Duplicate host number within same vlan_ref |
| E7862 | Error | host: 1 is reserved for VLAN gateway |
| E7863 | Error | host number exceeds VLAN CIDR host range |
| W7864 | Warning | Workload has hardcoded IP instead of vlan_ref + host |
| E7865 | Error | Cannot mix vlan_ref/host with hardcoded ip/gateway |

### 7. Servers Zone Inventory

| Host | Workload | Derived IP | Purpose |
|------|----------|------------|---------|
| 1 | gateway (vmbr0) | 10.0.30.1 | VLAN gateway |
| 5 | srv-orangepi5 | 10.0.30.5 | ARM SBC |
| 10 | lxc-postgresql | 10.0.30.10 | Database |
| 20 | lxc-redis | 10.0.30.20 | Cache |
| 30 | lxc-nextcloud | 10.0.30.30 | File sync |
| 40 | lxc-gitea | 10.0.30.40 | Git server |
| 60 | lxc-grafana | 10.0.30.60 | Dashboards |
| 70 | lxc-prometheus | 10.0.30.70 | Monitoring |
| 80 | lxc-nginx-proxy | 10.0.30.80 | Reverse proxy |
| 90 | lxc-docker | 10.0.30.90 | Container host |
| 100 | lxc-homeassistant | 10.0.30.100 | Home automation |

## Implementation

### Compiler Plugin

```python
# topology-tools/plugins/compilers/ip_derivation_compiler.py

class IpDerivationCompiler(CompilerPlugin):
    """Derives IP addresses from vlan_ref + host pattern."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        host_registry: dict[str, dict[int, str]] = {}  # vlan_ref -> {host -> instance_id}

        for instance_id, data in ctx.instances.items():
            network = data.get("network", {})

            if "vlan_ref" in network and "host" in network:
                vlan_ref = network["vlan_ref"]
                host = network["host"]

                # Validate host not duplicate
                if vlan_ref not in host_registry:
                    host_registry[vlan_ref] = {}

                if host in host_registry[vlan_ref]:
                    diagnostics.append(self.emit_diagnostic(
                        code="E7861",
                        severity="error",
                        message=f"Duplicate host {host} in {vlan_ref}: {instance_id} and {host_registry[vlan_ref][host]}"
                    ))
                else:
                    host_registry[vlan_ref][host] = instance_id

                # Validate host != 1 (gateway)
                if host == 1:
                    diagnostics.append(self.emit_diagnostic(
                        code="E7862",
                        severity="error",
                        message=f"host: 1 reserved for gateway in {instance_id}"
                    ))

                # Resolve IP
                vlan_data = ctx.instances.get(vlan_ref, {})
                cidr = vlan_data.get("cidr")
                if cidr:
                    resolved_ip, resolved_gw = self._resolve_ip(cidr, host)
                    network["_resolved_ip"] = resolved_ip
                    network["_resolved_gateway"] = resolved_gw

            elif "ip" in network:
                # Deprecated pattern
                diagnostics.append(self.emit_diagnostic(
                    code="W7864",
                    severity="warning",
                    message=f"Hardcoded IP in {instance_id}, migrate to vlan_ref + host"
                ))

        return self.make_result(diagnostics=diagnostics)

    def _resolve_ip(self, cidr: str, host: int) -> tuple[str, str]:
        network_part, prefix = cidr.rsplit("/", 1)
        octets = network_part.rsplit(".", 1)
        base = octets[0]
        resolved_ip = f"{base}.{host}/{prefix}"
        resolved_gw = f"{base}.1"
        return resolved_ip, resolved_gw
```

### Migration Script

```bash
#!/bin/bash
# migrate-ip-derivation.sh

for file in projects/home-lab/topology/instances/lxc/*.yaml; do
  # Extract current IP pattern and convert to vlan_ref + host
  # This is a one-time migration
  echo "Migrating: $file"
done
```

## Consequences

### Benefits

- **Single source of truth** — VLAN CIDR defines all addresses
- **Subnet changes are trivial** — edit one file, rebuild
- **Host collision detection** — E7861 catches duplicates early
- **Gateway consistency** — always derived from CIDR
- **Audit-friendly** — host inventory in compiled output

### Trade-offs

- **Migration effort** — 9+ files need updating
- **Learning curve** — new pattern for instance authors
- **Compiler dependency** — raw IP no longer visible in source

### Migration Path

| Phase | Action | Files |
|-------|--------|-------|
| 1 | Add compiler plugin | 1 |
| 2 | Add validators (E7861-E7865) | 1 |
| 3 | Migrate LXC instances | 9 |
| 4 | Migrate server instances | 2 |
| 5 | Remove W7864 warnings | — |
| 6 | Update ADR status | 1 |

## References

- ADR-0044: Instance References and Resolution
- ADR-0110: Universal Network Zone and VLAN Configuration (Security Matrix)
- VLAN instances: `projects/home-lab/topology/instances/network/inst.vlan.*.yaml`
