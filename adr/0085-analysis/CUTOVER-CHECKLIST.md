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
- [x] `DockerRunner` stub (raises NotImplementedError)
- [x] `RemoteLinuxRunner` stub (raises NotImplementedError)
- [x] `get_runner()` factory with auto-detection

### Refactoring

- [x] `service_chain_evidence.py` uses runner abstraction
- [x] WSL-specific code moved to WSLRunner

## Phase 1: Deploy Profile

### Schema

- [ ] `schemas/deploy-profile.schema.json` created
- [ ] Schema validates runner selection, timeouts, backend configs

### Implementation

- [ ] `scripts/orchestration/deploy/profile.py` created
- [ ] Profile loader with validation
- [ ] `get_runner()` respects profile default

### Project Integration

- [ ] `projects/home-lab/deploy/deploy-profile.yaml` created
- [ ] Profile documented in operator guide

## Phase 2: Bundle Assembly

### Schema

- [ ] `schemas/deploy-bundle-manifest.schema.json` created
- [ ] Manifest includes artifacts list, metadata, provenance

### Plugin

- [ ] `base.assembler.deploy_bundle` plugin registered
- [ ] Plugin in `plugins.yaml` with correct stage/order
- [ ] Consumes generated artifacts
- [ ] Injects secrets from SOPS
- [ ] Produces immutable bundle in `.work/deploy/bundles/`

### Metadata

- [ ] Bundle ID generation is deterministic
- [ ] `metadata.yaml` includes hash, timestamp, source refs

## Phase 3: Entry Point Migration

### CLI

- [ ] `--bundle <bundle_id>` parameter added to deploy entry points
- [ ] `bundle list` command available
- [ ] `bundle inspect <bundle_id>` command available
- [ ] `bundle delete <bundle_id>` command available

### Documentation

- [ ] Operator guide explains bundle workflow
- [ ] Deploy runbooks use bundle-ID based commands

## Validation

- [ ] Unit tests for bundle assembly
- [ ] Integration tests for runner + bundle flow
- [ ] ADR 0085 status promoted to Accepted

---

## Phase 4: Backend Completion (Deferred)

- [ ] `DockerRunner` implementation (Phase 0b)
- [ ] `RemoteLinuxRunner` implementation (Phase 0c)
- [ ] Backend-specific tests pass
