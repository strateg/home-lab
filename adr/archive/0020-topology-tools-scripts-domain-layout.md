# ADR 0020: Co-locate Generation and Validation Under topology-tools/scripts

- Status: Superseded by [0028](0028-topology-tools-architecture-consolidation.md)
- Date: 2026-02-21

## Context

`topology-tools/` already uses `schemas/` and `templates/` as first-level domains.
`generation/` and `validation/` were also first-level directories, but visually mixed domain code
with root executable scripts (`generate-*.py`, `validate-topology.py`, `regenerate-all.py`).

The required target structure is an explicit three-domain separation on one level:

- `schemas/`
- `templates/`
- `scripts/`

## Decision

1. Move modular code packages:
   - `topology-tools/generation/` -> `topology-tools/scripts/generation/`
   - `topology-tools/validation/` -> `topology-tools/scripts/validation/`
2. Add package marker `topology-tools/scripts/__init__.py`.
3. Update Python imports to new package roots:
   - `scripts.generation.*`
   - `scripts.validation.*`
4. Keep CLI entry points and filenames unchanged at `topology-tools/*.py`.

## Consequences

Benefits:

- Clear visual separation of architecture domains (`schemas`, `templates`, `scripts`) at one level.
- Lower cognitive load when navigating tooling structure.
- Better long-term modularization path for script internals without breaking CLI entry points.

Trade-offs:

- Internal import paths changed and require synchronized updates across modules.
- Historical ADR/file references may describe previous paths.

Compatibility:

- CLI commands remain unchanged.
- Topology schema and generated artifact formats remain unchanged.

## References

- Moved directories:
  - `topology-tools/scripts/generation/`
  - `topology-tools/scripts/validation/`
- Updated entry points:
  - `topology-tools/generate-terraform.py`
  - `topology-tools/generate-ansible-inventory.py`
  - `topology-tools/generate-terraform-mikrotik.py`
  - `topology-tools/generate-docs.py`
  - `topology-tools/generate-proxmox-answer.py`
  - `topology-tools/validate-topology.py`
