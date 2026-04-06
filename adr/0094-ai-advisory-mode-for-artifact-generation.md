# ADR 0094: AI Advisory Mode for Artifact Generation

**Status:** Proposed
**Date:** 2026-04-06
**Depends on:** ADR 0063, ADR 0072, ADR 0073, ADR 0074, ADR 0080, ADR 0092, ADR 0093
**Extracted from:** ADR 0092 D10

---

## Context

ADR 0092 устанавливает архитектуру Smart Artifact Generation с planning-first подходом, typed IR и hybrid rendering. В рамках этого ADR был обозначен future AI advisory path (D10), который позволяет внешнему AI-агенту участвовать в генерации артефактов.

Однако AI advisory mode — это отдельная архитектурная область со своими:
- trust boundaries;
- security constraints;
- operational modes;
- validation requirements;
- rollout strategy.

Включение AI path в основной ADR 0092 создавало:
1. Архитектурную перегруженность основного документа.
2. Ложное ожидание готовности AI-генерации.
3. Смешение deterministic baseline и experimental advisory concerns.

Выделение AI advisory mode в отдельный ADR позволяет:
- Сфокусировать ADR 0092 на детерминированной генерации.
- Дать AI path собственный lifecycle и acceptance criteria.
- Чётко разделить production-ready и experimental capabilities.

---

## Problem Statement

В текущей архитектуре отсутствует формализованный контракт для:

1. Безопасной передачи данных внешнему AI-агенту.
2. Обработки и валидации AI-generated artifacts.
3. Trust boundaries между deterministic и AI-assisted paths.
4. Operational modes (advisory vs generative vs hybrid).
5. Secrets redaction и data sanitization.
6. Sandbox isolation и rollback procedures.
7. Audit trail для AI-generated content.

---

## Decision

Принять **AI Advisory Mode** как опциональное расширение Smart Artifact Generation с explicit trust boundaries и sandbox-first подходом.

### D1. AI Advisory Mode — только opt-in

AI advisory path включается только явным образом:
- через CLI flag (`--ai-advisory`);
- через environment variable (`V5_AI_ADVISORY=true`);
- через project configuration (`ai_advisory.enabled: true`).

По умолчанию AI advisory mode **отключён**.

### D2. Определить три operational modes

```yaml
ai_modes:
  disabled:
    description: "AI не участвует в генерации"
    default: true

  advisory:
    description: "AI предлагает рекомендации, человек принимает решение"
    ai_can_modify: false
    human_approval: required

  assisted:
    description: "AI генерирует candidate artifacts, проходящие validation pipeline"
    ai_can_modify: true
    human_approval: required_for_publish

  # NOT SUPPORTED in v1
  autonomous:
    description: "AI генерирует и публикует без human review"
    status: not_implemented
    rationale: "Требует отдельного ADR и extended trust framework"
```

### D3. Ввести AI Input Contract

AI-агент получает на вход **sanitized payload**:

```yaml
ai_input_contract:
  allowed_inputs:
    - effective_json (compiled topology)
    - stable_projection (generator projection)
    - artifact_plan (from ADR 0093)
    - generation_context (family, capabilities, validation_profiles)

  forbidden_inputs:
    - raw secrets (even encrypted)
    - credentials
    - private keys
    - API tokens
    - personal identifiable information (PII)

  redaction_required:
    - all fields matching secret_patterns
    - all fields in secrets_registry
    - all fields with @secret annotation
```

### D4. Ввести Secrets Redaction Contract

```yaml
secrets_redaction:
  strategy: placeholder_replacement

  placeholder_format: "<<REDACTED:{field_path}>>"

  redaction_sources:
    - secrets_registry (from ADR 0072)
    - field_annotations (from ADR 0073)
    - pattern_matching:
        - "*_password"
        - "*_token"
        - "*_key"
        - "*_secret"
        - "credentials.*"

  verification:
    - pre-send scan for known secret patterns
    - hash-based leak detection
    - CI gate for redaction completeness
```

### D5. Ввести AI Output Contract

AI-агент возвращает **candidate package**:

```yaml
ai_output_contract:
  allowed_outputs:
    - candidate_artifact_plan
    - candidate_artifacts[]
    - advisory_recommendations[]
    - confidence_scores{}

  required_metadata:
    - ai_model_id
    - ai_request_id
    - generation_timestamp
    - input_hash (for reproducibility tracking)

  forbidden_outputs:
    - direct file writes
    - command execution
    - network requests
    - state mutations
```

### D6. AI Output — не trusted artifact

Любой AI-generated output:
- **не считается trusted** по умолчанию;
- **не может заменить** deterministic baseline без explicit approval;
- **должен пройти** полный validation/build/test pipeline;
- **должен быть помечен** как AI-generated в metadata.

```yaml
ai_trust_policy:
  trust_level: untrusted

  promotion_path:
    1: "AI generates candidate"
    2: "Candidate passes schema validation"
    3: "Candidate passes deterministic normalization"
    4: "Candidate passes full acceptance tests"
    5: "Human reviews diff against baseline"
    6: "Human approves promotion"
    7: "Candidate becomes trusted artifact"

  auto_promotion: never
```

### D7. Ввести Sandbox Execution Environment

AI advisory mode выполняется в изолированном окружении:

```yaml
sandbox_contract:
  isolation:
    filesystem: read-only except sandbox_output_dir
    network: blocked (AI API calls through proxy only)
    environment: sanitized (no secrets in env vars)

  output_directory:
    path: ".work/ai-sandbox/<request_id>/"
    cleanup: after_session (configurable retention)

  resource_limits:
    max_output_files: 100
    max_output_size_mb: 50
    max_execution_time_sec: 300
```

### D8. Ввести Audit Trail Contract

Все AI interactions логируются:

```yaml
audit_contract:
  log_location: ".work/ai-audit/<date>/"

  logged_events:
    - ai_request_sent
    - ai_response_received
    - candidate_validation_result
    - human_approval_decision
    - candidate_promotion_result

  log_format: jsonl

  retained_data:
    - input_hash (not input content)
    - output_hash
    - validation_results
    - approval_metadata

  not_retained:
    - full AI conversation
    - raw input payloads
    - rejected candidates content
```

### D9. Ввести Diff-First Review Contract

В assisted mode человек видит diff перед approval:

```yaml
diff_review_contract:
  diff_source: baseline_artifacts vs candidate_artifacts

  diff_presentation:
    - file-by-file unified diff
    - summary of changes (files added/modified/deleted)
    - AI confidence scores per change
    - AI rationale per change (if provided)

  approval_options:
    - approve_all
    - approve_selected
    - reject_all
    - request_regeneration

  approval_artifact:
    path: ".work/ai-sandbox/<request_id>/approval.json"
    contains:
      - approved_files[]
      - rejected_files[]
      - reviewer_id
      - review_timestamp
      - review_comments
```

### D10. Ввести Rollback Procedure

```yaml
rollback_contract:
  triggers:
    - validation_failure_after_promotion
    - regression_detected_in_ci
    - human_initiated_rollback

  procedure:
    1: "Identify AI-promoted artifacts by metadata"
    2: "Restore baseline versions from VCS"
    3: "Re-run validation pipeline"
    4: "Log rollback event to audit"

  prevention:
    - mandatory staging before production promotion
    - canary validation on subset of artifacts
```

### D11. Ввести Integration Points

```yaml
integration_points:
  cli:
    - "compile-topology.py --ai-advisory"
    - "compile-topology.py --ai-assisted"

  task:
    - "task generate:ai-advisory"
    - "task generate:ai-assisted"

  ci:
    - "AI advisory runs in dedicated CI job"
    - "AI candidates never auto-merge"
    - "Human approval gate required"

  api:
    - "AI adapter interface in topology-tools/ai/"
    - "Pluggable AI backends (OpenAI, Anthropic, local)"
```

### D12. Ввести Migration Strategy

```yaml
migration_waves:
  wave_1_sandbox:
    scope: "Sandbox infrastructure and redaction"
    deliverables:
      - Secrets redaction pipeline
      - Sandbox execution environment
      - Audit logging
    acceptance: "Redaction tests pass, sandbox isolated"

  wave_2_advisory:
    scope: "Advisory mode for Terraform families"
    deliverables:
      - AI input/output adapters
      - Advisory recommendations display
      - No artifact modification
    acceptance: "Advisory mode works without touching artifacts"

  wave_3_assisted:
    scope: "Assisted mode with human approval"
    deliverables:
      - Candidate generation
      - Diff review UI
      - Promotion workflow
    acceptance: "End-to-end assisted flow with approval gate"

  wave_4_expansion:
    scope: "Expand to Ansible families"
    deliverables:
      - Ansible-specific adapters
      - Family-aware prompting
    acceptance: "Ansible artifacts supported in assisted mode"
```

### D13. Ввести Acceptance Criteria

```yaml
acceptance_criteria:
  wave_1:
    - "Secrets redaction coverage >= 99%"
    - "No secrets leak in AI input (verified by tests)"
    - "Sandbox isolation verified by security review"
    - "Provider allowlist enforced (unknown provider is rejected)"
    - "Redaction/sandbox setup failures fail closed (AI call is blocked)"

  wave_2:
    - "Advisory mode produces valid recommendations"
    - "No artifacts modified in advisory mode"
    - "Audit trail complete for all requests"
    - "Advisory p95 latency <= 60s"

  wave_3:
    - "Candidate artifacts pass validation pipeline"
    - "Diff review shows accurate changes"
    - "Promotion requires explicit human approval"
    - "Rollback restores baseline within 5 minutes"
    - "Assisted p95 latency <= 300s"

  overall:
    - "AI path never becomes default"
    - "Deterministic baseline always available"
    - "Zero secrets exposure incidents"
    - "Fail-closed policy is enforced for security-critical failures"
    - "AI usage stays within configured project budget guardrails"
```

### D14. Provider Allowlist and Backend Governance

```yaml
provider_governance:
  backend_allowlist:
    source: "project config + framework defaults"
    mode: "default-deny"
  backend_selection_rules:
    - "only allowlisted providers can execute requests"
    - "provider/model pair must be explicitly configured"
    - "unapproved provider fallback is forbidden"
  change_control:
    - "allowlist changes require review"
    - "allowlist changes logged in audit trail"
```

### D15. Cost and Latency Guardrails

```yaml
cost_latency_guardrails:
  latency_slo:
    advisory_p95_sec: 60
    assisted_p95_sec: 300
  budget_policy:
    monthly_budget: "project-defined"
    soft_limit_action: "warning + audit event"
    hard_limit_action: "block assisted mode, advisory only"
  reporting:
    - "per-request cost estimate"
    - "daily usage summary"
```

### D16. Fail-Closed Execution Policy

```yaml
fail_closed_policy:
  critical_failures:
    - redaction_failure
    - sandbox_initialization_failure
    - audit_logger_unavailable
    - approval_artifact_missing
    - validation_pipeline_unavailable
  behavior:
    on_critical_failure: "abort AI path and keep deterministic baseline only"
    auto_retry: "allowed for transient transport errors only"
  operator_signal:
    - "emit explicit error code"
    - "write audit event with failure reason"
```

---

## Technical Specification

### 1. Goals

#### Business goals
- Explore AI-assisted artifact generation without compromising security.
- Maintain full control over generated infrastructure code.
- Provide audit trail for compliance requirements.

#### Engineering goals
- Clear separation between deterministic and AI-assisted paths.
- Secrets protection as first-class concern.
- Incremental adoption with rollback capability.

### 2. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Secrets redaction before AI input | Critical |
| FR-2 | Sandbox execution environment | Critical |
| FR-3 | AI output validation pipeline | Critical |
| FR-4 | Human approval gate for promotion | Critical |
| FR-5 | Audit logging for all AI interactions | High |
| FR-6 | Diff-based review interface | High |
| FR-7 | Rollback procedure | High |
| FR-8 | Pluggable AI backend adapters | Medium |
| FR-9 | Provider/model allowlist enforcement | Critical |
| FR-10 | Fail-closed behavior for security-critical failures | Critical |

### 3. Non-Functional Requirements

- No secrets in AI payloads (zero tolerance).
- AI response latency p95 < 60s for advisory, p95 < 300s for assisted.
- Audit logs retained for 90 days minimum.
- Sandbox cleanup within 24 hours of session end.
- AI mode toggle without pipeline restart.
- AI spend must stay within configured monthly project budget.
- On critical safety failures AI path must fail closed to deterministic baseline.

### 4. Security Considerations

| Threat | Control | Verification Gate |
|--------|---------|-------------------|
| Secrets leak to AI provider | Redaction pipeline + provider allowlist + forbidden-input contract | CI redaction leak tests (blocking) + allowlist policy tests |
| Malicious AI output | Untrusted-by-default output + validation pipeline + human approval | Candidate validation tests + approval gate integration tests |
| Prompt injection | Input sanitization + strict output schema validation | Injection regression suite + schema validation CI gate |
| Data exfiltration | Sandbox network isolation + sanitized environment | Sandbox isolation tests (FS/network/env) |
| Audit log tampering | Append-only audit + integrity checks | Audit integrity test + retention policy checks |
| Safety gate bypass | Fail-closed policy on critical failures | Integration tests for redaction/sandbox/audit failure paths |

---

## Consequences

### Positive
- AI capabilities available without compromising deterministic baseline.
- Clear trust boundaries protect production artifacts.
- Audit trail supports compliance and debugging.
- Incremental adoption reduces risk.

### Trade-offs
- Additional infrastructure for sandbox and redaction.
- Human approval adds latency to AI-assisted workflows.
- AI mode requires ongoing maintenance of adapters.

### Risks
- False sense of AI readiness before Wave 3 completion.
- Redaction gaps exposing secrets.
- AI output bypassing validation (implementation bug).

### Risk Mitigations
- Wave-gated rollout with explicit acceptance criteria.
- Redaction verification as CI blocker.
- Validation pipeline as mandatory gate (not optional).

---

## Implementation Plan

### Wave 1 — Sandbox Foundation
1. Implement secrets redaction pipeline.
2. Create sandbox execution environment.
3. Implement audit logging infrastructure.
4. Add redaction verification tests.

### Wave 2 — Advisory Mode
1. Implement AI input adapter (sanitized payload).
2. Implement AI output adapter (recommendations).
3. Add advisory display in CLI output.
4. No artifact modification in this wave.

### Wave 3 — Assisted Mode
1. Implement candidate artifact generation.
2. Implement diff review interface.
3. Implement promotion workflow with approval gate.
4. Implement rollback procedure.

### Wave 4 — Expansion
1. Add Ansible family support.
2. Add family-specific prompting strategies.
3. Refine confidence scoring.

---

## Relationship to ADR 0092/0093

This ADR extracts and expands D10 from ADR 0092.

### Cross-references (completed)

- ADR 0092 D10 updated to reference this ADR.
- ADR 0092 Wave 5 updated to reference this ADR.
- ADR 0092 focuses purely on deterministic Smart Artifact Generation.

### Implementation Prerequisites

> **IMPORTANT:** This ADR should be accepted together with ADR 0092/0093 as a package,
> but implementation must wait until ADR 0092/0093 Wave 1-2 are complete.

| Prerequisite | Description | Required Before |
| ------------ | ----------- | --------------- |
| ADR 0092 Wave 1 | ArtifactPlan baseline | ADR 0094 Wave 1 |
| ADR 0092 Wave 2 | Typed IR foundation | ADR 0094 Wave 2 |
| ADR 0093 | Schema and runtime integration | ADR 0094 Wave 1 |

### Rationale

AI advisory mode depends on:
1. **Stable projection** — provided by ADR 0092 generator contract.
2. **ArtifactPlan** — structured input for AI, defined by ADR 0093.
3. **Generation evidence** — allows AI to understand what was generated and why.

Without these foundations, AI advisory would be working with unstable/unstructured inputs.

---

## Register Entry

```md
| 0094 | AI Advisory Mode for Artifact Generation | Proposed | 2026-04-06 |
```

---

## Suggested Repository Updates

1. Add `adr/0094-ai-advisory-mode-for-artifact-generation.md`
2. Update `adr/REGISTER.md`
3. Create `adr/0094-analysis/` with standard documents
4. Update ADR 0092 to reference this ADR instead of D10/Wave 5
5. Add `topology-tools/ai/` directory structure (Wave 2)
6. Add `schemas/ai-input-contract.schema.json` (Wave 1)
7. Add `schemas/ai-output-contract.schema.json` (Wave 1)
