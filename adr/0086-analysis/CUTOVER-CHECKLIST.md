# ADR 0086 — Cutover Checklist

## 1) Contracts and Policy

- [ ] ADR 0086 text approved by architecture owners.
- [ ] Legacy level-boundary wording removed from policy docs.
- [ ] Contract-based boundary checks defined (stage/phase/depends_on/consumes/discovery).

## 2) Discovery and Extensibility Safety

- [x] `plugin_manifest_discovery.py` behavior unchanged for framework/class/object/project order.
- [x] Project plugin root (`project_plugins_root`) regression tests pass.
- [x] Boundary plugin tests still reject manifests under `topology/instances` data roots.

## 3) Validator Consolidation

- [x] Declarative reference validator implemented.
- [x] Router port validator consolidation implemented.
- [x] Replaced validator files removed from manifests.
- [x] Diagnostic parity tests pass (code/severity/path).

## 4) Manifest and ID Migration

- [x] ID mapping table created and reviewed.
- [x] All `depends_on` references updated.
- [x] All `consumes.from_plugin` references updated.
- [x] Manifest ID style linter passes.

## 5) Plugin Layout Cleanup

- [x] Remaining standalone class/object plugins migrated to `topology-tools/plugins/<family>/` or explicitly retained as extension-point exceptions.
- [x] Empty legacy class/object plugin manifests removed.
- [x] Required extension-point manifests preserved.
: Evidence: framework-shared helper/projection modules were relocated from `topology/object-modules/_shared/plugins/` to `topology-tools/plugins/generators/`; service directory `_shared` removed.

## 6) CI and Runtime Gates

- [x] `pytest tests/` green.
- [x] Plugin contract tests green.
- [x] Plugin integration tests green.
- [x] Compile pipeline run succeeds on baseline project.

## 7) Output and Behavior Parity

- [x] No unapproved diagnostic drift.
- [x] No unapproved generated artifact drift.
- [x] Deterministic output checks pass.
: Evidence: parallel vs sequential compile parity compared under `build/adr0086-parity/`; effective model and diagnostics differ only by approved volatile fields (`generated_at`, `compiled_at`, deploy-bundle id/path).

## 8) Documentation and Handover

- [ ] `adr/REGISTER.md` status/links are accurate.
- [x] Analysis docs (`GAP-ANALYSIS.md`, `IMPLEMENTATION-PLAN.md`) synced with final cutover.
- [x] Operator/developer notes updated with new plugin layout and ID policy.

## 9) Rollback Readiness

- [x] Rollback commit boundary identified per migration wave.
- [ ] Previous manifest/validator snapshots retained for fast revert.
- [ ] Recovery procedure documented and validated on dry-run.
: Current rollback boundaries are represented by sequential Wave 2/3 commits (`2a5aa5c`, `9dd6675`) plus current working boundary.
