# ADR 0084: Implementation Plan

## Phase 1: Architecture and Documentation

1. Add ADR 0084 and register it in `adr/REGISTER.md`.
2. Reference ADR 0084 from ADR 0083 as the execution-plane context.
3. Update deploy-oriented runbooks to distinguish:
   - cross-platform dev-plane commands,
   - Linux-backed deploy-plane commands.

## Phase 2: Runner Abstraction

1. Introduce a deploy-runner concept in orchestration utilities.
2. Replace `ansible_via_wsl` style booleans with a backend selector such as:
   - `wsl`
   - `docker`
   - `remote-linux`
3. Keep dev-plane orchestration platform-neutral.

## Phase 3: Backend Adapters

1. Preserve current WSL behavior behind the new runner interface.
2. Add Docker-backed execution for reproducible local/CI deploy checks.
3. Define the contract for remote Linux execution:
   - repo/material availability,
   - generated artifacts,
   - secrets access,
   - SSH and known_hosts handling.

## Phase 4: Runbook and Task Alignment

1. Mark authoritative deploy/apply flows as Linux-backed.
2. Clarify which task targets are safe in cross-platform dev mode.
3. Document backend-specific prerequisites and examples.

## Phase 5: Cutover

1. Make deploy-runner selection the canonical interface in deploy tooling.
2. De-emphasize direct WSL-only branching in documentation.
3. Treat WSL as a supported bridge backend, not the sole modeled solution.

## Exit Criteria

1. ADR 0084 remains consistent with ADR 0083.
2. At least one deploy flow uses a generic runner abstraction instead of a WSL-specific flag.
3. Runbooks clearly separate dev-plane and deploy-plane expectations.
