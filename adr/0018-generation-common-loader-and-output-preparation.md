# ADR 0018: Shared Generation Common Module for Layered Topology Loading and Output Directory Preparation

- Status: Accepted
- Date: 2026-02-21

## Context

Generation scripts in `topology-tools/` duplicated the same operational logic:

- loading `topology.yaml` with layered section checks and version warning;
- cleaning and recreating output directories before generation.

Duplication existed in multiple generators (`generate-terraform.py`, `generate-terraform-mikrotik.py`,
`generate-ansible-inventory.py`, `generate-docs.py`) and increased maintenance cost and inconsistency risk.

## Decision

1. Introduce `topology-tools/generation/common/` as shared generation infrastructure.
2. Add reusable helpers:
   - `load_and_validate_layered_topology(...)`
   - `prepare_output_directory(...)`
3. Migrate current generators to use shared helpers while preserving existing CLI entry points and behavior.

## Consequences

Benefits:

- Reduced duplicated logic in generator scripts.
- Uniform layered topology checks and version warning semantics.
- Lower cognitive load and easier future generator migration into `generation/`.

Trade-offs:

- New shared module becomes a dependency for top-level generator scripts.
- Any helper behavior changes now affect multiple generators and require coordinated verification.

Compatibility:

- No CLI contract changes.
- Existing script names and invocation paths remain valid.

## References

- Files:
  - `topology-tools/scripts/generation/common/__init__.py`
  - `topology-tools/scripts/generation/common/topology.py`
  - `topology-tools/generate-terraform.py`
  - `topology-tools/generate-terraform-mikrotik.py`
  - `topology-tools/generate-ansible-inventory.py`
  - `topology-tools/generate-docs.py`
