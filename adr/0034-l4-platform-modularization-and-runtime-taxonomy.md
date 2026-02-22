# ADR 0034: L4 Platform Modularization (MVP) and Runtime Taxonomy

- Status: Proposed
- Date: 2026-02-22

## Context

`L4_platform` is currently monolithic (`topology/L4-platform.yaml`, ~176 lines) and mixes:

1. defaults and anchors,
2. resource profiles,
3. runtime workloads (`lxc`, `vms`),
4. template catalog.

Current scale is small (2 LXC, 0 VM, 5 templates), but edits already touch unrelated sections and increase review noise.

Critical implementation constraint:

- current L4 uses YAML anchors/aliases for shared defaults;
- `!include_dir_sorted` in `topology-tools/topology_loader.py` loads each file independently, so cross-file aliases are not valid;
- anchor migration is therefore a phase-0 blocker for safe split.

Cross-layer analysis:

- Downward (`L4 -> L1/L2/L3`):
  - `device_ref` to L1 devices.
  - `bridge_ref`/`network_ref`/`trust_zone_ref` to L2.
  - `storage_endpoint_ref`/`data_asset_ref` to L3.
- Upward (`L5/L6/L7 <- L4`):
  - stable `lxc.id`/`vms.id` are consumed by service runtime targeting and operations flows.

Goal: reduce cognitive load now without speculative structure.

## Responsibility Contract (L4)

L4 owns:

1. Workload instances and placement (`lxc`, `vms`).
2. Runtime provisioning templates.
3. Resource sizing policy (`resource_profiles`).

L4 does not own:

1. Service semantics and endpoint contracts (L5).
2. Monitoring policy semantics (L6).
3. Backup/runbook workflow semantics (L7).

## Alternatives Considered

### A. Keep monolithic `topology/L4-platform.yaml`

Rejected: highest short-term simplicity, but weak review ergonomics as L4 grows.

### B. Deep hierarchy by provider/node now

Rejected: overfits future scale and adds unnecessary navigation depth for current footprint.

### C. Full runtime taxonomy now (`container-platforms/*`, `host-operating-systems/*`)

Rejected: speculative (YAGNI) because those objects do not exist in current data model.

### D. Selected: MVP modularization of existing domains only

Selected: smallest change set with immediate maintenance benefit and no schema churn.

## Decision

Adopt a minimal modular structure for current, schema-backed L4 domains only.

Canonical structure (phase-1 scope):

```text
topology/L4-platform/
  defaults.yaml
  resource-profiles/
    profile-*.yaml
  templates/
    lxc/
      tpl-lxc-*.yaml
    vms/
      tpl-vm-*.yaml
  workloads/
    lxc/
      lxc-*.yaml
    vms/
      vm-*.yaml
```

No `owned/proxmox/provider/region/node` nesting in phase-1.
Host-level grouping is introduced only when at least one threshold is met:

1. `workloads/<type>/` has more than 12 files, or
2. more than 2 placement domains are active (for example, `proxmox` + cloud provider).

Threshold rationale:

1. terminal ergonomics: around 10-15 entries remain quickly scannable in standard CLI listing output;
2. cognitive load: after about 10-12 peer objects, navigation benefit from grouping becomes noticeable;
3. `12` is a policy threshold, not a hard technical limit.

### Composition Root Example

`topology/L4-platform.yaml` becomes a thin composition root:

```yaml
# L4 Platform composition root
_defaults: !include L4-platform/defaults.yaml

resource_profiles: !include_dir_sorted L4-platform/resource-profiles
lxc: !include_dir_sorted L4-platform/workloads/lxc
vms: !include_dir_sorted L4-platform/workloads/vms

templates:
  lxc: !include_dir_sorted L4-platform/templates/lxc
  vms: !include_dir_sorted L4-platform/templates/vms
```

### Anchor Migration Strategy (Phase-0 Blocker)

Current monolithic L4 uses aliases such as `*dns_default` and `*lxc_os_default` inside workloads.
Because alias resolution is file-local during parsing, these aliases cannot safely reference anchors defined in another file.

Migration approach:

1. Pre-split normalization:
   - replace alias-based fields in each workload with explicit inline values (`dns`, `os`, and other aliased blocks);
   - keep effective values identical to current resolved topology.
2. Split after normalization:
   - move normalized workload objects into `workloads/lxc/` and `workloads/vms/`.
3. Transition handling:
   - keep `_defaults` in `defaults.yaml` only as documentation/reference in phase-1;
   - do not use cross-file aliases in modular L4 files.
4. Guardrail:
   - add validator warning/error for YAML aliases under `topology/L4-platform/workloads/` (implementation task).

## Public API Contract (for L5/L6/L7)

Public/stable in L4 `v1`:

1. `lxc[].id`
2. `vms[].id`

Internal (not for upper-layer references):

1. `_defaults`
2. `resource_profiles`
3. `templates` and template-internal fields

Evolution policy:

1. Breaking ID contract change requires new ADR and one release deprecation window.
2. Removal must keep validation warning for at least one cycle before strict error.

## Naming Contract

1. Directory names: `kebab-case` (`resource-profiles/`).
2. YAML keys: `snake_case` (`resource_profiles`).
3. Object IDs:
   - workloads: `lxc-*`, `vm-*`
   - profiles: `profile-*`
   - templates: `tpl-lxc-*`, `tpl-vm-*`

## Prerequisites and Blockers

Phase-1 (this ADR) readiness:

1. `!include_dir_sorted` support in loader: ready.
2. Current schema keys (`lxc`, `vms`, `resource_profiles`, `templates`): ready.
3. Reference validation for L4 IDs: ready.

Deferred (out of phase-1 scope):

1. `host_operating_systems` schema and validators: blocker, not implemented.
2. `container_runtimes` / cluster taxonomy schema and generators: blocker, not implemented.

## Toolchain Impact Analysis

Schema and data model:

1. No phase-1 schema changes required (`L4_platform` keys remain identical).

Generators:

1. `topology-tools/scripts/generators/terraform/proxmox/generator.py` expects `L4_platform.lxc`, `L4_platform.vms`, `L4_platform.templates`, `L4_platform.resource_profiles`; behavior is unchanged after composition.
2. `topology-tools/scripts/generators/docs/generator.py` reads the same keys; behavior is unchanged after composition.

Validators:

1. Existing cross-layer ID/ref checks remain valid because object IDs and top-level keys do not change.
2. Additional validator tasks for implementation phase:
   - enforce L4 composition-root include contract in `topology/L4-platform.yaml`;
   - detect alias usage under modular workload files as migration guardrail.

Documentation:

1. `topology/MODULAR-GUIDE.md` must be updated when phase-1 is implemented:
   - remove `L4-platform.yaml` from "single-file layers",
   - add the approved L4 modular paths.

## RACI / Ownership

1. Responsible: topology maintainer (L4 file/module edits).
2. Accountable: architecture owner (layer contracts and ADR compliance).
3. Consulted: service owners (L5 runtime target impacts).
4. Informed: operations owner (deploy and runbook impact).

## Rollback Plan

If migration causes breakage:

1. Restore monolithic `topology/L4-platform.yaml` from git.
2. Remove `topology/L4-platform/` modular tree.
3. Run `python topology-tools/validate-topology.py --strict`.
4. Run `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate`.

## Consequences

Benefits:

1. Immediate reduction of merge conflicts in L4.
2. Lower cognitive load with one-object-per-file in high-churn areas.
3. No schema changes required for phase-1.

Trade-offs:

1. File count increases from 1 monolith to about 10-11 files in current state.
2. Include contracts become part of validator governance.

Success metrics:

1. Adding one LXC changes 1-4 files in L4 (`workloads/lxc/lxc-*.yaml` plus optional profile/template updates).
2. Typical LXC introduction changes 0-2 additional files in L3 when new data assets/storage bindings are required.
3. Median diff size for workload-only changes stays under 60 lines.
4. Zero behavioral diff in generated outputs after phase-1 split.

## Deferred Extension Path

When first real object appears, add only the needed domain:

1. Add `host_operating_systems` only when OS lifecycle tracking is modeled as objects.
2. Add container runtime taxonomy only when at least one runtime/cluster object exists.
3. L5 one-object-per-file modularization is a separate decision and should be considered only after its own scale threshold is reached.
4. Document each added domain via follow-up ADR (expected next: ADR0035+).

## References

- `topology/L4-platform.yaml`
- `topology/MODULAR-GUIDE.md`
- [0031](0031-layered-topology-toolchain-contract-alignment.md)
- [0032](0032-l3-data-modularization-and-layer-contracts.md)
- [0033](0033-toolchain-contract-rebaseline-after-modularization.md)
- `topology-tools/topology_loader.py`
- `topology-tools/validate-topology.py`
- `topology-tools/scripts/validators/checks/references.py`
- `topology-tools/scripts/generators/terraform/proxmox/generator.py`
