# ADR 0084: Cutover Checklist

## ADR and Register

- [x] `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md` created
- [x] `adr/REGISTER.md` updated with ADR 0084
- [x] ADR 0083 references ADR 0084 as execution-plane context

## Orchestration

- [ ] Deploy tooling exposes a runner selector instead of WSL-only branching
- [ ] Existing WSL behavior preserved behind the runner abstraction
- [ ] Dev-plane commands remain runnable without Linux-only deploy dependencies

## Runbooks

- [ ] Deploy runbooks explicitly state Linux-backed execution requirements
- [ ] Dev workflows remain documented as cross-platform
- [ ] Backend options (`wsl`, `docker`, `remote-linux`) are documented consistently

## Validation

- [ ] `python topology-tools/check-adr-consistency.py --strict-titles` passes
- [ ] Related docs and ADR links resolve correctly
