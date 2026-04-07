# ADR 0093: ArtifactPlan Schema and Generator Runtime Integration

**Status:** Implemented (Waves 1-5 complete; compatibility mode closed)  
**Date:** 2026-04-05  
**Depends on:** ADR 0063, ADR 0065, ADR 0066, ADR 0074, ADR 0077, ADR 0080, ADR 0092

---

## Context

ADR 0092 задаёт направление Smart Artifact Generation:
- planning перед rendering;
- typed IR;
- generation evidence;
- hybrid rendering model;
- selective regeneration и obsolete management.

Чтобы ADR 0092 стал внедряемым, нужен следующий технический шаг:
зафиксировать конкретный runtime contract для `ArtifactPlan` и generation evidence,
а также интеграцию с существующим plugin runtime, validate/assemble/build pipeline и CI.

---

## Problem Statement

Сейчас в существующей generator-цепочке нет единого контракта, который бы:
1. описывал, какие файлы generator собирается создать;
2. отделял planned outputs от реально materialized outputs;
3. позволял публиковать explainability и evidence;
4. поддерживал obsolete detection и future selective regeneration;
5. интегрировался с tests/audit/build, не ломая текущий plugin API.

---

## Decision

Принять `ArtifactPlan` как первый обязательный runtime-артефакт для migrated generators.

### D1. Ввести JSON Schema для `ArtifactPlan`
Минимальные поля:
- plugin_id
- artifact_family
- projection_version
- ir_version
- planned_outputs[]
- obsolete_candidates[]
- capabilities[]
- validation_profiles[]

### D2. Ввести JSON Schema для `ArtifactGenerationReport`
Минимальные поля:
- plugin_id
- artifact_family
- generated[]
- skipped[]
- obsolete[]
- summary

### D3. Встроить ArtifactPlan в lifecycle generator plugin
Порядок:
1. build projection
2. build ArtifactPlan
3. optional IR build
4. render/serialize
5. build ArtifactGenerationReport
6. publish artifacts to plugin context

### D4. Validate stage должен понимать migrated generators
Validate stage должен:
- проверять schema-validity `ArtifactPlan`;
- проверять ownership и conflicts;
- различать planned, generated, skipped и obsolete outputs;
- уметь формировать usersafe summary.

### D5. Assemble/build stages должны получать generation metadata
Assemble/build получают:
- artifact family summary;
- generated outputs;
- obsolete candidates;
- validation profiles.

### D6. Ввести compatibility mode
До полной миграции допускаются:
- legacy generators без ArtifactPlan;
- migrated generators с ArtifactPlan.

Но для migrated generators `ArtifactPlan` становится обязательным.

### D7. Ввести первую пилотную миграцию
Первыми мигрировать:
- Terraform MikroTik generator
- Terraform Proxmox generator

### D8. Ввести runtime evidence outputs
Внутренние артефакты:
- `artifact-plan.json`
- `artifact-generation-report.json`
- `artifact-family-summary.json`

### D9. Ужесточить инварианты контракта
Обязательные поля (`required`) для `ArtifactPlan`:
- `schema_version`
- `plugin_id`
- `artifact_family`
- `planned_outputs`

Обязательные поля (`required`) для каждого элемента `planned_outputs[]`:
- `path`
- `renderer` (`jinja2|structured|programmatic`)
- `required`
- `reason`

Обязательные поля (`required`) для `ArtifactGenerationReport`:
- `schema_version`
- `plugin_id`
- `artifact_family`
- `summary`

`summary` обязан содержать:
- `planned_count`
- `generated_count`
- `skipped_count`
- `obsolete_count`

### D10. Зафиксировать compatibility и sunset policy
- Legacy generator без `ArtifactPlan` допускается только в compatibility mode.
- Для migrated generator отсутствие валидного `ArtifactPlan` — hard error.
- Compatibility mode должен иметь sunset milestone, после которого все generators целевой family обязаны публиковать `ArtifactPlan`.
- Validate stage должен публиковать явный статус family: `legacy`, `migrating`, `migrated`.

### D11. Ввести safe obsolete protocol
- `obsolete[]` в report использует только `retain|delete|warn`.
- `delete` допускается только при ownership proof.
- По умолчанию действие obsolete — `warn` (dry-run safe mode).
- Массовое удаление без ownership proof запрещено.

### D12. Ownership Proof Contract

Для безопасного удаления obsolete файлов generator должен доказать ownership.

**Определение ownership:**

```yaml
ownership_proof:
  definition: |
    A file is considered "owned" by a generator if ANY of:
    1. File path was in previous ArtifactPlan.planned_outputs[].path
    2. File path matches generator's output_prefix pattern
    3. File has generator's ownership marker in metadata

  methods:
    previous_plan_match:
      description: "File was planned in previous generation run"
      source: ".state/artifact-plans/<plugin_id>.json"
      lookup: "planned_outputs[].path"
      strength: strong

    output_prefix_match:
      description: "File path starts with generator's designated output directory"
      pattern: "generated/<project>/<family>/<subfamily>/"
      example:
        generator: "base.generator.terraform_mikrotik"
        prefix: "generated/home-lab/terraform/mikrotik/"
      strength: strong

    ownership_marker:
      description: "File contains ownership comment/annotation"
      format: "# Generated by: <plugin_id>"
      strength: weak (fallback only)
```

**Ownership verification flow:**

```yaml
verification_flow:
  1_check_previous_plan:
    action: "Load previous ArtifactPlan from state"
    on_match: "ownership_proven"
    on_no_match: "continue to step 2"

  2_check_prefix:
    action: "Verify file path starts with generator output_prefix"
    on_match: "ownership_proven"
    on_no_match: "continue to step 3"

  3_check_marker:
    action: "Scan file for ownership marker"
    on_match: "ownership_proven (weak)"
    on_no_match: "ownership_not_proven"

  result:
    ownership_proven: "delete action allowed"
    ownership_not_proven: "warn action only, delete blocked"
```

**Conflict resolution:**

```yaml
conflict_resolution:
  two_generators_claim_same_path:
    detection: "CI validation stage"
    action: "hard error, manual resolution required"
    resolution: "Update generator output_prefix to be non-overlapping"

  orphan_file_no_owner:
    detection: "File in generated/ but no generator claims it"
    action: "warn only, manual review required"
    cleanup: "Operator must delete manually or assign ownership"
```

**CI enforcement:**

```yaml
ci_gates:
  delete_without_proof:
    trigger: "obsolete[].action == 'delete' AND ownership_not_proven"
    result: "CI blocker"
    message: "Cannot delete {path}: ownership not proven"

  warn_action:
    trigger: "obsolete[].action == 'warn'"
    result: "CI pass with advisory"
    message: "Obsolete candidate: {path} (manual review recommended)"
```

### D13. Concrete Sunset Milestones

Compatibility mode должен иметь конкретные сроки завершения для каждой family.

**Pilot families (Wave 1-2):**

```yaml
pilot_sunset_schedule:
  terraform_mikrotik:
    migration_start: "Wave 1"
    migration_complete: "Wave 2 end"
    compatibility_sunset: "Wave 3 start"
    hard_error_date: "Wave 3 + 2 weeks"

  terraform_proxmox:
    migration_start: "Wave 1"
    migration_complete: "Wave 2 end"
    compatibility_sunset: "Wave 3 start"
    hard_error_date: "Wave 3 + 2 weeks"
```

**Secondary families (Wave 3-4):**

```yaml
secondary_sunset_schedule:
  ansible_inventory:
    migration_start: "Wave 3"
    migration_complete: "Wave 3 end"
    compatibility_sunset: "Wave 4 start"
    hard_error_date: "Wave 4 + 2 weeks"

  ansible_group_vars:
    migration_start: "Wave 3"
    migration_complete: "Wave 3 end"
    compatibility_sunset: "Wave 4 start"
    hard_error_date: "Wave 4 + 2 weeks"

  bootstrap_scripts:
    migration_start: "Wave 4"
    migration_complete: "Wave 4 end"
    compatibility_sunset: "Wave 5 start"
    hard_error_date: "Wave 5 + 2 weeks"
```

**Global compatibility removal:**

```yaml
global_sunset:
  condition: "All target families reach 'migrated' status"
  action: "Remove compatibility mode code paths"
  cleanup:
    - "Remove legacy generator detection"
    - "Remove fallback paths in validate stage"
    - "Update documentation"
```

**Sunset enforcement:**

```yaml
sunset_enforcement:
  pre_sunset:
    - "CI emits deprecation warning for legacy generators"
    - "Validate stage logs migration status"
    - "Weekly report on unmigrated generators"

  at_sunset:
    - "Legacy mode for family becomes CI warning"
    - "Migration guide prominently displayed"

  post_sunset_grace:
    duration: "2 weeks"
    behavior: "CI warning escalates to blocking warning"

  hard_error:
    behavior: "Missing ArtifactPlan is CI failure"
    exception: "None for target families"
```

### D14. Rollback Procedure

При проблемах с migrated generator должна быть возможность быстрого отката.

**Rollback triggers:**

```yaml
rollback_triggers:
  automatic:
    - "CI failure on migrated generator after merge to main"
    - "Runtime exception in ArtifactPlan building"
    - "Schema validation failure on published plan"
    - "Ownership conflict detected"

  manual:
    - "Operator initiates rollback via CLI flag"
    - "Emergency rollback by maintainer"
```

**Rollback procedure:**

```yaml
rollback_procedure:
  step_1_identify:
    action: "Identify affected generator and family"
    artifact: "Failure logs, CI output"

  step_2_disable_migration:
    action: "Set generator migration_mode to 'rollback'"
    method: "Update generator manifest"
    manifest_change:
      before: "migration_mode: migrated"
      after: "migration_mode: rollback"

  step_3_revert_artifacts:
    action: "Restore previous generated artifacts from VCS"
    command: "git checkout HEAD~1 -- generated/<family>/"

  step_4_validate:
    action: "Run validation pipeline on restored artifacts"
    expected: "Pipeline passes"

  step_5_notify:
    action: "Log rollback event and notify maintainer"
    channels:
      - "CI output"
      - "Audit log"
      - "Slack/email if configured"

  step_6_investigate:
    action: "Root cause analysis"
    output: "Bug fix in feature branch"

  step_7_re_enable:
    action: "After fix verified, restore migration_mode"
    manifest_change:
      before: "migration_mode: rollback"
      after: "migration_mode: migrated"
```

**Migration mode states:**

```yaml
migration_mode:
  legacy:
    description: "Generator does not produce ArtifactPlan"
    artifact_plan: "not required"
    validation: "legacy path"

  migrating:
    description: "Generator produces ArtifactPlan, validation optional"
    artifact_plan: "produced but not enforced"
    validation: "both paths active"

  migrated:
    description: "Generator must produce valid ArtifactPlan"
    artifact_plan: "required, validated"
    validation: "new path only"

  rollback:
    description: "Temporary revert to legacy behavior"
    artifact_plan: "not required"
    validation: "legacy path"
    flags:
      - "CI emits warning about rollback state"
      - "Automatic escalation after 7 days"
```

**Escalation policy:**

```yaml
escalation_policy:
  rollback_duration_warning:
    trigger: "Generator in rollback mode > 3 days"
    action: "Daily CI warning"

  rollback_duration_escalation:
    trigger: "Generator in rollback mode > 7 days"
    action: "CI warning becomes blocking"
    message: "Rollback exceeded 7 days, fix required"

  repeated_rollback:
    trigger: "Same generator rolled back 2+ times"
    action: "Architectural review required"
    output: "ADR amendment or generator redesign"
```

### D15. Schema Evolution Policy

```yaml
schema_evolution:
  versioning: "MAJOR.MINOR"
  current: "1.0"
  minor_changes_allowed:
    - "add optional fields"
    - "add enum values with backward compatibility"
  major_changes_required_for:
    - "remove or rename required fields"
    - "change field type or semantics"
  compatibility_window:
    runtime_support: "current + previous minor"
    deprecation_notice: "at least one wave before removal"
  enforcement:
    - "schema/runtime/tests updated in one PR"
```

### D16. Performance Budget Contract

```yaml
performance_budget:
  planning_stage_overhead:
    target: "<= 10%"
    baseline: "legacy generator runtime per family"
  validate_stage_overhead:
    target: "<= 10%"
  ci_enforcement:
    - "benchmark test for migrated families"
    - "warning at >10%, blocker at >20%"
```

### D17. State and Audit Storage Contract

```yaml
state_and_audit_contract:
  artifact_plan_state:
    path: ".state/artifact-plans/<plugin_id>.json"
    retention: "last successful + current run"
  generation_audit:
    path: ".work/generator-audit/<date>/"
    format: "jsonl"
    required_events:
      - artifact_plan_published
      - ownership_check_result
      - obsolete_action_selected
      - rollback_mode_transition
  safety:
    - "state writes are atomic"
    - "audit append-only"
```

---

## Acceptance Criteria

### Core Contract (Wave 1-2)

| ID | Criterion | Verification |
| -- | --------- | ------------ |
| AC-1 | JSON Schema for ArtifactPlan exists | Schema in `schemas/artifact-plan.schema.json` |
| AC-2 | JSON Schema for ArtifactGenerationReport exists | Schema in `schemas/artifact-generation-report.schema.json` |
| AC-3 | At least one generator publishes valid ArtifactPlan | CI test validates schema compliance |
| AC-4 | CI validates projection → plan → outputs consistency | Integration test exists |
| AC-5 | Validate stage does not break legacy generators | Regression test passes |
| AC-6 | Assemble/build stages consume generation metadata | Metadata visible in build output |

### Ownership Proof (Wave 2)

| ID | Criterion | Verification |
| -- | --------- | ------------ |
| AC-7 | Previous plan state stored and accessible | State file exists at `.state/artifact-plans/` |
| AC-8 | Output prefix match implemented | Generator manifest has `output_prefix` |
| AC-9 | Ownership verification runs before delete | CI logs show ownership check |
| AC-10 | Delete without proof is CI blocker | Test confirms CI failure |
| AC-11 | Ownership conflict detection works | Test with overlapping prefixes fails |

### Sunset Milestones (Wave 2-3)

| ID | Criterion | Verification |
| -- | --------- | ------------ |
| AC-12 | Pilot families have documented sunset dates | Dates in ADR and CI config |
| AC-13 | Migration status visible in CI output | Status shows `legacy/migrating/migrated/rollback` |
| AC-14 | Deprecation warnings emitted pre-sunset | CI logs show warnings |
| AC-15 | Hard error enforced post-sunset | Test confirms CI failure for legacy |

### Rollback Procedure (Wave 2)

| ID | Criterion | Verification |
| -- | --------- | ------------ |
| AC-16 | `migration_mode: rollback` supported in manifest | Schema allows value |
| AC-17 | Rollback disables ArtifactPlan requirement | Generator runs in legacy mode |
| AC-18 | Rollback event logged to audit | Audit log contains event |
| AC-19 | Rollback escalation after 7 days | CI warning becomes blocking |
| AC-20 | Rollback procedure documented | Runbook in docs/ |

### Schema Evolution and Performance (Wave 2-3)

| ID | Criterion | Verification |
| -- | --------- | ------------ |
| AC-21 | Schema evolution policy is implemented for ArtifactPlan/Report | Versioning and compatibility tests exist |
| AC-22 | Runtime supports current + previous minor schema versions | Backward-compat regression tests pass |
| AC-23 | Planning/validation overhead is within 10% target | Benchmark report attached to CI |
| AC-24 | State and audit storage paths are implemented and stable | State/audit artifacts visible in expected directories |

---

## Consequences

### Positive

- Идеи ADR 0092 получают конкретный runtime-контур.
- Появляется объяснимость генерации.
- Становится возможной более умная выборочная регенерация.
- Упрощается future integration для audit и AI advisory mode (ADR 0094).
- **Ownership proof** защищает от случайного удаления чужих файлов.
- **Concrete sunset milestones** обеспечивают предсказуемость миграции.
- **Rollback procedure** снижает риск застревания в broken state.

### Trade-offs

- Появляется дополнительный слой артефактов и тестов.
- Придётся некоторое время поддерживать mixed runtime mode.
- Ownership verification добавляет overhead к obsolete processing.
- State storage (`.state/artifact-plans/`) требует управления.

### Risks

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Schema drift | Medium | High | Couple schema + runtime + tests in single PR |
| Runtime complexity | Medium | Medium | Migrate 1-2 families at a time |
| Ownership false negatives | Low | High | Multiple proof methods (plan + prefix + marker) |
| Sunset too aggressive | Low | Medium | 2-week grace period after sunset |
| Rollback abuse | Low | Low | Escalation policy (7-day limit) |

### Mitigations

- Мигрировать по 1–2 generator family.
- Держать schemas минимальными.
- Не переносить лишнюю бизнес-логику в plan/report слой сразу.
- **Ownership proof**: три метода проверки для надёжности.
- **Sunset**: grace period + warnings перед hard error.
- **Rollback**: автоматическая эскалация предотвращает застревание.
