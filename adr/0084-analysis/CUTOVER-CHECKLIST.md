# ADR 0084: Cutover Checklist

## ADR and Register

- [x] `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md` created
- [x] `adr/REGISTER.md` updated with ADR 0084
- [x] ADR 0083 references ADR 0084 as execution-plane context

## Environment Check Implementation

- [ ] `scripts/orchestration/deploy/environment.py` created
- [ ] `check_deploy_environment()` returns `linux`/`wsl`/`macos`
- [ ] Windows execution exits with code 1 and WSL instructions
- [ ] Unit tests pass (T-E01..T-E05)

## ADR 0083 Integration

- [ ] ADR 0083 Phase 0 added to IMPLEMENTATION-PLAN.md
- [ ] `init-node.py` calls `check_deploy_environment()` at startup
- [ ] Environment tests added to ADR 0083 TEST-MATRIX.md

## Documentation

- [ ] `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md` created
- [ ] CLAUDE.md updated with Dev/Deploy plane model
- [ ] Deploy runbooks explicitly state Linux requirement

## Validation

- [ ] `python topology-tools/check-adr-consistency.py --strict-titles` passes
- [ ] Related docs and ADR links resolve correctly
- [ ] ADR 0084 status changed to Accepted

## NOT Required (Deferred)

- ~~Deploy runner abstraction class~~
- ~~Docker backend implementation~~
- ~~Remote-linux backend implementation~~
- ~~Backend selector CLI flags~~

These are explicitly deferred to future ADR when concrete need arises.
