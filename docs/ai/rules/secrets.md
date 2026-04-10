# AI Rule Pack: Secrets

Load when changing:

- `projects/*/secrets/**`
- secret annotations
- tfvars generation
- deploy bundle secret injection
- AI advisory prompts, audit logs, or sandbox material

## Rules

1. Never commit plaintext secrets.
2. SOPS/age is the canonical secrets mechanism.
3. Generated and committed artifacts should use placeholders unless an approved injection path is explicitly used.
4. Secret join point for deployment is bundle assembly, not generated source artifacts.
5. AI advisory/assisted workflows must redact secrets before prompt construction and audit logging.
6. Treat unknown credential-like values as sensitive until proven otherwise.

## Validation

- `task validate:default`
- `task test:ai-redaction`
- targeted tfvars/bundle tests when injection behavior changes

## ADR Sources

- ADR0072
- ADR0073
- ADR0085
- ADR0094
