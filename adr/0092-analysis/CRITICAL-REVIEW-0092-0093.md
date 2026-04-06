# Critical Review: ADR 0092 + ADR 0093

**Date:** 2026-04-06
**Scope:** ADR 0092 (Smart Artifact Generation) + ADR 0093 (ArtifactPlan Schema)
**Reviewer:** Claude Code analysis

---

## 1. Executive Summary

ADR 0092 и 0093 представляют собой хорошо продуманную пару документов:
- **ADR 0092** — архитектурная рамка (vision + направление)
- **ADR 0093** — implementation companion (конкретный первый шаг)

Разделение правильное: позволяет утвердить направление отдельно от деталей реализации.

**Вердикт:** Пакет 0092+0093 — сильное архитектурное решение. Рекомендуется принять с доработками по ownership proof, sunset policy и rollback strategy для 0093.

---

## 2. Critical Analysis

### 2.1 ADR 0092 — выявленные проблемы

| Проблема | Описание | Серьёзность |
|----------|----------|-------------|
| **Размытость IR layer** | IR описан абстрактно. Не ясно: IR per generator? Per family? Shared? | Средняя |
| **Перегруженность D-секций** | 12 решений в одном ADR — много. D10 (AI) мог бы быть отдельным ADR | Низкая |
| **Нет метрик успеха** | Acceptance criteria не количественные. "At least one generator" — слабый KPI | Средняя |
| **Capability resolution не формализован** | Упоминается, но нет контракта, как capabilities влияют на planning | Средняя |
| **Wave 5 (AI) слишком ранняя** | Включение AI path в scope создаёт ложное ожидание готовности | Низкая |

### 2.2 ADR 0093 — выявленные проблемы

| Проблема | Описание | Серьёзность | Статус |
|----------|----------|-------------|--------|
| **Нет конкретного sunset deadline** | "должен иметь sunset milestone" — но какой именно? | Высокая | **CLOSED** (D13) |
| **Schema версионирование неполное** | Как обрабатывается breaking change в schema? | Средняя | Open |
| **Нет rollback strategy** | Что делать, если migrated generator ломает pipeline? | Средняя | **CLOSED** (D14) |
| **Ownership proof не специфицирован** | Как именно доказывается ownership для delete? | Высокая | **CLOSED** (D12) |
| **Нет performance baseline** | Добавление planning overhead — какой допустимый лимит? | Низкая | Open |

> **Update 2026-04-06:** Критические пункты (ownership proof, sunset milestones, rollback) закрыты в ADR 0093 через D12-D14.

---

## 3. Improvement Proposals

### 3.1 Для ADR 0092

#### 3.1.1 Выделить IR contract в отдельную секцию с примерами

```yaml
# Предлагаемое дополнение к ADR 0092
ir_contract:
  ownership: per_artifact_family
  versioning: semver_minor_compatible
  sharing: not_allowed_between_families
  lifecycle:
    creation: during generate stage
    consumption: render/serialize only
    persistence: optional, for debug/audit
```

#### 3.1.2 Вынести AI advisory path в ADR 0094

Рекомендация:
- Удалить D10 и Wave 5 из ADR 0092
- Создать отдельный ADR 0094 "AI Advisory Mode for Artifact Generation"
- ADR 0092 становится чище и фокусируется на детерминированной генерации
- AI path получает собственный lifecycle и acceptance criteria

#### 3.1.3 Добавить количественные acceptance criteria

```yaml
# Предлагаемые метрики
acceptance_criteria_quantified:
  wave_1:
    - "≥2 Terraform generators emit valid ArtifactPlan"
    - "CI coverage for plan->output consistency ≥ 90%"
  wave_2:
    - "≥3 Terraform families have typed IR"
    - "IR regression tests exist for all migrated families"
  wave_3:
    - "Ansible inventory uses structured serialization"
    - "Parity tests pass against v5-baseline"
  overall:
    - "No regression in build/publish latency > 10%"
    - "Generator authoring guide published"
```

#### 3.1.4 Формализовать capability → artifact mapping

```yaml
# Предлагаемый контракт
capability_resolution:
  input: compiled_capabilities[]
  output:
    - artifact_family_set
    - planned_outputs[]
  contract:
    - deterministic
    - testable
    - capability order independent
  example:
    input: [network.qos.bundle, remote-access.bundle]
    output:
      artifact_family: terraform.mikrotik
      planned_outputs:
        - path: qos.tf
          reason: capability:network.qos.bundle
        - path: vpn.tf
          reason: capability:remote-access.bundle
```

### 3.2 Для ADR 0093

#### 3.2.1 Установить конкретный sunset deadline

```yaml
# Предлагаемое дополнение к D10
sunset_policy:
  terraform_mikrotik:
    migration_start: Wave 1
    migration_complete: Wave 2 end
    legacy_mode_sunset: Wave 3 start
  terraform_proxmox:
    migration_start: Wave 1
    migration_complete: Wave 2 end
    legacy_mode_sunset: Wave 3 start
  ansible_inventory:
    migration_start: Wave 3
    migration_complete: Wave 4 end
    legacy_mode_sunset: Wave 5 start
  compatibility_mode_global_removal: "After all target families reach 'migrated' status"
```

#### 3.2.2 Добавить ownership proof contract

```yaml
# Предлагаемое новое решение D12
ownership_proof_contract:
  definition: |
    A file is considered "owned" by a generator if:
    1. It was listed in a previous ArtifactPlan.planned_outputs[].path
    2. OR it matches the generator's output_prefix pattern
    3. AND no other generator claims ownership

  methods:
    path_prefix_match:
      rule: "obsolete_candidate.path starts with generator.output_prefix"
      example:
        output_prefix: "generated/home-lab/terraform/mikrotik/"
        valid_obsolete: "generated/home-lab/terraform/mikrotik/legacy_qos.tf"
        invalid_obsolete: "generated/home-lab/terraform/proxmox/old.tf"

    previous_plan_match:
      rule: "obsolete_candidate was in previous ArtifactPlan"
      source: ".state/artifact-plans/<plugin_id>.json"

  conflict_resolution:
    - "If two generators claim same path: hard error, manual resolution required"
    - "If no generator claims obsolete path: warn only, no auto-delete"

  ci_enforcement:
    - "delete action without ownership proof: CI blocker"
    - "warn action: CI pass with advisory message"
```

#### 3.2.3 Добавить rollback procedure

```yaml
# Предлагаемое новое решение D13
rollback_procedure:
  triggers:
    - "CI failure on migrated generator after merge"
    - "Runtime exception in planning/IR stage"
    - "Schema validation failure on published ArtifactPlan"

  immediate_actions:
    - "Revert generator to legacy mode via manifest flag"
    - "Disable ArtifactPlan requirement for affected family"
    - "Notify maintainer via CI alert"

  recovery_steps:
    1: "Identify root cause in planning/IR/render logic"
    2: "Fix in feature branch with regression test"
    3: "Re-enable migrated mode after CI pass"

  escalation:
    - "If rollback needed 2+ times: demote family to 'migrating' status"
    - "If rollback needed 3+ times: architectural review required"

  manifest_flag:
    name: "migration_mode"
    values: ["legacy", "migrating", "migrated", "rollback"]
    default: "legacy"
```

#### 3.2.4 Специфицировать schema evolution

```yaml
# Предлагаемое новое решение D14
schema_evolution_policy:
  versioning:
    format: "MAJOR.MINOR"
    current: "1.0"

  minor_bump_rules:
    allowed:
      - "Add optional fields"
      - "Add new enum values"
      - "Relax validation (e.g., remove 'required')"
    forbidden:
      - "Remove fields"
      - "Change field types"
      - "Rename fields"

  major_bump_rules:
    trigger:
      - "Remove or rename required fields"
      - "Change field semantics"
      - "Change enum value meanings"
    migration:
      - "Announce in ADR update"
      - "Provide migration script"
      - "Support N-1 version for 2 waves"

  backwards_compatibility:
    runtime_support: "Current + 1 previous minor version"
    test_coverage: "All supported versions"

  deprecation_flow:
    1: "Mark field as deprecated in schema"
    2: "Emit warning in runtime for 1 wave"
    3: "Remove in next major version"
```

---

## 4. SWOT Analysis (Consolidated)

### ADR 0092 + 0093 как единый пакет

```
┌─────────────────────────────────────┬─────────────────────────────────────┐
│           STRENGTHS                 │           WEAKNESSES                │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ S1. Эволюционный путь без big-bang  │ W1. Сложность контракта генератора ↑│
│ S2. Правильное разделение concerns: │ W2. Mixed-mode период неизбежен     │
│     planning/IR/render/evidence     │ W3. IR layer недостаточно           │
│ S3. Сохранение обратной             │     специфицирован                  │
│     совместимости                   │ W4. Нет конкретных sunset deadlines │
│ S4. Explainability для audit/debug  │ W5. Ownership proof не формализован │
│ S5. Dry-run safe obsolete           │ W6. Rollback strategy отсутствует   │
│     по умолчанию                    │ W7. AI path создаёт ложные ожидания │
│ S6. Хорошая база для                │ W8. Onboarding сложность для        │
│     Terraform+Ansible               │     авторов плагинов возрастает     │
│ S7. Пилотный подход снижает риск    │                                     │
│ S8. CI-интегрируемая архитектура    │                                     │
├─────────────────────────────────────┼─────────────────────────────────────┤
│           OPPORTUNITIES             │           THREATS                   │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ O1. Selective regeneration          │ T1. Schema drift между plan/runtime │
│ O2. Family-aware rebuild            │ T2. Half-implemented застревание    │
│ O3. Rich support/diagnostic bundles │ T3. Review overload в mixed period  │
│ O4. Foundation для typed IR →       │ T4. Premature programmatic emission │
│     более строгая проверяемость     │     может усложнить maintenance     │
│ O5. AI advisory на стабильных       │ T5. Недооценка 0093 как             │
│     inputs                          │     "слишком технического"          │
│ O6. Platform maturity для framework │ T6. Переархитектурить слишком рано  │
│ O7. Diff explainability для         │ T7. Schema становится бюрократией   │
│     operators                       │     если не показать быструю пользу │
│ O8. Меньше hidden logic в templates │                                     │
└─────────────────────────────────────┴─────────────────────────────────────┘
```

### SWOT Strategy Matrix

| Стратегия | Комбинация | Действие |
|-----------|------------|----------|
| **SO (Maxi-Maxi)** | S2+S4 → O1+O7 | Использовать planning/evidence для selective regen и diff explainability |
| **WO (Mini-Maxi)** | W3 → O4 | Формализовать IR после Wave 1 на основе практики |
| **ST (Maxi-Mini)** | S7 → T2 | Жёсткие wave gates предотвращают half-implemented state |
| **WT (Mini-Mini)** | W4+W6 → T2 | Добавить sunset deadlines и rollback до утверждения |

---

## 5. Risk Matrix

| ID | Риск | Вероятность | Влияние | Митигация | Owner |
|----|------|-------------|---------|-----------|-------|
| R1 | Schema drift | Средняя | Высокое | Связать schema + runtime + tests в одном PR | Tech Lead |
| R2 | Half-implemented state | Высокая | Высокое | Жёсткие wave gates, не начинать Wave N+1 без acceptance Wave N | Project |
| R3 | Ownership proof bypass | Низкая | Критическое | CI blocker на `delete` без proof | CI/DevOps |
| R4 | AI path overpromise | Средняя | Среднее | Вынести в отдельный ADR, пометить experimental | Architect |
| R5 | Performance regression | Низкая | Среднее | Baseline benchmark до миграции | Tech Lead |
| R6 | Onboarding complexity | Высокая | Среднее | Generator authoring guide + template starter | Documentation |
| R7 | Review overload | Средняя | Среднее | Automated checks, clear review guidelines | Team |

---

## 6. Adoption Recommendations

### 6.1 Immediate (before ADR approval)

| # | Action | Target | Blocker? | Status |
|---|--------|--------|----------|--------|
| 1 | Approve ADR 0092 as-is | Architecture | No | ✅ Ready |
| 2 | Add ownership proof contract to ADR 0093 (D12) | ADR 0093 | **Yes** | ✅ Done |
| 3 | Add concrete sunset milestones to ADR 0093 (D13) | ADR 0093 | **Yes** | ✅ Done |
| 4 | Add rollback procedure to ADR 0093 (D14) | ADR 0093 | **Yes** | ✅ Done |

### 6.2 Short-term (Wave 1)

| # | Action | Target | Priority | Status |
|---|--------|--------|----------|--------|
| 5 | Extract D10 (AI advisory) to separate ADR 0094 | ADR 0092 | High | ✅ Done |
| 6 | Create generator authoring guide | Documentation | High | Pending |
| 7 | Establish performance baseline before migration | CI/Metrics | Medium | Pending |
| 8 | Add schema evolution policy to ADR 0093 | ADR 0093 | Medium | Pending |

### 6.3 Mid-term (Wave 2-3)

| # | Action | Target | Priority | Status |
|---|--------|--------|----------|--------|
| 9 | Formalize IR contract based on Wave 1 experience | ADR 0092 addendum | High | Pending |
| 10 | Add quantified acceptance criteria | ADR 0092 update | Medium | Pending |
| 11 | Formalize capability → artifact mapping | ADR 0092 addendum | Medium | Pending |

---

## 7. Final Assessment

### Readiness Score

| Criterion | ADR 0092 | ADR 0093 |
|-----------|----------|----------|
| Architectural value | ★★★★★ | ★★★★☆ |
| Practical feasibility | ★★★★☆ | ★★★★★ |
| Specification completeness | ★★★☆☆ | ★★★★☆ |
| Implementation risk | Medium | Low-Medium |
| **Approval readiness** | **Ready** | **Ready** ✓ |

> **Update 2026-04-06:** ADR 0093 доработан — добавлены D12 (ownership proof), D13 (sunset milestones), D14 (rollback procedure). Все критические пункты закрыты.

### Verdict

Пакет ADR 0092+0093+0094 представляет собой **сильное архитектурное решение** с правильным эволюционным подходом.

**Рекомендация:**
1. ✅ **Утвердить ADR 0092** — готов
2. ✅ **Утвердить ADR 0093** — критические пункты закрыты (D12-D14)
3. ✅ **Утвердить ADR 0094** — AI advisory выделен в отдельный ADR
4. **Начать Wave 1** после утверждения всех ADR

---

## Appendix A: Cross-reference to Existing Analysis

| Document | Location | Relationship |
|----------|----------|--------------|
| SWOT 0092 | `0092-analysis/swot-adr-0092-smart-artifact-generation.md` | Superseded by Section 4 |
| SWOT 0093 | `0093-analysis/swot-adr-0093-artifact-plan.md` | Superseded by Section 4 |
| GAP 0092 | `0092-analysis/GAP-ANALYSIS.md` | Complementary |
| GAP 0093 | `0093-analysis/GAP-ANALYSIS.md` | Complementary |
| Decision Note | `0092-analysis/decision-note-0092-0093.md` | Complementary |

## Appendix B: Document History

| Version | Date       | Author      | Changes                                                   |
| ------- | ---------- | ----------- | --------------------------------------------------------- |
| 1.0     | 2026-04-06 | Claude Code | Initial comprehensive review                              |
| 1.1     | 2026-04-06 | Claude Code | Updated status: ADR 0093 critical gaps closed (D12-D14)   |
