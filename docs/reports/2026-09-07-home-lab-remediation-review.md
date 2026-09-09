# Повторное ревью исправлений home-lab — R01–R09

- **Дата:** 2026-09-07.
- **Репозиторий:** /home/nixos/workspaces/home-lab, WSL NixOS.
- **Проверенный HEAD:** fc455c68d0b2009bcfbec3fed0c4ffbd8fb2aec4.
- **Исправляющие коммиты:** f1cfb690 и fc455c68.
- **Исходный отчёт:** [Architecture and implementation review](/home/nixos/workspaces/home-lab/docs/reports/2026-09-07-home-lab-architecture-implementation-review.md).
- **Рабочее дерево до ревью:** чистое. Исправления оценивались по фактическому коду, не по сообщениям коммитов.
- **Изменения ревьюера:** только этот отчёт; исходники, topology, lock и конфигурация устройств не изменялись.
- **ADR для отчёта:** не требуется; отчёт не принимает новых архитектурных решений.

## 1. Вердикт

**Исправления полезны, но утверждение «все проблемы устранены» не подтверждается. Закрытие всего пакета R01–R09 и интеграционную готовность не рекомендую принимать.**

По критериям исходного отчёта:
- **2 замечания закрыты функционально:** R01, R05.
- **4 закрыты частично:** R02, R04, R06, R07.
- **3 не закрыты:** R03, R08, R09.

Наиболее важные оставшиеся проблемы:
1. Proxmox guard читает неправильную структуру compiled model и продолжает возвращать SUCCESS при активной матрице.
2. Timeout допускает SUCCESS после превышения лимита, а выход из executor ждёт работающий worker.
3. Bundle boundary check принимает symlink за пределы bundle при совпадающем строковом префиксе пути.
4. pytest-xdist не добавлен в проблемный plugin-validation workflow.
5. Strict framework lock, strict manifests и quality-fast gates не проходят.

Закрытие R01 означает исправление проверенного runtime-поведения, а не устранение дублирования runner-кода. Закрытие R05 относится к вновь создаваемым bundles, а не автоматическому исправлению уже существующих копий секретов.

## 2. Матрица оценки

| ID | Статус | Что реально исправлено | Что осталось |
| --- | --- | --- | --- |
| R01 | Закрыто функционально | Правильные envelope-поля, phase dispatch, scope, traceback | Дублирование run_plugin_once; нет нового постоянного regression-теста в исправляющем коммите |
| R02 | Частично | Известный VLAN преобразуется в CIDR, template использует адрес | Неизвестный VLAN игнорируется без ошибки; возможен fallback к целой зоне |
| R03 | Не закрыто | Добавлена попытка fail-closed guard | Guard читает payload.network и row.object_ref вместо канонической структуры; привязан к имени instance |
| R04 | Частично | Extra files, пустой checksum, дубликаты и простой traversal проверяются | startswith не доказывает принадлежность пути bundle; внешний symlink принимается |
| R05 | Закрыто для новых bundles | Secret directories 0700, files 0600 | Нужна отдельная обработка ранее созданных bundles |
| R06 | Частично | Текущие framework shards обнаруживаются: 105 plugins вместо 8 | Независимые копии resolver, рекурсивные includes без visited, missing includes пропускаются |
| R07 | Частично | Ошибки Git больше не превращаются в успешный scan | Недоступная история теперь блокирует scan; secrets-каталоги всё ещё исключены |
| R08 | Не закрыто | Добавлен -n auto в другую task-команду | pytest-xdist отсутствует в установке зависимостей plugin-validation.yml |
| R09 | Не закрыто | Есть глобальный timeout и диагностирование части задержек | Индивидуальный deadline не соблюдается; executor shutdown ждёт завершения worker |

## 3. Блокирующие и оставшиеся замечания

### F01 / R03 — P1: Proxmox guard не видит каноническую модель

**Код:** [firewall_proxmox_generator.py:103–111](/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py#L103).

Исправление читает:
- network_rows = payload.get("network", []);
- object_ref = row.get("object_ref", "").

Однако effective compiler публикует группы под instances, а object reference находится в instance.extends_object / instance.materializes_object.

**Контракт:** [effective_model_compiler.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/effective_model_compiler.py#L475), [projection_core.py](/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/projection_core.py#L89).

Независимый тест передал генератору канонически структурированную модель:
- instances.network содержит inst.security_matrix.proxmox;
- instance.extends_object = obj.network.security_matrix.proxmox_servers;
- instance_data.managed_by_ref = srv-gamayun.

**Результат:**

    R03_canonical_model= SUCCESS
    I9302: Proxmox firewall generator is a STUB. No active security matrix found - skipping.

Таким образом, защитная ветка не срабатывает на нормальном входе.

Дополнительно проверка "proxmox" in instance_id.lower() делает enforcement зависимым от имени instance: переименование не должно менять необходимость firewall. Это также противоречит capability-based классификации.

**Что требуется:**
1. Читать данные через канонические projection helpers.
2. Определять enforcer по managed_by_ref и его capabilities/контракту, а не по подстроке имени.
3. Проверять active matrix → FAILED на канонической модели, включая переименованный instance.
4. Не считать удаление декларации матрицы реализацией сетевой изоляции.

Статус работающего Proxmox не проверялся; замечание относится к реализации генератора.

### F02 / R09 — P2: timeout по-прежнему не является deadline

**Код:** [phase_executor.py:379–399](/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/phase_executor.py#L379), [with executor:201](/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/phase_executor.py#L201), [timeout handler:477–500](/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/phase_executor.py#L477).

Добавлен общий max(timeout) + 5 секунд. Но completed future уже завершён; result(timeout=remaining) не отклоняет результат, полученный позже индивидуального deadline.

Независимый тест использовал настоящий subinterpreter execution_mode и валидный manifest с timeout=1:

| Задержка worker | Wall time execute_stage | Результат медленного worker |
| --- | --- | --- |
| 1,4 s | 2,087 s | SUCCESS — лимит 1 s превышен |
| 7,0 s | 7,367 s | FAILED / E4103 — возврат только после завершения worker |

Во втором случае глобальный timeout не делает возврат bounded: context manager executor ожидает работающие задачи при shutdown. future.cancel() не останавливает уже исполняемый код. Зависший навсегда worker по-прежнему представляет риск зависания стадии; бесконечный worker в ревью не запускался.

**Что требуется:**
- индивидуальные deadlines от submission;
- явный отказ от commit просроченного результата;
- продуманная стратегия остановки/изоляции зависшего worker;
- bounded shutdown;
- статус TIMEOUT вместо обычного FAILED, если это предусмотрено общим runtime-контрактом;
- regression-тесты именно с execution_mode=subinterpreter.

### F03 / R04 — P1: проверка пути bundle допускает выход через symlink

**Код:** [bundle.py:302–307](/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/bundle.py#L302).

Условие str(file_path).startswith(str(root)) проверяет строковый префикс, а не принадлежность пути дереву каталогов.

Например, соседний каталог b-123-external имеет тот же префикс, что bundle b-123. Symlink из bundle на файл этого соседнего каталога принимается, если checksum-запись соответствует содержимому цели.

**Независимое воспроизведение в temp directory:**

    R04_sibling_symlink_accepted= (True, [])

В основном репозитории symlinks и внешние файлы для этой проверки не создавались.

**Что уже хорошо:** исходные два сценария больше не проходят:

    R04_extra_rejected= True
    R04_empty_rejected= True

**Что требуется:** Path.is_relative_to(root) / relative_to(root) после resolve, либо явный запрет symlinks для immutable bundle. Добавить тест соседнего каталога с совпадающим префиксом. Политика checksum-файлов не заменяет проверку происхождения bundle.

### F04 / R08 — P2: исправлена не причина ошибки CI

**Workflow:** [plugin-validation.yml:58–69](/home/nixos/workspaces/home-lab/.github/workflows/plugin-validation.yml#L58).

В нём по-прежнему устанавливаются pytest, pytest-cov, pyyaml, jsonschema — без pytest-xdist. Вызываемые plugin tasks по-прежнему используют -n auto.

Коммит изменил [task test:ci-coverage](/home/nixos/workspaces/home-lab/taskfiles/test.yml#L42), добавив -n auto. Это другая команда и не исправляет установку зависимостей проблемных jobs.

Проверка pytest с отключённой автозагрузкой plugins подтвердила зависимость аргумента от plugin:

    exit=4
    pytest: error: unrecognized arguments: -n

Это диагностическая имитация отсутствия xdist, не запуск чистого GitHub runner.

**Что требуется:** установить одинаковый dev dependency set во всех соответствующих jobs и проверить команды в чистом окружении. Желательно использовать lock-файл.

### F05 / R02 — P1 для fail-closed контракта: неизвестный VLAN всё ещё теряется

**Код:** [projections.py:739–750](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L739).

Для известного VLAN новая логика работает:

    R02_valid_scope= 192.0.2.0/24

Но при отсутствующем VLAN в индексе код просто не выставляет src_address / dst_address и не выдаёт ошибку:

    R02_missing_scope_no_error= MISSING

Template затем использует fallback к адресному списку всей зоны.

**Оценка:** исходный положительный случай исправлен. Требование «неподдерживаемое ограничение не должно молча исчезать» не выполнено.

**Что требуется:** при заданном, но неразрешённом VLAN-reference выдавать диагностическую ошибку и не выпускать расширенное правило; тестировать missing source/destination refs.

**Ограничение:** проверен boundary projection/template. Полный pipeline с некорректным VLAN не запускался; наличие другой ранней проверки могло бы блокировать отдельные случаи, но не заменяет явный контракт этого преобразования.

### F06 / R06 — P2: discovery стал полнее, но resolver остаётся неодинаковым

**Код:** [check_plugin_cycles.py](/home/nixos/workspaces/home-lab/scripts/validation/check_plugin_cycles.py#L29), [validate_plugin_manifests.py](/home/nixos/workspaces/home-lab/scripts/validation/validate_plugin_manifests.py), [lint_plugin_depth.py](/home/nixos/workspaces/home-lab/scripts/validation/lint_plugin_depth.py).

Положительный результат существенный: gate теперь проверяет **105 плагинов**. Исходный пропуск framework shards устранён на текущем дереве.

Однако вместо общего resolver добавлены три самостоятельные рекурсивные реализации:
- visited set отсутствует во время рекурсии; dedup выполняется после обхода;
- отсутствующие includes молча пропускаются;
- recursive include traversal применяется к root framework, не одинаково ко всем module manifests;
- validate_plugin_manifests не получает полного project-level discovery.

Синтетические проверки:

    R06_missing_include= []
    R06_cycle= RecursionError

**Что требуется:** общий resolver с runtime-эквивалентной семантикой, защитой от повторного обхода и явной политикой missing includes. Сравнивать наборы и порядок manifest/plugin IDs между runtime и validators.

### F07 / R07 — P2: fail-safe исправлен, работоспособность scan не восстановлена полностью

**Код:** [python-checks.yml:145–180](/home/nixos/workspaces/home-lab/.github/workflows/python-checks.yml#L145).

Git fetch/diff errors теперь корректно завершают gate ошибкой. Это правильное исправление исходного fail-open дефекта.

Но необходимая история для вычисления diff не обеспечена. При push без GITHUB_EVENT_BEFORE выбирается HEAD~1...HEAD. В shallow checkout этот ref отсутствует.

Воспроизведён сам Python body workflow на временном локальном Git checkout depth=1 с синтетическими файлами:

    R07_shallow_push_exit= 1
    git diff failed (exit 128): unknown revision HEAD~1...HEAD
    Secret scan cannot determine changed files - failing gate

Полный успешный прогон scanner локально не подтверждён: detect-secrets-hook отсутствовал в PATH тестового subprocess. Эта особенность окружения не классифицируется как дефект репозитория.

Дополнительно blanket exclusion projects/*/secrets/ не изменён.

**Что требуется:** корректно загружать нужную историю/refs, явно передавать event before SHA либо использовать event payload; отдельным gate проверять encrypted-формат секретных файлов вместо полного исключения каталога.

## 4. Подтверждённые исправления

### R01: реальное subinterpreter исполнение теперь работает

Использован настоящий InterpreterPoolExecutor с временным плагином:
- PRE handler публикует сообщение;
- RUN handler вызывает синтетическое исключение.

Результаты:

    R01 pre SUCCESS messages 1 traceback False
    R01 run FAILED messages 0 traceback True

Исправлены несовместимые поля envelope/diagnostic, phase dispatch и scope.

**Архитектурный остаток:** worker повторяет логику run_plugin_once(), а не делегирует ей. Риск дальнейшего расхождения остаётся; в частности, обработка outbox при исключении не полностью совпадает. Это не отменяет функциональное закрытие исходного R01.

### R05: права новых секретов ограничены

Синтетическая инъекция через create_bundle:

    secrets directory: 0700
    secret file: 0600

Пять новых regression-тестов в исправляющем пакете относятся к bundle: extra file, empty checksum, traversal, duplicate entry, secret permissions. Это хорошее направление тестирования.

**Операционная оговорка:** существующий bundle возвращается через ветку idempotent reuse и не проходит новую запись секретов. Ранее созданные bundles с 0644 необходимо отдельно проверить/пересоздать/ограничить в правах. Реальные секреты в ревью не расшифровывались.

## 5. Validation evidence

| Команда / проверка | Результат |
| --- | --- |
| task validate:plugin-manifests | PASS с 2 config_schema warnings |
| task validate:plugin-cycles | PASS, 105 plugins |
| task validate:module-index | PASS |
| task validate:adr-consistency | PASS, errors=0 warnings=0 |
| task framework:verify-lock | FAIL, E7824 |
| task validate:plugin-manifests-strict | FAIL, 2 warnings |
| task validate:quality-fast | FAIL, Black: 14 files would be reformatted |
| Целевые pytest | **165 passed, 1 skipped**, 8.93 s |
| Настоящий subinterpreter: phase/message/error | PASS |
| Bounded timeout: 1,4 / 7 секунд | Остаточный дефект подтверждён |
| Bundle extra/empty checksums | Оба исходных дефекта устранены |
| Bundle sibling-prefix symlink | Остаточный дефект подтверждён |
| Canonical model → Proxmox STUB | Остаточный дефект подтверждён |
| Valid/missing VLAN projection | Положительный случай исправлен, fail-closed отсутствует |
| Shallow Git scan body | Ошибка теперь блокирует gate |

### Целевые тесты

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -o addopts= -p no:cacheprovider tests/orchestration tests/kernel tests/test_deploy_workspace.py tests/plugin_api/test_parallel_execution.py -q

Итог предыдущего ревью был 158 passed, 1 skipped, но наборы не полностью идентичны: в повторный запуск дополнительно включён test_parallel_execution.py. Поэтому разницу числа passed нельзя интерпретировать только как количество добавленных тестов.

### Framework lock

Рабочее дерево было чистым, но committed framework lock не соответствует содержимому framework:

    E7824 framework.integrity mismatch
    lock:     sha256-c185e0ee9e0c00f10b4eb20e2690e2a878fe4c15e56a1dd5e94e5b709103965b
    computed: sha256-f6bc8c2bce0a1682e7e7f0dacd6012b0e596c71421c29fc16164e5d63a5f601f

В отличие от исходного ревью это нельзя объяснить только незакоммиченными изменениями: до проверки дерево было чистым. Lock не регенерировался ревьюером.

### Strict manifests

Теперь обнаруживаются реальные пропуски config_schema:
- base.generator.ansible_role: inventory_profile;
- base.assembler.artifact_contract_guard: generator_migration_metadata.

Само обнаружение этих warnings — положительный эффект более полного discovery. Но strict gate до их устранения не зелёный.

### Quality gate

Black сообщает: 14 files would be reformatted, 536 left unchanged. Среди них есть изменённые исправляющим пакетом bundle.py, test_bundle.py, firewall_proxmox_generator.py, projections.py.

Не все 14 замечаний обязательно появились в этих двух коммитах. Показатель характеризует readiness текущего HEAD. Isort в task validate:lint не был достигнут после падения Black.

## 6. Архитектурная оценка решения

### Что сделано правильно

- Исправления внесены в sources, а не в generated outputs.
- Bundle получил полезные негативные тесты.
- Увеличено реальное покрытие framework manifests.
- Ошибки Git перестали трактоваться как отсутствие изменений.
- Восстановлено исполняемое phase/envelope поведение worker.

### Что требует изменения подхода

1. **Исправлять контракт, а не похожий симптом.** R08 изменил команду исполнения, но оставил отсутствующую зависимость.
2. **Проверять реальные структуры данных.** R03 написан под модель, которую effective compiler не выпускает.
3. **Обеспечивать одну реализацию.** R01 повторяет runner, R06 добавляет три resolver-копии; исходное дублирование security matrix compiler/projection не устранено.
4. **Тестировать фактический execution mode.** Зелёный общий kernel suite не доказывает deadline поведения subinterpreter.
5. **Закрывать интеграционный цикл.** Lock, formatting и strict manifest gates должны проверяться после исправлений, а не только targeted pytest.

В исправляющих коммитах новые постоянные тесты добавлены только для bundle. Для R01/R02/R03/R06/R07/R08/R09 новые regression-тесты в рассматриваемом diff отсутствуют. Временные независимые probes этого ревью не заменяют committed tests.

## 7. Рекомендуемая следующая итерация

1. Исправить R03 через канонические helpers и enforcer capability contract; добавить canonical/renamed-instance tests.
2. Исправить containment R04 и добавить sibling-prefix symlink regression.
3. Обеспечить fail-closed VLAN resolution R02.
4. Реализовать индивидуальные deadlines R09 и bounded worker lifecycle.
5. Исправить зависимости plugin CI R08 и подготовку Git history R07.
6. Объединить discovery resolver и добавить coverage/parity tests R06.
7. Устранить strict config_schema warnings и форматирование.
8. После проверки доверенных изменений обновить framework lock штатной командой.
9. Выполнить full compile, targeted tests и task ci. Deployment acceptance проводить отдельно и только по согласованному сценарию.

**Критерий повторной приёмки:** исходные probes должны быть преобразованы в постоянные тесты, negative cases не должны возвращать SUCCESS, а обязательные gates текущего HEAD должны проходить.

## 8. Ограничения ревью

- Не выполнялись deployment, подключение к устройствам и расшифровка реальных секретов.
- Полный task ci не запускался: известны падающие prerequisite gates; task ci также содержит clean-generated, нежелательный для read-only review.
- Полная компиляция не выполнялась: strict framework lock уже не проходит.
- GitHub Actions и чистый hosted runner не запускались.
- Воспроизведения использовали временные файлы, синтетические данные и bounded delays; бесконечные worker-процессы не создавались.
- Проверка сосредоточена на R01–R09 и их исправляющих коммитах, не на всех промежуточных VPN/топологических изменениях.
- Ссылки и номера строк относятся к указанному HEAD.

