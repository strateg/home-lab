# ADR 0118/0119 — финальное предложение по реализации

**Historical implementation exploration — not the final design approval target.**
The [final architecture proposal](FINAL-ARCHITECTURE-PROPOSAL.md) supersedes this
document as the current proposal. Plugin count, first backend, controller/tool
choice and PR sequence below are unadopted options; implementation planning is deferred.

**Дата:** 2026-09-10. **Статус:** предложение к архитектурному утверждению, не реализация.
**Основа:** commit `c788237e` **плюс незакоммиченная rev 2**, последний
[SPC-рапорт](../../docs/reports/2026-09-10-adr0118-0119-spc-acceptability-review.md)
и [примеры](AUTHORING-EXAMPLES.md).
Исходная рабочая редакция сохранена; это отдельный анализ, а не её молчаливая замена.

## 1. Решение в одном абзаце

Сохранить **attachment → publication → bound policy**, но до G1 зафиксировать
одну реализуемую грамматику и правила наследования. Рекомендую **именованные
mapping-коллекции в authored YAML, нормализованные массивы в IR**, единственную
форму адреса, явное связывание политик и два небольших compiler-plugin:
`network_intent` и `security_plan`. Начать с статической IPv4-модели и одного
лабораторного RouterOS backend; другие семейства адресов и backend не считать
поддержанными до отдельного доказательства. Безопасность и доступность проверять
на всём выбранном пути, а применение выполнять отдельным transaction controller
через существующий DeployRunner. Не начинать с массовой миграции YAML или нового
универсального firewall framework.

**Вердикт по последнему рапорту:** направление верное, но заключение «остались
только человеческие действия, дальнейший анализ не нужен» преждевременно.
Есть проверяемые контрактные пробелы. G0a должен утвердить решения ниже;
G0b/DoD tailoring необходимы для соответствующих assurance-заявлений, но не
должны блокировать разработку схем и offline-прототипа.

## 2. Что проверено заново

| Проверка | Результат и границы |
|---|---|
| Штатные discover, compile, validate; strict-model-lock; fail-on-warning; secrets passthrough | 0 errors, 0 warnings, 80 info; без generate/assemble/build/deploy |
| Снятие compiled_json после штатных стадий | 189 instances; 29 services; 5 service instance_data с ports; 0 с owner |
| Security/IP/projection tests, три файла | **32 passed, 1 failed**; подробности ниже |
| Прямой вызов существующего merge | Sparse array override теряет driver/interface/defaults |
| Прямой вызов существующей IP-деривации | /23 и смещённый /25 дают неверные адреса |
| Документация RouterOS, Docker и Proxmox | Подтверждена необходимость backend-specific hook/state контракта; устройства не опрашивались |

[Воспроизводимость и хэши входов](FINAL-PROPOSAL-EVIDENCE-2026-09-10.md).
Данные наблюдений/диагностик находятся в build, не являются источником топологии.
Свежий compile PASS не подтверждает Proposed-схему, которая пока не реализована.

## 3. Что исправить в предложении до реализации

### R01 — P1: object reuse для массивов не работает так, как описано

[instance_rows_on_prepare_compiler.py](../../topology-tools/plugins/compilers/instance_rows_on_prepare_compiler.py),
строки 234–242: deep merge рекурсивен только для mapping; список заменяется целиком.

```text
object: attachments=[{id:primary, driver:bridge, interface:eth0}]
instance: attachments=[{id:primary, network_ref:servers, host:60}]
result: attachments=[{id:primary, network_ref:servers, host:60}]
```

Следовательно, отсутствие driver/interface в «простом примере» не доказывает их
наследование. Отдельного merge-by-id сейчас нет. Это блокирует обещанный авторский
бюджет, но не означает, что существующая flat-топология сломана.

**Решение:** mapping по локальному ID в новых source-коллекциях. Не менять
глобальную семантику списков и не вводить сопоставление по индексу.
Альтернатива — schema-scoped merge-by-id только для новых коллекций — возможна,
но требует отдельного алгоритма, delete/override-семантики и большего тестового
контракта без преимущества перед mapping.

### R02 — P1: address domain нельзя реализовать нынешней IP-функцией

[ip_derivation_compiler.py](../../topology-tools/plugins/compilers/ip_derivation_compiler.py),
строки 218–239, подставляет host как последний октет.

| Вход | Нынешний результат | Требуемое смещение от начала сети |
|---|---|---|
| 172.18.22.0/30 + 2 | 172.18.22.2 | 172.18.22.2 |
| 10.0.0.0/23 + 300 | 10.0.0.300 | 10.0.1.44 |
| 10.0.0.128/25 + 2 | 10.0.0.2 | 10.0.0.130 |

Это воспроизведение helper-функции, не утверждение, что текущие /24 в lab дают
такие ошибки. Принцип ADR 0111 сохраняем, реализацию арифметики — нет.
Также существующая функция предполагает gateway .1; новый resolver обязан брать
gateway из domain, а резервировать именно объявленные allocations.

### R03 — P1: не определено, когда policy template становится разрешением

В примерах policy существует отдельно, но нет точной грамматики её активации для
publication/direct/egress. Фраза «удаление публикации не удаляет авторизацию»
опасна: **шаблон** политики может остаться, но grant, связанный с удалённой
публикацией, обязан исчезнуть вместе с соответствующим session state.

**Решение:** L2 policy — неактивный контракт; только явный binding создаёт grant.
Удаление/отключение binding отзывает именно этот grant. Если существует другой
независимый binding, он рассматривается отдельно и показывается в explain.
Исключение — явно подключённые к enforcement scope mandatory guards: они
активируются scope, а не наличием publication.

### R04 — P1: не хватает endpoint-level источников без upward refs

Только zone/network selectors недостаточны для точных app→DB и admin→UI правил.
Нельзя лечить это L2 ссылкой на L5 service или новой копией IP-адреса в каждом
правиле.

**Решение:** L2 reusable policy допускает явные binding placeholders.
L4/L5 binding задаёт конкретные source/target references в разрешённых направлениях.
Compiler разрешает endpoints через attachments. Пустой placeholder не означает
any. Подробный контракт — раздел 5.

### R05 — P2: примеры ещё не образуют единую грамматику

- Пример 1 использует `attachments[].host`, пример 2 —
  `attachments[].address.host`.
- Пример 3 называет два сервиса, но YAML содержит один список; отсутствуют
  mechanism/announcement и полный network wrapper. Это sketch, не positive fixture.
- Правило «effective address никогда не пишется» нуждается в разграничении
  derived IP и явно допустимого статического allocation на L2.
- Enum `bridge/host/none/macvlan/ipvlan` найден в
  [workload class](../../topology/class-modules/L4-platform/compute/workload/class.compute.workload.yaml),
  строках 28–43, внутри **topology_scope_schema.internal_networks**.
  Это не зарегистрированный enum нового attachment и не доказательство RouterOS parity.
- Два разных host-offset улучшают учебный пример, но **не обязательны**:
  одинаковые числа в разных address domains допустимы.

**Решение:** одна canonical source-форма; примеры компилируются как fixtures;
сокращённые фрагменты явно помечены и не учитываются как passed examples.

### R06 — P2: авторский бюджет пока измеряет синтаксис, не когнитивную нагрузку

Числа key paths полезны; «половина сложности неизбежна» и 15→62 терминов не
являются экспериментальным измерением человеческого понимания. Исключение object
defaults из подсчёта hides navigation cost, если читатель вынужден открывать их.

**Решение:** сохранить budget как regression-индикатор, дополнить количеством
файлов для изменения и для объяснения effective результата. Проверять по fixture
с реальным наследованием и команде explain, а не по сокращённому куску YAML.
Не обещать заранее, что новая версия уложится в 30 paths.

### R07 — P1 для начала backend migration: baseline projection test не зелёный

[test_generator_projection_contract.py](../../tests/plugin_integration/test_generator_projection_contract.py)
падает для MikroTik:
`firewall.tf.j2:117: 'dict object' has no attribute 'firewall_baseline_rules'`.
[Generator](../../topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py),
строки 93–102, задаёт defaults для dhcp/dns_servers/nat, но не этого поля.

**Решение:** определить required/optional contract и синхронно исправить projection,
fixture и consumer. Не выключать StrictUndefined. Это существующий долг, не
регресс от текущей документационной работы.

### R08 — P1: reuse DeployRunner не означает готовую firewall transaction

[runner.py](../../scripts/orchestration/deploy/runner.py), строки 67–122,
предоставляет execution/staging abstraction. Он не является network authorization
engine. [bundle.py](../../scripts/orchestration/deploy/bundle.py), строки 201–219,
сохраняет topology/secrets hashes, но ещё не заявленный security evidence contract.

**Решение:** transaction controller поверх runner, не дублирование runner для
native/wsl/docker/remote; новая версия bundle contract и safety tests.

## 4. Неподвижные границы

1. Сохранить Class → Object → Instance, derived layers, @on и шесть стадий.
2. ADR 0110 legacy R1–R6 не менять неявно; новый schema contract не является
   новым полем, которое старый generator может проигнорировать.
3. Один semantic plan, per-enforcer projections и отдельная qualification каждого
   backend. «Один compiler owner» не требует одного огромного Python-файла.
4. Publication, NAT, trust level, state и высокий specificity не дают прав.
5. Никаких live queries, secrets decrypt, apply или commit в рамках этого анализа.
6. Не раскладывать servers на новые зоны ради исправления grammar. Гранулярные
   service bindings должны работать в существующей зоне; физическое разделение
   нужно только там, где текущую границу невозможно доказанно защитить.

## 5. Рекомендуемый source contract v2

Это **предлагаемое уточнение ADR 0118**, не уже принятая схема. При утверждении
нужно одновременно заменить array-примеры в ADR/authoring docs. Не поддерживать
две canonical грамматики ради сохранения учебных примеров.

### 5.1 Формы и правила

| Объект | Canonical source | Нормализованный результат |
|---|---|---|
| Workload attachment | `network.attachments.<local_id>` | Attachment record с полным composite ID |
| Service publication | `network.publications.<local_id>` | Publication с точным backend/frontend |
| Non-service access | `network.access.<local_id>` на L4 workload | Bound infrastructure grant |
| Reusable network policy | L2 `class.network.firewall_policy`, versioned schema | Неактивный policy template |
| Mandatory network guard | L2 policy + `guard_policy_refs` на matrix/scope | Активный scope-wide deny/constraint |
| Enforcement scope | Существующий L2 security_matrix instance | Profile + managed_by_ref + охватываемые domains |

- `network.schema_version: 2` обязателен в **effective source**, но может
  наследоваться из object defaults. Это не `@version` модуля.
- `attachments`, `publications`, `access` — mappings. ID — ключ mapping,
  не повторное поле `id`. В IR — массивы, отсортированные по полному identity.
- Mapping deep-merge использует действующий C→O→I порядок. Списки protocol/ports/
  selectors заменяются целиком, никогда не конкатенируются неявно.
- `enabled: false` — явное отключение унаследованного record. Исчезновение
  override не удаляет inherited record. Ссылка на disabled attachment — ошибка;
  disabled publication отзывает её bound grant. Null не является delete/wildcard.
- Один адресный синтаксис: `address: {allocation: static, host: N}`.
  Верхнеуровневый `host` внутри attachment запрещён. Literal address допускается
  как **L2 allocation input**, но не как override computed address workload.
- `network_ref` выбирает network; для нескольких address domains требуется
  явный `address.domain_id`. Единственный domain может быть выбран однозначно.
  Family/VRF выводятся из domain, а не из имени instance.
- Gateway задаётся L2 domain; default route принадлежит attachment.
  Не выводить gateway из service frontend и не резервировать host=1 универсально.
- Bridge/veth/host-stack mechanism получается из class/object capabilities и
  substrate relation. Схема capability → supported attachment должна быть
  зарегистрирована; чужой enum из internal_networks не переиспользуется наугад.
- Для v1 публикации backend workload **выводится из runtime.target_ref**.
  Автор пишет только attachment_id. Явный противоречащий workload_ref — ошибка,
  multi-backend service откладывается. Полный composite ref сохраняется в IR.
- Unknown keys и противоречащие derived fields — hard error, не annotations,
  которые генератор может проигнорировать.

### 5.2 Policy и binding — точная семантика

L2 policy v2 имеет:
`effect: permit|deny`, `activation: binding_only|scope_guard`,
`direction: ingress|egress|transit`, source/destination selectors,
typed `flows[]`, owner/rationale. Для permit публикации применяется binding_only.
В первой реализации scope_guard допускает только effect: deny; permit с такой
activation — schema error. Guards активируются scope, а не publication binding.

Селекторы задаются одним из способов:

1. Конкретные L2 `network_ref`/`zone_ref`/allocation references.
2. Явный placeholder `{binding: source}` или `{binding: destination}`.

Placeholder — типизированный параметр, **не any**. После binding он обязан
разрешиться в непустое точное множество. Политика без binding не рендерится.

У L5 publication:
- `source_refs` задаёт разрешённые источники: L2 networks либо явные
  `{workload_ref, attachment_id}` на L4. Device endpoint требует однозначного
  network/interface selector, а не всех адресов устройства.
- destination binding — только эта publication, её frontend, protocol/ports,
  transform и backend; не вся сеть из destination policy.
- `policy_ref` плюс ports-map ограничивают друг друга пересечением.
  Политика с широким L2 destination остаётся ограничена publication endpoint.

У L4 `network.access`:
- ingress binding: destination — текущий attachment;
- egress binding: source — текущий attachment, target — явный L2 network/allocation;
- используются для DNS/NTP/update/прочих infrastructure flows без L5 publication;
- для app→DB предпочтителен один binding **на L5 DB service** с источником
  app workload, а не копии ingress и egress политики в двух workloads.

Один разрешённый flow материализует все необходимые gates вдоль пути:
не нужно вручную дублировать одинаковый grant на source-host, router и destination.
Списки mandatory guards со всех применимых scopes сужают этот flow.
В частности, широкая независимая L2 policy не может «ещё раз» отрендериться
в обход service binding.

Направления ссылок регистрируются в G1: L5→L4/L2, L4→L2, L2→L2 и уже разрешённый
enforcer→L1 binding. Новые L2→L4/L5 refs не вводятся. Source IP не равен identity:
нужны ingress provenance и anti-spoofing; без них workload selector нельзя
представлять как криптографически подтверждённую идентичность.

### 5.3 Пример наследования, который допускает действующий deep merge

```yaml
# Proposed object fragment; class schemas v2 ещё должны быть зарегистрированы.
defaults:
  network:
    schema_version: 2
    attachments:
      primary:
        enabled: true
        interface: eth0
        address:
          allocation: static
        default_route: true
```

```yaml
# Instance fragment: object supplies the shape, instance supplies placement.
network:
  attachments:
    primary:
      network_ref: inst.vlan.servers
      address:
        host: 60
```

В результате сохраняются interface/allocation/default_route. Это проверяемое
свойство mapping merge; не обещание, что нынешняя workload schema уже принимает
эти поля. Computed IP/gateway не присутствуют в instance.

### 5.4 Пример DNS: одна policy и одна публикация

Ниже **согласованные fragments тестового fixture**, не готовый home-lab deploy.
Fixture задаёт `inst.vlan.client_test = 192.0.2.0/24`, gateway .1, DHCP
.100–.199; frontend .53 зарезервирован с единственным owner
`rtr-test`. `inst.bridge.backend_test = 198.51.100.0/24`, gateway .1,
backend .20 свободен. Fixture должен моделировать оба interfaces на rtr-test.
Это явно заданные premises для source/model tests, не наблюдённые lease/ARP facts.

```yaml
# L2 policy instance fragment after C->O->I normalization:
schema_version: 2
effect: permit
activation: binding_only
direction: ingress
source: {binding: source}
destination: {binding: destination}
flows:
  - {protocol: udp, destination_ports: [53]}
  - {protocol: tcp, destination_ports: [53]}
owner: test-network-owner
rationale: DNS service for the client test network
# identity in fixture: inst.policy.dns_test
```

```yaml
# L4 dns-test, object supplies schema_version/interface/allocation:
network:
  attachments:
    backend:
      network_ref: inst.bridge.backend_test
      address: {host: 20}
```

```yaml
# L5 service; full publication fragment, not two services in one list:
runtime:
  target_ref: dns-test
network:
  schema_version: 2
  publications:
    dns:
      enabled: true
      backend: {attachment_id: backend}
      mechanism: dnat
      frontend:
        network_ref: inst.vlan.client_test
        address: {allocation: static, host: 53}
        address_owner_ref: rtr-test
        announcement: interface_address
      ports:
        - {protocol: udp, frontend: 53, backend: 53}
        - {protocol: tcp, frontend: 53, backend: 53}
      source_refs:
        - {network_ref: inst.vlan.client_test}
      policy_ref: inst.policy.dns_test
      enforcer_ref: rtr-test
```

Только в изолированном fixture без иных grants/denies:
client→VIP:53 разрешён, client→backend:53 напрямую запрещён, UI:3000 запрещён,
guest→VIP:53 запрещён. Disable/delete binding отзывает flow и state.
Добавление другого независимого binding может изменить verdict и должно
появиться в explain. Наличие owner/rationale не заменяет реальное human approval.

Production-пример с .210 сохраняет статус **blocked** до решения DHCP/lease
конфликта. Не объявлять его исправленным только потому, что тестовый fixture green.

Для direct publication frontend не аллоцируется повторно; он ссылается на
attachment. Для host_publish owner — реальный host bind address. Для NTP/ICMP
нужны отдельные typed flows; TCP-port syntax не используется как универсальный
протокольный язык.

## 6. Реализация внутри существующего runtime

### 6.1 Минимальная декомпозиция

```text
instance_rows / capabilities
  -> effective_model (existing compiled_json_owner)
  -> network_intent (compile/finalize; explicit subscription)
  -> security_plan (compile/finalize)
  -> security_contract (validate)
  -> backend generators (generate)
  -> existing artifact guard + bundle evidence (assemble/build)
  -> network transaction controller (deploy, outside compiler lifecycle)
```

**Почему после effective_model:** C→O→I и @on уже обработаны. Подписываться именно
на `base.compiler.effective_model / effective_model_candidate`, а не ожидать,
что outer orchestrator уже присвоил `ctx.compiled_json` посередине compile stage.
Не добавлять обратную зависимость effective_model→security_plan: это создаст цикл.
Новый network/security projection хранится отдельно; compiled_json owner остаётся один.

Имена ниже **предлагаемые**, до G1 их нет в manifest:

| Plugin | consumes (from_plugin/key) | produces |
|---|---|---|
| base.compiler.network_intent | base.compiler.effective_model / effective_model_candidate | network_intent, source_map |
| base.compiler.security_plan | base.compiler.network_intent / network_intent | plans_by_enforcer, obligation_inventory |
| base.validator.security_contract | network_intent + security_plan outputs | validation_evidence |
| Existing backend generator | plan for its enforcer + validation_evidence | Backend artifacts + semantic manifest |
| Existing artifact guard | Backend artifact manifests + validated plan digest | Bundle consistency evidence |

Каждый edge оформляется depends_on + consumes + produces. Два компилятора —
subinterpreter, read-only inputs, publish-only outputs; никаких скрытых mutations
normalized_rows. Внутренние pure функции могут жить рядом в
`topology-tools/plugins/compilers/network_security/`, без нового daemon/framework.
Для тестируемости отделить types, domains, selectors, bindings, ordering и digest.

Существующий ip_derivation остаётся legacy adapter; новый resolver не должен
снова выводить адрес v2 из flat полей. Legacy→canonical comparison выдаёт
migration diagnostics, но не превращает legacy implicit grants в strict grants.

### 6.2 Только три содержательных контракта

1. **NetworkIntent:** version/profile, domains, attachments, publications,
   bound grants/guards, route constraints и provenance.
2. **SecurityPlan:** canonical intent digest, backend/version/capability requirements,
   per-context rules/transforms, path obligations, ownership/state/transition requirements.
3. **Evidence:** validator versions, exact digests, assumptions, result per obligation,
   counterexamples; live observation хранится отдельно с timestamp/expiry.

Не создавать ещё одну авторскую «security topology». Все эти records derived;
проект редактирует исходные C→O→I данные.

Provenance должна включать исходный файл/поле, object defaults и @on source.
`policy_ref` без происхождения и точного binding не достаточен для аудита.

### 6.3 Resolver и bounded semantic engine

- Использовать числовую IP-арифметику network_address + offset; отвергать bool,
  неверный offset, prefix mismatch, reserved allocations и collisions.
- Domain identity включает project/scope/VRF/family; collision проверяется также
  между соседними domain definitions в одном routing domain.
- /31, /32, IPv6 и несколько prefixes — явная поддержка или unsupported,
  не автоматическое правило «первый и последний адрес всегда запрещены».
- v1 runtime qualification: static IPv4, TCP/UDP и необходимый bounded control
  traffic. Неохваченный IPv6 должен быть проверяемо отключён на всех путях,
  иначе deployment не qualifies. Это не «универсальная IPv4 безопасность».
- Predicate algebra: пересечение/разность нормализованных адресных и port intervals,
  protocol, direction, ingress/domain context и original-flow identity.
  Не начинать с произвольного Python/regex/SQL языка политик.
- Conflicting mandatory deny/permit и неоднозначный NAT — error с witness.
  Unknown overlap, неразрешимый route/path, resource-budget exhaustion — fail closed.
- Exact анализ ограниченного языка допустим; bounded sampling не выдаётся за
  доказательство всех потоков. Сложные transformations сначала unsupported.
- Один canonical топологический order на executable context. Позиции consecutive;
  hash/producer class/specificity не определяют разрешения.
- Терминальный deny последний **в managed executable scope**, а не буквально
  последний resource на всём устройстве. Dispatch, return и unowned chains
  проверяются на bypass; это уточнение требуется внести в rev 2 ADR 0119 D4.

## 7. Backend и deploy: практический выбор

### 7.1 Первый pilot — RouterOS, но не production router

Первый backend — лабораторный RouterOS с закреплённой версией, отдельными
client/backend сетями, статическим DNS DNAT и одним enforcer. Именно он проверяет
основную проблему проекта: адрес frontend не равен адресу workload, а разрешение
должно пережить трансляцию. Сначала negative/model tests, затем отдельный
лабораторный endpoint; не «проверка» массовым apply на rtr-mikrotik-chateau.

RouterOS NAT выбирает правило на первом пакете соединения и использует conntrack
для следующих; изменение NAT без обработки существующих соединений не является
доказательством немедленного отзыва.
[Официальная документация NAT](https://help.mikrotik.com/docs/spaces/ROS/pages/3211299/NAT).

Для pilot проверить:
- original-flow binding до DNAT, отсутствие доступа через прямой backend;
- точные source/protocol/port matches и обратный путь;
- exclusive ownership используемых connection/routing marks;
- default deny и ingress provenance, без обхода через общий established/related;
- disable/exclusion FastTrack для защищаемых путей либо доказанную эквивалентность;
- VIP ownership, DHCP/lease preflight, session revocation и restart.

FastTrack способен обходить facilities, на которых строится policy enforcement;
его нельзя считать прозрачной оптимизацией без теста конкретного пути.
[RouterOS packet flow](https://help.mikrotik.com/docs/spaces/ROS/pages/328227/Packet%2BFlow%2Bin%2BRouterOS).

**Не начинать с nested NAT, Tailscale ACL, AWG или arbitrary policy routing.**
Они остаются в общем inventory и legacy deployment, но не входят в первую
qualification. Это ограничение rollout scope, не отрицание их существования.

### 7.2 Второй и третий backend — отдельные contracts

| Backend | Обязательная работа | Что не является заменой |
|---|---|---|
| Proxmox | Реальная реализация stub; host/VM/CT interface enablement, ownership, rules и read-back | Включить matrix или firewall flag без generated enforcement |
| Linux Docker | Закрепить engine/firewall backend, bind ownership, original tuple, host-local и direct routing | Просто создать Compose ports |
| Другие платформы | Новый capability-qualified adapter + conformance suite | Разрешить новый enum и считать его поддержанным |

Docker iptables `DOCKER-USER` видит пакеты уже после DNAT; для original
destination нужны соответствующие conntrack matches.
[Docker iptables](https://docs.docker.com/engine/network/firewall-iptables/).
У Docker nftables нет аналогичной готовой цепочки DOCKER-USER, нужны собственные
base chains; accept в одной base chain не гарантирует окончательный accept.
Поэтому это **не тот же adapter с другим флагом**.
[Docker nftables](https://docs.docker.com/engine/network/firewall-nftables/).

Proxmox host forwarding и VM/CT IN/OUT — разные scopes. В официальном source
guide некоторые FORWARD/VNet возможности привязаны к новому backend; включение
per-interface firewall требуется дополнительно к общей настройке. Выбирать
адаптер по фактической версии/режиму, не по слову Proxmox.
[Официальный pve-firewall guide](https://github.com/proxmox/pve-docs/blob/master/pve-firewall.adoc).
Установленные версии и режимы устройств этим анализом не установлены.

### 7.3 Владение и controller

Предлагаемый `scripts/orchestration/deploy/network_transaction.py` использует
`get_runner()`/DeployRunner, а не реализует заново SSH/WSL/Docker transport.

Рекомендуемая единица управления — **весь утверждённый security scope**:
filter/NAT/dispatch/marks и связанные обязательства не раздаются независимым
конкурирующим исполнителям. В pilot backend generator выпускает immutable
operation plan и backend commands в bundle; controller выполняет только
разрешённую state machine и live-ID resolution, не изобретает новые policy rules.

Для production нужен однозначный ownership manifest:

| Ресурс | Единственный владелец | Обязанность перед activation |
|---|---|---|
| Bridge/interface/address/DHCP infrastructure | Действующий инфраструктурный generator/tool | Создать по плану под защитой guards, подтвердить ownership/leases |
| Security rules/NAT/dispatch/marks выбранного strict scope | Qualified network backend adapter | Один полный ordered plan и read-back |
| Conntrack revocation / restrictive guards | Тот же network transaction | Уложиться в утверждённый deadline |
| Service configuration, listeners, application auth | Ansible/service artifact owner | Соответствовать endpoint contract |

Перед handoff удалить **конкурирующее управление**, а не вслепую удалить live rules:
инвентаризация Terraform state → новый owner → безопасный guarded переход →
read-back → снятие старого ownership. Генерируемая операция не является ручным
исправлением устройства: её источник — валидированная топология и immutable bundle.

Если сохраняется Terraform как sole executor security scope, его конкретная
реализация должна пройти те же transition/read-back tests. Самих depends_on,
place_before, resource order или `terraform -target` недостаточно.
**Выбор для первого pilot:** qualified backend operation adapter, не надежда на
атомарность обычного Terraform apply. Production handoff — отдельное решение G6,
явно отражаемое в ADR 0119; существующий legacy writer до него не меняется.

### 7.4 Транзакционный протокол

```text
inspect -> verify approval and expected epoch -> acquire exclusive ownership
-> preflight -> install/verify guards -> stage candidate
-> revoke affected sessions -> activate -> semantic read-back + flow probes
-> remove temporary guards when safe -> commit evidence
failure -> keep restrictive state -> authorized recovery
```

Controller хранит journal в mutable deploy-state, bundle остаётся неизменяемым.
Каждое изменение имеет precondition, expected postcondition, idempotency key,
deadline и разрешённый recovery step. Lease/lock сам по себе не защищает от
стороннего administrator: unexpected live state/writer блокирует продолжение.

В transition envelope заранее задаются допустимые старые/новые flows и сроки
отзыва. Не брать их union автоматически; новые mandatory denies действуют
согласно утверждённому моменту и deadline. После deadline нельзя восстановить
старые grants обычным rollback.

Восстановление management планируется отдельно: OOB, журнал шага, ожидаемые
guards и актуальный разрешённый recovery bundle. Availability может временно
снижаться только в утверждённых пределах; «всё закрыли навсегда» не успех.

Проверяется **вся цепь admission**, не только managed rules: dispatch из root
chains, ранние accepts, route transforms, host-local, IPv6 и offload.
Неизвестный путь за пределами выбранной модели означает неполную qualification.

## 8. Реальные изменения по компонентам

Пути новых файлов ниже — целевое предложение, не уже созданный код.

| Компонент | Изменение |
|---|---|
| ADR 0118 + AUTHORING-EXAMPLES + migration plan | Утвердить mappings, единый address syntax, binding lifecycle и поправить budget |
| ADR 0119 | Уточнить managed-scope terminal deny, compile-finalize data flow и transaction ownership |
| L4 workload schemas под topology/class-modules/L4-platform/compute/workload | Network v2 definitions, unknown-field rejection, references и capability constraints |
| L5 service schemas под topology/class-modules/L5-application/service | Общая reusable publication definition; не 14 расходящихся копий |
| class.network.firewall_policy + security_matrix | Versioned bound policy/scoped guards, explicit profile и endpoint placeholder schema |
| topology/layer-contract.yaml + semantic registry | Новые reference paths и local IDs; не менять @group/layer semantics |
| instance_rows_on_prepare_compiler.py | Сохранить общий mapping merge; добавить regressions на новые вложенные mappings |
| ip_derivation_compiler.py | Legacy behavior inventory и test debt; v2 не обрабатывать старым flat resolver |
| proposed plugins/compilers/network_intent_compiler.py | Domain index, address resolution, explicit binding и provenance |
| proposed plugins/compilers/security_plan_compiler.py | Typed policy semantics, plans_by_enforcer, ordering и obligations |
| proposed plugins/validators/network_security_contract_validator.py | Blocking schema/semantic/capability/path checks и witnesses |
| plugins/manifests/{compilers,validators,generators,assemblers}.yaml | Полные DAG/exchange declarations; existing snapshot/envelope semantics |
| MikroTik projections.py + terraform generator/templates | Устранить baseline test failure; отделить legacy output от plan-only strict adapter |
| Proxmox firewall generator stub | Не переименовать stub в поддержку; реализовать в отдельной qualification итерации |
| Docker Compose generator | Publication delivery из plan, не independent grant; separate host policy adapter |
| deploy/bundle.py + bundle schema | Security intent/plan/evidence/ownership digests и versioned manifest |
| proposed deploy/network_transaction.py | State machine через DeployRunner; scoped backend operations и read-back |
| tests/plugin_integration + plugin_contract + acceptance-testing | Положительные/отрицательные fixtures, snapshot/deploy и TUC evidence |
| projects/home-lab/framework.lock | Refresh только в code/schema PR после фактического изменения framework |

Не добавлять обособленную систему policy approval в YAML как `approved: true`.
Approval должен привязываться к exact resolved semantic digest и scope/epoch,
сохранять reviewer/expiry по действующему governance; изменение object defaults,
source selectors или адресов инвалидирует соответствующее approval/evidence.

## 9. Очерёдность PR и критерии выхода

| PR | Содержание | Критерий завершения |
|---|---|---|
| P0 — baseline | Изолированно устранить failing projection contract; зафиксировать текущие outputs и тесты | 33/33 выбранных baseline tests; никакого StrictUndefined bypass |
| P1 — language | Утвердить изменения ADR и schema v2; mapping inheritance; numeric diagnostic allocation с collision test | Полные fixtures приняты/отклонены ожидаемо; ambiguity/unknown fields fail |
| P2 — semantic core | Domain arithmetic, bindings, interval predicates, intent/plan digests и manifests | /23,/25 и boundary tests; source map; determinism; no mutation leakage |
| P3 — offline backend | Один RouterOS lowering/interpreter и rendered-rule normalization | Differential verdicts совпадают; NAT/direct/backend/mandatory-deny mutants ловятся |
| P4 — lab transaction | Bundle/journal/controller, isolated backend, revocation/read-back | Interrupt/retry/reboot/drift/revocation tests; нет обхода через old state |
| P5 — home-lab candidates | Effective inventory, derive-review-freeze, DHCP/owner/path remediation plan | Для каждого service/infra flow известны endpoints, owner, reason, evidence requirement |
| P6 — scoped production | Один согласованный end-to-end scope, ownership handoff и guarded deployment | Все applicable A/HA gates; positive + negative live tests; approved recovery |
| P7+ — parity | Proxmox, затем Docker, tunnels/nesting по реальной необходимости | Каждый backend имеет самостоятельную versioned qualification |

P1 может готовиться параллельно P0 как документация, но baseline failure нельзя
маскировать новым snapshot. P2/P3 не требуют реальных credentials. G0b и
production authority завершаются до соответствующих assurance/deploy gates.

**Не назначаю часы до P3:** сейчас неизвестны фактические backend versions,
границы offload/state и стоимость безопасного handoff. Оценивать по завершённым
testable deliverables, а не по числу YAML-файлов.

## 10. Минимальная test strategy

### Schema и наследование

- Проверять полный C→O→I fixture, не только `yaml.safe_load`.
- Одинаковая семантика full и object-defaults вариантов.
- Mapping override сохраняет defaults; list replacement не расширяет selectors.
- Disabled attachment с активной ссылкой — error; disabled publication отзывает grant.
- Неверный local ID, duplicate YAML key, mixed v1/v2, unknown key и
  user-authored derived override — error.
- Один механизм подсчёта authoring budget: syntax paths + files to edit +
  files to inspect via provenance. Baseline и candidate считаются одинаково.

### Semantic properties

- Host arithmetic и declared gateway на /24, /23, shifted /25; unsupported
  /31/IPv6 fail явно, а не случайным адресом.
- Identity содержит domain/VRF/family; одинаковые offsets в разных domains допустимы.
- Unbound policy создаёт **ноль grants**.
- Publication delete/disable удаляет свои grants; другой binding виден отдельно.
- Permit∩mandatory deny блокирует candidate с конкретным witness.
- Удаление permit не увеличивает admitted set; добавление deny не увеличивает его.
- Accept-all mutant нарушает soundness; all-drop — required-flow availability.
- Два frontend одного backend, прямой backend и потеря original tuple —
  отдельные отрицательные тесты, не один NAT snapshot.
- 0/1/101/1000 rules, перестановки unordered inputs, full-key collisions,
  cycle/unknown transform/complexity budget и envelope serialization.

### Backend и transition

- Reference verdict → rendered rule interpreter → backend observation —
  три разных уровня, результаты не подменяют друг друга.
- Проверять весь applicable путь: source provenance, NAT, policy, state, reverse
  traffic, dispatch/return и соседние unowned chains.
- Прервать apply после каждого шага; повторить после restart/retry; добавить
  неожиданный writer, lease conflict, stale approval/identity и audit failure.
- Verify activation и снятие guards, не только steady state.
- Повторный apply — idempotent; старый разрешающий rollback после revoke —
  запрещён.
- Все A01–A23 сохраняются; новые regressions R01–R08 добавляются, не заменяют их.

Новые execution scenarios оформлять отдельными TUC по шаблону; не резервировать
номера наугад. Logs, model fixtures и live evidence — внутри TUC, а этот документ
остаётся implementation plan.

## 11. Обратная связь для человека и агента

Не просить пользователя читать весь IR. Добавить **предлагаемые** Task entrypoints
после регистрации в taskfiles:

- `task security:candidates` — собрать неавторизующие предложения из effective
  topology; не превращать известный порт продукта в разрешённый live listener.
- `task security:explain` — показать «почему flow allow/deny/unknown», matched binding,
  source/object/host provenance, transforms и enforcer/path.
- `task security:check` — schema + semantic + capability gates, без live apply.
- Deploy остаётся явной bundle/approval операцией, не побочным эффектом explain.

Пример карточки feedback:

```text
requirement: SEC-NAT
source: svc-dns.network.publications.dns
binding: svc-dns/dns -> inst.policy.dns_test
witness: client -> direct backend:53, without original publication match
expected: deny
observed: accept in backend model
cause: forward rule lost original destination provenance
fix: preserve publication identity before transform or reject this backend plan
reproducer: negative fixture + backend version + exact plan digest
evidence-level: offline-validated (not live-observed)
```

Ownership/rationale — обязательны для review, но не повод агенту назначать
реальных ответственных или самостоятельно расширять доступ. Candidate может
указывать имеющиеся runtime/ports/security.allowed_from, но human approval
замораживает **разрешённый поток**, а не просто название сервиса.

## 12. Что предлагается утвердить сейчас

| Решение | Рекомендация |
|---|---|
| Mental model | Оставить три понятия, не возвращать primary/service |
| Source collections | Named mappings; normalized arrays только в IR |
| Address | Один typed allocation syntax; числовая арифметика domain |
| Permissions | Bound-only permits; scope-activated mandatory guards |
| Exact endpoint references | В bindings L4/L5, не upward references из L2 |
| Runtime integration | Два compiler-plugin + один validator; existing effective-model owner |
| First qualification | Isolated RouterOS static IPv4 DNAT pilot |
| Deploy | Transaction controller поверх DeployRunner, explicit single resource owner |
| Status | ADR Proposed до явного утверждения; backend readiness отдельно |

После утверждения это должно стать согласованной поправкой ADR 0118/0119,
authoring examples и rule pack **в одном P1 change set**. До этого данный документ
является финальной рекомендацией анализа, а не вторым действующим rulebook.

**Итог:** архитектуру стоит реализовывать, но начинать с точного языка,
наследования, адресного resolver и binding semantics. Главный риск сейчас —
не число политик и не алгоритм сортировки, а расхождение между заявленным
контрактом, реально работающим inheritance и способом безопасно применить его
на конкретном backend.
