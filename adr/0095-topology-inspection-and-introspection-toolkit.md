# ADR 0095: Topology Inspection and Introspection Toolkit

**Status:** Proposed  
**Date:** 2026-04-08  
**Depends on:** ADR 0062, ADR 0077, ADR 0080, ADR 0092, ADR 0093

---

## Context

V5 topology model is rich, but operator/developer introspection is fragmented:
- class/object/instance relations are visible only indirectly via compiled artifacts;
- no single CLI surface for quick hierarchy inspection;
- instance dependency exploration requires ad-hoc `rg`/manual parsing;
- no standard command family in `task` for topology diagnostics.

This slows down:
- migration and rollout review (ADR0092-0094 flows),
- root-cause analysis for configuration drift,
- authoring of new instances/objects,
- acceptance test evidence collection.

---

## Problem Statement

Нужен единый, repeatable и scriptable инструмент для:
1. Просмотра дерева классов, объектов и экземпляров.
2. Поиска экземпляров по паттернам.
3. Быстрой интроспекции графа зависимостей экземпляров.
4. Экспорта dependency graph для визуализации/дебага.
5. Стандартизированного запуска через `task inspect:*`.

---

## Decision

Принять unified inspection toolkit поверх `build/effective-topology.json` с entrypoint:

`task inspect:default`

и стандартным набором подкоманд.

### D1. Канонический CLI интроспекции

Вводится скрипт:

`scripts/inspection/inspect_topology.py`

Канонический источник данных:
- `build/effective-topology.json` (по умолчанию),
- переопределяется флагом `--effective`.

### D2. Стандартный task namespace

Вводится namespace `inspect` с командами:
- `task inspect:default` — сводка (classes/objects/instances + группы),
- `task inspect:classes` — дерево классов,
- `task inspect:objects` — объекты, сгруппированные по class,
- `task inspect:instances` — экземпляры по layer,
- `task inspect:search QUERY='<regex>'` — поиск экземпляров,
- `task inspect:deps INSTANCE='<id|source_id>' [MAX_DEPTH=N]` — локальный граф зависимостей,
- `task inspect:deps-dot [OUTPUT=path]` — экспорт полного instance dependency graph в DOT.

### D3. Контракт графа зависимостей

Graph extraction contract:
- источники ребер: поля, оканчивающиеся на `_ref` / `_refs`;
- сканируются `instance_data` и runtime-метаданные `instance`;
- alias-resolution:
  - `instance_id` (`inst.*`),
  - `source_id`,
  - short alias без префикса `inst.`;
- unresolved refs сохраняются отдельно и показываются как отдельные узлы при `deps-dot`.

### D4. Fail-fast поведение

Если effective topology отсутствует, toolkit завершает выполнение с actionable ошибкой:
- запускать после `task validate:default` (или другой команды, формирующей `build/effective-topology.json`).

### D5. Scope ограничения (v1)

В v1 toolkit:
- read-only;
- не модифицирует topology/generated;
- не выполняет online-интроспекцию внешних систем;
- не заменяет schema/contract validation.

---

## Consequences

### Positive

- Стандартизированная диагностика topology модели.
- Быстрый доступ к деревьям и зависимостям без ad-hoc скриптов.
- Улучшение DX для ADR0092-0094 миграционных проверок и TUC evidence.
- Единый task UX (`inspect:*`) в стиле ADR0077.

### Negative / Trade-offs

- Dependency graph в v1 зависит от naming-конвенций (`*_ref(s)`), возможны false negatives.
- Для корректности требуется свежий effective artifact.
- Без layer-aware semantic rules возможны ребра, которые логически допустимы, но не являются runtime-dependency.

---

## Rollout Plan

1. Ввести `inspect` namespace и базовые команды.
2. Зафиксировать ADR и добавить в `adr/REGISTER.md`.
3. Обновить manual command reference.
4. Расширить toolkit (следующая итерация):
   - semantic edge typing (network/storage/runtime),
   - machine-readable JSON output mode,
   - optional graph filters по layer/group/capability.

---

## Acceptance Criteria

- `task inspect:default` выполняется на актуальном effective topology.
- Команды `classes|objects|instances|search|deps|deps-dot` доступны и документированы.
- `task inspect:deps INSTANCE='rtr-mikrotik-chateau'` возвращает direct/transitive зависимости.
- `task inspect:deps-dot` создает DOT-файл в `build/diagnostics/`.
- ADR register содержит запись ADR0095.
