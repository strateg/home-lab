# Modular Topology Guide (v4)

This guide defines how to keep topology files small, readable, and safe to evolve.

## Goals

- Keep `topology.yaml` as the single composition root.
- Split large layers into stable modules.
- Enforce strict downward dependencies (`L(N)` may reference only `L<=N`).
- Make adding new hardware a small, local change.
- Keep **underlay vs overlay** explicit:
  - L1 = data links (`data_links`) and power links (`power_links`)
  - L2 = virtual segmentation (`network_plane`, `segmentation_type`, `transport`, `volatility`)

## Dependency Rules

| Layer | Can reference |
|-------|---------------|
| L0 Meta | L0 only (plus global default refs to canonical IDs in lower layers) |
| L1 Foundation | L0 |
| L2 Network | L0, L1 |
| L3 Data | L0, L1, L2 |
| L4 Platform | L0..L3 |
| L5 Application | L0..L4 |
| L6 Observability | L0..L5 |
| L7 Operations | L0..L6 |

Rules:
- Use `*_ref` fields only (no implicit links in free text).
- Do not introduce upward references.
- Keep IDs stable after first release.
- Every architecture decision must be recorded as a new ADR file in `adr/`.

## Layer Purpose, Responsibility, and Example (ADR-backed)

This section is based on active architecture decisions and implemented commits.
Primary contract sources:

- Accepted ADRs: `adr/0001-power-policy-layer-boundary.md`, `adr/0002-separate-data-and-power-links-in-l1.md`, `adr/0003-data-links-naming-and-power-constraints.md`, `adr/0004-l2-firewall-policy-references-and-validation.md`, `adr/0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md`, `adr/0028-topology-tools-architecture-consolidation.md`, `adr/0029-storage-taxonomy-and-layer-boundary-consolidation.md`
- Proposed but already influencing authoring and review: `adr/0031-layered-topology-toolchain-contract-alignment.md`, `adr/0032-l3-data-modularization-and-layer-contracts.md`, `adr/0033-toolchain-contract-rebaseline-after-modularization.md`, `adr/0034-l4-platform-modularization-and-runtime-taxonomy.md`
- Key implementation commits: `6a61f32`, `01e1aeb`, `f5a2789`, `f3a005e`, `febe840`, `fd46cff`

Use this section as the practical layer contract for day-to-day modeling.

### L0 Meta

Purpose:
- Define the global architecture envelope: versioning, governance metadata, and default policy refs.

Canonical ownership:
- `version`
- `metadata`
- `defaults.refs`
- `security_policy`

Public contract for other layers:
- `defaults.refs.security_policy_ref`
- `defaults.refs.network_manager_device_ref`

Boundary rules:
- L0 is not an inventory or runtime layer.
- L0 does not model devices, networks, storage internals, workloads, services, or operations.
- Cross-layer IDs in `defaults.refs` are allowed as global defaults, not as ownership transfer.

Example (`topology/L0-meta.yaml`):

```yaml
version: 4.0.0
defaults:
  refs:
    security_policy_ref: sec-baseline
    network_manager_device_ref: mikrotik-chateau
```

### L1 Foundation

Purpose:
- Model physical and provider underlay facts: what exists physically, where it is, and how it is physically connected.

Canonical ownership:
- Locations and device inventory.
- Device taxonomy (`class`, `substrate`, `access`) and hardware capabilities.
- Compute host architecture taxonomy (`specs.cpu.architecture`) used as compile/runtime target metadata.
- Physical storage capability (`specs.storage_slots`).
- Mutable media state (`media_registry`, `media_attachments`).
- Physical connectivity (`data_links`, `power_links`).

Public contract for upper layers:
- Stable infrastructure IDs (`device_ref`, `slot_ref`, `media_ref`, `link IDs`) referenced by L2/L3/L4/L6/L7.

Boundary rules:
- ADR 0001, ADR 0002, ADR 0003: L1 stores physical power and data topology only; outage/power orchestration belongs to L7.
- ADR 0029: L1 is physical-only for storage; no runtime logical mapping (`/dev/*`, mount plan, filesystem plan) in L1.
- Workloads are never authored in L1; VM/LXC belong to L4.

Validation-critical invariants:
- `data_links` and `power_links` are separate first-class domains.
- PoE is modeled as two links: one data link + one power link with `data_link_ref`.
- `upstream_power_ref` targets existing `class: power` devices.
- Every `class: compute` device must declare `specs.cpu.architecture`.
- Preferred architecture values are `x86_64` and `arm64`; aliases (`amd64`, `aarch64`) are allowed for compatibility.

Architecture taxonomy:

| Canonical | Common aliases | Typical substrate |
|---|---|---|
| `x86_64` | `amd64` | Proxmox and classic server hosts |
| `arm64` | `ARM64`, `aarch64` | SBC and ARM cloud hosts |
| `riscv64` | `RISCV64`, `riscv` | Future RISC-V nodes |
| `i386` | `x86` | Legacy/compatibility workloads |

Example (`topology/L1-foundation/devices/owned/compute/orangepi5.yaml`):

```yaml
id: orangepi5
class: compute
substrate: baremetal-owned
access: local-lan
specs:
  cpu:
    architecture: arm64
  storage_slots:
  - id: slot-m2-0
    bus: m2
```

### L2 Network

Purpose:
- Model logical network overlay and policy over L1 underlay facts.

Canonical ownership:
- `trust_zones`
- `network_profiles`
- `networks`
- `bridges`
- `routing`
- `firewall_templates`, `firewall_policies`
- `qos`, `ipv6`

Public contract for upper layers:
- Network and bridge identifiers consumed by L4/L5/L6 (`network_ref`, `bridge_ref`, `trust_zone_ref`).

Boundary rules:
- L2 references L1 device IDs for management/ownership (`managed_by_ref`) but does not own hardware inventory.
- L2 does not own service/runtime semantics (L5/L4 concern).

Validation-critical invariants:
- Firewall policies are explicit references, not free-text policy names (ADR 0004).
- In profile-driven networks, profile defines baseline and per-network files keep only intentional overrides.
- Trust-zone and VLAN policy is explicit (`vlan_ids`, default zone firewall policy) where declared.

Example (`topology/L2-network/networks/net-servers.yaml`):

```yaml
id: net-servers
cidr: 10.0.30.0/24
trust_zone_ref: servers
managed_by_ref: mikrotik-chateau
profile_ref: prof-virtual-vlan-wired
```

### L3 Data

Purpose:
- Model storage topology and data governance as a layer separate from platform runtime details.

Canonical ownership:
- Internal storage chain: `partitions`, `volume_groups`, `logical_volumes`, `filesystems`, `mount_points`.
- Public storage/data API: `storage_endpoints`, `data_assets`.

Public contract for upper layers:
- Stable `storage_endpoints[]` IDs and `data_assets[]` IDs (ADR 0032 direction, implemented in topology).

Boundary rules:
- ADR 0026 and ADR 0029: L3 separates data semantics from platform placement.
- `data_assets` describe data importance/governance; placement and capacity are modeled in L4 storage volumes.
- Upper layers should not couple to internal L3 chain IDs unless explicitly required by validator contracts.

Validation-critical invariants:
- Storage chain is structurally consistent.
- L3 references downward to L1 storage facts; no upward ownership.
- Deterministic modular loading is canonical for high-churn domains (`!include_dir_sorted`).

Example (`topology/L3-data/storage-endpoints/se-local.yaml`, `topology/L3-data/data-assets/data-nextcloud.yaml`):

```yaml
# storage endpoint
id: se-local
type: dir
mount_point_ref: mnt-gamayun-root

# data asset
id: data-nextcloud
device_ref: orangepi5
```

### L4 Platform

Purpose:
- Model compute/runtime placement and host platform state independently from service business semantics.

Canonical ownership:
- Runtime workload instances (`lxc`, `vms`).
- Placement/resource contracts (`resource_profiles`, templates, storage bindings).
- Host OS inventory objects (`host_operating_systems`) for installation state tracking.

Public contract for upper layers:
- Stable runtime targets (`lxc[].id`, `vms[].id`) consumed by L5/L6/L7.

Boundary rules:
- ADR 0026: app-level configuration should live in L5, not in L4 workload internals.
- L4 owns placement (`device_ref`, `storage_endpoint_ref`, volume sizing), not service intent.
- L4 references downward to L1 (hosts), L2 (network binding), and L3 (storage/data assets).

Validation-critical invariants:
- One-object-per-file structure for workloads/templates/profiles in modular form (ADR 0034 direction, implemented).
- No cross-file YAML anchor dependency in modular workload files.
- Runtime target IDs remain stable because they are consumed cross-layer.
- Host OS architecture must match `L1 specs.cpu.architecture` after alias normalization.
- Canonical stored architecture values should be lowercase (`x86_64`, `arm64`, `riscv64`, `i386`).
- `installation` is optional for `host_type: embedded`, but recommended for `baremetal` and `hypervisor`.

Host OS capability taxonomy:

| Capability | Meaning | Valid host types |
|---|---|---|
| `lxc` | Can run LXC workloads | `hypervisor` |
| `vm` | Can run VM workloads | `hypervisor` |
| `docker` | Docker engine/runtime available | `baremetal`, `hypervisor` |
| `container` | Generic container support | `embedded`, `baremetal`, `hypervisor` |
| `cloudinit` | Supports cloud-init guest bootstrap | `hypervisor`, `baremetal` |
| `baremetal` | Native host service execution (non-containerized) | `baremetal`, `embedded` |

Current maturity note:
- `host_operating_systems` is now authored in topology (e.g., Orange Pi Ubuntu on NVMe) and used as architectural fact tracking.
- Generator/validator deep semantics for host OS lifecycle remain an incremental hardening area.

Example (`topology/L4-platform/host-operating-systems/hos-orangepi5-ubuntu.yaml`, `topology/L4-platform/workloads/lxc/lxc-postgresql.yaml`):

```yaml
# host OS
id: hos-orangepi5-ubuntu
device_ref: orangepi5
distribution: ubuntu
installation:
  media_ref: disk-nvme-main
  slot_ref: slot-m2-0

# workload
id: lxc-postgresql
device_ref: gamayun
resource_profile_ref: profile-db-small
storage:
  rootfs:
    storage_endpoint_ref: se-lvm
```

### L5 Application

Purpose:
- Describe service intent: what runs, where it runs, how it is exposed, and what data it consumes.

Canonical ownership:
- Service catalog and dependencies.
- Service runtime binding (`runtime.type`, `runtime.target_ref`, `network_binding_ref`).
- Service endpoint intent and service-to-data binding (`data_asset_refs`).
- Certificates and DNS service-level declarations.

Public contract for upper layers:
- Service IDs and service dependency graph consumed by observability and operations.

Boundary rules:
- ADR 0026: unified runtime object is canonical; avoid duplicate host-placement fields.
- L5 does not own hardware, bridges, storage internals, or platform resource sizing.

Validation-critical invariants:
- `runtime.target_ref` resolves to valid L4/L1 target by runtime type.
- `data_asset_refs` resolve to L3 `data_assets`.
- Endpoint and runtime fields are normalized for generators (ongoing hardening in ADR 0031 and ADR 0033).

Example (`topology/L5-application/services.yaml`):

```yaml
- id: svc-nextcloud
  type: web-application
  runtime:
    type: docker
    target_ref: orangepi5
    network_binding_ref: net-servers
  data_asset_refs:
  - data-nextcloud
```

### L6 Observability

Purpose:
- Encode detection and notification logic for infrastructure and service health.

Canonical ownership:
- `healthchecks`
- `network_monitoring`
- `alerts`
- `notification_channels`
- `dashboard`

Public contract for upper layers:
- Alerting and monitoring IDs referenced by operational runbooks/escalation.

Boundary rules:
- L6 consumes IDs from L1/L2/L5 but does not own their source-of-truth fields.
- L6 does not model deployment procedures or backup orchestration.

Validation-critical invariants:
- References to devices/services/channels must resolve.
- Trigger semantics and cross-entity reference coverage are being hardened in toolchain phases (ADR 0031 and ADR 0033).

Example (`topology/L6-observability/healthchecks.yaml`, `topology/L6-observability/alerts.yaml`):

```yaml
- id: health-orangepi5
  device_ref: orangepi5
  checks:
  - type: ping
    target: 192.168.88.3

- id: alert-service-down
  trigger:
    condition: service_status != 'running'
```

### L7 Operations

Purpose:
- Model operational execution and resilience behavior: workflows, backup policy, and outage response.

Canonical ownership:
- Workflows and runbook-oriented automation intent.
- Power resilience orchestration (`power_resilience.policies`).
- Backup strategy/policies and operational notes.
- Operation-facing documentation generation policy.

Public contract for operations tooling:
- Workflow steps, script paths, and policy IDs consumed by deployment/ops flows.

Boundary rules:
- ADR 0001: outage and power runtime policy belongs to L7, not L1.
- L7 consumes lower-layer IDs; it does not redefine inventory/network/runtime source-of-truth.

Validation-critical invariants:
- Script/command paths and expected working-directory assumptions must be valid.
- Backup destination contracts should align to canonical L3 references (ongoing alignment in ADR 0031 and ADR 0033).

Example (`topology/L7-operations.yaml`, `topology/L7-operations/power/policy-ups-main.yaml`):

```yaml
workflows:
  update_topology:
    steps:
    - step: 2
      script: topology-tools/validate-topology.py

power_resilience:
  policies:
  - id: policy-ups-main
    type: ups-protection
```

## Where To Store What (Cloud Instance Example)

Use this mapping when the machine is "owned by account/billing" but physically controlled by a cloud provider.

- `L1`:
  - Store the cloud host itself as a device in `topology/L1-foundation/devices/provider/compute/`.
  - Use `type: cloud-vm`, `class: compute`, `substrate: provider-instance`, `access: public` or `access: vpn-only`.
  - Set `specs.cpu.architecture` explicitly to capture host/runtime compile target.
  - Keep CPU/RAM and base hardware-like capacity in `specs.cpu` and `specs.memory`.
  - Keep provider-specific sizing and placement in `cloud.instance_type`, `cloud.vcpus`, `cloud.memory_gb`, `cloud.region`.
- `L1 media + attachments`:
  - Store virtual provider volumes in `topology/L1-foundation/media/` as `disk-*`.
  - Bind volume-to-instance in `topology/L1-foundation/media-attachments/` as `attach-*`.
- `L3`:
  - Store logical storage chain and `storage_endpoints` only when those cloud disks are used for mounts, data placement, or backup destinations.
  - If the cloud disk is present but not used by modeled workloads/data flows yet, keep only L1 media/attachment facts.
- `L4`:
  - Store host OS fact in `host_operating_systems` when the cloud device is a runtime target in L4/L5.
  - For inventory-only cloud devices without modeled runtime targets, `host_operating_systems` may be omitted.
  - Store runtime placement/resources for workloads that run on that cloud host.
- `L5/L6/L7`:
  - `L5`: services and runtime bindings targeting that host.
  - `L6`: monitoring and alerting for host/services.
  - `L7`: operational workflows, backup policies, runbook policies.

Minimal placement sketch:

```yaml
# L1 device (provider compute)
id: oracle-arm-frankfurt
type: cloud-vm
class: compute
substrate: provider-instance
access: public
specs:
  cpu:
    architecture: arm64
cloud:
  instance_type: VM.Standard.A1.Flex
  vcpus: 4
  memory_gb: 24

# L1 media
id: disk-oci-boot-volume
type: ssd
form_factor: virtual
size_gb: 200

# L1 attachment
id: attach-oracle-arm-frankfurt-slot-virtio-blk-0
device_ref: oracle-arm-frankfurt
slot_ref: slot-virtio-blk-0
media_ref: disk-oci-boot-volume
```

## Current Modular Layout

- Modularized layers:
  - `topology/L1-foundation.yaml`:
  - `topology/L1-foundation/locations/`
  - `topology/L1-foundation/devices/owned/<class>/`
  - `topology/L1-foundation/devices/provider/<class>/`
  - `topology/L1-foundation/media/` (storage media registry)
  - `topology/L1-foundation/media-attachments/` (device slot to media bindings)
  - `topology/L1-foundation/data-links/` (data links)
  - `topology/L1-foundation/power-links/` (power links)
  - `topology/L7-operations.yaml`:
  - `topology/L7-operations/power/`
  - `topology/L2-network.yaml`:
  - `topology/L2-network/trust-zones/`
  - `topology/L2-network/profiles/`
  - `topology/L2-network/networks/`
  - `topology/L2-network/bridges/`
  - `topology/L2-network/routing/`
  - `topology/L2-network/firewall/policies/`
  - `topology/L2-network/firewall/templates.yaml`
  - `topology/L2-network/qos/`
  - `topology/L2-network/ipv6/`
  - `topology/L3-data.yaml`:
  - `topology/L3-data/partitions/`
  - `topology/L3-data/volume-groups/`
  - `topology/L3-data/logical-volumes/`
  - `topology/L3-data/filesystems/`
  - `topology/L3-data/mount-points/`
  - `topology/L3-data/storage-endpoints/`
  - `topology/L3-data/data-assets/`
  - `topology/L4-platform.yaml`:
  - `topology/L4-platform/defaults.yaml`
  - `topology/L4-platform/resource-profiles/`
  - `topology/L4-platform/workloads/lxc/`
  - `topology/L4-platform/workloads/vms/`
  - `topology/L4-platform/host-operating-systems/`
  - `topology/L4-platform/templates/lxc/`
  - `topology/L4-platform/templates/vms/`
  - `topology/L5-application.yaml`:
  - `topology/L5-application/certificates.yaml`
  - `topology/L5-application/services.yaml`
  - `topology/L5-application/dns.yaml`
  - `topology/L6-observability.yaml`:
  - `topology/L6-observability/healthchecks.yaml`
  - `topology/L6-observability/network-monitoring.yaml`
  - `topology/L6-observability/alerts.yaml`
  - `topology/L6-observability/notification-channels.yaml`
  - `topology/L6-observability/dashboard.yaml`
- Single-file layers (not yet modularized into subfolders):
  - `topology/L0-meta.yaml`

## Editing Conventions (AI + Human)

- One module file should represent one logical unit.
- Use predictable names: file name equals object `id` where possible.
- Prefer deterministic auto-discovery with `!include_dir_sorted` for order-insensitive domains.
- Keep `_index.yaml` only for order-sensitive domains (for example firewall policy chains).
- Keep module size practical (target under ~200 lines).
- Preserve key order: `id`, `name`, `type`, `role`, `class`, `substrate`, `access`, refs, config, `description`.
- Model is defined by fields inside files; folders are validated against model.
- Validator reports placement lints (warnings) and suggests expected paths when files are moved/copied incorrectly.
- In L1 devices, always set taxonomy explicitly: `class` + `substrate` + `access`.
- In L1 storage, keep slot capability in devices and media state in `media_registry` + `media_attachments` (no inline `slot.media`).
- `data_links` can reference only owned/colo substrate devices (no `provider-instance`).
- `power_links` can reference only owned/colo substrate devices (no `provider-instance`).
- For PoE, model both links: one data link + one power link with `data_link_ref`.
- VM/LXC remain in `L4_platform` (compute module), not in `L1_foundation`.
- L4 workloads are one-object-per-file in `topology/L4-platform/workloads/`.
- In L2 networks, `managed_by_ref` should point to `class: network` device.
- For L2 networks with `profile_ref`, keep only exception overrides in network files.

## ADR Boilerplate (Layer Modularization)

Use this section as shared source of truth for modularization ADRs to avoid repeated prose.

### Naming Conventions

- Directories: `kebab-case` (for example `resource-profiles/`, `storage-endpoints/`).
- YAML keys: `snake_case` (for example `resource_profiles`, `storage_endpoints`).
- Object IDs: stable, prefix-based, and layer-scoped.

### Discovery Contract

- Prefer deterministic auto-discovery: `!include_dir_sorted` for order-insensitive domains.
- Do not use manual `_index.yaml` in migrated autodiscovery domains.
- Keep one-object-per-file where practical; file name should match object `id` when possible.

### RACI Template

- Responsible: topology maintainer for layer files.
- Accountable: architecture owner for contracts and boundary changes.
- Consulted: upstream/downstream layer owners impacted by references.
- Informed: operations owner for deployment/runbook impacts.

### Rollback Template

1. Restore composition root and/or monolithic layer file from git.
2. Remove modular directory tree introduced by migration.
3. Run strict validation: `python topology-tools/validate-topology.py --strict`.
4. Regenerate outputs: `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate`.

## Add New Hardware Workflow

1. Add new device file under `topology/L1-foundation/devices/<substrate-group>/<class>/<device-id>.yaml`.
2. Set `class`/`substrate`/`access`.
3. Add/update data connectivity in `topology/L1-foundation/data-links/` only for non-provider substrates.
4. Add/update power cabling in `topology/L1-foundation/power-links/`.
5. Add/update storage media in `topology/L1-foundation/media/`.
6. Add/update slot/media bindings in `topology/L1-foundation/media-attachments/`.
7. If needed, add/update virtual network in `topology/L2-network/networks/`.
8. Prefer `profile_ref` from `topology/L2-network/profiles/default.yaml`.
9. Read profile rules in `topology/L2-network/profiles/README.md`.
10. Override explicit fields (`network_plane`, `segmentation_type`, `transport`, `volatility`) only when diverging from profile.
11. For firewall policy changes, edit `topology/L2-network/firewall/policies/*` and include from `topology/L2-network/firewall/policies/_index.yaml`.
12. Add VM/LXC workloads in `topology/L4-platform/workloads/lxc/` or `topology/L4-platform/workloads/vms/`.
13. Add platform/app/monitoring modules only if the device hosts workloads.
14. Validate and regenerate:
   - `python topology-tools/validate-topology.py`
   - `python topology-tools/generate-docs.py`
15. If architecture changed, add a new ADR in `adr/NNNN-*.md`.

## Anti-Patterns

- Large monolithic layer files with mixed concerns.
- Hardcoded cross-layer values instead of `*_ref`.
- Reordering IDs frequently (breaks stable diffs and AI reasoning).
