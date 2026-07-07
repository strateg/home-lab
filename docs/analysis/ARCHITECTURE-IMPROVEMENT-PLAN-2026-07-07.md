# Architecture Improvement Plan

**Date:** 2026-07-07
**Status:** Proposed
**Supersedes:** `ARCHITECTURE-IMPROVEMENT-PLAN-2026-06-27.md`
**Sources:** repository inventory (Explore agent) + architectural review (tech-lead-architect agent), verified against code and commit history at `21d0d023`
**Analyst:** Claude Code (claude-fable-5)

---

## 1. Health Assessment

**A− по управляемости и дисциплине, C+ по стоимости обратной связи.**

Система в заметно лучшей форме, чем на обзоре 2026-06-27: три из четырёх «критических» фаз того плана выполнены (декомпозиция компилятора — коммиты `0357fe84`, `a56b922c`; шардирование манифестов — `340451cc`, `8866b05f`; capability-driven ADR 0106), проект переведён в `operational`, v4-миграция закрыта, framework 5.0.0 выпущен. Инженерная дисциплина образцовая: 110 ADR (72 Implemented / 37 Superseded / 1 Draft), 0 FIXME/XXX/HACK, 95 плагинов с манифест-контрактами (93 subinterpreter), 241 тест-файл.

Однако сложность мигрировала, а не исчезла: `kernel/plugin_registry.py` вырос в god-class на 2383 строки, совмещающий загрузку манифестов, схемную валидацию, планирование, параллельное исполнение и envelope-commit — при том что пакеты `kernel/registry/` и `kernel/scheduler/` уже созданы, но основную массу логики не приняли. Главная операционная боль — экономика тестов: полный прогон ~15 минут, 55 интеграционных тест-файлов независимо запускают полный компилятор subprocess'ом (~11 с каждый), `pytest-xdist` не установлен, coverage включён даже в точечные прогоны. Герметичность конвейера неполная: компилятор пишет `.state/` в рабочее дерево независимо от `--artifacts-root` и падает сырым `ValueError` при out-of-tree путях вывода — дыры в контракте для системы с 1:N project-моделью (ADR 0081).

Позитив, снимающий одну гипотезу: полный compile — **11 с** на полной модели (164 инстанса, 95+ плагинов). Компиляция не является узким местом DX; узкое место — тесты.

### Scale Snapshot (2026-07-07)

| Метрика | Значение |
|---|---|
| Python LOC (tracked) | ~104K (kernel 5.7K; validators 14.6K/49 шт.; tests 53.7K/241 файл) |
| Плагины | 95 (49 validators, 17 compilers, 10 generators, 8 assemblers, 7 builders, 4 discoverers) |
| ADR | 110 (72 Implemented, 37 Superseded, 1 Draft) |
| Модель | 56 классов, 15 object-модулей, 163 инстанса |
| Полный pytest | ~15 мин (1661 passed); полный compile ~11 с |
| CI | 7 workflow; ~150+ task-целей в 38 неймспейсах |

---

## 2. Findings Register

| ID | Находка | Ось | Доказательство | Риск |
|----|---------|-----|----------------|------|
| N1 | `kernel/plugin_registry.py` — god-class 2383 LOC: манифесты, схемы, планирование, параллельное исполнение, envelope-commit, версии модели в одном классе; `kernel/registry/` и `kernel/scheduler/` существуют, но пусты по ответственности | A, B | `plugin_registry.py`: `load_manifest`, `_execute_phase_parallel` (:1308), `execute_stage` (:1885), `_validate_model_versions` (:2211) | High |
| N2 | 55 тест-файлов вызывают полный компилятор subprocess'ом; в `tests/plugin_integration/` (127 файлов) нет conftest с session-scoped компиляцией — паттерн есть только в `tests/plugin_regression/conftest.py:30` | C | `grep -rln "compile-topology.py" tests \| wc -l` → 55 | High |
| N3 | `pytest-xdist` отсутствует; `addopts` в `pyproject.toml` всегда включает coverage, замедляя даже точечные прогоны | C | `pyproject.toml:53-55`; import xdist → ModuleNotFoundError | High |
| N4 | In-process `PipelineTestHarness` (ADR 0099) используется ровно одним тест-файлом — инвестиция не окупается | C, B | `grep -rln PipelineTestHarness tests \| wc -l` → 1 | Med |
| N5 | Компилятор пишет `.state/artifact-plans/*.json` в рабочее дерево даже при внешнем `--artifacts-root` — скрытый side-effect вне объявленного artifact-root, ломает герметичность и изоляцию тестов | A, E | Запуск с `--artifacts-root /tmp/...` → `git status`: `M .state/artifact-plans/*.json` | High |
| N6 | Сырое падение `ValueError` (не диагностика) при `--output-json` вне repo root, в конце ~11-секундного прогона | D, E | `topology-tools/compiler_runtime.py:853`: `output_json.relative_to(repo_root)` без fallback | Med |
| N7 | Шесть refs-валидаторов (`lxc_refs`, `vm_refs`, `docker_refs`, `host_os_refs`, `service_runtime_refs`, `storage_l3_refs`; 412–744 LOC каждый) дублируют `_ARCH_ALIASES`, `_ACTIVE_OS_STATUSES`, subscribe-boilerplate и разрешение ссылок | B | `lxc_refs_validator.py:23-36` ≡ `vm_refs_validator.py:22-35` | Med |
| N8 | `manifests/validators.yaml` — 1299 строк, 41% объёма манифестов: внутри шарда зреет новый монолит | B, A | `wc -l topology-tools/plugins/manifests/*.yaml` | Low |
| N9 | `compile-topology.py` 1264 LOC; `V5Compiler` совмещает bootstrap, загрузку манифестов, оркестрацию и запись диагностик — цель «тонкий оркестратор» плана 2026-06-27 достигнута частично (модули `compiler_*.py` извлечены) | B | `compile-topology.py`: `_bootstrap_phase` (:921), `run` (:1039) | Med |
| N10 | `class_layers` в `topology/layer-contract.yaml:46` ведётся вручную — риск рассинхронизации с `@layer` class-модулей; прецедент был (коммит `c53b481c`) | B, E | `topology/layer-contract.yaml:46`; генератора нет | Med |
| N11 | CI гоняет полный suite с coverage на каждый push/PR без тиринга smoke/full — 15-минутная боль реплицирована в CI | C, E | `.github/workflows/python-checks.yml:99` → `task test:ci-coverage` | Med |
| N12 | Слой показа docs не проверяется в CI: ни один workflow не собирает mkdocs-сайт; `use_mmdc: false` — mmdc-рендер никогда не исполняется | E, F | `taskfiles/build.yml:60-70`; `manifests/assemblers.yaml` | Med |
| N13 | Отложенные пункты docs-пакета подтверждены: `graph_presets: []` (дефолт пуст), per-instance страниц нет, Pages CI нет | F | `manifests/generators.yaml:171`; SWOT 2026-07-07 §4 | Low |
| N14 | ADR-хвост: 0105 Draft, 0108 Proposed, 0103 Partially Implemented; superseded ADR не архивированы (137 файлов в `adr/`, в `adr/archive/` — 2) | F | `adr/REGISTER.md:107-112` | Med |
| N15 | Coverage-пороги рассинхронизированы: 75% (`ci:coverage-gate`, pyproject), 80% (`test:plugin-api`), 70% (`test:plugin-contract`) | C, D | `taskfiles/ci.yml:73`; `taskfiles/test.yml:17,22` | Low |
| N16 | `base.assembler.mermaid_verify` выполняет валидацию в assemble-стадии — осознанное отклонение, узаконено амендментом ADR 0079; зафиксировать как разрешённый паттерн «verify-phase внутри стадии», чтобы не размывать stage affinity прецедентами | A | `plugins/assemblers/mermaid_verify_assembler.py`; ADR 0079 Amendment A1 | Low |
| N17 | Позитив: цикл edit→compile ~11 с на полной модели — компиляция не узкое место DX | D | замер `time ... compile-topology.py` → real 11.0s | — |

Оси: A — архитектурная целостность, B — технический долг, C — тестовая стратегия, D — DX/операбельность, E — надёжность пайплайна, F — незавершённые линии.

---

## 3. Improvement Plan

### H1 — быстрые победы

| # | Что делать | Закрывает | Критерий готовности | ADR |
|---|-----------|-----------|---------------------|-----|
| H1.1 | Добавить `pytest-xdist`; перевести `test:plugin-integration` и `test:default` на `-n auto`; убрать coverage из дефолтных `addopts` (coverage — только в `ci-coverage`/`coverage-gate`) | N3, N11 | `task test:default` кратно быстрее 15 мин; точечный тест-файл стартует без coverage-оверхеда | Амендмент ADR 0066 при изменении CI-контракта |
| H1.2 | Session-scoped фикстура «скомпилированные артефакты» в `tests/plugin_integration/conftest.py` по образцу `plugin_regression/conftest.py:30`; мигрировать читающие-only тесты из 55 subprocess-файлов | N2 | Число независимых subprocess-компиляций сокращено измеримо (grep-метрика); plugin_integration ускорен | не требуется |
| H1.3 | Починить `compiler_runtime.py:853`: fallback к абсолютному пути вместо голого `relative_to` + ранняя валидация CLI-путей до запуска стадий (диагностика вместо traceback) | N6 | Компиляция с `--output-json /tmp/...` завершается успешно или падает мгновенно с E-кодом | не требуется |
| H1.4 | Законтрактовать `.state/`: перенаправлять под `--artifacts-root`/новый `--state-root`, либо задокументировать как mutable-корень и исключить запись при чужом artifacts-root | N5 | Компиляция во внешний artifacts-root оставляет `git status` чистым | Амендмент ADR 0093 |
| H1.5 | ADR-гигиена: решить судьбу 0105 (Draft) и 0108 (Proposed) — принять план или Rejected/Deferred; зафиксировать финал 0103; архивировать superseded ADR (перенос P4.2) | N14 | В REGISTER.md нет Draft/Proposed без owner-решения; superseded в `adr/archive/` | правки статусов + REGISTER.md |
| H1.6 | Единый канонический coverage-порог в `pyproject.toml`; task-специфичные — только выше, с комментарием-обоснованием | N15 | Все `--cov-fail-under` трассируются к одному правилу | не требуется |

### H2 — структурные

| # | Что делать | Закрывает | Критерий готовности | ADR |
|---|-----------|-----------|---------------------|-----|
| H2.1 | Декомпозиция `kernel/plugin_registry.py`: исполнение/commit (`_execute_phase_parallel`, `execute_plugin`, `execute_stage`, `_commit_envelope_result`) → `kernel/scheduler/`; загрузка/валидация манифестов и схем → `kernel/registry/`; `PluginRegistry` остаётся фасадом | N1 | `plugin_registry.py` — фасад; ни один kernel-модуль не превышает согласованный лимит; `test:plugin-api`/`plugin-contract` зелёные без изменения публичного API | Амендмент ADR 0063 + 0097 |
| H2.2 | Общая библиотека refs-валидации (subscribe к `normalized_rows`, `_ARCH_ALIASES`, OS-статусы, разрешение ссылок); переписать 6 refs-валидаторов; кандидат — слияние с `declarative_reference_validator` | N7 | `_ARCH_ALIASES` = 1 определение; LOC refs-валидаторов сокращён; диагностик-коды не изменены | Амендмент ADR 0065 |
| H2.3 | Тиринг тестов и CI: маркеры `smoke`/`full`/`subprocess_compile`; PR-гейт = smoke + targeted + lint/typecheck; полный suite с coverage — merge в main и nightly | N11, N2 | PR-пайплайн в целевом бюджете; nightly/main сохраняет полный охват; правило в testing-ci rule pack | Амендмент ADR 0066 |
| H2.4 | Массовая миграция интеграционных тестов на `PipelineTestHarness` (in-process) там, где не тестируется сам CLI; subprocess — только помеченным CLI-контрактным тестам | N4, N2 | Harness — доминирующий паттерн в plugin_integration | реализация ADR 0099 |
| H2.5 | Генерация `class_layers` из `@layer`-метаданных class-модулей + validate-плагин на рассинхронизацию (перенос P4.3) | N10 | Секция генерируется или валидируется автоматически; ручной дрейф ловится гейтом | малый ADR или амендмент ADR 0101 |
| H2.6 | CI-job сборки docs-сайта: `mkdocs build --strict` на PR, затрагивающие docs/diagrams-подсистему | N12 | Регресс шаблонов/nav ловится в CI | в рамках ADR 0079 |

### H3 — стратегические

| # | Что делать | Закрывает | Критерий готовности | ADR |
|---|-----------|-----------|---------------------|-----|
| H3.1 | Завершить слой показа: SVG-прекомпиляция через `use_mmdc` в assemble (пиннинг node/mmdc, graceful degradation), per-instance страницы, GitHub Pages publish workflow | N12, N13 | Сайт публикуется автоматически; mermaid-рендер проверяется реальным рендерером хотя бы в nightly | отложенный пакет ADR 0027/0079 |
| H3.2 | Инкрементальная компиляция: существующий `changed_input_scopes` (`plugin_registry.py:567`) + manifest consumes/produces для пропуска незатронутых плагинов; фундамент кэширования compile-фикстур в тестах | N17 (рост), N2 | Повторная компиляция без изменений — доли секунды; parity-тест full vs incremental | новый ADR (incremental execution contract) |
| H3.3 | Scalability-регрессия: синтетическая модель ×5–10 как fixture-профиль; nightly-гейты на время стадий, размер unified-графа, subinterpreter-таймауты | SWOT T1/T6 | Nightly-джоб с порогами; деградация ловится до боли | расширение ADR 0066/0070 |
| H3.4 | Политика размера манифест-шардов: вторичное шардирование `validators.yaml` по доменам (network/storage/compute) с сохранением includes-механизма | N8 | Ни один шард не превышает лимит; `validate:plugin-manifests` зелёный | Амендмент ADR 0082 |

### Зависимости

- H1.1, H1.2 → H2.3 (тиринг опирается на ускоренную базу);
- H2.1 желателен до H3.2 (инкрементальность трогает scheduler);
- H2.4 опирается на H1.2 (общая compile-фикстура).

---

## 4. Disposition of the 2026-06-27 Plan

**Закрыто как выполненное** (проверено по коду/коммитам):

| Пункт | Доказательство |
|---|---|
| Phase 1 (декомпозиция компилятора) | коммиты `0357fe84`, `a56b922c`; модули `compiler_runtime.py`, `compiler_ai_sessions.py`, `compiler_framework_lock.py`, `compiler_diagnostics.py` извлечены |
| Phase 2 (шардирование plugins.yaml) | `plugins.yaml` 47 строк + `manifests/` из 6 файлов; коммиты `340451cc`, `8866b05f` |
| Phase 3 (capability-driven, ADR 0106) | Implemented в регистре; вендор-хардкод по `topology-tools/` отсутствует |
| P4.1 (status → operational) | `projects/home-lab/project.yaml`: `status: operational`, `migration_completed: 2026-06-29` |
| P4.6 (DAG-валидация) | `host_ref_dag_validator.py`; cycle-проверки в `declarative_reference_validator.py`, `kernel/registry/dependency_resolver.py` |

**Списано как устаревшее:**

- Метрика «compile-topology.py < 200 LOC» — заменена качественным критерием «оркестрация без доменной логики» (остаточная зачистка — по желанию, не гейт; см. N9).
- P4.5 (параметризованный LXC-шаблон) — won't-do: ADR 0068 закрыл исходную боль, 13 явных lxc-файлов — приемлемая цена явности.

**Перенесено в настоящий план:** P4.2 → H1.5; P4.3 → H2.5; P4.7 → H1.5; P4.4 (capability lifecycle policy) — остаётся открытым, низкий приоритет.

---

## 5. Top-3 Risks of Inaction

1. **Деградация цикла обратной связи тестов (N2+N3+N11).** Каждый новый интеграционный тест по текущему паттерну добавляет полную subprocess-компиляцию (~11 с) — время растёт линейно с покрытием. Итог: эрозия дисциплины CORE-008 либо рост стоимости CI; регрессии доезжают до main.
2. **Концентрация риска в `kernel/plugin_registry.py` (N1).** Любая эволюция runtime проходит через один 2383-строчный класс без внутренних границ — максимальная вероятность регрессии там, где максимальная цена ошибки; блокирует H3.2.
3. **Эрозия герметичности (N5+N6+N10).** Скрытые `.state/`-записи и repo-relative допущения незаметны при исполнении из корня одного репозитория, но 1:N модель (ADR 0081), extracted-framework и CI-матрицы наступят на них с трудноотлаживаемыми отказами; ручной `class_layers` добавляет тихий дрейф модели (прецедент `c53b481c`).

---

## Related

- `ARCHITECTURE-ANALYSIS-2026-06-27.md` — предыдущий обзор (базис Phase 1–4)
- `ARCHITECTURE-IMPROVEMENT-PLAN-2026-06-27.md` — предыдущий план (superseded настоящим документом)
- `DOCS-DIAGRAMS-GENERATION-SWOT-2026-07-07.md` — SWOT docs/diagrams-подсистемы
- `adr/REGISTER.md`, `docs/ai/AGENT-RULEBOOK.md`
