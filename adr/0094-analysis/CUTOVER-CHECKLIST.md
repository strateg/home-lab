# ADR 0094 CUTOVER CHECKLIST

## Pre-Cutover: Dependencies

- [ ] ADR 0092 status: Accepted
- [ ] ADR 0093 status: Accepted
- [ ] Secrets registry operational (ADR 0072)
- [ ] Field annotations operational (ADR 0073)

## Wave 1 Cutover: Sandbox Foundation

### Security Verification

- [ ] Redaction engine implemented and tested
- [ ] Secrets registry integrated as redaction source
- [ ] Field annotations integrated as redaction source
- [ ] Pattern-based redaction covers common patterns
- [ ] Redaction verification tests exist and pass
- [ ] No secrets in any test AI payload (CI verified)

### Sandbox Verification

- [ ] Sandbox output directory created on demand
- [ ] Filesystem isolation enforced (cannot write outside sandbox)
- [ ] Environment sanitization removes secrets from env vars
- [ ] Resource limits enforced (files, size, time)
- [ ] Cleanup mechanism removes old sessions

### Audit Verification

- [ ] Audit logger writes to JSONL format
- [ ] All defined events are logged
- [ ] Log retention policy implemented
- [ ] Log integrity verification works

### Wave 1 Sign-off

- [ ] Security review completed
- [ ] Redaction coverage >= 99%
- [ ] Sandbox isolation verified
- [ ] Audit logs complete

**Approver:** _________________ **Date:** _________

## Wave 2 Cutover: Advisory Mode

### Input/Output Verification

- [ ] `schemas/ai-input-contract.schema.json` exists
- [ ] Payload builder produces valid payloads
- [ ] Redaction pipeline integrated in payload builder
- [ ] Input hash logged for traceability
- [ ] `schemas/ai-output-contract.schema.json` exists
- [ ] Output parser handles AI responses
- [ ] Recommendations extracted correctly
- [ ] Confidence scores available

### Advisory Mode Verification

- [ ] `--ai-advisory` CLI flag works
- [ ] Recommendations display correctly
- [ ] No artifacts modified in advisory mode (test verified)
- [ ] Audit trail complete for advisory sessions

### Wave 2 Sign-off

- [ ] Advisory mode functional
- [ ] Read-only verified (no artifact changes)
- [ ] Audit complete

**Approver:** _________________ **Date:** _________

## Wave 3 Cutover: Assisted Mode

### Candidate Generation Verification

- [ ] Candidates generated in sandbox directory
- [ ] Validation runs on candidates
- [ ] Invalid candidates rejected
- [ ] Diff against baseline accurate
- [ ] AI metadata attached to candidates

### Review Interface Verification

- [ ] Diff displays correctly in CLI
- [ ] Change summary accurate
- [ ] Confidence scores displayed
- [ ] Selective approval works (per-file)

### Promotion Workflow Verification

- [ ] Approval gate prevents auto-promotion
- [ ] Approved files copied to generated/
- [ ] AI metadata preserved in promoted files
- [ ] Promotion logged to audit

### Rollback Verification

- [ ] AI-promoted files identifiable by metadata
- [ ] Baseline restored from VCS correctly
- [ ] Rollback event logged
- [ ] Validation passes after rollback
- [ ] Rollback completes < 5 minutes

### Wave 3 Sign-off

- [ ] End-to-end flow works
- [ ] Human approval mandatory (no bypass)
- [ ] Rollback tested and documented
- [ ] Security review for promotion path

**Approver:** _________________ **Date:** _________

## Wave 4 Cutover: Expansion

### Ansible Support Verification

- [ ] Ansible input adapter works
- [ ] Ansible output parser works
- [ ] Ansible-lint validation integrated

### Refinement Verification

- [ ] Family-specific prompting implemented
- [ ] Confidence scores calibrated
- [ ] Performance within limits

### Wave 4 Sign-off

- [ ] Ansible support functional
- [ ] All families covered
- [ ] Performance acceptable

**Approver:** _________________ **Date:** _________

## Post-Cutover: Ongoing

### Operational Checklist

- [ ] AI advisory/assisted documented in operator guide
- [ ] Rollback procedure documented
- [ ] Audit log review process established
- [ ] Incident response for secrets leak defined

### Monitoring

- [ ] Redaction verification runs in CI
- [ ] Audit logs reviewed periodically
- [ ] AI usage metrics collected (opt-in)
