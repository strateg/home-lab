# ADR 0071: Sharded Instance Files and Flat `instances` Root

- Status: Proposed
- Date: 2026-03-11
- Related: ADR 0062, ADR 0063, ADR 0069, ADR 0070

## Context

Current storage uses a single project file:

- `v5/topology/instances/home-lab/instance-bindings.yaml`

This causes high cognitive load and operational friction:

1. frequent merge conflicts
2. large diffs for tiny changes
3. weak per-entity ownership
4. difficult review and scenario isolation

Runtime today also assumes one file path (`paths.instance_bindings`) and a pre-assembled payload.

## Decision

Adopt a **sharded instance model** with one instance per file and a flat project root under `v5/topology/instances/`.

### 1. Canonical Project Root

Canonical authoring root:

- `v5/topology/instances/`

`v5/topology/instances/home-lab/` is deprecated for active authoring.

### 2. Storage Layout and File Contract

One file contains exactly one instance row.

Recommended layout:

- `v5/topology/instances/<group>/<instance>.yaml`

Minimal file schema:

```yaml
schema_version: 1
instance: inst.ethernet_cable.cat5e
group: l1_devices
layer: L1
object_ref: obj.network.ethernet_cable
status: modeled
endpoint_a:
  device_ref: rtr-mikrotik-chateau
  port: ether2
endpoint_b:
  device_ref: rtr-slate
  port: lan1
creates_channel_ref: chan.eth.chateau_to_slate
length_m: 3
shielding: utp
category: cat5e
```

### 3. Identity and Determinism Rules

Strict rules:

1. `instance` is the global canonical identifier.
2. File basename MUST equal instance id: `<instance>.yaml`.
3. Basename mismatch is a hard error.
4. `instance` MUST be globally unique across all discovered files.
5. Discovery order is lexicographic by relative path.
6. Assembled in-group order is lexicographic by `instance`.

### 4. Path Contract

`topology.yaml` contract:

- canonical: `paths.instances_root`
- temporary compatibility: `paths.instance_bindings` (deprecated)

### 5. Loader Responsibility and Plugin Compatibility

Loader MUST:

1. discover instance files under `instances_root`
2. validate one-row-per-file contract
3. derive `class_ref` from `object_ref` (object contract)
4. assemble legacy-compatible in-memory payload:

```yaml
instance_bindings:
  <group>: [ ...rows... ]
```

Downstream compiler/validator/generator plugins continue consuming assembled payload, not shard files directly.

Plugin boundary rule:

1. `instances_root` stores data rows only (instance YAML files).
2. There are no `instance-modules`.
3. Plugin manifests and plugin code remain only in:
   - `class-modules`
   - `object-modules`
4. Plugin discovery MUST NOT scan `instances_root`.

Authoring rule:

1. shard files MUST NOT require `class_ref`
2. `class_ref` is derived by loader from `object_ref` chain
3. if authored explicitly, it MUST match derived value or loader fails

### 6. Validation Rules (Minimum)

Loader MUST enforce:

1. required keys: `schema_version`, `instance`, `group`, `layer`, `object_ref`
2. one-row-per-file
3. `group`/`layer` consistency with `layer-contract.yaml`
4. supported `schema_version`
5. `class_ref` derivation integrity from `object_ref`

Minimum diagnostic set:

- `E7101_INSTANCE_ID_FILENAME_MISMATCH`
- `E7102_DUPLICATE_INSTANCE_ID`
- `E7103_MULTIROW_INSTANCE_FILE`
- `E7104_UNSUPPORTED_INSTANCE_SCHEMA_VERSION`
- `E7105_RESERVED_FILE_INGESTION_ATTEMPT`
- `E7106_DUAL_SOURCE_CONFLICT`

### 7. Project Metadata

Non-instance project metadata SHOULD be stored in:

- `v5/topology/instances/project.yaml`

and not duplicated in shard files.

### 8. Migration and Cutover

Staged migration:

1. introduce dual-read (`instance_bindings` + `instances_root`)
2. provide splitter tool from monolith to shards
3. switch default authoring/CI to `instances_root`
4. retire legacy path after cutover evidence

Dual-read conflict policy:

1. If same `instance` exists in both legacy and sharded sources:
   - `dual-read`: shard wins + warning
   - `sharded-only`: hard error

## Consequences

### Positive

1. small, reviewable diffs for each instance change
2. lower merge-conflict probability
3. clearer ownership boundaries per device/link/service instance
4. better fit for TUC-style incremental acceptance modeling

### Trade-offs

1. more files to manage in repository
2. loader complexity increases (discovery + assembly + diagnostics)
3. migration requires tooling and transitional compatibility checks

### Compatibility Impact

1. plugin contracts can stay stable because loader emits legacy-shaped assembled payload
2. manifest path contract changes (`instances_root` introduced, `instance_bindings` deprecated)
3. CI and docs must be updated to new authoring path

### Out of Scope

1. no change to class/object semantics from ADR 0062
2. no change to plugin stage ownership from ADR 0063/0069
3. no change to generated artifact ownership

## References

- `v5/topology/topology.yaml`
- `v5/topology/instances/home-lab/instance-bindings.yaml`
- `v5/topology-tools/compiler_runtime.py`
- `v5/topology-tools/plugins/compilers/instance_rows_compiler.py`
- `v5/topology-tools/plugins/validators/reference_validator.py`
- `v5/topology-tools/plugins/validators/model_lock_validator.py`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TUC.md`
- `adr/0071-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0071-analysis/CUTOVER-CHECKLIST.md`
