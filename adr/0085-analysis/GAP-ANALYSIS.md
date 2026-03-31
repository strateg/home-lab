# ADR 0085: Gap Analysis

## Goal

Define the gap between the current deploy-time filesystem assumptions and the target deploy bundle + runner workspace contract.

## Current State

| Aspect | Status | Issue |
|--------|--------|-------|
| Generated artifacts | Available | Used both for inspection and implicitly for execution |
| Runtime execution roots | Ad hoc | `.work/native/...` is local-path-centric |
| Runner abstraction | Partial | `run()` exists, workspace staging contract does not |
| Remote/container backends | Planned | No bundle/workspace contract to support them |

## Target State

| Aspect | Target |
|--------|--------|
| Execution input | Immutable deploy bundle |
| Backend settings | Project-scoped deploy profile |
| Runtime state | Separate mutable deploy-state root |
| Runner model | Workspace-aware, capability-reporting |

## Key Gaps

1. No canonical deploy bundle layout
2. No project-scoped deploy profile contract
3. No workspace staging contract in `DeployRunner`
4. No explicit capability negotiation for backends
5. Existing ADR 0083 wording still reflects local-path execution assumptions

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bundle model adds complexity | Medium | Keep bundle layout minimal and deterministic |
| Backend staging semantics diverge | High | Define runner contract before implementing more backends |
| Secret sprawl across roots | High | Make bundle assembly the only secret join point |
