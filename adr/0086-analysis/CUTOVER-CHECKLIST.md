# ADR 0086 — Cutover Checklist

## 1) Contracts and Policy

- [ ] ADR 0086 text approved by architecture owners.
- [ ] Legacy level-boundary wording removed from policy docs.
- [ ] Contract-based boundary checks defined (stage/phase/depends_on/consumes/discovery).

## 2) Discovery and Extensibility Safety

- [ ] `plugin_manifest_discovery.py` behavior unchanged for framework/class/object/project order.
- [ ] Project plugin root (`project_plugins_root`) regression tests pass.
- [ ] Boundary plugin tests still reject manifests under `topology/instances` data roots.

## 3) Validator Consolidation

- [ ] Declarative reference validator implemented.
- [ ] Router port validator consolidation implemented.
- [ ] Replaced validator files removed from manifests.
- [ ] Diagnostic parity tests pass (code/severity/path).

## 4) Manifest and ID Migration

- [ ] ID mapping table created and reviewed.
- [ ] All `depends_on` references updated.
- [ ] All `consumes.from_plugin` references updated.
- [ ] Manifest ID style linter passes.

## 5) Plugin Layout Cleanup

- [ ] Remaining standalone class/object plugins migrated to `topology-tools/plugins/<family>/`.
- [ ] Empty legacy class/object plugin manifests removed.
- [ ] Required extension-point manifests preserved.

## 6) CI and Runtime Gates

- [ ] `pytest tests/` green.
- [ ] Plugin contract tests green.
- [ ] Plugin integration tests green.
- [ ] Compile pipeline run succeeds on baseline project.

## 7) Output and Behavior Parity

- [ ] No unapproved diagnostic drift.
- [ ] No unapproved generated artifact drift.
- [ ] Deterministic output checks pass.

## 8) Documentation and Handover

- [ ] `adr/REGISTER.md` status/links are accurate.
- [ ] Analysis docs (`GAP-ANALYSIS.md`, `IMPLEMENTATION-PLAN.md`) synced with final cutover.
- [ ] Operator/developer notes updated with new plugin layout and ID policy.

## 9) Rollback Readiness

- [ ] Rollback commit boundary identified per migration wave.
- [ ] Previous manifest/validator snapshots retained for fast revert.
- [ ] Recovery procedure documented and validated on dry-run.
