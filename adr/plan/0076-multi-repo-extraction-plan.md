# ADR 0076: Multi-Repository Extraction Plan

**Date:** 2026-03-20
**Status:** Draft
**Prerequisite:** ADR 0075 completed (2026-03-20)
**Depends on:** ADR 0074, ADR 0075

---

## Overview

This plan details the staged extraction of the v5 topology framework into a dedicated repository, enabling independent versioning and multi-project consumption.

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
3. [ ] E7821-E7828 registered in error-catalog.yaml
4. [ ] Existing tests remain green

---

## Wave 1: Lock Verification Runtime

### 1.1 Lock Loader

**File:** `v5/topology-tools/framework_lock.py`

Responsibilities:
- Parse `framework.lock.yaml`
- Validate schema version
- Verify integrity hash against framework directory
- Emit E7822/E7823/E7824 on violations

### 1.2 Compiler Integration

**File:** `v5/topology-tools/compile-topology.py`

Changes:
- Add `--strict-lock` flag (default: warn)
- Load `framework.lock.yaml` from project root
- Verify lock before loading framework modules
- Block compilation on E782x errors in strict mode

### 1.3 Lock Generation Utility

**File:** `v5/topology-tools/generate-framework-lock.py`

Features:
- Compute SHA256 hash of framework directory
- Emit lock file with current timestamp
- Support `--source git|local|package`

### Definition of Done (Wave 1)

1. [ ] Lock loader implemented with tests
2. [ ] Compiler respects lock in strict mode
3. [ ] Lock generator utility working
4. [ ] Integration tests for E7822/E7823/E7824

---

## Wave 2: Framework Repository Extraction

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
      - name: Sign release
        uses: sigstore/cosign-installer@v3
      - name: Create release with attestation
        run: |
          # Create tarball
          # Sign with cosign
          # Attach SBOM and provenance
```

### Definition of Done (Wave 2)

1. [ ] Framework repository created
2. [ ] All framework code extracted with history
3. [ ] Framework CI pipeline operational
4. [ ] First tagged release (v1.0.0) with SBOM

---

## Wave 3: Project Repository Restructure

### 3.1 Add Framework as Submodule

```bash
cd home-lab
git submodule add https://github.com/<org>/infra-topology-framework.git framework
git submodule update --init
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
        run: python framework/topology-tools/compile-topology.py --strict-lock
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
4. All 271+ tests pass

### 4.2 Version Skew Testing

Test compatibility matrix:
- Project N with Framework N
- Project N with Framework N-1
- Project N with Framework N+1 (preview)

### 4.3 Rollback Rehearsal

Document and test:
1. Revert submodule to previous framework version
2. Regenerate lock
3. Verify compilation
4. Restore generated artifacts

### 4.4 Production Cutover

1. Archive monorepo v5/ structure
2. Switch CI to multi-repo flow
3. Update CLAUDE.md and documentation
4. Announce migration complete

### Definition of Done (Wave 4)

1. [ ] Parity tests pass
2. [ ] Version skew matrix validated
3. [ ] Rollback procedure verified
4. [ ] Production cutover complete

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| History loss during extraction | Use git subtree split, verify blame works |
| CI permission issues for signing | Test cosign/OIDC flow in staging |
| Submodule update friction | Document clear update workflow |
| Lock verification performance | Cache hash computation |
| Breaking changes in framework | Semantic versioning + compatibility range |

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

```bash
# Wave 0-1: Monorepo validation
python -m pytest v5/tests -q -o addopts=''
V5_SECRETS_MODE=passthrough python v5/scripts/lane.py validate-v5

# Wave 2: Framework repo validation
cd infra-topology-framework
pytest tests/ -q

# Wave 3-4: Project repo validation
cd home-lab
python framework/topology-tools/verify-framework-lock.py --strict
python framework/topology-tools/compile-topology.py --strict-lock
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
