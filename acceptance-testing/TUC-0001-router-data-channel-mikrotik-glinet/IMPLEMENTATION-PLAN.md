# TUC-0001 Implementation Plan

## Workstream 1: Model Contracts

1. Add class module:
   - `v5/topology/class-modules/classes/network/class.network.physical_link.yaml` (OSI L1 physical link contract)
2. Rework class module:
   - `v5/topology/class-modules/classes/network/class.network.data_link.yaml` (OSI L2 logical channel contract)
3. Add object modules:
   - `v5/topology/object-modules/network/obj.network.ethernet_cable.yaml`
   - `v5/topology/object-modules/network/obj.network.ethernet_channel.yaml`
   - Keep cable-specific runtime parameters (`length_m`, `shielding`, ...) at instance level.
4. Add fixture rows in:
   - `v5/topology/instances/home-lab/instance-bindings.yaml`
   - one cable (`physical_link`) and one channel (`data_link`) with bidirectional linkage.

## Workstream 2: Compiler Stability for Instance Extensions

1. Update `instance_rows` compiler plugin to preserve custom row fields:
   - `v5/topology-tools/plugins/compilers/instance_rows_compiler.py`
2. Update effective model compiler to propagate preserved fields:
   - `v5/topology-tools/plugins/compilers/effective_model_compiler.py`
3. Add regression tests for extension field pass-through.

## Workstream 3: Domain Validators (Module Plugins)

1. Add class/object plugin manifests:
   - `v5/topology/class-modules/classes/router/plugins.yaml`
   - `v5/topology/object-modules/mikrotik/plugins.yaml`
   - `v5/topology/object-modules/glinet/plugins.yaml`
   - `v5/topology/object-modules/network/plugins.yaml`
2. Implement validators:
   - Router class validator (data-channel interface contract)
   - MikroTik object validator (ethernet field and port naming policy)
   - GL.iNet object validator (ethernet field and DSA constraints)
   - Cable connectivity validator (endpoint refs, port existence, and `physical_link -> data_link` integrity)

## Workstream 4: Acceptance Fixtures

1. Add valid fixture:
   - cable between `rtr-mikrotik-chateau:ether2` and `rtr-slate:lan1`
   - matching channel produced by cable via `creates_channel_ref`
2. Add invalid fixtures:
   - unknown endpoint instance
   - unknown port
   - wrong class_ref/object_ref for cable

## Workstream 5: Quality Gates

1. Run:
   - `python -m pytest -q v5/tests/plugin_contract v5/tests/plugin_integration`
2. Run compile command and archive diagnostics/effective outputs.
3. Verify deterministic output in repeated runs.

## Exit Criteria

1. All TUC matrix scenarios are `passed`.
2. No new regressions in plugin contract/integration suites.
3. Evidence artifacts are attached in `artifacts/`.

## Rollback

1. Remove newly added module plugin manifests from discovery paths.
2. Revert new class/object/cable fixture files.
3. Keep compiler changes only if covered by independent regression tests.
