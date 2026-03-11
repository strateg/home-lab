# ADR 0071: Sharded Instance Files and Flat `instances` Root

- Status: Proposed
- Date: 2026-03-11
- Related: ADR 0062, ADR 0063, ADR 0069, ADR 0070

## Context

`v5/topology/instances/home-lab/instance-bindings.yaml` currently stores all instance rows for the project in one file.

With active modeling this creates scaling problems:

1. high merge-conflict rate (many edits in one file)
2. very large diff noise for small local changes
3. weaker ownership boundaries for team work
4. poor ergonomics for acceptance scenarios that add/modify only a few instances

Current compiler runtime also assumes a single file path (`paths.instance_bindings`) and passes one combined payload to plugins.

## Decision

Adopt a **sharded instance storage model** with one instance per file and remove the extra project nesting level under `instances/`.

### 1. Canonical Project Root

Project instances MUST live directly under:

- `v5/topology/instances/`

`v5/topology/instances/home-lab/` is deprecated for active authoring.

### 2. One Instance Per File

Each instance is authored in its own YAML file.

Recommended layout:

- `v5/topology/instances/l1_devices/<instance-id>.yaml`
- `v5/topology/instances/l2_network/<instance-id>.yaml`
- ...

Each file contains exactly one instance row as top-level object:

```yaml
schema_version: 1
instance: inst.ethernet_cable.cat5e
group: l1_devices
layer: L1
class_ref: class.network.physical_link
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

### 3. Compiler Input Contract

`topology.yaml` path contract is extended:

- new canonical key: `paths.instances_root`
- legacy key: `paths.instance_bindings` (deprecated compatibility path)

Compiler loader MUST:

1. discover instance files under `instances_root` deterministically (lexicographic path order)
2. validate one-row-per-file contract
3. assemble in-memory combined payload compatible with existing plugin context:

```yaml
instance_bindings:
  <group>: [ ...rows... ]
```

This preserves current validator/compiler plugin interfaces while changing storage format.

### 4. Deterministic Merge and Validation Rules

Loader MUST enforce:

1. global uniqueness of `instance`
2. required fields (`instance`, `group`, `layer`, `class_ref`, `object_ref`)
3. group/layer consistency with `layer-contract.yaml`
4. deterministic row order in assembled payload (by `instance` within group)

### 5. Project Metadata

Project-level metadata that is not instance-specific (for example migration source pointers) SHOULD be moved to:

- `v5/topology/instances/project.yaml`

and not repeated in per-instance files.

### 6. Migration and Cutover

Migration is staged:

1. add sharded loader support with dual-read mode
2. provide splitter tool to convert legacy `instance-bindings.yaml` to per-instance files
3. switch default authoring and CI checks to `instances_root`
4. keep legacy single-file read as temporary compatibility mode
5. remove legacy path after cutover evidence

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

## References

- `v5/topology/topology.yaml`
- `v5/topology/instances/home-lab/instance-bindings.yaml`
- `v5/topology-tools/compiler_runtime.py`
- `v5/topology-tools/plugins/compilers/instance_rows_compiler.py`
- `v5/topology-tools/plugins/validators/reference_validator.py`
- `v5/topology-tools/plugins/validators/model_lock_validator.py`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TUC.md`
