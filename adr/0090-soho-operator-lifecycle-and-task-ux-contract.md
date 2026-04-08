# ADR 0090: SOHO Operator Lifecycle and Task UX Contract

- Status: Proposed
- Date: 2026-04-05
- Depends on: ADR 0070, ADR 0077, ADR 0080, ADR 0083, ADR 0084, ADR 0085, ADR 0089

---

## Context

SOHO deployments need a predictable operator flow that does not require framework internals knowledge.

The framework already has the required building blocks:
- deploy bundle mechanics,
- runtime/deploy layers,
- validation and acceptance stages,
- task-based orchestration.

But the user-facing lifecycle remains fragmented.
Operators currently need to understand too many internal entrypoints and execution details.

---

## Problem

There is no single normative lifecycle contract for SOHO operations and no unified user-facing task namespace for:

- bootstrap,
- plan/apply,
- backup/restore,
- update,
- audit,
- handover.

This increases onboarding cost, raises the chance of workflow drift, and weakens supportability.

---

## Decision

Define a canonical SOHO operator lifecycle and map it to `product:*` orchestration targets.

### D1. Lifecycle phases are normative

The canonical lifecycle is:

1. bootstrap
2. plan
3. apply
4. backup
5. restore
6. update
7. audit
8. handover

### D2. Task namespace is normative

The canonical SOHO task surface is:

- `product:init`
- `product:doctor`
- `product:plan`
- `product:apply`
- `product:backup`
- `product:restore`
- `product:update`
- `product:audit`
- `product:handover`

### D3. `product:*` targets are orchestration wrappers only

`product:*` targets:
- must reuse existing deploy/runtime contracts,
- must not introduce a parallel execution plane,
- must not bypass validation, bundle, runner, or workspace contracts,
- must remain thin operator-facing entrypoints.

### D4. Task semantics are explicit

| Task | Side effects | Expected mode | Notes |
|---|---|---|---|
| `product:init` | yes | controlled bootstrap | creates/initializes product-scoped baseline |
| `product:doctor` | no | read-only | single operator status entrypoint |
| `product:plan` | no | dry-run | change preview only |
| `product:apply` | yes | controlled execution | must depend on valid plan/preconditions |
| `product:backup` | yes | controlled execution | produces backup evidence |
| `product:restore` | yes | controlled execution / drill | may operate in restore-readiness or active recovery mode |
| `product:update` | yes | controlled execution | requires preflight and rollback semantics |
| `product:audit` | no | read-only | health/drift/secret hygiene/readiness audit |
| `product:handover` | yes | artifact assembly | assembles operator-facing package |

### D5. Idempotency and rerun expectations

- `product:doctor`, `product:plan`, and `product:audit` must be side-effect free.
- `product:init`, `product:backup`, and `product:handover` should be rerunnable without breaking state consistency.
- `product:apply`, `product:restore`, and `product:update` must define controlled rerun behavior and failure/rollback expectations.

### D6. `product:doctor` is the single operator-ready status entrypoint

`product:doctor` aggregates:

- lifecycle preconditions,
- deploy bundle/workspace state,
- profile compatibility (ADR 0089),
- readiness evidence availability (ADR 0091).

It must expose a normalized operator-visible status model:

- `green` — ready
- `yellow` — usable with warnings
- `red` — blocked / not ready

### D7. Preconditions and postconditions

Each `product:*` command must define:
- required preconditions,
- produced artifacts or state changes,
- failure class and operator-visible outcome.

### D8. Invariants

- The task surface must remain stable for operators.
- Task wrappers must not fork behavior away from framework/runtime truth.
- Dry-run tasks must not mutate managed state.
- Status aggregation must be readable without framework internals knowledge.

---

## Out of scope

This ADR does not define:
- product profile/bundle data contracts — see ADR 0089
- readiness evidence schemas and handover artifact completeness — see ADR 0091

---

## Consequences

### Positive
- Unified operator UX for SOHO lifecycle.
- Lower onboarding and handover complexity.
- Cleaner support and troubleshooting workflows.
- Reduced dependence on internal framework knowledge.

### Trade-offs
- Additional maintenance in task/lane adapters.
- Strict mapping is required to prevent wrapper drift.
- Operator UX now becomes a maintained contract.

### Risks
- Wrapper drift from real runtime behavior.
- Hidden side effects in tasks expected to be read-only.
- Inconsistent status aggregation if evidence/profile contracts are weak.

### Mitigations
- Keep wrappers thin and contract-driven.
- Define side-effect and precondition semantics explicitly.
- Reuse existing deploy/runtime stages rather than duplicating behavior.
- Test `product:*` as operator-facing acceptance surface.

---

## Decision summary

Adopt a single normative SOHO operator lifecycle and expose it through stable `product:*` orchestration targets with explicit side-effect, status, and rerun semantics.
