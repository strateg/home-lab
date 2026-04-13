# Анализ имплементации проекта: Области для улучшения и усиления

**Дата:** 2026-04-10
**Статус:** Аналитический документ
**Автор:** AI-анализ на основе полного code review
**Охват:** topology-tools/, scripts/, tests/, schemas/, kernel/

---

## Резюме

Проект имеет зрелую архитектуру (88+ ADR, 70+ плагинов, 6-stage pipeline, ~120 интеграционных тестов). Однако идентифицированы 12 областей для улучшения — от критических (God Object в компиляторе, дефицит unit-тестов ядра) до среднеприоритетных (DRY нарушения, отсутствие structured logging).

---

## Область 1: God Object — V5Compiler (КРИТИЧЕСКАЯ)

### Проблема

`compile-topology.py` — **2091 строка**, один класс `V5Compiler` с **50 параметрами** в `__init__` (строки 204–299). Это классический антипаттерн God Object. Класс совмещает:

- CLI-парсер и `main()` (строки 1769–2091)
- Бизнес-логику компиляции (метод `run()`, строки 1401–1766)
- AI advisory сессии (строки 960–1100)
- AI assisted сессии (строки 1102–1380)
- Diagnostic management
- Plugin manifest discovery/loading
- Framework lock verification

### Рекомендации

| # | Действие | Приоритет | Сложность |
|---|----------|-----------|-----------|
| 1.1 | Выделить AI-домен в `compiler_ai_sessions.py` (~400 строк advisory + assisted) | 🔴 Высокий | Средняя |
| 1.2 | Выделить CLI-парсер в `compiler_cli.py` (функция `build_parser()` + `main()`, ~320 строк) | 🔴 Высокий | Низкая |
| 1.3 | Группировать AI-параметры в `@dataclass AiConfig` вместо 18 отдельных полей в `__init__` | 🟡 Средний | Низкая |
| 1.4 | Инкапсулировать plugin discovery/loading в отдельный `PluginLoader` компонент | 🟡 Средний | Средняя |

### Доказательство дублирования (AI Sessions)

`_run_ai_advisory_session` (строки 960–1100) и `_run_ai_assisted_session` (строки 1102–1380) имеют **~80% идентичного кода** на этапах:
- cleanup audit logs
- cleanup sandbox sessions
- create sandbox session
- sanitize environment
- create AiAuditLogger
- build_ai_input_payload
- validate_ai_contract_payloads

Этот общий код следует вынести в приватный метод `_prepare_ai_session()`.

---

## Область 2: Дублирование Diagnostic / PluginDiagnostic (ЗНАЧИМАЯ)

### Проблема

Существуют **два параллельных dataclass** для диагностики:

1. `Diagnostic` в `compile-topology.py` (строки 161–200) — 8 полей
2. `PluginDiagnostic` в `kernel/plugin_base.py` (строки 113–155) — 13 полей (надмножество)

Связь осуществляется через конвертер `Diagnostic.from_plugin_diagnostic()` (строка 188).

### Рекомендации

| # | Действие | Приоритет |
|---|----------|-----------|
| 2.1 | Унифицировать в одну `Diagnostic` dataclass в kernel, убрать compiler-local дублирование | 🟡 Средний |
| 2.2 | Если orchestrator нуждается в подмножестве полей, использовать projection view, а не отдельный класс | 🟡 Средний |

---

## Область 3: Дублирование STAGE_ORDER (НИЗКАЯ, но принципиальная)

### Проблема

`STAGE_ORDER` определена в **двух местах**:
- `topology-tools/kernel/plugin_registry.py:69` (каноническое определение)
- `topology-tools/compile-topology.py:87` (дублирование)

### Рекомендации

Импортировать `STAGE_ORDER` из kernel вместо дублирования. Единая точка определения — `plugin_registry.py`.

---

## Область 4: Дефицит unit-тестов ядра (КРИТИЧЕСКАЯ)

### Проблема

Kernel API (`plugin_base.py` — 845 строк, `plugin_registry.py` — 1880 строк = **2725 строк**) тестируется только через:
- `tests/plugin_api/test_dataclasses.py` — **1 файл**
- `tests/test_plugin_registry.py` — 1 файл верхнего уровня

При этом kernel реализует критичные функции:
- **Параллельное выполнение плагинов** (ThreadPoolExecutor + ContextVar) — без изолированных concurrent тестов
- **DAG зависимостей** (topological sort) — без тестов на edge cases (циклы, diamond dependencies)
- **Data exchange** (publish/subscribe через Lock + ContextVar) — thread safety не покрыта тестами
- **Timeout handling** — без stress-тестов

### Рекомендации

| # | Действие | Приоритет | Покрываемый риск |
|---|----------|-----------|-----------------|
| 4.1 | Добавить `tests/plugin_api/test_plugin_context.py` (publish/subscribe, scope, thread safety) | 🔴 Высокий | Data corruption в параллельном режиме |
| 4.2 | Добавить `tests/plugin_api/test_execution_order.py` (DAG resolution, cycle detection, phase ordering) | 🔴 Высокий | Неправильный порядок выполнения |
| 4.3 | Добавить `tests/plugin_api/test_parallel_execution.py` (concurrent plugin execution, timeout behavior) | 🔴 Высокий | Race conditions |
| 4.4 | Добавить `tests/plugin_api/test_plugin_spec.py` (from_dict, config_schema validation, model_version filtering) | 🟡 Средний | Malformed manifest parsing |
| 4.5 | Добавить `tests/plugin_api/test_context_aware_config.py` (scoped config overlay) | 🟡 Средний | Config injection errors |

### Метрика

Task `test:plugin-api` требует `--cov-fail-under=80`, но с 1 файлом тестов покрытие достигается только за счет транзитивных вызовов из `test_plugin_registry.py`. Прямое unit-покрытие критических путей ~30%.

---

## Область 5: Отсутствие Structured Logging (ЗНАЧИМАЯ)

### Проблема

Компилятор использует **`print()` с ручными тегами** для вывода:
```python
print(f"[ai-advisory] Cleaned {len(cleaned)} old audit day folders.", flush=True)
print(f"[ai-assisted] Sandbox session: {self._path_for_diag(sandbox_session)}", flush=True)
```

Обнаружено **20+ вызовов `print()`** только в AI-логике `compile-topology.py`. Ни один модуль в `topology-tools/` не использует `logging` stdlib.

### Последствия
- Невозможно фильтровать по уровню серьёзности
- Нет структурированного формата (JSON/JSONL) для машинного анализа
- Нет ротации, нет потоковой обработки
- Смешивание user-facing output с debug output

### Рекомендации

| # | Действие | Приоритет |
|---|----------|-----------|
| 5.1 | Ввести `logging.getLogger("topology-compiler")` с уровнями INFO/DEBUG/WARNING | 🟡 Средний |
| 5.2 | Использовать `logging.StreamHandler(sys.stderr)` для debug/trace, `sys.stdout` для user output | 🟡 Средний |
| 5.3 | AI sessions: JSON structured logging уже существует через `AiAuditLogger` — перенаправить все `print()` через него | 🟡 Средний |

---

## Область 6: Security — Env Sanitization (ЗНАЧИМАЯ)

### Проблема

`sanitize_environment()` в `ai_sandbox.py` (строки 105–116) фильтрует env vars по regex-паттернам:
```python
_ENV_SECRET_PATTERNS = (
    re.compile(r".*SECRET.*", re.IGNORECASE),
    re.compile(r".*TOKEN.*", re.IGNORECASE),
    re.compile(r".*PASSWORD.*", re.IGNORECASE),
    re.compile(r".*CREDENTIAL.*", re.IGNORECASE),
    re.compile(r"^SOPS_.*", re.IGNORECASE),
    re.compile(r"^AGE_.*", re.IGNORECASE),
)
```

Проблемы:
1. **Allowlist vs Blocklist**: Используется blocklist-подход — пропускается всё, что не содержит ключевые слова. Более безопасен allowlist.
2. **Отсутствуют паттерны**: `AWS_*`, `AZURE_*`, `GCP_*`, `GITHUB_*`, `CI_*`, `API_KEY`, `PRIVATE_KEY`, `SSH_*`, `TF_VAR_*`.
3. **Вызов `dict(os.environ)`** в `compile-topology.py:1126` передаёт полный env до фильтрации.

### Рекомендации

| # | Действие | Приоритет |
|---|----------|-----------|
| 6.1 | Перейти на allowlist: определить explicit набор безопасных переменных (PATH, HOME, LANG, TERM, etc.) | 🔴 Высокий |
| 6.2 | Добавить паттерны для cloud providers и CI: `AWS_*`, `AZURE_*`, `GH_*`, `CI_*`, `TF_VAR_*` | 🔴 Высокий |
| 6.3 | Добавить contract-тест, проверяющий что `sanitize_environment` не пропускает заведомо опасные ключи | 🟡 Средний |

---

## Область 7: Пустые plugin config_schema (НИЗКАЯ)

### Проблема

Манифест `plugins.yaml` (2116 строк) содержит config_schema для каждого плагина, но **большинство имеют пустую схему**:
```yaml
config_schema:
  type: object
  properties: {}
  required: []
```

Это означает, что runtime-конфигурация плагинов **не валидируется** через JSON Schema, несмотря на наличие инфраструктуры для этого в `PluginRegistry._validate_plugin_config()`.

### Рекомендации

| # | Действие | Приоритет |
|---|----------|-----------|
| 7.1 | Для плагинов, использующих `ctx.config[]`, добавить реальные schema constraints | 🟢 Низкий |
| 7.2 | Добавить lint-правило, предупреждающее о пустых `config_schema` в manifest validation тестах | 🟢 Низкий |

---

## Область 8: Дисбаланс Plugin Families (ИНФОРМАЦИОННАЯ)

### Статистика

| Семейство | Количество файлов |
|-----------|-------------------|
| validators | **50** |
| generators | **27** (включая 7 AI-модулей) |
| compilers | 8 |
| discoverers | 1 файл (4 класса) |
| assemblers | 2 |
| builders | 2 |

### Наблюдения

1. **50 validators** — это богатая валидация (network, storage, vm, docker, security, governance). Вопрос: все ли запускаются при каждом прогоне? Рекомендуется периодический аудит `when:` предикатов.

2. **4 discoverer-класса в 1 файле** (`discover_compiler.py`) — нарушение single-class-per-module. Рекомендуется разделить на 4 файла.

3. **7 AI-модулей в `generators/`** (`ai_advisory_contract.py`, `ai_ansible.py`, `ai_assisted.py`, `ai_audit.py`, `ai_promotion.py`, `ai_rollback.py`, `ai_sandbox.py`): Это helper/utility модули, не генераторы. Stage affinity сомнительна — они не создают артефакты в `generated/`. Следует оценить вынос в `topology-tools/ai/` или `topology-tools/utils/ai/`.

---

## Область 9: Orchestration — Error Propagation (ЗНАЧИМАЯ)

### Проблема

`lane.py` (строки 21–23) использует простейший паттерн `subprocess.run(check=True)`:
```python
def run(cmd: list[str]) -> None:
    print(f"[lane] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)
```

Последствия:
1. **Нет partial failure handling**: Если второй из 4-х шагов в `validate-v5` падает, оставшиеся 2 не выполняются и пользователь не видит полную картину ошибок.
2. **Нет retry logic**: Transient failures (filesystem, network) сразу фатальны.
3. **Нет timeout**: Зависший subprocess блокирует pipeline навсегда.
4. **Нет structured exit codes**: Только 0 (ok) и CalledProcessError.

### Рекомендации

| # | Действие | Приоритет |
|---|----------|-----------|
| 9.1 | Добавить `timeout=` параметр в `subprocess.run()` | 🟡 Средний |
| 9.2 | Для `validate-v5`: рассмотреть режим collect-all-errors (run all steps, report all failures) | 🟡 Средний |
| 9.3 | Добавить structured exit code mapping (0=ok, 1=validation-error, 2=warning, 3=infra-error) | 🟢 Низкий |

---

## Область 10: Дублирование AI Agent Documentation (НИЗКАЯ)

### Проблема

Три файла содержат ~70% идентичного контента:
- `AGENTS.md` (57 строк)
- `CLAUDE.md` (~230 строк)
- `.github/copilot-instructions.md` (~230 строк)

Все три дублируют: Plugin Contract, Directory Structure, Migration Lane Guard, Common Workflows, Network Architecture, Secrets Management.

`docs/ai/AGENT-RULEBOOK.md` (93 строки) задуман как единый источник правил, но AGENTS.md / CLAUDE.md / copilot-instructions.md всё ещё содержат inline копии.

### Рекомендации

| # | Действие | Приоритет |
|---|----------|-----------|
| 10.1 | Сделать `docs/ai/AGENT-RULEBOOK.md` единственным source of truth для правил | 🟢 Низкий |
| 10.2 | Сократить AGENTS.md / CLAUDE.md / copilot-instructions.md до bootloader-формата: ссылка на rulebook + tool-specific overrides | 🟢 Низкий |

---

## Область 11: Непокрытые standalone-модули (СРЕДНЯЯ)

### Проблема

Следующие модули в `topology-tools/` не имеют **собственных** unit-тестов (хотя могут быть транзитивно покрыты через интеграционные тесты):

| Модуль | Строк | Unit-тесты |
|--------|-------|------------|
| `compiler_runtime.py` | 810 | ❌ Нет |
| `compiler_plugin_context.py` | ? | ❌ Нет |
| `compiler_contract.py` | 71 | ❌ Нет (есть `test_compiled_model_contract.py` — contract test, не unit) |
| `compiler_ownership.py` | ? | ❌ Нет |
| `compiler_decisions.py` | ? | ❌ Нет |
| `identifier_policy.py` | ? | ❌ Нет |
| `field_annotations.py` | ? | ❌ Нет |
| `framework_lock.py` | ? | ✅ `test_framework_lock.py` |
| `yaml_loader.py` | 80 | ✅ `test_yaml_loader.py` |

### Рекомендации

Приоритизировать unit-тесты для `compiler_runtime.py` (810 строк, основная бизнес-логика компиляции) и `compiler_plugin_context.py` (создание PluginContext).

---

## Область 12: `init-node.py` / `init_node.py` — Naming Convention (НИЗКАЯ)

### Проблема

В `scripts/orchestration/deploy/`:
- `init-node.py` — CLI wrapper (18 строк), kebab-case
- `init_node.py` — реальная реализация (1315 строк), snake_case

Это **intentional**: kebab-case файл — CLI entry point для вызова `python scripts/.../init-node.py`, а snake_case — Python module для `from .init_node import main`.

Но для нового разработчика это выглядит как дубликат. Рекомендуется: добавить комментарий в `init-node.py` или использовать `__main__.py` паттерн вместо этого.

---

## Сводная таблица приоритетов

| # | Область | Приоритет | Усилие | Влияние |
|---|---------|-----------|--------|---------|
| 4 | Unit-тесты ядра (kernel API) | 🔴 Критический | Высокое | Предотвращение regression в parallel execution, DAG, data exchange |
| 1 | God Object V5Compiler | 🔴 Критический | Среднее | Maintainability, тестируемость, SRP |
| 6 | Security env sanitization | 🔴 Критический | Низкое | Утечка credentials в AI sandbox |
| 2 | Diagnostic duplication | 🟡 Средний | Низкое | DRY, единый diagnostic pipeline |
| 5 | Structured logging | 🟡 Средний | Среднее | Observability, debugging |
| 9 | Orchestration error handling | 🟡 Средний | Среднее | UX, reliability |
| 11 | Standalone module tests | 🟡 Средний | Среднее | Regression safety |
| 3 | STAGE_ORDER duplication | 🟢 Низкий | Минимальное | Code hygiene |
| 7 | Empty config_schema | 🟢 Низкий | Низкое | Schema-driven validation |
| 8 | Plugin family balance | 🟢 Низкий | Низкое | Architecture clarity |
| 10 | AI agent docs duplication | 🟢 Низкий | Низкое | Documentation maintenance |
| 12 | init-node naming | 🟢 Низкий | Минимальное | Onboarding clarity |

---

## Рекомендуемый порядок внедрения

### Wave 1 — Security & Reliability (1–2 дня)
- 6.1–6.2: Allowlist для env sanitization
- 4.1: `test_plugin_context.py` (thread safety)

### Wave 2 — Architecture Cleanup (3–5 дней)
- 1.1: Вынос AI sessions в `compiler_ai_sessions.py`
- 1.2: Вынос CLI parser в `compiler_cli.py`
- 1.3: `@dataclass AiConfig` для AI-параметров
- 2.1: Унификация Diagnostic

### Wave 3 — Test Coverage (3–5 дней)
- 4.2–4.5: Unit-тесты ядра
- 11: Unit-тесты для `compiler_runtime.py`, `compiler_plugin_context.py`

### Wave 4 — Observability & Polish (2–3 дня)
- 5.1–5.3: Structured logging
- 9.1–9.2: Orchestration timeouts и collect-all-errors
- 3: Import STAGE_ORDER from kernel
