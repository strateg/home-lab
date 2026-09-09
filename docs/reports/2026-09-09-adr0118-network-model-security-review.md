# ADR 0118: гармоничность модели и безопасность на текущей топологии

**Дата:** 2026-09-09. **HEAD:** `d65a43d2a9deda6013fc4329ccdb1941ac22528a`.  
**Объект:** [ADR 0118](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/adr/0118-universal-container-network-model.md), статус **Proposed**, включая D14 Security Matrix Integration.  
**Репозиторий:** `/home/nixos/workspaces/home-lab`, NixOS/WSL.  
**Режим:** архитектурное ревью + проверка существующей реализации; без изменения ADR/топологии, без deploy и расшифровки секретов.

## 1. Краткий вывод

**Идею разделения runtime attachment и service exposure стоит принять. Текущую редакцию ADR принимать как готовый контракт реализации и безопасного rollout — рано.**

Гармоничность частичная: разделение двух задач полезно, но требование одинакового `primary/service` представления для всех платформ подменяет общую семантику внешней симметрией. IP интерфейса LXC, RouterOS VIP, Docker host bind и Kubernetes ClusterIP — разные сущности с разными владельцами и жизненным циклом.

Безопасность D14 пока недостаточна:

- NAT/exposure фактически смешаны с разрешением доступа;
- `isolated: true` обещает не то, что делает действующая матрица;
- не определены владелец/ARP сервисного IP, IPAM и исключение VIP из DHCP;
- отсутствует полный контракт host-local enforcement, особенно для Docker и intra-LXC;
- нет безопасной миграционной последовательности и обязательных отрицательных flow tests.

**Рекомендация:** оставить статус Proposed; уточнить ADR до реализации. Не отменять полезный рефакторинг, а сделать его контрактно завершённым.

## 2. Доказательства: проверено заново

Предыдущий отчёт не использовался как доказательство текущего состояния: после него есть новый commit исправлений.

| Проверка | Фактический результат |
|---|---|
| Strict V5Compiler, discover → compile → validate, secrets=passthrough | **0 errors / 0 warnings / 80 infos**, exit 0 |
| `task validate:layers PYTHON=.venv/bin/python` | **PASS**: 62 classes, 140 objects, 189 instances, 29 runtime edges — счётчики валидатора |
| `task validate:adr-consistency PYTHON=.venv/bin/python` | **PASS** |
| 4 профильных integration test files | **51 passed**, 10.57 s |
| Проверка новых диагностических кодов ADR против production code | **10 точных коллизий** |
| Контрпример proposed container_runtime через текущий matrix compiler | `isolated=true` разрешает Internet и same-zone на perimeter plane |
| Проверка proposed VIP .210–.212 против текущей LAN DHCP projection | Все три адреса входят в динамический пул |

Тесты: [test_security_matrix_compiler.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_security_matrix_compiler.py), [test_ip_derivation_compiler.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_ip_derivation_compiler.py), [test_projection_helpers.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_projection_helpers.py), [test_on_directive_object_defaults.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/tests/plugin_integration/test_on_directive_object_defaults.py).

Свежая редактированная копия effective JSON: `/tmp/adr0118-review-c92mcvvs/effective.json`. Proposed-модель туда не мигрировалась; для одного контрпримера зона добавлялась только в памяти.

**Граница доказательств:** зелёные проверки относятся к действующему flat-контракту, не к реализованному ADR 0118. Новые `network.primary/service` consumers и диагностические правила ADR не подтверждены. Полный CI, packet capture, Terraform apply и доступ к устройствам не выполнялись.

## 3. Приоритетные замечания

P1 — исправить до принятия deployment-контракта/rollout; P2 — исправить до стабилизации schema и API. Это риски предлагаемого дизайна, а не утверждения о подтверждённой эксплуатации уязвимости.

### F01 — P1: публикация сервиса не должна автоматически разрешать доступ

**ADR:** D9, D14c–D14e, строки 259–272, 419–492.

D9 показывает DNAT без protocol/ports. D14c сужает пример до UDP/53, но forward accept ограничен только backend IP и портом: не указаны разрешённый источник/ingress, принадлежность конкретной публикации и признак ожидаемого DNAT. Если пакет достигнет этого правила, правило само не отличит разрешённого клиента от другого достижимого источника.

D14d добавляет ещё более широкое `user → container_runtime accept` без портов. А E7883 требует policy override только для повышения security_level. Это не универсальная авторизация сервиса.

**На текущей топологии:** [svc-mosquitto](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-mosquitto.yaml) уже ограничивает allowed_from зонами/сетями IoT и servers; broad user exception не соответствует этому намерению. У [svc-adguard](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-adguard.yaml) DNS и web UI — разные поверхности доступа.

**Рекомендация:**

1. `exposure` описывает механизм доставки, **не permission**.
2. Каждая публикация требует `policy_ref` с source selectors, service/port selectors и enforcement point.
3. DNAT и filter rules строятся из одного normalized flow; сохраняется связь original frontend ↔ translated backend.
4. Нельзя открывать весь backend или все протоколы при отсутствии ports.
5. Ограничение исходной зоны должно учитывать ingress и anti-spoofing, а не только доверять source IP.
6. Незарегистрированная/неразрешимая политика — ошибка, а не предупреждение.

Для RouterOS filter forward работает после dst-nat: правила видят уже преобразованное назначение. Это нужно учитывать в компиляции политик, а не просто добавлять accept перед последним drop. [RouterOS Packet Flow](https://manual.mikrotik.com/docs/firewall-and-quality-of-service/packet-flow-in-routeros/).

### F02 — P1: isolated=true не реализует заявленный запрет исходящих соединений

**ADR:** D14a, строка 400: комментарий «Cannot initiate to external zones».

Проверен реальный [SecurityMatrixCompiler](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/security_matrix_compiler.py), строки 321–410: к текущим зонам добавлена proposed container_runtime, level=4, isolated=true.

| Поток | Результат текущего compiler, perimeter plane |
|---|---|
| container_runtime → untrusted | **ALLOW, R2** |
| container_runtime → container_runtime | **ALLOW, R1** |
| container_runtime → servers | DENY, R2 |
| management → container_runtime | ALLOW, R3 |

Это противоречит обещанному смыслу isolated. На internal plane same-zone имеет другую семантику; нельзя распространять perimeter-результат на все enforcers.

**Рекомендация:** не менять глобальную семантику isolated незаметно, поскольку она уже используется IoT/guest. Ввести явные `ingress_default`, `egress_default`, `intra_zone_default` или эквивалентный policy profile, с ADR-совместимостью. Исходящие DNS/NTP/update/VPN разрешения задавать отдельно.

Единая зона всех контейнеров также объединяет MQTT, management UI, DNS и VPN workers независимо от риска. Лучше группировать workload по роли/допустимым связям; runtime/platform — это placement, а не автоматически уровень доверия. Сетевое расположение само по себе не является основанием доверия по NIST Zero Trust. [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final).

### F03 — P1: сервисные VIP не имеют владельца и конфликтуют с DHCP

**ADR:** D1, D8–D9: VIP `192.168.88.210` → backend `172.18.0.210`.

Одной NAT-записи недостаточно для on-link клиента: нужно определить, кто отвечает за достижимость VIP. Для клиента в том же LAN /24 нужен разрешимый L2 next hop; RFC 826 описывает механизм IP→Ethernet address resolution. **Вывод для этой топологии:** без address owner/ARP announcement клиент может вообще не доставить пакет MikroTik для DNAT. [RFC 826](https://www.rfc-editor.org/rfc/rfc826.html).

Дополнительно [inst.vlan.lan.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.vlan.lan.yaml), строки 15–25:

- DHCP: `192.168.88.10–192.168.88.254`;
- reserved: только `.1–.9`;
- будущие VIP AdGuard/Mosquitto/Tailscale `.210/.211/.212` входят в DHCP;
- текущая MikroTik projection передаёт этот же DHCP range.

**Рекомендация:** объявить address allocation с owner/enforcer, адресное пространство и режим объявления: адрес на конкретном router interface, ограниченный proxy ARP либо routed prefix. Не включать глобальный proxy ARP как универсальное исправление. Исключить VIP из DHCP и общего IPAM, проверять static lease conflicts.

Нужны также обратный маршрут и политика SNAT/hairpin **по реальному пути**, а не обязательный hairpin NAT для всех случаев. Для backend в другом subnet лишний SNAT может лишь скрыть клиента.

### F04 — P1: Docker bind IP и firewall path определены неполно

**ADR:** D12, D14b, строки 319–347 и 416.

Пример публикует Grafana на `10.0.30.210:3000`, но:

1. В текущей топологии servers — **10.0.100.0/24**, не 10.0.30.0/24.
2. Grafana получает `10.0.100.210/24`; Orange Pi имеет management `10.0.99.20`, а intended servers host-address в workload defaults — `10.0.100.23`.
3. Не объявлено, кто назначает дополнительный `10.0.100.210` Docker host и обеспечивает его доступность.
4. Таблица «Host INPUT + forward» недостаточна: обычный Linux bridge port publishing нельзя защищать, полагаясь только на INPUT/ufw.

Docker документирует обработку публикаций firewall/NAT до обычного ufw INPUT/OUTPUT; backend может быть iptables или nftables. [Docker firewall integration](https://docs.docker.com/engine/network/packet-filtering-firewalls/). Для iptables пользовательские ограничения обычно размещаются в DOCKER-USER, где DNAT уже выполнен. [Docker with iptables](https://docs.docker.com/engine/network/firewall-iptables/).

**Рекомендация:** явный `bind_address_ref` на адрес, принадлежащий host, либо отдельный адресный provisioning dependency. Для текущего lab проще публиковать на проверенно назначенном servers-адресе Orange Pi с уникальными портами/reverse proxy, чем создавать VIP каждому контейнеру. Если нужны per-service VIP — это отдельное управляемое действие, не побочный эффект арифметики IP.

Выбор backend и его версия должны быть частью enforcer contract; не переносить DOCKER-USER-рецепт механически на nftables.

### F05 — P1: exposure=none ошибочно приравнен к отсутствию внешнего доступа

**ADR:** D2b–D3: Docker host_network → none → Internal service only.

Host-network контейнер разделяет network namespace хоста; port publish для него не действует. Отсутствие publish rules поэтому не гарантирует отсутствия listener на адресах host. [Docker host network driver](https://docs.docker.com/engine/network/drivers/host/).

Кроме того, Docker-контейнеры одной bridge network могут общаться независимо от внешних публикаций. [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/).

**Рекомендация:** определить `none` как «не создавать publication», не как security property. `host_network` требует явного исключения и host input policy; для RouterOS host-equivalent конфигурации отдельно описать поддерживаемую семантику и версии. Для same-bridge traffic нужен локальный enforcement/сегментация, не только MikroTik perimeter.

### F06 — P1: обход локального enforcement не закрыт D14

**ADR:** D14b–D14c; утверждение, что для L2 достаточно существующих zone rules.

На текущей топологии [inst.security_matrix.proxmox.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml) теперь честно **disabled**, managed_by_ref закомментирован. Это изменение после прежнего аудита. Но enforcement от отключения не появился; у 9 LXC остаётся `firewall: false` в host defaults [srv-gamayun.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/srv-gamayun.yaml), строка 24.

Контейнеры в одном L2 сегменте не обязательно проходят через perimeter router. RouterOS также различает bridge и routed packet paths; отправка bridged traffic в IP firewall требует отдельной настройки и имеет CPU cost. [RouterOS Packet Flow](https://manual.mikrotik.com/docs/firewall-and-quality-of-service/packet-flow-in-routeros/).

**Рекомендация:** каждой security guarantee сопоставлять конкретный enforcer/path. До PVE firewall реализации не заявлять меж-LXC default deny. Для Docker — host-local enforcement; для RouterOS — проверить actual bridge/veth path и control-plane INPUT отдельно от forwarding.

## 4. Гармоничность представления и внутренние противоречия

### F07 — P2: общая модель должна быть ортогональной, не обязательно симметричной

**ADR:** D1–D3, D11–D13, A3.

`bridge` и `dedicated_veth` — не полностью взаимоисключающие понятия: veth — интерфейс, bridge — способ его подключения. В свежем IR AmneziaWG уже имеет dedicated_veth и унаследованный bridge_ref одновременно.

Проблемы forced symmetry:

- IP LXC — свойство attachment; он нужен и контейнеру без опубликованного сервиса.
- Gateway LXC в D11 отсутствует, а D5 объявляет service._resolved_gateway только документационным.
- Сервисов/публикаций у workload может быть 0..N, не один service block.
- Существующие L5 services уже содержат ports, allowed_from и runtime target: их дублирование внутри L4 создаёт второй источник истины.
- ADR 0041 сохраняет typed `networks[]`; ADR 0118 не определяет совместимость или supersession.
- Отказ от всех capability checks в A3 не нужен: каталог уже имеет `cap.workload.network.bridge/macvlan/host`. Не нужен новый параллельный namespace, но нужен проверяемый support contract.

**Рекомендация:** три независимые сущности: **attachments[] → endpoints/publications[] → policies**. `primary` оставить удобным shorthand/default attachment, а не ограничением cardinality. Типы backend-specific возможностей проверять через существующую capability-модель и feature support table.

### F08 — P2: Kubernetes включён декларативно, но не смоделирован

**ADR:** D2b: cni + ingress → ClusterIP; D1: cni_network=calico.

CNI attachment, Service ClusterIP и HTTP ingress — разные уровни. ClusterIP относится к Service, а не является IP ingress controller или VLAN-derived IP. [Kubernetes Service](https://kubernetes.io/docs/concepts/services-networking/service/).

Ingress покрывает HTTP(S), не универсальную публикацию DNS/MQTT. Для новых дизайнов Kubernetes рекомендует Gateway API; Ingress API frozen. [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/).

**Рекомендация:** K8s — explicit future extension point, не поддерживаемая платформа v1. Не навязывать Kubernetes vlan_ref+host. Когда появится реальный кластер: separate Pod attachment, Service, Gateway/routes, NetworkPolicy; проверять наличие CNI enforcement. NetworkPolicy без реализующего контроллера не защищает, ingress/egress isolation независимы. [Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/).

### F09 — P2: диагностические коды уже заняты

Точные совпадения в текущем production code:

| Предлагаемый код | Действующий consumer |
|---|---|
| W7870 | security_matrix_compiler.py:97 — matrix without zone_refs |
| E7871, E7872, E7873 | vm_refs_validator.py — device/trust-zone/OS refs |
| E7875, E7876, E7877 | vm_refs_validator.py — существующие VM contracts |
| E7880, E7881, E7883 | lxc_refs_validator.py — normalized rows и refs |

Источники: [vm_refs_validator.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/vm_refs_validator.py), [lxc_refs_validator.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/validators/lxc_refs_validator.py), [security_matrix_compiler.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/compilers/security_matrix_compiler.py).

**Рекомендация:** выделить свободный диапазон через error catalog governance. Не считать совпадение номера новым validator implementation. Остальные комбинации severity/number тоже проверить перед резервированием.

### F10 — P2: примеры и правила ADR противоречат друг другу

- D8 DNAT example не содержит ports, но D14 E7880 требует их.
- D9 NAT разрешает все протоколы/порты; D14 уже требует ограничения.
- W7874 сравнивает service gateway и primary gateway, хотя разность нормальна при DNAT.
- W7882 оставляет отсутствие зоны в enforcement address_space предупреждением, хотя ADR обещает security integration.
- W7878 требует service/default; D10 специально разрешает primary-only.
- D10 говорит «no changes needed», но перенос flat полей под primary сам является миграцией.
- D11/D12 используют устаревшую сеть 10.0.30.0/24.
- После переразмещения IP у LXC не определён источник gateway/default route.
- Docker bridge named `docker0`, engine default network `bridge` и Compose named network не следует считать одним идентификатором.

**Рекомендация:** все примеры ADR сделать executable fixtures, прогоняемыми schema/compiler/projection tests. Для необязательной публикации — отсутствие side effects, не platform-default auto-exposure. Для отсутствующего enforcer — hard error в security-enforced профиле.

## 5. Применение к текущей топологии

Инвентарь: **24 workload: 6 RouterOS + 9 Docker + 9 LXC**, дополнительно **3 Docker stack instances**. В ADR планирует 5 RouterOS и 10 Docker; scope надо пересчитать, не мигрировать только перечисленные пять.

### RouterOS / rtr-mikrotik-chateau

| Workload | Что есть сейчас | Рекомендуемая трактовка |
|---|---|---|
| docker-adguard | LAN .210 + internal gateway conflict; svc-adguard объявляет UDP/TCP 53 и UI 3000 | Runtime attachment отдельно; DNS publications UDP и TCP; UI только management; VIP/ARP/DHCP lifecycle явно |
| docker-mosquitto | LAN .211 + internal gateway conflict; L5 allowed_from=IoT,servers; TLS | Отдельный backend; publications из svc-mosquitto, а не blanket user→runtime; 8883/TLS, 1883 только при обоснованном исключении |
| docker-tailscale | LAN .212 + gateway conflict; L5 mesh/exit-node/subnet-routing features | Не мигрировать автоматически в DNAT: сначала определить outbound node, subnet router или exit node; явно описать routed prefixes и ACL |
| docker-nginx | veth1 / 172.18.0.2; observed_runtime содержит tcp 8080→80 | Включить шестым workload в migration fixtures; frontend bind/source policy явно, не оставлять широкий legacy NAT |
| docker-amneziawg-russia | 172.18.22.2/30 → .1 | Сохранить routed/egress intent и mapping к VPN-Russia, не делать frontend DNAT |
| docker-amneziawg-sweden | 172.18.23.2/30 → .1 | Аналогично; regression tests на exit route и запрет обхода при падении tunnel |

Источник: [RouterOS workload inventory](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau).

**Уточнение root cause ADR:** два адресных пространства действительно полезно разделить, но действующая топология не доказывает, что .210/.211/.212 уже обслуживаются через DNAT. В [router observed_runtime.nat](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml) явно есть port forward nginx 8080→172.18.0.2:80; DNAT для этих трёх VIP в прочитанном наборе отсутствует. `observed_runtime` — сохранённое описание, не live inspection. Root cause следует формулировать как **неоднозначность attachment/exposure intent**, а NAT — как выбранный target design, не установленный факт.

### Docker / srv-orangepi5

Девять контейнеров: adguard-secondary, alertmanager, grafana, homeassistant, jellyfin, loki, nextcloud, portainer, prometheus.

- Сейчас их service-like IP лежат в **10.0.100.0/24**.
- Сохранить management address **10.0.99.20** отдельно от серверных публикаций.
- Для Grafana/Nextcloud/Jellyfin предпочтителен один управляемый frontend/reverse proxy с backend endpoints; не создавать per-container VIP без необходимости.
- Portainer — management-only, не публикация всей user zone по умолчанию.
- Prometheus/Loki/Alertmanager — локальная observability policy, не public port_publish default.
- Home Assistant: если реально требуется multicast/discovery, выбрать поддерживаемый attachment/relay; не включать host_network автоматически.
- Действующий [docker_compose_generator.py](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology-tools/plugins/generators/docker_compose_generator.py) читает flat network.ports и отдельный networks; одной перестановки source YAML недостаточно.
- Три stack instances требуют проверки member_refs, host placement и output grouping, хотя не являются отдельными контейнерами.

Источник: [Docker/stack inventory](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/docker), [srv-orangepi5.yaml](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/srv-orangepi5.yaml).

### LXC / srv-gamayun

Сохранить существующие direct attachments в servers VLAN 100 / 10.0.100.0/24. **Не добавлять NAT ради унификации.**

- lxc-grafana: **10.0.100.60/24**, gateway **10.0.100.1**.
- lxc-postgresql: .10; lxc-redis: .20; lxc-nginx-proxy: .80; lxc-docker: .90.
- Адрес, gateway, VLAN tag и firewall flag должны остаться свойствами attachment и полностью попасть в Proxmox output.
- L5 endpoints ссылаются на attachment address, не создают его второй раз.
- lxc-docker требует возможности chained exposure/enforcement для вложенных workload, но текущий инвентарь не доказывает наличие вложенных Docker instances на нём.

Источник: [LXC inventory](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/lxc), [PVE projection](//wsl.localhost/NixOS/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/projections.py). Intra-zone enforcement остаётся отдельной незавершённой работой.

## 6. Предлагаемый гармоничный контракт

Это **эскиз для изменения ADR**, не YAML, уже принимаемый текущим compiler.

### 6.1 Разделение ответственности

| Слой модели | Владелец данных | Смысл |
|---|---|---|
| Network/address space | L2 network instance | CIDR, VRF/namespace, zone, IPAM, gateway |
| Attachment | L4 workload | interface/driver, network_ref, allocation, routes |
| Service | L5 service instance | protocol/ports, backend target, auth/TLS intent |
| Publication | Endpoint reference to service | frontend allocation/bind, backend attachment, mechanism, enforcer |
| Security policy | Security model | кто/куда/на какие порты; ingress, egress, intra-zone |
| Projection | Compiled IR | resolved addresses, ownership, packet path, normalized flow rules |

Не обязательно создавать отдельный C→O→I объект для каждого endpoint: v1 может хранить typed publication records в service. Важно сохранить один источник истины и stable IDs.

### 6.2 Нормализация вместо копирования IP

```yaml
# Псевдоконтракт: предлагаемые поля/ID, ещё не реализованы.
# L4 docker-adguard:
network:
  primary_attachment: backend
  attachments:
    - id: backend
      driver: veth
      network_ref: inst.bridge.containers
      address:
        allocation: static
        host: 210
      gateway: derive_from_network

# L5 svc-adguard:
publications:
  - id: dns
    backend_attachment: backend
    mechanism: dnat
    frontend:
      network_ref: inst.vlan.lan
      host: 210
      address_owner_ref: rtr-mikrotik-chateau
      announcement: interface_address
    ports:
      - {protocol: udp, frontend: 53, backend: 53}
      - {protocol: tcp, frontend: 53, backend: 53}
    policy_ref: proposed.policy.dns-approved-clients
    enforcer_ref: rtr-mikrotik-chateau
```

Перед использованием .210 нужно исправить DHCP/IPAM; совпадение frontend/backend host number — удобство примера, **не инвариант**. UI оформить отдельной publication с management policy. Конкретные ID, announcement field и protocol schema необходимо согласовать с ADR/key registry.

Для LXC publication типа direct ссылается на attachment address. Для Docker host_publish ссылается на **host-owned bind address**. Для routed VPN вместо фиктивного service IP нужны advertised/served prefixes и route-policy refs.

### 6.3 Обязательные инварианты

1. Gateway принадлежит attachment subnet или есть явный on-link/route exception; сравнение unrelated frontend/backend gateway запрещено.
2. IPAM scope = routing domain / host namespace / network, не глобальная уникальность всех Docker private CIDR.
3. Frontend address имеет owner/announcement; VIP не пересекается с DHCP и другими allocations.
4. Bind collision проверяется по owner + address family + IP + protocol + port, учитывая wildcard bindings.
5. Публикация не создаёт permission; нужен подтверждённый policy и enforcer.
6. Backend ports структурированы, protocol обязателен; port remap не теряется.
7. Direct/host/none не означают автоматической безопасности; нужны ingress/egress/intra-zone policies.
8. Unknown network/zone, missing enforcement и unsupported feature — fail closed.
9. IPv6 либо поддерживается с паритетом правил, либо явно disabled/unsupported; нельзя гарантировать изоляцию только для IPv4.
10. MTU, return path, route policy и DNS dependencies проверяются для tunnel/nested cases.
11. Resource-address identity сохраняется при миграции; новый IR не должен случайно удалять существующие Terraform resources.
12. Детерминированные projections читают effective JSON/published contracts, не повторно YAML-файлы.

## 7. Оценка по современным security principles

Это сопоставление с рекомендациями, **не сертификация соответствия NIST/CIS**. «Современные» означает актуальную практику и актуальность источников на дату проверки, а не обязательно новый год публикации документа.

| Принцип | Состояние ADR 0118 | Что добавить |
|---|---|---|
| Least privilege / explicit authorization | Частично: есть D14, но broad accept и implicit trust | Service-specific flow policies, source selectors, default deny |
| Defense in depth | Runtime и publication разделены, local enforcement неполон | Host/PVE enforcement, control-plane ACL, runtime hardening |
| Fail closed | Missing zone = warning; defaults могут скрыть неполноту | Error для отсутствующего security path |
| Address/identity integrity | IP арифметика без owner/IPAM lifecycle | Address ownership, reservations, DHCP/bind collision checks |
| East-west isolation | Общая runtime zone не гарантирует microsegmentation | Workload groups и локальные policies |
| Auditability | Не описан original/translated flow lineage | Stable rule IDs, source provenance, counters/logging, policy diff |
| Safe change | Миграция инстансов раньше consumers/security | Atomic dependency closure, canary, rollback и negative tests |
| Container host protection | В основном вне scope | Явные prerequisite/related hardening requirements |

Сетевой ADR не обязан реализовывать весь container security stack, но должен обозначить ограничения: immutable/pinned image identity, provenance/scanning, least privilege runtime, resource limits, secrets isolation и patch lifecycle. NIST отдельно рассматривает безопасность контейнеров как более широкий набор проблем, чем сеть. [NIST SP 800-190](https://csrc.nist.gov/pubs/sp/800/190/final).

Для данного lab особенно важен blast radius: шесть контейнеров размещены на perimeter MikroTik. Производитель прямо предупреждает о рисках сторонних образов для безопасности RouterOS host. **Моя рекомендация:** после ресурсной оценки оставить на router только необходимые network/VPN workloads; перенос обычных приложений на compute host уменьшит связанность отказов, но не является обязательным условием принятия schema. [RouterOS Container security disclaimer](https://manual.mikrotik.com/docs/containers/).

## 8. План доработки ADR и внедрения

### До принятия ADR

1. Исправить F01–F06: policy ≠ exposure; isolated semantics; address ownership; host-local enforcement.
2. Зафиксировать attachments + publications + policy refs; primary оставить shorthand.
3. Ограничить v1 реально имеющимися RouterOS/Docker/LXC; K8s оставить extensibility note.
4. Исправить примеры, gateway rules, занятые diagnostics и migration inventory.
5. Уточнить связь/supersession ADR 0041 и изменения ADR 0107/0110/0111; REGISTER и rule packs обновлять при принятии.
6. Указать out-of-scope и threat model. Оценку «36h» не считать достоверным планом до acceptance matrix.

### Порядок реализации

В текущем Migration Path объекты/instances обновляются раньше generators, security validators включаются позже NAT. Так возникает окно семантически неполной генерации.

Безопаснее:

1. Versioned canonical IR + schema + adapters, без изменения deployed output.
2. Validators и policy/address ownership contracts.
3. Все нужные consumers: IP derivation, MikroTik projection/NAT/filter, Docker Compose/host policy, Proxmox attachment.
4. Regression snapshots и normalized flow comparison old→new.
5. Миграция source с reject mixed flat/nested, без молчаливого deep-merge старых и новых gateway.
6. Build immutable candidate bundle; deployment preflight; staged canary.
7. При rollout обеспечить filters/address reservations **до включения публикаций**, health checks и recovery channel.
8. После паритета удалить legacy adapter и включить strict-only schema.

Для RouterOS policy-routed VPN отдельно проверить FastTrack и connection tracking: FastTrack способен обходить ряд processing facilities; он не должен нарушать routing-mark/kill-switch поведение. Это отдельный regression case, не повод отключать ускорение глобально без измерений. [RouterOS Packet Flow / FastTrack](https://manual.mikrotik.com/docs/firewall-and-quality-of-service/packet-flow-in-routeros/).

## 9. Минимальная acceptance matrix

| Сценарий | Ожидание |
|---|---|
| AdGuard DNS от разрешённого клиента UDP **и TCP** 53 | ALLOW; сохраняется корректный return path |
| AdGuard UI от user/IoT/guest | DENY; management допускается отдельной policy |
| Mosquitto TLS от declared IoT и servers | ALLOW; auth/TLS сохранены |
| Mosquitto от незаявленного user/WAN | DENY, даже если существует DNAT |
| Прямой доступ к backend IP в обход VIP | DENY, если policy разрешает только publication |
| Контейнер → router management API/SSH | DENY по умолчанию |
| Same-bridge и same-VLAN lateral traffic | Соответствует intra-zone policy, проверяется локально |
| runtime → Internet без egress exception | DENY в предлагаемом default-deny профиле |
| Duplicate VIP / VIP в DHCP / host bind collision | Compile/preflight ERROR |
| host_network + exposure=none | Нет ложного обещания isolation; host policy обязательна |
| LXC без publication | IP/gateway сохранены, сервисы не открываются автоматически |
| AWG Russia/Sweden при живом и упавшем tunnel | Правильный exit; запрещён непредусмотренный fallback |
| IPv6, wildcard bind, NAT port remap | Нет обхода IPv4 policy и потери port semantics |
| Nested Docker-in-LXC | Каждый hop имеет address owner и enforcer; проверяется при появлении workload |
| Все 6 RouterOS / 9 Docker / 9 LXC | Нет пропущенных миграций; 3 stacks сохраняют membership |
| Rollback | Сохраняет management access, IP ownership и resource identity |

**Итоговое решение ревью:** **Request changes для ADR 0118; поддержать направление, не принимать текущую security semantics и rollout plan без доработки.** Главный полезный шаг — не «две сети у каждого контейнера», а **явный граф attachment → endpoint → policy → enforcement**.
