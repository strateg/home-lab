# ADR0088 Status Snapshot — 2026-04-25

## Scope

Post-cutover quality hardening checkpoint (Wave 5), focused on governance controls and active-lane legacy boundaries.

## Fact snapshot

1. Active instances contract is canonical:
   - canonical shard header is `@instance/@extends/@group/@version`;
   - plain top-level `group` is treated as legacy/non-canonical in governance boundary checks.
2. ADR0088 governance policy (`configs/quality/adr0088-governance-policy.yaml`) currently enforces:
   - metadata coverage thresholds for class/object semantic fields;
   - warning allowlist + max-count guardrails;
   - legacy-boundary detection for `class_ref`, `object_ref`, and plain top-level `group`.
3. `validate-v5` lane executes ADR0088 governance in `enforce` mode by default and produces:
   - `build/diagnostics/adr0088-governance-report.json`.

## Evidence (2026-04-25)

- `.venv/bin/python -m pytest -q -o addopts= tests/test_validate_adr0088_governance.py` → PASS
- `task validate:default` → PASS
- `task validate:adr-consistency` → PASS

## Gate interpretation

- Wave-5 legacy-boundary governance control is active for plain `group` in active-lane instance shards.
- Governance hardening remains compatible with current diagnostics profile (`W7816`, `W7892`, `W7941`, `W7942`) under explicit policy.

## Next recommended checkpoint

- Refresh this snapshot after next governance policy change, warning profile change, or cutover checklist state update.
