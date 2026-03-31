# ADR 0085: Implementation Plan

**Priority note:** This is the primary deploy-domain implementation track. ADR 0084 follows it, and ADR 0083 is an optional later consumer.

## Phase 1: Contract Definition

1. Define deploy bundle layout and metadata fields
2. Define project deploy profile shape
3. Align ADR 0083 terminology with bundle/workspace model
4. Align ADR 0084 runner terminology with workspace-aware execution

## Phase 2: Runner Evolution

1. Extend `DeployRunner` contract to cover workspace staging
2. Refactor `WSLRunner` and `NativeRunner` to use the new contract
3. Add capability reporting
4. Refactor legacy WSL-specific code to consume the runner contract

## Phase 3: Deploy Tooling Integration

1. Update `init-node.py` design to require `--bundle`
2. Move mutable runtime state to `.work/deploy-state/...`
3. Update logging/audit flow to include bundle identifiers
4. Prepare future Terraform/Ansible deploy entry points to consume bundles

## Acceptance Criteria

- Deploy bundle layout is documented and stable
- Runner contract is explicitly workspace-aware
- ADR 0083 and ADR 0084 are consistent with ADR 0085
- No deploy ADR relies on `.work/native/...` as the architectural execution contract
