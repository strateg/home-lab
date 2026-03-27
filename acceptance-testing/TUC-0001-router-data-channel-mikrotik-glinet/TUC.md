# TUC-0001: Router-to-Router Ethernet Link + Data Channel (MikroTik + GL.iNet)

## Metadata

- `id`: `TUC-0001`
- `status`: `passed`
- `owner`: `topology-tools`
- `created_at`: `2026-03-11`
- `last_verified_at`: `2026-03-27`
- `related_adrs`:
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  - `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
  - `adr/0071-sharded-instance-files-and-flat-instances-root.md`
  - `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`

## Objective

Validate that the current plugin-first runtime correctly models and validates:

1. L1 cable instance between two real router instances.
2. L2 data-channel instance bound to that cable.
3. Cross-reference integrity (`creates_channel_ref` and `link_ref`).
4. Preservation of instance-level cable and power properties in effective model.

## Scope

- In scope:
  - `obj.network.ethernet_cable` + `class.network.physical_link`
  - `obj.network.ethernet_channel` + `class.network.data_link`
  - Instances `rtr-mikrotik-chateau` and `rtr-slate`
  - Instances `inst.ethernet_cable.cat5e` and `inst.chan.eth.chateau_to_slate`
  - Validator behavior for endpoint/port/reference consistency
  - Compile contract for preserving `instance_data` in effective model
- Out of scope:
  - L3 routing design and policy
  - Runtime deployment correctness (Terraform/Ansible execution)
  - Non-ethernet channel families

## Preconditions

- Framework modules are in `topology/`.
- Active project is `home-lab` with sharded instances in `projects/home-lab/topology/instances`.
- Plugin-first compiler runtime is used via `topology-tools/compile-topology.py`.

## Inputs

- Topology manifest: `topology/topology.yaml`
- Project manifest: `projects/home-lab/project.yaml`
- Instances:
  - `projects/home-lab/topology/instances/L1-foundation/devices/rtr-mikrotik-chateau.yaml`
  - `projects/home-lab/topology/instances/L1-foundation/devices/rtr-slate.yaml`
  - `projects/home-lab/topology/instances/L1-foundation/physical-links/inst.ethernet_cable.cat5e.yaml`
  - `projects/home-lab/topology/instances/L2-network/data-channels/inst.chan.eth.chateau_to_slate.yaml`
- Network validator manifest: `topology/object-modules/network/plugins.yaml`
- TUC integration tests: `tests/plugin_integration/test_tuc0001_router_data_link.py`

## Expected Outcomes

- Valid cable+channel topology passes validator checks.
- Invalid endpoint/port/reference variants fail with stable diagnostics (`E7304`, `E7305`, `E7307`, `E7308`).
- Effective model retains cable `instance_data` (`length_m`, `shielding`, `category`, endpoints).
- Effective model retains power bindings for tested devices (`source_ref`, `outlet_ref`).

## Acceptance Criteria

1. `pytest -q tests/plugin_integration/test_tuc0001_router_data_link.py` passes.
2. Cable endpoints must reference existing device instances and valid object ports.
3. Cable must declare `creates_channel_ref` to an existing data-channel instance.
4. Channel `link_ref` must point back to the cable instance.
5. Cable/channel endpoint pair must match regardless of endpoint order.
6. Compile output preserves cable and power instance attributes used by this TUC.

## Risks and Open Questions

- Port occupancy policy (single cable per port vs multi-cable) is still a policy choice outside this TUC.
- TUC currently covers one router pair only; additional device families require new TUCs or matrix extensions.
