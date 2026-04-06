# adr/0093-artifact-plan-schema-and-generator-runtime-integration.md

# ADR 0093: ArtifactPlan Schema and Generator Runtime Integration

**Status:** Candidate / Draft  
**Date:** 2026-04-05  
**Depends on:** ADR 0063, ADR 0065, ADR 0066, ADR 0074, ADR 0077, ADR 0080, ADR 0090

---

## Context

ADR 0090 задаёт направление Smart Artifact Generation:
- planning перед rendering;
- typed IR;
- generation evidence;
- hybrid rendering model;
- selective regeneration и obsolete management.

Чтобы ADR 0090 стал внедряемым, нужен следующий технический шаг:
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

---

## Acceptance Criteria

Считается внедрённым, когда:
- есть schema для ArtifactPlan;
- хотя бы один generator публикует валидный ArtifactPlan;
- CI проверяет projection -> plan -> outputs;
- validate stage не ломает legacy generators;
- assemble/build умеют читать generation metadata.

---

## Consequences

### Positive
- идеи ADR 0090 получают конкретный runtime-контур;
- появляется объяснимость генерации;
- становится возможной более умная выборочная регенерация;
- упрощается future integration для audit и AI advisory mode.

### Trade-offs
- появляется дополнительный слой артефактов и тестов;
- придётся некоторое время поддерживать mixed runtime mode.

### Risks
- можно слишком рано усложнить runtime;
- schema drift между plan/report и runtime-кодом;
- дублирование логики между planning и render stages.

### Mitigations
- мигрировать по 1–2 generator family;
- держать schemas минимальными;
- не переносить лишнюю бизнес-логику в plan/report слой сразу.
