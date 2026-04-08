# ADR 0092 CUTOVER CHECKLIST

## Contract readiness

- [x] ADR0092 references and numbering are consistent.
- [x] Architecture/runtime boundary with ADR0093 is explicit.
- [x] Renderer modes and ownership semantics are documented.

## Runtime readiness

- [x] Artifact planning is implemented for pilot generators.
- [x] Evidence outputs are published and consumed by validation/build.
- [x] Obsolete management defaults to safe non-destructive behavior.

## CI and regression readiness

- [x] CI validates plan schema and plan/output consistency.
- [ ] No regressions for legacy generator families.
- [x] Mixed mode behavior is covered by tests.

## Governance readiness

- [x] Sunset criteria for legacy mode is defined in ADR0093 plan.
- [ ] Register status and analysis artifacts are synchronized.
