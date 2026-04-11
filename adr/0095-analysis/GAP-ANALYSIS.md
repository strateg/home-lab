# ADR 0095 GAP ANALYSIS

**Last updated:** 2026-04-11
**Status:** Open (initial rollout in progress)

## AS-IS

- Нет единого task namespace для интроспекции topology.
- Нет стандартизированного tree view для class/object/instance.
- Поиск экземпляров и связей выполняется ad-hoc.
- Нет штатного экспорта instance dependency graph.

## TO-BE (ADR 0095)

- Единый namespace: `task inspect:*`.
- CLI introspection toolkit поверх `build/effective-topology.json`.
- Tree views: classes/objects/instances.
- Search и dependency inspection по instance id/source id.
- DOT export для графа зависимостей.
- Capability-pack inspection (catalog + class/object dependency bindings).

## Primary Gaps

| Gap | Description | Priority | Closure target |
| --- | ----------- | -------- | -------------- |
| G1 | Отсутствие канонического inspect CLI | High | `scripts/inspection/inspect_topology.py` |
| G2 | Нет стандартных task-команд интроспекции | High | `taskfiles/inspect.yml` + include в `Taskfile.yml` |
| G3 | Нет ADR-формализации inspect contract | Medium | `adr/0095-*.md` |
| G4 | Нет operator/dev reference по inspect-командам | Medium | Обновление manual command reference |
| G5 | Нет inspect-режима для capability packs и связей class/object | Medium | `inspect_topology.py capability-packs` + `task inspect:capability-packs` |

## Risks

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Heuristic refs пропустит часть связей | Medium | Medium | Ввести v2 semantic edge typing |
| Несвежий effective snapshot даст ложную картину | Medium | Medium | Fail-fast + явная подсказка про `task validate:default` |
| Alias matching source_id может быть неоднозначным | Low | Medium | Приоритизировать `instance_id`, лог unresolved refs |
