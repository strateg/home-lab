---
@pack: generator-artifacts
@version: 1.0
@tokens: ~375
@adr: [0074, 0075, 0078, 0104]
---

# AI Rule Pack: Generator Artifacts

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Never edit | `generated/` is output-only, edit sources instead |
| Regenerate | Change generator/projection/template → recompile |
| Snapshots | Golden tests change only on intentional contract change |
| Paths | Output under `generated/<project>/` |
| AI artifacts | Untrusted until approved via ADR0094 |

## Load When

- Generator plugins, projection helpers, templates
- Golden snapshots, generated artifact contracts
- `topology-tools/plugins/generators/**`

## Generator Pipeline

| Stage | Input | Output |
|-------|-------|--------|
| Compile | Topology sources | Compiled model |
| Project | Model contracts | Stable projections |
| Generate | Projections | `generated/<project>/` |
| Validate | Generated artifacts | Syntax/lint checks |

## Output Structure

| Path | Content |
|------|---------|
| `generated/<project>/terraform/` | Terraform configurations |
| `generated/<project>/ansible/` | Ansible inventory, playbooks |
| `generated/<project>/bootstrap/` | Bootstrap packages |
| `generated/<project>/docs/` | Generated documentation |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Edit `generated/` | Overwritten on compile | Edit sources |
| Consume raw internals | Unstable contracts | Use stable projections |
| Change snapshots casually | Hides contract drift | Intentional changes only |
| Trust AI artifacts | May contain errors | Approve via ADR0094 |

## Validation

```bash
task validate:default
# Targeted generator tests
# Terraform/Ansible syntax checks
```
