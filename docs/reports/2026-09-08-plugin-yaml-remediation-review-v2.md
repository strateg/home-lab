# Повторное ревью после исправлений — рапорт v2

**Дата:** 2026-09-08.  
**Репозиторий:** /home/nixos/workspaces/home-lab, WSL NixOS, не Windows-копия на D:.  
**Проверенный HEAD:** bd7dfbce19b4652c8c52e9151484cdc6a12a7b3f.  
**Рабочее дерево:** tracked-изменений нет; до ревью присутствовали untracked Markdown-рапорты. HEAD и отсутствие tracked-изменений повторно проверены после тестов.  
**Изменения агента:** только этот рапорт. Исходники, fixtures, manifests, lock и generated вручную не менялись.

Этот документ **заменяет предыдущий remediation review в части оценки текущего состояния**. Старый [docs/reports/2026-09-08-plugin-yaml-remediation-review.md](/home/nixos/workspaces/home-lab/docs/reports/2026-09-08-plugin-yaml-remediation-review.md) сохранён как исторический результат на прежнем коде; его открытые замечания нельзя автоматически переносить на текущий HEAD.

## 1. Итог

**Большая часть конкретных дефектов исправлена и повторно подтверждена. Полного закрытия пока нет: остаются несовместимость lane с новым diagnostics-контрактом и незавершённая миграция тестов.**

- SOHO missing/empty profile теперь различаются корректно.
- Финализатор больше не требует effective JSON, если output явно disabled.
- Неверный тип validated_rows теперь сопровождается fallback-диагностикой.
- I7950–I7953 зарегистрированы в error catalog.
- SOHO и CLI output tests восстановлены.
- Placeholder validator переведён на compiler publication вместо повторного чтения YAML.
- **Штатный compile/validate: PASS, 0 errors, 21 warnings, 79 infos.**
- **Расширенный целевой набор: 159 passed, 16 failed, 142.86 s.**
  - 14 падений: placeholder fixtures не создают новое обязательное publication;
  - 2 падения: прежние MikroTik snapshot/full-topology tests.

Расширенный набор содержит **175 тестов**, прежний — 147. Поэтому сами числа падений не означают ухудшение по всему проекту: проверка расширена на дополнительно изменённый validator.

## 2. Какие новые изменения проверены

После 8519fb22 появились:
- a27132d9 — fallback visibility diagnostics;
- 99514986 — annotation_formats subscription в placeholder validator;
- 878be494 — общий helper разрешения policy paths/date;
- 472aef7d — исправления F01–F05 предыдущего рапорта;
- bd7dfbce — актуализация compiler output tests.

Прочитаны актуальные diff и реализации. Применены ранее загруженные AI rulebook, ADR rule map, scoped plugin-runtime/generator/testing/secrets rules и Codex overlay. Изменения архитектуры в рамках этого ревью не выполнялись.

## 3. Повторная проверка прежних замечаний

| Прежнее замечание | Текущий статус | Новое доказательство |
|---|---|---|
| F01: finalizer требует disabled effective JSON | **Исправлено** | Реальная связка ownership → effective generator → finalizer возвращает I9001 с явным disabled и на чистом, и на старом output |
| F01: lane/deploy callers не включают diagnostics | **Осталось** | В сформированной lane compiler command нет --diagnostics; governance следующим шагом требует report.json |
| F02: отсутствующий SOHO profile превращается в schema error | **Исправлено** | Реальный compiler→validator: missing → W7941; заданный {} → E7941 |
| F03: wrong-type fallback не диагностируется | **Исправлено для проверенного сценария**, аналогичные ветки добавлены в других compilers | validated_rows={} → I7953 с wrong type; отсутствующий payload → publication unavailable; [] не вызывает fallback |
| F03: recursive legacy fallback как архитектурная зависимость | **Сохранён намеренно, не устранён** | Общая recursive chain осталась; улучшена наблюдаемость, не разделение входов |
| F04: SOHO fixtures и CLI tests устарели | **Исправлено** | Соответствующие файлы входят в зелёную часть повторного запуска |
| F04: MikroTik fixtures/golden | **Не исправлено** | Два прежних теста снова падают |
| F05: I7950–I7953 нет в каталоге | **Исправлено** | Defined codes 168→172; undefined 280→276 |

### 3.1. Disabled artifact: прежняя ошибка действительно закрыта

[topology-tools/compiler_runtime.py:839](/home/nixos/workspaces/home-lab/topology-tools/compiler_runtime.py#L839) теперь отдельно обрабатывает effective_json_owner == "disabled".

Повторно вызваны реальные artifact_owner, EffectiveJsonGenerator и emit_effective_artifact с временным output:

| Начальное состояние | Результат |
|---|---|
| Файла нет | I9001: Compile success (effective JSON artifact disabled); ошибки нет, файл не создаётся |
| Существует старый синтетический JSON | То же явное disabled-сообщение; файл не обновляется |

Старый файл теперь не используется как условие успешности disabled-ветки. **Прежнее утверждение о E3001 на чистом output больше не актуально.** Необновление файла само по себе ожидаемо при намеренно disabled output; несовместимость остаётся у consumers, которым нужен свежий файл.

### 3.2. SOHO: missing и empty больше не смешиваются

[topology-tools/plugins/validators/soho_product_profile_validator.py:93](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/soho_product_profile_validator.py#L93) использует resolution.profile_present.

Проверены реальные compiler publications, без ручной подмены exchange payload:

| Синтетический project manifest | Compiler | Validator |
|---|---|---|
| {"project":"audit"} | SUCCESS, profile_present=false | PARTIAL, W7941 |
| {"project":"audit","product_profile":{}} | SUCCESS, profile_present=true | FAILED, E7941 |

Policy отсутствовала, sunset не включён. PARTIAL для missing — ожидаемый статус результата с предупреждением, а не новое падение. Логика отсутствующего профиля восстановлена, невалидный заданный профиль не маскируется.

### 3.3. Fallback: наблюдаемость улучшена, повторная обработка сохранена

Для base.compiler.instance_rows повторён probe с заменой _build_validated_rows счётчиком:

| validated_rows | Вызовы fallback | Диагностика |
|---|---:|---|
| Публикации нет | 1 | I7953, publication unavailable |
| {} | 1 | I7953, wrong type (expected list) |
| [] | 0 | нет |

Это закрывает прежнее конкретное замечание о молчаливом wrong-type переходе. В resolve/prepare добавлены аналогичные ветки; validate возвращает fallback reason.

Но цепочка _build_validated_rows → _build_prepared_rows → _build_resolved_rows → _build_secret_resolved_rows осталась. Поэтому нельзя объявлять все четыре compiler IDs полностью освобождёнными от YAML-зависимости. При корректных required publications штатного snapshot pipeline fallback не используется.

Это **остаточный архитектурный долг/compatibility choice**, не повторное предъявление уже исправленного дефекта логирования. Если цель — полностью запретить повторную сборку при нарушении required exchange, нужен отдельный explicit legacy contract либо fail-fast.

## 4. Оставшиеся actionable findings

### R01 — P1: lane не создаёт diagnostics, обязательные для следующего шага

**Места:**
- [scripts/orchestration/lane.py:100](/home/nixos/workspaces/home-lab/scripts/orchestration/lane.py#L100);
- [scripts/orchestration/lane.py:115](/home/nixos/workspaces/home-lab/scripts/orchestration/lane.py#L115);
- [scripts/validation/validate_adr0088_governance.py:174](/home/nixos/workspaces/home-lab/scripts/validation/validate_adr0088_governance.py#L174).

Фактически сформированная _validate_v5_commands("passthrough") команда compiler:

```text
/home/nixos/workspaces/home-lab/.venv/bin/python
topology-tools/compile-topology.py
--topology topology/topology.yaml
--strict-model-lock
--secrets-mode passthrough
```

В ней **нет --diagnostics**. Следующая команда передаёт governance-validator путь build/diagnostics/report.json. Новый compiler default этот report не записывает.

Независимо вызван реальный _evaluate_warning_governance с временным diagnostics path:
- отсутствующий файл → **P2002, diagnostics report not found**;
- старый синтетический {"diagnostics": []} → ошибок нет при минимальной policy.

Последний probe использует минимальную policy, а не production policy; он доказывает отсутствие проверки свежести входного отчёта, **не** прохождение всей production governance на произвольном stale JSON.

Исправление disabled finalizer не решает эту зависимость. На чистом workspace lane дойдёт до отсутствующего diagnostics input; на загрязнённом может анализировать не тот запуск.

Дополнительно [scripts/orchestration/deploy/workspace.py:124](/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/workspace.py#L124) задаёт --output-json/--diagnostics-json/--diagnostics-txt, но тоже не включает новый --diagnostics. В этом ревью deploy не запускался: это замечание по согласованности command builder, а не сообщение о проверенном production incident.

**Что исправить:** включить диагностическую выгрузку там, где downstream её требует, либо перевести downstream на новый явно переданный результат. Добавить lane contract test на наличие/актуальность diagnostics. Полезно связать отчёт с текущим run ID/input digest, а не полагаться только на exists().

### R02 — P2: 14 placeholder tests не подготовлены к required annotation_formats

**Места:**
- [tests/plugin_integration/test_instance_placeholder_plugin.py:28](/home/nixos/workspaces/home-lab/tests/plugin_integration/test_instance_placeholder_plugin.py#L28);
- [tests/plugin_integration/test_instance_placeholder_plugin.py:77](/home/nixos/workspaces/home-lab/tests/plugin_integration/test_instance_placeholder_plugin.py#L77);
- [topology-tools/plugins/manifests/validators.yaml:955](/home/nixos/workspaces/home-lab/topology-tools/plugins/manifests/validators.yaml#L955);
- [topology-tools/plugins/validators/instance_placeholder_validator.py:92](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/instance_placeholder_validator.py#L92).

Новый dependency/consumes contract правильный, однако тесты продолжают запускать validator отдельно, без annotation_resolver и без его публикации.

Непосредственный результат реального registry.execute_plugin:
```text
E8003:
Plugin 'base.validator.instance_placeholders' requires payload
'base.compiler.annotation_resolver.annotation_formats',
but it is not available in published data.
```

Эта ошибка возникает до предметных проверок, поэтому тесты не получают ожидаемые E6801/E6802/E6803/E6805/E6806/E6807.

**Первопричина проверена двумя способами:**
1. Реальный annotation compiler перед validator: SUCCESS → SUCCESS для валидного синтетического input.
2. В отдельном эксперименте к registry.execute_plugin временно добавлен bootstrap annotation compiler только в памяти; исходники тестов не редактировались. Все **14 placeholder tests прошли, 20.13 s**.

Экспериментальные 14 passed **не заменяют** официальный результат рабочего дерева 159 passed / 16 failed. Они показывают, что нужно исправить fixture/bootstrap, а не возвращать YAML-чтение в validator.

**Что исправить:** обновить test setup под producer→consumer contract или публиковать validated annotation_formats fixture; добавить manifest assertion на новый required consume и отдельный тест отсутствующей публикации.

### R03 — P2 / прежний долг: два MikroTik contract tests остаются красными

- [tests/plugin_integration/test_projection_snapshots.py:66](/home/nixos/workspaces/home-lab/tests/plugin_integration/test_projection_snapshots.py#L66);
- [tests/plugin_integration/test_terraform_mikrotik_generator.py:476](/home/nixos/workspaces/home-lab/tests/plugin_integration/test_terraform_mikrotik_generator.py#L476).

Повторно подтверждены:
- несовпадение MikroTik projection с golden snapshot;
- full-topology fixture не даёт ожидаемый guest VLAN.

Эти файлы и соответствующий generator/projection не изменялись в новой серии исправлений. В предыдущем ревью отдельно установлено: snapshot mismatch существовал и со старым projection; full-topology test также был красным до удаления YAML reads, но точка падения изменилась.

**Что исправить:** сделать full-topology fixture самостоятельным effective model с objects/defaults/instance overrides; пересмотреть golden по утверждённому контракту. Не обновлять snapshot автоматически без проверки содержимого и не возвращать disk fallback ради теста.

## 5. Оценка нового рефакторинга validators

### Placeholder format registry

Перевод на annotation_formats — правильная консолидация: форматный registry разбирается compiler, validator использует его publication. depends_on и required consumes объявлены. Compiler уже фильтрует registry до mapping format-name → mapping specification, поэтому удаление повторной такой фильтрации в validator согласовано с producer contract.

Текущий production compile/validate с новым exchange проходит. Ошибка R02 относится к тестовой подготовке, а не к доказанной поломке штатного pipeline.

### Shared policy helper

[topology-tools/plugins/validators/policy_path_helper.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/policy_path_helper.py) устраняет дублирование path/date helpers у sunset и rollback validators. Порядок выбора остался прежним: absolute path → repo-relative существующий путь → framework-relative → исходный repo candidate. UTC parsing также сохранён.

В расширенном запуске tests для generator_sunset и generator_rollback_escalation прошли. Нового дефекта в этой ограниченной области не обнаружено.

Это **рефакторинг общей реализации, а не устранение policy YAML reads**: load_yaml_file по-прежнему вызывается внутри обоих validators. Так и следует описывать результат.

## 6. Актуальная YAML-инвентаризация

Повторный AST scan:
- **219** tracked active Python files;
- **141** Python files в plugin-каталогах;
- **12** plugin Python files содержат прямой parser/helper call, включая load_yaml_text.

В manifests по-прежнему **105 plugin IDs**. С учётом ранее разобранных inherited/helper/callback paths:
- было 19 потенциальных YAML-reading IDs в исходном аудите;
- стало 18 после первого исправления;
- сейчас **17**: instance_placeholders больше не читает YAML.
- у **88** IDs в проверенных путях YAML parsing не найден. Это не доказательство использования исключительно ctx.compiled_json: допустимы отдельные intermediate publications.

| Остаточная категория | IDs |
|---|---:|
| Generator object topology YAML | **0** |
| WireGuard SOPS YAML | 1 |
| Source/layout validators | 2 |
| Policy validators: SOHO, sunset, rollback | 3 |
| Compile input loaders | 6 |
| Conditional compiler fallback | 4 |
| Discover manifest callback | 1 |
| Всего с потенциальным YAML-путём | **17** |

Оставшиеся IDs:
- base.generator.wireguard;
- base.validator.foundation_file_placement;
- base.validator.foundation_include_contract;
- base.validator.soho_product_profile;
- base.validator.generator_sunset;
- base.validator.generator_rollback_escalation;
- base.compiler.module_loader;
- base.compiler.model_lock_loader;
- base.compiler.annotation_resolver;
- base.compiler.capability_contract_loader;
- base.compiler.soho_profile_resolver;
- base.compiler.instance_rows_secret_resolve;
- base.compiler.instance_rows_resolve;
- base.compiler.instance_rows_prepare;
- base.compiler.instance_rows_validate;
- base.compiler.instance_rows;
- base.discover.manifest_loader.

Это **потенциально достижимые пути**, не число обязательных чтений в каждом запуске. Source loaders, source/layout checks и approved secrets processing нельзя автоматически считать нарушением архитектуры. Секреты не следует переносить в публичный effective JSON ради нулевого YAML-count.

## 7. Валидация текущего HEAD

Команды выполнялись из /home/nixos/workspaces/home-lab; task использовал PYTHON=.venv/bin/python, Python bytecode write отключён.

| Команда / проверка | Новый результат |
|---|---|
| Целевой pytest, 20 файлов / 175 tests | **159 passed, 16 failed**, 142.86 s |
| task build:compile-validate PYTHON=.venv/bin/python | **PASS**; total=100, errors=0, warnings=21, infos=79 |
| task framework:verify-lock PYTHON=.venv/bin/python | **PASS**, strict verification |
| task validate:plugin-cycles PYTHON=.venv/bin/python | **PASS**, 105 plugins |
| task validate:adr-consistency PYTHON=.venv/bin/python | **PASS**, errors=0, warnings=0 |
| task validate:ai-layer-table PYTHON=.venv/bin/python | **PASS** |
| task validate:plugin-manifests-strict PYTHON=.venv/bin/python | **FAIL**, прежние 2 config-schema warnings |
| task validate:quality-fast PYTHON=.venv/bin/python | **FAIL**, Black: 12 files would be reformatted, 542 unchanged |
| task validate:error-catalog-sync PYTHON=.venv/bin/python | **FAIL**, 276 undefined / 53 unused |
| git diff --check | PASS; tracked diff отсутствует |
| Placeholder tests с экспериментальным in-memory bootstrap | **14 passed**, отдельно от рабочего дерева |

**Прежние manifest warnings:**
- base.generator.ansible_role: inventory_profile без config_schema coverage;
- base.assembler.artifact_contract_guard: generator_migration_metadata без config_schema coverage.

**Error catalog:** I7950–I7953 добавлены корректно. Остаточные 276 undefined codes не являются незакрытым F05 для этих четырёх кодов. Большой общий drift остаётся отдельным debt.

**Black:** список 12 файлов по существу тот же, что в предыдущем рапорте; новая серия не устранила форматирование ранее затронутых SOHO compiler, WireGuard и MikroTik projection. Здесь нельзя приписывать все 12 текущему commit.

### Воспроизводимая команда целевых тестов

```bash
cd /home/nixos/workspaces/home-lab
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -o addopts= -p no:cacheprovider \
  tests/plugin_integration/test_instance_rows_compiler.py \
  tests/plugin_integration/test_soho_product_profile_validator.py \
  tests/plugin_integration/test_soho_profile_resolver_compiler.py \
  tests/plugin_integration/test_projection_helpers.py \
  tests/plugin_integration/test_projection_snapshots.py \
  tests/plugin_integration/test_terraform_mikrotik_generator.py \
  tests/plugin_integration/test_mikrotik_capability_driven.py \
  tests/plugin_contract/test_projection_ownership_boundaries.py \
  tests/plugin_contract/test_soho_contract_schemas.py \
  tests/plugin_contract/test_soho_profile_catalog_contract.py \
  tests/ai_rules/test_layer_table_contract.py \
  tests/plugin_contract/test_compiler_support_modules.py \
  tests/plugin_contract/test_compiler_runtime_emit.py \
  tests/plugin_contract/test_compiler_diagnostics.py \
  tests/plugin_contract/test_compiler_output_streams.py \
  tests/plugin_integration/test_compiler_reporting.py \
  tests/plugin_integration/test_instance_placeholder_plugin.py \
  tests/plugin_integration/test_generator_sunset_validator.py \
  tests/plugin_integration/test_generator_rollback_escalation_validator.py \
  tests/test_strict_profile_placeholder_contract.py \
  -q --tb=short
```

## 8. Порядок завершения

1. Синхронизировать lane/deploy diagnostics callers и покрыть clean/stale report contract.
2. Обновить placeholder test bootstrap; подтверждён минимальный путь через annotation compiler.
3. Закрыть два MikroTik теста осмысленным effective fixture/golden update.
4. Привести relevant quality gates к зелёному состоянию; старый manifest/catalog debt явно отделить от исправленного поведения.
5. После этого выполнить полный task ci и безопасный полный build.

**Ограничения:** полный task ci, полный generate/assemble/build и deploy в этой итерации не запускались. Стандартный compile/validate выполнялся в passthrough secrets mode. Production secrets не расшифровывались; SOPS не вызывался. Широкие build tasks, очищающие generated, не запускались. Изолированные probes использовали синтетические данные и временные каталоги; не являются заявлением об успешном production deploy.

**Финальная оценка:** прежние локальные регрессии исправлены в основном правильно; перенос на effective model/publications стоит сохранить. Главный оставшийся функциональный разрыв — не parser, а несогласованность orchestration с opt-in diagnostics. Остальное ближайшее завершение — тестовые fixtures и подтверждающие gates.
