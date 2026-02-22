---
adr: "0032"
layer: "L3"
scope: "modularization"
status: "Proposed"
date: "2026-02-22"
public_api:
  - "storage_endpoints[]"
  - "data_assets[]"
breaking_changes: false
---

# ADR 0032: L3 Data Modularization and Layer Contracts

- Status: Proposed
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Split monolithic `L3_data` into domain modules |
| Public API | `storage_endpoints[]`, `data_assets[]` only |
| Internal chain | `partitions`, `volume_groups`, `logical_volumes`, `filesystems`, `mount_points` |
| Breaking changes | None in phase-1 |
| Main risk | Upper layers referencing internal chain IDs |

## Context

`L3_data` was maintained as one file (`topology/L3-data.yaml`) while neighboring layers were already modularized.
L3 combines two different concern types:

1. Internal storage implementation chain.
2. Public cross-layer storage contract.

Growth drivers (NAS, new Proxmox nodes, provider nodes) increase review noise and coupling risk when internal and public entities share one monolith.

Cross-layer contracts:

- Downward (`L3 -> L1`): `media_attachment_ref`, `device_ref`.
- Upward (`L4/L5/L7 <- L3`): upper layers should consume only `storage_endpoints` and `data_assets`.

## Alternatives Considered

| Option | Decision | Reason |
|---|---|---|
| Keep monolithic `L3-data.yaml` | Rejected | Poor scalability and large unrelated diffs |
| Per-device modularization | Rejected | Duplicates shared storage concepts |
| Flat split in one folder | Rejected | Weak navigation and ownership boundaries |
| Per-entity modularization (selected) | Selected | Clear internal/public boundary and consistent validation |

## Decision

Use per-entity modularization with explicit internal/public L3 boundary.

```text
topology/L3-data/
  partitions/
  volume-groups/
  logical-volumes/
  filesystems/
  mount-points/
  storage-endpoints/
    owned/
    provider/
  data-assets/
    owned/
    provider/
```

Composition root (`topology/L3-data.yaml`) uses deterministic include discovery per domain.

## Contracts

### Public API

| Entity | Visibility | Stability | Consumers |
|---|---|---|---|
| `storage_endpoints[]` | Public | Stable `v1` | L4, L7 |
| `data_assets[]` | Public | Stable `v1` | L4, L5, L7 |
| `partitions[]` | Internal | Mutable | L3 only |
| `volume_groups[]` | Internal | Mutable | L3 only |
| `logical_volumes[]` | Internal | Mutable | L3 only |
| `filesystems[]` | Internal | Mutable | L3 only |
| `mount_points[]` | Internal | Mutable | L3 only |

Evolution rule: breaking API changes require new ADR and deprecation cycle.

### Boundary Rules

| Rule | Requirement |
|---|---|
| Downward refs | L3 may reference L1 only |
| Upward refs | L3 must not reference L4+ |
| Upper-layer refs | L4/L5/L7 must not reference internal L3 chain IDs |
| Ownership split | `owned/` and `provider/` are navigation/review partitions |

### Naming

Shared naming/discovery conventions are centralized in `topology/MODULAR-GUIDE.md` (`Naming conventions`, `Discovery contract`).
L3-specific ID families:

- `se-<scope>-<node>-<purpose>`
- `data-<scope>-<workload>-<purpose>`

## Migration

### Rollout

1. Non-functional split first (same IDs/content, new file layout).
2. Keep generated behavior unchanged.
3. Enforce stricter semantic checks after split is stable.

### Extension Patterns

| Scenario | L3 change pattern |
|---|---|
| Add NAS | Add endpoints/assets under `owned/`; keep internal chain local to new storage path |
| Add Proxmox node | Add node-specific chain modules and expose new endpoints/assets |
| Add cloud node | Add entries under `provider/` with no changes to existing `owned/` modules |

### Toolchain Impact

| Component | Impact | Action |
|---|---|---|
| Schema | None for phase-1 shape | Keep keys unchanged |
| Loader | Required | Deterministic directory include support |
| Validators | Required | Duplicate ID checks, include contract checks, cross-layer boundary checks |
| Generators | None/low | Consume merged topology as before |

### Verification Checklist

- [ ] `python topology-tools/validate-topology.py --strict` passes
- [ ] `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate` passes
- [ ] No manual `_index.yaml` in autodiscovery L3 domains
- [ ] Upper layers reference only `storage_endpoints` / `data_assets`

### Rollback

```powershell
git restore topology/L3-data.yaml
Remove-Item -Recurse -Force topology/L3-data
python topology-tools/validate-topology.py --strict
python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate
```

## Blockers And Prerequisites

| Item | Status | Note |
|---|---|---|
| Deterministic include support | Ready | Required for modular loading |
| Duplicate-ID checks in L3 domains | Ready | Validator-enforced |
| Detect upper-layer references to internal L3 IDs | Required for final strict acceptance | Must be enforced in validators |
| Strict `L7 storage_ref -> storage_endpoints` resolution | Required for final strict acceptance | Blocker if missing |

## Consequences

Benefits:

- Smaller scoped diffs.
- Clear internal/public L3 contract.
- Better scalability for heterogeneous storage growth.

Trade-offs:

- More files than monolith.
- Stronger validator contract and stricter governance.

Success metrics:

| Metric | Target |
|---|---|
| L3 entities loaded via modular includes | 100% |
| Behavioral diffs in infra outputs after phase-1 split | 0 |
| Files touched for adding storage endpoint | 1-2 in L3 |
| Median diff size for endpoint addition | < 50 lines |

## Ownership

| Role | Party |
|---|---|
| Responsible | topology maintainers |
| Accountable | architecture owner |
| Consulted | generator/validator maintainers |
| Informed | service/platform owners consuming L3 API |

## References

- `topology/L3-data.yaml`
- `topology/MODULAR-GUIDE.md`
- `docs/architecture/L3-DATA-MODULARIZATION-PLAN.md`
- `topology-tools/schemas/topology-v4-schema.json`
- `topology-tools/scripts/validators/checks/storage.py`
- [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md)
- [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
- [0031](0031-layered-topology-toolchain-contract-alignment.md)
