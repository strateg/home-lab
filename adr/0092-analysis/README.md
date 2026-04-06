# Пакет документов: ADR 0090 / ADR 0091 SWOT

Дата сборки: 2026-04-05

## Состав пакета

1. `adr-0090-smart-artifact-generation-and-hybrid-rendering.md`  
   Базовый ADR 0090 по умной генерации конечных артефактов.

2. `swot-adr-0090-smart-artifact-generation.md`  
   SWOT-анализ ADR 0090.

3. `adr-0091-candidate-artifact-plan-schema-and-generator-runtime-integration.md`  
   Черновик companion ADR 0091.  
   Статус: **candidate / implementation companion**, не утверждённый исходный ADR.

4. `swot-adr-0091-candidate.md`  
   SWOT-анализ для candidate ADR 0091.

5. `decision-note-0090-0091.md`  
   Краткая связка между ADR 0090 и ADR 0091: что даёт первый и зачем нужен второй.

## Как читать комплект

- **ADR 0090** — архитектурная рамка: как сделать генерацию артефактов умнее, не ломая текущую цепочку.
- **ADR 0091 (candidate)** — прикладная спецификация следующего шага: как встроить ArtifactPlan, evidence и runtime integration.
- **SWOT** — помогает оценить, где сильные стороны, где архитектурные риски, что является рыночной/инженерной возможностью и что может пойти не так.

## Важная оговорка

В рамках этого пакета **ADR 0091 оформлен как candidate**, потому что ранее он не был принят как отдельный готовый ADR.  
SWOT по 0091 сделан именно для этого candidate-документа.
