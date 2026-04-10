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

- ADR0027 (Mermaid rendering strategy)
- ADR0046 (Generators architecture)
- ADR0050 (Generated directory restructuring)
- ADR0055 (Manual Terraform extension)
- ADR0074 (V5 generator architecture)
- ADR0075 (Framework/project separation)
- ADR0078 (Object-module local template layout)
- ADR0079 (V5 documentation and diagram generation)
- ADR0092 (Smart artifact generation)
- ADR0093 (ArtifactPlan schema)
- ADR0094 (AI advisory mode)
