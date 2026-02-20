# Architecture Decision Records (ADR)

This directory is mandatory for architecture governance in this repository.

## Rule

- Every architecture decision must be captured in a separate ADR file.
- One decision equals one ADR file.
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

1. Create a new ADR file for each new architectural decision.
2. Update `adr/REGISTER.md` with ADR number, title, status, and date.
3. Keep decisions immutable after `Accepted` (only status transitions and references may be updated).
4. Link related commits, PRs, schema changes, and docs updates in `References`.
