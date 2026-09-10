# Совместное ревью ADR 0118 и ADR 0119: модель сети, авторизация и математика порядка правил

**Дата:** 2026-09-09\
**Вердикт:** **Request Changes для согласованного принятия ADR 0118/0119.** Исправления модели полезны, но предложенный порядок правил пока не доказывает её безопасность.\
**Проверенная ревизия:** `ce8018754db0bd28d67568a8f7fb755236c9d8a9`.\
**Репозиторий:** `/home/nixos/workspaces/home-lab`, WSL NixOS; Windows-доступ: `\\wsl.localhost\NixOS\home\nixos\workspaces\home-lab`.\
**Характер работы:** анализ документов, исходников, свежего effective JSON, локальные проверки и математические контрпримеры. ADR, код и топология не изменялись.

## 1. Краткий вывод

ADR 0118 правильно движется от смешанного `network.primary/service` к разделению **подключения workload → публикации сервиса → разрешающей политики**. Добавлены владение VIP, явные defaults, исключение Kubernetes из v1 и негативные acceptance-сценарии.

Однако ADR 0119 пока смешивает три разных задачи:

1. **Авторизацию:** какие потоки вообще допустимы.
2. **Компиляцию:** как выразить эти потоки правилами конкретного enforcer.
3. **Размещение:** в какой последовательности правила реально исполняются.

Правильный порядок не может исправить чрезмерное разрешение. DNAT, высокий trust level, established-состояние или более специфичный match сами по себе не должны предоставлять право доступа.

Обнаружены четыре воспроизводимых математических дефекта:

- граф D7 допускает нарушение порядка классов: **6 из 15** допустимых сортировок минимального примера;
- `hash(id) mod 100` не обеспечивает I2 и допускает коллизии; ранжирование D7 дополнительно переполняет диапазоны;
- сумма «специфичности» не соответствует включению множеств пакетов;
- I3 «No Leak» выполняется для `accept everything` и потому **не является свойством отсутствия неразрешённого доступа**.

Для строгого профиля рекомендую не добавлять новые приоритеты поверх старой схемы, а ввести **единый версионированный Security Intent IR**, семантику обязательных запретов и явных разрешений, проверку сохранения авторизации после NAT, доказательство покрытия всех путей и проверку фактически установленного порядка.

**Текущее состояние проекта не равно реализации этих предложений.** После предыдущего ревью изменены ADR и документация, но проверенные compiler/template/topology ещё используют прежнюю сетевую модель.

## 2. Что означает «по военным стандартам»

Единого универсального «самого строгого военного стандарта» нет. Для реальной системы требуется определить юрисдикцию, классификацию данных, миссию, допустимый ущерб, организационный baseline, оборудование, криптографию и процедуру допуска.

Здесь используется **предлагаемый инженерный профиль повышенной защищённости**, основанный на открытых документах:

| Основание | Принцип, применённый в ревью |
|---|---|
| [DoD Zero Trust Strategy, 2022](https://dodcio.defense.gov/Portals/0/Documents/Library/DoD-ZTStrategy.pdf) | Zero Trust рассматривается как архитектура, а не отдельный firewall |
| [NSA Zero Trust Implementation Guidelines](https://www.nsa.gov/Cybersecurity/ZIG/) | Assume breach, гранулярный доступ, непрерывная проверка; на официальном ресурсе доступны материалы Discovery, Phase One и Phase Two |
| [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final) | Нельзя автоматически доверять субъекту только из-за его сетевого расположения |
| [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final) | Контроль потоков, default deny, безопасное поведение при отказе; официальная страница учитывает release 5.2.0 от 2025-08-27 |
| [DISA SRG/STIG library](https://www.cyber.mil/stigs/compilations/) | Нужен отдельный применимый checklist для продукта, версии и условий эксплуатации |

Это **не аудит соответствия DISA, не ATO, не сертификация для обработки секретных сведений**. Полный актуальный product-specific Firewall SRG/STIG checklist в этой работе не выгружался; конкретные STIG V-ID и заявления о прохождении требований не присваиваются.

Предварительное сопоставление с контролями: AC-4 — управление информационными потоками; SC-7(5) — deny by default / allow by exception; SC-7(12) — защита на хостах; SC-7(18) — fail secure; SC-24 — известное безопасное состояние при отказе. Это ориентиры для tailoring, не утверждение, что каждый контроль обязателен для home-lab. [Каталог NIST SP 800-53](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf).

### 2.1. Принятая модель угроз

Рассматриваются: компрометация IoT/guest/workload; lateral movement; обход через прямой backend, L2, IPv6 или VPN; ошибка генератора; конфликт политик; частичное применение конфигурации; устаревшая conntrack-сессия; ручной drift; подмена входных артефактов; отказ enforcer и перегрузка журналирования.

Предполагается, что доверенная база вычислений и криптографические ключи отдельно контролируются. Компрометацию ядра маршрутизатора, supply-chain производителя, физические атаки и скрытые каналы один firewall DSL не устраняет. Контейнер на маршрутизаторе нельзя объявлять независимой доверительной границей только из-за наличия veth.

## 3. Доказательства и границы проверки

### 3.1. Источники проекта

- [ADR 0118](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/adr/0118-universal-container-network-model.md): D1–D14 и дополнения D15–D21.
- [ADR 0119](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/adr/0119-firewall-rule-ordering-contract.md): D1–D9.
- [Security matrix compiler](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/security_matrix_compiler.py): особенно строки 322–425.
- [MikroTik zone firewall template](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2): строки 39–215.
- [Docker Compose generator](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/docker_compose_generator.py): существующие flat network/ports.
- [MikroTik matrix](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml), [Proxmox matrix](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml), [LAN](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.vlan.lan.yaml).
- Загружены универсальный AI rulebook, ADR rule map, scoped rules и Codex role overlay.

На начало и после проверок рабочее дерево было чистым. Сравнение с предыдущей проверенной ревизией `d65a43d2` показывает изменения ADR/отчёта/регистра, но не внедрение нового сетевого IR или нового алгоритма firewall.

### 3.2. Выполненные проверки

| Проверка | Свежий результат |
|---|---|
| Строгая компиляция через V5Compiler, диагностические выходы во временный каталог | 0 errors, 0 warnings, 80 info |
| `task validate:layers` | PASS: 62 classes, 140 objects, 189 instances, 29 runtime edges |
| `task validate:adr-consistency` | PASS, strict titles |
| `task framework:verify-lock` | PASS |
| Четыре профильных файла pytest | **51 passed**, 24.12 s |
| Полный перебор DAG-примера ADR 0119 | Найдены контрпримеры, см. `5 и приложение |

Тестовые файлы: [security matrix](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_security_matrix_compiler.py), [IP derivation](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_ip_derivation_compiler.py), [projection helpers](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_projection_helpers.py), [object defaults](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_on_directive_object_defaults.py).

Команда профильных тестов, выполняемая из указанного абсолютного корня репозитория:

~~~sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/plugin_integration/test_security_matrix_compiler.py \
  tests/plugin_integration/test_ip_derivation_compiler.py \
  tests/plugin_integration/test_projection_helpers.py \
  tests/plugin_integration/test_on_directive_object_defaults.py
~~~

Свежий effective JSON для анализа был сохранён в `/tmp/adr0118-0119-review-fqw09wyl/effective.json` в редактированном для безопасного анализа виде. Временный каталог не является постоянным артефактом проекта.

**Ограничения:** не выполнялись apply, подключение к устройствам, захват трафика, расшифровка secrets, полный acceptance suite или аттестация backend. Прохождение текущих тестов не доказывает выполнение ещё не реализованных D15–D21 или I1–I3.

Прежнее замечание про «165 passed, 1 skipped», timeout, внешний symlink bundle и pytest-xdist не перенесено как актуальный результат. Framework lock в этом запуске проверен и проходит; остальные перечисленные механизмы не входят в этот сетевой аудит и здесь повторно не проверялись. :codex-annotation{index="1"}

## 4. Реестр замечаний

**P1** — блокирует принятие объединённого security-контракта или внедрение строгого профиля. **P2** — важный пробел спецификации/реализации. Это инженерные приоритеты, не CVSS и не подтверждение эксплуатации уязвимости на работающем устройстве.

| ID | Приоритет | Замечание | Статус доказательства |
|---|---|---|---|
| J01 | P1 | Две несовместимые нормативные модели в ADR 0118 | Прямое чтение D1–D14 vs D15–D21 |
| J02 | P1 | Приоритет P3/P4 над P5 не различает разрешённое исключение и обход обязательного запрета | Контрпример авторизации |
| J03 | P1 | D7 не фиксирует нижнюю границу класса | Полный перебор минимального DAG |
| J04 | P1 | D4/D7 определяют разные order; коллизии и переполнение | Арифметические контрпримеры |
| J05 | P1 | Specificity score и conflict недостаточны для безопасного разрешения конфликтов | Контрпример множеств, анализ NAT |
| J06 | P1 | I3 не выражает заявленный NoLeak | Контрпример accept-all |
| J07 | P1 | NAT/forward correspondence не связывает исходную авторизацию с преобразованным потоком | Недостаточность D5/D9/E7979 |
| J08 | P1 | Нет контракта безопасного применения и проверки порядка на устройстве | Отсутствует в ADR; Terraform dependency не заменяет контракт backend |
| J09 | P1 | Новые deny defaults не реализованы текущим compiler; неполное покрытие топологии enforcer-ами | Свежая проекция, source и локальный probe |
| J10 | P2 | Не определены единый владелец IR, lifecycle и строгие негативные валидаторы | Сопоставление ADR с правилами репозитория |

### J01. ADR 0118: дополнения ещё не заменили старый контракт

**Места:** D1 строка 90, D2b строка 146, D14 строки 389–494; D15–D21 строки 573–693.

D15 вводит attachments/publications/policies, но D1 продолжает объявлять universal primary/service. D19 откладывает Kubernetes, но старая platform matrix его содержит. D20 перечисляет исправления, однако старые CIDR и широкие примеры остаются. D18 переносит диагностические коды, а старые разделы всё ещё показывают прежние номера.

D14 описывает `isolated`, тогда как D16 предлагает другую семантику. В результате реализация по старому примеру может противоречить новой acceptance matrix.

**Исправление:** сделать одну нормативную редакцию: явно supersede D1–D14 в затронутых частях либо переписать их; старые примеры вынести в non-normative migration appendix. Добавить `schema_version` и правила миграции flat → canonical IR. Согласовать ADR 0110: нельзя молча поменять его R1–R6 через новые defaults в другом ADR.

### J02. Порядок классов подменяет авторизацию

**Место:** ADR 0119, Context строки 28–48 и D1 строки 52–72.

Вводный пример считает «guest→servers deny раньше конкретного allow» ошибкой. Это ошибка **только если** deny является default, а более узкий allow — утверждённым исключением. Если deny — запрет на гостевой доступ к серверной зоне или карантин, allow должен быть отклонён, а не переставлен выше.

P3 POLICY_ACCEPT и P4 PUBLICATION_FORWARD стоят перед P5 MATRIX_DENY. Но происхождение правила от генератора не определяет его право обходить другой запрет. В модели отсутствует полноценное различие `mandatory_deny`, `default_deny` и `approved_exception`.

Отдельно P1 unconditional established/related и P2 общий ICMP обходят последующие ограничения. Established не означает «разрешён текущей политикой после отзыва доступа», related требует ограничения доверенных helpers. Это требование строгого профиля, а не утверждение, что обычный stateful firewall всегда некорректен.

**Исправление:** определить combining algorithm до классов. Обязательные запреты не обходятся specificity или publication. В строгом профиле отключить автоматический R3 downhill allow; ICMP оформить ограниченными явными политиками, сохранив необходимые PMTU/ND и диагностику, а не запрещая весь ICMP.

### J03. DAG не доказывает порядок классов

**Место:** ADR 0119 D7 строки 309–322.

Алгоритм добавляет только `rule → next_anchor`. Нет `current_anchor → rule`.

Для A1→A3→A4→A5→A7, R3→A4 и R4→A5 допустима последовательность:

~~~text
A1, A3, R4, R3, A4, A5, A7
~~~

Она удовлетворяет всем описанным рёбрам, но R4 расположен перед R3. Из 15 допустимых линейных расширений 6 нарушают порядок этих классов. Добавление A3→R3 и A4→R4 устраняет нарушение в данном конечном примере.

**Исправление:** две границы класса, канонический tie-break и проверка всех рёбер на конечном плане. Это локальное доказательство дефекта, а не полноценная верификация firewall.

### J04. Order не является единым согласованным отношением

**Места:** D4b строки 151–164; I2 строки 198–200; D7 строки 327–334.

1. D4 назначает order по hash; D7 — по количеству предыдущих правил класса. Это разные функции.
2. 101 идентификатор в 100 слотах гарантирует коллизию. Если конфликтующая пара с разной specificity получает равный offset, строгое неравенство I2 невыполнимо.
3. Даже без коллизии hash не зависит от specificity и не гарантирует I2.
4. В D7 101-е правило P3 получает `200 + 100 = 300`, а первое P4 — `300`: нарушается I1.
5. Перестановка результата D7 по числовому order отдельно не описана и всё равно не исправляет переполнение.
6. Нестабильный выбор среди доступных вершин даёт разные планы при изменении порядка discovery/input.

**Исправление:** одна функция позиции от канонического топологического порядка, без фиксированных «окон по 100». Если нужны классы для UI — отдельное поле, а не арифметика адресации слотов.

### J05. Specificity score не отражает семантическую вложенность

**Место:** D4c строки 167–178; D4d строки 181–189.

Правило A: source host 10.0.0.1, destination any, TCP/80 → score 11.\
Правило B: source 10.0.0.0/24, destination 192.0.2.0/24, любой протокол/порт → score 8.

Есть пересечение, но ни одно множество не включено в другое. Следовательно, больший score не является доказательством «более узкого исключения». /8 и /32, address-list, interface, state, negation, IPv6 и dynamic membership требуют собственной семантики.

`same chain + overlap + action differs` тоже недостаточно:

- одинаковая строка chain на разных enforcer/VRF/AF не означает конфликт;
- два `dst-nat` с разными targets могут конфликтовать при одинаковом action;
- terminal action, passthrough, jump и state transformation нельзя сравнивать только как строки.

**Исправление:** сравнивать предикаты и эффекты в одном execution context. Неизвестный/неподдерживаемый match — ошибка строгого профиля, а не отсутствие конфликта. Неразрешённый конфликт W7974 должен блокировать компиляцию; «specificity=0 ⇒ matches everything» из W7975 заменить проверкой истинности всего предиката.

### J06. I3 — покрытие, не NoLeak

**Место:** D4e строки 202–204.

~~~text
∀ p ∃ r: matches(r,p) ∧ terminal(action(r))
~~~

Одно правило `accept all` удовлетворяет формуле. Неразрешённый guest→management TCP/22 будет разрешён. Формула ничего не говорит о policy_ref или допустимости пакета.

При наличии jump/return/циклов существование подходящего terminal rule даже не доказывает, что выполнение до него дойдёт. Для линейной terminating chain это условие покрытия; для общего firewall нужен переходный автомат.

**Исправление:** разделить termination/coverage, authorization soundness и required-flow availability. Не называть эти свойства полной защитой от утечки информации: разрешённый DNS/HTTPS тоже может переносить нежелательные данные.

### J07. NAT — преобразование адресов, не разрешение

**Места:** ADR 0118 D14c и D15; ADR 0119 D5 и D9, E7978/E7979.

Новый D15 лучше старого D14: есть ports, owner и policy_ref. Но ADR 0119 не определяет точного соединения этих полей с match после DNAT. В примере P4 IR отсутствует policy_ref, хотя E7978 требует его.

Наличие любой forward-записи рядом с NAT не доказывает, что совпадают клиент, протокол, порт, публикация и направление. Разрешение по одному backend IP может открыть UI AdGuard:3000 вместе с DNS:53. Без связи с исходной публикацией прямой доступ к backend может получить права, предусмотренные только для frontend.

E7979 «любая NAT rule должна иметь forward rule» слишком общее: local INPUT/OUTPUT, srcnat и маршрутизируемая публикация имеют разные пути. Нужна проверка соответствующего пути, а не универсальная пара ресурсов.

RouterOS обрабатывает routed DNAT до forward-filter; FastTrack может обходить L3 facilities. Поэтому математика должна учитывать hook и состояния преобразования, а не сравнивать только адреса из YAML. [Официальная схема RouterOS](https://manual.mikrotik.com/docs/firewall-and-quality-of-service/packet-flow-in-routeros/).

### J08. Логический порядок ≠ порядок после apply

**Места:** D2 anchors, D3 placement, D6 generator contract, Migration Path.

Все sibling rules могут иметь один `place_before`. Это устанавливает верхнюю границу, но не задаёт их взаимный порядок. `depends_on` управляет очередностью операций Terraform; вывод о том, что он сам по себе не доказывает последовательность правил внутри устройства, — инженерное следствие этого контракта. [HashiCorp depends_on](https://developer.hashicorp.com/terraform/language/meta-arguments/depends_on).

A1 при этом не нейтральный якорь: он сам принимает established/related. A2/A6 не описаны, хотя E7976 требует anchor для класса. Непонятно, как сохраняются инварианты при обновлении, удалении, ручных правилах, restart и частичном apply.

**Исправление:** отдельный backend deployment contract: владение цепочкой, точное отображение plan→device, read-back, drift detection, безопасная смена поколений и revocation существующих сессий. Не обещать атомарную транзакцию там, где конкретный backend/provider её не гарантирует.

### J09. Новые defaults и границы enforcement пока декларативны

Текущий `_calculate_matrix` читает `isolated/security_level`, но не D16 defaults. Локальный probe добавил гипотетическую зону с тремя `deny` defaults к действующему вычислителю: perimeter self получил R1 allow, направления к untrusted и IoT — R3 allow.

Это **не тест реализованного нового API**, а свидетельство, что добавление этих YAML-полей само по себе ещё не включает обещанное поведение. Существующие R1/R3 не следует объявлять новым zero-trust режимом.

В MikroTik template:
- input established/related/**untracked** разрешён на строках 39–44;
- весь ICMP принят на 46–50;
- input drop ограничен `!LAN` на 62–67, а не полным deny для management plane;
- forward established принят на 72–76;
- R3 allow-ресурсы закомментированы на 181–205, но final drop активен на 208–215.

Последнее требует проверки **сохранения доступности** между матрицей и rendered plan. Другие правила могут влиять на итог; по одному шаблону нельзя объявить конкретный живой маршрут доступным или заблокированным.

### J10. Нужен один producer нормализованного security plan

ADR 0119 D5 показывает `build/projections/mikrotik/firewall_rules.yaml`, а D6 поручает генераторам самостоятельно назначать класс/specificity/placement.

Если YAML — только иллюстрация, это надо явно указать. Если runtime-источник, возникает ещё одно представление истины. Генераторы не должны независимо решать авторизацию и порядок, а compile не должен читать результаты более позднего generate.

**Исправление:** canonical effective JSON + typed bus; нормализация правил в compile, проверка в validate, генераторы только переводят проверенный plan в backend syntax. Все зависимости объявить manifest-контрактами; не возвращать неявное чтение source YAML.

## 5. Предлагаемый согласованный математический контракт

Ниже — **предложение**, не описание существующей реализации. Оно связывает модель ADR 0118 с доказательными обязательствами ADR 0119.

### 5.1. Объекты и область вычисления

Сохранить C→O→I. Workload attachment принадлежит L4, service publication — L5; политика связывает субъект/сервис/направление, а не становится побочным свойством IP.

Минимальные сущности:

~~~text
Attachment(id, workload_ref, network_ref, driver, address, routing_domain)
Publication(id, service_ref, backend_attachment_ref, mechanism,
            frontend, ports, policy_ref, enforcer_ref)
Policy(id, revision, effect, source_selector, destination_selector,
       service_selector, conditions, approval_ref, expires_at)
Enforcer(id, capabilities, observed_version, failure_mode, managed_scope)
~~~

Добавить обязательные schema versions и provenance. `approval_ref`/`expires_at` — не строки для декорации: их валидность должна проверяться, а enforcement обязан поддерживать требуемый срок отзыва или отклонять профиль.

Контекст состояния:

~~~text
x = (enforcer, namespace/VRF, address_family, table, hook, chain,
     in_interface, out_interface, original_5tuple, current_5tuple,
     connection_state, subject/device/workload_identity,
     policy_epoch, time, labels)
~~~

Это не означает, что каждый firewall умеет проверять identity. Compiler должен либо назначить дополнительный способ enforcement, либо выдать unsupported-capability. IP-подсеть — атрибут расположения, не доказательство личности.

### 5.2. Сначала авторизация, затем порядок

Для каждого применимого gate k: source egress, destination ingress, intra-zone при необходимости, service access:

~~~text
Gate_k(x) =
    NOT MandatoryDeny_k(x)
    AND (ExplicitApprovedPermit_k(x) OR DefaultAllow_k)

Authorized(x) =
    ValidContext(x)
    AND LabelFlowAllowed(x)
    AND EnforcementReady(x)
    AND AND_over_applicable_k Gate_k(x)
~~~

В строгом профиле `DefaultAllow_k = false`. Default deny — **значение по умолчанию при отсутствии разрешения**, а не обязательный запрет, отменяющий все исключения. Mandatory deny, напротив, нельзя обойти обычным permit.

Обязательны правила composition:
- внутри набора явных permits — объединение;
- между обязательными gates — пересечение;
- обязательные запреты — вычитание;
- exception разрешает только явно утверждённую область и срок, а не весь flow class;
- R3 и same-zone не дают автоматического права;
- publication не добавляет право, а реализует уже разрешённый сервис.

Полезный инвариант монотонности: добавление mandatory deny или удаление permit не должно увеличивать разрешённое множество.

~~~text
Permits' ⊆ Permits AND Denies' ⊇ Denies
    ⇒ Authorized' ⊆ Authorized
~~~

Рекомендация не доверять одной сетевой принадлежности согласуется с [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final); приведённые формулы — предлагаемая реализация для этого проекта, не цитата из стандарта.

### 5.3. Семантика правил и specificity

Пусть `M(r)` — множество состояний, удовлетворяющих полному match в фиксированном scope.

~~~text
StrictlyMoreSpecific(r1, r2) ⇔ M(r1) ⊂ M(r2)
Overlap(r1, r2) ⇔ M(r1) ∩ M(r2) ≠ ∅
~~~

Вложенность — частичный порядок; для несравнимых правил нельзя изобретать авторизацию баллами. Даже строго более узкий permit не получает права преодолеть mandatory deny.

Эффекты должны включать target NAT, jump destination, side effects и terminal/non-terminal semantics. Для статических CIDR/ports/protocol возможно точное вычисление областей; для неподдерживаемых динамических predicates результат `unknown` должен блокировать строгий профиль. Snapshot address-list должен иметь версию и срок актуальности.

### 5.4. Заменить I3 тремя независимыми свойствами

Для **линейной цепочки только из terminal accept/drop**:

~~~text
EffectiveMatch_i = M_i \ UNION_{j<i} M_j
CompiledAllow = UNION_{i : action_i=accept} EffectiveMatch_i
~~~

Для passthrough/jump/NAT эта сокращённая формула не применима без интерпретатора переходов. Нейтральный anchor не должен «забирать» область match у следующих правил.

Новые обязательства:

~~~text
S1 Authorization soundness:
    CompiledAllow ⊆ Authorized

S2 Required-flow availability:
    RequiredFlows ⊆ CompiledAllow
    (при явно заданных здоровых компонентах/маршрутах)

S3 Termination and default decision:
    каждый допустимый вход в модель за конечное число шагов
    завершается разрешённым terminal verdict;
    отсутствие разрешения ведёт к deny.
~~~

Для составного пути `CompiledAllow` определяется на **исходных состояниях потока**, с учётом всех преобразований и enforcer-ов, а не на одном post-NAT адресе.

Доказательство S1 не является доказательством полной information-flow noninterference: для последнего нужны семантика приложений, ответы, побочные и скрытые каналы, declassification и отдельная доверенная база.

### 5.5. Порядок как следствие семантики

Внутри одного execution scope использовать логические категории:

~~~text
SANITY / MANDATORY_DENY / VALIDATED_SESSION / EXPLICIT_PERMIT / DEFAULT_DENY
~~~

Это не универсальная физическая цепочка для всех hooks. Например, predicate mandatory deny, зависящий от DNAT, должен корректно переноситься в соответствующее адресное пространство. ICMP — набор explicit permits; publication — provenance, не особый обходной класс безопасности.

Для каждого класса c:

~~~text
A_c → r → A_(c+1), для каждого r класса c
~~~

Дополнительно — только семантически обоснованные precedence edges. Anchors могут существовать лишь в IR и не обязаны превращаться в исполняемые allow/no-op ресурсы.

Алгоритм:
1. Нормализовать IDs, scopes, predicates и эффекты.
2. Разрешить policy composition до размещения.
3. Построить обе границы классов и необходимые precedence edges.
4. Отклонить цикл с минимальным объясняющим conflict witness.
5. Выполнить стабильный topological sort с canonical ID среди независимых вершин.
6. Назначить `position(r)=index_in_final_sequence(r)`, глобально внутри scope.
7. Проверить S1/S2/S3 и все рёбра на итоговом плане.

Нет `hash mod 100`, нет переполнения bands. Canonical tie-break обеспечивает воспроизводимость, но **не разрешает противоречащие политики**. Переставлять без семантического эффекта можно лишь доказанно независимые/эквивалентные правила.

### 5.6. NAT: отношение преобразования, а не строковый класс

Пусть `T_P ⊆ X × X` — преобразование исходного состояния в post-NAT состояние для публикации P.

~~~text
PublicationAccept_P(x, x') ⇒
    Authorized(x)
    AND T_P(x, x')
    AND BoundToPublication(x, x', P)
~~~

Должны сохраняться source restrictions, protocol и отображение frontend/backend ports. `BoundToPublication` требует доступного enforcer-у доказательства происхождения: original tuple/conntrack/NAT state, защищённой mark либо доказанного ограничения маршрутов. Одного post-NAT backend IP недостаточно.

Две публикации могут иметь один backend; SNAT может быть many-to-one. Поэтому нельзя предполагать наличие единственной обратной функции `T^-1`.

Отдельные obligations:
- DNAT, SNAT, local input/output и hairpin имеют свои paths;
- никакая NAT-трансформация не расширяет Authorized;
- direct backend access проверяется отдельно;
- совпадающие match с разными NAT targets требуют явного разрешения неоднозначности;
- существующие conntrack bindings учитываются при смене версии.

Connection tracking действительно сохраняет состояние и используется NAT; related/untracked имеют отдельную семантику. Это причина включить их в модель, а не считать все такие пакеты одинаково доверенными. [RouterOS Connection Tracking](https://manual.mikrotik.com/docs/firewall-and-quality-of-service/connection-tracking/).

### 5.7. Покрытие всех путей и отказов

Сеть моделируется графом состояний/переходов, включая L2, routed L3, host-local, IPv6, tunnels и обходные ускоренные пути.

~~~text
∀ reachable path π from source to protected destination:
    если π доставляет поток, этот исходный поток входит в Authorized
~~~

Эквивалентное практическое obligation: каждый запрещённый маршрут должен пересекать реально работающий enforcement cut. Наличие `enforcer_ref` без доказательства прохождения пакета недостаточно.

В свойства backend включить `ipv6`, `bridge_filtering`, `host_forward`, `conntrack_original_tuple`, `policy_revocation`, `atomic_switch`, `readback` и hardware/FastTrack semantics. Необеспеченная capability → ошибка строгого профиля.

Нельзя автоматически предполагать, что межконтейнерный трафик одного bridge достигает маршрутизатора. Для Docker published ports проверяется действительный forwarding path, а не только INPUT хоста. [Docker with iptables](https://docs.docker.com/engine/network/firewall-iptables/).

### 5.8. Безопасность во времени: apply, revocation, expiry

Статический порядок недостаточен. Для каждого промежуточного состояния применения S_t:

~~~text
Allow(S_t) ⊆ Authorized(policy_effective_at_t)
~~~

Нельзя использовать `old_allow ∪ new_allow` как универсально безопасный переход: при отзыве доступа это сохраняет уже запрещённые потоки. Для консервативного перехода подходит ограничение пересечением там, где оно реализуемо, с отдельно согласованным влиянием на доступность.

Контракт deployment:
- один владелец управляемой chain/scope;
- подписанный или проверяемый manifest плана, policy generation и content digest;
- preflight capabilities и актуальный snapshot устройства;
- staged install / switch только с документированными гарантиями backend;
- read-back и сравнение фактического семантического порядка;
- unknown/manual rules — reconcile либо остановка, не молчаливое игнорирование;
- revocation session с измеримым deadline и targeted invalidation;
- аварийный доступ через отдельный OOB/break-glass механизм с ограниченным сроком;
- rollback не должен автоматически возвращать отозванные разрешения.

На backend без атомарности допустим управляемый deny-first переход или окно обслуживания; обещать одновременно нулевой downtime и отсутствие промежуточных расширений доступа без доказательства нельзя.

### 5.9. Метки данных — отдельно от trust level

Для обычного home-lab достаточно строгой явной политики. Для перспективного профиля с классифицированными доменами `security_level` нельзя переиспользовать как уровень секретности.

Предлагаемая отдельная метка:

~~~text
L = (classification, compartments)
L1 ⪯ L2 ⇔ classification1 ≤ classification2
           AND compartments1 ⊆ compartments2
~~~

Для защищённого потока данных без declassification допускается только выбранное политикой направление относительно этого порядка; в простом confidentiality-профиле — `L_source ⪯ L_destination`. Это **не** готовое правило для TCP request/response: ответы тоже переносят данные. Integrity требует отдельного отношения, а не переворота существующего trust score на глаз.

Переход через несовместимые домены должен ссылаться на явно утверждённый guard/declassifier с собственными гарантиями. Обычный permit или DNAT не делает такой переход допустимым. Реализация на текущем home-lab не должна заявлять поддержку classified cross-domain security.

## 6. Влияние улучшений модели на математику

| Улучшение ADR 0118 / общей модели | Изменение ADR 0119 | Новое доказательное обязательство |
|---|---|---|
| Отдельные attachments/publications/policies | Rule provenance и явная привязка к intent | Каждое accept выводится из действующего permit |
| Ingress/egress/intra-zone defaults | AND между gates, explicit permits внутри gate | Нет автоматического R1/R3 доступа в strict profile |
| Mandatory deny vs default deny | Приоритет по семантике, не generator class | Ужесточение не увеличивает allow set |
| Address owner и lifecycle VIP | Время, routing domain и address binding входят в состояние | Единственный авторизованный активный владелец; нет DHCP-конфликта |
| NAT с ports и frontend/backend | Отношение T_P и original/current tuple | Нет расширения разрешения после трансляции |
| Enforcer capabilities и path binding | Многопутевая transition semantics | Все обходные пути закрыты либо scope явно unsupported |
| Identity, approval, expiry | Authorization зависит от контекста и времени | Неизвестная identity/просроченное разрешение не принимаются молча |
| Session policy epoch | Stateful правила вместо unconditional established | Отзыв действует в установленный deadline |
| Конечный canonical plan | Topological position вместо hash bands | Детерминизм, отсутствие циклов, сохранение precedence |
| Deployment generation/read-back | Инвариант на последовательности состояний | Ни один этап apply/rollback не расширяет действующее разрешение |
| Метки/compartments при необходимости | Частичный порядок потоков данных | Cross-domain flow не разрешается ordinary ACL |
| Auditable compiler pipeline | Provenance chain от source revision до observed state | Можно объяснить и воспроизвести каждый принятый flow |

Изменения затрагивают не только два документа: требуется согласование с ADR 0110, схемами классов/объектов, compiler bus, capability catalog, validators, generator adapters, deploy orchestration, тестами и ADR register. Это архитектурная работа, а не косметический перенос правил.

## 7. Применение к текущей топологии

В свежем effective state: **6 RouterOS containers, 9 Docker containers и 3 Docker stacks, 9 LXC**, всего 189 instances всех типов. Указанные ниже проблемы относятся к source/IR, а не к подтверждённой конфигурации живых устройств.

### 7.1. RouterOS AdGuard / Mosquitto / Tailscale

[AdGuard attachment](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-adguard.yaml), [Mosquitto attachment](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-mosquitto.yaml), [Tailscale attachment](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-tailscale.yaml).

Все три сохраняют:
- bridge `inst.bridge.containers` и заданный gateway `172.18.0.1`;
- VLAN LAN и вычисленный адрес `192.168.88.210/.211/.212`;
- вычисленный gateway `192.168.88.1`.

Это исходная неоднозначность attachment/publication, ещё не устранённая добавлением ADR D15. Рекомендуется отдельный backend attachment в выбранном container subnet, а LAN VIP — только при обоснованной необходимости frontend.

LAN DHCP pool `192.168.88.10–192.168.88.254` включает предполагаемые VIP .210–.212. `dhcp_exclude: true` недостаточно: compiler должен либо детерминированно преобразовать pool и проверить итог, либо отклонить конфликт. При deployment нужно проверить активные leases и согласовать порядок освобождения адреса/назначения владельца. Для HA допустимые владельцы и fencing должны быть отдельной моделью, а не два независимо активных владельца одного VIP.

### 7.2. DNS: сервис и управление разделить

Для AdGuard:
- DNS TCP/UDP 53 — только утверждённые client selectors;
- UI 3000 — только management identity/path;
- upstream DNS/NTP — конкретные утверждённые направления;
- прямой доступ к backend тестировать отдельно;
- frontend DNS publication не должна порождать accept-all к контейнеру.

Источник: [AdGuard service](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-adguard.yaml).

DNS egress сам по себе не исключает exfiltration; при высоких требованиях нужны контролируемый resolver, журналирование и дополнительные прикладные ограничения. Проверка L3/L4 не доказывает содержание DNS-запросов безопасным.

### 7.3. MQTT: источник и криптография должны пережить компиляцию

[Service Mosquitto](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-mosquitto.yaml) объявляет allowed_from IoT/servers, TLS/auth и порты 1883/8883/9001.

Рекомендуемый strict-профиль: разрешать только реально используемые защищённые listeners с аутентификацией; 1883 и websocket listener не считать допустимыми автоматически. Если 9001 требуется, отдельно определить TLS termination и identity policy. Расширение до user/guest через общий P3/P4 запрещать.

Математически source selector сервиса должен пересекаться с network permit, а не теряться при materialization публикации.

### 7.4. Management и базы данных

В текущей MikroTik projection остаются:
- `lan-to-management-admin`: вся `192.168.88.0/24`, без ограничения ports;
- `management-to-servers-full`: полный доступ;
- `user-to-servers-db`: TCP 5432/6379 ко всей server zone.

Для строгого профиля это слишком широкие разрешения. Заменить их отдельными flow policies: управляемые admin devices → bastion/management endpoints; application workloads → конкретные DB endpoints; отдельные backup/monitoring flows. Не оставлять Redis/PostgreSQL доступными всей user zone только из удобства.

Ранее исправленные inheritance/HTTP проблемы не объявляются повторно найденными: здесь перечислены только текущие четыре projected overrides, включая servers→management drop.

### 7.5. LXC и east-west enforcement

Все 9 LXC имеют `firewall: false`; Proxmox security matrix выключена. Пример: [LXC Grafana](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/lxc/srv-gamayun/lxc-grafana.yaml), `10.0.100.60/24`, gateway `10.0.100.1`.

Не менять реальные addresses на старые ADR-примеры `10.0.30.0/24`. Сначала выбрать и внедрить working enforcer на host/bridge/VM boundary. Роутер не доказывает изоляцию соседей одной L2-сети.

Правильная зависимость: topology path → enforcer capability → validated policy plan → deployment evidence. Одной записи zone matrix или переключения `firewall: true` без backend rules недостаточно.

### 7.6. Docker на OrangePi

Текущая модель смешивает container address intent и host publication. Management IP `10.0.99.20` не должен автоматически становиться bind address сервисов. Если выбран service address `10.0.100.23`, сначала подтвердить его назначение хосту/интерфейсу и маршрутизацию.

Для каждой publication определить host bind IP, порт и внутренний attachment. Не объявлять адреса .200/.210 и подобные автоматически принадлежащими хосту. Enforcement проверять на фактическом Docker backend и forwarding path, включая direct routing; рекомендация не предполагает конкретный включённый firewall backend без наблюдения устройства.

### 7.7. AmneziaWG и Tailscale — не обычные веб-публикации

Два AWG-контейнера уже имеют отдельные /30 veth: `172.18.22.2` и `172.18.23.2` с gateway .1. Их route-policy semantics нельзя заменять universal DNAT.

Добавить:
- явные разрешённые маршруты/subnets;
- anti-spoofing входного tunnel traffic;
- запрет fallback на обычный WAN для flows с обязательным VPN;
- отдельные failure scenarios tunnel down / route withdrawn;
- исключение обходящих enforcement acceleration paths либо доказанную эквивалентность.

Для Tailscale exit/subnet router нужен отдельный контракт identity и разрешённых маршрутов. Наличие контейнера или VPN не означает авторизацию всех клиентов. Проверка actual coordination/ACL state в этом ревью не выполнялась.

### 7.8. Предлагаемая логическая топология

~~~text
Untrusted / Guest / IoT / User
            |
      ingress policy gates
            |
   Explicit service publications ---- Admin bastion / managed devices
            |                                |
      service-facing boundary         management-only endpoints
            |
   Workloads / app groups -- exact service flows --> Databases
            |
   bounded egress policies --> DNS/NTP/update/proxy/VPN endpoints

На каждом фактическом L2/L3/host/tunnel пути:
enforcer capability + tested rules + observed state
~~~

Это логическая схема, **не требование создать отдельный VLAN на каждый контейнер**. Где host enforcement доказуем и поддерживается, можно сохранить адресный план. Где нет — нужна более сильная граница: отдельный bridge/VLAN/VM/хост по результатам threat model.

Для повышенной защищённости желательно убрать необязательные приложения с пограничного маршрутизатора: общий runtime расширяет его доверенную базу. Это рекомендация архитектурного разделения ролей, не вывод о подтверждённой компрометации.

## 8. Дополнительные требования строгого профиля

1. **Криптография:** профиль должен задавать protocol/version, peer identity, trust roots, rotation и проверяемые свойства реализации. Если применимый baseline требует validated crypto, проверяется конкретный модуль, версия и operational environment; использование TLS/WireGuard само по себе не является такой аттестацией. [NIST CMVP](https://csrc.nist.gov/projects/cryptographic-module-validation-program).
2. **Администрирование:** отдельный management plane, MFA/сильная аутентификация на доступных компонентах, least privilege, короткоживущие credentials и audit. Эти гарантии нельзя вывести из IP allowlist.
3. **Supply chain:** pin и provenance для compiler/plugins/templates/provider/image; проверяемый plan digest; отделение авторства policy от утверждения критических изменений. Framework lock — полезный контроль целостности, но не полный доказательный пакет.
4. **IPv6 и L2:** явная поддержка с аналогичными политиками либо контролируемое отключение и проверка. IPv4-only доказательство не покрывает IPv6, ARP/ND spoofing или bridge bypass.
5. **Отказы:** недоступность policy source, устаревший identity snapshot, потеря времени/clock trust и enforcer failure имеют определённый безопасный результат. Grace period допустим только как ограниченная утверждённая политика, не скрытый allow.
6. **Наблюдаемость:** reason codes и счётчики отказов; защищённая доставка audit; rate limiting/sampling для массовых drops. Текущее `log=true` на final drop требует нагрузочного теста, чтобы журналирование не стало DoS-вектором.
7. **Отсутствие молчаливого downgrade:** если backend не поддерживает требуемое свойство, build/deploy отклоняется. «Сгенерировали похожие правила» не считается успешной реализацией strict profile.

## 9. Рекомендуемые acceptance и property tests

| Тест | Ожидаемое свойство |
|---|---|
| Перестановки порядка discovery, input YAML и независимых rules | Одинаковый normalized plan digest |
| 101, 1000 и более правил класса | Нет коллизии позиции или пересечения классов |
| DAG missing-boundary mutation | Тест обнаруживает R4 before R3 |
| accept-all mutant | S1 падает с конкретным unauthorized packet witness |
| Более специфичный allow внутри mandatory deny | Compile ERROR либо безопасное вычитание с явным объяснением, не bypass |
| Несравнимые пересекающиеся predicates | Не решать конфликт score/hash |
| DNAT DNS53 + backend UI3000 | 53 разрешён утверждённым клиентам, UI не открывается |
| Прямой backend и две публикации одного backend | Не наследуют права чужого frontend |
| UDP/TCP, IPv4/IPv6, fragments, ICMP errors | Согласованная семантика либо explicit unsupported |
| Same bridge, host-local, routed, tunnel и FastTrack paths | Нет непроверенного обходного пути |
| Удаление permit / добавление deny | Allow set не увеличивается |
| Revocation при established и related | Отзыв применяется в заявленный deadline |
| Partial apply / retry / reboot / rollback | Temporal invariant сохраняется |
| Неизвестное ручное правило выше managed chain | Drift обнаружен, safety не предполагается |
| VIP внутри pool или active lease | Ошибка/preflight block либо доказанный migration procedure |
| Потеря enforcer, identity source или trusted time | Заданный fail-secure результат |
| Повторный apply | Идемпотентность и совпадение observed plan |
| Удаление обязательного служебного permit | S2 указывает потерянный DNS/NTP/PMTU/admin flow |

Нужны уровни: unit algebra → property-based finite models → differential interpreter vs rendered rules → backend integration → controlled packet tests → transition/failure tests. Полный перебор из приложения покрывает только небольшой DAG; его нельзя представлять как formal verification всей инфраструктуры.

## 10. Порядок реализации

### Этап A — единый документированный контракт

- Нормативно свести ADR 0118 D1–D21.
- Заменить ADR 0119 I1–I3 согласованными authorization/order/termination obligations.
- Согласовать семантику strict defaults и legacy R1–R6 с ADR 0110.
- Зарегистрировать диагностические коды без двусмысленности severity.
- Обновить ADR register и затронутые rule packs при принятии решений.

### Этап B — canonical IR и валидаторы раньше миграции

~~~text
discover
  → compile:
      normalize network + identity/address references
      → resolve policy intent
      → construct enforcement plan and canonical order
  → validate:
      schema + capabilities + authorization/path/order proofs
  → generate:
      deterministic backend rendering
  → assemble:
      artifact consistency + provenance manifest
  → build:
      immutable candidate bundle
~~~

Названия стадий и manifest contracts сохраняются по ADR 0086. Offline evidence не подменяет live deployment evidence; latter собирается отдельным deploy/reconcile процессом.

### Этап C — исправить фактическую топологию

Сначала VIP/attachment ambiguity и DHCP, затем source-scoped DNS/MQTT/admin policies, затем Docker host binds и LXC east-west enforcement. AWG route semantics сохранить и отдельно проверить kill-switch.

### Этап D — безопасное применение

Один проверенный enforcer/backend как pilot; staged rules, OOB recovery, explicit session revocation, read-back. Затем backend parity. Не мигрировать все instances до готовности compiler, validators и deployment contract.

### Этап E — критерий принятия

ADR могут быть приняты как целевая архитектура после устранения логических противоречий. **Реализация strict profile** считается готовой только после acceptance evidence для заявленных capabilities и текущей топологии. Оценки в несколько десятков часов из ADR не включают весь объём stateful/path/transition verification и не должны обещать подтверждённую высокую защищённость.

## 11. Итог

**Сохранить:** attachments/publications/policies, явное владение VIP, policy_ref, ограничение scope v1 и единый projection bus.

**Переработать:** приоритет по происхождению правила, hash-based order, score-based разрешение конфликтов, I3 NoLeak, NAT/forward correspondence и применение через одни anchors.

**Главное изменение модели:** не «какое правило поставить раньше», а **«какое разрешение доказано, где оно исполняется и сохраняется ли оно после трансляции, изменения конфигурации и отказа»**.

Это позволяет сделать ADR 0118 моделью намерений, ADR 0119 — контрактом их безопасной реализации, а effective JSON и observed-state evidence — проверяемой связью между ними.

## Приложение A. Воспроизводимые математические контрпримеры

Скрипт Python использует только standard library. SHA-256 здесь выбран для иллюстрации; ADR не фиксирует конкретную hash-функцию. Принцип Дирихле применим к любой функции из 101 ID в 100 offset.

~~~python
import itertools,hashlib,ipaddress,json
# Literal dependency relations described in ADR0119 D7 for its example anchors.
nodes=['A1','A3','A4','A5','A7','R3','R4']
edges=[('A1','A3'),('A3','A4'),('A4','A5'),('A5','A7'),('R3','A4'),('R4','A5')]
def extensions(es):
 return [p for p in itertools.permutations(nodes) if all(p.index(a)<p.index(b) for a,b in es)]
old=extensions(edges);bad=[p for p in old if p.index('R4')<p.index('R3')]
new=extensions(edges+[('A3','R3'),('A4','R4')])
print('D7_COUNTEREXAMPLE',json.dumps({'valid_orders':len(old),'class_violations':len(bad),'witness':bad[0],'fixed_valid_orders':len(new),'fixed_violations':sum(p.index('R4')<p.index('R3') for p in new)}))
# Any map of 101 rules to 100 offsets collides. SHA256 is an illustrative deterministic hash.
slots={}
for i in range(101):
 rid='rule-'+str(i);h=int.from_bytes(hashlib.sha256(rid.encode()).digest(),'big')%100;slots.setdefault(h,[]).append(rid)
pair=next((v for v in slots.values() if len(v)>1))
print('HASH_COUNTEREXAMPLE',json.dumps({'hash':'sha256 (illustrative; ADR does not specify hash)','rules':101,'distinct_slots':len(slots),'collision':pair[:2]}))
print('D7_OVERFLOW',json.dumps({'P3_rule_101':200+100,'P4_rule_1':300,'I1_strict_less':200+100<300}))
# I3 is total coverage, not no unauthorized acceptance.
rules=[('all','accept')]
unauthorized={'source':'guest','destination':'management','protocol':'tcp','port':22}
print('I3_COUNTEREXAMPLE',json.dumps({'I3_satisfied':True,'packet':unauthorized,'verdict':'accept','authorization':False}))
# Specificity A=8+2+1=11; B=4+4=8. Intersection but neither set contains the other.
def A(p):return p[0]=='10.0.0.1' and p[2]=='tcp' and p[3]==80
def B(p):return ipaddress.ip_address(p[0]) in ipaddress.ip_network('10.0.0.0/24') and ipaddress.ip_address(p[1]) in ipaddress.ip_network('192.0.2.0/24')
both=('10.0.0.1','192.0.2.1','tcp',80)
aonly=('10.0.0.1','198.51.100.1','tcp',80)
bonly=('10.0.0.2','192.0.2.1','udp',53)
print('SPECIFICITY_COUNTEREXAMPLE',json.dumps({'A_score':11,'B_score':8,'overlap':A(both) and B(both),'A_not_subset_B':A(aonly) and not B(aonly),'B_not_subset_A':B(bonly) and not A(bonly)}))
# Presence of a matching terminal action is insufficient for authorization; ports must be preserved.
print('PUBLICATION_SUBSET',json.dumps({'approved_frontend_ports':[53],'blanket_backend_accept_port':3000,'would_be_allowed_by_backend_IP_only_rule':True}))
~~~

Получено:

~~~text
D7: valid_orders=15, class_violations=6
Witness: A1, A3, R4, R3, A4, A5, A7
With both class boundaries: valid_orders=1, class_violations=0

Hash illustration: 101 IDs, 65 distinct slots;
collision: rule-1 / rule-33

D7 overflow: P3_rule_101=300, P4_rule_1=300; strict I1=false
I3: accept-all satisfies formula, unauthorized guest→management TCP22 accepted
Specificity: A_score=11 > B_score=8, overlap=true,
             A⊄B and B⊄A
~~~

Пример PUBLICATION_SUBSET иллюстрирует логическую недостаточность accept по backend IP; он не исполняет конфигурацию реального устройства.
