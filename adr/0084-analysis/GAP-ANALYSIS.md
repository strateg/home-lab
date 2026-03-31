# ADR 0084: Gap Analysis

## Goal

Define the gap between the current mixed execution model and the target model:

- cross-platform dev plane,
- Linux-backed deploy plane,
- explicit deploy-runner abstraction.

## Current State

1. Dev workflows are already mostly cross-platform because validation and compilation are Python-based.
2. Deploy tooling is split:
   - Terraform/OpenTofu may run natively on Windows,
   - Ansible requires Linux-backed execution.
3. WSL-specific logic already exists in `topology-tools/utils/service_chain_evidence.py`.
4. Evidence documents record that native Windows Ansible execution is not a viable baseline in the current environment.
5. Deploy-plane backend selection is not yet expressed as a first-class orchestration contract.

## Target State

1. Dev workflows remain cross-platform and platform-neutral.
2. Deploy workflows always run against a Linux-backed backend.
3. Orchestration selects a deploy runner explicitly.
4. Runbooks distinguish dev-plane commands from deploy-plane commands.
5. ADR 0083 and future deploy ADRs build on one execution model instead of embedding ad hoc platform rules.

## Main Gaps

### Gap 1: No explicit plane boundary

- The repo conceptually separates build and deploy concerns, but the operator model is not documented as a formal architecture decision.

### Gap 2: WSL is hard-coded as a tactic

- Some flows refer directly to WSL commands instead of targeting a generic Linux-backed deploy runner.

### Gap 3: Terraform/OpenTofu and Ansible are not framed as one execution domain

- In practice they should share secrets, SSH, caches, and runtime semantics, but the current operator story still allows them to drift apart.

### Gap 4: Runbooks and tasks do not consistently declare backend expectations

- Operators can infer current behavior, but the intended backend policy is not yet explicit.

## Risks if Unchanged

1. More Windows/WSL special cases will leak into orchestration code.
2. Future Docker or remote-Linux runners will require refactoring instead of plugging into a stable interface.
3. Operator expectations for deploy support will remain ambiguous.
4. ADR 0083 implementation may grow deploy assumptions that later need reversal.

## Acceptance Signal

ADR 0084 is successfully adopted when:

1. the plane split is documented,
2. deploy backends are explicitly named,
3. orchestration can evolve from `ansible_via_wsl` to a generic deploy-runner model,
4. and deploy runbooks consistently target Linux-backed execution.
