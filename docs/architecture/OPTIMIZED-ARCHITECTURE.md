# Оптимизированная архитектура Home Lab

## Обзор

Оптимизированная архитектура переносит DNS и VPN сервисы с Proxmox на GL-AXT1800 Slate AX для освобождения RAM.

## Проблема

**Dell XPS L701X (Proxmox host):**
- RAM: 8 GB DDR3 (не расширяется)
- OPNsense VM: 2 GB
- 9 LXC контейнеров: ~4 GB
- **Свободно:** ~0.5 GB ❌ (критически мало!)

## Решение

**Перенос сервисов на GL-AXT1800 Slate AX:**
- AdGuard Home: ~100 MB
- WireGuard Server: ~20 MB
- AmneziaWG Server: ~20 MB
- **Освобождено на Proxmox:** ~1 GB ✅

## Диаграмма архитектуры

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                    ┌─────────┴─────────┐
                    │   ISP Router      │
                    │  192.168.1.1/24   │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                 PROXMOX VE                 │
        │         Dell XPS L701X (8GB RAM)          │
        │                                            │
        │  ┌──────────────────────────────────┐    │
        │  │      OPNsense Firewall (2GB)     │    │
        │  │                                   │    │
        │  │  WAN:  vmbr0 (ISP DHCP)          │    │
        │  │  LAN:  192.168.10.1/24           │◄───┼─── vmbr1
        │  │  INT:  10.0.30.254/24            │◄───┼─── vmbr2
        │  │  MGMT: 10.0.99.10/24             │◄───┼─── vmbr99
        │  │                                   │    │
        │  │  ┌─────────────────────────────┐ │    │
        │  │  │   Nginx Reverse Proxy       │ │    │
        │  │  │   Port 443 (HTTPS)          │ │    │
        │  │  └─────────────────────────────┘ │    │
        │  └──────────────────────────────────┘    │
        │                      │                    │
        │  ┌───────────────────┼──────────────┐    │
        │  │    LXC Containers (10.0.30.0/24) │    │
        │  │                                   │    │
        │  │  200: PostgreSQL   (10.0.30.10)  │    │
        │  │  201: Redis        (10.0.30.20)  │    │
        │  │  202: Nextcloud    (10.0.30.30)  │    │
        │  │  203: Gitea        (10.0.30.40)  │    │
        │  │  204: Home Assist  (10.0.30.50)  │    │
        │  │  205: Grafana      (10.0.30.60)  │    │
        │  │  206: Prometheus   (10.0.30.70)  │    │
        │  │  207: Nginx Proxy  (10.0.30.80)  │    │
        │  │  208: Docker       (10.0.30.90)  │    │
        │  │                                   │    │
        │  │  Gateway: 10.0.30.254 (OPNsense) │    │
        │  └───────────────────────────────────┘    │
        └─────────────────────────────────────────────┘
                              │
                              │ vmbr1 (192.168.10.0/24)
                              │
        ┌─────────────────────┴─────────────────────┐
        │        GL-AXT1800 Slate AX (512MB RAM)    │
        │          192.168.10.2 (WAN от OPNsense)   │
        │                                            │
        │  ┌──────────────────────────────────────┐ │
        │  │       AdGuard Home (~100MB)          │ │
        │  │       DNS: 53                        │ │
        │  │       Web: 3000                      │ │
        │  │       https://adguard.home.local     │ │
        │  └──────────────────────────────────────┘ │
        │                                            │
        │  ┌──────────────────────────────────────┐ │
        │  │   WireGuard Server (~20MB)           │ │
        │  │   Port: 51820 (UDP)                  │ │
        │  │   Network: 10.0.200.0/24             │ │
        │  │   Access: Home LAN + LXC + MGMT      │ │
        │  └──────────────────────────────────────┘ │
        │                                            │
        │  ┌──────────────────────────────────────┐ │
        │  │   AmneziaWG Server (~20MB)           │ │
        │  │   Port: 51821 (UDP)                  │ │
        │  │   Network: 10.8.2.0/24               │ │
        │  │   Access: Internet only (no LAN)     │ │
        │  └──────────────────────────────────────┘ │
        │                                            │
        │  WiFi:  192.168.20.1/24 (LAN)             │
        │  Guest: 192.168.30.1/24                   │
        │  IoT:   192.168.40.1/24                   │
        └────────────────────────────────────────────┘
                     │       │       │
                     ▼       ▼       ▼
              ┌──────────┬──────────┬──────────┐
              │ Laptops  │ Phones   │ IoT      │
              │ Tablets  │ Desktop  │ Devices  │
              └──────────┴──────────┴──────────┘

    ┌─────────────────────────────────────────────┐
    │         VPN Clients (Remote Access)         │
    │                                             │
    │  WireGuard (10.0.200.0/24):                │
    │  ├─ slate-ax-travel (10.0.200.10)          │
    │  ├─ android-phone   (10.0.200.20)          │
    │  ├─ laptop          (10.0.200.30)          │
    │  └─ ipad            (10.0.200.40)          │
    │                                             │
    │  AmneziaWG (10.8.2.0/24):                  │
    │  ├─ russia-client-1 (10.8.2.10)            │
    │  ├─ russia-client-2 (10.8.2.20)            │
    │  └─ russia-client-3 (10.8.2.30)            │
    └─────────────────────────────────────────────┘
```

## Nginx Reverse Proxy

```
Client Browser
      │
      ├─ https://adguard.home.local ──┐
      ├─ https://router.home.local ───┤
      └─ https://luci.home.local ─────┤
                                      │
                                      ▼
                          ┌─────────────────────┐
                          │  OPNsense Nginx     │
                          │  10.0.99.10:443     │
                          │                     │
                          │  ✅ HTTPS терминация│
                          │  ✅ Rate limiting   │
                          │  ✅ Security headers│
                          │  ✅ Logging         │
                          └─────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
    192.168.10.2:3000       192.168.10.2:80         192.168.10.2:81
    AdGuard Home            GL.iNet UI              OpenWRT LuCI
```

## Port Forwarding на OPNsense

```
Internet (WAN)
      │
      ├─ UDP 51820 ──► 192.168.10.2:51820  (WireGuard Server)
      └─ UDP 51821 ──► 192.168.10.2:51821  (AmneziaWG Server)
```

## Два режима работы Slate AX

### HOME MODE (дома за OPNsense)

```
Slate AX WAN:  192.168.10.2  (от OPNsense LAN)
Slate AX LAN:  192.168.20.1  (WiFi клиенты)

Сервисы:
  ✅ AdGuard Home         (DNS для всей сети)
  ✅ WireGuard Server     (VPN в домашнюю сеть)
  ✅ AmneziaWG Server     (VPN для России)
  ✅ WiFi Access Point    (домашняя сеть)
```

### TRAVEL MODE (в поездке, VPN туннель)

```
Slate AX WAN:  DHCP от отеля/кафе
Slate AX LAN:  192.168.100.1  (ваши устройства)
Slate AX VPN:  WireGuard → Home OPNsense

Новые возможности (firmware 4.8.2):
  ✅ VPN Multi-Instance   (Oracle + Russia + Home одновременно)
  ✅ VPN Composite Policy (умная маршрутизация по доменам)
  ✅ VPN Failover         (автопереключение при блокировках)
```

## Сравнение: ДО и ПОСЛЕ

| Параметр | До оптимизации | После оптимизации |
|----------|----------------|-------------------|
| **Proxmox RAM** | | |
| OPNsense VM | 2.0 GB | 2.0 GB |
| LXC контейнеры | 4.0 GB | 4.0 GB |
| AdGuard Home | 0.2 GB (LXC) | - |
| VPN серверы | 0.3 GB (планировалось) | - |
| **Свободно** | **0.5 GB** ❌ | **1.5 GB** ✅ |
| | | |
| **Slate AX RAM** | | |
| AdGuard Home | - | 0.1 GB |
| WireGuard Server | - | 0.02 GB |
| AmneziaWG Server | - | 0.02 GB |
| OpenWRT + WiFi | 0.15 GB | 0.15 GB |
| **Свободно** | **0.35 GB** | **0.21 GB** |
| | | |
| **VPN Capabilities** | | |
| Удалённый доступ | OPNsense только | ✅ Slate AX WireGuard |
| Россия клиенты | Нет | ✅ Slate AX AmneziaWG |
| VPN Multi-Instance | Нет | ✅ firmware 4.8.2 |
| VPN Composite Policy | Нет | ✅ firmware 4.8.2 |

## Преимущества оптимизации

### 1. Производительность
- ✅ **+1 GB RAM на Proxmox** - можно запустить новые LXC сервисы
- ✅ **Меньше нагрузка на Proxmox** - DNS/VPN не создают нагрузку на CPU
- ✅ **Slate AX 512MB RAM** - достаточно для всех сервисов

### 2. Надёжность
- ✅ **VPN работает без Proxmox** - если Proxmox выключен, VPN серверы всё равно работают
- ✅ **Независимость сервисов** - перезагрузка Proxmox не влияет на VPN клиентов
- ✅ **Аппаратная отказоустойчивость** - роутер более надёжен чем VM

### 3. Безопасность
- ✅ **Nginx Reverse Proxy** - HTTPS терминация, rate limiting
- ✅ **Изоляция AmneziaWG** - клиенты не видят домашнюю сеть
- ✅ **Firewall на OPNsense** - централизованный контроль доступа

### 4. Удобство
- ✅ **Красивые домены** - `adguard.home.local` вместо `192.168.20.1:3000`
- ✅ **HTTPS везде** - безопасный доступ к Web UI
- ✅ **VPN Multi-Instance** - несколько VPN одновременно (firmware 4.8.2)
- ✅ **VPN Composite Policy** - умная маршрутизация (firmware 4.8.2)

## Быстрый старт

### 1. Установка VPN серверов на Slate AX

```bash
# Запустить автоустановку
bash manual-scripts/openwrt/setup-vpn-servers.sh

# Скрипт автоматически:
# ✅ Установит WireGuard и AmneziaWG
# ✅ Сгенерирует ключи серверов
# ✅ Создаст конфигурации
# ✅ Настроит автозагрузку
# ✅ Запустит VPN серверы
```

### 2. Генерация клиентских конфигураций

```bash
# Запустить генератор
bash manual-scripts/openwrt/generate-vpn-client-configs.sh

# Скрипт создаст:
# ✅ Конфигурации для WireGuard клиентов
# ✅ Конфигурации для AmneziaWG клиентов
# ✅ QR коды для мобильных устройств
# ✅ Инструкции по добавлению на сервер
```

### 3. Настройка Nginx Reverse Proxy на OPNsense

```bash
# 1. Установить Nginx plugin
#    System → Firmware → Plugins → os-nginx

# 2. Создать SSL сертификат
#    System → Trust → Certificates → *.home.local

# 3. Применить конфигурацию
#    См. opnsense/configs/nginx-reverse-proxy-slate-ax.conf

# 4. Добавить DNS записи в AdGuard Home
#    adguard.home.local → 10.0.99.10
#    router.home.local → 10.0.99.10
#    luci.home.local → 10.0.99.10
```

### 4. Настройка Firewall на OPNsense

```bash
# Применить правила
# См. opnsense/configs/firewall-rules-vpn-servers.txt

# Основные правила:
# ✅ WAN:51820 → 192.168.10.2:51820 (WireGuard)
# ✅ WAN:51821 → 192.168.10.2:51821 (AmneziaWG)
# ✅ LAN → 192.168.10.2:3000 (AdGuard Web UI)
# ✅ VPN clients → Home network access
```

## Мониторинг

### Proxmox RAM usage

```bash
# На Proxmox host
free -h

# Ожидается:
# Used: ~6.5 GB (было ~7.5 GB)
# Free: ~1.5 GB (было ~0.5 GB)
```

### Slate AX VPN status

```bash
# SSH на Slate AX
ssh root@192.168.20.1

# WireGuard status
wg show wg0

# AmneziaWG status
awg show awg0

# Активные клиенты
wg show wg0 | grep peer
awg show awg0 | grep peer
```

### Nginx Reverse Proxy logs

```bash
# На OPNsense
tail -f /var/log/nginx/adguard_access.log
tail -f /var/log/nginx/router_access.log
tail -f /var/log/nginx/luci_access.log
```

## Файлы конфигурации

```
openwrt/
├── home/
│   ├── wireguard-server-home.conf       # WireGuard сервер
│   └── amneziawg-server-home.conf       # AmneziaWG сервер
└── scripts/
    ├── setup-vpn-servers.sh             # Автоустановка
    └── generate-vpn-client-configs.sh   # Генератор клиентов

opnsense/
└── configs/
    ├── nginx-reverse-proxy-slate-ax.conf    # Nginx config
    └── firewall-rules-vpn-servers.txt       # Firewall rules
```

## Дополнительная документация

- **Полная архитектура:** `/tmp/optimized-architecture-slate-ax.md` (700+ строк)
- **Summary:** `/tmp/architecture-optimization-summary.md`
- **GL-AXT1800 спецификации:** `hardware/gl-inet/GL-AXT1800-NOTES.md`
- **Главная документация:** `README.md`

## Поддержка

Вопросы и улучшения: создавайте issues в вашем репозитории.

---

**Версия:** 2.1
**Дата:** 2025-10-06
**Статус:** Production Ready ✅
