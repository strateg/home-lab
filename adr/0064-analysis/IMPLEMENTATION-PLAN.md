# ADR 0064 Implementation Plan (v5 only)

Date: 2026-03-09
Status: Draft for execution
Owner: topology v5 lane

## 1. Objective

Implement ADR 0064 end-to-end in v5 so firmware and OS are modeled as separate first-class entities with canonical `class -> object -> instance` semantics, and device/workload bindings use instance references only.

Target runtime contract:
- `firmware_ref: inst.firmware.*`
- `os_refs: [inst.os.*]`
- class/object constraints define allowed classes and cardinality
- concrete software choices are instance-level only

## 2. Scope and Boundaries

In scope:
- `v5/topology/*`
- `v5/topology-tools/*`
- `v5/tests/*`
- ADR/docs alignment for v5 semantics

Out of scope:
- net-new feature work in `v4/*`
- LXC/Docker runtime taxonomy extension (deferred to ADR 0065/0066)

## 3. Current Gap Snapshot

Already present:
- OS policy gate by class (`required|allowed|forbidden`)
- derived `cap.os.*` and architecture capability checks
- ADR harmonization across older ADRs

Main gaps to close:
1. Transitional model still uses `software.os` / `prerequisites.os_ref` in tooling.
2. No canonical `class.firmware` / `class.os` module chain enforced in topology data.
3. Device/workload binding not fully migrated to `firmware_ref + os_refs[]`.
4. Multi-boot cardinality and compatibility checks are partial.
5. Capability derivation still tied to legacy object-level OS payload in key paths.

## 4. Workstreams

### WS1 - Canonical Data Model in v5 Topology

Deliverables:
- Add/normalize class modules for:
  - `class.firmware`
  - `class.os`
- Ensure object modules use:
  - `object: obj.*`
  - `class_ref: class.firmware|class.os`
- Ensure instance modules use:
  - `instance: inst.*`
  - `object_ref: obj.*`
- Add software-instance registry section (or equivalent include) for firmware/OS instances.

DoD:
- No new firmware/OS payload authored outside class/object/instance chain.
- Naming prefixes are consistent in all new/changed v5 files.

### WS2 - Instance Binding Contract in Device/Workload Instances

Deliverables:
- Migrate bindings to canonical fields:
  - `firmware_ref` (single)
  - `os_refs[]` (array)
- Remove usage of legacy fields in authored v5 data:
  - `bindings.firmware`
  - `os_primary`, `os_secondary`, `os_tertiary`
  - direct class-contract OS subclass references

DoD:
- Device/workload instances resolve software only through instance refs.
- Legacy fields fail validation (after deprecation phase).

### WS3 - Compiler and Validator Contract

Deliverables in `v5/topology-tools/compile-topology.py` and `v5/topology-tools/check-capability-contract.py`:
- Resolve and validate `firmware_ref` existence and type.
- Resolve and validate each `os_refs[]` entry.
- Validate class policy + cardinality:
  - `os_policy`
  - `multi_boot`
  - min/max OS refs by class/object policy.
- Validate compatibility:
  - architecture (device <-> firmware <-> OS)
  - installation model constraints
- Emit explicit diagnostics for each violation class.

DoD:
- `validate-v5` fails deterministically on all invalid software binding scenarios.
- Diagnostics point to exact entity/path causing mismatch.

### WS4 - Capability Derivation and Effective Model

Deliverables:
- Derive software capabilities from resolved instances (not legacy object payload):
  - `cap.firmware.*`
  - `cap.os.*`
  - `cap.arch.*` where applicable
- Merge derived capabilities into effective capability set before service compatibility checks.
- Ensure capability registry/taxonomy alignment stays consistent with current `cap.net.*` model.

DoD:
- Service-to-device matching uses effective capabilities including resolved firmware/OS.
- No drift between compiler and capability checker derivation logic.

### WS5 - Migration Compatibility and Cutover

Deliverables:
- Introduce temporary compatibility reader for legacy fields (read-only) with warnings.
- Provide deterministic migration mapping document (legacy -> canonical).
- Phase out compatibility reader after topology migration completes.

DoD:
- Phase gate report shows zero legacy field usage before hard removal.
- Final mode runs without legacy readers.

### WS6 - Test Matrix and CI Gates

Deliverables:
- Add fixtures/tests for:
  - valid single-OS device
  - valid multi-boot device
  - firmware-only device (where allowed)
  - missing firmware ref
  - invalid OS class/type ref
  - architecture mismatch
  - installation model mismatch
  - forbidden OS policy violations
- Add gate in `v5/scripts/orchestration/lane.py validate-v5` for ADR0064 contract checks.

DoD:
- All new fixtures pass in success cases and fail in negative cases with expected diagnostics.
- CI gate prevents regressions on binding semantics.

## 5. Execution Phases

Phase 1 (Contract freeze, 1-2 days)
- Finalize schema/field contract for `firmware_ref` + `os_refs[]` and cardinality fields.
- Freeze naming and diagnostics codes for new violations.

Phase 2 (Tooling core, 2-4 days)
- Implement WS3 + WS4 in compiler/checker.
- Keep temporary compatibility reader active.

Phase 3 (Topology migration, 2-4 days)
- Migrate all v5 object/instance data to canonical refs.
- Resolve all compatibility warnings.

Phase 4 (Hard cutover, 1-2 days)
- Disable/remove legacy field readers.
- Enforce canonical fields only.

Phase 5 (Stabilization, 1-2 days)
- Expand fixtures.
- Run repeated `validate-v5` and finalize migration report.

## 6. Risks and Controls

Risk: hidden legacy field usage in rarely used modules.
Control: repo-wide scan + fail-on-legacy gate before cutover.

Risk: capability mismatch after derivation change.
Control: dual-run comparison (old/new derivation) during Phase 2-3.

Risk: inconsistent implementation between compiler and checker.
Control: shared helper or mirrored unit tests with identical fixtures.

## 7. Acceptance Criteria

ADR 0064 implementation is complete when:
1. All v5 device/workload software bindings are instance-based (`firmware_ref`, `os_refs[]`).
2. Legacy software fields are absent from authored v5 topology.
3. Compiler/checker enforce type, existence, cardinality, and compatibility rules.
4. Effective capabilities include instance-derived `cap.firmware.*` and `cap.os.*`.
5. `python v5/scripts/orchestration/lane.py validate-v5` passes cleanly on main topology and fixtures.

## 8. Immediate Next Tasks (Start Order)

1. Freeze canonical schema snippets and diagnostics codes for WS3.
2. Implement resolver/validator path for `firmware_ref` and `os_refs[]`.
3. Migrate one representative class set (router + compute) end-to-end.
4. Add negative fixtures and enforce gate in `validate-v5`.
5. Complete full v5 topology migration and remove legacy readers.
