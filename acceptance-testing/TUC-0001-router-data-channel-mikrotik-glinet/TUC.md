# TUC-0001: Router-to-Router Ethernet Data Channel (MikroTik + GL.iNet)

## Metadata

- `id`: `TUC-0001`
- `status`: `planned`
- `owner`: `topology-tools`
- `created_at`: `2026-03-11`
- `target_date`: `2026-03-18`
- `related_adrs`:
  - `adr/0062-modular-topology-architecture-consolidation.md`
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  - `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md`
  - `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`

## Objective

Prove that the plugin/module system can model two concrete routers and their physical ethernet connection using class/object/instance contracts, with stable compile/validate/generate behavior.

## Scope

- In scope:
  - Generic class module for data channels (ethernet/wifi/fiber baseline): `class.network.data_channel`
  - Object module for ethernet cable: `obj.network.ethernet_cable`
  - Two router instances:
    - `rtr-mikrotik-chateau`
    - `rtr-slate`
  - One cable instance connecting router ports with instance-specific length
  - Plugin validations for endpoint/port correctness
- Out of scope:
  - L3 routing policy design between routers
  - Provisioning/runtime deployment generation
  - Non-ethernet channel types

## Preconditions

- Existing router class and object modules are present:
  - `v5/topology/class-modules/classes/router/class.router.yaml`
  - `v5/topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml`
  - `v5/topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml`
- Existing router instances are present:
  - `v5/topology/instances/home-lab/instance-bindings.yaml`
- Plugin-first runtime is active.

## Inputs

- Topology manifest:
  - `v5/topology/topology.yaml`
- Instance bindings:
  - `v5/topology/instances/home-lab/instance-bindings.yaml`
- Plugin manifests:
  - Base: `v5/topology-tools/plugins/plugins.yaml`
  - Module-level manifests discovered under:
    - `v5/topology/class-modules/**/plugins.yaml`
    - `v5/topology/object-modules/**/plugins.yaml`

## Expected Outcomes

- New class/object modules are compiled and visible in effective model.
- Cable instance is validated against real object port definitions.
- Invalid endpoint/port combinations return deterministic diagnostics.
- No regression in existing plugin contract/integration tests.

## Acceptance Criteria

1. Compile succeeds with zero errors for the valid two-router + one-cable fixture.
2. Cable endpoints must reference existing router instances and existing ethernet ports.
3. Instance-specific cable properties (`length_m`, `shielding`) are preserved in compiled model.
4. Invalid port name on either endpoint fails with stable diagnostic code.
5. Duplicate connection endpoint usage policy is enforced (as defined in validator).
6. Plugin order and output remain deterministic across repeated runs.

## Risks and Open Questions

- Current compile path normalizes rows into fixed shape; extension fields may be dropped.
- `instance_overrides` are validated but currently not projected into compiled output.
- Need explicit policy for port occupancy:
  - allow many cables per port
  - or enforce single cable per port
