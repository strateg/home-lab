# ADR 0090: SOHO Operator Lifecycle and Task UX Contract

- Status: Proposed
- Date: 2026-04-05
- Depends on: ADR 0070, ADR 0077, ADR 0080, ADR 0083, ADR 0084, ADR 0085, ADR 0089

---

## Context

SOHO deployments need a predictable operator flow that does not require framework internals knowledge.  
Current capabilities exist, but user-facing lifecycle entrypoints are fragmented.

---

## Problem

There is no single normative lifecycle contract for SOHO operations and no unified task namespace for bootstrap, plan/apply, backup/restore, update, audit, and handover.

---

## Decision

Define a canonical SOHO operator lifecycle and map it to `product:*` orchestration targets.

### 1. Lifecycle phases (normative)

1. bootstrap
2. plan
3. apply
4. backup
5. restore
6. update
7. audit
8. handover

### 2. Task namespace (normative)

- `product:init`
- `product:doctor`
- `product:plan`
- `product:apply`
- `product:backup`
- `product:restore`
- `product:update`
- `product:audit`
- `product:handover`

### 3. Architectural constraint

`product:*` targets are orchestration wrappers only.  
They must reuse existing deploy/runtime contracts (ADR0083/0085) and must not introduce a parallel execution plane.

### 4. Readiness semantics

`product:doctor` is the single operator-ready status entrypoint and aggregates:

- lifecycle preconditions
- deploy bundle/workspace state
- profile compatibility
- evidence availability (from ADR0091)

---

## Out of scope

This ADR does not define product profile/bundle data contracts (ADR0089) or evidence artifact schema (ADR0091).

---

## Consequences

### Positive

- Unified operator UX for SOHO lifecycle.
- Lower onboarding and handover complexity.
- Less dependence on ad-hoc operator knowledge.

### Trade-offs

- Additional orchestration maintenance in task/lane adapters.
- Requires strict contract mapping to avoid wrapper drift.

