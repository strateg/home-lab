# ADR 0094 GAP ANALYSIS

## AS-IS

- No formal AI integration in artifact generation pipeline.
- No secrets redaction infrastructure for external AI consumption.
- No sandbox environment for experimental generation.
- No audit trail for AI-assisted workflows.
- No trust boundaries defined between deterministic and AI paths.

## TO-BE (ADR 0094)

- Explicit opt-in AI advisory and assisted modes.
- Secrets redaction pipeline with verification tests.
- Sandbox execution environment with isolation guarantees.
- Full audit trail for AI interactions.
- Clear trust boundaries: AI output is untrusted until promoted.
- Human approval gate for artifact promotion.

## Primary Gaps

| Gap | Description                              | Severity |
| --- | ---------------------------------------- | -------- |
| G1  | No secrets redaction infrastructure      | Critical |
| G2  | No sandbox execution environment         | Critical |
| G3  | No AI input/output adapters              | High     |
| G4  | No audit logging for AI interactions     | High     |
| G5  | No diff review interface                 | Medium   |
| G6  | No rollback procedure for AI artifacts   | Medium   |
| G7  | No pluggable AI backend architecture     | Low      |

## Dependency Analysis

| Dependency                              | Status   | Required For                                   |
| --------------------------------------- | -------- | ---------------------------------------------- |
| ADR 0092 (Smart Artifact Generation)    | Proposed | AI input contract (projection, ArtifactPlan)   |
| ADR 0093 (ArtifactPlan Schema)          | Proposed | Structured AI input                            |
| ADR 0072 (Secrets Management)           | Accepted | Secrets registry for redaction                 |
| ADR 0073 (Field Annotations)            | Accepted | @secret annotations                            |

## Risk Assessment

| Risk                           | Probability          | Impact   | Mitigation                                            |
| ------------------------------ | -------------------- | -------- | ----------------------------------------------------- |
| Secrets leak to AI provider    | Low (with redaction) | Critical | Redaction verification as CI blocker                  |
| AI output bypasses validation  | Low                  | High     | Mandatory validation pipeline                         |
| Premature production use       | Medium               | High     | Wave-gated rollout, no auto-promotion                 |
| Redaction gaps                 | Medium               | Critical | Pattern-based + registry-based + annotation-based     |

## Mitigation Strategy

1. **Secrets First**: Wave 1 focuses entirely on redaction and sandbox — no AI interaction until proven safe.
2. **Advisory Before Assisted**: Wave 2 is read-only — AI can suggest but cannot modify.
3. **Human in the Loop**: No auto-promotion ever; human approval mandatory.
4. **Audit Everything**: Complete trail for compliance and debugging.
5. **Baseline Always Available**: Deterministic path remains default and always works.
