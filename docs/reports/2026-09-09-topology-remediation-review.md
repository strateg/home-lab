# Повторный аудит топологии home-lab после исправлений

**Дата:** 2026-09-09  
**Проверенный commit:** `71c426471a540bdb38d69fdee4899df214de24ff`  
**База сравнения:** `c9a7cab8cd25d4398c7a07c1828cefabcc66c666`  
**Рабочая копия:** `/home/nixos/workspaces/home-lab` (NixOS/WSL, не копия на диске D:).  
**Предыдущий документ:** [Аудит ограничений и целевой топологии](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/docs/reports/2026-09-08-topology-constraints-and-target-design.md)

## 1. Вердикт

**Исправления существенно улучшили согласованность модели, но закрытие всех замечаний и готовность безопасного развёртывания пока не подтверждаются.**

Главное достижение: строгая компиляция теперь даёт **0 errors / 0 warnings**. Исправлены model lock, capability-каталог, шлюзы девяти LXC, физическая привязка Orange Pi и типы runtime AmneziaWG. Новые ADR 0116/0117 задают разумное разделение физического устройства и сетевого интерфейса.

Однако зелёная компиляция не обнаруживает несколько существенных разрывов:

1. **P1:** Proxmox firewall остаётся stub; защитная проверка не замечает реально объявленную матрицу.
2. **P1:** три RouterOS-контейнера сохраняют противоречивые сетевые привязки.
3. **P1:** VPN overlay `10.100.1.0/24` отсутствует в CIDR-составе зоны в проекции security matrix.
4. **P1:** ссылки на секреты периферии переименованы, но все три новых файла отсутствуют в проверенной рабочей копии.
5. **P2:** перенос IoT-привязок на L2 не доведён до MikroTik-проекции.
6. **P2:** профильные тесты и строгий manifest gate не полностью зелёные.

Это вывод о **модели и реализации pipeline**, не утверждение о фактическом нарушении изоляции на работающем оборудовании.

## 2. Область и методика

Прочитаны universal rulebook, ADR rule map, Codex role overlay, scoped packs topology/host-placement/network-security/secrets/generator/testing, новые ADR 0116/0117. Проверены изменения между указанными коммитами, исходная топология, свежий effective JSON, проекции MikroTik/Proxmox и поведение firewall generator.

Разделены три вида доказательств:

- **Исходная модель:** ссылки, значения, объявления политик и backup-путей.
- **Компиляция/генерация:** actual effective JSON и результаты вызова production-кода на нём.
- **Эксплуатация:** не проверялась; нет подключения к устройствам, apply/deploy или restore-тестов.

Исходники не исправлялись. Штатный `task validate:default` включает полный вызов компилятора и обновляет диагностические/генерируемые артефакты; ручного редактирования `generated/` не выполнялось. Секреты не расшифровывались; для анализа сохранена редактированная копия IR в `/tmp/home-lab-topology-recheck-i8i_p6on/effective.json`.

## 3. Проверки: свежие результаты

Во всех task-командах использован `PYTHON=.venv/bin/python`; режим секретов — passthrough.

| Проверка | Результат |
|---|---|
| V5Compiler, strict_model_lock=true, discover → compile → validate | **PASS: 0 errors, 0 warnings, 80 infos** |
| `task build:compile-validate` | **PASS: 0 / 0 / 80** |
| `task validate:default` | **PASS**, полный compile: **0 / 0 / 149** |
| `task validate:layers` | **PASS: 62 classes, 140 objects, 189 instances, 29 runtime edges** — счётчики валидатора |
| `task framework:verify-lock` | **PASS** |
| `task validate:adr-consistency` | **PASS**, strict titles |
| `task validate:quality-fast` | **PASS**, Black: 555 файлов без изменений; isort: PASS |
| `task validate:plugin-manifests-strict` | **FAIL**, 2 config_schema warnings; task exit 201, underlying script exit 1 |
| 9 профильных integration test files | **85 passed, 1 failed**, 20.91 s |
| Независимое сравнение CIDR VLAN | **10 VLAN, пересечений не найдено** |
| Проверка дубликатов `network._resolved_ip` | **Не найдены** в проверенном наборе полей |
| Проверка выбранных критических source-ref полей | **Остались 2 ссылки на отсутствующий ws-nixos** |
| Proxmox firewall generator на свежем IR | **SUCCESS + I9302**, ошибочно сообщает, что active matrix не найдена |

Полный `task ci` и весь pytest-suite не запускались. Отсутствие дубликатов в указанных полях не равно полной проверке всех адресов внутри произвольных вложенных runtime-структур.

### Профильный pytest

```bash
.venv/bin/python -B -m pytest -o addopts= -p no:cacheprovider -q \
  tests/plugin_integration/test_security_policy_refs_validator.py \
  tests/plugin_integration/test_security_matrix_compiler.py \
  tests/plugin_integration/test_ip_derivation_compiler.py \
  tests/plugin_integration/test_projection_helpers.py \
  tests/plugin_integration/test_projection_snapshots.py \
  tests/plugin_integration/test_generator_projection_contract.py \
  tests/plugin_integration/test_object_projection_loader.py \
  tests/plugin_integration/test_terraform_mikrotik_generator.py \
  tests/plugin_integration/test_on_directive_object_defaults.py
```

## 4. Повторная оценка T01–T10

| ID | Статус | Что подтверждено / что осталось |
|---|---|---|
| **T01 — WiFi secrets** | **Исходный дефект устранён; эксплуатационное закрытие не подтверждено** | Два plaintext `passphrase` заменены на `passphrase_ref`. Ротация ранее опубликованных значений и судьба Git history не проверялись. |
| **T02 — model lock / capabilities** | **Закрыто** | Строгая компиляция не воспроизводит прежние E3201/W3201; framework lock также проходит отдельную строгую проверку. |
| **T03 — gateway / attachment** | **Частично** | Все 9 LXC теперь имеют gateway = _resolved_gateway = 10.0.100.1. Противоречие трёх RouterOS-контейнеров осталось. |
| **T04 — Proxmox isolation** | **Не закрыто** | firewall=false у 9 LXC; projection.status=stub; enforcement отсутствует, guard ошибочно возвращает success. |
| **T05 — широкие разрешения / HTTP inheritance** | **Не закрыто** | LAN→management остаётся разрешён целиком; object-level HTTP override не попадает в MikroTik projection. |
| **T06 — VPN exit zone** | **Частично** | Неверный trust_level заменён на security_level=1, отличие от vpn_tunnel=2 восстановлено. Но overlay CIDR теряется; баг обработки 0 остаётся. |
| **T07 — broken references** | **Частично** | Из прежнего набора 11 неразрешимых ссылок остались 2: ws-nixos в двух WireGuard peer lists. Исправлены 5 data-asset hostrefs, router trust-zone и набор WiFi refs. |
| **T08 — Orange Pi physical port** | **Закрыто в физической модели** | Кабель и канал согласованы: ether3 → usb_hub_eth, via_peripheral указывает на существующий hub; порт объявлен у host. См. отдельный новый риск миграции секретов ниже. |
| **T09 — backup graph** | **Не закрыто** | Producer/consumer пути MikroTik backup по-прежнему различаются; weekly-full охватывает 2 из 9 LXC. |
| **T10 — runtime / image mismatch** | **Закрыто в прежнем диагностическом scope** | AmneziaWG использует routeros_container с target_ref контейнера. У PostgreSQL Germany удалена неверная прямая VLAN-привязка, listen address соответствует tunnel IP. Nextcloud latest заменён на 28. Типизированную service→tunnel связь и digest pinning стоит добавить отдельно. |

Не следует считать устранение warning достаточным доказательством сетевой достижимости. В частности, PostgreSQL Germany теперь описывает overlay через конфигурацию и notes, а не через проверяемый runtime network-binding.

## 5. Незакрытые замечания — доказательства и критерии закрытия

### R01 / T04 — P1: Proxmox isolation не обеспечивается pipeline

**Доказательства:**

- [srv-gamayun.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/srv-gamayun.yaml), строки 19–24: `firewall: false`, наследуется всеми 9 LXC.
- [Proxmox projection](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/projections.py), строки 52–93: возвращает пустую матрицу со статусом stub.
- [Proxmox firewall generator](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py), строки 115, 127, 141: ищет `instances.device` и `instance.extends_object`, тогда как свежий IR использует `instances.devices` и `instance.materializes_object`.
- Прямой вызов генератора на текущем IR вернул **PluginStatus.SUCCESS / I9302: No active security matrix found**. Матрица [inst.security_matrix.proxmox.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml) реально объявлена и управляется srv-gamayun.

**Следствие:** даже уже написанный fail-closed guard обходится из-за неверного контракта чтения IR. Межконтейнерная изоляция внутри одного VLAN не возникает автоматически от perimeter firewall.

**Закрытие:** сначала исправить guard и добавить тест с настоящей canonical shape; затем реализовать PVE rules, enable flags и тесты разрешённых/запрещённых потоков. Внутризонные overrides должны выбирать workload/service endpoints: сейчас названия prometheus/nginx не ограничивают source конкретным контейнером.

### R02 / T03 — P1: RouterOS attachment всё ещё противоречив

В свежем IR у **docker-adguard, docker-mosquitto, docker-tailscale**:

| Поле | Значение |
|---|---|
| bridge_ref | inst.bridge.containers |
| gateway | 172.18.0.1 |
| vlan_ref | inst.vlan.lan |
| _resolved_ip | 192.168.88.210/24, .211/24, .212/24 |
| _resolved_gateway | 192.168.88.1 |

Источник: [RouterOS container instances](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/routeros_container); проекция: [projections.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py).

Это не исправлено заменой gateway на Proxmox host. Явное намерение routed/multi-interface attachment для этой комбинации не установлено. Выделенные /30 veth двух AmneziaWG-контейнеров в это замечание **не включены**.

**Закрытие:** выбрать одну каноническую привязку и derivation chain либо объявить отдельные интерфейсы/маршрутизацию. Валидатор должен запрещать несовпадение gateway и производной сети без явного исключения. Проверять конечный veth/interface output, а не только IR.

### R03 / T06 — P1: VPN overlay не входит в адресный состав зоны

Источник [inst.trust_zone.vpn_exit.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.trust_zone.vpn_exit.yaml), строки 18–23: security_level=1 и additional_networks=10.100.1.0/24.

Фактическая проекция:

```json
{
  "security_level": 1,
  "isolated": true,
  "vlans": ["inst.vlan.vpn_exit"],
  "cidrs": ["192.168.56.0/24"]
}
```

[MikroTik projection](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py), строка 639, формирует CIDR только из VLAN. Поэтому реальный road-warrior prefix не входит в zone address list. Наличие отдельных tunnel/runtime rules не доказывает эквивалентность zone policy для этого prefix.

Дополнительная in-memory проверка: только `security_level` изменён на **0**, без изменения исходников. Проекция вернула **2** — из object default. Причина: строки 631–632 используют `or`, смешивая «значение отсутствует» с 0/false. Текущее значение 1 обходит, но не исправляет этот дефект.

**Закрытие:** объединять и валидировать VLAN + overlay CIDR; сохранять явно заданные 0/false; добавить regression tests и отрицательные flow tests. Проектору желательно потреблять уже рассчитанную canonical matrix, а не повторять derivation с иной семантикой.

### R04 / T05 — P2: разрешения шире заявленной цели, HTTP override теряется

- [inst.security_matrix.mikrotik.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml), строки 75–81: правило «admin» принимает весь LAN `192.168.88.0/24` к management без ограничения портов.
- Строки 50–57 разрешают всей user zone TCP 5432/6379 ко всей servers zone.
- Это разрешённые R6 exceptions, а **не нарушение синтаксиса схемы**. Но least-privilege и граница management ослаблены.

Независимый дефект inheritance:

- [obj.network.security_matrix.soho.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/network/obj.network.security_matrix.soho.yaml), строки 30–38: HTTP override находится на верхнем уровне object.
- [projections.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py), строка 713: читает его из `properties.policy_overrides`.
- В actual projection только четыре instance override; `user-to-servers-http` отсутствует.

**Закрытие:** задать явные admin endpoints и сервисные назначения, ограничить порты; исправить object/instance merge и тестировать наличие всех ожидаемых R6 rules в проекции и выходных правилах.

### R05 / T07 — P2: два peer device_ref всё ещё не разрешаются

`ws-nixos` отсутствует среди 189 instance IDs:

- [inst.tunnel.wg-home-to-oci.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.tunnel.wg-home-to-oci.yaml), строка 79.
- [inst.tunnel.wg-exit.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.tunnel.wg-exit.yaml), строка 128.

**Закрытие:** добавить реальное C→O→I устройство, заменить ref корректным либо ввести явный контракт external peer. Не создавать фиктивный host только для подавления диагностики. Включить nested road_warrior_peers.device_ref в reference validation.

### R06 / T09 — P2: backup не образует доказанный полный путь восстановления

- [backup-mikrotik-config.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/operations/backup-mikrotik-config.yaml), строка 18: producer сохраняет в `/home/dmpr/workspaces/projects/home-lab/backups/mikrotik`.
- [backup-offsite-weekly.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/operations/backup-offsite-weekly.yaml), строка 19: consumer читает `/mnt/hdd/backups/mikrotik`.
- Между ними не объявлен transfer/replication edge.
- [backup-weekly-full.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/operations/backup-weekly-full.yaml), строки 12–16: только PostgreSQL и Redis при названии «all LXC».

**Закрытие:** связать output/input через artifact/data-asset refs и execution/storage host; задать обязательное покрытие persistent workloads и документированные исключения; проверить restore. Исправленные asset hostrefs сами по себе не чинят producer/consumer path mismatch.

## 6. Новые риски после рефакторинга

### N01 — P2: L2 IoT interface не подключён к MikroTik projection

Сама архитектурная идея ADR 0117 правильная. Но [projections.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py), строки 1240–1304, всё ещё ищет `vlan_ref` и `secrets_ref` на **device row**, не разрешая новую связь `device.provides_ref → network interface.device_ref`.

**Воспроизведение:**

1. Текущая проекция: `mac_vlan_assignments = []`.
2. На копии текущего IR только возвращены старые перемещённые поля трёх устройств из source на commit d0ad4fef.
3. Тот же production projection builder снова возвращает **3 assignments**: BOOX, Jolla, Sony.
4. Исходники при этом не изменялись.

**Важно о масштабе:** [bridge_hosts.tf.j2](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/templates/terraform/bridge_hosts.tf.j2) сейчас выводит эти assignments как **комментарии**, не как Terraform resources. Поэтому подтверждена потеря проекции и генерируемого описания, **не доказано исчезновение live VLAN enforcement**. Отдельный Ansible access-list playbook имеет свой список устройств и этим тестом не проверялся на оборудовании.

У Sony DHCP reservation теперь задана в L2 interface, но этот аудит не подтвердил её сквозной путь до deployable DHCP output.

**Закрытие:** projection должен join-ить L2 interface с L1 device в effective JSON; добавить тесты join, missing/mismatched backref и snapshot трёх assignments. Не возвращать L2 поля на L1 ради совместимости. Отдельно доказать генерацию DHCP reservation.

### N02 — P1: миграция peripheral secrets не завершена в рабочей копии

Все три новых instance `secrets_ref` указывают на отсутствующие файлы:

| Instance | Ожидаемый файл внутри project secrets | Факт |
|---|---|---|
| inst.peripheral.usb.hub.bluecloud-001 | peripherals/usb-hub-bluecloud-001.yaml | отсутствует |
| inst.peripheral.usb.wifi.asus-001 | peripherals/usb-wifi-asus-001.yaml | отсутствует |
| inst.peripheral.bt.hid.logitech-m720-001 | peripherals/bt-hid-logitech-m720-001.yaml | отсутствует |

Источники: [Peripheral instances](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/peripherals). Существуют два файла под **старыми** именами; это установлено перечислением имён без чтения зашифрованного содержимого.

[MIGRATION.md](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/secrets/peripherals/MIGRATION.md) описывает перенос, но инструкция не является доказательством выполненной миграции. Hub обеспечивает основной NIC Orange Pi, поэтому ошибка не ограничивается новым несущественным HID.

**Закрытие:** подготовить корректные SOPS-файлы и схему device_id/mac_address/linux_interface, проверить resolve в доверенной среде. Добавить safe preflight existence/schema для ссылок без вывода секретов. При переносе использовать защищённый временный каталог/права, а не предсказуемые plaintext-файлы общего /tmp из примера инструкции. Без проверки ключей/содержимого здесь нельзя утверждать, что существующие шифротексты совместимы с новой схемой.

### N03 — P2: profile test suite не зелёный

Падает MikroTik-параметр теста [test_generator_uses_projection_contract_only](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_generator_projection_contract.py), строка 183:

```text
jinja2.exceptions.UndefinedError:
'dict object' has no attribute 'firewall_baseline_rules'
```

[terraform_mikrotik_generator.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py), строки 93–103, задаёт defaults для dhcp/dns_servers/nat, но не firewall_baseline_rules; [firewall.tf.j2](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/templates/terraform/firewall.tf.j2), строка 117, обращается к нему напрямую.

**Закрытие:** определить, обязательное это поле или optional; синхронно исправить контракт projection, defaults и test fixture. Не подавлять StrictUndefined глобально.

Ошибка воспроизводится на текущем HEAD; её появление именно в новых topology commits не доказано. Полный current-project compile проходит, поэтому вывод не равен «весь MikroTik generator неработоспособен».

### N04 — P2: строгий manifest gate обнаруживает неполные schemas

Не покрыты читаемые config keys:

- `base.generator.ansible_role` → `inventory_profile`;
- `base.assembler.artifact_contract_guard` → `generator_migration_metadata`.

Manifest sources: [generators.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/manifests/generators.yaml), строка 345; [assemblers.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/manifests/assemblers.yaml), строка 102.

**Закрытие:** дополнить/согласовать config_schema, затем повторить `task validate:plugin-manifests-strict`. Зелёная обычная компиляция не заменяет этот gate. Новизна этих двух долгов относительно прежнего аудита не установлена.

## 7. Оценка ADR 0116/0117

### Что полезно сохранить

- Разделение L1 physical device и L2 network attachment.
- Общий peripheral base и connection-type hierarchy вместо несвязанных USB-классов.
- Явные `via_peripheral` и host port inventory для повреждённого onboard NIC.
- Обновления class/object/module registration и lock вместе с миграцией.
- ADR и REGISTER согласованы по автоматической проверке.

### Что ещё нужно довести

1. **Сквозной контракт:** новая сущность должна иметь consumer, а не только schema и instance.
2. **Referential integrity:** backrefs device↔interface, peripheral attachment, nested peers и secret refs нуждаются в отдельном негативном тестировании.
3. **Миграционная атомарность:** новый ref + consumer + secrets migration + regression tests должны составлять один законченный change.
4. **ADR clarity:** ADR 0117 имеет статус Implemented, но D1 всё ещё говорит о technical debt вместо immediate refactor, а D2 — Future Refactoring Pattern. Раздел Implementation уже описывает выполненную миграцию. Обновить формулировки решений, сохранив D3 как явно deferred.
5. **Не расширять иерархию раньше потребителей:** stub-классы допустимы, но полезнее завершить поддержку реально используемых hub/interface, чем добавлять новые типы периферии.

## 8. Приоритетный план и целевой вариант топологии

**Перенумерация VLAN и перестройка физической сети сейчас не нужны:** пересечений десяти VLAN не найдено. Основной долг — довести имеющиеся данные до корректного enforcement и deployment.

### Шаг 1 — до следующего rollout

- Завершить peripheral secret migration и безопасный preflight.
- Сделать PVE guard честным fail-closed; не считать stub реализацией изоляции.
- Исправить три RouterOS attachments.
- Включить VPN overlay prefix в canonical zone membership.
- Подтвердить ротацию ранее опубликованных WiFi credentials.

### Шаг 2 — закрыть data-to-artifact contract

- Перевести IoT projection на join через effective JSON.
- Исправить HTTP policy inheritance и обработку 0/false.
- Ограничить admin/database доступ конкретными endpoints/ports.
- Довести PVE policies до workload-level enforcement и отрицательных flow tests.
- Закрыть failing test и strict manifest gate.

### Шаг 3 — эксплуатационная полнота

- Замкнуть backup producer → transfer → offsite → restore graph.
- Оформить ws-nixos как inventory instance или explicit external peer.
- Добавить service→tunnel binding, не полагаясь только на notes.
- Проверить доступность management при переходе на default-deny; иметь out-of-band/recovery путь.
- По возможности закрепить образы digest-ами: `nextcloud:28` устраняет прежний latest/28 mismatch, но тег major остаётся изменяемым.

### Критерий следующего успешного аудита

1. Все validation gates и профильные тесты PASS.
2. Проекции сохраняют policy inheritance, 0/false, overlay CIDRs и L2 interface joins.
3. Включённая PVE security matrix либо производит реальные rules, либо останавливает rollout.
4. Каждая обязательная secret/data/peer reference разрешается.
5. Backup coverage и restore подтверждены не только названиями jobs.
6. Live positive/negative flow tests и recovery plan подтверждены оператором.

**Итог:** принять исправления как значимый прогресс в модели; не объявлять весь remediation завершённым. Следующая итерация должна быть направлена преимущественно на consumers, negative tests и enforcement, а не на новые схемы.

---

Ранее выбранный фрагмент про timeout, внешний symlink и pytest-xdist относится к более широкому implementation-аудиту. Эти пункты не перепроверялись данным topology review и не считаются автоматически закрытыми; старое число «165 passed, 1 skipped» не является результатом текущего запуска. :codex-annotation{index="1"}
