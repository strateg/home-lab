# План реализации по результатам implementation improvement analysis

**Дата:** 2026-04-10
**Основание:** `adr/analysis/IMPLEMENTATION-IMPROVEMENT-ANALYSIS.md`
**Статус:** Draft implementation plan

---

## Цели

- Снизить архитектурные и эксплуатационные риски в `topology-tools/`.
- Повысить надёжность plugin kernel через прямые unit-тесты критических путей.
- Упростить поддержку компилятора за счёт пошаговой декомпозиции `V5Compiler`.
- Усилить безопасность AI sandbox через строгую фильтрацию окружения.
- Сохранить CLI/API совместимость и существующие plugin manifest contracts.

---

## Non-Goals

- Не менять вручную `generated/`.
- Не создавать root `v4/` или `v5/`.
- Не менять внешний CLI-контракт `topology-tools/compile-topology.py` без отдельного contract-test покрытия.
- Не переносить AI helper modules или discoverer classes до отдельного audit-решения по stage affinity.
- Не объединять `Diagnostic` / `PluginDiagnostic` без compatibility layer и тестов обратной совместимости.
- Не выносить analysis/plan из `adr/analysis/` без отдельного решения по layout.

---

## Execution Model

Каждая wave должна быть PR-sized. Если wave затрагивает разные подсистемы, она делится на несколько PR.

Общий порядок:

1. Закрыть low-effort security risk.
2. Добавить тестовый каркас для kernel API.
3. Декомпозировать `V5Compiler` только после появления страховочных тестов.
4. Убирать DRY-дубли и диагностические модели после покрытия edge-cases.
5. Переносить observability и orchestration UX в отдельные PR после стабилизации core behavior.

---

## Wave 0: Plan Hygiene

### Scope

1. Зафиксировать этот implementation plan рядом с analysis source.
2. Исправить фактическую ошибку в analysis summary: документ содержит 12 областей, а не 10.
3. Явно зафиксировать, что `adr/analysis/IMPLEMENTATION-IMPROVEMENT-ANALYSIS.md` является canonical analysis source, пока не принято отдельное layout-решение.

### Entry Criteria

- `adr/analysis/IMPLEMENTATION-IMPROVEMENT-ANALYSIS.md` прочитан полностью.
- `docs/ai/rules/adr-governance.md` применён для изменений в `adr/**`.

### Exit Criteria

- План покрывает все 12 областей анализа.
- Валидация ADR/agent-rule consistency выполнена или явно указана как не применимая с причиной.

### Validation

- `task validate:adr-consistency`

---

## Wave 1A: AI Sandbox Env Security

### Covered Analysis Areas

- Area 6: Security — Env Sanitization

### Scope

1. Перевести `sanitize_environment()` в `topology-tools/plugins/generators/ai_sandbox.py` на allowlist-first модель.
2. Сохранить deny-patterns как дополнительную защиту для `AWS_*`, `AZURE_*`, `GCP_*`, `GH_*`, `GITHUB_*`, `CI_*`, `TF_VAR_*`, `*_KEY`, `PRIVATE_KEY`, `SSH_*`, `SOPS_*`, `AGE_*`.
3. Добавить unit/contract tests для безопасных и опасных env vars.
4. Проверить call sites в `compile-topology.py`, где используется `sanitize_environment(dict(os.environ))`.

### Entry Criteria

- Текущие AI sandbox tests найдены или зафиксировано их отсутствие.
- Определён минимальный allowlist: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR`, `TZ`, repo-specific non-secret runtime keys if needed.

### Exit Criteria

- Опасные переменные не попадают в sandbox env.
- Безопасные переменные, необходимые для локального выполнения, не ломают AI advisory/assisted flow.
- Поведение удаления env keys отражено в audit output.

### Validation

- Targeted pytest for `ai_sandbox`.
- Relevant AI advisory/assisted contract tests if present.
- `task test:plugin-contract`

### Suggested PR Split

- PR 1: sanitizer implementation + tests only.

---

## Wave 1B: Kernel API Test Foundation

### Covered Analysis Areas

- Area 4: Unit-тесты ядра

### Scope

1. Добавить `tests/plugin_api/test_plugin_context.py`.
2. Покрыть `publish` / `subscribe`, scope isolation, missing key behavior, and thread-safety basics.
3. Добавить `tests/plugin_api/test_parallel_execution.py` для concurrent execution и failure propagation.

### Entry Criteria

- Зафиксированы публичные API из `topology-tools/kernel/plugin_base.py` и `topology-tools/kernel/plugin_registry.py`, которые тестируются напрямую.
- Тесты не зависят от полного repository topology fixture, если это не требуется контрактом.

### Exit Criteria

- Kernel API имеет прямые unit-тесты для data exchange и параллельного execution path.
- Тесты стабильны при повторном запуске.

### Validation

- `task test:plugin-api`
- `task test:plugin-contract`

### Suggested PR Split

- PR 2: `PluginContext` tests.
- PR 3: parallel execution tests.

---

## Wave 2: V5Compiler Decomposition

### Covered Analysis Areas

- Area 1: God Object — `V5Compiler`

### Scope

1. Ввести `AiConfig` dataclass для AI-related параметров.
2. Вынести общий advisory/assisted preflight в `_prepare_ai_session()`.
3. Вынести AI session orchestration в `topology-tools/compiler_ai_sessions.py`.
4. Вынести CLI parser/main в `topology-tools/compiler_cli.py`, сохранив существующий `compile-topology.py` как стабильный entrypoint.

### Entry Criteria

- Wave 1B tests проходят.
- Зафиксирован baseline для `compile-topology.py --help` и основных compile flags.

### Exit Criteria

- Внешний CLI contract не изменён.
- AI advisory/assisted behavior покрыт существующими или добавленными tests.
- `V5Compiler` теряет часть orchestration responsibility без изменения compile output.

### Validation

- Targeted pytest for compiler CLI/AI session extraction.
- `task test:plugin-api`
- `task test:plugin-contract`
- `task test:plugin-integration`
- `.venv/bin/python topology-tools/compile-topology.py --help`

### Suggested PR Split

- PR 4: `AiConfig` + `_prepare_ai_session()` with no module relocation.
- PR 5: extract `compiler_ai_sessions.py`.
- PR 6: extract `compiler_cli.py` while preserving entrypoint.

---

## Wave 3A: Kernel Ordering And Manifest Contracts

### Covered Analysis Areas

- Area 3: `STAGE_ORDER` duplication
- Area 4: Unit-тесты ядра

### Scope

1. Добавить `tests/plugin_api/test_execution_order.py`.
2. Покрыть cycle detection, diamond dependencies, stage/phase ordering, and deterministic tie handling where applicable.
3. Убрать локальный `STAGE_ORDER` из `compile-topology.py`; импортировать canonical value из kernel.

### Entry Criteria

- Existing registry ordering behavior зафиксирован тестами до DRY-изменения.

### Exit Criteria

- Единственная точка определения `STAGE_ORDER` находится в `topology-tools/kernel/plugin_registry.py`.
- Order-sensitive behavior покрыто тестами.

### Validation

- `task test:plugin-api`
- `task test:plugin-contract`

### Suggested PR Split

- PR 7: execution order tests.
- PR 8: `STAGE_ORDER` import cleanup.

---

## Wave 3B: Standalone Compiler Module Coverage

### Covered Analysis Areas

- Area 11: Непокрытые standalone-модули

### Scope

1. Добавить unit-тесты для `compiler_runtime.py`.
2. Добавить unit-тесты для `compiler_plugin_context.py`.
3. Добавить focused tests для `compiler_contract.py`, если существующий contract test не покрывает unit-level behavior.
4. Оценить `identifier_policy.py` и `field_annotations.py` на наличие публичных pure functions, пригодных для быстрых unit-тестов.

### Entry Criteria

- Определены stable public functions/classes для тестирования без full compile.

### Exit Criteria

- Критичные standalone modules имеют собственные unit-тесты, а не только транзитивное integration покрытие.

### Validation

- Targeted pytest for added tests.
- `task test:plugin-api`
- `task test:plugin-contract`

### Suggested PR Split

- PR 9: `compiler_runtime.py` tests.
- PR 10: `compiler_plugin_context.py` and small pure-module tests.

---

## Wave 4: Diagnostics Compatibility

### Covered Analysis Areas

- Area 2: `Diagnostic` / `PluginDiagnostic` duplication

### Scope

1. Ввести shared diagnostic model or projection helper in kernel-compatible module.
2. Сохранить compatibility conversion for existing compiler diagnostics.
3. Добавить tests для serialization/projection fields used by compiler and plugins.
4. Удалять compiler-local dataclass только после подтверждения обратной совместимости.

### Entry Criteria

- Kernel and compiler tests from Waves 1-3 pass.
- Список полей, используемых diagnostics consumers, зафиксирован тестами.

### Exit Criteria

- Diagnostic data path имеет один canonical model or documented projection layer.
- Existing diagnostics JSON/schema output не ломается.

### Validation

- Targeted diagnostics tests.
- `task test:plugin-contract`
- `task test:plugin-integration`
- `task validate:default`

### Suggested PR Split

- PR 11: shared model/projection + tests.
- PR 12: remove compiler-local duplication if no compatibility risk remains.

---

## Wave 5: Observability And Orchestration UX

### Covered Analysis Areas

- Area 5: Structured Logging
- Area 9: Orchestration Error Propagation

### Scope

1. Replace AI-flow `print()` calls with stdlib `logging` while preserving user-facing output where required.
2. Route debug/trace to `stderr`; keep intentional CLI output on `stdout`.
3. Add timeout support in `scripts/orchestration/lane.py`.
4. Add optional collect-all-errors behavior for `validate-v5`.
5. Define structured exit-code mapping only after current callers are checked.

### Entry Criteria

- Existing runbook and task callers of `lane.py` identified.
- Output-sensitive tests or snapshots checked before logging changes.

### Exit Criteria

- AI session logs are filterable by severity.
- `validate-v5` can report multiple step failures when collect-all-errors mode is enabled.
- Default behavior remains compatible unless explicitly changed by flag/config.

### Validation

- Targeted lane/orchestration tests.
- Relevant AI session tests.
- `task validate:default`

### Suggested PR Split

- PR 13: logging migration for AI flow.
- PR 14: lane timeout + collect-all-errors.

---

## Wave 6: Low-Priority Hygiene

### Covered Analysis Areas

- Area 7: Empty plugin `config_schema`
- Area 8: Plugin family balance
- Area 10: AI agent docs duplication
- Area 12: `init-node.py` / `init_node.py` naming

### Scope

1. Add manifest validation warning or lint for empty `config_schema` where plugin config is actually consumed.
2. Audit plugin family placement:
   - discoverer classes in `discover_compiler.py`,
   - AI helper modules under `topology-tools/plugins/generators/`,
   - validator `when:` predicate coverage.
3. Keep agent-specific docs in bootloader format and avoid duplicating rulebook content.
4. Add a short comment to `scripts/orchestration/deploy/init-node.py` explaining wrapper vs implementation naming, or document why `__main__.py` is not used.
5. Resolve duplicate analysis artifact only after choosing canonical layout.

### Entry Criteria

- Critical and medium-risk waves are complete or explicitly deferred.

### Exit Criteria

- Hygiene changes do not alter runtime behavior.
- Documentation duplication is reduced without creating a new source of truth.

### Validation

- `task validate:agent-rules-strict` if agent docs are touched.
- `task validate:adr-consistency` if ADR artifacts are reorganized.
- Targeted tests for manifest linting if implemented.

### Suggested PR Split

- PR 15: manifest schema lint.
- PR 16: plugin family audit report only.
- PR 17: documentation/naming cleanup.

---

## Validation Matrix

| Change Type | Required Validation |
|---|---|
| ADR/plan-only update | `task validate:adr-consistency` |
| Agent docs/rules update | `task validate:agent-rules-strict` |
| Kernel API change | `task test:plugin-api`, `task test:plugin-contract` |
| Compiler orchestration change | targeted compiler tests, `task test:plugin-integration`, `task validate:default` |
| Plugin manifest/runtime contract change | `task validate:plugin-manifests`, `task test:plugin-contract` |
| AI sandbox/security change | targeted AI sandbox tests, `task test:plugin-contract` |
| Lane/orchestration change | targeted orchestration tests, `task validate:default` |

---

## Risk Controls

| Risk | Control |
|---|---|
| Regression after compiler decomposition | Split extraction into small PRs and preserve `compile-topology.py` entrypoint |
| Hidden CLI behavior change | Add baseline tests for parser/help and representative flags |
| Sandbox false positives | Keep minimal allowlist explicit and test safe env vars |
| Sandbox false negatives | Keep deny-pattern guard in addition to allowlist |
| Diagnostic output drift | Add projection/serialization tests before removing duplicate dataclass |
| Parallel execution flakiness | Use deterministic test fixtures and bounded timeouts |
| Documentation drift | Keep analysis as source and plan as execution artifact; do not copy rulebook content |

---

## Canonical Artifact Policy

- Canonical analysis source: `adr/analysis/IMPLEMENTATION-IMPROVEMENT-ANALYSIS.md`.
- Implementation plan: `adr/analysis/IMPLEMENTATION-IMPROVEMENT-PLAN.md`.
- Duplicate current copy: none.

The analysis and implementation plan currently live under `adr/analysis/`. Keep this layout until a separate decision chooses a different canonical location.
