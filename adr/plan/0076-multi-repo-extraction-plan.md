# ADR 0076: Multi-Repository Extraction Plan

**Date:** 2026-03-20
**Status:** Draft
**Prerequisite:** ADR 0075 completed (2026-03-20)
**Depends on:** ADR 0074, ADR 0075

---

## Overview

This plan details the staged extraction of the v5 topology framework into a dedicated repository, enabling independent versioning and multi-project consumption.

Execution mode for this plan is strict-by-default: no legacy fallback semantics for framework/project resolution.

Initial execution profile is **submodule-first**:

1. framework continues development in current source repository;
2. project repositories consume framework via git submodule + `framework.lock.yaml`;
3. physical extraction/split of framework repository is optional follow-up once flow stabilizes.

---

## Current State (Post-0075)

```
home-lab/
├── v5/
│   ├── topology/                    # Framework root
│   │   ├── class-modules/           # 36 classes
│   │   ├── object-modules/          # 59 objects
│   │   ├── topology.yaml            # Root manifest
│   │   ├── layer-contract.yaml
│   │   ├── model.lock.yaml
│   │   └── profile-map.yaml
│   ├── topology-tools/              # Compiler + plugins
│   │   ├── kernel/
│   │   ├── plugins/
│   │   ├── templates/
│   │   ├── data/
│   │   └── *.py
│   └── projects/
│       └── home-lab/                # Project root
│           ├── project.yaml
│           ├── instances/
│           └── secrets/
└── v5-generated/
    └── home-lab/                    # Project-qualified outputs
```

---

## Target State (Post-0076)

### Repository: `infra-topology-framework`

```
infra-topology-framework/
├── framework.yaml                   # Framework manifest
├── class-modules/
├── object-modules/
├── topology-tools/
│   ├── kernel/
│   ├── plugins/
│   ├── templates/
│   ├── data/
│   └── *.py
├── layer-contract.yaml
├── tests/                           # Framework tests only
├── CHANGELOG.md
└── .github/
    └── workflows/
        └── release.yml              # Provenance + SBOM
```

### Repository: `home-lab` (Project)

```
home-lab/
├── framework/                       # git submodule -> infra-topology-framework
├── framework.lock.yaml              # Lock file
├── project.yaml
├── instances/
├── secrets/
├── overrides/                       # Optional project-local patches
├── generated/                       # Project outputs
└── .github/
    └── workflows/
        └── validate.yml             # Lock verification + compile
```

### Optional Meta-Repository: `infra-stacks`

```
infra-stacks/
├── infra-topology-framework/        # git submodule
└── home-lab/                        # git submodule
```

This layout is convenient for coordinated updates while preserving independent repos.

---

## Global Acceptance Gates (All Waves)

1. Determinism gate: repeated generation produces equivalent artifacts under canonical normalization.
2. Contract gate: framework/project compatibility checks are enforced as hard errors.
3. Supply-chain gate: signed framework artifacts + provenance + SBOM are verified in CI.
4. Rollback gate: rollback procedure is rehearsed and passes CI simulation.
5. Observability gate: E7808/E781x/E782x diagnostics are visible in CI logs and dashboards.

---

## Wave 0: Preparation and Baseline Lock

### 0.1 Framework Manifest Contract

**Files to create:**
- `v5/topology/framework.yaml`

**Schema:**
```yaml
schema_version: 1
framework_id: infra-topology-framework
framework_api_version: 1.0.0
supported_project_schema_range: ">=1.0.0 <2.0.0"

paths:
  class_modules: class-modules
  object_modules: object-modules
  layer_contract: layer-contract.yaml
  tools: topology-tools

requires:
  python: ">=3.11"
```

### 0.2 Lock File Contract

**Files to create:**
- `v5/projects/home-lab/framework.lock.yaml`

**Schema:**
```yaml
schema_version: 1
framework:
  id: infra-topology-framework
  version: 1.0.0
  source: git
  repository: https://github.com/<org>/infra-topology-framework.git
  revision: <commit-sha>
  integrity: sha256-<hash>
  signature:
    issuer: https://token.actions.githubusercontent.com
    subject: https://github.com/<org>/infra-topology-framework/.github/workflows/release.yml@refs/tags/v1.0.0
    verified: true
provenance:
  predicate_type: https://slsa.dev/provenance/v1
  uri: https://github.com/<org>/infra-topology-framework/releases/download/v1.0.0/provenance.json
sbom:
  format: spdx-json
  uri: https://github.com/<org>/infra-topology-framework/releases/download/v1.0.0/sbom.spdx.json
locked_at: 2026-03-20T12:00:00Z
```

### 0.3 Diagnostics Registration

**File:** `v5/topology-tools/data/error-catalog.yaml`

Add:
```yaml
E7821:
  severity: error
  stage: load
  title: Framework Dependency Not Resolvable
  hint: Check framework source URL and network connectivity.
E7822:
  severity: error
  stage: load
  title: Framework Lock Missing
  hint: Run framework lock command or create framework.lock.yaml.
E7823:
  severity: error
  stage: validate
  title: Lock Revision Mismatch
  hint: Framework revision differs from lock; run update or revert.
E7824:
  severity: error
  stage: validate
  title: Integrity Hash Mismatch
  hint: Framework content changed unexpectedly; verify source.
E7825:
  severity: error
  stage: validate
  title: Missing or Invalid Artifact Signature
  hint: Framework release must be signed; check release artifacts.
E7826:
  severity: error
  stage: validate
  title: Missing Provenance Attestation
  hint: Framework release must include provenance attestation.
E7827:
  severity: error
  stage: validate
  title: Lock Contract Violation
  hint: Lock file schema or constraints violated.
E7828:
  severity: error
  stage: validate
  title: SBOM Missing
  hint: Framework release must include SBOM manifest.
```

### Definition of Done (Wave 0)

1. [ ] `framework.yaml` created and schema documented
2. [ ] `framework.lock.yaml` template created
3. [ ] E7821-E7828 registered in error catalog
4. [ ] Compatibility contract fields mapped to ADR 0075 requirements
5. [ ] Existing tests remain green

---

## Wave 1: Lock Verification Runtime

### 1.1 Lock Loader

**File:** `v5/topology-tools/framework_lock.py`

Responsibilities:
- Parse `framework.lock.yaml`
- Validate schema version and required trust metadata
- Verify integrity hash against framework directory
- Verify signature/provenance/SBOM presence and policy requirements
- Emit E7822/E7823/E7824/E7825/E7826/E7828 on violations

### 1.2 Compiler Integration

**File:** `v5/topology-tools/compile-topology.py`

Changes:
- Remove warn-mode lock behavior; strict lock verification is default
- Load `framework.lock.yaml` from project root
- Verify lock before loading framework modules
- Block compilation on any E782x violation

### 1.3 Lock Generation Utility

**File:** `v5/topology-tools/generate-framework-lock.py`

Features:
- Compute SHA256 hash of framework directory
- Emit lock file with current timestamp
- Support `--source git|local|package`
- Record provenance and SBOM URIs for release artifacts

### 1.4 Verification Utility Naming Alignment

Standardize one verification entrypoint to avoid drift:
- Canonical tool: `v5/topology-tools/verify-framework-lock.py`
- `compile-topology.py` calls the same verification module internally

### Definition of Done (Wave 1)

1. [ ] Lock loader implemented with tests
2. [ ] Compiler enforces strict lock by default
3. [ ] Lock generator utility working
4. [ ] Integration tests for E7822/E7823/E7824/E7825/E7826/E7828
5. [ ] Negative tests for tampered lock and missing attestation

---

## Wave 2: Framework Repository Extraction (Optional)

### 2.1 Repository Creation

1. Create `infra-topology-framework` repository
2. Extract framework files:
   - `v5/topology/class-modules/` -> `class-modules/`
   - `v5/topology/object-modules/` -> `object-modules/`
   - `v5/topology/layer-contract.yaml` -> `layer-contract.yaml`
   - `v5/topology-tools/` -> `topology-tools/`
   - `v5/topology/framework.yaml` -> `framework.yaml`
3. Preserve git history where feasible (git filter-branch or git subtree split)

### 2.2 Framework Tests Migration

Move framework-specific tests:
- `v5/tests/plugin_integration/` -> `tests/plugin_integration/`
- `v5/tests/test_projection_*.py` -> `tests/`
- `v5/tests/conftest.py` (framework portion) -> `tests/conftest.py`

Keep project-specific tests in home-lab repository.

### 2.3 CI Pipeline for Framework

**File:** `.github/workflows/release.yml`

```yaml
name: Release
on:
  push:
    tags: ['v*']

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/ -q
      - name: Generate SBOM
        uses: anchore/sbom-action@v0
      - name: Generate provenance
        run: echo "Generate SLSA provenance artifact"
      - name: Sign release
        uses: sigstore/cosign-installer@v3
      - name: Verify signature in CI
        run: echo "Verify produced signature before publish"
      - name: Create release with attestation
        run: |
          # Create tarball
          # Sign with cosign
          # Attach SBOM and provenance
```

### Definition of Done (Wave 2, if extraction executed)

1. [ ] Framework repository created
2. [ ] All framework code extracted with history
3. [ ] Framework CI pipeline operational
4. [ ] First tagged release (v1.0.0) includes signature, provenance, and SBOM

---

## Wave 3: Project Repository Restructure

### 3.1 Add Framework as Submodule

```cmd
cd home-lab
git submodule add https://github.com/<org>/infra-topology-framework.git framework
git submodule update --init --recursive
```

### 3.2 Update Path Resolution

**File:** `project.yaml`

```yaml
schema_version: 1
project: home-lab
framework_source: submodule
framework_path: framework
instances_root: instances
secrets_root: secrets
```

### 3.3 Project CI Pipeline

**File:** `.github/workflows/validate.yml`

```yaml
name: Validate
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - name: Verify lock
        run: python framework/topology-tools/verify-framework-lock.py --strict
      - name: Compile
        run: python framework/topology-tools/compile-topology.py
      - name: Validate
        run: python framework/topology-tools/validate-project.py
```

### 3.4 Operator Workflows Documentation

Create `docs/operator-workflows.md`:
- Framework update procedure
- Lock regeneration
- Rollback procedure
- Version skew policy

### Definition of Done (Wave 3)

1. [ ] Framework wired as submodule
2. [ ] Project compiles against external framework
3. [ ] Lock verification in CI
4. [ ] Operator documentation complete

---

## Wave 4: Cutover and Validation

### 4.1 Parity Testing

Verify:
1. Generated Terraform matches pre-extraction baseline
2. Generated Ansible inventory matches
3. Bootstrap artifacts match
4. Existing repository test suite passes in strict mode

### 4.2 Version Skew Testing

Test compatibility matrix:
- Project N with Framework N
- Project N with Framework N-1
- Project N with Framework N+1 (preview)

Enforce expected outcomes from compatibility contract:
- unsupported combinations fail with E7811/E7812/E7813

### 4.3 Rollback Rehearsal

Document and test:
1. Revert submodule to previous framework version
2. Regenerate lock
3. Verify compilation
4. Restore generated artifacts

### 4.4 Production Cutover

1. Archive monorepo `v5/` framework-internal structure after verification freeze
2. Switch CI to multi-repo flow
3. Update `CLAUDE.md` and migration documentation
4. Announce migration complete
5. Mark strict-only policy as operational baseline

### Definition of Done (Wave 4)

1. [ ] Parity tests pass
2. [ ] Version skew matrix validated
3. [ ] Rollback procedure verified
4. [ ] Production cutover complete
5. [ ] No legacy/fallback execution paths remain in runtime entrypoints

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| History loss during extraction | Use git subtree split, verify blame works |
| CI permission issues for signing | Test cosign/OIDC flow in staging |
| Submodule update friction | Document clear update workflow |
| Lock verification performance | Cache hash computation |
| Breaking changes in framework | Semantic versioning + compatibility range |
| Provenance/signature drift between releases | Enforce release checklist and CI verify step |
| Lock/schema drift across repos | Shared contract tests in both repositories |

---

## RACI (Execution Ownership)

- Framework Maintainer: framework repo release, signature/provenance/SBOM publication
- Project Maintainer: lock updates, project CI enforcement, rollout coordination
- CI/SRE Owner: OIDC/cosign setup, verification gates, rollback rehearsal automation
- Architecture Owner: compatibility policy, diagnostics governance, final cutover approval

---

## Commit Strategy

```
feat(0076-wave0): add framework.yaml manifest and lock schema
feat(0076-wave0): register E7821-E7828 diagnostics
feat(0076-wave1): implement framework lock loader and verification
feat(0076-wave1): add generate-framework-lock utility
refactor(0076-wave2): extract framework to dedicated repository
feat(0076-wave2): add framework CI with SBOM and signing
refactor(0076-wave3): wire framework as submodule in project
feat(0076-wave3): add project CI with lock verification
docs(0076-wave4): operator workflows and version policy
feat(0076-wave4): cutover to multi-repo flow
```

---

## Control Commands (Each Wave)

```cmd
:: Wave 0-1: Monorepo validation
python -m pytest v5\tests -q -o addopts=''
set V5_SECRETS_MODE=passthrough && python v5\scripts\lane.py validate-v5

:: Wave 2: Framework repo validation
cd infra-topology-framework
pytest tests\ -q

:: Wave 3-4: Project repo validation
cd home-lab
python framework\topology-tools\verify-framework-lock.py --strict
python framework\topology-tools\compile-topology.py
```

---

## Timeline Dependencies

```
Wave 0 (Preparation)
    │
    ▼
Wave 1 (Lock Runtime)
    │
    ▼
Wave 2 (Framework Extraction) ──────┐
    │                                │
    ▼                                ▼
Wave 3 (Project Restructure)    Framework CI Ready
    │                                │
    ▼                                │
Wave 4 (Cutover) ◄───────────────────┘
```

---

## Execution Status

- [ ] Wave 0: Preparation and Baseline Lock
- [ ] Wave 1: Lock Verification Runtime
- [ ] Wave 2: Framework Repository Extraction
- [ ] Wave 3: Project Repository Restructure
- [ ] Wave 4: Cutover and Validation
