# ADR 0034: L4 Platform Modularization and Runtime Taxonomy

- Status: Proposed
- Date: 2026-02-22

## Context

`L4_platform` is currently a monolithic file (`topology/L4-platform.yaml`) that combines:

1. Defaults and anchors.
2. Resource profiles.
3. VM and LXC runtime instances.
4. Template catalog.

After L1/L2/L3 modularization, L4 remains the largest unsplit runtime layer and now carries growing responsibilities:

1. Hypervisor workloads (VM/LXC).
2. Containerized runtime platforms (Docker/Podman).
3. Orchestrated platforms (Kubernetes/OpenShift).
4. Host OS state for L1 devices (planned/active lifecycle).

This increases cognitive load and creates large diffs for small changes.

Cross-layer analysis:

- Downward (`L4 -> L1/L2/L3`):
  - `device_ref` to L1 host inventory.
  - `bridge_ref`, `network_ref`, `trust_zone_ref` to L2 network model.
  - `storage_endpoint_ref` and `data_asset_ref` bindings to L3 contracts.
- Upward (`L5/L6/L7 <- L4`):
  - L5 runtime targets (`lxc_ref`/`vm_ref`) depend on stable L4 IDs.
  - L6 healthchecks depend on L4 workload IDs (`lxc_ref`).
  - L7 backup/ops flows depend on L4 workload IDs and placement semantics.

L4 therefore requires modularization by runtime domain, while preserving stable IDs for upper layers.

## Alternatives Considered

### A. Keep monolithic `topology/L4-platform.yaml`

Rejected:

- high review noise,
- weak ownership boundaries,
- poor scalability with container/orchestrator expansion.

### B. Split only by host (`by-node`) without domain boundaries

Rejected:

- duplicates shared concerns (profiles/templates),
- weak discoverability for platform-wide contracts,
- harder validation of domain-specific invariants.

### C. Selected: domain-first modularization with optional host partitioning

Selected:

- clear bounded contexts in L4,
- stable contracts for upper layers,
- scalable extension to Docker/OpenShift and host OS lifecycle.

## Decision

Adopt modular L4 structure with domain-based composition and deterministic auto-discovery for order-insensitive domains.

Canonical structure:

```text
topology/L4-platform/
  defaults/
    defaults.yaml
  resource-profiles/
    profile-*.yaml
  templates/
    lxc/
      tpl-lxc-*.yaml
    vms/
      tpl-vm-*.yaml
  workloads/
    lxc/
      owned/proxmox/<node-id>/lxc-*.yaml
      provider/<provider>/<region>/lxc-*.yaml
    vms/
      owned/proxmox/<node-id>/vm-*.yaml
      provider/<provider>/<region>/vm-*.yaml
  host-operating-systems/
    owned/hos-*.yaml
    provider/hos-*.yaml
  container-platforms/
    runtimes/
      rt-*.yaml
    clusters/
      cluster-*.yaml
    nodes/
      cnode-*.yaml
    namespaces/
      ns-*.yaml
```

`topology/L4-platform.yaml` becomes composition root:

1. `_defaults: !include L4-platform/defaults/defaults.yaml`
2. `resource_profiles: !include_dir_sorted L4-platform/resource-profiles`
3. `lxc: !include_dir_sorted L4-platform/workloads/lxc`
4. `vms: !include_dir_sorted L4-platform/workloads/vms`
5. `templates.lxc: !include_dir_sorted L4-platform/templates/lxc`
6. `templates.vms: !include_dir_sorted L4-platform/templates/vms`
7. New domains (schema rollout dependent):
   - `host_operating_systems: !include_dir_sorted L4-platform/host-operating-systems`
   - `container_runtimes: !include_dir_sorted L4-platform/container-platforms/runtimes`
   - `container_clusters: !include_dir_sorted L4-platform/container-platforms/clusters`
   - `container_nodes: !include_dir_sorted L4-platform/container-platforms/nodes`
   - `platform_namespaces: !include_dir_sorted L4-platform/container-platforms/namespaces`

### L4 Responsibility Contract

L4 owns runtime substrate and placement only:

1. Workload instances and host bindings.
2. Runtime platform inventory (VM/LXC/container runtimes/clusters).
3. Host OS lifecycle state.
4. Resource/profile/template policy.

L4 does not own:

1. Service semantics and endpoint behavior (L5).
2. Alerting/monitoring policy semantics (L6).
3. Backup/runbook/workflow policy semantics (L7).

### Naming Contract

1. Directories: `kebab-case`.
2. YAML keys: `snake_case`.
3. IDs:
   - `vm-*`, `lxc-*`, `profile-*`, `tpl-*` (existing),
   - `hos-*` for host OS entries,
   - `rt-*`, `cluster-*`, `cnode-*`, `ns-*` for container platform domains.

### Extension Patterns

1. Add new Proxmox node:
   - add L1 device/media,
   - add L4 workloads under `workloads/*/owned/proxmox/<node-id>/`,
   - optionally add host OS entry in `host-operating-systems/owned/`.
2. Add Docker host:
   - add L1 device,
   - add `container-platforms/runtimes/rt-*.yaml`,
   - bind L5 runtime targets to `rt-*` (migration phase).
3. Add OpenShift cluster:
   - add `container_clusters`, `container_nodes`, `platform_namespaces`,
   - keep service semantics in L5.

### Validator and Governance Requirements

1. Add L4 include-contract checks (required `!include_dir_sorted` lines).
2. Add duplicate ID checks by L4 domain.
3. Add filename==id lint for new one-object-per-file domains.
4. Keep strict mode as default.

## Consequences

Benefits:

- Smaller, localized diffs for L4 changes.
- Clear separation between runtime substrate and service semantics.
- Scalable path for Docker/OpenShift without overloading L5.
- Lower cognitive load via domain-oriented navigation.

Trade-offs:

- More files and stronger validator contracts.
- Schema and generator updates required for new container/host-OS domains.
- Transition period where old and new runtime targeting may coexist.

Migration impact:

1. Phase 1: non-functional L4 split of existing domains (`resource_profiles`, `lxc`, `vms`, `templates`).
2. Phase 2: introduce `host_operating_systems` domain and migrate planned host OS state from L1.
3. Phase 3: introduce `container-platforms/*` domains and runtime-target evolution for L5.
4. Phase 4: enforce strict validator contracts and remove legacy compatibility paths.

Success metrics:

1. Adding one LXC/VM changes at most 1-2 files in L4 modules.
2. Median diff size for runtime instance changes stays under 60 lines.
3. Zero behavioral diffs in generated outputs after phase-1 split.
4. No manual `_index.yaml` in migrated L4 order-insensitive domains.

## References

- Current monolith: `topology/L4-platform.yaml`
- Layer contracts and storage/platform context:
  - [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md)
  - [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
  - [0032](0032-l3-data-modularization-and-layer-contracts.md)
  - [0033](0033-toolchain-contract-rebaseline-after-modularization.md)
- Related toolchain alignment:
  - [0031](0031-layered-topology-toolchain-contract-alignment.md)
- Validators/generators:
  - `topology-tools/validate-topology.py`
  - `topology-tools/scripts/validators/checks/references.py`
  - `topology-tools/scripts/generators/terraform/proxmox/generator.py`
  - `topology-tools/generate-ansible-inventory.py`
