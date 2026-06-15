# AI Rule Pack: Topology Model

> **Version:** 1.0 | **Updated:** 2026-06-15 | **ADRs:** See `ADR-RULE-MAP.yaml` → `topology-model.source_adr`

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Hierarchy | Class → Object → Instance (never bypass) |
| Source of truth | `topology/topology.yaml`, class-modules/, object-modules/ |
| Generated | Never edit `generated/` to change topology |
| Semantic keys | Use canonical keys from ADR0088 |
| Layers | L0-L7 boundaries explicit, validated by orchestrator |

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

| Layer | Scope | Examples |
|-------|-------|----------|
| L0 | Physical | Hardware, racks, power |
| L1 | Network | VLANs, bridges, IPs |
| L2 | Storage | Disks, volumes, mounts |
| L3 | Compute | VMs, containers, hosts |
| L4 | Platform | Kubernetes, Proxmox |
| L5 | Services | Applications, databases |
| L6 | Observability | Monitoring, logging |
| L7 | Access | Users, permissions |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Edit `generated/` | Changes overwritten on compile | Edit source topology |
| Bypass Class→Object | Breaks inheritance | Follow hierarchy |
| Legacy refs in active | Confuses readiness state | Keep historical separate |
| Non-canonical keys | Breaks semantic contracts | Use ADR0088 registry |

## Validation

```bash
task validate:default
task validate:layers
task inspect:default  # Check topology shape
```
