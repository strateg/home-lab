# Финальный архитектурный proposal: network intent и enforcement

**Редакция:** 3.4, 2026-09-15 (enforcer/scope, adapter и apply unit; capability satisfaction rev 3.2 сохранён). **Статус:** Accepted: базовый дизайн утверждён 2026-09-10 (gate G0a), поправка AD-11 принята по указанию пользователя 2026-09-11. Это целевая архитектура, не разрешение на реализацию или deployment.
Это совместное design-приложение [ADR 0118](../0118-universal-container-network-model.md)
и [ADR 0119](../0119-firewall-rule-ordering-contract.md), а не третий независимый ADR.
ADR 0118 определяет модель намерений; ADR 0119 — её семантику исполнения.
При конфликте основной ADR имеет приоритет; расхождение требует исправления,
а не выбора удобной версии.

## 1. Предлагаемое решение

Принять **одну декларативную модель**, разделяющую три вопроса:

1. **Attachment:** к какой сети подключена среда исполнения?
2. **Publication:** какой endpoint сервиса представлен клиенту и как доставляется трафик?
3. **Policy binding:** кто вправе инициировать какой поток к этому endpoint?

Существование сети, адреса, маршрута, туннеля, NAT, открытого listener или
состояния established не создаёт разрешения. Разрешение возникает только из
явного, разрешённого к применению binding; delivery и authorization независимы,
но в активной публикации связаны проверяемым контрактом.

Архитектура универсальна по понятиям, а не по обещанию одинаковых возможностей
всех платформ. Неизвестную или неподдерживаемую семантику нельзя заменять
приблизительно похожими правилами.

**За пределами этого proposal:** количество и имена плагинов, файлы кода,
библиотеки, конкретные вызовы API/команды, выбор первого backend,
порядок PR, сроки и rollout. Архитектурное владение общей семантикой на
framework/core уровне и граница Terraform/Ansible, напротив, входят в AD-07/AD-08.

Редакция учитывает [applicability review rev 3](../../docs/reports/2026-09-10-adr0118-0119-rev3-applicability-review.md).
[Разбор замечаний](REV3-APPLICABILITY-RESPONSE.md) отделяет принятые поправки,
проверенные ограничения и неточности рапорта. [Снимок rev 3](history/REV3-ARCHITECTURE-PROPOSAL.md)
сохранён для воспроизводимости; это не отдельный действующий контракт.

## 2. Цели, ограничения и доверие

### Цели

- Однозначная адресация без обязательных двух IP и NAT для каждого workload.
- Один источник сетевых разрешений, сохраняющий смысл при трансформациях.
- Явные ограничения доступа внутри зоны, между зонами и на исходящий трафик.
- Проверяемое отсутствие обхода и работоспособность необходимых потоков.
- Повторное использование Class → Object → Instance без скрытых defaults,
  способных превратить отсутствие селектора в широкий доступ.
- Отзыв разрешений, безопасные переходы и объяснимость для человека.

### Не обещается

Сетевой allow не заменяет TLS, application authentication, permissions сервиса,
защиту от утечки через разрешённое соединение или безопасность общего kernel.
Проверенный план не доказывает соответствие установленного устройства.
Документ не является разрешением на deployment или заявлением о compliance.

Модель угроз включает скомпрометированные endpoints, spoofing, lateral movement,
обходы, stale identity/state, ошибку генерации, внешнее изменение конфигурации и
частичное применение. Trusted computing base: enforcer/kernel, управление,
источник identity, compiler/validator и проверяемые корни доверия.
Компрометация этой базы не закрывается одной политикой firewall.

## 3. Сущности, владельцы и связи — AD-01

| Сущность | Владелец | Смысл и кардинальность |
|---|---|---|
| Network substrate / address domain | L2 | Сеть либо область адресации; VLAN не обязателен. Один substrate может содержать несколько явно различимых domains |
| Attachment | L4 workload | Именованное подключение одного workload к одному substrate; workload имеет 0..N attachments |
| Address allocation | L2 domain | Выделение адреса одному владельцу в определённом routing domain/family |
| Publication | L5 service | Один клиентский endpoint и один backend attachment в базовом профиле; сервис имеет 0..N публикаций |
| Policy template | L2 | Переиспользуемые ограничения потока; сам по себе не создаёт grant |
| Binding | L4/L5 либо L2 network scope | Применение permit template к конкретному subject/target; identity и scope явны |
| Mandatory guard | L2 enforcement scope | Независимое deny-ограничение, действующее на все применимые bindings |
| Route/tunnel constraint | L2 routing/tunnel intent | Разрешённый путь, next-hop/tunnel endpoint, routing domain и поведение при отказе; не permit |
| Interface-scoped NAT | L2 egress transform intent | SNAT/masquerade на именованном L2 interface/tunnel endpoint; не service publication и не grant |
| Tunnel realization binding | L4 workload | Связывает runtime/attachment с L2 tunnel endpoint; обратный join производен |
| Enforcement scope | L2 security matrix | Часть сети/контекстов, за которую отвечает ровно один enforcer. Обратное неверно: один enforcer может держать несколько scopes, в том числе на разных плоскостях исполнения (enforcement planes). Scope имеет собственную идентичность и не адресуется через свой `managed_by_ref` |
| Approval / exception | L7 operations | Право применить конкретный resolved intent/transition; не второй набор firewall rules |
| Plan / evidence | Derived | Производные данные, не редактируемый источник намерений |

```text
L2 domain <--- L4 workload / attachment <--- L5 service / publication
     ^                    |                           |
     |                    +---- policy binding ------+
     |                                  |
L2 scopes / guards <---------------- L2 policy template
     |
one enforcer per scope -> derived enforcement obligations
     |
scope -> enforcer -> resolved adapter -> owned resource set -> apply unit
```

**Поправка 2026-09-15 (rev 3.3 → 3.4), синхронизация с [ADR 0119 D1.1](../0119-firewall-rule-ordering-contract.md).**
Нижняя строка схемы — не новые авторские сущности, а различения внутри уже
существующих C→O→I и производных контрактов; авторская форма ими не растёт.

- **Enforcer** — устройство, исполняющее правила. Идентичность стабильна и на неё
  ссылаются scopes; сам enforcer scopes не перечисляет.
- **Scope** — намерение с собственной идентичностью, ровно одним enforcer, плоскостью исполнения и
  ограниченным набором контекстов. Ключевать scope его enforcer'ом нельзя: связь
  один-ко-многим, и индекс, хранящий по одной записи на enforcer, теряет scope.
- **Resolved adapter** — версионированный контракт рендеринга и реализации, ровно
  один на целевой контекст; ноль означает неподдержанный enforcer, больше одного —
  блокирующая неоднозначность. Идентичность и версия закрепляются до validate и
  входят в проверяемую идентичность плана.
- **Owned resource set** и **apply unit** — какие ресурсы принадлежат scope, кто их
  единственный writer, где записано их состояние и что применяется, откатывается и
  восстанавливается вместе.

Разделение плоскостей исполнения на одном устройстве семантическое. Оно не доказывает изоляцию
общих chains, hooks, address sets или ресурсов: композиция между scopes одного
enforcer проверяется, а не предполагается.

L5 binding может ссылаться на точный L4 source attachment; L4 и L5 ссылаются
на L2 policy. L2 policies не ссылаются вверх на сервисы/workloads: они содержат
L2 selectors либо типизированные параметры binding. Reverse join производен.
Ссылка scope на L1 enforcer сохраняет действующий контракт managed_by_ref.
Zone membership и trust level классифицируют, но не авторизуют.

Class задаёт допустимые данные, Object — reusable intent/defaults, Instance —
конкретное размещение и связи. Embedded records не становятся самостоятельной
параллельной topology. Их identity: project + owning instance + record kind +
local key; неоднозначная склейка строк через точку не используется.

## 4. Авторская форма и наследование — AD-02

**Решение:** attachments, publications и bindings — именованные mappings.
Порядок ключей не задаёт порядок исполнения. В нормализованном представлении
допустимы канонически упорядоченные коллекции.

- Local key — identity record; дублировать его полем id не нужно.
- Вложенные mappings объединяются по правилам C→O→I; списки значений заменяются
  целиком, а не неявно расширяются.
- Удаление override восстанавливает inherited value, а не удаляет record.
- `enabled: false` явно отключает inherited record. Null не означает удаление,
  wildcard или восстановление default.
- Ссылка на disabled/missing attachment — ошибка. Отключение publication
  исключает её binding из нового desired intent.
- Rename local key означает удаление старой identity и создание новой.
  Сохранение адресов/state при rename не предполагается автоматически.
- Неизвестные поля, duplicate keys, mixed versions и derived overrides отвергаются.
- Schema version обязателен в effective source; он может быть унаследован.
  Version модели не равен версии модуля.

**Контекст имён.** ADR 0088 регулирует manifest/capability metadata и не
регистрирует local keys embedded records. Local keys определяются class schema
с baseline-формой `[A-Za-z_][A-Za-z0-9_]*`, case-sensitive: без точки, дефиса
и `@`. Это даёт однозначные paths, совместимые с текущим `@on`.
Ограничение не распространяется на существующие instance IDs с дефисами.

`network.schema_version` сохраняется как domain-data field. Семантический
идентификатор его версии — **network_intent_version**, не manifest token
`schema_version -> @version`. Для policy payload используется тот же domain
version contract в отдельном network-policy context. Global remapping запрещён.
G1 должен зарегистрировать context-scoped domain keys/relations; текущий
реестр этих contexts ещё не содержит. Это дополнение схемы, не переименование
`@version` и не утверждение о работающей регистрации.

Reference contract должен описывать каждый typed collection edge и сохранять
конкретный local key в диагностике. Mapping wildcard обозначает обход записей,
не wildcard network selector. Семантика refs определяется единым declarative
layer/schema contract, не расходящимися таблицами в нескольких validators.

Изменение Object может изменить много effective instances. Review показывает
всех затронутых владельцев, endpoints и grants; approval не переносится
автоматически со старого resolved intent на новый.

## 5. Подключение, адреса и маршруты — AD-03

Attachment определяет substrate, interface identity, allocation intent и
выбор маршрута по умолчанию. Механизм подключения ограничен capabilities среды;
названия продуктов не являются проверкой возможностей.

Static allocation задаётся единообразно: `address: {allocation: static, host: N}`.
N — числовой offset от network address, не последний octet строки.
L2 domain владеет prefix, gateway, family, routing domain, reservations и pools.
Effective address/gateway вычисляются; gateway не обязан иметь offset 1.
Literal address допустим как L2 allocation input, не как второй override
вычисленного адреса workload. Поле attachment.host вне address не допускается.

При нескольких domains выбор должен быть явным. При одном — однозначное
выведение допустимо. В одном family/routing domain допускается одна явно
выбранная default route; multipath требует отдельного профиля.
Backend gateway никогда не выводится из frontend публикации.

Один адрес имеет одного allocation owner. Несколько публикаций могут ссылаться
на **одно и то же** выделение VIP, если listener tuples совместимы.
Они не создают несколько независимых allocations одинакового IP.
Совпадение domain/адреса с разными владельцами — конфликт, а не shared VIP.
Shared/HA ownership требует отдельного контракта, не списка owners «на всякий случай».

Статические reservations и модель проверяются отдельно от live leases/ARP.
Отсутствие конфликта в YAML не доказывает свободу адреса на устройстве.
Маршрут определяет путь, но не grant; запрещённый fallback при потере туннеля
должен быть явно представлен route constraint, не неявной надеждой на firewall.

### Route/tunnel intent и NAT вне публикаций

L2 route constraint задаёт bounded source/destination selectors, routing domain,
целевой L2 next-hop/interface/tunnel endpoint, допустимый fallback и failure action.
Туннель L2 владеет network/peer endpoint semantics; L4 realization binding
ссылается вниз на него и на конкретный attachment. L2 не содержит container_ref.
Разрешение endpoint и обратные связи производятся из этих downward declarations.

Для текущих AWG-политик целевая декомпозиция такова (не миграция данных):
- dedicated /30 — L2 address domain + L4 attachment;
- WG interface/peer — L2 tunnel intent; proxy runtime — L4 realization;
- VLAN route — L2 route constraint, связанный с L2 tunnel;
- proxy→remote VPN endpoint — отдельный bounded egress grant;
- source VLAN→tunnel — отдельный transit grant с route constraint;
- kill-switch — обязательный deny для запрещённого direct-WAN path,
  действующий и при down/unknown состоянии tunnel;
- interface SNAT/masquerade — отдельный L2 egress transform, ограниченный
  source domain, egress endpoint и переводом адреса, не публикация.

Provider interface names, marks и priority становятся производными backend
деталями; авторами задаются путь/ограничения, не порядок mangle/filter rules.
Priority с бизнес-смыслом выбора маршрута требует явной семантики, а не переноса
старого числа в firewall ordering. Неоднозначный legacy смысл блокирует mapping.

Route constraint сам не разрешает ни data plane, ни tunnel-control traffic.
NAT не расширяет grant; original/current tuples и reverse path сохраняются.
Динамический адрес masquerade, proxy identity и nested transforms требуют
квалифицированного расширения AD-09: наличие владельца не означает поддержку.

## 6. Публикация и delivery — AD-04

Publication принадлежит L5 service и выбирает его runtime attachment.
В базовом профиле workload выводится из service runtime target; автор выбирает
attachment, не задаёт независимо второй противоречащий runtime target.

Три механизма сохраняют одинаковую модель permissions:

| Механизм | Frontend | Обязательство |
|---|---|---|
| direct | Адрес существующего attachment | Не выделять второй адрес и не создавать NAT |
| dnat | Явно выделенный frontend отдельного owner | Сохранить различимость original endpoint после transform |
| host_publish | Реальный bind endpoint host | Подтвердить ownership и охват host-local/direct paths |

У publication есть точные protocol/frontend ports/backend ports и одно
явное permit binding. Несколько source selectors одного binding образуют
явное множество, а не порядок приоритетов. Несколько разных независимых
разрешений могут использовать раздельные records с совместимым delivery;
эквивалентный delivery объединяется только с сохранением provenance.
Неоднозначные или конфликтующие frontend→backend mappings запрещены.

Ports permit policy относятся к **original, client-facing tuple**. Backend port mapping
— transform publication; совпадение чисел frontend/backend не предполагается.
Ограничения backend/listener проверяются отдельно; их нельзя ошибочно пересечь
с frontend port в одной системе координат.

Delivery без разрешённого binding может существовать только как неактивный
candidate/staged объект. Активная publication обязана иметь валидный binding.
При direct publication физическая достижимость attachment не исчезает после
удаления публикации: исчезает только её permission и отдельные delivery resources,
если они больше никем не используются.

## 7. Policy, binding и разрешённый поток — AD-05

В базовом профиле существуют ровно два режима:

- `effect: permit, activation: binding_only`: неактивный без binding template;
- `effect: deny, activation: scope_guard`: обязательный запрет, активированный
  явным scope reference и независимый от публикаций.

Другие сочетания не имеют неявного смысла и не допускаются базовым профилем.
Template задаёт direction, source/destination constraints, typed protocol/ports,
owner/rationale. Направление ingress/egress относится к subject binding,
а transit — к явной паре network endpoints; оно не выбирает backend chain.

Binding выбирает:
- source: L2 network/zone/allocation либо точный L4 attachment через L4/L5 owner;
- destination: publication endpoint, attachment endpoint или явный L2 endpoint;
- policy template и дополнительные сужающие ограничения.

L4 bindings предназначены для non-service infrastructure ingress/egress;
L2 network bindings — для явно разрешённого network-to-network/transit трафика.
Они видны в общем intent и проходят такой же review, а не становятся fallback
для отсутствующей L5 policy. App→DB обычно задаётся на DB publication с source
app attachment; копировать permit на каждый промежуточный enforcer не требуется.

Существующий `clients.service_ref` служит evidence для migration candidate,
а не новым разрешающим L5→L5 selector. Candidate разрешает service.runtime.target
в конкретный L4 attachment с явным выбором при нескольких attachments, фиксирует
service provenance и проходит review. Неоднозначный target — ошибка; не выбирать
первый attachment и не разрешать все его адреса. L5 application identity нельзя
приписать общему IP нескольких сервисов; при такой зависимости нужна отдельная
application-identity qualification.

Policy placeholder `{binding: source}` или `{binding: destination}` — параметр,
не wildcard. После связывания остаётся непустое bounded множество.
Missing/empty selector — ошибка. Явный широкий selector требует отдельного review.
Guard имеет concrete L2 selectors без незаполненных binding parameters и явную
систему координат match: original либо current в названном execution context.
Запрет обращения к исходному frontend и запрет доставки в backend subnet —
разные predicates; неявная подмена одного другим запрещена. Permit binding
всегда описывает original intent, а все guards проверяются на применимых views
его полного пути.

IP address не является аутентифицированной workload identity: необходима
проверяемая ingress provenance/anti-spoofing либо более сильный источник identity.

Для epoch e, в объявленной области U:

```text
P = union(resolved, approved bound permits)
D = union(applicable mandatory guards)
C = identity, binding, validity and path constraints
A = (P intersect C) minus D
Q subseteq A = required legitimate flows
```

Конфликт permit с mandatory deny **отклоняет candidate с witness**.
Silent trimming, «более специфичный allow» и приоритет производителя запрещены.
Default deny означает отсутствие permit; это не mandatory deny над всем U.

Пересечение policy с publication может сузить reusable template без конфликта,
но пустое пересечение делает binding ошибочным. Review показывает effective
множество, не только template name. Независимый network binding, разрешающий
прямой backend, не исчезает от удаления publication; такой доступ должен быть
явным и объяснимым. «Публикация закрыта» не значит «workload полностью изолирован».

## 8. Жизненный цикл — AD-06

```text
source intent -> resolved candidate -> reviewed semantic revision
-> capability-qualified plan -> authorized transition
-> observed active revision -> revoked / superseded
```

Это состояния предметной области, не новые compiler stages.

- Создание template не открывает доступ.
- Binding становится grant только после разрешения всех refs/constraints и
  требуемого approval; наличие owner/rationale не является approval.
- Disable/delete publication удаляет её bound grant из нового desired intent.
  Reusable template и grants других bindings сохраняются.
- Удаление используемого template/attachment/allocation блокируется до
  согласованного изменения зависимых records.
- Удаление guard может расширить A; оно требует review расширения доступа.
  Недоступный enforcer или stale identity не отключают guard молча.
- Revocation actual state завершается в пределах утверждённого deadline.
  Редактирование YAML само по себе не завершает live revocation.
- Изменение default, selector, identity snapshot или route, влияющее на смысл,
  меняет semantic revision и требует нового соответствующего evidence/approval.

Required flows Q включают критичные management и служебные зависимости с
объявленными prerequisites и availability objectives. Новое разрешение не
создаётся автоматически потому, что без него не проходит health check.

## 9. Enforcement, путь и порядок — AD-07

Один логический владелец производного плана определяет authorization semantics;
конкретные enforcers исполняют свои проекции. Общая, не зависящая от платформы
семантика принадлежит **framework/core**, а не object-модулю MikroTik или другой
платформы. Backend modules владеют platform capabilities и lowering/rendering
валидированного intent/plan; они не пересчитывают zone membership, grants или
policy conflicts независимо. Backend-specific requirements публикуются явно
до validation; rendering не вводит новую authorization semantics.
Это граница ответственности, **не четырёхуровневый runtime ACL**: ADR 0086,
stage affinity и manifest exchange contracts сохраняются.
Число модулей, процессов и плагинов по-прежнему не фиксируется. Один scope имеет одного enforcer; устройство может
иметь несколько непересекающихся contexts, но у каждого ресурса один writer.

План охватывает весь применимый путь: исходный endpoint, routing/NAT,
host/bridge/forward/local hooks, state, reverse traffic и dispatch.
Для каждого обходного пути нужно enforcement или доказанное disablement.
Неизвестный путь запрещает заявление о полной strict-защите данного scope.

Original и transformed tuples различны. Два разных original flows с разными
permissions не должны стать неразличимыми на единственном authorization gate.
Нужны сохранённая provenance, более ранний gate либо отказ от candidate.

Порядок выводится из семантических зависимостей, не из trust level,
specificity score, имени генератора или числового priority автора.
При равноправных узлах используется полный канонический semantic key;
конфликт не разрешается tie-break. Циклы и неизвестные match/effect relations —
ошибки. Все исполнения завершаются допустимым verdict за ограниченное число шагов.

Terminal default deny обязателен на конце каждого соответствующего
**managed executable scope**. Это не требование последнего resource во всём
устройстве. Отсутствие обходящих earlier accepts/dispatch и соседних chains
доказывается отдельно; размещение drop в недостижимой цепочке ничего не доказывает.
Legacy final-drop obligation не ослабляется.

## 10. Применение, владение и evidence — AD-08

Design фиксирует safety contract **и архитектурную границу выполнения**.
Конкретные команды/SDK не выбираются, но ответственность инструментов не
оставляется произвольной:

- Вход — immutable plan/bundle, привязанный к resolved intent и approval.
- Preflight подтверждает expected current revision, ownership, versions,
  freshness, адреса и recovery prerequisites.
- Переход имеет явный time-indexed authorization envelope; старые и новые
  permissions не объединяются автоматически.
- Каждый промежуточный state остаётся внутри envelope, включая retry,
  reboot, partial failure и удаление временных guards.
- Старые sessions отзываются в пределах deadline; related/control traffic
  имеет bounded semantics и не становится универсальным ранним allow.
- Rollback допустим только к revision, ещё разрешённой текущим epoch.
- Unexpected writer/drift или недостоверный read-back блокируют success.
- Успех требует semantic observed state и positive/negative path evidence.
  All-drop не удовлетворяет availability.

Владельцы различаются: author intent, approver, enforcer scope owner и resource
writer. Роли могут принадлежать одному оператору, но не смешиваются в данных.
Transfer writer ownership — явный guarded переход, не два конкурирующих apply.
### Архитектурная граница инструментов

Сохраняется действующая граница: Terraform — provisioning/infrastructure,
Ansible — OS/service/runtime configuration. Для RouterOS действует более
конкретный [ADR 0057](../0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md):
Terraform остаётся post-bootstrap владельцем desired configuration, включая
управляемые interface/address/route/NAT/filter ресурсы. Новый controller или
Ansible wrapper не получает скрытого права стать вторым владельцем этих ресурсов.

| Ответственность | Владелец по архитектуре |
|---|---|
| Backend-neutral intent/authorization/ordering obligations | Framework/core |
| Desired инфраструктура и RouterOS post-bootstrap configuration | Terraform-owned resource domain |
| OS/service/runtime configuration вне Terraform-owned domain | Ansible-owned resource domain |
| Проверка bundle/approval, sequencing, read-back и evidence | Deploy orchestration через существующую runner boundary |
| Session invalidation и временные guards | Явные transition operations, делегированные владельцем соответствующего resource domain |

Read-only observation не передаёт resource ownership. Изменяющая операция
временного guard не получает исключения из single-writer: она входит в
утверждённый plan, имеет владельца, duration и reconciliation contract с его
desired state. Нельзя спрятать независимый API writer под названием wrapper.

**Поправка 2026-09-15 (rev 3.3 → 3.4).** Таблица выше распределяет владение по
инструментам. Она не говорит, чем ограничена **единица применения**, и без этого
«один writer на ресурс» проверяется только на словах. Разделяются:

| Понятие | Что фиксирует |
|---|---|
| Connection binding | Endpoint, селектор целей и ссылка на credentials, которыми инструмент достигает цели |
| Resource identity и writer | Какие конкретные ресурсы принадлежат scope и кто их единственный writer |
| State namespace | Где записано применённое состояние этих ресурсов |
| Apply / transaction unit | Что применяется, откатывается и восстанавливается вместе, и каков радиус отказа |

Требуется однозначный выбор цели и единственный writer на ресурс. Уникальные
адреса и credentials **не требуются**: несколько явно адресуемых целей могут
законно пользоваться одним management endpoint и одним принципалом, а разные
каталоги сами по себе не доказывают ни разных ресурсов, ни независимых отказов.
Совместное использование connection binding, state namespace или apply unit
допустимо там, где связанность объявлена, а её reconciliation и recovery
проверены. Раздельная атрибуция scope не выдаётся за независимый failure domain.

Замена Terraform на другого владельца RouterOS rules или перенос границы
Terraform/Ansible — **отдельное архитектурное решение** с явной поправкой ADR 0057
и ADR 0119, не свобода implementation-фазы. Если текущий владелец не может
выполнить transition guarantees, strict qualification блокируется; это не
разрешение обойти архитектуру. Дизайн фиксирует требование, но не доказывает
возможность конкретного Terraform provider.

OOB/recovery prerequisite моделируется L7 recovery contract со ссылками на
L1/L2 management path, независимый от изменяемого failure domain, и проверкой
доступности до изменения. UI в management zone через тот же router не является
доказательством OOB. Отсутствующий путь явно блокирует опасный переход; proposal
не объявляет, что такой путь уже создан.

Semantic digest включает все влияющие на authorization normalized inputs и
их версии. Evidence связывается с exact plan, assumptions, validator/backend
versions, временем и сроком актуальности. Time metadata не меняет смысл source
произвольно; истечение freshness инвалидирует применимость evidence.

## 11. Границы базового профиля и расширения — AD-09

| Уровень | Входит | Не допускается без отдельного qualification contract |
|---|---|---|
| Общая модель | Multiple attachments, domains, publication/binding/guard, route/tunnel constraints, interface NAT, original/current tuple, full path | Неявные grants и unknown-as-allow никогда |
| Базовый strict profile | Static IPv4 allocations, один runtime backend на publication, direct/dnat/host_publish как моделируемые механизмы, bounded typed flows | Непроверенный механизм конкретного backend |
| Расширения | Имена и обязанности совместимы с общей моделью | Dynamic identity/allocations, IPv6, shared-stack isolation, HA/VIP failover, multipath, nested transforms, proxy identity |

Таблица не объявляет IPv4-only сеть безопасной автоматически. IPv6/offload/bridge
обходы в выбранном scope должны быть проверяемо отключены либо охвачены
поддержанным расширением. Unsupported workload не «понижается» молча до legacy.

Новая платформа получает capability contract с точными версиями/режимами,
domain/path/state semantics и доказательствами. Архитектура не выбирает
RouterOS первым и не объявляет Proxmox/Docker готовыми.

## 12. Legacy boundary — AD-10

ADR 0110/0111 сохраняют действующее legacy-поведение. Strict — явно выбранный
versioned profile scope; trust-zone classification не конвертируется в grants.

R1/R2/R3 implicit allows не переносятся. R6 permits/denies дают только reviewed
candidates. Удаление legacy ограничения при переходе не разрешается «потерей»
записи: migration review должен явно показать каждый исчезающий запрет/permit.
Новый scope не активируется до approval полного изменения authorized set.

**Решение для существующего routing/VPN plane:** сохранить его явно versioned
legacy scope до отдельной extension qualification, не включать AWG/proxy chains
в static baseline по умолчанию. Их целевые владельцы уже определены AD-01/AD-03;
это отложенная поддержка, не отсутствующая модель. Шесть legacy L2 container_ref
не легализуются в strict: целевая модель использует L4→L2 realization и reverse join.
Инвентарь: четыре в inst.routing_policy.* и два внутри inst.vlan.vpn_amnezia/vpn_sweden;
вторые весомее, поскольку upward-ссылка находится внутри самого address domain.

Логическая метка отдельного scope не изолирует общие forward/mangle/NAT chains.
Для совместного enforcer обязательны inventory всех rules/dispatch/transforms,
единый resource writer и доказанная композиция paths/order/state. Если legacy
VPN rules могут повлиять на strict flow, гарантия не заявляется и shared-boundary
activation блокируется до композиции либо реального разделения. Рекомендация
«выбрать не-VPN сервис» сама по себе не снимает этот риск.

Disabled/staged intents не исчезают из inventory: в частности, Proxmox matrix
и её overrides остаются видимыми как planned/unqualified requirements, не active
grants. Для intra-zone flows без подходящего enforcer результат — unsupported,
не выдуманное deny enforcement и не потеря требований.

Zone migration различает L2 domain declaration и consumer override. Авторитетный
trust_zone_ref домена сохраняется; зона каждого workload attachment выводится
из его domain, а frontend публикации имеет собственный domain. Для multi-attachment
workload нет единственной автоматически выбранной зоны. L5 declaration с другим
смыслом сохраняется как отдельно названная application classification, если это
подтверждено review, но не как override network authorization zone. Конфликты
показываются с обоими источниками; массовое удаление всех trust_zone_ref запрещено.

На одном общем managed boundary legacy и strict не смешиваются без доказанной
композиции. Разные scopes могут сосуществовать, но гарантия strict для потока
требует проверки всего его пути. Нет автоматической миграции адресов, ролей,
VLANs или выключенных enforcers ради соответствия рисунку.

## 12A. Capabilities как проверяемый контракт — AD-11

**Решение:** использовать capabilities не только для выбора backend, а для
проверки выполнимости обязательств intent. Нормативные подробности —
[Capability satisfaction contract](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md).

Разделяются четыре вопроса: что нужно; что заявлено компонентом; что применимо
в конкретной конфигурации; что доказано на нужном уровне evidence.
Declared capability ≠ effective support ≠ evidence ≠ разрешение.

Три контракта входят в существующие intent/plan/evidence:
1. **Requirements:** core выводит их из attachments/publications/bindings,
   route constraints и profile, сохраняя source/obligation provenance.
2. **Offers:** versioned device/runtime/adapter contracts описывают context,
   predicates/transforms/state semantics, ограничения и prerequisites.
3. **Resolution evidence:** связывает requirement со strategy, offers, покрытием
   paths/states, проверенными условиями, evidence и сроком применимости.

Это не три новых обязательных plugin и не четвёртая authored topology-сущность.
Effective capability — производный join, не параллельная база. ADR 0106 остаётся
основой классификации; catalog/packs и derivation ownership переиспользуются.
На publication не появляется второй ручной список inferred requirements.

SEC-CAP проверяет **композицию по каждому применимому пути/состоянию**:
device/runtime + adapter/version + разрешённые owner operations + context.
Сумма флагов разных устройств не доказывает end-to-end поддержку. Все выбранные
strategies должны быть совместимы в одном плане, включая общую ёмкость ресурсов,
режимы конфигурации и владение; отдельные несовместимые witnesses не складываются.
DNAT требует сохранения original authorization; workload selector — достоверной
identity/provenance; tunnel-only egress — проверенного fail-closed fallback.
safe_mode/state_restore не доказывают допустимость возврата отозванного grant.

Возможны bounded declarative alternatives: original tuple match, более ранний
полностью покрывающий gate либо сохранённая connection identity. Для доказанно
эквивалентных вариантов выбор канонический и детерминированный. Изменение topology,
security boundary, owner или transition envelope требует review; silent fallback
в host-network/legacy либо расширение selector запрещены.

Результат — satisfied, unsatisfied или unverified **для указанного claim/gate**.
Отсутствие live evidence не запрещает offline candidate, но блокирует activation;
доказанная несовместимость блокирует соответствующий executable candidate.
Неизвестные/пустые inventories и self-attestation не дают vacuous pass.
SEC-CAP не заменяет SEC-AUTH/AVAIL/PATH/NAT/STATE/TRANSITION и не расширяет P/A.

Offer/contract versions, strategy и semantic conditions входят в plan/bundle
binding. Evidence привязано к subject, digests, scope и freshness. Изменение версии,
режима, path или owner инвалидирует затронутое resolution; live timestamps не
делают semantic plan недетерминированным. Наблюдение не утверждает новые grants.
Новые runtime/schema/catalog поля в этой редакции не реализованы.

**Уточнения AD-11 (rev 3.2a).** Три пункта AD-11 недоопределены и потому
непроверяемы в исходной формулировке; они уточняются, а не отменяются.

1. Детерминизм плана при живом evidence возможен только при разделении offer на
   semantic core и evidence annex: rev 3.2 одновременно требует hash-binding
   содержимого offer и относит qualification evidence references к этому
   содержимому. Нормативное разделение — §4.1 [capability contract](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md).
2. `complete(R_g, Omega_g)` не проверяемо, пока Omega_g определяется самим
   резолвером. Нижняя граница Omega_g привязана к списку путей D6 (L2, routed,
   host INPUT/OUTPUT, tunnel, direct backend, IPv6, offload/acceleration).
3. Три статуса satisfied/unsatisfied/unverified сосуществуют с уже принятым
   verdict `unsupported` для потока. Отображение одностороннее: unsatisfied и
   unverified могут давать `unsupported` для затронутого потока, но `unsupported`
   никогда не превращает unverified в scope decision и не читается как «supported».

Кроме того, словарь capability закрыт и доходит до runtime только идентификаторами,
поэтому известные дыры enforcement (FastTrack/offload, hook DOCKER-USER против
nftables, IPv6, Proxmox STUB, отсутствие guard у девяти LXC, приём `untracked`)
сегодня **невыразимы** как требования. Это долг словаря W03/G1, а не доказанное
отсутствие пути; до его закрытия соответствующее требование — unverified.

## 13. Проверка архитектуры на сценариях

Verdicts ниже предполагают отсутствие иных независимых grants и конфликтов.

| Сценарий | Модель | Ожидаемый смысл |
|---|---|---|
| LXC имеет IP, publication отсутствует | Один attachment | Связность описана; permissions не созданы |
| Прямой Grafana endpoint | direct publication + management binding | Без второго IP/NAT; остальные источники не получают allow |
| DNS на отдельном frontend | backend attachment + dnat publication TCP/UDP 53 | Разрешён DNS через frontend; прямой backend не разрешён этим binding |
| DNS и UI одного приложения | Разные publications/bindings; возможно общий allocation | DNS grant не даёт доступ к UI; общий backend не объединяет права |
| App→DB | DB publication, source app attachment | Одно логическое разрешение; gates по всему пути производны |
| DNS/NTP исходящий от workload | L4 egress binding | Никакого общего allow Internet или outbound-by-default |
| Запрет guest→management | Scope guard | Более узкий permit не обходит guard; candidate конфликтует |
| Publication отключена | Её grant отозван | Другие bindings остаются; sessions обязаны истечь/отозваться по deadline |
| Shared host stack | Общий namespace отражён явно | Не обещать различение workloads, если enforcer его не обеспечивает |
| Tunnel потерян | Route constraints и path obligations | Запрещённый WAN fallback не становится разрешённым |
| VIP внутри DHCP pool | Allocation ownership + live preflight | Нельзя объявить deployment-ready по одному YAML |
| Часть устройств применила новый plan | Approved transition envelope | Нет несанкционированного промежуточного расширения доступа |

[Authoring examples](AUTHORING-EXAMPLES.md) иллюстрируют только source shape.
[Formal contract](../0119-analysis/FORMAL-CONTRACT.md) задаёт обязательства
SEC-AUTH/AVAIL/PATH/NAT/ORDER/STATE/TRANSITION.

## 14. Альтернативы и принятые компромиссы

| Альтернатива | Решение и цена |
|---|---|
| Universal primary/service, два IP каждому workload | Отказ: роли подключения и публикации различны; простой direct case остаётся простым |
| Policy прямо внутри каждой publication без reuse | Отказ: template переиспользуем, binding локален; цена — явная ссылка и provenance |
| Автоактивация всех L2 permit templates | Отказ: создаёт скрытый второй grant вне publication scope |
| Permissions только в L5 | Отказ: нужны L4 infrastructure и L2 transit bindings, но с той же алгеброй |
| List-of-records с частичными overrides | Named mappings: стабильная identity и ясная семантика merge; цена — строгие local keys |
| Silent trimming permit по deny | Отказ в базовом профиле: ошибка автора должна быть видна |
| Один унифицированный набор firewall primitives для всех платформ | Общий intent, capability-qualified lowering; цена — раздельные доказательства |
| Все платформы и dynamic discovery сразу | Bounded profile с явными расширениями; цена — часть topology пока остаётся legacy |
| Всегда закрыть всё при ошибке и считать успехом | Отказ: safety и availability — отдельные обязательства |
| Утвердить архитектуру только после production тестов | Отказ: design approval, implementation verification и deployment authorization различны |

Малый authoring surface достигается defaults и reuse, не пропуском security intent.
Бюджет измеряет authored paths/files/refs и отдельно navigation по inherited
источникам; уменьшение видимого YAML не доказательство меньшей сложности.
Численные targets migration plan сохраняются как проверяемые цели, но прежние
array-based подсчёты не являются доказательством для rev 3.

## 15. Завершение архитектурной фазы

AD-01..AD-10 **утверждены** 2026-09-10 как согласованный пакет ADR 0118/0119
rev 3.1 (gate G0a). Перед утверждением исправлены два инвентарных дефекта:
шесть legacy L2 `container_ref` вместо четырёх и девять файлов с авторским
`routing_mark`; добавлен сценарий приёмки A24. Gate G0b (именованные владельцы
HA-01..HA-10 и tailoring record) **не закрыт**; G1-G8 открыты; ни один backend
не квалифицирован; deployment не разрешён.

Поправка rev 3.2 добавляет AD-11/SEC-CAP и acceptance A25-A32 по указанию
пользователя 2026-09-11. Результаты независимых review rev 3.1 не выдаются за
review этой поправки. G0b/G1-G8 остаются открыты; новая поддержка не заявляется.

Design review rev 3.1 подтвердил:
- понятия, кардинальности, владельцев и направления refs;
- source identity/merge/disable, context-scoped keys и allocation ownership;
- binding/guard algebra, coordinates портов и lifecycle revoke;
- threat model, full-path coverage, bounded profile и отказ при unknown;
- framework/core authority, Terraform/Ansible ownership и transition/evidence contract;
- routing/VPN legacy composition boundary, visibility planned intents и zone migration;
- смысл приведённых сценариев и принятые компромиссы.

Не требуется выбирать количество плагинов, backend SDK, исполнителя команд,
файлы, сроки или первый pilot, чтобы принять эти архитектурные решения.
Но framework/core ownership и существующая Terraform/Ansible граница являются
частью утверждаемого дизайна и не могут быть изменены как implementation detail.
Но review может отвергнуть/уточнить любой AD; финальность proposal не означает
отсутствия права на замечания.

После явного архитектурного approval отдельно разрабатывается implementation
proposal, согласующий способы реализации с этими решениями. Дефекты текущего
resolver/merge/projection из [предыдущего анализа](FINAL-PROPOSAL-EVIDENCE-2026-09-10.md)
— ограничения существующей реализации, не основания привязывать новый дизайн
к её внутреннему устройству.

[Предыдущий implementation proposal](FINAL-IMPLEMENTATION-PROPOSAL.md) остаётся
историческим исследованием вариантов. Его выбор плагинов, backend и PR sequence
**не принят** и не входит в предмет текущего архитектурного утверждения.
