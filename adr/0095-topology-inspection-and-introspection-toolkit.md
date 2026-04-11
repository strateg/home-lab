# ADR 0095: Topology Inspection and Introspection Toolkit

**Status:** Implemented (v1)  
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

After v1 implementation, the remaining problem is no longer toolkit absence, but toolkit optimization:
- dependency traceability is present but heuristic,
- class inheritance is visible but not isolated as a dedicated inspection question,
- capability information is spread across class/object/pack structures,
- some outputs are materially larger than compact first-screen summaries,
- multiple concerns are concentrated in one CLI module.

---

## Problem Statement

Нужен единый, repeatable и scriptable инструмент для:
1. Просмотра дерева классов, объектов и экземпляров.
2. Поиска экземпляров по паттернам.
3. Быстрой интроспекции графа зависимостей экземпляров.
4. Экспорта dependency graph для визуализации/дебага.
5. Инспекции capability packs и их зависимостей от object classes.
6. Стандартизированного запуска через `task inspect:*`.

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
- `task inspect:summary-json` — machine-readable JSON summary,
- `task inspect:classes` — дерево классов,
- `task inspect:inheritance [CLASS=<class_ref>]` — summary/focused lineage inspection,
- `task inspect:inheritance-json [CLASS=<class_ref>]` — machine-readable inheritance view,
- `task inspect:objects` — объекты, сгруппированные по class,
- `task inspect:objects-detailed` — расширенный детальный object view,
- `task inspect:instances` — экземпляры по layer,
- `task inspect:instances-detailed` — расширенный детальный instance view,
- `task inspect:search QUERY='<regex>'` — поиск экземпляров,
- `task inspect:deps INSTANCE='<id|source_id>' [MAX_DEPTH=N]` — локальный граф зависимостей,
- `task inspect:deps-typed-shadow INSTANCE='<id|source_id>'` — dependency view + non-authoritative typed relation shadow,
- `task inspect:deps-json INSTANCE='<id|source_id>'` — machine-readable dependency view,
- `task inspect:deps-json-typed-shadow INSTANCE='<id|source_id>'` — dependency JSON + typed shadow block,
- `task inspect:deps-dot [OUTPUT=path]` — экспорт полного instance dependency graph в DOT,
- `task inspect:capability-packs` — инспекция capability packs и матрицы `class -> packs -> objects`,
- `task inspect:capabilities [CLASS=<class_ref>|OBJECT=<object_id>]` — unified capability relation inspection,
- `task inspect:capabilities-json [CLASS=<class_ref>|OBJECT=<object_id>]` — machine-readable capability relation view.

Instance-scoped commands (`summary`, `instances`, `search`, `deps`, `deps-dot` and their JSON/shadow variants) MAY be narrowed with optional `LAYER=<layer>` and/or `GROUP=<instance_group>` filters in task wrappers.

Optimization direction after v1:
- inspection surface SHOULD evolve around question-oriented domains rather than only entity dumps:
  - overview,
  - inheritance / lineage,
  - dependency traceability,
  - capability traceability,
  - export / machine-readable views;
- public `task inspect:*` namespace remains the stable operator contract.

### D3. Контракт графа зависимостей

Graph extraction contract:
- источники ребер: поля, оканчивающиеся на `_ref` / `_refs`;
- сканируются `instance_data` и runtime-метаданные `instance`;
- alias-resolution:
  - `instance_id` (`inst.*`),
  - `source_id`,
  - short alias без префикса `inst.`;
- unresolved refs сохраняются отдельно и показываются как отдельные узлы при `deps-dot`.

### D4. Контракт инспекции capability packs

Capability-pack inspection contract:
- source of truth для pack catalog: `framework.capability_packs` из topology manifest;
- class dependencies: `classes.*.capability_packs` из effective topology;
- object bindings: `objects.*.enabled_packs` + class binding (`materializes_class` / `class_ref` / `extends_class`);
- toolkit показывает:
  - snapshot pack catalog (`pack_id`, `class_ref`, capability count, object usage),
  - matrix `class -> declared packs -> bound objects`,
  - contract warnings:
    - class pack refs отсутствуют в catalog,
    - object enabled packs отсутствуют в catalog,
    - object enabled pack не объявлен в class `capability_packs`.

Capability inspection after v1 SHOULD cover three descriptive layers:
- class intent (`required_capabilities`, `optional_capabilities`, `capability_packs`);
- object effective functionality (`enabled_capabilities`, `enabled_packs`);
- pack aggregation (`capabilities`, `class_ref`, object usage).

### D5. Optimization direction for implementation boundaries

The canonical CLI entrypoint remains:

`scripts/inspection/inspect_topology.py`

but internal implementation SHOULD be decomposed into reusable concerns rather than one expanding procedural surface:
- artifact loading,
- normalized indexes / resolvers,
- relation extractors,
- output formatters / presenters,
- CLI command wiring.

This preserves one public entrypoint while allowing code minimization and internal reuse.

### D6. Compact vs detailed output contract

Human-facing inspection output SHOULD default to compact, high-signal summaries.

Detailed output remains admissible, but SHOULD be explicit rather than implicit.

Compact output goals:
- show the highest-value relationships first;
- prefer grouped summaries over raw full dumps by default;
- separate overview questions from deep trace questions;
- keep machine-readable output separate from human-readable compact output.

### D7. Machine-readable output direction

The next iteration SHOULD add structured machine-readable output for inspection commands where stable contracts are feasible.

Initial machine-readable priority areas:
- dependency traceability,
- inheritance / lineage,
- capability relations,
- overview summaries.

### D8. Semantic relation typing direction

The next iteration SHOULD evolve from syntax-only relation discovery toward semantic relation typing where feasible.

Target semantic domains include:
- network relations,
- storage relations,
- runtime / host-placement relations,
- capability relations,
- inheritance / binding relations.

Typed relations are intended to reduce ambiguity between “reference exists” and “runtime-significant dependency”.

Execution note (2026-04-11):
- semantic relation typing is currently delivered in shadow mode for `deps` (`--typed-shadow`) and corresponding JSON shadow block;
- diagnostics artifacts for promotion-gate evidence are available via:
  - `task inspect:typed-shadow-report` (`build/diagnostics/typed-shadow-report.{json,txt}`)
  - `task inspect:typed-shadow-gate` (same artifacts + threshold exit-code gate);
- validate-lane aliases expose the same diagnostics in validation workflows:
  - `task validate:typed-shadow-report`
  - `task validate:typed-shadow-gate`;
- current home-lab snapshot reaches G2 threshold gate (`coverage=100.0`, `generic_ref_share=0.72`), while semantic typing remains non-authoritative pending full promotion decision;
- parity guards verify that enabling typed shadow does not change authoritative baseline dependency edge sets (`deps --json` vs `deps --json --typed-shadow`);
- baseline dependency extraction remains authoritative until promotion criteria are accepted (see `adr/0095-analysis/SEMANTIC-TYPING-PROMOTION-CRITERIA.md`).

### D9. Fail-fast поведение

Если effective topology отсутствует, toolkit завершает выполнение с actionable ошибкой:
- запускать после `task validate:default` (или другой команды, формирующей `build/effective-topology.json`).

### D10. Scope ограничения (v1)

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
- После v1 дальнейшая оптимизация может происходить без смены канонического entrypoint.

### Negative / Trade-offs

- Dependency graph в v1 зависит от naming-конвенций (`*_ref(s)`), возможны false negatives.
- Для корректности требуется свежий effective artifact.
- Без layer-aware semantic rules возможны ребра, которые логически допустимы, но не являются runtime-dependency.
- Более компактные и question-oriented surfaces требуют дополнительной дисциплины в contract testing.

---

## Rollout Plan

1. Ввести `inspect` namespace и базовые команды.
2. Зафиксировать ADR и добавить в `adr/REGISTER.md`.
3. Обновить manual command reference.
4. Оптимизировать toolkit (следующая итерация):
   - internal modularization behind the canonical CLI,
   - question-oriented inspection surface,
   - compact-vs-detailed output discipline,
   - machine-readable JSON output mode,
   - semantic edge typing (network/storage/runtime/capability/inheritance),
   - optional graph filters по layer/group/capability.

---

## Acceptance Criteria

- `task inspect:default` выполняется на актуальном effective topology.
- Команды `classes|inheritance|objects|instances|search|deps|deps-dot|capability-packs|capabilities` доступны и документированы.
- Machine-readable JSON paths доступны для `summary|deps|inheritance|capabilities`.
- `task inspect:deps INSTANCE='rtr-mikrotik-chateau'` возвращает direct/transitive зависимости.
- `task inspect:deps-typed-shadow INSTANCE='rtr-mikrotik-chateau'` добавляет non-authoritative typed shadow без изменения baseline dependency extraction.
- `task inspect:deps-dot` создает DOT-файл в `build/diagnostics/`.
- `task inspect:default LAYER='L5' GROUP='services'` и `task inspect:deps-dot LAYER='L5' GROUP='services'` корректно ограничивают inspection scope.
- `task inspect:capability-packs` показывает capability-pack зависимости от object classes.
- `task inspect:capabilities` показывает unified class/object/pack capability traceability.
- ADR register содержит запись ADR0095.

---

## References

- `adr/0095-analysis/GAP-ANALYSIS.md`
- `adr/0095-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0095-analysis/SWOT-ANALYSIS.md`
- `adr/0095-analysis/REFACTORING-PLAN.md`
- `adr/0095-analysis/OPTIMIZATION-IMPLEMENTATION-PLAN.md`
- `adr/0095-analysis/SEMANTIC-TYPING-PROMOTION-CRITERIA.md`
- `scripts/inspection/inspect_topology.py`
- `taskfiles/inspect.yml`
- `tests/test_inspect_topology.py`
