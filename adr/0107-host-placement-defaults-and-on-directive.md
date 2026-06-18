# ADR 0107: Host Placement Defaults with `@on` Directive

- Status: **Implemented**
- Date: 2026-06-17
- Implemented: 2026-06-18
- Extends: ADR 0068 (Object YAML Template with Typed Instance Placeholders)
- Related: ADR 0062 (C-O-I Architecture), ADR 0071 (Sharded Instances), ADR 0086 (Plugin Runtime Contract), ADR 0087 (host_ref DAG Validator)
- Analysis: SWOT P04 (Host-level repetition), SPC Protocol
- Review: 2026-06-17 (tech-lead-architect — gaps G1–G8 identified, D9–D13 added)

## Context

### Problem Statement

ADR 0068 defines Object→Instance inheritance via placeholder system (`@required`, `@optional`), but does not address host-level field repetition. Diagnostic analysis shows:

- 9 LXC instances on srv-gamayun share 14 identical fields (63.6% repetition)
- Repeated fields: `network.bridge_ref`, `network.vlan_ref`, `dns.*`, `trust_zone_ref`, `storage.pool_ref`
- Total redundancy: ~258 field occurrences across 23+ instances on 3 hosts
- Average instance file: 57 lines, of which 35 lines (61%) are host-invariant

### Root Cause

No mechanism exists for workloads to inherit defaults from their placement host. Current merge order:

```
Class.defaults → Object.defaults → Instance.overrides
```

Missing: Host-scoped defaults injection between Object and Instance.

### Affected Hosts

| Host | Workload Type | Instances | Repeated Fields |
|------|---------------|-----------|-----------------|
| srv-gamayun | LXC | 9 | 14 per instance |
| srv-orangepi5 | Docker | ~10 | ~10 per instance |
| rtr-mikrotik-chateau | Docker (RouterOS) | ~4 | ~8 per instance |

## Decision

### D1: Host Instance `workload_defaults` Section

Host device instances (and intermediate container hosts) MAY define a `workload_defaults` section containing default values for workloads placed on that host.

```yaml
# projects/home-lab/topology/instances/devices/srv-gamayun.yaml
@instance: srv-gamayun
@extends: obj.proxmox.ve
@version: 1.0.0

# Existing fields...
firmware_ref: inst.firmware.uefi.generic.x86_64
os_refs:
  - inst.os.proxmox.ve.9

# NEW: Workload placement defaults
workload_defaults:
  trust_zone_ref: inst.trust_zone.servers
  network:
    bridge_ref: inst.bridge.vmbr0
    vlan_ref: inst.vlan.servers
    gateway: 10.0.30.1
  dns:
    nameserver: 192.168.88.1
    searchdomain: home.local
  storage:
    default_pool_ref: inst.storage.pool.local_lvm
  cloudinit:
    enabled: true
  ansible:
    enabled: true
```

### D2: `@on` Directive Syntax

Extend ADR 0068 placeholder grammar with host inheritance directive:

```
@on:<source>.<path>[?][:<default>]

<source>  := host | root | host[N]
<path>    := dotted.path.to.field
?         := optional modifier (no error if missing)
<default> := fallback value if path not found
```

| Source | Meaning |
|--------|---------|
| `host` | Immediate host (resolved via `host_ref`) |
| `root` | Physical device at chain root (traverse all `host_ref`) |
| `host[N]` | N levels up the host chain (host[1] = immediate, host[2] = parent) |

Examples:

```yaml
# Object template
defaults:
  trust_zone_ref: @on:host.trust_zone_ref
  network:
    bridge_ref: @on:host.network.bridge_ref
    gateway: @on:host.network.gateway
  dns:
    nameserver: @on:host.dns.nameserver?
    searchdomain: @on:host.dns.searchdomain?:local

  # For nested hosts (Docker in LXC):
  physical_dns: @on:root.dns.nameserver
```

### D3: Extended Merge Order

`@on` markers are **placeholders** in the object template — they are the object author's explicit grant of authority to the host for specific fields. They are NOT a new merge priority level that lets host data override object design decisions. Where the object template defines a static field without a placeholder, the host has no authority over it.

The correct mental model:

```
Class.defaults           (static, non-overridable)
  → Object.template
      ├─ static fields   (fixed for all instances of this object type)
      ├─ @on:host.X      → resolved from Host.workload_defaults
      ├─ @required       → resolved from Instance.overrides
      └─ @optional       → resolved from Instance.overrides (or default)
```

Instance overrides always win at their level (ADR 0062 §2). An instance may explicitly override an `@on`-resolved value by supplying a non-null value for that field. See D10 for `null` override semantics.

Constraint: `@on` resolution happens in the **on-prepare sub-stage** (D12), after `object_ref` is resolved and `ctx.objects` is available, and before `instance_rows_validate`.

### D4: Nested Host Support

Workloads may be nested (e.g., Docker container inside LXC container on Proxmox):

```
srv-gamayun (Proxmox)          workload_defaults: { network: vmbr0, ... }
  └── lxc-docker (LXC)         workload_defaults: { network: docker0, ... }
        └── docker-myapp       host_ref: lxc-docker
```

Resolution rules:

1. `@on:host.X` resolves from immediate `host_ref` target
2. `@on:root.X` traverses `host_ref` chain to physical device
3. `@on:host[N].X` goes N levels up (host[1] = immediate)

```yaml
# docker-myapp.yaml
@instance: docker-myapp
host_ref: lxc-docker

network:
  bridge_ref: @on:host.network.bridge_ref    # → docker0 (from lxc-docker)
dns:
  nameserver: @on:root.dns.nameserver        # → 192.168.88.1 (from srv-gamayun)
```

### D5: Compiler Resolution Rules

1. When the `@on` resolver encounters `@on:<source>.<path>` in an object template field:
   - Resolve the instance's `host_ref` field to the host instance's raw data
   - For `root`: traverse `host_ref` chain until `host_ref` is null/absent (physical device)
   - Navigate `<path>` within the host's `workload_defaults` section
   - Substitute the resolved value into the prepared row, or emit the appropriate error code

2. Resolution happens in the **on-prepare sub-stage** (a new compiler plugin at order ~41.5, between `instance_rows_prepare` and `instance_rows_validate` — see D12). This is the only point in the pipeline where both `object_ref` (resolved at `prepare`) and `ctx.objects` / raw `ctx.instance_bindings` (for host data) are simultaneously available.

3. Resolution requires a pre-built `host_workload_defaults_index` (host_id → workload_defaults dict), produced by `instance_host_index_compiler` during the init phase (order ~35). The index MUST be built in topological order (leaf-to-root over the `host_ref` DAG) to support nested hosts whose `workload_defaults` may themselves contain `@on` markers — see D13.

4. Effective model MUST NOT contain unresolved `@on` directives after the on-prepare sub-stage completes.

5. `@on` markers are only valid in object templates. An `@on` marker found in a raw instance file MUST emit E3201 (invalid annotation context).

### D6: Error Codes

| Code | Severity | Condition |
|------|----------|-----------|
| `E6810_ON_PATH_NOT_FOUND` | Error | Required `@on:host.X` path missing in workload_defaults |
| `E6811_ON_HOST_NOT_RESOLVED` | Error | Instance has no valid host_ref |
| `E6812_ON_CIRCULAR_REFERENCE` | Error | Circular host_ref chain detected during `@on` resolution |
| `E6813_ON_ROOT_NOT_FOUND` | Error | Cannot resolve root host (no chain termination) |
| `W6814_ON_OPTIONAL_MISSING` | Warning | Optional `@on:host.X?` path not found (uses default) |
| `E6815_ON_NULL_OVERRIDE` | Error | Instance explicitly sets an `@on`-marked field to `null` (see D10) |

**Note on code range**: E6808 and E6809 are intentionally unallocated (reserved for future host-chain diagnostics). E6812 is **complementary** to E7896 (host_ref DAG cycle detection in validate stage) — both remain active; see D11.

### D7: Instance Simplification

After migration, instances specify only unique values:

```yaml
# BEFORE (57 lines, 61% redundant)
@instance: lxc-postgresql
@extends: obj.proxmox.lxc.debian12.postgresql
host_ref: srv-gamayun
trust_zone_ref: inst.trust_zone.servers      # REPEATED
os_refs: [inst.os.debian.12.proxmox.lxc]     # REPEATED
network:
  interface: eth0                             # REPEATED
  bridge_ref: inst.bridge.vmbr0              # REPEATED
  vlan_ref: inst.vlan.servers                # REPEATED
  gateway: 10.0.30.1                         # REPEATED
  ip: 10.0.30.10/24
  firewall: false                            # REPEATED
dns:
  nameserver: 192.168.88.1                   # REPEATED
  searchdomain: home.local                   # REPEATED
cloudinit:
  enabled: true                              # REPEATED
  user: postgres
ansible:
  enabled: true                              # REPEATED
  playbook: postgresql.yml
storage:
  rootfs:
    pool_ref: inst.storage.pool.local_lvm   # REPEATED
    size_gb: 8
# ... ~57 lines total

# AFTER (~25 lines, unique values only)
@instance: lxc-postgresql
@extends: obj.proxmox.lxc.debian12.postgresql
host_ref: srv-gamayun
vmid: 200
hostname: postgresql-db
boot:
  startup_order: 10
resource_profile_ref: rp.lxc.balanced
network:
  ip: 10.0.30.10/24
storage:
  rootfs:
    size_gb: 8
  volumes:
    - mount_path: /var/lib/postgresql/data
      size_gb: 20
cloudinit:
  user: postgres
ansible:
  playbook: postgresql.yml
```

### D8: Migration Strategy

**Phase 1 (`warn`):**
- Add `workload_defaults` to host instances
- Update object templates with `@on` placeholders
- Compiler warns on redundant instance fields that match host defaults
- Existing instances continue to work (explicit values override)

> ⚠️ **Note**: The Phase 1 redundancy warning requires the same `host_workload_defaults_index` infrastructure as `@on` resolution itself (D5 §3). This is non-trivial: the warning pass performs a cross-instance comparison against the host index. It is NOT a low-effort stub — it should be implemented together with the `instance_host_index_compiler` (D12), not as a separate prior step.

**Phase 2 (`enforce`):**
- Remove redundant fields from instances
- `@on` resolution required for all placeholder-marked paths
- Full boilerplate reduction achieved

### D9: `host_ref` and `workload_defaults` as Reserved Row Keys

`host_ref` is a first-class reserved field on instance rows, semantically equivalent to `object_ref`. It MUST be added to `_RESERVED_ROW_KEYS` in `instance_rows_compiler.py` so that it is promoted to a top-level column in `normalized_rows` rather than falling through to `extensions`.

Consequences of D9:
- All validators currently using the dual-lookup pattern (`extensions.host_ref || row.host_ref`) MUST be updated to read `row.host_ref` directly. This is a mechanical change covered by the existing test suite.
- `workload_defaults` MUST also be added to `_RESERVED_ROW_KEYS` and stripped from workload rows during normalization. It is a host-only field and MUST NOT propagate to generators via `extensions`. Exception: an instance that is simultaneously a workload and a host (e.g., `lxc-docker` in Docker-in-LXC) retains `workload_defaults` for the host-index build pass, but it is stripped before the row reaches generators.

### D10: `null` Override Semantics for `@on`-Marked Fields

An instance MUST NOT set an `@on`-marked field to `null`. In alignment with ADR 0068 §Edge Cases rule 4, `null` on a placeholder-marked field is invalid.

- **Omission** of the field: host default is applied via `@on` resolution.
- **Explicit non-null value**: instance override wins; host default is superseded.
- **Explicit `null`**: rejected with `E6815_ON_NULL_OVERRIDE` (error).

This prevents ambiguity between "intentionally absent" and "broken null injection."

### D11: Relationship to `host_ref_dag_validator` (ADR 0087)

`E6812_ON_CIRCULAR_REFERENCE` (compile-time, in `instance_rows_on_prepare_compiler`) and `E7896` (`host_ref_dag_validator`, validate-time) are **complementary, not redundant**:

- E6812 fires only when `@on` resolution traverses a cycle during workload default injection (compile stage).
- E7896 fires for all workloads regardless of `@on` usage (validate stage).

Both MUST remain active. To prevent divergent implementations, cycle detection and host-chain traversal logic MUST be extracted into a shared utility module `topology-tools/host_chain_utils.py` and imported by both the `@on` resolver and the DAG validator.

### D12: Plugin Decomposition (Corrects D5 Implementation Location)

The `@on` resolution MUST NOT be added to `instance_rows_compiler.py` directly. The correct decomposition follows the existing shim pattern:

```
order ~35  instance_host_index_compiler   (init phase)
           produces: host_workload_defaults_index  [pipeline_shared]

order  39  instance_rows_secret_resolve   → secret_resolved_rows
order  40  instance_rows_resolve          → resolved_rows
order  41  instance_rows_prepare          → prepared_rows
order  41.5 instance_rows_on_prepare      → on_prepared_rows      ← NEW
order  42  instance_rows_validate         → validated_rows  (consumes on_prepared_rows, fallback: prepared_rows)
order  43  instance_rows                  → normalized_rows  [pipeline_shared]
```

`instance_rows_on_prepare_compiler.py` manifest contract:
```yaml
id: base.compiler.instance_rows_on_prepare
kind: compiler
stage: compile
phase: run
depends_on:
  - base.compiler.instance_rows_prepare
  - base.compiler.instance_host_index
consumes:
  - from_plugin: base.compiler.instance_rows_prepare
    key: prepared_rows
    required: true
  - from_plugin: base.compiler.instance_host_index
    key: host_workload_defaults_index
    required: true
produces:
  - key: on_prepared_rows
    scope: stage_local
execution_mode: main_interpreter
```

`execution_mode: main_interpreter` is required because the plugin needs `ctx.objects` for object template lookup. Under ADR 0097's subinterpreter model, `PluginInputSnapshot` carries only declared `consumes` payloads — `ctx.objects` is not available in subinterpreter mode.

**Test blast radius**: Adding an optional sub-stage between `prepare` and `validate` does NOT require changes to existing test files, as long as `instance_rows_validate` retains its fallback to `prepared_rows` when `on_prepared_rows` is absent (consistent with the existing fallback pattern throughout the pipeline).

### D13: Two-Pass Requirement for Nested Host Resolution

D4 describes Docker-in-LXC nesting where an intermediate host (`lxc-docker`) may itself have `workload_defaults` containing `@on:host.X` markers pointing to its own host (`srv-gamayun`).

The `instance_host_index_compiler` (D12) MUST resolve host `workload_defaults` before workload `@on` markers are resolved. Resolution order:

1. Build raw `host_ref` DAG from all instances in `ctx.instance_bindings`
2. Topologically sort the DAG (leaf = physical device, root = deepest nested workload)
3. Resolve `workload_defaults` for each host in leaf-to-root order: if a host's `workload_defaults` contains `@on` markers, resolve them against the host's own `host_ref` before publishing the index entry
4. Publish the fully resolved `host_workload_defaults_index`

Circular `host_ref` chains detected during step 1 MUST emit E6812 and abort index construction for the affected chain (not the entire build).

## Consequences

### Positive

1. **-60% instance boilerplate**: 14 repeated fields eliminated per instance
2. **DRY compliance**: Host-scoped configuration defined once
3. **Consistency**: Host changes propagate automatically to all workloads
4. **ADR 0062 preserved**: C-O-I hierarchy unchanged (host is data source, not hierarchy level)
5. **Nested host support**: Docker-in-LXC scenarios properly modeled
6. **Explicit inheritance**: `@on` markers make data flow visible

### Trade-offs

1. **Indirection**: Must check host instance for some field values
2. **Compiler complexity**: New on-prepare sub-stage plugin + host-index init plugin; `@on` resolution requires topological sort over `host_ref` DAG for nested hosts
3. **Migration effort**: 4 hosts + ~6 objects + 23 instances
4. **Reserved key change**: Adding `host_ref` and `workload_defaults` to `_RESERVED_ROW_KEYS` requires updating all validators that currently use dual-lookup (`extensions.host_ref || row.host_ref`) — mechanical but non-trivial

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Circular host_ref | Medium | E6812 at compile time + E7896 at validate time (D11); shared logic in `host_chain_utils.py` |
| Missing workload_defaults | Medium | E6810 error + warn phase for adoption |
| Over-inheritance | Low | Explicit `@on` markers (not implicit) |
| Nested host two-pass resolution | High | D13: topological sort in `instance_host_index_compiler`; host `workload_defaults` resolved before workloads |
| `host_ref` in extensions (existing convention) | High | D9: add to `_RESERVED_ROW_KEYS`; update validator dual-lookups — covered by existing test suite |
| Two divergent cycle-detection implementations | Medium | D11: extract shared `host_chain_utils.py` |
| Phase 1 warning more complex than expected | Medium | D8 note: implement together with host-index plugin, not separately |
| `null` override ambiguity with ADR 0068 | Low | D10: explicitly reject null overrides on `@on`-marked fields (E6815) |

## Implementation

### Files to Modify

| Category | File(s) | Changes |
|----------|---------|----------|
| Compiler (new) | `plugins/compilers/instance_rows_on_prepare_compiler.py` | New ~50-line shim at order 41.5; resolves `@on` markers using `on_prepared_rows`; consumes `prepared_rows`; produces `on_prepared_rows` |
| Compiler (new) | `plugins/compilers/instance_host_index_compiler.py` | New init-phase compiler at order ~35; builds `host_workload_defaults_index` from raw `ctx.instance_bindings` using topological sort over `host_ref` DAG; produces `pipeline_shared` key |
| Compiler (existing) | `instance_rows_validate_compiler.py` | Add fallback: consume `on_prepared_rows` before `prepared_rows` |
| Compiler (existing) | `instance_rows_compiler.py` | Add `host_ref`, `workload_defaults` to `_RESERVED_ROW_KEYS`; no `@on` logic added here |
| Core library (new) | `topology-tools/host_chain_utils.py` | Shared host_ref chain traversal + cycle detection (deduplicated from `host_ref_dag_validator.py`) |
| Validator (existing) | `instance_placeholder_validator.py` | Add E6810–E6815 post-resolution checks; D8 Phase 1 redundancy warnings (consumes `host_workload_defaults_index`) |
| Validators (existing) | `host_ref_dag_validator.py` + others using dual-lookup | Migrate `extensions.host_ref || row.host_ref` to `row.host_ref` after D9 reserved-key change |
| Format registry | `instance-field-formats.yaml` | `@on` format definition |
| Host instances | 4 files | Add `workload_defaults` section |
| Object templates | ~6 files | Replace `@required:ref` with `@on:host.X` for host-scoped fields |
| Workload instances | 23+ files | Remove redundant fields (Phase 2 only) |
| AI Rules | `docs/ai/rules/topology-model.md` | Add `@on` directive guidance |
| AI Rules (new) | `docs/ai/rules/host-placement.md` | New rule pack for `workload_defaults` authoring |

### D14: AI Agent Rule Pack

Create/update AI agent rules for `@on` directive usage:

**Update `docs/ai/rules/topology-model.md`:**
```markdown
## Host Placement Defaults (@on directive)

| Rule | Key Point |
|------|-----------|
| workload_defaults | Define in host instance, not object |
| @on:host.X | Inherit from immediate host_ref |
| @on:root.X | Inherit from physical device |
| Nested hosts | LXC/VM can define own workload_defaults |
```

**Create `docs/ai/rules/host-placement.md`:**
- When to use `@on` vs explicit values
- workload_defaults structure for different host types
- Nested host resolution order
- Error codes E6810-E6815 troubleshooting

**Update `docs/ai/ADR-RULE-MAP.yaml`:**
```yaml
ADR-0107:
  rule_packs: [topology-model, host-placement]
  triggers:
    - "workload_defaults"
    - "@on:host"
    - "@on:root"
    - "host_ref inheritance"
```

### Estimated Impact

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Avg instance lines | 57 | ~25 | **-56%** |
| Repeated field occurrences | 258 | 0 | **-100%** |
| Host files modified | 0 | 4 | +4 |
| Object templates modified | 0 | ~6 | +6 |

## References

- ADR 0062: Modular C-O-I Architecture
- ADR 0068: Object YAML Template with Placeholders (governs `@on` null semantics via §Edge Cases)
- ADR 0071: Sharded Instance Files
- ADR 0086: Plugin Runtime Contract (stage affinity, manifest contracts)
- ADR 0087: host_ref DAG Validator (E7896 cycle detection — complementary to E6812, see D11)
- ADR 0088: Semantic Keyword Registry
- ADR 0096: AI Agent Rulebook (governs rule pack structure)
- ADR 0097: Actor-Style Dataflow Runtime (subinterpreter model — informs D5 `main_interpreter` requirement)
- SWOT Analysis: P04 (Host-level repetition)
- SPC Analysis: `docs/analysis/TOPOLOGY-ONTOLOGY-SWOT-2026-06-17.md`
- AI Rules: `docs/ai/rules/topology-model.md`, `docs/ai/rules/host-placement.md` (D14)

## Implementation Status

### Completed (2026-06-18)

| Component | Commit | Status |
|-----------|--------|--------|
| `instance_host_index_compiler.py` | ab197807 | ✅ Builds host_workload_defaults_index |
| `instance_rows_on_prepare_compiler.py` | ab197807, c54fb4f2 | ✅ Resolves @on in instance + object defaults |
| `host_chain_utils.py` | ab197807 | ✅ Shared host_ref chain traversal |
| `instance_rows_compiler.py` | 907a5cc3 | ✅ host_ref in normalized rows |
| `field_annotations.py` | 77e4a85e | ✅ Skip @on in annotation parsing |
| srv-gamayun workload_defaults | 77e4a85e | ✅ 11 host-scoped fields |
| srv-orangepi5 workload_defaults | 42c85dae | ✅ Docker host defaults |
| rtr-mikrotik-chateau workload_defaults | b7c43823 | ✅ RouterOS container host defaults |
| Docker object template | 42c85dae | ✅ @on directives in defaults |
| RouterOS container object template | b7c43823 | ✅ obj.routeros.container.generic |
| Strip None values in @on merge | 42c85dae | ✅ Prevents validator errors for host-specific fields |
| LXC object templates (10 files) | c54fb4f2 | ✅ @on directives in defaults |
| LXC instances simplified | 77e4a85e | ✅ ~77% field reduction |
| Docker instances simplified | b7c43823 | ✅ Removed redundant os_refs, network, gateway |
| Integration tests | c54fb4f2 | ✅ 5 test cases |
| AI rules (D14) | 7dc516e4 | ✅ host-placement.md v1.1, HPL-001 |

### Measured Impact

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Compilation errors | 12 | 0 | **-100%** |
| Compilation warnings | 9 | 0 | **-100%** |
| Avg LXC instance lines | ~50 | ~25 | **-50%** |
| Redundant field declarations | 117 | 0 | **-100%** |

### Remaining Work

| Item | Priority | Notes |
|------|----------|-------|
| Phase 1 redundancy warnings | Low | Optional diagnostic for detecting duplicate fields in instances |
