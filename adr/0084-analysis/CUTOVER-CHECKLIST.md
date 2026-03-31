# ADR 0084: Cutover Checklist

## ADR Alignment

- [x] `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md` updated
- [x] ADR 0084 references ADR 0085
- [x] ADR 0084 no longer treats `generated/` as the deploy execution source
- [x] ADR 0084 describes workspace-aware runner behavior

## Phase 0a: Runner Contract Alignment

### Code

- [x] `scripts/orchestration/deploy/runner.py` exists
- [x] `scripts/orchestration/deploy/__init__.py` exports runner API
- [x] `DeployRunner` contract updated for bundle staging and workspace lifecycle
- [x] `NativeRunner` aligned to workspace-aware execution
- [x] `WSLRunner` aligned to workspace-aware execution
- [x] `get_runner()` still works with updated contract

### Tests

- [ ] `tests/orchestration/test_runner.py` exists
- [ ] Runner contract tests pass
- [ ] Capability-behavior tests pass

### Refactoring

- [x] `service_chain_evidence.py` uses `DeployRunner`
- [x] WSL-specific helper logic removed from evidence tool
- [x] Evidence tooling stages bundle before deploy execution

## Documentation

- [ ] Operator docs clearly distinguish dev plane vs deploy plane
- [ ] Deploy runbooks describe bundle/workspace expectations
- [ ] Windows operator workflow explicitly points to WSL-backed deploy execution
- [ ] Linux operator workflow explicitly points to native runner execution

## Validation

- [ ] Related ADR links resolve correctly
- [ ] ADR 0084 analysis docs match ADR 0084 decision text
- [ ] ADR 0083/0084/0085 terminology is consistent
- [ ] ADR 0084 status can be promoted when code and docs catch up

---

## Phase 0b: Docker Runner (Future)

- [ ] Docker toolchain image created
- [ ] Bundle staging/mount strategy documented
- [ ] `DockerRunner` implemented
- [ ] Docker runner tests pass
- [ ] CI usage documented or implemented

---

## Phase 0c: Remote Linux Runner (Future)

- [ ] Remote bundle staging strategy documented
- [ ] `RemoteLinuxRunner` implemented
- [ ] Remote secret/tooling prerequisites documented
- [ ] Remote runner tests pass
