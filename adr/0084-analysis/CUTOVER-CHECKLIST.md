# ADR 0084: Cutover Checklist

## ADR Alignment

- [x] `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md` updated
- [x] ADR 0084 references ADR 0085
- [x] ADR 0084 no longer treats `generated/` as the deploy execution source
- [x] ADR 0084 describes workspace-aware runner behavior

## Phase 0a: Runner Contract Alignment ✅

### Code

- [x] `scripts/orchestration/deploy/runner.py` exists
- [x] `scripts/orchestration/deploy/__init__.py` exports runner API
- [x] `DeployRunner` contract updated for bundle staging and workspace lifecycle
- [x] `NativeRunner` aligned to workspace-aware execution
- [x] `WSLRunner` aligned to workspace-aware execution
- [x] `get_runner()` supports explicit runner and profile-based default

### Tests

- [x] `tests/orchestration/test_runner.py` exists
- [x] Runner contract tests pass
- [x] Capability-behavior tests pass

### Refactoring

- [x] `service_chain_evidence.py` uses `DeployRunner`
- [x] WSL-specific helper logic removed from evidence tool
- [x] Evidence tooling stages explicit bundle before deploy execution

## Documentation ✅

- [x] Operator docs distinguish bundle-based deploy workflow from generated artifact inspection
- [x] Deploy runbooks describe bundle/workspace expectations
- [x] Windows workflow points to WSL-backed deploy execution path
- [x] Linux workflow remains native-runner compatible

## Validation ✅

- [x] Related ADR links resolve correctly
- [x] ADR 0084 analysis docs match ADR 0084 decision text
- [x] ADR 0083/0084/0085 terminology is consistent
- [x] ADR 0084 status promoted to Accepted

---

## Phase 0b: Docker Runner (Partial)

- [ ] Docker toolchain image created
- [x] Bundle staging/mount strategy implemented in runner
- [x] `DockerRunner` implemented
- [x] Docker runner tests pass
- [ ] CI usage documented or implemented

---

## Phase 0c: Remote Linux Runner (Partial)

- [x] Remote bundle staging strategy implemented (`rsync|scp`)
- [x] `RemoteLinuxRunner` implemented
- [ ] Remote secret/tooling prerequisites documented
- [x] Remote runner tests pass
