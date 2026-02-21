# Architecture Decision Records (ADR)

This directory is mandatory for architecture governance in this repository.

## Rule

- Every significant architecture decision must be captured in ADR.
- Use the smallest practical ADR set: prefer updating an existing domain ADR for iterative refinements.
- Create a new ADR only for a new decision boundary, not for small follow-up implementation steps.
- Architecture changes are not complete until ADR is added/updated.

## Naming

- File format: `NNNN-short-kebab-title.md`
- Example: `0002-network-profile-governance.md`
- `NNNN` is a monotonic sequence (0001, 0002, ...).

## Statuses

- `Proposed`
- `Accepted`
- `Superseded` (must reference replacement ADR)
- `Deprecated`

## Required Sections

- `Title`
- `Status`
- `Date`
- `Context`
- `Decision`
- `Consequences`
- `References`

## Process

1. Check if the change fits an existing ADR domain; if yes, update that ADR.
2. Create a new ADR only when introducing a distinct decision boundary.
3. Update `adr/REGISTER.md` with ADR number, title, status, and date.
4. For consolidation, mark old ADRs as `Superseded` and link replacement ADR in both directions.
5. Keep accepted decisions stable: update outcomes/status/references, avoid rewriting historical context.
6. Link related commits, PRs, schema changes, and docs updates in `References`.
