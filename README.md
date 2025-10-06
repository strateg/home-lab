# Secure Home Network Configuration

Универсальная конфигурация домашней сети с Proxmox, OPNsense, OpenWRT и Oracle Cloud. Поддерживает два режима работы: дома и в поездке с автоматическим переключением.

## Структура проекта

```
home-lab/
├── README.md                      # Этот файл
├── docs/                          # Документация
│   ├── START-HERE.md             # Быстрый старт
│   ├── QUICK-REFERENCE.md        # Краткая справка
│   ├── CHANGELOG.md              # История изменений
│   ├── FILES-INDEX.md            # Индекс файлов
│   ├── AMNEZIAWG-SETUP.md        # AmneziaWG настройка
│   ├── HOME-RUSSIA-VPN-SETUP.md  # Russia VPN дома
│   ├── NETWORK-DIAGRAM.txt       # Диаграмма сети
│   └── ИНСТРУКЦИЯ.md             # Инструкция (RU)
├── proxmox/                       # Proxmox VE
│   ├── install/                  # Автоустановка
│   │   ├── create-proxmox-usb.sh
│   │   ├── answer.toml
│   │   ├── README-AUTOINSTALL.md
│   │   └── PROXMOX-UNATTENDED-INSTALL.md
│   ├── scripts/                  # Automation система ⚡
│   │   ├── lib/                  # Библиотеки
│   │   │   ├── common-functions.sh
│   │   │   └── network-functions.sh
│   │   ├── templates/            # LXC шаблоны
│   │   │   └── create-all-templates.sh
│   │   ├── vms/                  # VM шаблоны
│   │   │   ├── create-opnsense-template.sh
│   │   │   └── deploy-opnsense.sh
│   │   ├── services/             # LXC deployment
│   │   │   └── deploy-*.sh
│   │   ├── proxmox-post-install.sh
│   │   ├── configure-network.sh  # Сетевая автоматизация
│   │   ├── configure-lxc-routing.sh
│   │   ├── deploy-all-services.sh
│   │   ├── deploy-complete-system.sh  # Полное развертывание
│   │   ├── README.md
│   │   ├── ARCHITECTURE.md
│   │   ├── QUICK-START.md
│   │   └── NETWORK-SETUP.md
│   └── configs/                  # Конфигурация
│       └── proxmox-network-interfaces
├── openwrt/                       # OpenWRT Router
│   ├── home/                     # Home режим
│   │   ├── openwrt-home-network
│   │   ├── openwrt-home-wireless
│   │   ├── openwrt-home-dhcp
│   │   ├── openwrt-home-firewall
│   │   └── openwrt-home-russia-vpn.conf
│   ├── travel/                   # Travel режим
│   │   ├── openwrt-travel-network
│   │   ├── openwrt-travel-wireless
│   │   ├── openwrt-travel-dhcp
│   │   ├── openwrt-travel-firewall
│   │   ├── openwrt-travel-amneziawg-client.conf
│   │   └── openwrt-travel-russia-client.conf
│   └── scripts/                  # Скрипты управления
│       ├── openwrt-install-script.sh
│       ├── openwrt-mode-switcher.sh
│       ├── openwrt-init-mode-detector
│       ├── openwrt-vpn-selector.sh
│       ├── openwrt-vpn-failover.sh
│       └── openwrt-amneziawg-failover.sh
├── opnsense/                      # OPNsense Firewall
│   └── configs/
│       ├── opnsense-interfaces-config.txt
│       └── opnsense-russia-vpn-firewall.txt
├── vpn-servers/                   # VPN Серверы
│   ├── oracle-cloud/
│   │   ├── oracle-cloud-wireguard.conf
│   │   └── oracle-cloud-amneziawg.conf
│   └── russia-vps/
│       ├── RUSSIA-VPS-SETUP.md
│       └── russia-vps-amneziawg.conf
├── hardware/                      # Оборудование
│   ├── dell-xps/
│   │   ├── DELL-XPS-L701X-NOTES.md
│   │   ├── DELL-XPS-SETUP-GUIDE.md
│   │   └── DELL-XPS-EXTERNAL-DISPLAY-NOTES.md
│   └── gl-inet/
│       ├── GL-AXT1800-NOTES.md
│       └── GL-INET-UI-GUIDE.md
└── services/                      # Сервисы
    └── adguardhome/
        └── adguardhome-config.yaml
```

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

> 📖 **Подробнее:** См. [hardware/dell-xps/DELL-XPS-L701X-NOTES.md](hardware/dell-xps/DELL-XPS-L701X-NOTES.md)

**Конфигурация:** [proxmox/configs/proxmox-network-interfaces](proxmox/configs/proxmox-network-interfaces)

**Bridges:**
- `vmbr0` - WAN (к ISP Router через USB-Ethernet)
- `vmbr1` - LAN (к OpenWRT через встроенный Ethernet)
- `vmbr2` - INTERNAL (LXC контейнеры)
- `vmbr99` - MGMT (управление)

**Storage (Template Strategy):**
- `local-hdd` (HDD 500GB) - Templates (LXC 900-908, VM 910), backup, ISO
- `local-lvm` (SSD 180GB) - Production (VM 100, LXC 200-208)

> 💡 **Стратегия:** Шаблоны на медленном HDD (редкий доступ), production на быстром SSD (ежедневная работа)

### 2. OPNsense (Основной Firewall)

**VM параметры (оптимизировано для 8GB RAM):**
- CPU: 2 cores
- RAM: 2 GB (минимум для стабильной работы)
- Disk: 32 GB (на SSD через local-lvm)
- Autostart: Priority 1
- Storage: local-lvm (SSD для производительности)

**Конфигурация:** [opnsense/configs/opnsense-interfaces-config.txt](opnsense/configs/opnsense-interfaces-config.txt)

**Интерфейсы:**
- WAN (vtnet0): DHCP от ISP (192.168.1.x) → vmbr0
- LAN (vtnet1): 192.168.10.1/24 → vmbr1 (к OpenWRT)
- INTERNAL (vtnet2): 10.0.30.254/24 → vmbr2 (gateway для LXC)
- MGMT (vtnet3): 10.0.99.10/24 → vmbr99 (Web UI)
- WireGuard: 10.0.200.1/24 (VPN для походного OpenWRT)

> 💡 **Примечание:** Proxmox host использует 10.0.30.1 для прямого доступа к LXC, OPNsense использует 10.0.30.254 как Internet gateway

**Функции:**
- Stateful firewall
- NAT
- DHCP server
- WireGuard VPN server
- IDS/IPS (опционально)

### 3. OpenWRT (WiFi Router + Travel VPN Gateway)

**Устройство:** GL.iNet GL-AXT1800 (Slate AX)
- CPU: MediaTek MT7621A (880 MHz dual-core)
- RAM: 512 MB
- WiFi: WiFi 6 (802.11ax) - 1200+574 Mbps
- Ethernet: **3x Gigabit (1 WAN + 2 LAN)**
- Размер: Компактный ~10x6x2 см (портативный travel router)
- **Dual UI:** GL.iNet UI (удобный) + OpenWRT LuCI (расширенный)

> 📖 **Подробнее:** См. [hardware/gl-inet/GL-AXT1800-NOTES.md](hardware/gl-inet/GL-AXT1800-NOTES.md)
>
> **Web интерфейсы:**
> - GL.iNet UI: http://192.168.20.1 (для повседневных задач)
> - OpenWRT LuCI: http://192.168.20.1:81 (для расширенных настроек)

**Режим ДОМА:**

Файлы конфигурации:
- [openwrt/home/openwrt-home-network](openwrt/home/openwrt-home-network) - сетевая конфигурация
- [openwrt/home/openwrt-home-wireless](openwrt/home/openwrt-home-wireless) - WiFi настройки
- [openwrt/home/openwrt-home-dhcp](openwrt/home/openwrt-home-dhcp) - DHCP и DNS
- [openwrt/home/openwrt-home-firewall](openwrt/home/openwrt-home-firewall) - правила firewall

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
- Конфигурация: [services/adguardhome/adguardhome-config.yaml](services/adguardhome/adguardhome-config.yaml)
- Фильтрация рекламы для всей сети
- RAM usage: ~100-150 MB (на OpenWRT, не затрагивает Proxmox)

---

**Режим В ПОЕЗДКЕ:**

Файлы конфигурации:
- [openwrt/travel/openwrt-travel-network](openwrt/travel/openwrt-travel-network) - сетевая конфигурация с WireGuard
- [openwrt/travel/openwrt-travel-wireless](openwrt/travel/openwrt-travel-wireless) - WiFi для ваших устройств
- [openwrt/travel/openwrt-travel-dhcp](openwrt/travel/openwrt-travel-dhcp) - DHCP с DNS через VPN
- [openwrt/travel/openwrt-travel-firewall](openwrt/travel/openwrt-travel-firewall) - строгий firewall для публичных сетей

**Сети:**
- WAN: DHCP от отеля/кафе
- LAN: 192.168.100.1/24 (ваши устройства)
- WireGuard Home: 10.0.200.10/32
- WireGuard Oracle: 10.1.200.10/32

**WiFi SSID:**
- `Travel-Secure-5G` / `Travel-Secure-2G` - весь трафик через VPN

**VPN Failover:**
- Primary: AmneziaWG → Oracle Cloud (обход DPI блокировок РФ)
- Backup: WireGuard → Home OPNsense (если AmneziaWG заблокирован)

> 📖 **Важно для России:** См. [docs/AMNEZIAWG-SETUP.md](docs/AMNEZIAWG-SETUP.md)

### 4. Oracle Cloud (Backup VPN Gateway)

**Конфигурации:**
- [vpn-servers/oracle-cloud/oracle-cloud-wireguard.conf](vpn-servers/oracle-cloud/oracle-cloud-wireguard.conf) - обычный WireGuard
- [vpn-servers/oracle-cloud/oracle-cloud-amneziawg.conf](vpn-servers/oracle-cloud/oracle-cloud-amneziawg.conf) - AmneziaWG с обфускацией (для РФ)

**Instance:**
- OS: Ubuntu 22.04 LTS
- Shape: Always Free (4 OCPU ARM, 24GB RAM)
- VPN: WireGuard + AmneziaWG серверы

**Функции:**
- Site-to-site VPN с домашней сетью
- Failover точка для походного OpenWRT
- AmneziaWG для обхода DPI блокировок (Россия, Китай, Иран)
- Backup reverse proxy (опционально)

**IP адресация:**
- WireGuard: 10.8.1.0/24 (порт 51820)
- AmneziaWG: 10.8.2.0/24 (порт 51821, с обфускацией)
- Peer Home: 10.0.0.0/16
- Peer OpenWRT: 10.8.1.2 (WG) / 10.8.2.2 (AWG)

### 5. Russia VPS (Российский IP адрес)

**Конфигурации:**
- [vpn-servers/russia-vps/russia-vps-amneziawg.conf](vpn-servers/russia-vps/russia-vps-amneziawg.conf) - сервер на российском VPS
- [openwrt/travel/openwrt-travel-russia-client.conf](openwrt/travel/openwrt-travel-russia-client.conf) - клиент для Travel Mode
- [openwrt/home/openwrt-home-russia-vpn.conf](openwrt/home/openwrt-home-russia-vpn.conf) - клиент для Home Mode

**Назначение:** Получение российского IP для доступа к РФ сервисам из-за границы

**VPS:**
- Хостинг: Timeweb / REG.RU / Selectel
- Стоимость: 150-500₽/мес (~$2-5)
- Расположение: Москва или Санкт-Петербург
- VPN: AmneziaWG сервер

**Сервисы с российским IP:**
- 🏦 Банки РФ (Сбербанк, Тинькофф, ВТБ)
- 🏛️ Госуслуги
- 📺 Стриминг (Okko, Kinopoisk, Match TV)
- 🛍️ Маркетплейсы (Wildberries, Ozon)
- 🎵 Яндекс.Музыка, Яндекс.Диск

**IP адресация:**
- AmneziaWG: 10.9.1.0/24 (порт 51822)
- Сервер: 10.9.1.1
- Клиент: 10.9.1.2

**Использование дома (через OPNsense):**
- Russia VPN работает и дома! Трафик проходит через OPNsense firewall
- Нужно настроить правила на OPNsense (разрешить UDP 51822)
- Та же AmneziaWG конфигурация, разная только маршрутизация

> 📖 **Подробнее:**
> - Настройка российского VPS: [vpn-servers/russia-vps/RUSSIA-VPS-SETUP.md](vpn-servers/russia-vps/RUSSIA-VPS-SETUP.md)
> - Использование дома: [docs/HOME-RUSSIA-VPN-SETUP.md](docs/HOME-RUSSIA-VPN-SETUP.md)
> - Правила OPNsense: [opnsense/configs/opnsense-russia-vpn-firewall.txt](opnsense/configs/opnsense-russia-vpn-firewall.txt)

### 6. VPN Протоколы

**WireGuard** (базовый):
- ✅ Максимальная скорость
- ✅ Простая настройка
- ❌ Легко блокируется DPI (в РФ, Китае)
- Файлы: [vpn-servers/oracle-cloud/oracle-cloud-wireguard.conf](vpn-servers/oracle-cloud/oracle-cloud-wireguard.conf)

**AmneziaWG Oracle** (обход блокировок):
- ✅ Обход DPI блокировок в РФ
- ✅ Почти такая же скорость как WireGuard
- ✅ Обфускация трафика
- Файлы: [vpn-servers/oracle-cloud/oracle-cloud-amneziawg.conf](vpn-servers/oracle-cloud/oracle-cloud-amneziawg.conf), [openwrt/travel/openwrt-travel-amneziawg-client.conf](openwrt/travel/openwrt-travel-amneziawg-client.conf)

**AmneziaWG Russia** (российский IP):
- ✅ Российский IP адрес
- ✅ Доступ к РФ сервисам из-за границы
- ✅ Та же обфускация
- Файлы: [vpn-servers/russia-vps/russia-vps-amneziawg.conf](vpn-servers/russia-vps/russia-vps-amneziawg.conf), [openwrt/travel/openwrt-travel-russia-client.conf](openwrt/travel/openwrt-travel-russia-client.conf)

**VPN Selector:**
- Скрипт: [openwrt/scripts/openwrt-vpn-selector.sh](openwrt/scripts/openwrt-vpn-selector.sh)
- Переключение одной командой: `vpn oracle`, `vpn russia`, `vpn home`

> 📖 **Подробнее:**
> - AmneziaWG настройка: [docs/AMNEZIAWG-SETUP.md](docs/AMNEZIAWG-SETUP.md)
> - Российский VPS: [vpn-servers/russia-vps/RUSSIA-VPS-SETUP.md](vpn-servers/russia-vps/RUSSIA-VPS-SETUP.md)

## IP адресация

### Домашняя сеть

| Сеть | CIDR | Gateway | Назначение |
|------|------|---------|------------|
| ISP | 192.168.1.0/24 | 192.168.1.1 | ISP Router |
| OPNsense LAN | 192.168.10.0/24 | 192.168.10.1 | К OpenWRT |
| OpenWRT LAN | 192.168.20.0/24 | 192.168.20.1 | Клиенты |
| Guest WiFi | 192.168.30.0/24 | 192.168.30.1 | Гости |
| IoT | 192.168.40.0/24 | 192.168.40.1 | Умный дом |
| LXC Internal | 10.0.30.0/24 | **10.0.30.254** | Контейнеры (Internet via OPNsense) |
| Management | 10.0.99.0/24 | 10.0.99.1 | Proxmox + OPNsense Admin |
| VPN Travel | 10.0.200.0/24 | 10.0.200.1 | OpenWRT VPN |

> 💡 **Важно:** LXC контейнеры используют 10.0.30.254 (OPNsense) как Internet gateway, Proxmox host доступен на 10.0.30.1

### VPN Серверы

| Сервер | Сеть | CIDR | Gateway | Назначение |
|--------|------|------|---------|------------|
| **Oracle Cloud** | WireGuard | 10.8.1.0/24 | 10.8.1.1 | Обычный WireGuard (порт 51820) |
| **Oracle Cloud** | AmneziaWG | 10.8.2.0/24 | 10.8.2.1 | Обход DPI РФ (порт 51821) |
| **Russia VPS** | AmneziaWG | 10.9.1.0/24 | 10.9.1.1 | Российский IP (порт 51822) |

## Установка

### 1. Proxmox - Автоматическая установка

**Для Dell XPS L701X с внешним дисплеем:**

⭐ **Используйте автоматическую установку**: [proxmox/install/create-proxmox-usb.sh](proxmox/install/create-proxmox-usb.sh)

```bash
# 1. Создайте загрузочную USB
sudo ./proxmox/install/create-proxmox-usb.sh /dev/sdX proxmox-ve_9.0.iso

# 2. Загрузитесь с USB (F12 → UEFI: USB)
# 3. Нажмите 'a' в меню для автоустановки
# 4. Подождите 10-15 минут
```

**📖 Подробная инструкция:**
- English: [proxmox/install/README-AUTOINSTALL.md](proxmox/install/README-AUTOINSTALL.md)
- Русский: [docs/ИНСТРУКЦИЯ.md](docs/ИНСТРУКЦИЯ.md)

**После установки:**

1. Войдите через SSH:
```bash
ssh root@<ip-address>  # Пароль: Homelab2025!
```

2. Запустите post-install скрипт с сетевой автоматизацией:
```bash
# Полная автоматизация (новая система)
bash proxmox-post-install.sh --init-hdd --auto-network

# Или интерактивно (существующая система)
bash proxmox-post-install.sh
```

Скрипт автоматически:
- ✅ Настроит репозитории (no-subscription)
- ✅ **Автоматически обнаружит сетевые интерфейсы** (PCI/USB)
- ✅ **Создаст UDEV правила** (eth-wan, eth-lan)
- ✅ **Сгенерирует network config** (vmbr0-vmbr99)
- ✅ Инициализирует HDD или смонтирует существующий
- ✅ Применит оптимизации (KSM, USB power)

3. Перезагрузите систему:
```bash
systemctl reboot
```

> 📖 **Сетевая автоматизация:** См. [proxmox/scripts/NETWORK-SETUP.md](proxmox/scripts/NETWORK-SETUP.md)

### 2. OPNsense VM - Автоматизированное развертывание ⚡

**Вариант A: Полная автоматизация (рекомендуется)**

```bash
cd /root/scripts

# Шаг 1: Создать OPNsense template (один раз, ~15 минут)
bash vms/create-opnsense-template.sh
# Следуйте инструкциям для ручной установки OPNsense
# После установки: qm template 910

# Шаг 2: Развернуть OPNsense VM из template (~2 минуты)
bash vms/deploy-opnsense.sh

# Готово! OPNsense работает на VM ID 100
```

**Вариант B: Ручная установка**

1. Создайте VM в Proxmox (см. параметры в [opnsense/configs/opnsense-interfaces-config.txt](opnsense/configs/opnsense-interfaces-config.txt))
2. Установите OPNsense с ISO образа
3. Настройте интерфейсы через консоль
4. Откройте Web UI: https://192.168.10.1 или https://10.0.99.10
5. Следуйте инструкциям в [opnsense/configs/opnsense-interfaces-config.txt](opnsense/configs/opnsense-interfaces-config.txt)

> 📖 **Подробнее:** См. [proxmox/scripts/README.md#vm-management-opnsense-firewall](proxmox/scripts/README.md#vm-management-opnsense-firewall)

### 3. OpenWRT Router

**Первичная настройка:**

1. Подключитесь к OpenWRT через SSH или Web UI
2. Запустите установочный скрипт:
```bash
scp openwrt/scripts/openwrt-install-script.sh root@192.168.1.1:/tmp/
ssh root@192.168.1.1
cd /tmp
sh openwrt-install-script.sh
```

**Настройка режима ДОМА:**

1. Скопируйте конфигурации:
```bash
scp openwrt/home/openwrt-home-* root@192.168.20.1:/etc/openwrt-configs/home/
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
cp services/adguardhome/adguardhome-config.yaml /etc/adguardhome.yaml
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
scp openwrt/travel/openwrt-travel-* root@192.168.20.1:/etc/openwrt-configs/travel/
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
# Paste content from vpn-servers/oracle-cloud/oracle-cloud-wireguard.conf
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

# Или используйте локальные скрипты
openwrt/scripts/openwrt-mode-switcher.sh
openwrt/scripts/openwrt-vpn-failover.sh

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
# Proxmox (пример ручного создания)
pct create 200 local:vztmpl/debian-12-standard.tar.zst \
  --hostname postgres-db \
  --net0 name=eth0,bridge=vmbr2,ip=10.0.30.10/24,gw=10.0.30.254 \
  --nameserver 192.168.10.2 \
  --memory 2048 --cores 2 --rootfs local-lvm:8

# Доступ из домашней сети
# http://10.0.30.10 (через роутинг OPNsense)
```

> 💡 **Автоматизация:** Используйте `bash deploy-complete-system.sh` вместо ручного создания!

**Популярные сервисы:**
- 10.0.30.10 - PostgreSQL
- 10.0.30.20 - Redis
- 10.0.30.30 - Nextcloud
- 10.0.30.40 - Gitea
- 10.0.30.50 - Home Assistant
- 10.0.30.60 - Grafana
- 10.0.30.70 - Prometheus

## Полная автоматизация Home Lab 🚀

Система автоматического создания templates и развёртывания OPNsense + LXC сервисов:

### Быстрый старт (13 минут до production!)

```bash
cd /root/scripts

# ВАРИАНТ 1: Полное развертывание (OPNsense + 9 LXC сервисов)
bash deploy-complete-system.sh

# ВАРИАНТ 2: Пошаговое развертывание
# Шаг 1: Создать templates (один раз, ~45 минут)
bash templates/create-all-templates.sh  # LXC templates
bash vms/create-opnsense-template.sh    # OPNsense template

# Шаг 2: Развернуть систему (~13 минут)
bash vms/deploy-opnsense.sh             # OPNsense VM
bash configure-lxc-routing.sh           # Routing через OPNsense
bash deploy-all-services.sh             # 9 LXC сервисов

# Готово! OPNsense + 9 сервисов запущены и настроены
```

### Что создаётся автоматически

**Templates на HDD (local-hdd):**
- **LXC (ID 900-908):** PostgreSQL, Redis, Nextcloud, Gitea, Home Assistant, Grafana, Prometheus, Nginx Proxy Manager, Docker
- **VM (ID 910):** OPNsense Firewall

**Production на SSD (local-lvm):**
- **VM (ID 100):** OPNsense Firewall (запускается первым)
- **LXC (ID 200-208):** Все сервисы с static IP 10.0.30.10-90

**Сетевая конфигурация:**
- Gateway для LXC: **10.0.30.254** (OPNsense INTERNAL)
- DNS: 192.168.10.2 (AdGuard на OpenWRT)
- Routing: LXC → OPNsense → Internet

### Примеры использования

```bash
# Развернуть только OPNsense
bash deploy-complete-system.sh --opnsense-only

# Развернуть только LXC сервисы
bash deploy-complete-system.sh --lxc-only

# Развернуть отдельный LXC сервис
bash services/deploy-postgresql.sh

# Создать дополнительный экземпляр PostgreSQL
pct clone 900 210 --hostname postgres-02 --full --storage local-lvm
pct set 210 --net0 name=eth0,bridge=vmbr2,ip=10.0.30.11/24,gw=10.0.30.254
pct start 210

# Проверить статус
qm status 100          # OPNsense VM
pct list               # Все LXC контейнеры

# Проверить интернет из LXC
pct exec 200 -- ping -c 3 8.8.8.8
```

📖 **Полная документация:**
- [Quick Start Guide](proxmox/scripts/QUICK-START.md) - 5 минут до первого сервиса
- [Full Documentation](proxmox/scripts/README.md) - Полное руководство по автоматизации
- [Architecture](proxmox/scripts/ARCHITECTURE.md) - Дизайн системы
- [Network Setup](proxmox/scripts/NETWORK-SETUP.md) - Сетевая автоматизация

**Преимущества:**
- ✅ **100% автоматизация** (от Proxmox до production за 78 минут)
- ✅ **Template-based** (клонирование за 2-5 минут)
- ✅ **Proxmox Community Scripts** (374 готовых LXC шаблона)
- ✅ **Умное хранение** (templates на HDD, production на SSD)
- ✅ **Безопасная сеть** (весь трафик через OPNsense firewall)
- ✅ **Infrastructure as Code** (все в Git, воспроизводимо)

---

## VM Templates для мультиплицирования

HDD также настроен для хранения VM templates:

```bash
# Создать VM template
qm template 100

# Клонировать для production (SSD)
qm clone 100 201 --name my-service-01 --full --storage local-lvm

# Клонировать для testing (HDD)
qm clone 100 202 --name my-service-02 --full --storage local-hdd
```

📖 **Подробнее:** См. [proxmox/VM-TEMPLATES-GUIDE.md](proxmox/VM-TEMPLATES-GUIDE.md)

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

Эта конфигурация оптимизирована для **GL.iNet GL-AXT1800 (Slate AX)**:
- ✅ WiFi 6 (802.11ax) - высокая скорость
- ✅ Dual-band (5GHz + 2.4GHz)
- ✅ **3x Gigabit Ethernet (1 WAN + 2 LAN)** - портативный роутер
- ✅ Компактный размер ~10x6x2 см (идеален для поездок)
- ✅ 512 MB RAM (достаточно для AdGuard + VPN)
- ✅ USB 3.0 порт (можно добавить USB-Ethernet для дополнительных портов)
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

A: Да, весь трафик шифруется через WireGuard/AmneziaWG VPN. Публичная сеть видит только зашифрованный туннель.

**Q: Будет ли VPN работать в России с блокировками?**

A: Да! Используйте **AmneziaWG** вместо обычного WireGuard. AmneziaWG маскирует VPN трафик под обычный UDP и обходит DPI блокировки. См. `AMNEZIAWG-SETUP.md` для настройки.

**Q: В чём разница между WireGuard и AmneziaWG?**

A: AmneziaWG — это форк WireGuard с обфускацией трафика. Та же безопасность и почти такая же скорость, но DPI не может определить VPN. Оба протокола могут работать параллельно.

**Q: Зачем нужен российский VPS если есть Oracle Cloud?**

A: **Разные цели:**
- **Oracle Cloud** (не-РФ IP) - для обхода блокировок В России
- **Russia VPS** (РФ IP) - для доступа к РФ сервисам ИЗ-ЗА ГРАНИЦЫ (банки, госуслуги, стриминг)

**Q: Сколько стоит российский VPS?**

A: 150-500₽/мес (~$2-5). Рекомендуем Timeweb VPS-1 за 200₽/мес. Оплата картой РФ или криптовалютой.

**Q: Как переключаться между VPN?**

A: Используйте VPN selector скрипт:
```bash
vpn russia  # Российский IP (за границей)
vpn oracle  # Обход блокировок (в России)
vpn home    # Домашняя сеть
vpn status  # Проверить текущий VPN
```

**Q: Можно ли использовать Russia VPN находясь дома?**

A: Да! Russia VPN работает в обоих режимах:
- **Travel Mode** - прямое подключение к Russia VPS (в отеле/кафе)
- **Home Mode** - через OPNsense firewall (когда роутер дома)

Для Home Mode нужно настроить правила firewall на OPNsense (разрешить UDP 51822). Используется та же AmneziaWG конфигурация, разница только в маршрутизации. Подробности в [docs/HOME-RUSSIA-VPN-SETUP.md](docs/HOME-RUSSIA-VPN-SETUP.md).

**Когда использовать дома:**
- Тестирование перед поездкой
- Доступ к российским сервисам (банки, стриминг)
- Проверка geo-ограничений
- Отладка VPN конфигурации

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

**Дата последнего обновления:** 2025-01-06
**Версия:** 2.0 (полная автоматизация)
**Ключевые изменения:**
- ✅ Сетевая автоматизация (auto-detect, UDEV rules, vmbr0-99)
- ✅ OPNsense VM automation (template + deployment)
- ✅ LXC routing через OPNsense (10.0.30.254 gateway)
- ✅ Полное развертывание системы одной командой
- ✅ 100% Infrastructure as Code
