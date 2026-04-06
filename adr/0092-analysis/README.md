# Пакет документов: ADR 0092 / ADR 0093

Дата сборки: 2026-04-05

## Состав пакета

1. `adr-0092-smart-artifact-generation-and-hybrid-rendering.md`  
   Базовый ADR 0092 по умной генерации конечных артефактов.

2. `swot-adr-0092-smart-artifact-generation.md`  
   SWOT-анализ ADR 0092.

3. `../0093-artifact-plan-schema-and-generator-runtime-integration.md`  
   Companion ADR 0093 с implementation-level контрактом.

4. `../0093-analysis/swot-adr-0093-artifact-plan.md`  
   SWOT-анализ ADR 0093.

5. `decision-note-0092-0093.md`  
   Краткая связка между ADR 0092 и ADR 0093: что даёт первый и зачем нужен второй.

## Как читать комплект

- **ADR 0092** — архитектурная рамка: как сделать генерацию артефактов умнее, не ломая текущую цепочку.
- **ADR 0093** — прикладная спецификация следующего шага: как встроить ArtifactPlan, evidence и runtime integration.
- **SWOT** — помогает оценить, где сильные стороны, где архитектурные риски, что является рыночной/инженерной возможностью и что может пойти не так.

## Нормативные analysis-артефакты

Для обоих ADR поддерживаются обязательные документы:
- `GAP-ANALYSIS.md`
- `IMPLEMENTATION-PLAN.md`
- `CUTOVER-CHECKLIST.md`
