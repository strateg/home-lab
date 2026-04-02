# ADR 0086: Упрощение плагинной архитектуры без потери расширяемости проектов

- Status: Implemented (approval pending)
- Date: 2026-04-01
- Depends on: ADR 0063, 0065, 0066, 0074, 0080, 0081
- Supersedes: ADR 0063 Section 4B (4-level plugin boundary model)

## Context

Текущая реализация выросла до десятков плагинов и поддерживает 6 стадий жизненного цикла:
`discover -> compile -> validate -> generate -> assemble -> build`.

При этом возникли 4 системные проблемы.

### Problem 1: Runtime не обеспечивает level-boundaries

`PluginContext` передает одинаково широкий контекст всем плагинам:

```python
@dataclass
class PluginContext:
    raw_yaml: dict
    compiled_json: dict
    classes: dict
    objects: dict
```

В runtime нет ACL/скоупинга на уровень class/object/instance.
Границы 4-уровневой модели фактически остаются соглашением об именовании,
проверяемым тестами и ревью.

### Problem 2: Формальные boundary-правила противоречат OOP-семантике

В модели Class -> Object -> Instance:
- class задает контракт,
- object реализует вариации,
- instance является развернутым состоянием.

Проверка контракта class почти всегда требует анализа object/instance данных.
Запрет "class plugin не видит object" противоречит реальной задаче валидации.

### Problem 3: Избыточная гранулярность создает операционный overhead

Наблюдается высокая доля однотипных плагинов с минимальной уникальной логикой:
- дублирующиеся reference-validators,
- тонкие vendor-specific validators,
- повторение шаблона генераторов.

Каждый плагин добавляет стоимость: файл + manifest entry + DAG node + test support.

### Problem 4: Когнитивная нагрузка

Для разработки и сопровождения сейчас сложны:
- множественные каталоги и манифесты,
- плотная связка ID-нейминга с физическим расположением,
- дорогое перемещение плагина между уровнями,
- неявные правила, не гарантируемые runtime.

## Decision

### D1. Отказ от level-boundaries как runtime-policy

4-уровневая модель (global/class/object/instance) перестает быть правилом видимости
данных в runtime. Границы становятся **архитектурными** и **контрактными**:
- по stage/phase,
- по `depends_on`, `consumes`, `produces`, `when`,
- по тестам архитектурных ограничений.

Это прямо решает Problem 1 и Problem 2 без попытки внедрять ложный runtime ACL,
которого в текущем ядре нет.

### D2. Плоское размещение standalone-плагинов во framework

Все standalone-плагины (discoverers/compilers/validators/generators/assemblers/builders)
размещаются в `topology-tools/plugins/<family>/`.

Модульные `plugins.yaml` в class/object сохраняются только как переходный механизм
миграции и/или как extension points, но не как основное место для standalone-плагинов.

### D3. Сохранение discover chain и project extensibility (ADR 0081)

Сохраняется текущая детерминированная цепочка discovery:
1. framework base manifest,
2. class manifests,
3. object manifests,
4. project manifests (`project_plugins_root`).

`plugin_manifest_discovery.py` не упрощается до single-file режима.
Это обязательно для 1:N модели framework -> projects.

### D4. Консолидация однотипных validators (без изменений kernel API)

Консолидировать дублирующиеся reference-checks в один декларативный валидатор
(таблица правил), сохранив коды диагностик и совместимость отчетов.

Приоритет консолидации:
1. reference validators,
2. router ports validators,
3. остальные однотипные проверки по шаблону.

### D5. Генераторы: сначала shared-core, потом структурная консолидация

Для generator family сначала вводится shared-core и унификация projection/render-пайплайна
без новых полей schema/runtime.

Per-vendor generator plugins сохраняются на текущем этапе.
Полная host/strategy-модель выносится в отдельный ADR после внедрения:
- manifest schema support,
- runtime support,
- contract tests.

### D6. Нормализация plugin ID policy

Вводится единая policy:
- ID должны быть глобально уникальными,
- формат и стиль единообразны во всех manifests,
- запрет смешения разных namespace-pattern в одном домене.

Переименование выполняется по mapping-таблице с тестами совместимости.

### D7. Архитектурные тесты вместо legacy boundary-теста

Снять фокус с теста "кто что видит" и перейти к тестам:
- stage/phase affinity,
- корректность manifest discovery order,
- project plugin boundary (`project_plugins_root`),
- отсутствие запрещенных standalone plugin placements,
- детерминизм execution order и dependency rules.

### D8. Projection-first остается неизменным (ADR 0074)

Консолидация не меняет источник данных для генерации:
projection-first остается обязательным.

## Consequences

### Плюсы

1. Снижение когнитивной нагрузки: единый центр standalone-плагинов.
2. Уменьшение числа дублирующихся плагинов и boilerplate.
3. Устранение ложного конфликта между OOP и boundary-правилами.
4. Сохранение расширяемости проектов по ADR 0081.
5. Предсказуемая миграция без внедрения неподдерживаемых runtime-механизмов.

### Минусы / Trade-offs

1. Крупная миграция ID и manifests требует координации и regression gates.
2. Часть модульных manifests останется в переходный период.
3. Полная консолидация генераторов откладывается в отдельный шаг/ADR.

## Migration Plan (реализуемый по текущему коду)

### Wave 1: Contract and Policy (низкий риск)

1. Зафиксировать новую boundary-policy в документации и тестах.
2. Ввести единый ID lint/check для manifests.
3. Стабилизировать discovery chain regression-тесты (включая project slot).

### Wave 2: Validator Consolidation (средний риск)

1. Консолидировать reference validators в декларативный валидатор.
2. Консолидировать router port validators.
3. Сохранить диагностическую совместимость (коды, severity, paths).

### Wave 3: Plugin Layout Cleanup (средний риск)

1. Переместить remaining standalone-плагины в `topology-tools/plugins/<family>/`.
2. Свести module-level manifests к минимально необходимым extension points.
3. Обновить CI-гейты и архитектурные тесты.

## Acceptance Criteria

- Сохранен детерминированный discovery order framework/class/object/project.
- Project plugins продолжают автодискавериться через `project_plugins_root`.
- Сокращено количество дублирующихся validator plugins.
- Единая ID policy применена и проверяется CI.
- Все существующие regression tests проходят.
- Генерируемые артефакты не имеют непреднамеренных функциональных регрессий.

## References

- ADR 0063: Plugin Microkernel
- ADR 0065: Plugin API Contract
- ADR 0066: Plugin Testing and CI Strategy
- ADR 0074: Generator Architecture (projection-first)
- ADR 0080: Unified Build Pipeline
- ADR 0081: Framework Runtime Artifact and 1:N Project Model
- Analysis directory: `adr/0086-analysis/`
