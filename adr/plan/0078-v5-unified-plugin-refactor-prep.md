# ADR0078: v5 Unified Plugin Refactor Preparation

**Date:** 2026-03-22  
**Status:** Ready for execution  
**Related:** `adr/0078-object-module-local-template-layout.md`, `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`

---

## 1. Purpose

Подготовить v5 рефакторинг под единые правила для всех типов плагинов:

1. compilers;
2. validators;
3. generators.

---

## 2. Unified Rules Baseline

1. Архитектура строго 4-уровневая:
   - global/core;
   - class;
   - object;
   - instance.
2. Уровень class не содержит object/instance-specific зависимостей.
3. Уровень object не содержит instance-specific зависимостей.
4. Плагин уровня `N` использует только интерфейсы, которые реализует уровень `N+1`.
5. Глобальные плагины без class/object-specific имен переносятся в core/global уровень.
6. Глобальные плагины оркестрируют специализированные плагины через интерфейсы или проектные паттерны.
7. Весь код следует SOLID.

---

## 3. Refactor Inventory Deliverables

Обязательные артефакты перед стартом рефакторинга:

1. Полный реестр плагинов по семействам и уровням:
   - plugin id;
   - family (`compiler|validator|generator`);
   - level (`core|class|object|instance`);
   - owner manifest/path.
2. Карта нарушений:
   - cross-level direct imports/calls;
   - leakage высоких уровней;
   - global plugins с конкретной class/object логикой.
3. Карта целевых интерфейсов:
   - какой глобальный плагин оркестрирует какие specialized плагины;
   - какой контракт заменяет прямую зависимость.

---

## 4. Execution Batches

1. Batch A: core/global cleanup
   - отделить global orchestration от domain-specific logic;
   - подготовить shared interfaces.
2. Batch B: class-level normalization
   - убрать object/instance leakage;
   - унифицировать class-level contracts.
3. Batch C: object-level normalization
   - убрать instance leakage;
   - выровнять object manifest ownership.
4. Batch D: instance-level strictness
   - закрепить instance-only semantics;
   - убрать дублирующую оркестрацию из higher levels.

---

## 5. Mandatory Gates Per Batch

1. `python -m pytest -o addopts= v5/tests/plugin_contract/test_plugin_level_boundaries.py -q`
2. `task test:parity-v4-v5` (для затронутых parity-доменов)
3. `python -m pytest -o addopts= v5/tests/plugin_integration -q`
4. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`
5. `python v5/topology-tools/verify-framework-lock.py --strict`

---

## 6. Done Criteria for Preparation Phase

1. Inventory готов и покрывает все active plugins.
2. Violation map подтвержден и приоритизирован.
3. Batch order согласован (A -> B -> C -> D).
4. Для каждого batch есть ожидаемые touchpoints (paths/tests/gates).
5. Реализационная команда может начинать refactor без дополнительных ADR-уточнений.
