# SWOT-анализ ADR 0094: AI Advisory Mode for Artifact Generation

## Краткий вывод

ADR 0094 правильно выделяет AI-assisted generation в отдельный контракт с explicit trust boundaries.
Главная сила — security-first подход с sandbox и redaction.
Главный риск — premature expectations от AI capabilities.

---

## Strengths

### S1. Security-First Architecture

ADR 0094 ставит безопасность на первое место:
- Secrets redaction как обязательный первый шаг.
- Sandbox isolation для всех AI interactions.
- No auto-promotion policy.

Это правильный подход для infrastructure-as-code, где утечка секретов критична.

### S2. Clear Trust Boundaries

Явное разделение:
- **Deterministic path** — trusted, production-ready.
- **AI path** — untrusted until promoted.
- **Human approval** — mandatory gate.

Это защищает от случайного использования непроверенных артефактов.

### S3. Wave-Gated Rollout

Постепенное внедрение:
1. Sandbox only (no AI yet).
2. Advisory only (no modifications).
3. Assisted with approval.
4. Expansion.

Каждая волна имеет gate criteria — нельзя перейти к следующей без проверки.

### S4. Audit Trail

Полная трассировка:
- Все AI запросы логируются.
- Все approvals записываются.
- Rollback отслеживается.

Это важно для compliance и debugging.

### S5. Separation from ADR 0092

Выделение в отдельный ADR:
- ADR 0092 остаётся focused на deterministic generation.
- AI path получает собственный lifecycle.
- Нет смешения production и experimental concerns.

---

## Weaknesses

### W1. Complexity Overhead

AI advisory mode добавляет значительную инфраструктуру:
- Redaction pipeline.
- Sandbox environment.
- Audit logging.
- Diff review interface.
- Promotion workflow.

Это требует maintenance даже если AI используется редко.

### W2. Latency in Assisted Mode

Human approval добавляет latency:
- AI генерирует кандидатов.
- Человек ревьюит diff.
- Человек approves/rejects.

Для частых операций это может быть неудобно.

### W3. AI Backend Lock-in Risk

Pluggable adapters — хорошо, но:
- Разные AI имеют разные capabilities.
- Prompts могут быть model-specific.
- Switching backends может требовать re-tuning.

### W4. Limited Autonomous Mode

ADR явно запрещает autonomous mode:
- Всегда требуется human approval.
- Нет auto-promotion.

Это ограничивает automation scenarios.

---

## Opportunities

### O1. Safe AI Exploration

ADR 0094 создаёт безопасную песочницу для экспериментов с AI:
- Можно пробовать разные AI backends.
- Можно тестировать prompts.
- Без риска для production.

### O2. Learning from AI Suggestions

Даже в advisory mode AI может:
- Предлагать оптимизации.
- Находить patterns.
- Указывать на потенциальные проблемы.

Это обучающий инструмент для команды.

### O3. Future Autonomous Mode

После накопления опыта:
- Можно собрать статистику по AI accuracy.
- Можно идентифицировать safe scenarios.
- Можно предложить limited autonomous mode в отдельном ADR.

### O4. Compliance Documentation

Audit trail может использоваться для:
- Compliance reports.
- Security audits.
- Change management documentation.

### O5. Multi-Provider Strategy

Pluggable adapters позволяют:
- Сравнивать разные AI providers.
- Использовать specialized models для разных families.
- Fallback при недоступности одного provider.

---

## Threats

### T1. Premature AI Expectations

Наличие AI mode может создать ожидание:
- "AI сгенерирует всё автоматически".
- "AI заменит ручную работу".

Reality: AI — advisory tool, не автономный генератор.

### T2. Redaction Gaps

Несмотря на тройную защиту (registry + annotations + patterns):
- Новые secret patterns могут быть пропущены.
- Edge cases в complex structures.
- False negatives критичны.

### T3. AI Hallucinations

AI может генерировать:
- Несуществующие resource types.
- Неправильные конфигурации.
- Subtle bugs.

Validation pipeline должен ловить это, но не всё.

### T4. Vendor Lock-in

Если prompts и workflows оптимизированы под один AI:
- Switching costs растут.
- Negotiating power падает.

### T5. Maintenance Burden

AI infrastructure требует:
- Updating prompts.
- Adapting to API changes.
- Security patching.
- Audit log management.

Это ongoing cost даже при low usage.

---

## Итоговая оценка

### Архитектурная ценность
Высокая. Правильное разделение concerns и security-first подход.

### Практическая ценность
Средняя на текущем этапе. Польза появится после Wave 2-3.

### Риск внедрения
Низкий благодаря wave-gated rollout и sandbox-first.

### Приоритет
Низкий-средний. Зависит от ADR 0092/0093. Не блокирует основную работу.

### Рекомендация

1. **Принять ADR 0094** как часть пакета 0092/0093/0094.
2. **Не начинать реализацию** до завершения Wave 1-2 ADR 0092/0093.
3. **Wave 1 (Sandbox)** может начаться параллельно с Wave 3 ADR 0092.
4. **Установить clear expectations**: AI — experimental, не production-critical.

---

## SWOT Matrix

```
┌─────────────────────────────────────┬─────────────────────────────────────┐
│           STRENGTHS                 │           WEAKNESSES                │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ S1. Security-first architecture     │ W1. Complexity overhead             │
│ S2. Clear trust boundaries          │ W2. Latency in assisted mode        │
│ S3. Wave-gated rollout              │ W3. AI backend lock-in risk         │
│ S4. Audit trail                     │ W4. Limited autonomous mode         │
│ S5. Separation from ADR 0092        │                                     │
├─────────────────────────────────────┼─────────────────────────────────────┤
│           OPPORTUNITIES             │           THREATS                   │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ O1. Safe AI exploration             │ T1. Premature AI expectations       │
│ O2. Learning from AI suggestions    │ T2. Redaction gaps                  │
│ O3. Future autonomous mode          │ T3. AI hallucinations               │
│ O4. Compliance documentation        │ T4. Vendor lock-in                  │
│ O5. Multi-provider strategy         │ T5. Maintenance burden              │
└─────────────────────────────────────┴─────────────────────────────────────┘
```
