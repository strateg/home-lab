# ADR 0076: Framework Distribution and Multi-Repository Extraction (Stage 2)

**Date:** 2026-03-20
**Status:** Proposed
**Depends on:** ADR 0075

---

## Context

After ADR 0075 Stage 1, framework and project are cleanly separated inside one repository.

Next architectural step is distribution and lifecycle separation:

1. Framework evolves independently.
2. Projects pin framework versions.
3. Builds remain reproducible and verifiable.

## Decision

Adopt staged extraction from monorepo separation to multi-repo distribution.

### Target Model

1. `infra-topology-framework` repository contains:
   - `class-modules/`
   - `object-modules/`
   - `topology-tools/`
   - `layer-contract.yaml`
   - `framework.yaml`

2. Project repositories contain:
   - `instances/`
   - `secrets/`
   - `project.yaml`
   - `framework.lock.yaml`
   - optional `overrides/`

3. Projects consume framework by one of supported methods:
   - git submodule (initial default)
   - package release (later)
   - local path (development only)

## Non-Goals

1. Changing class/object/instance semantics.
2. Replacing plugin microkernel contract.
3. Reworking ADR 0074 generator logic unrelated to path/dependency resolution.

## Dependency and Lock Contract

Each project MUST maintain `framework.lock.yaml` containing:

1. framework version
2. source (git/package)
3. immutable revision (commit or artifact digest)
4. integrity hash

Compiler MUST verify lock consistency before compile in strict mode.

## Diagnostics Reservation

To avoid conflicts with existing ranges, reserve:

- `E7821..E7829` for framework dependency/lock hard errors
- `W7830..W7839` for framework drift/deprecation warnings

Examples:

- `E7821`: framework dependency not resolvable
- `E7822`: framework lock missing in strict mode
- `E7823`: lock revision mismatch
- `E7824`: integrity hash mismatch
- `W7830`: framework update available but not pinned

## Migration Stages

### Stage 2.1: Framework Manifest and Packaging Readiness

1. Add `framework.yaml` contract.
2. Add packaging metadata.
3. Publish first pinned framework release.

### Stage 2.2: Project Repo Bootstrap

1. Create standalone project repository.
2. Import project data from `v5/projects/home-lab`.
3. Wire framework dependency + lock.

### Stage 2.3: CI and Operational Cutover

1. Enforce lock verification in CI.
2. Run compile/generate/validate gates against external framework dependency.
3. Document upgrade workflow (`pin`, `verify`, `update`).

## Consequences

Positive:

1. Independent release cadence for framework and projects.
2. Stronger ownership boundaries.
3. Reproducible dependency model.

Trade-offs:

1. Multi-repo operational overhead.
2. Version coordination burden.

## References

- ADR 0075: monorepo framework/project boundary (required precursor)
- ADR 0074: generator architecture in project-aware runtime
