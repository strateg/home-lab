# ADR 0094 Security Review

**Date:** 2026-04-07  
**Scope:** Wave 1 sandbox/redaction controls and Wave 3 assisted promotion path

## Reviewed Controls

- Redaction sources:
  - static sensitive key patterns,
  - field annotation-derived patterns,
  - secrets registry-derived patterns.
- Sandbox isolation:
  - session path confinement,
  - path escape rejection,
  - environment secret variable sanitization,
  - file/size retention limits.
- Promotion gate:
  - no auto-promotion by default,
  - explicit human approval required (`--ai-promote-approved` + approvals),
  - selective approval supported (`--ai-approve-paths`),
  - promotion and rollback events audited.

## Evidence

- Contract/runtime tests:
  - `tests/plugin_contract/test_ai_advisory_contract_runtime.py`
  - `tests/plugin_contract/test_ai_sandbox.py`
  - `tests/plugin_contract/test_ai_assisted.py`
  - `tests/plugin_contract/test_ai_promotion.py`
  - `tests/plugin_contract/test_ai_rollback.py`
- CI gate:
  - `.github/workflows/plugin-validation.yml` job `ai-redaction-verification`.
- Operational controls:
  - `docs/runbooks/ADR0094-AI-OPERATOR-GUIDE.md`
  - `docs/runbooks/ADR0094-ROLLBACK-PROCEDURE.md`

## Result

- Wave 1 security review: **PASS**
- Promotion path security review: **PASS**

## Residual Risks

- Human approval quality depends on operator discipline.
- AI payload provider trust is external; compromise of external provider remains out of repo boundary.
