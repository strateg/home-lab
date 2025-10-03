# Secure Home Network Configuration

Универсальная конфигурация домашней сети с Proxmox, OPNsense, OpenWRT и Oracle Cloud. Поддерживает два режима работы: дома и в поездке с автоматическим переключением.

## Архитектура

### Дома

```
Internet → ISP Router → Proxmox NIC1 (WAN)
                           ↓
                      OPNsense VM (Firewall)
                           ↓
                    Proxmox NIC2 (LAN)
                           ↓
                      OpenWRT Router
                           ↓
                  WiFi клиенты + LAN
```

### В поездке

```
Hotel WiFi → OpenWRT WAN → WireGuard VPN → Home OPNsense
                              ↓
                         Your devices
```

## Компоненты

### 1. Proxmox (Гипервизор)

**Устройство:** Dell XPS L701X (Studio XPS 17)
- CPU: Intel Core i5/i7 (1st gen, 2 ядра + HT)
- RAM: 8 GB DDR3
- SSD: 250 GB (быстрый - для VM/LXC)
- HDD: 500 GB (медленный - для backup/ISO)
- Встроенный Ethernet: 1x Gigabit (LAN)
- USB-Ethernet: 1x Gigabit (WAN)

> 📖 **Подробнее:** См. `DELL-XPS-L701X-NOTES.md` для оптимизации и особенностей

**Конфигурация:** `proxmox-network-interfaces`

**Bridges:**
- `vmbr0` - WAN (к ISP Router через USB-Ethernet)
- `vmbr1` - LAN (к OpenWRT через встроенный Ethernet)
- `vmbr2` - INTERNAL (LXC контейнеры)
- `vmbr99` - MGMT (управление)

**Storage:**
- `local-lvm` (SSD 250GB) - OPNsense VM, критичные LXC
- `local-hdd` (HDD 500GB) - backup, ISO, большие LXC

### 2. OPNsense (Основной Firewall)

**VM параметры (оптимизировано для 8GB RAM):**
- CPU: 2 cores
- RAM: 2 GB (минимум для стабильной работы)
- Disk: 32 GB (на SSD через local-lvm)
- Autostart: Priority 1
- Storage: local-lvm (SSD для производительности)

**Конфигурация:** `opnsense-interfaces-config.txt`

**Интерфейсы:**
- WAN: DHCP от ISP (192.168.1.x)
- LAN: 192.168.10.1/24 (к OpenWRT)
- INTERNAL: 10.0.30.1/24 (LXC)
- MGMT: 10.0.99.10/24 (управление)
- WireGuard: 10.0.200.1/24 (VPN для походного OpenWRT)

**Функции:**
- Stateful firewall
- NAT
- DHCP server
- WireGuard VPN server
- IDS/IPS (опционально)

### 3. OpenWRT (WiFi Router + Travel VPN Gateway)

**Устройство:** GL.iNet GL-AX1800 (Flint)
- CPU: MediaTek MT7621A (880 MHz dual-core)
- RAM: 512 MB
- WiFi: WiFi 6 (802.11ax) - 1200+574 Mbps
- Ethernet: 5x Gigabit (1 WAN + 4 LAN)
- Размер: Компактный (подходит для поездок)
- **Dual UI:** GL.iNet UI (удобный) + OpenWRT LuCI (расширенный)

> 📖 **Подробнее:** См. `GL-AX1800-NOTES.md` для специфичных настроек
>
> **Web интерфейсы:**
> - GL.iNet UI: http://192.168.20.1 (для повседневных задач)
> - OpenWRT LuCI: http://192.168.20.1:81 (для расширенных настроек)

**Режим ДОМА:**

Файлы конфигурации:
- `openwrt-home-network` - сетевая конфигурация
- `openwrt-home-wireless` - WiFi настройки
- `openwrt-home-dhcp` - DHCP и DNS
- `openwrt-home-firewall` - правила firewall

**Сети:**
- WAN: 192.168.10.2 (к OPNsense LAN)
- LAN: 192.168.20.1/24 (основная сеть)
- Guest: 192.168.30.1/24 (гостевая WiFi)
- IoT: 192.168.40.1/24 (умный дом)

**WiFi SSID:**
- `HomeNet-5G` / `HomeNet-2G` - основная сеть (WPA3)
- `Guest-5G` - гостевая (изолирована)
- `Smart-Home` - IoT устройства

**AdGuard Home:**
- **Расположение:** На OpenWRT (экономия RAM Proxmox!)
- Port: 53 (DNS)
- Web UI: http://192.168.20.1:3000
- Конфигурация: `adguardhome-config.yaml`
- Фильтрация рекламы для всей сети
- RAM usage: ~100-150 MB (на OpenWRT, не затрагивает Proxmox)

---

**Режим В ПОЕЗДКЕ:**

Файлы конфигурации:
- `openwrt-travel-network` - сетевая конфигурация с WireGuard
- `openwrt-travel-wireless` - WiFi для ваших устройств
- `openwrt-travel-dhcp` - DHCP с DNS через VPN
- `openwrt-travel-firewall` - строгий firewall для публичных сетей

**Сети:**
- WAN: DHCP от отеля/кафе
- LAN: 192.168.100.1/24 (ваши устройства)
- WireGuard Home: 10.0.200.10/32
- WireGuard Oracle: 10.1.200.10/32

**WiFi SSID:**
- `Travel-Secure-5G` / `Travel-Secure-2G` - весь трафик через VPN

**VPN Failover:**
- Primary: WireGuard → Home OPNsense
- Backup: WireGuard → Oracle Cloud

### 4. Oracle Cloud (Backup VPN Gateway)

**Конфигурация:** `oracle-cloud-wireguard.conf`

**Instance:**
- OS: Ubuntu 22.04 LTS
- Shape: Always Free (4 OCPU ARM, 24GB RAM)
- VPN: WireGuard server

**Функции:**
- Site-to-site VPN с домашней сетью
- Failover точка для походного OpenWRT
- Backup reverse proxy (опционально)

**IP адресация:**
- WireGuard: 10.1.0.1/24
- Peer Home: 10.0.0.0/16
- Peer OpenWRT: 10.1.200.10/32

## IP адресация

### Домашняя сеть

| Сеть | CIDR | Gateway | Назначение |
|------|------|---------|------------|
| ISP | 192.168.1.0/24 | 192.168.1.1 | ISP Router |
| OPNsense LAN | 192.168.10.0/24 | 192.168.10.1 | К OpenWRT |
| OpenWRT LAN | 192.168.20.0/24 | 192.168.20.1 | Клиенты |
| Guest WiFi | 192.168.30.0/24 | 192.168.30.1 | Гости |
| IoT | 192.168.40.0/24 | 192.168.40.1 | Умный дом |
| LXC Internal | 10.0.30.0/24 | 10.0.30.1 | Контейнеры |
| Management | 10.0.99.0/24 | 10.0.99.1 | Управление |
| VPN Travel | 10.0.200.0/24 | 10.0.200.1 | OpenWRT VPN |

### Oracle Cloud

| Сеть | CIDR | Gateway | Назначение |
|------|------|---------|------------|
| Oracle VPN | 10.1.0.0/24 | 10.1.0.1 | WireGuard |
| Travel VPN | 10.1.200.0/24 | - | OpenWRT clients |

## Установка

### 1. Proxmox

1. Установите Proxmox VE на сервер
2. Скопируйте конфигурацию:
```bash
cp proxmox-network-interfaces /etc/network/interfaces
```
3. Настройте имена интерфейсов под ваше оборудование
4. Перезапустите сеть:
```bash
ifreload -a
```

### 2. OPNsense VM

1. Создайте VM в Proxmox (см. параметры в `opnsense-interfaces-config.txt`)
2. Установите OPNsense с ISO образа
3. Настройте интерфейсы через консоль
4. Откройте Web UI: https://192.168.10.1
5. Следуйте инструкциям в `opnsense-interfaces-config.txt`

### 3. OpenWRT Router

**Первичная настройка:**

1. Подключитесь к OpenWRT через SSH или Web UI
2. Запустите установочный скрипт:
```bash
scp openwrt-install-script.sh root@192.168.1.1:/tmp/
ssh root@192.168.1.1
cd /tmp
sh openwrt-install-script.sh
```

**Настройка режима ДОМА:**

1. Скопируйте конфигурации:
```bash
scp openwrt-home-* root@192.168.20.1:/etc/openwrt-configs/home/
ssh root@192.168.20.1

# Rename files
cd /etc/openwrt-configs/home/
mv openwrt-home-network network
mv openwrt-home-wireless wireless
mv openwrt-home-dhcp dhcp
mv openwrt-home-firewall firewall
```

2. Настройте WiFi пароли в файле `wireless`
3. Настройте AdGuard Home:
```bash
cp adguardhome-config.yaml /etc/adguardhome.yaml
/etc/init.d/AdGuardHome restart
```
4. Откройте http://192.168.20.1:3000 и завершите настройку

**Настройка режима В ПОЕЗДКЕ:**

1. Сгенерируйте WireGuard ключи:
```bash
ssh root@192.168.20.1
wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey
```

2. Добавьте публичный ключ в OPNsense (VPN → WireGuard → Peers)

3. Скопируйте конфигурации:
```bash
scp openwrt-travel-* root@192.168.20.1:/etc/openwrt-configs/travel/
ssh root@192.168.20.1

cd /etc/openwrt-configs/travel/
mv openwrt-travel-network network
mv openwrt-travel-wireless wireless
mv openwrt-travel-dhcp dhcp
mv openwrt-travel-firewall firewall
```

4. Отредактируйте `/etc/openwrt-configs/travel/network`:
   - Замените `YOUR_OPENWRT_PRIVATE_KEY_HERE` на ваш приватный ключ
   - Замените `OPNSENSE_PUBLIC_KEY_HERE` на публичный ключ OPNsense
   - Замените `your-home-ddns.example.com` на ваш домашний DDNS

### 4. Oracle Cloud

1. Создайте Always Free instance (Ubuntu 22.04 ARM)

2. Настройте WireGuard:
```bash
ssh ubuntu@oracle-ip
sudo apt update && sudo apt install wireguard-tools

# Generate keys
wg genkey | sudo tee /etc/wireguard/privatekey | wg pubkey | sudo tee /etc/wireguard/publickey

# Copy config
sudo nano /etc/wireguard/wg0.conf
# Paste content from oracle-cloud-wireguard.conf
```

3. Включите IP forwarding:
```bash
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

4. Настройте firewall:
```bash
sudo ufw allow 51820/udp
sudo ufw enable
```

5. Добавьте Security List в OCI Console:
   - Ingress Rule: UDP port 51820 from 0.0.0.0/0

6. Запустите WireGuard:
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

## Использование

### Автоматическое переключение режимов

OpenWRT автоматически определяет, находитесь вы дома или в поездке:

**Дома:**
- Обнаруживает OPNsense на 192.168.10.1
- Работает как обычный WiFi роутер
- AdGuard фильтрует рекламу

**В поездке:**
- Не находит OPNsense
- Автоматически переключается в VPN режим
- Поднимает WireGuard туннель

### Ручное переключение

```bash
ssh root@192.168.20.1  # или 192.168.100.1 в поездке

# Переключить в режим дома
/usr/bin/openwrt-mode-switcher.sh

# Проверить VPN failover
/usr/bin/openwrt-vpn-failover.sh

# Проверить текущий режим
cat /etc/openwrt-mode
```

### Мониторинг

**OpenWRT:**
- Web UI: http://192.168.20.1 (дома) или http://192.168.100.1 (поездка)
- Logs: `logread -f`
- WireGuard status: `wg show`

**OPNsense:**
- Web UI: https://192.168.10.1 или https://10.0.99.10
- Dashboard → Gateways для статуса VPN

**AdGuard Home:**
- Web UI: http://192.168.20.1:3000
- Query Log: просмотр всех DNS запросов
- Statistics: статистика блокировки

## Безопасность

### Многоуровневая защита

1. **Периметр:** OPNsense firewall (stateful inspection)
2. **Access layer:** OpenWRT с изолированными VLAN
3. **DNS filtering:** AdGuard Home блокирует вредоносные домены
4. **Encryption:** WPA3 для WiFi, WireGuard для VPN

### Изоляция сетей

- **Guest WiFi:** нет доступа к локальной сети
- **IoT:** только интернет, заблокирован доступ к другим устройствам
- **LXC:** изолированы от управления (MGMT)
- **Travel mode:** весь трафик через VPN

### Защита в поездках

- Автоматическое шифрование всего трафика
- Защита от атак в публичных WiFi
- Failover через Oracle Cloud если дом недоступен
- DNS через домашний AdGuard (защита от DNS spoofing)

## Troubleshooting

### OpenWRT не переключается в режим дома

```bash
# Проверьте доступность OPNsense
ping -c 3 192.168.10.1

# Проверьте логи
logread | grep mode-switcher

# Принудительное переключение
cp /etc/openwrt-configs/home/* /etc/config/
/etc/init.d/network restart
```

### VPN не поднимается в поездке

```bash
# Проверьте статус WireGuard
wg show

# Проверьте доступность endpoint
ping your-home-ddns.example.com

# Перезапустите WireGuard
/etc/init.d/wireguard restart

# Проверьте логи
logread | grep wireguard
```

### AdGuard не блокирует рекламу

```bash
# Проверьте статус
/etc/init.d/AdGuardHome status

# Проверьте, что клиенты используют правильный DNS
nslookup google.com 192.168.20.1

# Обновите фильтры в Web UI
# Settings → DNS settings → Update filters
```

### Нет доступа к LXC контейнерам

```bash
# Проверьте маршрутизацию на OPNsense
# Firewall → Rules → LAN
# Должно быть правило: LAN net → INTERNAL net (Allow)

# Проверьте из OpenWRT
traceroute 10.0.30.10
```

## LXC Контейнеры (примеры)

Все LXC контейнеры подключаются к `vmbr2` (10.0.30.0/24):

```bash
# Proxmox
pct create 200 local:vztmpl/debian-12-standard.tar.zst \
  --hostname postgres-db \
  --net0 name=eth0,bridge=vmbr2,ip=10.0.30.10/24,gw=10.0.30.1 \
  --nameserver 192.168.10.2 \
  --memory 2048 --cores 2 --rootfs local-lvm:8

# Доступ из домашней сети
# http://10.0.30.10 (через роутинг OPNsense)
```

**Популярные сервисы:**
- 10.0.30.10 - PostgreSQL
- 10.0.30.20 - Redis
- 10.0.30.30 - Nextcloud
- 10.0.30.40 - Gitea
- 10.0.30.50 - Home Assistant
- 10.0.30.60 - Grafana
- 10.0.30.70 - Prometheus

## Backup и восстановление

### Backup конфигураций

```bash
# OpenWRT
ssh root@192.168.20.1
sysupgrade -b /tmp/backup-$(date +%Y%m%d).tar.gz
scp root@192.168.20.1:/tmp/backup-*.tar.gz ./

# OPNsense
# System → Configuration → Backups → Download configuration
```

### Восстановление

```bash
# OpenWRT
scp backup-20250101.tar.gz root@192.168.20.1:/tmp/
ssh root@192.168.20.1
sysupgrade -r /tmp/backup-20250101.tar.gz

# OPNsense
# System → Configuration → Backups → Restore configuration
```

## Производительность

### Рекомендуемое оборудование

**Proxmox:**
- CPU: 4+ cores (Intel/AMD x86_64)
- RAM: 16+ GB
- Storage: 250+ GB SSD
- Network: 2x Gigabit Ethernet

**OpenWRT Router:**

Эта конфигурация оптимизирована для **GL.iNet GL-AX1800 (Flint)**:
- ✅ WiFi 6 (802.11ax) - высокая скорость
- ✅ Dual-band (5GHz + 2.4GHz)
- ✅ 5x Gigabit Ethernet
- ✅ Компактный размер (идеален для поездок)
- ✅ 512 MB RAM (достаточно для AdGuard + VPN)
- ✅ USB 3.0 порт
- ✅ GL.iNet firmware на базе OpenWRT

**Альтернативные роутеры:**
- GL.iNet GL-MT3000 (Beryl AX) - компактнее
- TP-Link Archer AX23 - WiFi 6, бюджетный
- Netgear R7800 - мощный, WiFi 5
- Linksys WRT3200ACM - open source friendly

## FAQ

**Q: Можно ли использовать только OpenWRT без OPNsense?**

A: Да, но OPNsense обеспечивает дополнительный уровень защиты. Для упрощённой схемы можно использовать только OpenWRT с AdGuard.

**Q: Работает ли это с IPv6?**

A: Да, конфигурации поддерживают IPv6. Убедитесь, что ваш провайдер предоставляет IPv6.

**Q: Можно ли использовать другой VPN провайдер вместо Oracle Cloud?**

A: Да, подойдёт любой VPS с публичным IP и WireGuard. Oracle Cloud выбран из-за Always Free tier.

**Q: Сколько устройств поддерживает эта конфигурация?**

A: Зависит от оборудования. Типичный setup поддерживает 50-100 устройств одновременно.

**Q: Безопасно ли использовать походный роутер в публичных WiFi?**

A: Да, весь трафик шифруется через WireGuard VPN. Публичная сеть видит только зашифрованный туннель.

## Дополнительные улучшения

### Опциональные фичи

1. **Dynamic DNS:** Настройте DDNS для домашнего IP
2. **Let's Encrypt:** Автоматические SSL сертификаты для OPNsense
3. **Suricata IDS:** Установите на OPNsense для обнаружения вторжений
4. **QoS:** Настройте SQM на OpenWRT для стабильного интернета
5. **VLANs:** Добавьте больше изолированных сетей
6. **Reverse Proxy:** HAProxy на OPNsense для веб-сервисов

### Мониторинг

1. **Grafana Dashboard:** Визуализация метрик сети
2. **Prometheus:** Сбор метрик с OPNsense и OpenWRT
3. **Uptime Kuma:** Мониторинг доступности сервисов

## Лицензия

Эта конфигурация предоставляется "как есть" для личного использования.

## Поддержка

Для вопросов и улучшений создавайте issues в вашем репозитории.

---

**Автор:** Ваше имя
**Дата:** 2025-10-03
**Версия:** 1.0
