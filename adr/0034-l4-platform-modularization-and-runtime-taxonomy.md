---
adr: "0034"
layer: "L4"
scope: "modularization"
status: "Proposed"
date: "2026-02-22"
blockers:
  - id: "anchor-normalization"
    phase: 0
    status: "required"
public_api:
  - "lxc[].id"
  - "vms[].id"
breaking_changes: false
---

# ADR 0034: L4 Platform Modularization (MVP)

- Status: Proposed
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Split `L4_platform` monolith into modular files by existing domains only |
| Blocker | Phase-0 anchor normalization before split |
| Public API | `lxc[].id`, `vms[].id` |
| Breaking changes | None in phase-1 (`L4_platform` keys unchanged) |
| Risk | Low, rollback by restoring monolith and removing modular tree |

## Context

Current `L4_platform` (`topology/L4-platform.yaml`) mixes defaults, profiles, workloads, and templates in one file.
At current scale (2 LXC, 0 VM, 5 templates), changes already create unnecessary review noise.

Key constraint:

- YAML aliases used in monolith cannot be safely reused across modular files because `!include_dir_sorted` loads files independently (`topology-tools/topology_loader.py`).

Cross-layer contracts:

- Downward (`L4 -> L1/L2/L3`): `device_ref`, `bridge_ref`/`network_ref`, `storage_endpoint_ref`/`data_asset_ref`.
- Upward (`L5/L6/L7 <- L4`): stable workload IDs (`lxc[].id`, `vms[].id`).

## Related ADRs

| ADR | Relationship | Dependency |
|---|---|---|
| [0031](0031-layered-topology-toolchain-contract-alignment.md) | Baseline | Layered toolchain contract |
| [0032](0032-l3-data-modularization-and-layer-contracts.md) | Pattern source | L3 modularization approach |
| [0033](0033-toolchain-contract-rebaseline-after-modularization.md) | Prerequisite | Deterministic include support and contract tightening |

## Blockers And Prerequisites

### Phase-0 (Before Split)

| Task | Status | Owner |
|---|---|---|
| Normalize anchors in monolithic `L4-platform.yaml` (inline alias-based fields in workloads) | Required | topology-maintainer |
| Verify no behavior changes (`validate` + `regenerate-all` before/after) | Required | topology-maintainer |

### Phase-1 (This ADR)

| Dependency | Status |
|---|---|
| `!include_dir_sorted` loader support | Ready |
| Existing schema keys (`lxc`, `vms`, `resource_profiles`, `templates`) | Ready |
| Cross-layer reference validation on L4 IDs | Ready |

### Deferred

| Feature | Blocker |
|---|---|
| `host_operating_systems` domain | Schema and validators not implemented |
| Container runtime/cluster taxonomy | Schema and generators not implemented |

## Decision

Use MVP modularization only for existing, schema-backed L4 domains.

```text
topology/L4-platform/
  defaults.yaml
  resource-profiles/
    profile-*.yaml
  workloads/
    lxc/
      lxc-*.yaml
    vms/
      vm-*.yaml
  templates/
    lxc/
      tpl-lxc-*.yaml
    vms/
      tpl-vm-*.yaml
```

No provider/node deep nesting in phase-1.

Thresholds for introducing deeper grouping:

| Trigger | Action |
|---|---|
| `workloads/<type>/` grows beyond ~12 files | Introduce additional grouping |
| More than 2 placement domains active | Introduce grouping by placement |

Rationale: around 10-15 peer entries remain quickly scannable in common CLI views; after that grouping helps navigation.

### Composition Root

```yaml
_defaults: !include L4-platform/defaults.yaml
resource_profiles: !include_dir_sorted L4-platform/resource-profiles
lxc: !include_dir_sorted L4-platform/workloads/lxc
vms: !include_dir_sorted L4-platform/workloads/vms
templates:
  lxc: !include_dir_sorted L4-platform/templates/lxc
  vms: !include_dir_sorted L4-platform/templates/vms
```

Note: `_defaults` is reference/documentation only after phase-0 normalization; modular workloads must not use YAML aliases.

## Contracts

### Public API

| ID | Visibility | Stability | Consumers |
|---|---|---|---|
| `lxc[].id` | Public | Stable `v1` | L5, L6, L7 |
| `vms[].id` | Public | Stable `v1` | L5, L6, L7 |
| `_defaults` | Internal | Mutable | L4 only |
| `resource_profiles` | Internal | Mutable | L4 only |
| `templates.*` | Internal | Mutable | L4 only |

Evolution rule: breaking ID change requires new ADR plus at least one deprecation cycle.

### Naming

Common naming/discovery conventions are centralized in `topology/MODULAR-GUIDE.md` (`Naming conventions`, `Discovery contract`).
L4-specific ID families: `lxc-*`, `vm-*`, `profile-*`, `tpl-lxc-*`, `tpl-vm-*`.

## Migration

### Anchor Strategy

1. In monolithic L4, replace alias-based workload fields with explicit values.
2. Validate and regenerate to confirm no behavioral diffs.
3. Split workloads/profiles/templates into modular files.
4. Keep `_defaults` as reference only; disallow aliases in modular workload files.

### Toolchain Impact

| Component | Impact | Action |
|---|---|---|
| Schema | None | Keep existing keys |
| `terraform/proxmox/generator.py` | None | Input keys unchanged |
| `docs/generator.py` | None | Input keys unchanged |
| Validators | Minor | Enforce L4 include contract; detect aliases in workloads |
| `topology/MODULAR-GUIDE.md` | Minor | Remove L4 from single-file list; add modular paths |

### Verification Checklist

- [ ] `python topology-tools/validate-topology.py --strict` passes
- [ ] `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate` passes
- [ ] Generated infra outputs (`terraform`, `terraform-mikrotik`, `ansible`) match before/after split
- [ ] No YAML aliases under `topology/L4-platform/workloads/**/*.yaml`
- [ ] L5/L6/L7 references to `lxc[].id` and `vms[].id` remain valid

### Rollback

```powershell
git restore topology/L4-platform.yaml
Remove-Item -Recurse -Force topology/L4-platform
python topology-tools/validate-topology.py --strict
python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate
```

## Consequences

Benefits:

- Smaller, localized diffs for L4 changes.
- Lower cognitive load via one-object-per-file workload modules.
- No phase-1 schema churn.

Trade-offs:

- File count increases from 1 monolith to about 10-11 files at current scale.
- Include contract and alias guardrails become validator responsibilities.

Success metrics:

| Metric | Target |
|---|---|
| Files touched for new LXC in L4 | 1-4 |
| Additional L3 files touched for new LXC data placement | 0-2 |
| Median workload-only diff size | < 60 changed lines |
| Behavioral diff after phase-1 split | 0 in infra outputs |

## Ownership

| Role | Party |
|---|---|
| Responsible | topology maintainer |
| Accountable | architecture owner |
| Consulted | service owners |
| Informed | operations owner |

## References

- `topology/L4-platform.yaml`
- `topology/MODULAR-GUIDE.md`
- `topology-tools/topology_loader.py`
- `topology-tools/validate-topology.py`
- `topology-tools/scripts/validators/checks/references.py`
- `topology-tools/scripts/generators/terraform/proxmox/generator.py`
- [0031](0031-layered-topology-toolchain-contract-alignment.md)
- [0032](0032-l3-data-modularization-and-layer-contracts.md)
- [0033](0033-toolchain-contract-rebaseline-after-modularization.md)
