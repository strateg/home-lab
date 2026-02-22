# ADR 0023: Terraform Generators and Templates Domain Layout

- Status: Superseded by [0028](0028-topology-tools-architecture-consolidation.md)
- Date: 2026-02-21

## Context

Terraform generation was split between two top-level scripts and two template roots:

- `topology-tools/generate-terraform.py`
- `topology-tools/generate-terraform-mikrotik.py`
- `topology-tools/templates/terraform/`
- `topology-tools/templates/terraform-mikrotik/`

The requested target layout is explicit domain grouping:

- generators under `generators/terraform`
- MikroTik specialization under `generators/terraform/mikrotik`
- corresponding template layout in dedicated `template/terraform`.

## Decision

1. Move Terraform generator implementation into:
   - `topology-tools/scripts/generators/terraform/`
   - `topology-tools/scripts/generators/terraform/mikrotik/`
2. Keep existing top-level CLI script names as compatibility wrappers:
   - `topology-tools/generate-terraform.py`
   - `topology-tools/generate-terraform-mikrotik.py`
3. Move templates into:
   - `topology-tools/template/terraform/`
   - `topology-tools/template/terraform/mikrotik/`
4. Update template resolution paths in generator code to use new template hierarchy.

## Consequences

Benefits:

- Clearer separation of generic Terraform and MikroTik-specific generator modules.
- Template hierarchy matches generator hierarchy.
- Lower cognitive load for navigation and future extension.

Trade-offs:

- Additional module depth and import path changes.
- Transitional complexity due to wrappers and moved files.

Compatibility:

- Existing CLI commands remain unchanged.
- Generated Terraform outputs remain unchanged in location/format.

## References

- `topology-tools/scripts/generators/terraform/generator.py`
- `topology-tools/scripts/generators/terraform/cli.py`
- `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- `topology-tools/scripts/generators/terraform/mikrotik/cli.py`
- `topology-tools/template/terraform/`
- `topology-tools/template/terraform/mikrotik/`
