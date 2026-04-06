# ADR 0092 CUTOVER CHECKLIST

## Contract readiness

- [ ] ADR0092 references and numbering are consistent.
- [ ] Architecture/runtime boundary with ADR0093 is explicit.
- [ ] Renderer modes and ownership semantics are documented.

## Runtime readiness

- [ ] Artifact planning is implemented for pilot generators.
- [ ] Evidence outputs are published and consumed by validation/build.
- [ ] Obsolete management defaults to safe non-destructive behavior.

## CI and regression readiness

- [ ] CI validates plan schema and plan/output consistency.
- [ ] No regressions for legacy generator families.
- [ ] Mixed mode behavior is covered by tests.

## Governance readiness

- [ ] Sunset criteria for legacy mode is defined in ADR0093 plan.
- [ ] Register status and analysis artifacts are synchronized.
