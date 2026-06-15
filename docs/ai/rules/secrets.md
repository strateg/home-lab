# AI Rule Pack: Secrets

> **Version:** 1.0 | **Updated:** 2026-06-15 | **ADRs:** See `ADR-RULE-MAP.yaml` → `secrets.source_adr`

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Never commit | Plaintext secrets = violation |
| Encryption | SOPS/age is canonical mechanism |
| Placeholders | Generated artifacts use placeholders |
| Injection | Secrets join at bundle assembly |
| AI workflows | Redact before prompt/audit logging |

## Load When

- `projects/*/secrets/**`
- Secret annotations, tfvars generation
- Deploy bundle secret injection
- AI advisory prompts, audit logs

## Secret Handling Matrix

| Context | Allowed | Forbidden |
|---------|---------|-----------|
| Source files | SOPS-encrypted | Plaintext |
| Generated artifacts | Placeholders | Actual values |
| Bundle assembly | Injected secrets | Hardcoded |
| AI prompts | Redacted | Raw secrets |
| Audit logs | Redacted | Raw secrets |

## Injection Points

| Stage | Mechanism | Location |
|-------|-----------|----------|
| Development | `V5_SECRETS_MODE=passthrough` | Validation |
| Bundle | SOPS decrypt + inject | `.work/deploy/bundles/` |
| Runtime | Environment variables | Target host |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Plaintext in repo | Security violation | Use SOPS/age |
| Secrets in `generated/` | Committed to git | Use placeholders |
| Secrets in AI prompts | LLM exposure | Redact first |
| Unknown credentials | Potential secrets | Treat as sensitive |

## Validation

```bash
task validate:default
task test:ai-redaction
# tfvars/bundle tests
```
