# adr/0092-smart-artifact-generation-and-hybrid-rendering.md

# ADR 0092: Smart Artifact Generation and Hybrid Rendering

**Status:** Proposed
**Date:** 2026-04-05
**Depends on:** ADR 0063, ADR 0065, ADR 0066, ADR 0072, ADR 0074, ADR 0077, ADR 0080
**Related:** ADR 0081, ADR 0093, ADR 0094
**Extracts to:** ADR 0094 (AI Advisory Mode)

---

## Context

Текущая архитектура уже зафиксировала сильный baseline:
- plugin-first microkernel runtime;
- projection-first generator contract;
- deterministic generated artifacts;
- fixed output ownership;
- Jinja2-based rendering for deployment artifacts;
- unified pipeline lifecycle and Task orchestration.

Это хороший фундамент, но текущая система генерации конечных артефактов всё ещё в основном работает как:

`projection -> render context -> template list -> file writes`

Такой подход достаточен для baseline generation, но уже начинает ограничивать развитие Terraform и Ansible генераторов:
- сложно делать умный выбор состава файлов и artifact families;
- сложно вычислять obsolete artifacts и selective regeneration;
- сложнее удерживать capability logic вне шаблонов;
- шаблоны постепенно начинают нести не только presentation, но и hidden generation logic;
- Ansible/YAML-подобные артефакты неудобно генерировать через чисто текстовый templating;
- Terraform generation в сложных family cases тяготеет к структурированной сборке, а не только к текстовому рендерингу.

При этом полный отказ от существующей цепочки и от Jinja2 сейчас нежелателен:
- сломается текущий generator contract;
- нарушится совместимость с существующими templates, tests и CI gates;
- усложнится cutover.

Нужно эволюционное решение: сначала сделать генерацию умнее **в существующей цепочке**, а уже затем оставить контролируемый путь к более структурированным emitters.

---

## Problem Statement

В проекте отсутствует архитектурный контракт для:

1. умного планирования конечных артефактов до этапа рендера;
2. разделения semantic generation logic и presentation rendering;
3. постепенного перехода от template-only к hybrid rendering model;
4. selective regeneration и контроля obsolete files;
5. безопасного будущего подключения внешнего AI-агента как опционального advisory слоя без нарушения deterministic baseline.

---

## Decision

Принять архитектуру **Smart Artifact Generation** с приоритетом на алгоритмическую генерацию внутри существующей pipeline-цепочки.

### D1. Эволюция генератора: от template emitter к artifact planner

Каждый generator plugin должен логически выполнять не один шаг, а пять стадий:

1. **Projection Build**  
   Построение стабильной projection-модели из compiled payload.

2. **Artifact Planning**  
   Вычисление состава конечных артефактов, artifact families, capability bundles, obsolete targets и generation reasons.

3. **Intermediate Representation (IR) Build**  
   Построение typed intermediate model для конкретного семейства артефактов.

4. **Render / Serialize**  
   Рендер текста через шаблоны или сериализация структурированных моделей.

5. **Post-Generation Evidence**  
   Публикация плана, списка файлов, причин генерации и metadata для assemble/build/audit.

Нормативно generator plugin по-прежнему остаётся `kind: generator`, но его внутренний контракт расширяется этими стадиями.

### D2. Ввести Artifact Plan как обязательный внутренний артефакт

Каждый generator должен формировать `ArtifactPlan` до записи файлов.

Минимальная структура `ArtifactPlan`:

```yaml
plugin_id: base.generator.terraform_mikrotik
artifact_family: terraform.mikrotik
projection_version: v1
ir_version: v1
planned_outputs:
  - path: v5-generated/<project>/terraform/mikrotik/provider.tf
    renderer: jinja2
    required: true
    reason: base-family
  - path: v5-generated/<project>/terraform/mikrotik/qos.tf
    renderer: jinja2
    required: false
    reason: capability:network.qos.bundle
obsolete_candidates:
  - v5-generated/<project>/terraform/mikrotik/legacy_qos.tf
capabilities:
  - network.qos.bundle
  - remote-access.bundle
validation_profiles:
  - terraform_fmt_check
  - terraform_validate
```

`ArtifactPlan` не является внешним runtime output по умолчанию, но должен публиковаться через plugin context и быть доступен для audit, tests и future diff logic.

### D3. Ввести typed Intermediate Representation (IR) per artifact family

Projection остаётся общим стабильным входом для генератора.

IR вводится как дополнительный слой между projection и рендером.

Примеры:
- `TerraformProviderIR`
- `TerraformResourceSetIR`
- `TerraformModuleFamilyIR`
- `AnsibleInventoryIR`
- `AnsibleGroupVarsIR`
- `BootstrapScriptIR`

Правила:
- projection не должен зависеть от renderer;
- IR может быть renderer-specific only if justified;
- IR версии должны быть явно зафиксированы;
- generator tests должны покрывать projection -> IR и IR -> artifact path.

### D4. Ввести hybrid rendering model

Разрешить в рамках generator contract три режима materialization:

1. **Template Rendering**  
   Использование Jinja2 для текстовых файлов.

2. **Structured Serialization**  
   Прямая сериализация структурированных данных в YAML/JSON/INI/CSV и аналогичные форматы.

3. **Programmatic Emission**  
   Алгоритмическая генерация текста из typed IR для случаев, где шаблонный рендер неудобен или избыточен.

Приоритет по умолчанию:
- YAML/JSON/INI inventory-подобные артефакты: prefer structured serialization;
- Terraform/HCL family: prefer template rendering initially, allow programmatic emission in complex cases;
- docs/runbooks/bootstrap text: keep template rendering.

### D5. Сохранить совместимость с текущей цепочкой

Новый контракт не ломает текущую архитектуру:
- plugin manifests остаются в существующей модели;
- StageGuard/CI gates сохраняются;
- fixed output ownership сохраняется;
- current templates остаются supported;
- current generator plugins можно мигрировать поэтапно.

### D6. Ввести obsolete management и selective regeneration

Generator обязан:
- вычислять `obsolete_candidates`;
- публиковать причины удаления/сохранения;
- поддерживать selective regeneration на уровне artifact family и capability bundle;
- не удалять файл без explicit ownership proof;
- использовать action taxonomy `retain|delete|warn` для obsolete outcomes;
- работать в dry-run-safe режиме по умолчанию (`warn`, если deletion policy явно не подтверждена).

### D7. Ввести generator evidence для audit и tests

После генерации должны публиковаться usersafe/internal артефакты:

- `artifact-plan.json`
- `artifact-generation-report.json`
- `artifact-obsolete-report.json`
- `artifact-family-summary.json`

Эти артефакты используются:
- acceptance tests;
- diff explainability;
- operator audit;
- future AI advisory path.

### D8. Terraform-specific policy

Для Terraform generation:
- сохранить текущий template-based baseline;
- вынести capability resolution и file-family planning из шаблонов в planning stage;
- разрешить programmatic emission для:
  - provider/version blocks;
  - repeated resource groups;
  - dependency-heavy fragments;
  - generated locals/outputs blocks.

Цель: уменьшить скрытую логику в `.tf.j2` и сделать resource composition более проверяемой.

### D9. Ansible-specific policy

Для Ansible generation:
- inventory/group_vars/host_vars и подобные структуры должны по умолчанию переходить на structured serialization;
- Jinja2 сохраняется для human-oriented docs, runbooks, text configs и отдельных legacy files;
- runtime assembly остаётся отдельным этапом, но должен получать richer artifact metadata от generator stage.

Цель: сделать Ansible output более data-native и менее зависимым от текстовых шаблонов там, где конечный формат сам является сериализуемой структурой.

### D10. Внешний AI-агент — see ADR 0094

> **Extracted to [ADR 0094](0094-ai-advisory-mode-for-artifact-generation.md)**
>
> AI advisory mode выделен в отдельный ADR для:
> - чёткого разделения deterministic и experimental concerns;
> - собственного lifecycle и acceptance criteria;
> - детальной проработки security boundaries.
>
> ADR 0094 определяет:
> - trust boundaries и operational modes (advisory/assisted);
> - secrets redaction contract;
> - sandbox execution environment;
> - human approval gates;
> - audit trail requirements.
>
> **Зависимость:** ADR 0094 может быть реализован только после завершения Wave 1-2 данного ADR.

### D11. Ввести migration strategy

Миграция по волнам:

**Wave 1**  
ArtifactPlan для существующих Terraform generators без изменения renderer.

**Wave 2**  
Typed IR для Terraform families.

**Wave 3**  
Structured serialization для Ansible inventory/group_vars/host_vars.

**Wave 4**  
Selective programmatic emission для сложных Terraform blocks.

**Wave 5**
AI advisory mode — see [ADR 0094](0094-ai-advisory-mode-for-artifact-generation.md).

### D12. Граница ADR0092
Этот ADR фиксирует архитектурную рамку и целевой runtime shape.  
Строгие schema-инварианты, compatibility/sunset policy и CI gating details выносятся в ADR 0093.

---

## Technical Specification

## 1. Goals

### Business goals
- повысить качество и предсказуемость конечных артефактов;
- сократить стоимость развития generator logic;
- уменьшить hidden logic в шаблонах;
- подготовить архитектуру к более умной генерации без потери контроля.

### Engineering goals
- сохранить plugin-first и projection-first architecture;
- не ломать current CI/test pipeline;
- ввести explainable planning перед render stage;
- сделать Terraform и Ansible generation более проверяемыми и менее brittle.

## 2. Functional requirements

### FR-1 Artifact plan
Каждый generator plugin должен строить `ArtifactPlan` до записи файлов.

### FR-2 Renderer abstraction
Generator должен явно указывать renderer mode: `jinja2`, `structured`, `programmatic`.

### FR-3 IR support
Generator contract должен поддерживать optional/required IR layer.

### FR-4 Obsolete detection
Generator должен уметь вычислять obsolete outputs и публиковать их отдельно.

### FR-5 Explainability
Generator должен публиковать reasons, capability bundles и artifact family summary.

### FR-6 Compatibility mode
Существующие generators должны работать в compatibility mode до завершения миграции.

### FR-7 AI advisory hook
Pipeline должна поддерживать future optional advisory input без изменения deterministic baseline path.

## 3. Non-functional requirements

- deterministic output for identical inputs;
- stable projection contract;
- stable IR versioning;
- no plaintext secrets in externalized AI payloads;
- no destructive deletion without ownership proof;
- full compatibility with StageGuard/acceptance/build chain.

## 4. Proposed contracts

### 4.1 ArtifactPlan schema sketch

```yaml
plugin_id: string
artifact_family: string
projection_version: string
ir_version: string
planned_outputs:
  - path: string
    renderer: jinja2|structured|programmatic
    required: bool
    reason: string
    source_ref: string
obsolete_candidates:
  - string
capabilities:
  - string
validation_profiles:
  - string
```

### 4.2 ArtifactGenerationReport schema sketch

```yaml
plugin_id: string
artifact_family: string
generated:
  - path: string
    checksum: string
    renderer: string
skipped:
  - path: string
    reason: string
obsolete:
  - path: string
    action: retain|delete|warn
summary:
  planned_count: int
  generated_count: int
  skipped_count: int
  obsolete_count: int
```

## 5. Pipeline integration

### discover
- resolve generator capabilities
- resolve artifact family support

### compile
- build stable projection

### generate
- build ArtifactPlan
- build IR
- render/serialize outputs
- publish generation evidence

### validate
- syntax and schema validation
- family-specific validation
- artifact ownership and obsolete checks

### assemble
- consume richer artifact metadata

### build
- package outputs with artifact evidence

## 6. Acceptance criteria

ADR implementation is considered complete when:
- at least one Terraform family generator emits ArtifactPlan;
- at least one Ansible family generator uses structured serialization;
- obsolete detection exists for migrated generators;
- CI has tests for projection -> plan and plan -> outputs;
- no regression in current build/publish path.

---

## Consequences

### Positive
- генераторы становятся объяснимее и умнее;
- логика перемещается из шаблонов в planning/IR layers;
- появляется controlled path к structured emitters;
- Terraform и Ansible generation становятся менее brittle;
- появляется безопасная база для будущих AI-assisted experiments.

### Trade-offs
- усложняется generator contract;
- появятся дополнительные внутренние артефакты и тесты;
- некоторое время придётся поддерживать mixed model.

### Risks
- слишком ранний переход к programmatic emission может увеличить сложность;
- смешанный режим может временно повысить нагрузку на review;
- AI path может создать ложное ожидание «умной полной генерации» раньше времени.

### Risk mitigations
- идти волнами миграции;
- сначала ввести planning и evidence, потом менять renderer;
- оставить AI path только advisory и sandboxed.

---

## Implementation plan

### Wave 1 — Planning
- добавить ArtifactPlan и generation reports в generator runtime;
- мигрировать Terraform MikroTik и Terraform Proxmox в planning mode.

### Wave 2 — IR
- выделить typed IR families для Terraform.

### Wave 3 — Structured Ansible
- перевести inventory/group_vars/host_vars на structured emitters.

### Wave 4 — Hybrid Terraform
- вынести сложные Terraform fragments в programmatic emission.

### Wave 5 — AI advisory mode

> See [ADR 0094](0094-ai-advisory-mode-for-artifact-generation.md) for detailed implementation plan.
>
> Prerequisites: Waves 1-2 of this ADR must be complete before starting ADR 0094 implementation.

---

## Register entry for `adr/REGISTER.md`

```md
| 0092 | Smart Artifact Generation and Hybrid Rendering | Proposed | 2026-04-05 |
```

## Suggested repository updates

1. Add `adr/0092-smart-artifact-generation-and-hybrid-rendering.md`
2. Update `adr/REGISTER.md`
3. Add `schemas/artifact-plan.schema.json`
4. Add `schemas/artifact-generation-report.schema.json`
5. Add generator planning support in `topology-tools/plugins/generators/`
6. Add tests for projection -> plan -> outputs
7. Add structured serializer path for Ansible inventory family
