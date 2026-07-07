# SWOT: генерация документации и диаграмм из топологии

**Status:** Completed (реализация выполнена, см. раздел «Результат»)
**Date:** 2026-07-07
**Scope:** подсистема docs/diagrams генерации (`base.generator.docs`, `base.generator.diagrams`, `base.generator.topology_graph`) и слой показа
**Process:** SPC MODE (`docs/ai/spc-contract.md`), STEP 3–4 артефакт
**Related:** ADR 0027, ADR 0079 (+ амендменты 2026-07-07), ADR 0080, ADR 0063

---

## 1. Диагностические факты (SPC STEP 3)

### Группа F1: Дрейф ADR ↔ реализация

| ID | Факт | Доказательство |
|---|---|---|
| F1.1 | ADR 0079 планирует config `template_sets` (селективная генерация docs-страниц); фактический config docs-генератора пуст (`config: {}`), 19 шаблонов захардкожены в кортеже кода | generators.yaml; docs_generator.py |
| F1.2 | ADR 0079 планирует плагин `base.validator_generated.mermaid` (validate-стадия); фактически валидация существует только как standalone-скрипт вне pipeline | grep по plugins/: 0 совпадений; utils/validate-mermaid-render.py |
| F1.3 | ADR 0027 декларирует icon-nodes режим по умолчанию; фактический default — `none` (манифест и сгенерированный артефакт) | generators.yaml; diagrams/index.md «Current render mode: `none`» |
| F1.4 | ADR 0027 References указывает на несуществующие v4-пути (`topology-tools/regenerate-all.py`, `topology-tools/scripts/generators/docs/`) | adr/0027 References |
| F1.5 | ADR 0079 планирует подкаталоги шаблонов (core/, network/, …); фактически структура плоская — 24 файла в одном каталоге | templates/docs/ |

### Группа F2: Отсутствующие звенья цепочки «показ»

| ID | Факт | Доказательство |
|---|---|---|
| F2.1 | Единственный формат вывода — Markdown с embedded Mermaid; рендеринг в SVG/PNG в pipeline отсутствует | отсутствие assembler/builder для docs |
| F2.2 | HTML-сайт/viewer (mkdocs, sphinx, docsify и т.п.) отсутствует; конфигов таких систем в репо нет | Explore-инвентаризация |
| F2.3 | CI не генерирует, не валидирует и не публикует docs; docs упоминаются только как lint-исключения | python-checks.yml; grep по 7 workflow |
| F2.4 | `mmdc`-рендер (E9802) — opt-in флаг standalone-скрипта; в task `build:docs-validate` вызывается без него (только regex-валидация) | validate-mermaid-render.py; taskfiles/build.yml |
| F2.5 | SVG-кэш иконок генерируется только в режиме icon-nodes; при дефолте `none` icon-cache не создаётся | diagram_generator.py |

### Группа F3: Ограничения текущей генерации диаграмм

| ID | Факт | Доказательство |
|---|---|---|
| F3.1 | Диаграммных страниц 5, из них тополого-графических 3 (physical, network, unified); все — Mermaid `graph`/`flowchart` | diagrams/ |
| F3.2 | topology_graph имеет 15 config-опций, но генерирует ровно один файл `unified-topology.md` с одной конфигурацией; механизм пресетов отсутствует | topology_graph_generator.py |
| F3.3 | Unified-граф: 125 узлов / 95 рёбер в одном Mermaid-блоке; файл 20K | unified-topology.md |
| F3.4 | icon-legend.md в режиме `none` печатает имена иконок с дубликатами строк | icon-legend.md |
| F3.5 | В network-topology VLAN-инвентаре большинство VLAN имеют `VLAN ID = None`, пустые CIDR/gateway | network-topology.md |
| F3.6 | Типы диаграмм ограничены graph/flowchart; sequence/state/C4/ER/mindmap-представления отсутствуют | шаблоны diagrams |
| F3.7 | Интерактивность (клик по узлу → страница, кросс-ссылки) в Mermaid-выводе отсутствует | сгенерированные артефакты |

### Группа F4: Состояние docs-генерации

| ID | Факт |
|---|---|
| F4.1 | 19 docs-страниц покрывают домены: network (7), operations (4), storage (2), services (2), физика (2), обзор (2); детерминизм закреплён тестом |
| F4.2 | Индекс/навигация есть только для diagrams; корневого `docs/index.md` нет |
| F4.3 | Per-instance страницы отсутствуют — только сводные таблицы |
| F4.4 | Тестовое покрытие подсистемы: 3 файла / 441 строка на ~2250 строк кода |

### Группа F5: Позитивные факты

| ID | Факт |
|---|---|
| F5.1 | Архитектура проекций стабильна и переиспользуема: topology_graph композитно строится из diagram+docs проекций |
| F5.2 | Config-schema topology_graph — самая богатая в подсистеме (15 опций) — инфраструктура параметризации уже существует |
| F5.3 | Icon-инфраструктура полная: 40 маппингов, discovery паков, SVG-кэш, fallback, 3 режима, env-override |
| F5.4 | Диагностическая дисциплина: коды E97xx/E98xx, contract produces, `_generated_files.txt` obsolete-учёт |
| F5.5 | 0 TODO в подсистеме; детерминизм + graceful degradation закреплены тестами |

### Группа F6: Масштаб

| ID | Факт |
|---|---|
| F6.1 | Модель: 6 devices, 7 zones, 7 VLANs, 27 services, 9 LXC, 2 VM, 15 external refs; граф 125n/95e |
| F6.2 | Совокупный вывод ~124K markdown; крупнейший файл unified-topology.md 20K |

---

## 2. Классификация проблем (SPC STEP 4.1)

| ID | Проблема | Факты | Класс | Тяжесть |
|---|---|---|---|---|
| P1 | Разрыв цепочки «показ»: генерация останавливается на markdown+Mermaid; нет рендеринга, сайта, публикации | F2.1–F2.3 | Capability gap | Высокая |
| P2 | Валидация Mermaid вне pipeline; mmdc-рендер фактически не вызывается | F1.2, F2.4 | ADR drift + quality gap | Средняя |
| P3 | Icon-политика не соответствует ADR 0027: default `none` вместо icon-nodes | F1.3, F2.5 | ADR drift | Средняя |
| P4 | Негибкая docs-генерация: 19 шаблонов захардкожены, `template_sets` не реализован | F1.1 | ADR drift + extensibility gap | Низкая-средняя |
| P5 | Один unified-граф на 125 узлов без пресетов; per-domain срезы не генерируются | F3.2, F3.3 | Capability gap | Средняя |
| P6 | Нет навигации и интерактивности: нет корневого индекса, кликабельных узлов, per-instance страниц | F4.2, F4.3, F3.7 | Capability gap (UX) | Средняя |
| P7 | Косметические дефекты: дубликаты в icon-legend, `VLAN ID = None` | F3.4, F3.5 | Quality defect | Низкая |
| P8 | Документационный долг ADR: stale-ссылки 0027, расхождение структуры шаблонов 0079 | F1.4, F1.5 | Doc debt | Низкая |
| P9 | Тестовое покрытие подсистемы тоньше среднего по репо | F4.4 | Quality gap | Низкая-средняя |

---

## 3. SWOT (SPC STEP 4.2)

### Strengths

| # | Сила | Основание |
|---|---|---|
| S1 | Projection-first архитектура: стабильные проекции переиспользуются композитно; новые представления не требуют трогать компилятор | F5.1 |
| S2 | Готовая инфраструктура параметризации: 15-опционная config-schema topology_graph — образец для расширения | F5.2 |
| S3 | Полная icon-подсистема: маппинги, discovery, SVG-кэш, fallback, 3 режима, env-override | F5.3 |
| S4 | Инженерная дисциплина: диагностик-диапазоны, contract produces, obsolete-учёт, детерминизм под тестом, graceful degradation | F5.4, F5.5 |
| S5 | Широкое доменное покрытие docs: 19 страниц по 6 доменам | F4.1 |
| S6 | Чистое состояние: 0 TODO, ADR подсистемы Implemented, рефакторинг контрактов завершён | F5.5 |

### Weaknesses

| # | Слабость | Проблема |
|---|---|---|
| W1 | Нет слоя показа: продукт — сырой markdown, потребляемый только через IDE/GitHub-рендерер | P1 |
| W2 | Mermaid-корректность не гарантирована: синтаксис-gate вне pipeline, реальный рендер не выполняется | P2 |
| W3 | Три задокументированных дрейфа ADR↔код (icon default, validator-плагин, template_sets) | P2–P4, P8 |
| W4 | Монолитный unified-граф без срезов — 125 узлов, читаемость на пределе | P5 |
| W5 | Отсутствие навигационной связности: нет индекса docs, кросс-ссылок, per-instance детализации | P6 |
| W6 | Косметические дефекты и тонкое тестовое покрытие проекций | P7, P9 |

### Opportunities

| # | Возможность | Опора |
|---|---|---|
| O1 | Пустые стадии assemble/build для docs-семейства: рендеринг и сборка сайта ложатся в существующую 6-стадийную модель | ADR 0080 |
| O2 | Богатая графовая проекция (15 node-типов, 11 edge-типов) позволяет генерировать тематические срезы из готовых данных | F6.1, S2 |
| O3 | Mermaid-экосистема поддерживает клик-навигацию (`click`), а mkdocs-material рендерит Mermaid из коробки | ADR 0027 |
| O4 | CI-каркас существует (7 workflow) — публикация docs добавляется без новой инфраструктуры | F2.3 |
| O5 | Snapshot-контракты упрощают добавление плагинов: чёткий publish-протокол, migrated-only | ADR 0093/0097 |
| O6 | Compiled model содержит больше данных, чем показывается (capabilities, security matrix, dependencies) — сырьё для новых диаграмм | F6.1 |

### Threats

| # | Угроза | Опора |
|---|---|---|
| T1 | Рост модели → нечитаемость unified-графа и таймауты Mermaid-рендереров; truncation молча режет картину | F3.3 |
| T2 | Невалидируемый Mermaid: регресс шаблона обнаруживается человеком, а не gate'ом | W2 |
| T3 | Дрейф ADR накапливается: новые участники/агенты принимают решения по ложным нормам | W3 |
| T4 | Внешние зависимости показа (mmdc/puppeteer, node_modules, mkdocs) — новые точки отказа CI | — |
| T5 | Расширение без пресетов/индексации умножит страницы и усугубит навигационный хаос | P5, P6 |
| T6 | Subinterpreter + timeout 30–60s ограничивают тяжёлый рендеринг внутри generate-стадии | ADR 0080 |

### Итоговая позиция (SO/WO/ST/WT)

- **SO**: сильные проекции (S1, S2) + пустые assemble/build (O1) → расширение естественно ложится в существующую архитектуру.
- **WO**: слабость показа (W1) закрывается зрелой внешней экосистемой (O3, O4).
- **ST**: дисциплина диагностик (S4) — готовый механизм против T2 при переносе валидатора в pipeline.
- **WT**: критическая связка W4+T1: без срезов/пресетов рост модели сломает читаемость раньше, чем появится слой показа.

---

## 4. Результат (пост-реализация, SPC STEP 6–7, 2026-07-07)

Реализован «рекомендуемый пакет»; трассировка слабостей к устранению:

| Слабость | Устранение | Артефакт |
|---|---|---|
| W1 (нет показа) | `base.assembler.docs_site` (assemble/run, 415) эмитит `mkdocs.yml` + nav; `task build:docs-site` / `build:docs-serve` | plugins/assemblers/docs_site_assembler.py |
| W2 (нет gate) | `base.assembler.mermaid_verify` (assemble/verify, 419): синтаксис-проверки всегда, mmdc opt-in (`use_mmdc`) | plugins/assemblers/mermaid_verify_assembler.py |
| W3 (дрейф ADR) | Амендменты ADR 0027 (default `none` узаконен) и ADR 0079 (validator→assembler, template_sets, новые возможности) | adr/0027, adr/0079 |
| W4 (монолитный граф) | `graph_presets` в topology_graph: N тематических `topology-<name>.md` из одного прогона | topology_graph_generator.py |
| W5 (нет навигации) | Корневой `docs/index.md`, Mermaid `click`-директивы (opt-out `enable_click_links`), mkdocs-nav | docs_generator.py, шаблоны diagrams |
| W6 (косметика/тесты) | Дедупликация icon-legend, маскирование None (`default('-', true)`); +19 тестов подсистемы | шаблоны, tests/plugin_integration |

Отложено по согласованию: SVG-прекомпиляция (mmdc, заготовка `use_mmdc`), per-instance страницы, GitHub Pages CI.

Гейты: full pytest 1661 passed, compile 0 errors, validate-v5 PASS, `task ci` exit 0.
