# Заключение о применимости FINAL-ARCHITECTURE-PROPOSAL (rev 3) к топологии

> **ERRATUM 2026-09-10.** Последующее ревью rev 3.1 нашло в этом отчёте девять
> фактических ошибок (E1-E9), из них восемь — ошибки замеров и одно завышенное
> заявление. Затронуты: число сервисов без данных (26 → 27 без хотя бы одного,
> 23 без обоих), число firewall-правил (110/72/38 → 86/67/19; за живые приняты 24
> закомментированных блока в `zone_firewall.tf:483-675`), объяснение `place_before`
> в `vpn.tf`, число файлов с `trust_zone_ref` (43 токена → 42 объявления),
> утверждение «`docker-nginx` уже рендерится» (в `containers.tf` его нет),
> «коллизия `schema_version` с ADR 0088» (коллизии не существует — реестр
> context-scoped), число авторских `priority` (9 → 15), число Docker на
> `srv-orangepi5` (12 → 11), и вывод о достижимости `runtime_nat_5` с WAN
> (наблюдение верно, вывод статически не следует и отзывается).
>
> Отчёт **оставлен без изменений** как запись состояния на момент ревью rev 3.
> Актуальные числа, разбор возражений авторов и текущий вердикт:
> [ревью rev 3.1](2026-09-10-adr0118-0119-rev31-applicability-review.md), раздел 0.

Предмет: `adr/0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md`, 419 строк, rev 3
предложения по ADR 0118 и ADR 0119.
Роль: архитектурное ревью применимости, выполнено агентом `tech-lead-architect`.
Дата: 2026-09-10.

Состояние дерева на момент ревью: HEAD `c788237e`, предмет ревью **untracked**;
ADR 0118, ADR 0119, `MIGRATION-AND-ACCEPTANCE.md`, `FORMAL-CONTRACT.md`,
`REGISTER.md`, `docs/ai/rules/network-security.md` — modified, не закоммичены.

## Граница доказательности

| Установлено | Не установлено |
|---|---|
| Соответствие текста предложения содержимому файлов рабочего дерева | Любое поведение рантайма |
| Статические замеры (grep, парсинг текста) с указанным методом | Результаты компиляции — не запускалась |
| Наличие/отсутствие сущностей в сгенерированных артефактах | Состояние живых устройств — не опрашивались |

Изменений в репозиторий это ревью не вносило. Тесты и `task ci` не запускались,
соответственно об их результатах ничего не заявляется.

---

## 0. Состояние ревизии

`git show HEAD:adr/0119-firewall-rule-ordering-contract.md` содержит редакцию 1
(«2026-09-10, authorization-preserving»). Заголовочные строки rev 2 **и** rev 3
добавляются одним и тем же незакоммиченным изменением.

Следствие: **rev 2 не существует как извлекаемое состояние.** Ссылки вида
«прежние array-based подсчёты не являются доказательством для rev 3»
(`FINAL-ARCHITECTURE-PROPOSAL.md:391`, `MIGRATION-AND-ACCEPTANCE.md:62`) отсылают
к состоянию, которое рецензент не может получить из истории.

Класс: дефект прослеживаемости. Лечится коммитом. На архитектуру не влияет.

---

## 1. Совместимость с действующей моделью

### 1.1 Что сохраняется — проверено

| Механизм | Подтверждение | Оценка |
|---|---|---|
| C→O→I merge для mappings | `topology-tools/plugins/compilers/instance_rows_on_prepare_compiler.py:234-242` — `_deep_merge` рекурсивно сливает вложенные dict; списки заменяются целиком (`:240-241`) | Ровно семантика AD-02. Движок уже существует |
| `@on` / ADR 0107 | `topology/object-modules/proxmox/obj.proxmox.lxc.debian12.base.yaml:10-29`, `topology/object-modules/mikrotik/obj.routeros.container.generic.yaml:29-33`, `topology/object-modules/docker/obj.docker.container.generic.yaml:26-31` | D7 «Object-level reuse» опирается на существующий механизм |
| 6 стадий + stage affinity | `topology-tools/plugins/manifests/{discoverers,compilers,validators,generators,assemblers,builders}.yaml` = 4/17/51/10/8/7 плагинов | ADR 0119 D3 воспроизводит существующие стадии дословно |
| ADR 0106 capability-driven | `topology/class-modules/capability-catalog.yaml:233-294`, `:442-456`, `:1476`, `:1518` | D6 ложится на существующий каталог |
| M1-B (ADR 0110) | `adr/0119-firewall-rule-ordering-contract.md:47-63`; `projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml:12` | Сохраняется без изменений |
| Address domain обобщает VLAN | `topology-tools/plugins/compilers/ip_derivation_compiler.py:76-80` **уже** принимает `bridge_ref` как альтернативу `vlan_ref`; живой потребитель `projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-nginx.yaml:11-12` | AD-03 легализует уже сделанное ad-hoc, а не изобретает понятие |
| ADR 0102 / `@group` как shard key | Не затрагивается; `FINAL-ARCHITECTURE-PROPOSAL.md:88-91`, ADR 0118 D1 | Совместимо |

**Шесть из семи опорных механизмов предложение не требует менять**, седьмой
(address domain) уже частично реализован.

### 1.2 Что ломается или требует решения

**(1) Направление ссылок вниз уже нарушено; rev 3 делает это блокирующей ошибкой.**

`projects/home-lab/topology/instances/network/inst.routing_policy.vpn_amnezia.yaml:37`:

```yaml
target_gateway:
  type: wireguard_interface
  value: wg-awg-russia
  container_ref: docker-amneziawg-russia
```

Инстанс с `@group: network` (L2), ссылающийся на L4 workload. То же в
`inst.routing_policy.rw_russia.yaml:35`, `inst.routing_policy.rw_sweden.yaml:35`,
`inst.routing_policy.vpn_sweden.yaml:37`.

ADR 0118 D4 (`adr/0118-universal-container-network-model.md:139-142`): «L2 policies
reference network/zone/address-domain selectors, not L4/L5 instances… Do not add
upward L2 -> service dependencies».

Класс: существующее нарушение топологии, которое предложение превращает из
незамеченного в блокирующее. Решать **до G0a**, не на G2.

**(2) Relation contract не поддерживает коллекции.**

`topology/layer-contract.yaml:232-244` задаёт отношения по плоскому двухсегментному
пути. `topology-tools/plugins/validators/reference_validator.py:235-249` —
`_extract_relation_ref_candidate` умеет ровно `extensions.<field>` или
`extensions.<namespace>.<field>`. Путь `network.attachments.<local_id>.network_ref`
требует обхода с wildcard-сегментом.

Правила **продублированы** — в `layer-contract.yaml:210-265` и в
`reference_validator.py:34-113`; менять придётся оба, иначе дрейф.

Класс: отсутствующая реализация. Ограниченная, но обязательная на G1.

**(3) Коллизия `schema_version` с ADR 0088.**

`topology/semantic-keywords.yaml:3-5` регистрирует токен `schema_version` с
canonical `@version` и alias `version`; контексты (`:39-56`) — только
`entity_manifest` и `capability_entry`. Предложенный `network.schema_version: 2` —
вложенное поле данных с именем занятого семантического токена, вне обоих
зарегистрированных контекстов.

Параллельно ADR 0118 D1 (`:48-49`) утверждает, что local IDs «registered under the
ADR 0088 semantic keyword rules». Но ADR 0088 (`adr/0088-...md:52-78`) регулирует
алиасинг `@`-мета-полей манифестов и capability-записей, а не local keys
встроенных записей; механизма регистрации local keys там нет.

Класс: дефект документа (неточная ссылка) + новый контекст в реестре на G1.

**(4) `@on` regex ограничивает форму local keys.**

`instance_rows_on_prepare_compiler.py:29`: путь `(?P<path>[a-zA-Z0-9_.]+)`. Дефисы
в local key (`attachments.wan-uplink`) не разберутся. Зафиксировать как ограничение
схемы на G1.

**(5) Derived-field contract (D7/A23) сталкивается с 43 инстансами.**

`trust_zone_ref` объявлен в 43 файлах инстансов, включая все 29 сервисов. D7
(`adr/0118-universal-container-network-model.md:242`) объявляет zone membership
производным от `network_ref -> trust_zone_ref`; A23
(`MIGRATION-AND-ACCEPTANCE.md:182`) требует отклонения инстанса, объявляющего
производное поле.

Живой контрпример: `projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-adguard.yaml:13`
объявляет `trust_zone_ref: inst.trust_zone.servers`, тогда как его runtime target
`docker-adguard` сидит на `inst.vlan.lan` (`docker-adguard.yaml:9`), а
`inst.vlan.lan.yaml:13` даёт `trust_zone_ref: inst.trust_zone.user`.
**Объявленная и производная зоны противоречат друг другу уже сегодня.**

Модель ловит дрейф — это её плюс. Но объём (43 файла) в
`MIGRATION-AND-ACCEPTANCE.md §2C` не учтён.

**(6) `_resolve_ip` придётся переписать.**

`ip_derivation_compiler.py:229-239`:

```python
network_part, prefix = cidr.rsplit("/", 1)
octets = network_part.rsplit(".", 1)
base = octets[0]
resolved_ip = f"{base}.{host}/{prefix}"
resolved_gw = f"{base}.1"
```

Строковая подстановка последнего октета плюс жёстко зашитый gateway `.1`; `host == 1`
жёстко зарезервирован (`:103-112`). AD-03 (`FINAL-ARCHITECTURE-PROPOSAL.md:122-126`)
требует численного offset от network address и gateway без обязательного offset 1.

Масштаб на текущих данных: все VLAN-домены проекта — `/24` с gateway `.1`;
исключения — два `/30` у AWG-контейнеров, где адрес сегодня записан литералом.
Численный результат совпадёт везде, кроме двух `/30`. Риск низкий, но подлежит
измерению, а не утверждению. Rev 3 корректно этого не утверждает.

---

## 2. Изменения rev 3 против rev 2 — покомпонентно

### 2.1 `attachments[]` → `attachments.<local_id>` — улучшает применимость сильнее всего остального

Единственное изменение rev 3, устраняющее механический разрыв, а не
переформулирующее. Движок наследования проекта — `_deep_merge`
(`instance_rows_on_prepare_compiler.py:234-242`) — сливает mappings по ключу и
**не умеет** сливать списки по identity (`:240-241`).

С массивами C→O→I override был бы неопределён: объект не мог бы задать shape, а
инстанс — только placement, потому что инстансный список стёр бы объектный целиком.
С mappings пример из `AUTHORING-EXAMPLES.md §1` работает **на существующем движке
без изменений**.

Новый разрыв минимален: local keys ограничены `[A-Za-z0-9_]` — см. 1.2(4).

### 2.2 Backend workload выводится из `runtime.target_ref` — улучшает

`runtime.target_ref` уже является enforced-отношением L5→L1/L4
(`topology/layer-contract.yaml:210-216`) и присутствует у сервисов вместе с
`network_binding_ref` (27 из 29 файлов сервисов). `publication.backend` в baseline
не требует нового поля вообще — только `attachment_id`.

### 2.3 Пересечение портов в «original client-facing coordinates» — улучшает корректность, нагружает отсутствующие данные

На `projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-mosquitto.yaml`
сходятся три несогласованных системы координат:

- `:8-11` — `ports: {mqtt: 1883, mqtt_tls: 8883, websocket: 9001}`;
- `:31-33` — `security.allowed_from: [inst.vlan.iot, inst.vlan.servers]`;
- `:38` — `runtime.network_binding_ref: inst.vlan.lan`.

Ни один источник не говорит, какой из трёх портов публикуется, на каком frontend и
с каким backend port. Правило «An empty resolved intersection is an error»
(ADR 0118 D3 `:111-112`) корректно, но на этих данных даст ошибку, а не миграцию.

Разрыва нет — есть подтверждение, что `MIGRATION-AND-ACCEPTANCE.md §2B`
(derive→review→freeze) обязателен, а не факультативен.

### 2.4 «One logical security-plan authority» — улучшает, снимает конфликт с ADR 0063/0080/0086

Формулировка rev 1/rev 2 («One security-plan **compiler** owns the canonical plan»)
читалась как требование одного плагина, что противоречило бы микроядру и stage
affinity. Rev 3 (`adr/0119-firewall-rule-ordering-contract.md:41`, `:47-63`)
отделяет логическое владение планом от числа модулей и сохраняет M1-B явно.

Это соответствует реальности. Сегодня план forward-цепочки RouterOS производят три
независимых источника:

| Источник | Инстансы | Артефакт | Правил `routeros_ip_firewall_filter` | Из них с `place_before` |
|---|---|---|---|---|
| `inst.fw.*` (firewall_policy) | 4 | `firewall.tf` | 11 | 0 |
| `inst.security_matrix.mikrotik` | 1 | `zone_firewall.tf` | 61 | 31 |
| routing policies / VPN | 5 | `vpn.tf` | 38 | 41* |

\* в `vpn.tf` число `place_before` превышает число filter-ресурсов: часть приходится
на NAT/mangle-ресурсы.

Итого **110 filter-правил, 72 с `place_before`, 38 без**. Все `place_before`
указывают на один якорь `routeros_ip_firewall_filter.zone_drop_all_forward`,
который эмитится **шаблоном**
(`topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2:208-215`),
а не компилятором плана.

### 2.5 «Число и идентичность плагинов — implementation choice» — улучшает, но оставляет вопрос уровня

Плюс: соответствует ADR 0063, снимает конфликт с границей плагинов.

Минус — новый мягкий разрыв. «One logical authority» без указания уровня оставляет
открытым, где он живёт. Сегодня матрица считается дважды:

- `topology-tools/plugins/compilers/security_matrix_compiler.py:168-171` публикует
  каналы `security_matrices`, `zone_vlans`, `matrix_by_enforcer`, `vlan_cidr_map`;
- потребители этих каналов — **только валидаторы**
  (`topology-tools/plugins/manifests/validators.yaml:613,624,627`);
- `topology/object-modules/mikrotik/plugins/projections.py:552-770` заново выводит
  `zone_vlans`, `vlan_cidr_map` и мержит `policy_overrides` (`:720-770`)
  **на стадии generate**.

Это ровно то, что запрещает ADR 0119 D1 (`:42-45`): «generators render the validated
plan and do not create independent permits, reorder it, or **rediscover topology**».

Размещение authority — выбор **уровня плагина** (global/core против object-level
`mikrotik`), а не implementation detail. Логика в `projections.py:552-770` не
содержит mikrotik-специфики, кроме имён ресурсов.

### 2.6 Baseline: только `permit/binding_only` и `deny/scope_guard` — улучшает

Сужение до двух режимов делает A04 проверяемым. На реальных данных раскладывается
без остатка: 9 авторских `policy_overrides` (5 в `inst.security_matrix.mikrotik.yaml:50-81`,
4 в `inst.security_matrix.proxmox.yaml:33-67`) плюс объекты
`obj.network.firewall_policy.*` с `default_action` + `rules[]`
(`topology/object-modules/network/obj.network.firewall_policy.guest_isolated.yaml:12-32`).
Таблица D4.1 (`adr/0118-universal-container-network-model.md:161-171`) покрывает их
полностью.

### 2.7 ADR 0111: «numeric prefix-plus-offset» — улучшает точность

Единственная формулировка rev 3, прямо предписывающая изменение работающего кода.
См. 1.2(6). Формулировка корректна; последствие для существующего вывода не
оценено, но и не заявлено ложно.

### 2.8 Изменение, которое не улучшает применимость

`FINAL-ARCHITECTURE-PROPOSAL.md:27-29` выводит за скобки «Terraform-versus-command
adapter, выбор первого backend, порядок PR»; `adr/0119-...md:174-176` — «this does
not prescribe a new runner, controller or choice of Terraform/Ansible/backend
commands».

Для этого проекта граница Terraform/Ansible — не implementation detail, а
конституционный принцип. Именно она определяет, где живут `place_before`,
read-back и transition envelope из AD-08. Rev 3 честно объявляет это вне scope — но
тогда AD-08 нельзя принять как завершённый safety contract без пометки, что
привязка к существующей границе есть **отдельное архитектурное решение**.

---

## 3. Применимость к конкретным объектам топологии

### 3.1 Ложится без натяжки

**9 LXC на `srv-gamayun`.** Все девять объявляют ровно
`network: {vlan_ref: inst.vlan.servers, host: N}`. Один attachment, `direct`,
publication опциональна. `AUTHORING-EXAMPLES.md §1` отображается один-в-один; часть
shape уже в объекте (`obj.proxmox.lxc.debian12.base.yaml:12-17`). Бюджет
«6 key paths / 1 file / 1 ref» реалистичен: сегодня инстанс пишет 3 сетевых пути.

Оговорка — отсутствующий бэкенд, не модель: `obj.proxmox.lxc.debian12.base.yaml:17`
даёт `firewall: "@on:host.network.firewall?:false"`, а
`projects/home-lab/topology/instances/devices/srv-gamayun.yaml:24` — `firewall: false`.
`generated/home-lab/terraform/proxmox/lxc.tf` целиком — `locals { lxc_instances = [...] }`
с комментарием «LXC resource rendering is added in parity phase».

**12 Docker на `srv-orangepi5`.** 9 контейнеров ровно `vlan_ref + host`, 2 стека,
1 portainer. `docker-portainer.yaml:20-22` — единственный инстанс проекта с готовым
port mapping (`"9000:9000"`, `"9443:9443"`), кандидат на `host_publish`. Остальные —
attachment без publication (сценарий A06).

Побочно: `obj.docker.container.generic.yaml:30` наследует `network.network_ref` от
host, а инстансы пишут `vlan_ref` — два имени одного понятия уже сейчас;
`network_ref` в attachment это унифицирует.

**`inst.bridge.containers.yaml`** (`ip: 172.18.0.1/24`, `cidr: 172.18.0.0/24`).
AD-03 уже реализовано: `docker-nginx.yaml:11-12` использует `bridge_ref + host: 2`.
Чего не хватает: у файла нет `trust_zone_ref`, и в
`generated/home-lab/terraform/mikrotik/zone_firewall.tf` нет address-list для
`172.18.0.0/24` — bridge-домен вне зональной модели. Класс: отсутствующие данные.

**`inst.vlan.lan.yaml`** — есть prefix, gateway (`:18-20`),
`dhcp_range: 192.168.88.10-192.168.88.254` (`:15`), `reserved_ranges: .1-.9` (`:22-25`).
Данные для проверки владения адресом есть. Сразу даёт результат A05: `docker-adguard`
host 210, `docker-mosquitto` 211, `docker-tailscale` 212 — все три внутри
объявленного DHCP-диапазона. Сегодня это никем не проверяется.

**`inst.vlan.servers.yaml`** — `status: staged`, canonical `10.0.100.0/24`
(подтверждено: `zone_firewall.tf` даёт `zone-servers = 10.0.100.0/24`). Устаревший
комментарий `inst.security_matrix.proxmox.yaml:24` («10.0.30.0/24») уже зафиксирован
в `MIGRATION-AND-ACCEPTANCE.md:18-19`.

**`inst.security_matrix.mikrotik.yaml`** — `managed_by_ref` (`:12`), `zone_refs`
(`:15-23`), `address_space.vlan_refs` (`:27-37`), `policy_overrides` (`:45-81`).
Прямо соответствует AD-01 «Enforcement scope» и AD-05 candidates. M1-B сохраняется.

### 3.2 Ложится, но требует данных, которых нет

**`docker-adguard.yaml` (13 строк).** Дефект из «Context» ADR 0118 воспроизводится
по файлам:

- инстанс: `network: {vlan_ref: inst.vlan.lan, host: 210}` → `192.168.88.210/24`;
- объект `obj.routeros.container.generic.yaml:31-33` наследует `bridge_ref` и
  `gateway` через `@on:host.*`;
- хост `projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml:271-273`:
  `bridge_ref: inst.bridge.containers`, `gateway: 172.18.0.1`.

Эффективный `network`-блок имеет адрес из одного домена и gateway из другого. AD-03
разводит это на два attachment корректно.

Данных нет: ни один источник не говорит, какой адрес AdGuard слушает, публикуется ли
UI 3000 и кому. `svc-adguard.yaml:8-11` даёт три порта без источников,
`security.allowed_from` отсутствует, `owner` отсутствует.

Отсутствующий бэкенд: `generated/home-lab/terraform/mikrotik/containers.tf` содержит
только `awg_proxy_russia` (`:82`) и `awg_proxy_sweden` (`:267`). AdGuard, mosquitto,
tailscale и nginx **не рендерятся вообще**.

Замер authoring-базы воспроизводится точно: `MIGRATION-AND-ACCEPTANCE.md:51-52`
заявляет «nine key paths in two files with three references». Подсчёт по методу §2A:
`docker-adguard.yaml` — `host_ref`, `network.vlan_ref`, `network.host` (3);
`svc-adguard.yaml` — `ports.dns_udp`, `ports.dns_tcp`, `ports.web_ui`,
`trust_zone_ref`, `runtime.target_ref`, `runtime.network_binding_ref` (6). Итого 9
путей, 2 файла, 3 ссылки. Совпадает.

**`docker-tailscale.yaml` / `svc-tailscale.yaml`.** Сервис не имеет ни
`network_binding_ref`, ни `ports`, ни `allowed_from`. AD-09
(`FINAL-ARCHITECTURE-PROPOSAL.md:324`) относит dynamic identity к расширениям.
Ложится только как расширение; данных (маршруты, ACL) нет вообще.

**`docker-mosquitto.yaml` / `svc-mosquitto.yaml`.** Единственный сервис с почти
полным набором (ports + allowed_from + tls + clients). Кандидат №1 на пилот.

Пробел документа: `svc-mosquitto.yaml:26` —
`clients: - service_ref: svc-homeassistant@lxc.lxc-homeassistant`, боковая L5→L5
ссылка. AD-05 (`FINAL-ARCHITECTURE-PROPOSAL.md:191-193`) разрешает source = L2
selector либо точный L4 attachment через L4/L5 owner. Конверсия «сервис как источник
→ attachment его runtime target» подразумевается, но не описана. Мелкий пробел, не
блокирующий.

### 3.3 Не ложится без отдельного контракта

**`docker-amneziawg-russia.yaml` и `-sweden.yaml`** — четыре несоответствия сразу:

1. `network: {type: dedicated_veth, veth_name: veth-awg-ru, address: 172.18.22.2/30,
   gateway: 172.18.22.1}` (`:28-32`) — литеральный адрес на workload. AD-03
   (`FINAL-ARCHITECTURE-PROPOSAL.md:126-127`) требует модельный `/30` address domain —
   **его не существует** ни как инстанс, ни как класс. Класс: отсутствующие данные
   (создаваемые, не собираемые).
2. `wireguard_interface` (`:68-81`) с `address: 100.98.32.29/32` и
   `peer.endpoint: 172.18.22.2:51820` — третий адресный домен плюс цепочка transform
   WG→veth→proxy. AD-09 относит nested transforms и multipath к расширениям.
   **Не ложится в baseline по собственному тексту предложения** — то есть 2 из 6
   RouterOS-контейнеров baseline не покрывает.
3. `routing_policy_ref: inst.routing_policy.vpn_amnezia` (`:84`). Сам
   `inst.routing_policy.vpn_amnezia.yaml` — L2-инстанс с 15 chain-записями, mangle,
   routing table, MSS clamp, kill-switch и NAT, с upward-ссылкой `container_ref`
   (`:37`) и авторскими приоритетами `priority: 100` (`:41`), `priority: high`
   (`:87,94,101`). ADR 0119 D4 п.3 (`:119-120`) запрещает выводить порядок из
   числового priority автора.

   Совокупный объём по пяти routing policies: **50 записей `chain:`**, 4 файла с
   `container_ref`, 9 авторских `priority`.

   Целевой формы rev 3 для них не предлагает. Kill-switch (`:139-144`) в AD-03 назван
   «route constraint» (`FINAL-ARCHITECTURE-PROPOSAL.md:142-143`), но **route
   constraint отсутствует в таблице сущностей AD-01** (`:58-69`): там есть
   Attachment, Address allocation, Publication, Policy template, Binding, Mandatory
   guard, Enforcement scope, Approval, Plan. Владельца для маршрутного ограничения
   нет.

   Класс: **настоящий пробел документа.** Единственный случай, где AD-01 не даёт
   владельца для существующей сущности топологии.
4. `tunnel_nat: {enabled: true, out_interface: wg-awg-russia}` (`:90-92`) — NAT,
   привязанный к интерфейсу, а не к публикации. AD-04 (`:151-158`) знает только
   `direct`/`dnat`/`host_publish`. Владельца в AD-01 тоже нет.

**`docker-nginx.yaml`** — двойственный случай, и в этом его ценность.

`:17-22`:

```yaml
nat_rules:
  - chain: dstnat
    protocol: tcp
    dst_port: 8080
    to_address: 172.18.0.2
    to_port: 80
```

`to_address: 172.18.0.2` — руками записанный **производный** адрес: он же выводится
из `bridge_ref: inst.bridge.containers` + `host: 2` (`:11-12`). Это буквально A23
(`MIGRATION-AND-ACCEPTANCE.md:182`).

Одновременно — единственный в проекте полный `dnat`-случай с обоими портами
(frontend 8080 → backend 80) и явным bridge-доменом. Ложится идеально как пилот,
если `to_address` исчезнет.

Живое подтверждение F01/SEC-NAT на этой же цепочке: в
`generated/home-lab/terraform/mikrotik/firewall.tf` есть `runtime_nat_5`
(dstnat 8080 → `172.18.0.2:80`), а соответствующего forward-accept нет. При этом
`firewall.tf:72-78`:

```hcl
resource "routeros_ip_firewall_filter" "default_deny_wan_default_deny" {
  chain                = "forward"
  action               = "drop"
  in_interface_list    = "WAN"
  connection_nat_state = "!dstnat"
}
```

Условие `!dstnat` означает, что WAN-drop **обходится любым dstnat-соединением**.
DNAT сам по себе создаёт достижимость с WAN без явного permit — ровно тот паттерн,
который ADR 0119 D5 (`:148-152`) запрещает. Это видно в сгенерированном файле, а не
выведено умозрительно.

**`inst.security_matrix.proxmox.yaml`** — `status: disabled` (`:7`),
`managed_by_ref` закомментирован (`:17-18`), генератор
`topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py:10`
— «Status: STUB - Not yet implemented». Модель ложится концептуально (второй
enforcement scope, независимая capability-квалификация), но применять её не к чему.
Класс: отсутствующий бэкенд. ADR 0118 D6 (`:213`) этого не скрывает.

---

## 4. Влияние на существующий код — что и в каком порядке

Порядок идёт от контракта к потребителям: 8 плагинов читают `network.vlan_ref` по
фиксированному пути.

### Шаг 1 — контракт ссылок и идентичности

- `topology/layer-contract.yaml:232-244` — relation для коллекции
  `network.attachments.*.network_ref`; новые relations L4→L2 policy, L5→L2 policy,
  L5→L4 attachment. Формат сегодня не поддерживает wildcard-сегмент.
- `topology-tools/plugins/validators/reference_validator.py:235-249` — обход
  коллекций; `:34-113` — устранить дублирование правил с `layer-contract.yaml`.
- `topology/semantic-keywords.yaml` — новый контекст для local keys; разрешить
  коллизию имени `schema_version` (`:3-5`).
- `topology-tools/data/error-catalog.yaml` — provisional `NET-*`/`SEC-*` коды
  (ADR 0118 D7 `:268-272`); текущие 15 сетевых кодов сохраняют смысл.

### Шаг 2 — деривация адреса

- `topology-tools/plugins/compilers/ip_derivation_compiler.py:219-241` — `_resolve_ip`
  на численный offset через `ipaddress`; gateway из домена, не `base + ".1"`. Снять
  жёсткое `host == 1` (`:103-112`).
- Реестр дубликатов (`:118-137`) уже ключуется по `network_ref` — совместим с
  multi-domain, менять не нужно.
- `vlan_ref`/`bridge_ref` + `host` остаются входом legacy-адаптера (ADR 0118 D7 `:259-260`).

### Шаг 3 — единый источник правды по security intent

- `security_matrix_compiler.py:168-171` публикует 4 канала; потребители — только
  валидаторы (`validators.yaml:613,624,627`).
- `topology/object-modules/mikrotik/plugins/projections.py:552-770` — удалить
  повторный вывод `zone_vlans`/`vlan_cidr_map`/`policy_overrides`, заменить чтением
  канала.
- **Порядок обязателен:** сначала генератор начинает потреблять канал (поведение не
  меняется, диффы артефактов должны быть пустыми), только потом меняется семантика
  плана. Иначе рефакторинг и смена семантики смешиваются в одном шаге.
- **Уровневая граница:** authority размещается на global/core уровне
  (`topology-tools/plugins/compilers/`), object-level `mikrotik` сводится к rendering.

### Шаг 4 — рендеринг

`topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2` —
переписывание, а не правка:

- `:208-215` эмитит `zone_drop_all_forward`; ADR 0119 D4 (`:140-143`) требует, чтобы
  terminal deny «emitted by the plan compiler rather than by a template»;
- `:39-44` безусловный `input_established_related` (`established,related,untracked`)
  конфликтует с ADR 0119 D5 (`:160-162`);
- `:46-51` безусловный `input_icmp` accept конфликтует с D5 (`:163-165`);
- `:108,129,148,175` — `place_before` как единственный механизм порядка заменяется на
  consecutive positions (ADR 0119 D4 п.5).

### Шаг 5 — периферия (8 потребителей `vlan_ref`)

| Файл | Что меняется |
|---|---|
| `topology-tools/plugins/validators/network_core_refs_validator.py:59,65` | `_validate_vlan_refs` расширяется на attachments |
| `topology-tools/plugins/validators/network_runtime_reachability_validator.py:233-255` | уже умеет два формата; добавляется третий |
| `topology-tools/plugins/validators/network_runtime_reachability_validator.py:127-212` | `network_binding_ref` заменяется на `publication.frontend` |
| `topology-tools/plugins/generators/ansible_role_generator.py:406-410` | `routed_networks[0].get("vlan_ref")` — паттерн «первый выигрывает»; при multi-attachment становится ошибкой |
| `topology-tools/plugins/generators/projections/ansible_roles.py:188-205` | механическая правка resolve по `instance_id` |
| `topology-tools/plugins/generators/wireguard_generator.py:167-232` | **изменений не требует** — использует `allowed_vlan_refs`/`source_vlan_refs` как L2 selectors. Единственный из восьми, переживающий миграцию без правок |
| `topology-tools/plugins/validators/reference_validator.py` | см. шаг 1 |
| `topology-tools/plugins/compilers/security_matrix_compiler.py` | см. шаг 3 |

### Шаг 6 — данные топологии

25 файлов с `network`-блоком, 38 с `vlan_ref`, 43 с `trust_zone_ref`, 29 сервисов,
5 routing policies, 4 `inst.fw.*`, 2 security matrix (одна disabled).

---

## 5. Риски применимости

### R1 — высокая × высокие. Routing policies не имеют владельца в AD-01

5 файлов, 50 chain-записей, kill-switch, 4 upward L2→L4 ссылки, 9 авторских priority.
Симптом: миграция встаёт на G2 без варианта «оставить как есть», потому что эти
правила живут в той же forward-цепочке, что и strict-план. Смягчение — объявить
routing/VPN plane отдельным versioned scope (ADR 0118 D4 `:149-150`, AD-10
`FINAL-ARCHITECTURE-PROPOSAL.md:344-345` это разрешают), но тогда strict-гарантия для
VPN-VLAN не заявляется. **Решать до G0a.**

### R2 — высокая × высокие. 110 правил на единственном enforcer, 38 без порядка, два независимых drop-источника

`zone_drop_all_forward` (`zone_firewall.tf`, из шаблона) и
`default_deny_wan_default_deny` (`firewall.tf:72`, из `inst.fw.default_deny`) — два
источника drop в forward-цепочке в разных файлах; межфайловый порядок Terraform не
гарантирует. `baseline_rule_1/2` (accept LAN→WAN и VPN_EXIT→WAN, `firewall.tf:123,131`)
идут **после** drop в порядке файла и `place_before` не имеют вовсе.

`MIGRATION-AND-ACCEPTANCE.md:145-147` требует одновременного переключения всех
активных потребителей для мигрируемого scope. На единственном роутере, который сам
является каналом управления, это блокирующий риск. G6 (`:141`) требует OOB management
и tested recovery plan — **OOB в топологии не смоделирован**: `svc-mikrotik-ui.yaml`
находится в management zone, доступ через ту же сеть.

### R3 — высокая × средние. Derive→review→freeze упирается в отсутствие данных

26 из 29 сервисов без `ports` или source-ограничения; `owner` не объявлен **ни у
одного** сервиса (0 из 29). G5 — не техническая задача, а сбор потоков в работающей
сети. До него strict неприменим ни к одному scope, кроме `docker-nginx` и
`svc-mosquitto`.

### R4 — средняя × высокие. Зональная перегрузка превращается в 20 сервисов без разрешений

20 из 29 сервисов в zone `servers`. В strict R1a same-zone allow даёт «Nothing»
(D4.1, `adr/0118-...md:165`). Энфорсер, который должен выражать intra-zone политику,
disabled со stub-генератором. Итог: 4 `policy_overrides` в
`inst.security_matrix.proxmox.yaml:33-67` (prometheus scrape 9090/9100/9187/9121/9150,
nginx→backends, app→postgres, app→redis) не станут ни разрешёнными, ни
проэнфорсенными — они просто перестанут быть описанными. Это не отказ, это **потеря
видимости**.

### R5 — средняя × средние. A23 отклонит 43 инстанса, и это не учтено в §2C

`trust_zone_ref` в 43 файлах, включая все 29 сервисов; `MIGRATION-AND-ACCEPTANCE.md §2C`
содержит 8 строк, `trust_zone_ref` среди них нет. Контрпример уже есть
(`svc-adguard.yaml:13` против `inst.vlan.lan.yaml:13`). Модель ловит дрейф — это плюс;
объём coordinated switch занижен.

### R6 — средняя × низкие. Два замера в supporting docs не сходились с репозиторием

| Утверждение | Проверка | Метод |
|---|---|---|
| «twenty-two of them declare exactly two keys» | **21**; распределение 21×2, 1×3, 2×4, 1×7 | Парсинг top-level блока `^network:` во всех `*.yaml` под `projects/home-lab/topology/instances/` |
| «Validators registered in the runtime \| 55» | **52** = 51 в `topology-tools/plugins/manifests/validators.yaml` + 1 в `topology/object-modules/network/plugins.yaml`; 55 — число файлов в каталоге валидаторов | Подсчёт зарегистрированных записей в манифестах |

Оба значения исправлены (см. раздел 7). ADR 0118 D8 (`:275`) заявляет: «The claim in
D7 is verifiable or it is not a requirement» — расхождение метода счёта подрывало
именно это.

Позитив в ту же сторону: база AdGuard «9 путей / 2 файла / 3 ссылки» воспроизводится
точно. Не сходились два производных числа, а не сам метод.

### R7 — низкая × средние. Rev 2 не существует в истории

См. раздел 0.

### R8 — низкая × низкие

`@on` regex и дефисы в local keys (`instance_rows_on_prepare_compiler.py:29`);
коллизия `schema_version` с ADR 0088. Обе закрываются на G1.

---

## 6. Вердикт

### Как целевая архитектура — применимо условно

Пять условий, каждое требует правки документа, а не кода:

1. **AD-01 дополняется владельцем для route/tunnel constraint и interface-scoped NAT.**
   Без этого 5 routing policies (50 записей) и 2 AWG-контейнера остаются вне модели, а
   kill-switch не имеет представления.
2. **Явно фиксируется, что «one logical security-plan authority» размещается на
   global/core уровне**, а `mikrotik` object-модуль сводится к rendering. Иначе rev 3
   разрешает воспроизвести текущее нарушение (`projections.py:552-770`) в новой обёртке.
3. **Уточняется ссылка на ADR 0088** и разрешается коллизия имени `schema_version`.
4. **Фиксируется, что граница Terraform/Ansible — отдельное архитектурное решение**,
   а не implementation choice, поскольку AD-08 без неё не имеет исполнителя.
5. **Приводятся в соответствие два замера** — выполнено, см. раздел 7.

При выполнении этих условий AD-01..AD-10 внутренне согласованы и совместимы с C→O→I,
ADR 0102, 0063/0080/0086, 0106, 0107, M1-B и деривацией IP.

Отдельно: **именованные mappings — правильный выбор именно для этого репозитория, и
это проверяемо, а не вкусовое.** `_deep_merge` уже даёт нужную семантику наследования;
массивы её не имели бы, и rev 2 в этом месте был бы неприменим по механическим причинам.

### Как основание для миграции прямо сейчас — не применимо

Не из-за качества документа. Блокируют три независимые вещи, ни одна из которых не
находится в зоне design-фазы:

1. **Нет данных.** 26 из 29 сервисов без `ports`/source; 0 из 29 с `owner`. Требуется
   сбор потоков в работающей сети (G5).
2. **Нет бэкендов.** `firewall_proxmox_generator.py` — STUB;
   `generated/home-lab/terraform/proxmox/lxc.tf` не рендерит LXC вообще; 4 из 6
   RouterOS-контейнеров отсутствуют в `containers.tf`.
3. **Нет модели** для 5 routing policies и 2 AWG-контейнеров (условие 1 выше).

### Применимо немедленно, не требует ждать G1-G8

Каждый пункт независим от статуса ADR 0118/0119:

- **Устранить дублирование security matrix.** `security_matrix_compiler.py:168-171`
  публикует каналы, которые не потребляет ни один генератор;
  `projections.py:552-770` считает то же самое заново на стадии generate. Чистая
  рефакторинг-задача, снимающая существующий дрейф между compile и generate.
- **38 из 110 firewall-правил без `place_before`**, включая два независимых
  drop-источника в forward-цепочке — существующий дефект порядка, диагностируемый
  сегодня.
- **`docker-nginx.yaml:21` `to_address: 172.18.0.2`** — руками записанный производный
  адрес. Валидатор A23 можно ввести точечно.
- **A05 на текущих данных:** `.210/.211/.212` внутри объявленного DHCP-пула
  `192.168.88.10-.254` (`inst.vlan.lan.yaml:15`). Проверка реализуема без нового профиля.
- **`connection_nat_state = "!dstnat"`** в `firewall.tf:76`: WAN-drop обходится любым
  dstnat-соединением, `runtime_nat_5` достижим с WAN без явного permit.

### Рекомендуемый пилот

`docker-nginx` (единственный полный `direct` + `dnat` с обоими портами и явным
bridge-доменом, уже рендерится) плюс `svc-mosquitto` (единственный сервис с `ports` +
`allowed_from` + TLS). Оба на RouterOS, оба не затрагивают routing policies, оба не
требуют proxmox-энфорсера.

---

## 7. Исправления замеров, внесённые по итогам ревью

| Файл | Было | Стало |
|---|---|---|
| `adr/0118-analysis/MIGRATION-AND-ACCEPTANCE.md:49` | «twenty-two of them declare exactly two keys» | «twenty-one» |
| `adr/0118-analysis/MIGRATION-AND-ACCEPTANCE.md:126` | «Validators registered in the runtime \| 55» | «Validator plugins registered in manifests \| 52» |
| `adr/0118-analysis/SPC-REBUILD-2026-09-10.md:75,82` | 22, 55 | 21, 52 |
| `docs/reports/2026-09-10-adr0118-0119-spc-acceptability-review.md:182,190` | 22, 55 | 21, 52 |

Дополнительно в `MIGRATION-AND-ACCEPTANCE.md §2C` и в разделе замеров SPC-рапорта
добавлен метод счёта, без которого числа невоспроизводимы.

Проверки после правок: `check_adr_consistency.py --strict-titles` PASS (0 errors,
0 warnings); `validate_agent_rules.py --fail-on-warnings` PASS (20 rules, 12 packs);
`git diff --check` PASS.

---

## 8. Открытые вопросы для человека

| Вопрос | Гейт |
|---|---|
| Принять или отклонить 5 условий раздела 6 | G0a |
| Решить судьбу upward L2→L4 ссылок в 4 routing policies | G0a |
| Объявить routing/VPN plane отдельным versioned scope или включить в strict | G0a |
| Разместить «logical plan authority» на уровне core | G0a / G1 |
| Собрать flow-данные для 26 сервисов | G5 |
| Смоделировать OOB management для G6 | G6 |

---

## Приложение. Проверенные файлы

`adr/0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md`,
`adr/0118-analysis/MIGRATION-AND-ACCEPTANCE.md`,
`adr/0118-analysis/AUTHORING-EXAMPLES.md`,
`adr/0118-universal-container-network-model.md`,
`adr/0119-firewall-rule-ordering-contract.md`,
`adr/0119-analysis/FORMAL-CONTRACT.md`,
`adr/0088-semantic-keyword-registry-and-at-prefixed-meta-fields.md`,
`topology/layer-contract.yaml`,
`topology/semantic-keywords.yaml`,
`topology/class-modules/capability-catalog.yaml`,
`topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2`,
`topology/object-modules/mikrotik/plugins/projections.py`,
`topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py`,
`topology-tools/plugins/compilers/ip_derivation_compiler.py`,
`topology-tools/plugins/compilers/security_matrix_compiler.py`,
`topology-tools/plugins/compilers/instance_rows_on_prepare_compiler.py`,
`topology-tools/plugins/validators/reference_validator.py`,
`topology-tools/plugins/manifests/*.yaml`,
инстансы под `projects/home-lab/topology/instances/`,
артефакты под `generated/home-lab/terraform/`.
