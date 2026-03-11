# План дальнейшего анализа ADR 0063

> Historical note: this document is a pre-implementation planning artifact for ADR 0063.
> The plugin microkernel runtime is now implemented, and operational cutover/governance is further defined by `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md` and related analysis documents.

## Цель
Подготовить обоснованное и безопасное решение для перехода к plugin-microkernel модели (compiler/validators/generators) без регрессий относительно ADR 0062/0064.

## 1. Фиксация исходного состояния (Baseline)
- Подтвердить текущие инварианты пайплайна `validate-v5` и `compile-topology`.
- Зафиксировать текущие проблемы в артефактах:
  - потеря `embedded_in` и части групп при экспорте `instance-bindings`;
  - поведение `--strict-model-lock` для L2/L3;
  - дублирование валидационной логики между `compile-topology.py` и `check-capability-contract.py`.
- Результат: документ `baseline.md` с воспроизводимыми командами и фактическими ошибками.

## 2. Scope и границы ADR 0063
- Разделить, что входит в 0063, а что остается в 0062/0064:
  - входит: runtime extensibility, plugin lifecycle, deterministic execution;
  - не входит: изменение доменной модели firmware/os и layer contracts.
- Определить минимальный функциональный срез (MVP) для первой итерации.
- Результат: `scope.md` + список `in/out`.

## 3. Проектирование Plugin API v1
- Формализовать контракт plugin manifest:
  - `id`, `kind`, `entry`, `api_version`, `stages`, `order`, `depends_on`, опционально `capabilities/config_schema`.
- Описать runtime-контракты:
  - `PluginContext`, входные/выходные данные по стадиям;
  - единый diagnostics sink;
  - политика обработки exception/crash.
- Результат: `plugin-api-v1.md` + черновик schema (`plugin-manifest.schema.json`).

## 4. Архитектура микрокернела
- Спроектировать компоненты:
  - discovery/loader;
  - registry;
  - dependency resolver (topological sort + cycle detection);
  - stage executor;
  - compatibility guard (`api_version`, profile restrictions, model lock constraints).
- Зафиксировать deterministic ordering:
  - stage -> depends_on -> order -> lexical `id`.
- Результат: `microkernel-architecture.md` + sequence diagram.

## 5. План миграции без регрессий
- Этап 1: обернуть существующие генераторы в plugins (без изменения поведения).
- Этап 2: перенести YAML/JSON validators в plugins (с паритетом diagnostics).
- Этап 3: перенести compiler transforms в plugins, удалить hardcoded dispatch.
- Для каждого этапа определить:
  - критерии входа/выхода;
  - rollback стратегию;
  - контрольные метрики.
- Результат: `migration-phases.md`.

## 6. Стратегия тестирования и quality gates
- Ввести тесты на:
  - plugin order/dependency/cycle;
  - parity diagnostics JSON/TXT до/после;
  - parity `effective-topology.json` на golden fixtures;
  - fail-fast на несовместимость версии API.
- Обновить test discovery для v5 (`pytest` конфигурация/команды в CI).
- Результат: `test-strategy.md` + матрица тестов.

## 7. Риски и решения
- Риск: дрейф API плагинов.
  - Митигация: version negotiation + контрактные тесты.
- Риск: скрытые side-effects в plugin hooks.
  - Митигация: stage-scoped интерфейсы + запрет недокументированных мутаций.
- Риск: сложность отладки.
  - Митигация: строгая plugin attribution в diagnostics и execution trace.
- Результат: `risks-and-mitigations.md`.

## 8. Подготовка к implementation-ready статусу
- Чеклист “готово к разработке”:
  - baseline стабилен и воспроизводим;
  - scope согласован;
  - Plugin API v1 зафиксирован;
  - схема manifest и diagnostics extension согласованы;
  - миграционный план и тест-гейты утверждены.
- Результат: `implementation-readiness-checklist.md`.

## Ожидаемые артефакты анализа
- `adr/0063-analysis/baseline.md`
- `adr/0063-analysis/scope.md`
- `adr/0063-analysis/plugin-api-v1.md`
- `adr/0063-analysis/microkernel-architecture.md`
- `adr/0063-analysis/migration-phases.md`
- `adr/0063-analysis/test-strategy.md`
- `adr/0063-analysis/risks-and-mitigations.md`
- `adr/0063-analysis/implementation-readiness-checklist.md`

## Порядок выполнения
1. Baseline и фиксация проблем.
2. Scope и API v1.
3. Архитектура микрокернела.
4. Миграционный план.
5. Тестовая стратегия.
6. Риски и readiness-gate.
