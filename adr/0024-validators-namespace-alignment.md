# ADR 0024: Rename Validation Package Namespace to validators

- Status: Accepted
- Date: 2026-02-21

## Context

Validation code was previously placed under `topology-tools/scripts/validation/`.
To align naming with intent and improve readability in imports and directory structure,
the namespace should use plural form: `validators`.

## Decision

1. Rename validation package path:
   - `topology-tools/scripts/validation/` -> `topology-tools/scripts/validators/`
2. Update imports to new namespace:
   - `scripts.validators.*`
3. Keep top-level CLI entry points unchanged (`validate-topology.py` etc.).

## Consequences

Benefits:

- Clearer semantic naming for validation modules.
- Consistent terminology across folder names and import paths.

Trade-offs:

- Requires coordinated import updates across validator call sites.

Compatibility:

- CLI behavior and command names remain unchanged.
- Internal Python import paths change.

## References

- `topology-tools/scripts/validators/`
- `topology-tools/validate-topology.py`
