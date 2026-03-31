# ADR 0085: Cutover Checklist

## ADR Alignment

- [x] `adr/0085-deploy-bundle-and-runner-workspace-contract.md` created
- [x] ADR 0085 references ADR 0084 and ADR 0083
- [x] ADR 0084 references ADR 0085 as foundation
- [x] ADR 0083 references ADR 0085 as execution input contract

## Phase 0: Runner Foundation ✅

### Code

- [x] `scripts/orchestration/deploy/runner.py` exists
- [x] `scripts/orchestration/deploy/__init__.py` exports runner API
- [x] `scripts/orchestration/deploy/workspace.py` exists
- [x] `DeployRunner` has `stage_bundle()`, `run()`, `capabilities()`, `cleanup_workspace()`
- [x] `NativeRunner` implemented
- [x] `WSLRunner` implemented
- [x] `DockerRunner` stub (raises `NotImplementedError`)
- [x] `RemoteLinuxRunner` stub (raises `NotImplementedError`)
- [x] `get_runner()` factory with auto-detection/profile fallback

### Refactoring

- [x] `service_chain_evidence.py` uses runner abstraction
- [x] WSL-specific code moved to runner layer

## Phase 1: Deploy Profile ✅

### Schema

- [x] `schemas/deploy-profile.schema.json` created
- [x] Schema validates runner selection, timeouts, backend configs

### Implementation

- [x] `scripts/orchestration/deploy/profile.py` created
- [x] Profile loader with validation
- [x] `get_runner()` respects profile default

### Project Integration

- [x] `projects/home-lab/deploy/deploy-profile.yaml` created
- [x] Profile documented in operator/deploy docs

## Phase 2: Bundle Assembly ✅

### Schema

- [x] `schemas/deploy-bundle-manifest.schema.json` created
- [x] Manifest includes artifacts list, metadata, provenance

### Implementation

- [x] `scripts/orchestration/deploy/bundle.py` implements create/list/inspect/delete
- [x] Consumes generated artifacts as assembly input
- [x] Injects secrets from SOPS (optional)
- [x] Produces immutable bundle in `.work/deploy/bundles/`

### Metadata

- [x] Bundle ID generation is deterministic
- [x] `metadata.yaml` includes hash, timestamp, source refs

### Optional Pipeline Follow-up

- [x] `base.assembler.deploy_bundle` plugin registered in compile/build pipeline

## Phase 3: Entry Point Migration ✅ (Active Flow)

### CLI

- [x] `--bundle <bundle_id>` parameter added to active deploy entry point (`service_chain_evidence.py`)
- [x] `bundle list` command available
- [x] `bundle inspect <bundle_id>` command available
- [x] `bundle delete <bundle_id>` command available

### Documentation

- [x] Operator guide explains bundle workflow
- [x] Deploy runbooks use bundle-ID based commands

## Validation

- [x] Unit tests for bundle assembly
- [x] Integration tests for runner + bundle flow
- [x] ADR 0085 status promoted to Accepted (core phases complete)

---

## Phase 4: Backend Completion (Deferred)

- [ ] `DockerRunner` implementation (Phase 0b)
- [ ] `RemoteLinuxRunner` implementation (Phase 0c)
- [ ] Backend-specific tests pass
