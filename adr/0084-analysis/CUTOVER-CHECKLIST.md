# ADR 0084: Cutover Checklist

## ADR and Register

- [x] `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md` created
- [x] `adr/REGISTER.md` updated with ADR 0084
- [x] ADR 0083 references ADR 0084 as execution-plane context

## Phase 0a: Runner Abstraction (Current)

### Code Implementation

- [x] `scripts/orchestration/deploy/runner.py` created
- [x] `DeployRunner` ABC defined
- [x] `NativeRunner` implemented
- [x] `WSLRunner` implemented
- [x] `get_runner()` factory with auto-detection
- [x] `scripts/orchestration/deploy/__init__.py` exports public API

### Placeholder Implementations

- [x] `DockerRunner` stub (raises NotImplementedError)
- [x] `RemoteLinuxRunner` stub (raises NotImplementedError)

### Tests

- [ ] `tests/orchestration/test_runner.py` created
- [ ] T-R01..T-R12 pass

### Refactoring

- [ ] `service_chain_evidence.py` uses `get_runner()`
- [ ] WSL-specific functions removed (moved to WSLRunner)
- [ ] Tests updated

## Documentation

- [ ] `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md` created
- [ ] CLAUDE.md updated with Dev/Deploy plane model
- [ ] Deploy runbooks explicitly state runner requirements

## Validation

- [ ] `python -c "from scripts.orchestration.deploy import get_runner; print(get_runner())"` works
- [ ] Related docs and ADR links resolve correctly
- [ ] ADR 0084 status changed to Accepted

---

## Phase 0b: Docker Runner (Future)

- [ ] `docker/Dockerfile.toolchain` created
- [ ] `DockerRunner.run()` implemented
- [ ] `DockerRunner.translate_path()` implemented
- [ ] Volume mount for workspace works
- [ ] `--network=host` for netinstall mechanism
- [ ] CI workflow uses DockerRunner

---

## Phase 0c: Remote Linux Runner (Future)

- [ ] `RemoteLinuxRunner.run()` implemented (SSH)
- [ ] File sync strategy documented (rsync/git)
- [ ] Secret handling on remote documented
- [ ] SSH key management documented
- [ ] Tests pass
