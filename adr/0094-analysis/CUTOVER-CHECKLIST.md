# ADR 0094 CUTOVER CHECKLIST

## Pre-Cutover: Dependencies

- [x] ADR 0092 dependency baseline ready (Wave 1-2 deliverables available for ADR0094 integration)
- [x] ADR 0093 implemented (ArtifactPlan runtime integration complete)
- [x] Secrets registry operational (ADR 0072)
- [x] Field annotations operational (ADR 0073)

Evidence:
- ADR register: `adr/REGISTER.md` (`0072`, `0073` accepted/implemented; `0093` implemented).
- ADR0092/0093 cross-link and extraction contract: `adr/0092-smart-artifact-generation-and-hybrid-rendering.md`.
- Runtime integration points verified by ADR0094 implementation and tests in `tests/plugin_contract/` and `tests/plugin_integration/`.

## Wave 1 Cutover: Sandbox Foundation

### Security Verification

- [x] Redaction engine implemented and tested
- [x] Secrets registry integrated as redaction source
- [x] Field annotations integrated as redaction source
- [x] Pattern-based redaction covers common patterns
- [x] Redaction verification tests exist and pass
- [x] No secrets in any test AI payload (CI verified)

### Sandbox Verification

- [x] Sandbox output directory created on demand
- [x] Filesystem isolation enforced (cannot write outside sandbox)
- [x] Environment sanitization removes secrets from env vars
- [x] Resource limits enforced (files, size, time)
- [x] Cleanup mechanism removes old sessions

### Audit Verification

- [x] Audit logger writes to JSONL format
- [x] All defined events are logged
- [x] Log retention policy implemented
- [x] Log integrity verification works

### Wave 1 Sign-off

- [x] Security review completed
- [x] Redaction coverage >= 99%
- [x] Sandbox isolation verified
- [x] Audit logs complete

**Approver:** _________________ **Date:** _________

## Wave 2 Cutover: Advisory Mode

### Input/Output Verification

- [x] `schemas/ai-input-contract.schema.json` exists
- [x] Payload builder produces valid payloads
- [x] Redaction pipeline integrated in payload builder
- [x] Input hash logged for traceability
- [x] `schemas/ai-output-contract.schema.json` exists
- [x] Output parser handles AI responses
- [x] Recommendations extracted correctly
- [x] Confidence scores available

### Advisory Mode Verification

- [x] `--ai-advisory` CLI flag works
- [x] Recommendations display correctly
- [x] No artifacts modified in advisory mode (test verified)
- [x] Audit trail complete for advisory sessions

### Wave 2 Sign-off

- [x] Advisory mode functional
- [x] Read-only verified (no artifact changes)
- [x] Audit complete

**Approver:** _________________ **Date:** _________

## Wave 3 Cutover: Assisted Mode

### Candidate Generation Verification

- [x] Candidates generated in sandbox directory
- [x] Validation runs on candidates
- [x] Invalid candidates rejected
- [x] Diff against baseline accurate
- [x] AI metadata attached to candidates

### Review Interface Verification

- [x] Diff displays correctly in CLI
- [x] Change summary accurate
- [x] Confidence scores displayed
- [x] Selective approval works (per-file)

### Promotion Workflow Verification

- [x] Approval gate prevents auto-promotion
- [x] Approved files copied to generated/
- [x] AI metadata preserved in promoted files
- [x] Promotion logged to audit

### Rollback Verification

- [x] AI-promoted files identifiable by metadata
- [x] Baseline restored from VCS correctly
- [x] Rollback event logged
- [x] Validation passes after rollback
- [x] Rollback completes < 5 minutes

### Wave 3 Sign-off

- [x] End-to-end flow works
- [x] Human approval mandatory (no bypass)
- [x] Rollback tested and documented
- [x] Security review for promotion path

**Approver:** _________________ **Date:** _________

## Wave 4 Cutover: Expansion

### Ansible Support Verification

- [x] Ansible input adapter works
- [x] Ansible output parser works
- [x] Ansible-lint validation integrated

### Refinement Verification

- [x] Family-specific prompting implemented
- [x] Confidence scores calibrated
- [x] Performance within limits

### Wave 4 Sign-off

- [x] Ansible support functional
- [x] All families covered
- [x] Performance acceptable

**Approver:** _________________ **Date:** _________

## Post-Cutover: Ongoing

### Operational Checklist

- [x] AI advisory/assisted documented in operator guide
- [x] Rollback procedure documented
- [x] Audit log review process established
- [x] Incident response for secrets leak defined

### Monitoring

- [x] Redaction verification runs in CI
- [x] Audit logs reviewed periodically
- [x] AI usage metrics collected (opt-in)
