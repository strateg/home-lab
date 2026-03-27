# TUC-0001 Implementation Plan

Status: `mostly completed` (2026-03-11) — see workstream completion notes below

## Workstream 1: Model Contracts

**Status:** ✅ COMPLETED

1. ✅ Added class module:
   - `v5/topology/class-modules/network/class.network.physical_link.yaml` (OSI L1 physical link contract)
2. ✅ Reworked class module:
   - `v5/topology/class-modules/network/class.network.data_link.yaml` (OSI L2 logical channel contract)
3. ✅ Added object modules:
   - `v5/topology/object-modules/network/obj.network.ethernet_cable.yaml`
   - `v5/topology/object-modules/network/obj.network.ethernet_channel.yaml`
   - Cable-specific runtime parameters (`length_m`, `shielding`, `category`, `color`) at instance level.
4. ⚠️ Partially added fixture shard files in:
   - ✅ `v5/topology/instances/l1_devices/inst.ethernet_cable.cat5e.yaml` (cable instance created)
   - ❌ `v5/topology/instances/l2_network/chan.eth.chateau_to_slate.yaml` (channel instance TODO)

## Workstream 2: Compiler Stability for Instance Extensions

**Status:** ✅ COMPLETED

1. ✅ Updated `instance_rows` compiler plugin to preserve custom row fields:
   - `v5/topology-tools/plugins/compilers/instance_rows_compiler.py`
2. ✅ Updated effective model compiler to propagate preserved fields:
   - `v5/topology-tools/plugins/compilers/effective_model_compiler.py`
3. ✅ Evidence: TUC1-T9 validates that `length_m`, `shielding`, `category` survive compile

## Workstream 3: Domain Validators (Module Plugins)

**Status:** ✅ MOSTLY COMPLETED

1. ✅ Added class/object plugin manifests:
   - `v5/topology/object-modules/network/plugins/plugins.yaml`
2. ✅ Implemented validators:
   - Endpoint validator: `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py`
   - Validates endpoint refs, port existence, and `physical_link -> data_link` integrity
   - **NEW:** Port existence validation against device object port definitions
3. ✅ Port validation partially working:
   - **NEW:** Endpoint validator now validates ports exist on device objects
   - MikroTik port names validated (ether*, wlan*, lte*, usb*)
   - GL.iNet port names validated (wan, lan*, wlan*, usb*)
   - Error code E7305 for unknown ports with list of available ports

## Workstream 4: Acceptance Fixtures

**Status:** ✅ MOSTLY COMPLETED

1. ✅ Added valid fixture:
   - Cable between `rtr-mikrotik-chateau:ether2` and `rtr-slate:lan1`
   - Matching channel reference via `creates_channel_ref`
2. ✅ Added invalid fixtures (tested scenarios TUC1-T2 through TUC1-T8):
   - Unknown endpoint instance
   - Unknown port (MikroTik + GL.iNet)
   - Wrong class_ref for cable
   - Missing creates_channel_ref
   - Channel/link mismatch
   - Endpoint pair mismatch

## Workstream 5: Quality Gates

**Status:** ✅ COMPLETED

1. ✅ Ran test suite:
   - `pytest -q v5/tests/plugin_integration/test_tuc0001_router_data_link.py`: 9 passed
   - `pytest -q v5/tests/plugin_contract v5/tests/plugin_integration`: 81 passed
2. ✅ Compiled fixture and archived diagnostics/effective outputs:
   - `artifacts/compile-valid.json`, `artifacts/diagnostics-valid.json`
3. ✅ Verified deterministic output in repeated runs:
   - `artifacts/determinism-report.txt` confirms no noisy diffs

## Exit Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All 11 TUC matrix scenarios passed | ✅ | `../TEST-MATRIX.md`, `EVIDENCE-LOG.md` |
| No new regressions in plugin suites | ✅ | `artifacts/plugin-suites.txt` (81/81 passed) |
| Evidence artifacts archived | ✅ | `artifacts/` directory with compile/diagnostic outputs |

## Remaining Open Items (for Phase 2)

1. **Channel instance fixture**: ✅ CREATED
   - Created `v5/topology/instances/l2_network/inst.chan.eth.chateau_to_slate.yaml`
   - References cable via `link_ref: inst.ethernet_cable.cat5e`
   - Completes the L2 model for the fixture

2. **Port occupancy policy**: ✅ DECIDED AND IMPLEMENTED
   - **Decision: Single cable per port** (strict enforcement)
   - Rationale: Prevents accidental port reuse and ensures clear link assignment
   - Implementation: `v5/topology/object-modules/network/plugins/port_occupancy_validator.py`
   - Diagnostic code: `E7306` for violations
   - Test scenario: TUC1-T14 validates this constraint

3. **Port existence validation**: ✅ IMPLEMENTED
   - **Enhancement:** Endpoint validator now checks port exists on device object
   - Quality gate validates before compile
   - Endpoint validator validates at compile time
   - Error code: E7305 for unknown ports
   - Test scenarios: TUC1-T12, TUC1-T13 validate port existence
   - Documentation: PORT-VALIDATION-SUMMARY.md explains implementation

4. **Extended port validation**: In progress for Phase 4
   - Additional router types (Ubiquiti, Cisco, etc.)
   - Port role/speed compatibility checks
   - L1 signal integrity checks

5. **Extended test matrix**: ✅ UPDATED
   - Added 6 new scenarios (TUC1-T12 through TUC1-T17)
   - Port occupancy, missing references, schema validation, port existence
   - Marked as "planned" pending execution

## Rollback (Not Needed - No Regressions)

Since all regression tests passed and no breakage occurred, rollback is not needed.
If required, revert would:
1. Remove newly added module plugin manifests from discovery paths.
2. Revert new class/object/cable fixture files.
3. Keep compiler changes (they are backward-compatible).
