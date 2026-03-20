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

Strict-policy inheritance from ADR 0075 is preserved:

1. no legacy fallback execution modes for framework/project resolution;
2. lock and compatibility verification are blocking checks in strict mode.

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
5. lock generation timestamp

Compiler MUST verify lock consistency before compile in strict mode.
Release CI MUST run in strict mode.

## Artifact Trust Baseline (Normative)

All distributed framework artifacts MUST satisfy minimum trust and reproducibility requirements.

Mandatory controls:

1. Locked dependency graph for release builds.
2. Provenance attestation attached to each artifact.
3. Cryptographic signature for release artifacts.
4. SBOM published with each release.
5. Verification step in consumer CI before execution.

Recommended hard errors:

- `E7825`: missing or invalid artifact signature
- `E7826`: missing provenance attestation
- `E7827`: lock contract violation
- `E7828`: SBOM missing

## Diagnostics Reservation

To avoid conflicts with existing ranges, reserve:

- `E7821..E7829` for framework dependency/lock hard errors

Compatibility diagnostics remain in ADR 0075 range:

- `E7811..E7813` for framework/project version and migration compatibility checks

Examples:

- `E7821`: framework dependency not resolvable
- `E7822`: framework lock missing in strict mode
- `E7823`: lock revision mismatch
- `E7824`: integrity hash mismatch
- `E7825`: missing or invalid artifact signature
- `E7826`: missing provenance attestation
- `E7827`: lock contract violation
- `E7828`: SBOM missing

Naming convention (normative):

1. Lock creation utility: `generate-framework-lock.py`
2. Lock verification utility: `verify-framework-lock.py`
3. Compiler path MUST reuse the same verification module as `verify-framework-lock.py` (no parallel verifier implementations).

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

1. Enforce strict lock verification in CI.
2. Run compile/generate/validate gates against external framework dependency.
3. Document upgrade workflow (`pin`, `verify`, `update`).
4. Validate rollback path in CI simulation before production cutover.

## Multi-Repo Cutover Readiness Gates

Cutover from integrated repository flow to multi-repository flow is Go/No-Go gated.

Go criteria:

1. Functional parity: golden tests pass with equivalent generated outputs.
2. Determinism: repeated builds produce equivalent artifacts under canonical normalization.
3. Compatibility: version-skew tests pass (`N`, `N-1`, `N+1` policy).
4. Rollback: documented and rehearsed rollback procedure validated in CI simulation.
5. Observability: diagnostics and dependency health metrics visible in dashboards.

No-Go triggers:

1. Any unresolved `E782x` in release candidate.
2. Unverified artifact provenance/signature.
3. Regression in generation determinism beyond approved threshold.

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
- Diagnostics catalog: `docs/diagnostics-catalog.md`
- Implementation plan: `adr/plan/0076-multi-repo-extraction-plan.md`
