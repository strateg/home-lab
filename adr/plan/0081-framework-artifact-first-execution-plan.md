# ADR 0081: Framework Artifact-First Execution Plan

**Date:** 2026-03-29
**Status:** Active
**Implements:** `adr/0081-framework-runtime-artifact-and-1-n-project-repository-model.md`
**Depends on:** ADR0076 Stage 2 baseline + Phase 13 assets

---

## Objective

Make artifact-first framework consumption the canonical model for framework + multiple projects (1:N). Project + framework artifact = sufficient for complete artifact generation pipeline.

---

## Current State (2026-03-29)

1. Framework/project separation and strict diagnostics are implemented (ADR 0075).
2. Phase 13 extraction tooling exists (`extract-framework-history.py`, `bootstrap-project-repo.py`).
3. Six-stage lifecycle and six plugin families are implemented in runtime contracts (ADR 0080).
4. Baseline strict gates are currently red due to lock integrity drift (`E7824`).
5. v4 is in `archive/v4/`, v5 content is at repository root.
6. Framework distribution spec exists in `topology/framework.yaml`.
7. Project-level plugin root is contractually defined but not enforced in runtime.

---

## Active Implementation Track (2026-04-09)

Cross-ADR bridge to keep artifact-first extraction aligned with SOHO product contracts (ADR0089-0091):

- [x] Split rehearsal lane is automated (`task framework:split-rehearsal`).
- [x] Phase13 evidence bundle includes split rehearsal (`task framework:phase13-evidence`).
- [x] Split rehearsal summary validates ADR0091 handover/report contract and D3 domain coverage.
- [ ] Add deterministic parity check between monorepo and extracted `operator-readiness.json` semantics.
- [ ] Promote split-rehearsal summary publication as mandatory CI artifact in Phase13 gate.
- [ ] Add Go/No-Go guard: any critical `E794x` in extracted-mode evidence is No-Go for cutover.

Execution priority now:

1. Finish P0 baseline recovery (strict green baseline).
2. Close P2.5 extracted-mode compatibility tests.
3. Close P3 trust hardening (package verification).
4. Execute P5 cutover checklist with new SOHO bridge gates.

---

## Target State

1. Framework source repository produces runtime-only artifact (classes, objects, plugins, toolchain — no tests/ADR/dev-docs).
2. Project repositories consume framework as package artifact dependency.
3. Plugin discovery chain: kernel → framework → class → object → project.
4. Project plugin root is first-class for all six families.
5. Strict CI verifies lock + integrity + compile/generate determinism.

---

## Priority Workstreams

### P0 — Baseline Recovery (Blocker)

- [ ] Refresh and commit valid `framework.lock.yaml` for baseline project.
- [ ] Restore green strict gates (`E7824` resolution).
- [ ] Store baseline evidence snapshot under `build/diagnostics/`.

Gate commands:

```powershell
task framework:lock-refresh
task framework:strict
task validate:v5-passthrough
```

Definition of Done:

1. No blocking `E782x` in baseline.
2. Strict and validate gates are green in current repository.

---

### P1 — Runtime Artifact Boundary Hardening

- [ ] Verify `topology/framework.yaml` distribution spec covers exactly §2.1 contents from ADR 0081.
- [ ] Add explicit exclusions to distribution spec per ADR 0081 §2.2 (tests, adr, docs, projects, archive, dev tooling, AI config, IDE config, generated outputs, bytecode).
- [ ] Add artifact content contract tests: assert included files, assert excluded files.
- [ ] Build trial artifact and verify against contract.

Gate commands:

```powershell
task framework:release-build FRAMEWORK_VERSION=5.0.0-rc1
task framework:verify-artifact-contents
```

Definition of Done:

1. Built artifact contains only runtime contract assets per ADR 0081 §2.1.
2. Artifact excludes all items listed in ADR 0081 §2.2, verified by automated tests.

---

### P2 — Project Plugin Root Completion

- [ ] Implement project-level plugin manifest discovery (`<project-root>/plugins/plugins.yaml`).
- [ ] Extend `plugin_manifest_discovery.py` with project level in merge chain (kernel → framework → class → object → **project**).
- [ ] Add stage-family affinity validation for project plugins.
- [ ] Add tests for project plugin discovery, ordering, and ID conflict detection.
- [ ] Document project plugin authoring in runtime reference.
- [ ] Keep global plugin-id uniqueness (no cross-level shadowing).

Gate commands:

```powershell
task test:default
task framework:strict
```

Definition of Done:

1. Project plugins are discovered, loaded, and executed for all six families.
2. Plugin discovery order matches ADR 0081 §3.4.
3. Duplicate plugin IDs across any loaded manifest fail as hard errors.

---

### P2.5 — Topology Execution Environment Script Compatibility

- [ ] Add contract tests that monorepo and standalone project modes use equivalent runtime entrypoints (`compile-topology.py`, `generate-framework-lock.py`, `verify-framework-lock.py`).
- [ ] Ensure bootstrap utilities generate runnable Task/CI command templates for mounted framework path (`framework/topology-tools/...`).
- [ ] Add rehearsal test for project dependency integration: build artifact -> bootstrap project -> strict verify + compile with mounted scripts.

Gate commands:

```powershell
task framework:strict
task test:default
task project:init-from-dist -- PROJECT_ROOT=build/project-bootstrap/home-lab PROJECT_ID=home-lab FRAMEWORK_DIST_ZIP=dist/framework/... FRAMEWORK_DIST_VERSION=5.0.0-rc1
```

Definition of Done:

1. Standalone project execution environment works with mounted framework scripts only.
2. Generated bootstrap notes and workflow templates are executable without manual patching.
3. Compile output contract is equivalent between co-located fixture and standalone rehearsal.

---

### P3 — Package Trust Verification Hardening

- [ ] Replace metadata-presence-only checks with integrity verification flow.
- [ ] Implement cryptographic signature validation for package mode.
- [ ] Implement provenance attestation verification.
- [ ] Implement SBOM presence check.
- [ ] Gate: package mode strict verification fails on invalid trust metadata.

Gate commands:

```powershell
task framework:release-ci
task framework:release-candidate FRAMEWORK_VERSION=5.0.0-rc1
```

Definition of Done:

1. Package mode strict verification fails on invalid signature/provenance/SBOM.
2. Release pipeline publishes trust metadata without placeholders.

Note: trust verification is phased per ADR 0081 §4.3. Integrity checks are mandatory now; cryptographic trust is enforced incrementally.

---

### P4 — Split Rehearsal Lane

- [x] Add deterministic rehearsal workflow:
  1. Extract framework artifact from current repo.
  2. Bootstrap project repository from artifact.
  3. Generate lock in project repo.
  4. Strict verify + compile in project repo (no access to framework source).
  5. Generate artifacts and verify determinism.
- [x] Publish machine-readable rehearsal summary.
- [x] Validate ADR0089-0091 SOHO contract outputs in rehearsal summary:
  1. mandatory handover/report files are present in extracted-mode output;
  2. `operator-readiness.json` includes all ADR0091 D3 evidence domains;
  3. support bundle manifest exposes normalized completeness state.

Gate commands:

```powershell
python topology-tools/utils/build-framework-distribution.py --version 5.0.0-rc1
python topology-tools/utils/bootstrap-project-repo.py --framework-dist-zip dist/framework/...
python topology-tools/generate-framework-lock.py --project-root build/project-bootstrap/home-lab
python topology-tools/compile-topology.py --strict-model-lock --project-root build/project-bootstrap/home-lab
```

Definition of Done:

1. One-command rehearsal lane is green and repeatable.
2. Generated artifacts in project repo match current monorepo outputs.

---

### P5 — Cutover and Documentation

- [ ] Align Phase 13 plan/checklist with ADR 0081 artifact-first primary mode.
- [ ] Execute cutover checklist with updated gates.
- [ ] Update `README.md` with 1:N project model documentation.
- [ ] Mark closure in production-readiness plan.

Definition of Done:

1. Phase 13 cutover approved with evidence.
2. Artifact-first mode is canonical in docs/workflows.

---

## Execution Sequence

Strict dependency order:

```
P0 (Baseline Recovery)
└── P1 (Artifact Boundary)
    └── P2 (Project Plugins)
        └── P2.5 (Execution Environment Compatibility)
            └── P3 (Trust Verification)
                └── P4 (Split Rehearsal)
                    └── P5 (Cutover)
```

Documentation updates can run in parallel but no closure gate can pass before P0.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Baseline remains red (`E7824`) | Blocks all downstream | Mandatory P0 before any cutover work |
| Artifact accidentally contains dev assets | Contract drift | Content contract tests in P1 |
| Project plugin discovery breaks existing pipeline | Runtime regression | Extend (not replace) existing discovery chain in P2 |
| Trust verification overhead for home lab | Slowed development | Phase incrementally per ADR 0081 §4.3 |
| Split rehearsal produces different artifacts | False cutover confidence | Deterministic comparison in P4 |
