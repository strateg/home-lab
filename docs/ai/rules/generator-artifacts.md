# AI Rule Pack: Generator Artifacts

Load when changing:

- generator plugins
- projection helpers
- templates
- golden snapshots
- generated artifact contracts

## Rules

1. Never hand-edit `generated/` as the source of a fix.
2. Change generator/projection/template inputs, then regenerate.
3. Generators should consume stable projections or compiled model contracts, not arbitrary raw internals.
4. Generated output paths must remain project-qualified under `generated/<project>/`.
5. Golden snapshots should change only when the output contract intentionally changes.
6. Obsolete artifact handling must remain dry-run safe unless explicitly approved by contract.
7. AI-assisted artifacts are untrusted until approved and promoted through ADR0094 mechanisms.

## Validation

- targeted generator tests
- projection snapshot tests
- Terraform/Ansible syntax checks when affected
- `task validate:default`

## ADR Sources

- ADR0074
- ADR0075
- ADR0078
- ADR0079
- ADR0092
- ADR0093
- ADR0094
