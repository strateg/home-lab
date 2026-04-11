# ADR 0095 GAP ANALYSIS

**Last updated:** 2026-04-11
**Status:** In progress (Wave 3 execution active)

## AS-IS

- Нет единого task namespace для интроспекции topology.
- Нет стандартизированного tree view для class/object/instance.
- Поиск экземпляров и связей выполняется ad-hoc.
- Нет штатного экспорта instance dependency graph.

## TO-BE (ADR 0095)

- Единый namespace: `task inspect:*`.
- CLI introspection toolkit поверх `build/effective-topology.json`.
- Question-oriented inspection surface поверх единого CLI.
- Tree/inheritance views: classes/objects/instances/lineage.
- Search и dependency inspection по instance id/source id.
- DOT export + machine-readable export для графа зависимостей.
- Capability inspection across class/object/pack descriptive layers.
- Compact human-readable output with explicit detailed expansions.
- Internal modularization behind the canonical CLI entrypoint.

## Primary Gaps

| Gap | Description | Priority | Closure target |
| --- | ----------- | -------- | -------------- |
| G1 | Отсутствие канонического inspect CLI | High | `scripts/inspection/inspect_topology.py` |
| G2 | Нет стандартных task-команд интроспекции | High | `taskfiles/inspect.yml` + include в `Taskfile.yml` |
| G3 | Нет ADR-формализации inspect contract | Medium | `adr/0095-*.md` |
| G4 | Нет operator/dev reference по inspect-командам | Medium | Обновление manual command reference |
| G5 | Нет inspect-режима для capability packs и связей class/object | Medium | `inspect_topology.py capability-packs` + `task inspect:capability-packs` |
| G6 | Нет выделенной inheritance-oriented inspection surface | Medium | lineage/inheritance-oriented inspect views |
| G7 | Нет unified capability inspection across class/object/pack layers | High | question-oriented capability views |
| G8 | Нет compact-vs-detailed output contract | High | compact defaults + explicit detailed/machine-readable modes |
| G9 | Нет machine-readable inspection contract | High | JSON output modes for stable domains |
| G10 | Нет semantic relation typing | High | typed relation extraction for dependency/capability/inheritance domains |
| G11 | Внутренние concerns inspection CLI сконцентрированы в одном модуле | High | internal modularization behind canonical CLI |

## Closure Snapshot (2026-04-11)

| Gap | Current state |
| --- | ------------- |
| G1 | Closed — canonical inspect CLI implemented and stabilized by contract tests |
| G2 | Closed — `task inspect:*` namespace wired and used in smoke matrix |
| G3 | Closed — ADR0095 formalized and synchronized with analysis artifacts |
| G4 | Open — broader manual command reference still needs explicit operator section refresh |
| G5 | Closed — capability-pack inspection implemented and validated |
| G6 | Closed — inheritance-oriented inspection (`inheritance`) implemented and validated |
| G7 | Closed — unified capability surface (`capabilities`) implemented and validated |
| G8 | Closed — compact defaults + explicit detailed modes for high-volume views, plus layer/group filters for instance-scoped diagnostics |
| G9 | Closed — machine-readable JSON contracts added for overview/dependency/inheritance/capability domains |
| G10 | Partial — semantic typing delivered as shadow mode for `deps`; promotion to authoritative semantic model is pending |
| G11 | Closed — loader/index/relation/presenter/export concerns extracted behind canonical CLI |

## Risks

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Heuristic refs пропустит часть связей | Medium | Medium | Ввести v2 semantic edge typing |
| Несвежий effective snapshot даст ложную картину | Medium | Medium | Fail-fast + явная подсказка про `task validate:default` |
| Alias matching source_id может быть неоднозначным | Low | Medium | Приоритизировать `instance_id`, лог unresolved refs |
| Рост inspection surface ухудшит maintainability | Medium | High | Разделить loaders/indexes/extractors/formatters внутри canonical CLI |
| Расширение traceability ухудшит compactness | High | Medium | Разделить compact overview и explicit detailed modes |
