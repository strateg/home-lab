# ADR 0094 IMPLEMENTATION PLAN

**Status:** Completed (Waves 1-4 delivered)  
**Last updated:** 2026-04-08

## Prerequisites

Before starting Wave 1:

- [x] ADR 0092 approved (provides projection/ArtifactPlan contracts)
- [x] ADR 0093 approved (provides schema for AI input)
- [x] Secrets registry operational (ADR 0072)
- [x] Field annotations operational (ADR 0073)

## Wave 1 — Sandbox Foundation

**Goal:** Establish secure infrastructure for AI interaction.

### 1.1 Secrets Redaction Pipeline

| Task | Description | Acceptance |
|------|-------------|------------|
| 1.1.1 | Implement RedactionEngine class | Unit tests pass |
| 1.1.2 | Integrate secrets_registry as redaction source | Registry patterns redacted |
| 1.1.3 | Integrate field annotations (@secret) | Annotated fields redacted |
| 1.1.4 | Add pattern-based redaction | Common patterns caught |
| 1.1.5 | Add redaction verification tests | CI gate blocks leaks |
| 1.1.6 | Add placeholder format support | Placeholders parseable |

### 1.2 Sandbox Execution Environment

| Task | Description | Acceptance |
|------|-------------|------------|
| 1.2.1 | Create sandbox output directory structure | Directory created on demand |
| 1.2.2 | Implement filesystem isolation | Write only to sandbox dir |
| 1.2.3 | Implement environment sanitization | No secrets in env vars |
| 1.2.4 | Add resource limits (files, size, time) | Limits enforced |
| 1.2.5 | Add cleanup mechanism | Old sessions cleaned |

### 1.3 Audit Logging Infrastructure

| Task | Description | Acceptance |
|------|-------------|------------|
| 1.3.1 | Create AuditLogger class | Logs to JSONL |
| 1.3.2 | Define audit event schema | Schema documented |
| 1.3.3 | Implement event logging | All events captured |
| 1.3.4 | Add log retention policy | Old logs cleaned |
| 1.3.5 | Add integrity verification | Tampering detectable |

### Wave 1 Gate

- [x] Redaction coverage >= 99% (measured by test suite)
- [x] Zero secrets in test AI payloads
- [x] Sandbox isolation verified
- [x] Audit logs complete for test scenarios

## Wave 2 — Advisory Mode

**Goal:** AI can provide recommendations without modifying artifacts.

### 2.1 AI Input Adapter

| Task | Description | Acceptance |
|------|-------------|------------|
| 2.1.1 | Define `schemas/ai-input-contract.schema.json` | Schema file exists in `schemas/` |
| 2.1.2 | Implement payload builder | Payload from projection |
| 2.1.3 | Integrate redaction pipeline | No secrets in payload |
| 2.1.4 | Add input hash for traceability | Hash logged |

### 2.2 AI Output Adapter

| Task | Description | Acceptance |
|------|-------------|------------|
| 2.2.1 | Define `schemas/ai-output-contract.schema.json` | Schema file exists in `schemas/` |
| 2.2.2 | Implement output parser | Parse AI response |
| 2.2.3 | Extract recommendations | Recommendations structured |
| 2.2.4 | Add confidence scores | Scores available |

### 2.3 Advisory Display

| Task | Description | Acceptance |
|------|-------------|------------|
| 2.3.1 | Add --ai-advisory CLI flag | Flag recognized |
| 2.3.2 | Display recommendations in CLI | Human-readable output |
| 2.3.3 | Log advisory session to audit | Audit complete |

### Wave 2 Gate

- [x] Advisory mode produces valid recommendations
- [x] No artifacts modified (verified by tests)
- [x] Audit trail complete
- [x] Recommendations display correctly

## Wave 3 — Assisted Mode

**Goal:** AI generates candidate artifacts with human approval.

### 3.1 Candidate Generation

| Task | Description | Acceptance |
|------|-------------|------------|
| 3.1.1 | Implement CandidateGenerator | Candidates in sandbox |
| 3.1.2 | Run validation on candidates | Invalid candidates rejected |
| 3.1.3 | Generate diff against baseline | Diff accurate |
| 3.1.4 | Add AI metadata to candidates | Origin traceable |

### 3.2 Diff Review Interface

| Task | Description | Acceptance |
|------|-------------|------------|
| 3.2.1 | Implement diff display in CLI | Diff readable |
| 3.2.2 | Add change summary | Summary accurate |
| 3.2.3 | Show confidence scores | Scores displayed |
| 3.2.4 | Support selective approval | Per-file approval works |

### 3.3 Promotion Workflow

| Task | Description | Acceptance |
|------|-------------|------------|
| 3.3.1 | Implement approval gate | No auto-promotion |
| 3.3.2 | Copy approved files to generated/ | Files copied correctly |
| 3.3.3 | Mark files with AI metadata | Metadata preserved |
| 3.3.4 | Log promotion to audit | Audit complete |

### 3.4 Rollback Procedure

| Task | Description | Acceptance |
|------|-------------|------------|
| 3.4.1 | Identify AI-promoted files | Files identifiable |
| 3.4.2 | Restore from VCS | Baseline restored |
| 3.4.3 | Log rollback event | Audit complete |
| 3.4.4 | Re-run validation | Pipeline passes |

### Wave 3 Gate

- [x] End-to-end assisted flow works
- [x] Human approval required (no bypass)
- [x] Diff review accurate
- [x] Rollback restores baseline < 5 min
- [x] All promoted files traceable to AI

## Wave 4 — Expansion

**Goal:** Extend to additional artifact families.

### 4.1 Ansible Support

| Task | Description | Acceptance |
|------|-------------|------------|
| 4.1.1 | Add Ansible-specific input adapter | Inventory/vars in payload |
| 4.1.2 | Add Ansible-specific output parser | YAML artifacts parsed |
| 4.1.3 | Add Ansible validation integration | Ansible-lint runs |

### 4.2 Refinements

| Task | Description | Acceptance |
|------|-------------|------------|
| 4.2.1 | Family-specific prompting | Better AI output |
| 4.2.2 | Confidence calibration | Scores meaningful |
| 4.2.3 | Performance optimization | Latency acceptable |

### Wave 4 Gate

- [x] Ansible artifacts supported
- [x] Family-specific features work
- [x] Performance within limits

## Timeline Dependencies

```
Wave 1 ─────────────────────────────────────────────┐
  │                                                  │
  └──► Wave 2 ──────────────────────────────┐       │
         │                                   │       │
         └──► Wave 3 ───────────────┐       │       │
                │                    │       │       │
                └──► Wave 4 ────────┴───────┴───────┘
```

Each wave requires completion of previous wave gate.
