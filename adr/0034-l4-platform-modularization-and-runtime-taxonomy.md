# ADR 0034: L4 Platform Modularization (MVP)

- Status: Proposed
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|--------|-------|
| Scope | Split `L4-platform.yaml` (~176 lines) into ~10 modular files |
| Blocker | Phase-0: inline YAML anchors before split |
| Public API | `lxc[].id`, `vms[].id` (stable, consumed by L5/L6/L7) |
| Schema changes | None |
| Risk | Low (git restore rollback) |

## Context

`L4_platform` is monolithic and mixes defaults, profiles, workloads, and templates. Current scale is small (2 LXC, 5 templates), but edits touch unrelated sections.

**Critical constraint:** L4 uses YAML anchors (`*dns_default`, `*lxc_os_default`). The `!include_dir_sorted` loader parses files independently, so cross-file aliases fail. Anchor inlining is a phase-0 blocker.

**Cross-layer dependencies:**

| Direction | References |
|-----------|------------|
| L4 → L1 | `device_ref` |
| L4 → L2 | `bridge_ref`, `network_ref`, `trust_zone_ref` |
| L4 → L3 | `storage_endpoint_ref`, `data_asset_ref` |
| L5/L6/L7 → L4 | `lxc[].id`, `vms[].id` |

## Blockers & Prerequisites

### Phase-0 (before split)

| Task | Status | Notes |
|------|--------|-------|
| Inline all YAML anchors | TODO | Replace `*alias` with explicit values |
| Verify zero-diff regeneration | TODO | Compare outputs before/after |

### Phase-1 (this ADR)

| Dependency | Status |
|------------|--------|
| `!include_dir_sorted` in loader | Ready |
| Schema keys unchanged | Ready |
| Reference validation | Ready |

### Deferred

| Feature | Status |
|---------|--------|
| `host_operating_systems` schema | Not implemented |
| `container_runtimes` schema | Not implemented |

## Decision

### Target Structure

```
topology/L4-platform/
  defaults.yaml           # Reference only (post-migration)
  resource-profiles/
    profile-*.yaml
  templates/
    lxc/tpl-lxc-*.yaml
    vms/tpl-vm-*.yaml
  workloads/
    lxc/lxc-*.yaml
    vms/vm-*.yaml
```

### Composition Root

```yaml
# topology/L4-platform.yaml
_defaults: !include L4-platform/defaults.yaml

resource_profiles: !include_dir_sorted L4-platform/resource-profiles
lxc: !include_dir_sorted L4-platform/workloads/lxc
vms: !include_dir_sorted L4-platform/workloads/vms

templates:
  lxc: !include_dir_sorted L4-platform/templates/lxc
  vms: !include_dir_sorted L4-platform/templates/vms
```

### Scaling Thresholds

| Trigger | Action |
|---------|--------|
| `workloads/<type>/` > 12 files | Add `owned/`/`provider/` subdirs |
| > 2 placement domains | Add per-domain grouping |

Rationale: ~10-15 entries remain scannable in CLI; cognitive benefit from grouping appears after 10-12 peers.

## Contracts

### Public API

| ID Pattern | Visibility | Stability | Consumer |
|------------|------------|-----------|----------|
| `lxc-*` | Public | Stable v1 | L5 `runtime.target_ref`, L6, L7 backup |
| `vm-*` | Public | Stable v1 | L5, L6, L7 |
| `profile-*` | Internal | Mutable | L4 only |
| `tpl-*` | Internal | Mutable | L4 only |
| `_defaults` | Internal | Mutable | L4 only |

**Evolution:** Breaking ID change requires new ADR + one deprecation cycle.

### Naming

| Scope | Convention | Example |
|-------|------------|---------|
| Directories | `kebab-case` | `resource-profiles/` |
| YAML keys | `snake_case` | `resource_profiles:` |
| Workload IDs | `lxc-*`, `vm-*` | `lxc-postgresql` |
| Profile IDs | `profile-*` | `profile-db-small` |
| Template IDs | `tpl-lxc-*`, `tpl-vm-*` | `tpl-lxc-debian` |

### Responsibility Boundary

| L4 Owns | L4 Does NOT Own |
|---------|-----------------|
| Workload instances & placement | Service semantics (L5) |
| Templates & provisioning | Monitoring policy (L6) |
| Resource profiles | Backup/runbook policy (L7) |

## Migration

### Phase-0: Anchor Normalization

1. Replace all `*alias` references with inline values in `L4-platform.yaml`
2. Run `regenerate-all.py`, verify zero diff
3. Commit normalized monolith

### Phase-1: Split

1. Create `topology/L4-platform/` structure
2. Move objects to per-file modules
3. Convert `L4-platform.yaml` to composition root
4. Run `regenerate-all.py`, verify zero diff
5. Add validator guardrail for alias detection in `workloads/`

### Rollback

```bash
git checkout HEAD~1 -- topology/L4-platform.yaml
rm -rf topology/L4-platform/
python topology-tools/validate-topology.py --strict
python topology-tools/regenerate-all.py --strict --skip-mermaid-validate
```

## Toolchain Impact

| Component | Impact | Action Required |
|-----------|--------|-----------------|
| Schema | None | Keys unchanged |
| `proxmox/generator.py` | None | Reads same structure |
| `docs/generator.py` | None | Reads same structure |
| Validators | Minor | Add alias detection guardrail |
| `MODULAR-GUIDE.md` | Update | Move L4 to modularized list |

## Consequences

### Benefits

- Smaller, localized diffs (one-object-per-file)
- Reduced merge conflicts
- No schema changes required

### Trade-offs

- File count: 1 → ~10
- Include contracts become validator-enforced

### Success Metrics

| Metric | Target |
|--------|--------|
| Files changed per new LXC | 1-4 (workload + optional profile/template) |
| Additional L3 files | 0-2 (if new data assets) |
| Median diff size | < 60 lines |
| Behavioral diff after split | Zero |

## Ownership (RACI)

| Role | Party |
|------|-------|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | L5 service owners |
| Informed | Operations owner |

## Deferred

| Extension | Trigger |
|-----------|---------|
| `host_operating_systems` | When OS lifecycle objects exist |
| `container_runtimes` | When first runtime/cluster object exists |
| L5 modularization | Separate ADR after L5 scale threshold |

## References

- Source: `topology/L4-platform.yaml`
- Guide: `topology/MODULAR-GUIDE.md`
- Loader: `topology-tools/topology_loader.py`
- Validator: `topology-tools/scripts/validators/checks/references.py`
- Generator: `topology-tools/scripts/generators/terraform/proxmox/generator.py`
- Related: [0031], [0032], [0033]

## Alternatives Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| A. Keep monolith | Rejected | Poor review ergonomics at scale |
| B. Deep hierarchy now | Rejected | Overfits future, unnecessary depth |
| C. Full taxonomy now | Rejected | YAGNI, objects don't exist |
| **D. MVP split** | **Selected** | Minimal change, immediate benefit |
