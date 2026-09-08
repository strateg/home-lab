---
"@pack": topology-model
"@version": 1.1
"@tokens": ~500
"@adr": [0062, 0071, 0088, 0107]
---

# AI Rule Pack: Topology Model

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Hierarchy | Class → Object → Instance (never bypass) |
| Source of truth | `topology/topology.yaml`, class-modules/, object-modules/ |
| Generated | Never edit `generated/` to change topology |
| Semantic keys | Use canonical keys from ADR0088 |
| Layers | L0-L7 boundaries explicit, validated by orchestrator |
| Host placement | Use `@on:host.X` for host defaults (ADR 0107) |

## Load When

- `topology/**`
- `projects/*/topology/**`
- Class, object, instance, module-index, or layer-contract files

## Source of Truth Hierarchy

| Level | Location | Purpose |
|-------|----------|---------|
| Entry point | `topology/topology.yaml` | Main topology definition |
| Classes | `topology/class-modules/` | Reusable templates |
| Objects | `topology/object-modules/` | Concrete configurations |
| Instances | `projects/<project>/topology/instances/` | Project-specific deployments |

## Layer Boundaries (L0-L7)

<!-- GENERATED:LAYER_TABLE:START -->

| Layer | Scope | Examples |
|-------|-------|----------|
| L0 | Meta | Global defaults, version, policies |
| L1 | Foundation | Devices, routers, power, firmware, physical links |
| L2 | Network | Bridges, VLANs, firewall, QoS, tunnels |
| L3 | Storage | Storage pools, volumes, data assets |
| L4 | Platform | VMs, LXC, containers, workloads |
| L5 | Application | Services, applications, DNS, VPN |
| L6 | Observability | Healthchecks, alerts, dashboards |
| L7 | Operations | Backups, workflows, policies, schedules |

<!-- GENERATED:LAYER_TABLE:END -->

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Edit `generated/` | Changes overwritten on compile | Edit source topology |
| Bypass Class→Object | Breaks inheritance | Follow hierarchy |
| Legacy refs in active | Confuses readiness state | Keep historical separate |
| Non-canonical keys | Breaks semantic contracts | Use ADR0088 registry |

## Host Placement Defaults (@on Directive)

See **`host-placement.md`** rule pack for detailed guidance. Quick reference:

| Directive | Purpose |
|-----------|---------|
| `@on:host.X` | Inherit X from immediate host_ref |
| `@on:root.X` | Inherit X from physical device |
| `workload_defaults` | Define in host instance, not object |

## Validation

```bash
task validate:default
task validate:layers
task inspect:default  # Check topology shape
```
