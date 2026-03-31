# Deploy Domain Scope (2026-03)

This note summarizes what is in scope now and what is intentionally deferred across ADR 0085, ADR 0084, and ADR 0083.

## Current Priority

1. `adr/0085-deploy-bundle-and-runner-workspace-contract.md`
2. `adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md`
3. `adr/0083-unified-node-initialization-contract.md` only if still justified later

## In Scope Now

- Define deploy bundle as the canonical execution input
- Define project-scoped deploy profile and deploy-state separation
- Make deploy execution Linux-backed
- Make `DeployRunner` workspace-aware
- Remove architectural dependence on direct execution from `generated/...`
- Refactor deploy tooling to consume explicit bundle/workspace inputs

## Deferred

- Unified node initialization as a repository-wide program
- `init-node.py` orchestration and adapter implementation
- Full bootstrap state machine rollout
- Hardware-specific bootstrap adapters
- Cutover of existing devices into initialization state tracking

## Why This Sequence

- ADR 0085 defines what deploy tooling executes
- ADR 0084 defines where and how that execution runs
- ADR 0083 only makes sense after those two foundations are accepted and implemented

Without that sequence, node-initialization design keeps pulling filesystem, runner, and operator-environment concerns into the wrong layer.

## Practical Rule

When making deploy-domain changes now:

- prefer bundle/workspace terminology,
- prefer runner capabilities and staging semantics,
- avoid introducing new direct dependencies on `.work/native/...`,
- do not treat ADR 0083 as an implementation commitment yet.
