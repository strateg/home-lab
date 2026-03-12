# TUC-0001: Router-to-Router Ethernet Data Link + Data Channel (MikroTik + GL.iNet)

## Metadata

- `id`: `TUC-0001`
- `status`: `passed` (2026-03-11, evidence baseline: `65af255`)
- `owner`: `topology-tools`
- `created_at`: `2026-03-11`
- `target_date`: `2026-03-18`
- `related_adrs`:
  - `adr/0062-modular-topology-architecture-consolidation.md`
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  - `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md`
  - `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
  - `adr/0071-sharded-instance-files-and-flat-instances-root.md`

## Objective

Prove that the plugin/module system can model two concrete routers via OSI-aligned contracts:
- physical connection as `physical_link` (ethernet cable, L1),
- information flow as `data_link` (ethernet channel, L2),
- lateral power wiring as `power.source_ref` (L1 -> L1),
with stable compile/validate/generate behavior.

## Implementation Status (as of 2026-03-11)

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| `class.network.physical_link` | ✅ Exists | `v5/topology/class-modules/network/class.network.physical_link.yaml` | Defined; requires instance objects |
| `class.network.data_link` | ✅ Exists | `v5/topology/class-modules/network/class.network.data_link.yaml` | Defined; requires instance objects |
| `obj.network.ethernet_cable` | ✅ Exists | `v5/topology/object-modules/network/obj.network.ethernet_cable.yaml` | Defined with L1 physical properties |
| `obj.network.ethernet_channel` | ✅ Exists | `v5/topology/object-modules/network/obj.network.ethernet_channel.yaml` | Defined with L2 logical properties |
| Cable instance (cat5e fixture) | ✅ Exists | `v5/topology/instances/l1_devices/inst.ethernet_cable.cat5e.yaml` | Sharded instance; endpoints and properties defined |
| Channel instance (fixture) | ✅ Exists | `v5/topology/instances/l2_network/inst.chan.eth.chateau_to_slate.yaml` | Created; references cable instance via `link_ref` |
| Endpoint validator | ✅ Exists | `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py` | Validates endpoints and port references |
| Port validation (MikroTik) | ✅ Exists | `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py` | Covered by integration test for invalid MikroTik port (`E7305`) |
| Port validation (GL.iNet) | ✅ Exists | `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py` | Covered by integration test for invalid GL.iNet port (`E7305`) |
| Cable-to-channel integrity | ✅ Exists | `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py` | Validates `creates_channel_ref`, `link_ref` back-reference, and unordered endpoint match (`E7307/E7308`) |
| L1 power-source relation (`power.source_ref`) | ✅ Exists | `v5/topology-tools/plugins/validators/power_source_refs_validator.py` | Validates L1 source class/layer, outlet occupancy, and cycle constraints |
| Determinism validation | ✅ Passed | `artifacts/determinism-report.txt` | Repeated runs produce identical output |
| Plugin suite regression | ✅ Passed | `artifacts/plugin-suites.txt` | 81 existing plugin contract/integration tests still pass |

## Scope

- In scope:
  - Generic class module for physical links: `class.network.physical_link`
  - Generic class module for logical channels: `class.network.data_link`
  - Object module for ethernet cable (L1): `obj.network.ethernet_cable`
  - Object module for ethernet channel (L2): `obj.network.ethernet_channel`
  - Two router instances:
    - `rtr-mikrotik-chateau`
    - `rtr-slate`
  - One cable instance connecting router ports with instance-specific link properties
  - One channel instance produced by the cable instance
  - Plugin validations for endpoint/port correctness and `physical_link -> data_link` consistency
- Out of scope:
  - L3 routing policy design between routers
  - Provisioning/runtime deployment generation
  - Non-ethernet channel types

## Preconditions

- Existing router class and object modules are present:
  - `v5/topology/class-modules/router/class.router.yaml`
  - `v5/topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml`
  - `v5/topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml`
- Existing router instances are present:
  - `v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml`
  - `v5/topology/instances/l1_devices/rtr-slate.yaml`
- Plugin-first runtime is active.

## Inputs

- Topology manifest:
  - `v5/topology/topology.yaml`
- Instance shards root:
  - `v5/topology/instances/`
- Plugin manifests:
  - Base: `v5/topology-tools/plugins/plugins.yaml`
  - Module-level manifests discovered under:
    - `v5/topology/class-modules/**/plugins.yaml`
    - `v5/topology/object-modules/**/plugins.yaml`

## Expected Outcomes

- New class/object modules are compiled and visible in effective model.
- Cable instance is validated against real object port definitions.
- Cable instance references created channel instance (`creates_channel_ref`).
- L1 device power bindings (`power.source_ref`) are validated and preserved in compiled model.
- Invalid endpoint/port combinations return deterministic diagnostics.
- No regression in existing plugin contract/integration tests.

## Acceptance Criteria

1. Compile succeeds with zero errors for the valid two-router + one-cable fixture.
2. Cable endpoints must reference existing router instances and existing ethernet ports.
3. Cable class is `class.network.physical_link`; channel class is `class.network.data_link`.
4. Cable instance must declare `creates_channel_ref` pointing to an existing `data_link` instance.
5. Cable and channel endpoints must match as an unordered endpoint pair.
6. Instance-specific cable properties (`length_m`, `shielding`) are preserved in compiled model.
7. Invalid port name on either endpoint fails with stable diagnostic code.
8. Duplicate connection endpoint usage policy is enforced (as defined in validator).
9. Plugin order and output remain deterministic across repeated runs.
10. L1 `power.source_ref` wiring is valid (`router -> pdu -> ups`) with unique outlet assignment per source.

## Risks and Open Questions

- Port occupancy policy is still open:
  - allow many cables per port
  - or enforce single cable per port
