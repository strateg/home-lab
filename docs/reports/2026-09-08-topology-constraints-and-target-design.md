# Аудит ограничений топологии и предложение целевого состояния

**Дата:** 2026-09-08.  
**Репозиторий:** /home/nixos/workspaces/home-lab (WSL NixOS).  
**HEAD:** c9a7cab8cd25d4398c7a07c1828cefabcc66c666.  
**Объём:** 185 instances в 19 группах; исходные Class → Object → Instance, свежая effective model, relevant compiler/validator/projection contracts.  
**Режим:** анализ и предложение. Топология, generated, model.lock и устройства не изменялись. Секреты SOPS не расшифровывались.

## 1. Вывод

**Улучшение нужно, но полная смена VLAN/IP-плана не требуется.** У десяти VLAN нет пересекающихся CIDR, а среди проверенных вычисленных network._resolved_ip не обнаружено дублей. Главные проблемы — рассогласованные источники адресации, неполное enforcement, открытые секреты и ссылки/политики, которые не охвачены штатной проверкой.

Нельзя считать текущую топологию готовой к строгому воспроизводимому развёртыванию:
- стандартный task build:compile-validate: **0 errors, 21 warnings**;
- та же цепочка discover → compile → validate с **strict_model_lock=True**: **7 errors, 14 warnings**;
- дополнительно подтверждены проблемы, которые эта проверка не обнаруживает.

Это аудит **декларативной модели**, не сканирование реальных устройств. Статусы active/observed_runtime не доказывают актуальное состояние оборудования. Ниже явно различаются нарушения контракта, противоречия модели, риски и предложения.

## 2. Приоритетные находки

### T01 — P1 / нарушение secrets contract: открытые Wi-Fi passphrase в Git

Места: [projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml:152](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml#L152) и [projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml:166](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml#L166).

Два значения passphrase записаны открытым текстом в observed_runtime Wi-Fi конфигурациях. Значения намеренно не включены в рапорт. Поле observed_runtime не является исключением из secrets policy.

**Ограничение:** CORE-006 / SEC-001, [docs/ai/rules/secrets.md](/home/nixos/workspaces/home-lab/docs/ai/rules/secrets.md).  
**Что сделать:** сменить оба секрета, перенести новые значения в SOPS, оставить approved secret references/placeholders. Удаление значений из HEAD не отменяет их присутствия в Git history. Историю не переписывать автоматически: это отдельная согласованная операция. Добавить сканирование чувствительных полей во всех topology subtrees, включая observed_runtime.

### T02 — P1 / нарушен strict model-lock: 7 ошибок на шести уникальных references

Строгий запуск выдаёт E3201 для:
- obj.device.sony_bravia_a90j;
- class.peripheral.usb_hub_ethernet;
- obj.peripheral.bluecloud.usbc_hub_gbe;
- class.peripheral.usb_wifi_adapter;
- obj.peripheral.asus.usb_ax55_nano;
- obj.service.amneziawg — используется двумя service instances, поэтому две ошибки.

Места использования: [projects/home-lab/topology/instances/devices/inst.device.tv-sony-bravia.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/inst.device.tv-sony-bravia.yaml), [projects/home-lab/topology/instances/peripherals/inst.peripheral.usb_hub_eth.bluecloud-001.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/peripherals/inst.peripheral.usb_hub_eth.bluecloud-001.yaml), [projects/home-lab/topology/instances/peripherals/inst.peripheral.usb_wifi.asus-ax55-nano-001.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/peripherals/inst.peripheral.usb_wifi.asus-ax55-nano-001.yaml), [projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-amneziawg.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-amneziawg.yaml), [projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-amneziawg-sweden.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-amneziawg-sweden.yaml).

**Что сделать:** проверить нужные версии definitions и согласованно обновить [topology/model.lock.yaml](/home/nixos/workspaces/home-lab/topology/model.lock.yaml). Не отключать strict mode для закрытия ошибки. Framework lock и model.lock — разные контракты.

### T03 — P1 / адресация: все 9 LXC наследуют gateway старой сети

[projects/home-lab/topology/instances/devices/srv-gamayun.yaml:23](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/srv-gamayun.yaml#L23) задаёт workload_defaults.network.gateway = 10.0.30.1. Но canonical servers object задаёт VLAN 100, 10.0.100.0/24, gateway 10.0.100.1: [topology/object-modules/network/obj.network.vlan.servers.yaml](/home/nixos/workspaces/home-lab/topology/object-modules/network/obj.network.vlan.servers.yaml).

Свежий effective row lxc-postgresql:
- network._resolved_ip = 10.0.100.10/24;
- network.gateway = **10.0.30.1**;
- network._resolved_gateway = **10.0.100.1**.

Та же противоречивая пара gateway присутствует у всех девяти LXC. Старый адрес не входит в вычисленную /24. Дополнительно typed Proxmox projection читает именно network.gateway: [topology/object-modules/proxmox/plugins/projections.py:204](/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/projections.py#L204). Это подтверждённое противоречие IR и риск неверного consumer output; реальная connectivity LXC не проверялась.

**Ограничение:** ADR0111 — generator должен потреблять _resolved_ip/_resolved_gateway, а изменение CIDR не должно требовать ручной перенумерации workloads.

**Что сделать:** сохранить servers 10.0.100.0/24; убрать устаревший gateway из host defaults либо временно синхронизировать с canonical VLAN. Затем обеспечить единый resolved gateway для всех consumers и проверку mismatch. Одно исправление gateway в YAML без фикса потребления лишь уменьшит текущий drift.

Также RouterOS workloads docker-adguard, docker-mosquitto, docker-tailscale одновременно имеют bridge_ref containers (172.18.0.0/24), gateway 172.18.0.1 и derived IP в LAN 192.168.88.0/24. Если это routed topology, в модели не выражена достаточная связь между этими L3 сегментами. Нужно выбрать однозначное размещение: LAN-attached veth либо routed container subnet, а не смешивать оба.

### T04 — P1 / enforcement gap: заявленная Proxmox isolation не реализована

[projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml) обещает deny lateral movement с ограниченными исключениями. Однако:
1. host defaults устанавливают network.firewall: false, и это наследуется всеми 9 LXC;
2. свежая Proxmox projection возвращает zones={}, matrix={}, policy_overrides=[], status="stub";
3. [topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py](/home/nixos/workspaces/home-lab/topology/object-modules/proxmox/plugins/generators/firewall_proxmox_generator.py) всё ещё stub; manifest также помечает его как не реализованный.

**Вывод:** наличие security_matrix instance не обеспечивает CT-level policy через этот pipeline. Не утверждается, что на живом Proxmox нет вручную настроенных правил — это не проверялось.

Официальная документация отдельно требует firewall enable на virtual NIC и общий enable. Поэтому одного YAML matrix недостаточно. [Proxmox firewall documentation](https://raw.githubusercontent.com/proxmox/pve-docs/master/pve-firewall.adoc).

**Что сделать:** реализовать и проверить CT-level enforcement либо явно исключить эту гарантию из operational/readiness до реализации. Включать firewall только вместе с разрешёнными management/DNS/application flows и rollback-доступом.

Ещё одна семантическая проблема: названия overrides “Prometheus → all”, “Nginx → backends” не ограничивают источники конкретными workloads. Реальные selectors — servers zone → servers zone. Нужны endpoint/role-scoped правила, иначе любой участник зоны получает те же разрешённые порты.

### T05 — P1/P2 / политика безопасности: избыточный admin-доступ и потерянное HTTP-исключение

**Избыточный доступ — риск, а не нарушение синтаксиса R6.**  
[projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml:75](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml#L75) разрешает всю LAN 192.168.88.0/24 → management без ports/destination restrictions. Свежая projection разрешает src_vlan_ref в этот /24; template выводит безусловный по портам accept.

Комментарий о доступе операторской станции не соответствует масштабу разрешения. Аналогично user-to-servers-db даёт всей user zone TCP 5432/6379 ко всей servers zone.

**Что сделать:** дать operator/controller identity или approved management addresses только нужные target/ports; database доступ — только приложениям и оператору через управляемый путь. Само нахождение в LAN не должно означать административное доверие. [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final).

**Потерянное исключение — подтверждённое расхождение намерения и projection.**  
[projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml:45](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml#L45) комментирует наследование user-to-servers-http из object. Оно определено в [topology/object-modules/network/obj.network.security_matrix.soho.yaml](/home/nixos/workspaces/home-lab/topology/object-modules/network/obj.network.security_matrix.soho.yaml). Но в свежей MikroTik projection остаются только четыре instance overrides; HTTP/HTTPS override отсутствует. User→servers cell содержит только ports 5432/6379.

Причина включает различие размещения object-level policy_overrides и того, откуда helper их читает. **Что сделать:** определить проверяемую merge-by-name семантику object+instance и test ожидаемого HTTP allow. Временное явное дублирование правила в instance допустимо лишь как обозначенная мера, не новый второй источник истины.

### T06 — P2 / VPN policy: trust_level не управляет security_level, overlay CIDR не попадает в zone projection

[projects/home-lab/topology/instances/network/inst.trust_zone.vpn_exit.yaml:18](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/network/inst.trust_zone.vpn_exit.yaml#L18) задаёт trust_level: 0, но matrix engine использует security_level. Из родительского объекта получается **security_level=2**, а не 0.

Дополнительный probe: установка instance_data.security_level=0 в копии IR **всё ещё дала 2** в MikroTik projection из-за “value or object_default” в [topology/object-modules/mikrotik/plugins/projections.py:637](/home/nixos/workspaces/home-lab/topology/object-modules/mikrotik/plugins/projections.py#L637). Поэтому простая замена названия YAML-поля не завершает исправление.

В этом же instance additional_networks содержит WireGuard overlay 10.100.1.0/24, но CIDR-list свежей zone projection содержит только 192.168.56.0/24. Не следует считать overlay покрытым zone CIDR rules. Отдельные interface/baseline правила могут частично компенсировать это; их наличие не заменяет согласованность matrix.

**Что сделать:**
- отдельная canonical vpn_exit zone с security_level=0, isolated=true;
- None-aware обработка 0/false вместо boolean fallback;
- включение VLAN и overlay CIDRs в один объявленный zone-address contract;
- отдельные admin VPN и exit-only VPN, с отрицательными connectivity tests.

Не утверждается доказанная утечка трафика на живом router: найдены расхождения модели и enforcement input.

### T07 — P2 / неполные references: 11 вхождений вне активного inventory

Независимый обход критических *_ref/*_refs в source YAML обнаружил:
- 3 отсутствующих Wi-Fi ACL device IDs: inst.device.boox_go103_lumi, inst.device.laptop_katana, inst.device.tv_sony_bravia — [projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml:113](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml#L113);
- inst.trust_zone.lan в router workload_defaults — [projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml:268](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml#L268);
- ws-nixos в road-warrior peers обоих tunnels;
- mikrotik-chateau вместо rtr-mikrotik-chateau в пяти data assets: adguard, mosquitto, tailscale, wireguard, mikrotik_config.

Это отсутствие в активных class/object/instance IDs, **не** доказательство отсутствия внешнего устройства. Если внешний ID допустим, он должен иметь отдельный явно проверяемый external-reference contract.

**Что сделать:** нормализовать BOOX/TV refs к существующим canonical IDs, описать laptop/ws-nixos либо удалить неактуальные refs; выбрать существующую zone для router containers; исправить owner refs пяти assets. Nested refs в observed_runtime и peer lists также должны валидироваться.

### T08 — P2 / physical topology: uplink ссылается на неисправный интерфейс

[projects/home-lab/topology/instances/physical-links/inst.ethernet_cable.chateau_to_orangepi5.yaml:14](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/physical-links/inst.ethernet_cable.chateau_to_orangepi5.yaml#L14) и [projects/home-lab/topology/instances/data-channels/inst.chan.eth.chateau_to_orangepi5.yaml](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/data-channels/inst.chan.eth.chateau_to_orangepi5.yaml) имеют endpoint_b.port=end1. Но object inventory помечает end1 degraded/non-functional, а host network указывает USB-Ethernet peripheral.

Сеть фактически **описана двумя несовместимыми способами**, независимо от живого link state. В notes servers VLAN также упоминается ether5, тогда как cable/channel/switch_port задают ether3.

**Что сделать:** представить действующий peripheral-backed Ethernet endpoint в canonical interface inventory и ссылаться на него из cable/channel/network. Комментарий “actual USB adapter” не должен заменять endpoint relation. Сохранить ether3 как текущий согласованный кандидат, физическую коммутацию подтвердить перед cutover.

### T09 — P2 / backup topology: разрыв producer→offsite и неполное coverage

- [projects/home-lab/topology/instances/operations/backup-mikrotik-config.yaml:18](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/operations/backup-mikrotik-config.yaml#L18) пишет config export в Git repository path.
- [projects/home-lab/topology/instances/operations/backup-offsite-weekly.yaml:17](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/operations/backup-offsite-weekly.yaml#L17) забирает /mnt/hdd/backups/mikrotik.
- В просмотренной operation topology нет declared transfer между этими путями.
- [projects/home-lab/topology/instances/operations/backup-weekly-full.yaml:12](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/operations/backup-weekly-full.yaml#L12) называется полным backup всех LXC, но перечисляет только PostgreSQL и Redis — **2 из 9 LXC**.
- В пяти router data assets ещё и неверный host_ref (T07).

Это **пробел декларативного backup graph**, не утверждение об отсутствии внешней ручной backup-задачи.

**Что сделать:** связать export artifact → staging location → offsite target через declared refs/paths; либо переименовать weekly job в DB-only, либо расширить coverage нужных assets. Задать RPO/RTO и restoration test для каждого critical asset. Offline/immutable copy и тест восстановления нужны отдельно от самого наличия offsite job. [CISA StopRansomware Guide](https://www.cisa.gov/stopransomware/ransomware-guide).

### T10 — P2 / service-runtime contract и воспроизводимость

Штатные warnings подтверждают:
- svc-amneziawg и svc-amneziawg-sweden используют runtime.type=container вне enum; canonical family здесь routeros_container;
- svc-postgresql-germany привязан к vpn_germany VLAN, хотя target описан как доступный по routed WireGuard overlay, не непосредственно attached к этому VLAN.

Нужно исправить тип и target binding AmneziaWG согласно runtime contract, а PostgreSQL выразить через реальный overlay/reachability contract. Не объявлять VPS участником локальной L2 VLAN только для подавления warning.

Есть конфликт image для одного workload:
- [projects/home-lab/topology/instances/docker/srv-orangepi5/docker-nextcloud.yaml:12](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/docker/srv-orangepi5/docker-nextcloud.yaml#L12): nextcloud:latest;
- [projects/home-lab/topology/instances/services/srv-orangepi5/svc-nextcloud@docker.srv-orangepi5.yaml:42](/home/nixos/workspaces/home-lab/projects/home-lab/topology/instances/services/srv-orangepi5/svc-nextcloud@docker.srv-orangepi5.yaml#L42): nextcloud:28.

**Что сделать:** один canonical image/version/digest owner; service должен ссылаться на runtime, а не независимо выбирать его образ. Конкретную версию выбирать после совместимости/backup checks, не подменять произвольным latest.

## 3. Неполнота модели, которую нельзя превратить в доказанную аварию

1. **Capacity.** В проверенных definitions двух compute hosts нет измеренных CPU/RAM/storage capacity, достаточных для доказательства безопасного размещения. Есть LXC resource_profile_ref и размеры отдельных дисков, но это не host admission budget. Поэтому ниже не обещаются новые нагрузки без sizing.
2. **Lifecycle.** Effective model: pending=153, planned=6, active=18, staged=7, disconnected=1; при этом project.yaml обозначает operational/migrated-hard, а topology.meta ещё migration. Pending часто возникает по default, поэтому это не равно “153 устройства не работают”. Но состояние desired/observed/deployable надо разделить.
3. **Дубли сервисов.** Nextcloud, Home Assistant, Grafana и Prometheus представлены и LXC, и Docker deployment variants. Само дублирование допустимо. Не определены достаточно явно primary/standby, data ownership и критерии cutover; нельзя считать это HA автоматически.
4. **Control plane на workload host.** Orange Pi заявлен infrastructure controller и одновременно хостит web/media services. Это увеличивает последствия компрометации workload. Разделение privileges/credentials предпочтительнее простой VLAN-метки на том же хосте.
5. **Availability.** Один edge router и один Proxmox host остаются single points of failure. Для домашней лаборатории это может быть допустимым бюджетным решением; покупка второго узла не является обязательным результатом этого аудита.

## 4. Предлагаемая улучшенная топология

### 4.1. Принцип: сначала согласованность, затем усложнение

Сохранить существующие устройства и основную нумерацию. Не добавлять кластер, Kubernetes, новые VLAN или оборудование ради формального “улучшения”.

Предложение ниже — **целевой design**, не готовый к применению YAML и не уже проверенный deploy plan. Нельзя применить его только topology edits: T04/T05/T06 требуют исправления consumer/enforcement contracts. Для принятого архитектурного изменения обновить relevant ADR и adr/REGISTER.md.

### 4.2. Сегменты

| Segment | VLAN / CIDR | Целевое назначение |
|---|---|---|
| Legacy LAN | native 1 / 192.168.88.0/24 | Временный migration segment; не management trust |
| User | 10 / 192.168.10.0/24 | Обычные пользовательские устройства |
| Guest | 20 / 192.168.20.0/24 | Internet-only + необходимые DNS/DHCP |
| IoT | 30 / 192.168.30.0/24 | Home automation devices; только нужные application flows |
| Management | 99 / 10.0.99.0/24 | Router admin, Proxmox, controller; доступ только approved operator path |
| Servers | 100 / 10.0.100.0/24 | Единственный текущий servers CIDR для LXC/Docker services |
| VPN Germany | 55 / 192.168.55.0/24 | Exit-policy segment |
| VPN exit physical | 56 / 192.168.56.0/24 | Сохранять лишь при подтверждённой потребности в physical VLAN |
| VPN Russia | 57 / 192.168.57.0/24 | Отдельный exit path |
| VPN Sweden | 58 / 192.168.58.0/24 | Отдельный exit path |

Overlay 10.100.0.0/24 и 10.100.1.0/24 моделировать как L3 tunnel networks, **не смешивать с physical VLAN**. Если VLAN56 не несёт реального L2 трафика и используется только как proxy для zone membership, после добавления overlay contract его можно убрать; сейчас не удалять, пока потребители зависят от VLAN.

### 4.3. Хосты и роли

| Узел | Предлагаемая роль | Изменения |
|---|---|---|
| rtr-mikrotik-chateau | Edge routing, VLAN, DHCP/DNS forwarding, VPN, perimeter enforcement | Не использовать как общий application host; оставить только оправданные routing-related containers. Перенос AdGuard/MQTT/Tailscale — отдельный cutover с fallback |
| srv-gamayun | Stateful/core LXC: PostgreSQL, Redis, reverse proxy, Gitea; предпочтительный primary Nextcloud | Единая servers сеть, gateway .100.1, CT firewall enforcement; проверить capacity до консолидации |
| srv-orangepi5 | Edge/media/automation и secondary monitoring/DNS | Исправить USB NIC inventory; не смешивать admin credentials с публичными workload privileges |
| Изолированный controller runtime | Управление topology/Ansible/Terraform | Отдельный доверенный runtime с минимальными правами; VM на существующем Proxmox возможна после sizing. Recovery должен работать и без этой VM |
| Cloud VPS | Явно разделённые admin/exit overlays | PostgreSQL binding через фактический overlay; запрет exit-only peers → management/server networks |
| Backup plane | Local staging → offsite, отдельные restoration checks | Согласованные artifact paths и owner refs; critical asset coverage вместо предположения “weekly-full” |

Это выбор целевой роли, **не** утверждение, какой из двух Nextcloud/HA экземпляров сейчас реально primary. Перед миграцией определить владельца production data. Не останавливать “дубликат” по имени файла.

### 4.4. Адресация: минимальная коррекция

Сохранить существующие host numbers LXC:
- PostgreSQL .10, Redis .20, Nextcloud .30, Gitea .40;
- Grafana .60, Prometheus .70, reverse proxy .80, Docker-host .90, Home Assistant .100;
- все адреса из 10.0.100.0/24, gateway 10.0.100.1.

Сохранить management: router .1, Proxmox .10, Orange Pi .20 в 10.0.99.0/24.

У Orange Pi servers-side сейчас расходятся упоминания .5 (VLAN allocation) и .23 (host workload defaults/notes). До cutover выбрать один host-interface address по фактической конфигурации. Не путать host address с отдельными container addresses .200–.250.

Проверяемые инварианты:
- explicit gateway либо отсутствует, либо совпадает с canonical resolved gateway;
- адрес принадлежит назначенному интерфейсу/сегменту;
- bridge↔VLAN↔host attachment согласованы;
- static IP не входит в DHCP pool без reservation;
- все consumers используют одинаковые resolved IP/gateway.

### 4.5. Целевые разрешённые потоки

| Источник | Назначение | Разрешить |
|---|---|---|
| Approved operator/admin VPN | Management targets | Нужные SSH/HTTPS/Proxmox API, не вся подсеть и не все порты |
| User | Reverse proxy / опубликованные приложения | HTTPS; HTTP только redirect/обоснованный endpoint |
| Приложения с DB dependency | PostgreSQL/Redis | Нужные порты к конкретным targets; не вся user zone |
| Prometheus | Exporter targets | Перечень реально используемых exporter ports |
| Guest | DNS/DHCP/NTP и WAN | Только необходимые инфраструктурные сервисы + internet |
| IoT | Home Assistant/MQTT | Только нужные targets/ports; internet по policy |
| Exit-only VPN | Выбранный exit | Без доступа к management, servers и admin tunnel |
| Backup worker | Backup sources/destination | Объявленные backup flows; credentials с минимальными правами |

По умолчанию закрывать **необъявленные межзонные и lateral flows**. Это усиление текущей downhill-модели: при принятии обновить ADR0110/policy contract, а не скрыто изменить значение R1–R6.

На Proxmox использовать CT-level endpoint-aware правила. Не рассчитывать, что inter-VLAN router отфильтрует трафик между контейнерами одного L2 segment. Тип firewall backend и поддерживаемые directions проверить отдельно: у Proxmox возможности host/VNet forward rules зависят от backend. [Официальный firewall contract](https://raw.githubusercontent.com/proxmox/pve-docs/master/pve-firewall.adoc).

### 4.6. Backup и отказоустойчивость

Предлагаемые **целевые**, ещё не измеренные SLO:
- critical PostgreSQL: RPO до 1 часа по текущему hourly dump намерению; проверка restore обязательна;
- primary application data: RPO до 24 часов, только после согласования backup job/paths;
- config/keys recovery: после изменения + ежедневная защищённая копия;
- RTO устанавливать после измеренного восстановления, не назначать обещание на основании cron.

Обязательный граф:
source instance → data asset → backup artifact → staging storage → offsite copy → verified restore.
Offsite job не должен ссылаться на путь, которого не создаёт ни один producer.

## 5. План безопасного перехода

1. **Секреты:** rotation и SOPS, без сетевого cutover.
2. **Model integrity:** pins, canonical refs, корректные physical endpoint identities.
3. **Адресация:** привести host defaults и consumers к единому servers CIDR; собрать candidate IR, сравнить diff.
4. **Policy contracts:** исправить object/instance merge, zero-value handling, overlay zone membership, Proxmox enforcement.
5. **Canary:** один не критичный workload; проверить management/recovery path до включения default-deny.
6. **Service ownership:** определить primary экземпляры и data paths; сделать и проверить backup перед переносом.
7. **Миграция VLAN:** guest/IoT/user активировать по одному; legacy LAN удалять только после полного inventory/DHCP/ACL cutover.
8. **Operational status:** выставлять ready/active на основании acceptance evidence, а не успешного parsing.

Перед ограничением LAN→management обязательно обеспечить отдельный административный доступ и rollback. В рамках этого аудита никакие firewall, VLAN, services или workloads не отключались.

## 6. Acceptance criteria и необходимые новые проверки

### Статика/компиляция
- strict model-lock: 0 E3201;
- unknown refs во вложенных ACL/peers/asset owners: 0 или явно declared external refs;
- gateway mismatch, bridge/subnet mismatch: 0;
- 0 открытых secret values;
- inherited HTTP override присутствует в candidate policy;
- vpn_exit security_level=0 сохраняется после projection;
- оба tunnel CIDR относятся к правильным zones;
- требуемый enforcement со status=stub блокирует readiness;
- runtime types соответствуют canonical enum;
- primary image/data owner определён единственным контрактом.

### Сетевые негативные тесты, не только ping
- Guest/IoT/exit-only VPN не достигают management/admin tunnel;
- обычный user не подключается напрямую к PostgreSQL/Redis;
- посторонний LXC не получает те же DB permissions, что authorized application;
- controller сохраняет approved SSH/API-доступ;
- DNS/DHCP и обратный established/related traffic работают;
- при отказе VPN нет нежелательного direct-WAN fallback, если policy требует fail-closed.

### Операционные тесты
- восстановление PostgreSQL и primary Nextcloud из backup;
- восстановление router configuration без зависимости от единственного controller;
- определение поведения при отключении Orange Pi / Proxmox / uplink;
- budgets CPU/RAM/storage после sizing, с резервом для host OS и отказных сценариев.

Эти acceptance tests **предложены**, не выполнены на устройствах.

## 7. Что выполнено и границы доказательств

Выполнено:
- загрузка AI rules и scoped topology/host-placement/network-security/secrets constraints;
- разбор всех 185 source instances и соответствующей свежей effective model;
- compiler discover/compile/validate в passthrough, strict_model_lock=True; candidate IR перехвачен в памяти перед generate и сохранён временно для анализа;
- стандартный task build:compile-validate PYTHON=.venv/bin/python;
- независимый поиск критических refs, CIDR overlaps, derived-IP duplicates и sensitive fields;
- MikroTik/Proxmox projection на свежем IR, без deployment;
- probe security_level=0 в копии IR;
- проверка HEAD и отсутствия tracked modifications.

Не выполнялось:
- queries к реальным routers/hosts;
- SOPS decrypt;
- полный generate/assemble/build, Terraform plan/apply или Ansible deploy;
- ресурсный нагрузочный тест и restore;
- изменение исходной топологии.

Временная копия effective IR была очищена от значений sensitive fields; рапорт не содержит passphrase. Вся оценка реального состояния ограничена декларациями репозитория.

**Итоговое решение:** сохранить текущий адресный план, устранить T01–T10, затем принять целевое разделение management/application/backup enforcement. Перестройка аппаратного состава сейчас не обоснована: сначала нужна непротиворечивая и проверяемая топология на имеющемся оборудовании.
