# ADR 0075: Monorepo Framework/Project Boundary (Stage 1)

**Date:** 2026-03-20
**Status:** Proposed
**Depends on:** ADR 0062, ADR 0071, ADR 0072
**Blocks:** ADR 0074 remaining rollout tasks (project-aware generation)

---

## Context

v5 already has a reusable framework layer and a project-specific data layer, but both are still mixed under `v5/topology/`.

Current state:

- Framework assets (class/object contracts, layer model, compiler contracts) live in `v5/topology/` and `v5/topology-tools/`.
- Home-lab project state (instances, secrets coupling, runtime assumptions) is still wired by `paths.instances_root` in `v5/topology/topology.yaml`.
- Generator runtime from ADR 0074 is implemented, but output and runtime assembly still assume a single project context.

This prevents clean multi-project operation in one repository and creates coupling between framework evolution and one deployment inventory.

## Scope Split (Normative)

ADR 0075 is intentionally limited to **Stage 1 (monorepo separation)**.

Included here:

1. Framework/project boundary inside current repository.
2. Project-aware path resolution and validation.
3. Strict project-only contract (no legacy `paths.*` fallback semantics).

Explicitly out of scope:

1. Framework extraction to a dedicated repository.
2. Package/submodule distribution strategy.
3. Cross-repo versioning/lock transport.

Those are handled by **ADR 0076**.

## Decision

Adopt a two-root monorepo model:

1. `v5/topology/` + `v5/topology-tools/` are the **framework root**.
2. `v5/projects/<project-id>/` is the **project root**.

Canonical project root for current deployment becomes `v5/projects/home-lab/`.

### Canonical Layout (Stage 1)

```
v5/
├── topology/                      # framework contracts
│   ├── class-modules/
│   ├── object-modules/
│   ├── layer-contract.yaml
│   ├── model.lock.yaml
│   └── profile-map.yaml
├── topology-tools/                # compiler/plugins/templates
└── projects/
    └── home-lab/
        ├── project.yaml
        ├── instances/
        │   └── <layer-bucket>/<group>/<instance>.yaml
        ├── secrets/               # project-local secret sidecars
        └── _legacy/               # archived migration artifacts
```

### Root Manifest Contract

`v5/topology/topology.yaml` MUST define explicit `framework:` and `project:` sections.

Legacy `paths.*` resolution is not part of the target system contract for this ADR and MUST NOT be used by default runtime paths.

```
version: 5.1.0
model: class-object-instance

framework:
  root: v5/topology
  class_modules_root: v5/topology/class-modules
  object_modules_root: v5/topology/object-modules
  layer_contract: v5/topology/layer-contract.yaml
  model_lock: v5/topology/model.lock.yaml
  profile_map: v5/topology/profile-map.yaml
  capability_catalog: v5/topology/class-modules/router/capability-catalog.yaml
  capability_packs: v5/topology/class-modules/router/capability-packs.yaml

project:
  active: home-lab
  projects_root: v5/projects
```

### Project Manifest Contract

`v5/projects/<project-id>/project.yaml` is required.

```
schema_version: 1
project: home-lab
status: production

instances_root: instances
secrets_root: secrets

generation:
  output_mode: project-qualified
```

### Validation and Diagnostics

New code range for framework/project separation is reserved to avoid collision with existing network codes:

- `E7801..E7809`

Reserved semantics:

- `E7801`: invalid/missing `project` section in root manifest
- `E7802`: active project not found under `projects_root`
- `E7803`: invalid `project.yaml` schema
- `E7804`: project `instances_root` missing
- `E7805`: project `secrets_root` missing/invalid
- `E7806`: project path escapes repository root
- `E7807`: cross-project reference detected
- `E7808`: legacy `paths.*` contract detected (unsupported)

## Compatibility Contract (Normative)

Framework and project compatibility is explicit and machine-validated.

Project metadata in `project.yaml` MUST define:

- `project_schema_version` (SemVer)
- `project_min_framework_version` (SemVer lower bound)
- `project_max_framework_version` (optional upper bound, inclusive)
- `project_contract_revision` (integer, monotonic)

Framework metadata MUST define:

- `framework_api_version` (SemVer)
- `supported_project_schema_range` (SemVer range)

Generation/compile MUST stop with an error when:

1. framework version is below `project_min_framework_version`;
2. project schema is outside `supported_project_schema_range`;
3. contract revision requires migration steps not applied.

Recommended error codes:

- `E7811`: Framework version too old
- `E7812`: Project schema not supported
- `E7813`: Contract migration required

## Why ADR 0074 Must Follow ADR 0075

ADR 0074 open rollout tasks (runtime assembly hardening, final path ownership, cutover runbooks) are path-sensitive.

If done before project separation, they must be reworked after project separation.

Therefore sequence is fixed:

1. Implement ADR 0075 Stage 1.
2. Rebind ADR 0074 remaining tasks to project-aware paths and outputs.

## Migration Plan (Stage 1)

### Phase 1: Contract Introduction (Breaking by Design)

1. Add `framework:` and `project:` parsing to compiler runtime.
2. Add diagnostics `E780x` and tests.
3. Fail fast on legacy `paths.*` usage (`E7808`).

### Phase 2: Directory Migration

1. Move `v5/topology/instances/` -> `v5/projects/home-lab/instances/`.
2. Move legacy migration artifacts to `v5/projects/home-lab/_legacy/`.
3. Move secrets sidecars to `v5/projects/home-lab/secrets/`.
4. Update root manifest to project path.

### Phase 3: Tooling and Script Rewire

1. Update validators/scripts that hardcode `v5/topology/instances`.
2. Update scaffold and lane checks to expect project root.
3. Remove compatibility adapters that preserve legacy `paths.*` behavior.

### Phase 4: Closure

1. Enforce project-only resolution in all runtime entrypoints.
2. Remove stale documentation paths and deprecated settings.
3. Record cutover baseline for ADR 0074 sequencing.

## Consequences

Positive:

1. Clear ownership boundary: framework vs deployment state.
2. Enables multiple projects in one repo without instance pollution.
3. Provides stable foundation for ADR 0074 project-aware generator execution.

Trade-offs:

1. One-time path migration across scripts/tests/docs.
2. Hard cutover requires coordinated updates without fallback safety net.

## Implementation Checklist

- [ ] Introduce `framework/project` manifest contract in compiler runtime.
- [ ] Add `E780x` catalog entries and tests.
- [ ] Create `v5/projects/home-lab/project.yaml`.
- [ ] Move `instances` to project root.
- [ ] Move/archive `_legacy-home-lab` under project root.
- [ ] Rewire scripts and validation gates to project root.
- [ ] Enable project-aware secrets root.
- [ ] Remove legacy `paths.*` readers from runtime path resolution.
- [ ] Publish cutover note for ADR 0074 sequencing.

## References

- ADR 0062: Class/Object/Instance modular architecture
- ADR 0071: sharded instance source model
- ADR 0072: SOPS/age secrets sidecar model
- ADR 0074: generator architecture (execution sequence depends on this ADR)
- ADR 0076: framework distribution and multi-repo extraction (Stage 2)
- Master migration plan: `adr/plan/0075-0074-master-migration-plan.md`
- Diagnostics catalog: `docs/diagnostics-catalog.md`
