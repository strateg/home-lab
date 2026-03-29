# ADR 0071: Sharded Instance Files and Flat `instances` Root

- Status: Accepted
- Date: 2026-03-11
- Revised: 2026-03-19
- Related: ADR 0062, ADR 0063, ADR 0069, ADR 0070

## Context

Before cutover, storage used a single project file:

- `v5/topology/instances/_legacy-home-lab/instance-bindings.yaml`

This causes high cognitive load and operational friction:

1. frequent merge conflicts
2. large diffs for tiny changes
3. weak per-entity ownership
4. difficult review and scenario isolation

Legacy runtime previously assumed one monolithic file and required explicit `class_ref` in rows.

## Decision

Adopt a **sharded instance model** with one instance per file under `v5/topology/instances/`,
organized by canonical layer bucket and instance group.

### 1. Canonical Project Root

Canonical authoring root:

- `v5/topology/instances/`

Legacy monolith content is archived under `v5/topology/instances/_legacy-home-lab/`.

### 2. Storage Layout and File Contract

One file contains exactly one instance row.

Recommended layout:

- `v5/topology/instances/<layer-bucket>/<group>/<instance>.yaml`

Minimal file schema:

```yaml
instance: inst.ethernet_cable.cat5e
object_ref: obj.network.ethernet_cable
group: devices
layer: L1
version: 1.0.0
status: modeled
endpoint_a:
  device_ref: rtr-mikrotik-chateau
  port: ether2
endpoint_b:
  device_ref: rtr-slate
  port: lan1
creates_channel_ref: inst.chan.eth.chateau_to_slate
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
7. `instance` MUST be filename-safe across platforms (no `<>:"/\\|?*`).
8. Canonical top-level key order in shard files is: `instance`, `object_ref`, `group`, `layer`, `version`, then other fields.
9. Relative shard path under `instances_root` MUST be exactly `<layer-bucket>/<group>/<instance>.yaml`.
10. `<layer-bucket>` MUST match layer:
   - `L0-meta`, `L1-foundation`, `L2-network`, `L3-data`, `L4-platform`, `L5-application`, `L6-observability`, `L7-operations`.
11. `<group>` directory name MUST match shard field `group`.

### 4. Path Contract

`topology.yaml` contract:

- canonical: `paths.instances_root`

### 5. Loader Responsibility and Plugin Compatibility

Loader MUST:

1. discover instance files under `instances_root`
2. validate one-row-per-file contract
3. keep `class_ref` optional in shard authoring and derive/verify it during instance normalization
4. assemble legacy-compatible in-memory payload:

```yaml
instance_bindings:
  <group>: [ ...rows... ]
```

Downstream compiler/validator/generator plugins continue consuming assembled payload, not shard files directly.

Plugin boundary rule:

1. `instances_root` stores data rows only (instance YAML files).
2. There are no `instance-modules` under `instances_root`.
3. Plugin manifests and plugin code remain in:
   - `class-modules`
   - `object-modules`
   - optional project-level plugin root (for instance-scoped extensions), for example `projects/<project-id>/plugins`
4. Plugin discovery MUST NOT scan `instances_root` data tree.

Authoring rule:

1. shard files MUST NOT require `class_ref`
2. `class_ref` is derived by loader from `object_ref` chain
3. if authored explicitly, it MUST match derived value or loader fails

### 6. Validation Rules (Minimum)

Loader MUST enforce:

1. required keys: `instance`, `version`, `group`, `layer`, `object_ref`
2. one-row-per-file
3. `group`/`layer` consistency with `layer-contract.yaml`
4. supported shard `version` (semver, major `1`; e.g. `1.0.0`)
5. `class_ref` derivation integrity from `object_ref` during compile normalization

Minimum diagnostic set:

- `E7101_INSTANCE_ID_FILENAME_MISMATCH`
- `E7102_DUPLICATE_INSTANCE_ID`
- `E7103_MULTIROW_INSTANCE_FILE`
- `E7104_UNSUPPORTED_INSTANCE_SCHEMA_VERSION`
- `E7105_RESERVED_FILE_INGESTION_ATTEMPT`
- `E7108_INSTANCE_PATH_LAYER_BUCKET_MISMATCH`
- `E7109_INSTANCE_PATH_GROUP_DIR_MISMATCH`

### 7. Project Metadata

Non-instance project metadata SHOULD be stored in:

- `v5/topology/instances/project.yaml`

and not duplicated in shard files.

### 8. Migration and Cutover

Completed cutover:

1. splitter tool delivered: `v5/topology-tools/utils/split-instance-bindings.py`
2. monolith split to per-instance shards in `v5/topology/instances/<layer-bucket>/<group>/`
3. compiler runtime switched to `sharded-only` instance source
4. legacy path `paths.instance_bindings` removed from manifest
5. service instance ids containing `:` were normalized to `.` for cross-platform shard filenames

## Consequences

### Positive

1. small, reviewable diffs for each instance change
2. lower merge-conflict probability
3. clearer ownership boundaries per device/link/service instance
4. better fit for TUC-style incremental acceptance modeling

### Trade-offs

1. more files to manage in repository
2. loader complexity increases (discovery + assembly + diagnostics)
3. migration required one-time split and path updates

### Compatibility Impact

1. plugin contracts can stay stable because loader emits legacy-shaped assembled payload
2. manifest path contract is now `paths.instances_root` only
3. CI and docs must be updated to new authoring path

### Out of Scope

1. no change to class/object semantics from ADR 0062
2. no change to plugin stage ownership from ADR 0063/0069
3. no change to generated artifact ownership

## References

- `v5/topology/topology.yaml`
- `v5/topology/instances/project.yaml`
- `v5/topology/instances/_legacy-home-lab/instance-bindings.yaml`
- `v5/topology-tools/compiler_runtime.py`
- `v5/topology-tools/plugins/compilers/instance_rows_compiler.py`
- `v5/topology-tools/plugins/validators/reference_validator.py`
- `v5/topology-tools/plugins/validators/model_lock_validator.py`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TUC.md`
- `adr/0071-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0071-analysis/CUTOVER-CHECKLIST.md`
