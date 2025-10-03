# Индекс файлов конфигурации

## Документация

| Файл | Описание |
|------|----------|
| `README.md` | Полная документация по установке и использованию |
| `FILES-INDEX.md` | Этот файл - краткое описание всех конфигураций |
| `DELL-XPS-L701X-NOTES.md` | Оптимизация Proxmox для Dell XPS L701X (8GB RAM, USB-Ethernet) |
| `GL-AX1800-NOTES.md` | Специфичные настройки для GL.iNet GL-AX1800 (Flint) |
| `NETWORK-DIAGRAM.txt` | ASCII диаграммы сетевой архитектуры |
| `QUICK-REFERENCE.md` | Быстрые команды и troubleshooting |
| `CHANGELOG.md` | История изменений конфигурации |

## Proxmox

| Файл | Назначение | Путь установки |
|------|------------|----------------|
| `proxmox-network-interfaces` | Конфигурация сетевых интерфейсов и bridges | `/etc/network/interfaces` |

**Содержит:**
- vmbr0 (WAN к ISP)
- vmbr1 (LAN к OpenWRT)
- vmbr2 (Internal для LXC)
- vmbr99 (Management)

## OPNsense

| Файл | Назначение | Применение |
|------|------------|------------|
| `opnsense-interfaces-config.txt` | Полная конфигурация OPNsense VM | Настройка через Web UI |

**Содержит:**
- Настройки VM в Proxmox
- Конфигурацию интерфейсов (WAN, LAN, INTERNAL, MGMT)
- DHCP серверы
- Правила firewall
- NAT
- WireGuard VPN для travel router

## OpenWRT - Режим ДОМА

**Устройство:** GL.iNet GL-AX1800 (Flint) с WiFi 6 (802.11ax)

| Файл | Назначение | Путь установки |
|------|------------|----------------|
| `openwrt-home-network` | Сетевые интерфейсы и routing (DSA) | `/etc/config/network` |
| `openwrt-home-wireless` | WiFi 6 конфигурация (SSID, шифрование) | `/etc/config/wireless` |
| `openwrt-home-dhcp` | DHCP server и DNS forwarding | `/etc/config/dhcp` |
| `openwrt-home-firewall` | Правила firewall и forwarding | `/etc/config/firewall` |

**Сети дома:**
- LAN: 192.168.20.0/24 (основная)
- Guest: 192.168.30.0/24 (изолированная)
- IoT: 192.168.40.0/24 (умный дом)

**SSID:**
- HomeNet-5G / HomeNet-2G (WPA3)
- Guest-5G (WPA3, изоляция)
- Smart-Home (WPA2, IoT)

## OpenWRT - Режим В ПОЕЗДКЕ

**Устройство:** GL.iNet GL-AX1800 (Flint) - портативный VPN роутер

| Файл | Назначение | Путь установки |
|------|------------|----------------|
| `openwrt-travel-network` | Сеть с WireGuard VPN (DSA) | `/etc/config/network` |
| `openwrt-travel-wireless` | WiFi 6 для ваших устройств | `/etc/config/wireless` |
| `openwrt-travel-dhcp` | DHCP с DNS через VPN | `/etc/config/dhcp` |
| `openwrt-travel-firewall` | Строгий firewall для публичных сетей | `/etc/config/firewall` |

**Сети в поездке:**
- LAN: 192.168.100.0/24 (ваши устройства)
- WireGuard Home: 10.0.200.10/32
- WireGuard Oracle: 10.1.200.10/32

**SSID:**
- Travel-Secure-5G / Travel-Secure-2G (WPA3)
- Весь трафик через VPN

## Скрипты OpenWRT

| Файл | Назначение | Путь установки |
|------|------------|----------------|
| `openwrt-mode-switcher.sh` | Автоматическое переключение home/travel | `/usr/bin/openwrt-mode-switcher.sh` |
| `openwrt-init-mode-detector` | Init script для автозапуска | `/etc/init.d/mode-detector` |
| `openwrt-vpn-failover.sh` | Автоматический failover между VPN | `/usr/bin/openwrt-vpn-failover.sh` |
| `openwrt-install-script.sh` | Скрипт установки всех компонентов | Запустить на OpenWRT |

**Функции:**
- Определение локации (дома/поездка)
- Автоматическое переключение конфигураций
- Мониторинг VPN соединений
- Failover с Home на Oracle

## AdGuard Home

| Файл | Назначение | Путь установки |
|------|------------|----------------|
| `adguardhome-config.yaml` | Конфигурация AdGuard Home | `/etc/adguardhome.yaml` |

**Содержит:**
- DNS серверы (DoH/DoT)
- Фильтры блокировки рекламы
- Настройки кеша
- Логирование
- Статистика

**Доступ:** http://192.168.20.1:3000

## Oracle Cloud

| Файл | Назначение | Путь установки |
|------|------------|----------------|
| `oracle-cloud-wireguard.conf` | WireGuard конфигурация для Oracle | `/etc/wireguard/wg0.conf` |

**Содержит:**
- WireGuard server настройки
- Peers: OpenWRT travel + Home OPNsense
- Routing для site-to-site VPN
- iptables правила

## Порядок установки

### 1. Proxmox (первым)
```bash
cp proxmox-network-interfaces /etc/network/interfaces
# Отредактировать имена интерфейсов
ifreload -a
```

### 2. OPNsense VM (вторым)
```bash
# Создать VM в Proxmox
# Установить OPNsense
# Настроить по opnsense-interfaces-config.txt
```

### 3. OpenWRT (третьим)
```bash
# Запустить openwrt-install-script.sh
# Скопировать home configs в /etc/openwrt-configs/home/
# Скопировать travel configs в /etc/openwrt-configs/travel/
# Настроить adguardhome-config.yaml
```

### 4. Oracle Cloud (последним)
```bash
# Создать instance
# Настроить oracle-cloud-wireguard.conf
# Настроить firewall в OCI Console
```

## Важные замены перед использованием

### В конфигах OpenWRT travel mode:

- `YOUR_OPENWRT_PRIVATE_KEY_HERE` → приватный ключ OpenWRT
- `OPNSENSE_PUBLIC_KEY_HERE` → публичный ключ OPNsense
- `ORACLE_PUBLIC_KEY_HERE` → публичный ключ Oracle
- `your-home-ddns.example.com` → ваш домашний DDNS адрес
- `oracle-instance.region.oraclecloud.com` → IP Oracle instance

### В конфигах WiFi:

- `YOUR_STRONG_PASSWORD_HERE` → основной WiFi пароль
- `GUEST_PASSWORD_HERE` → гостевой WiFi пароль
- `IOT_PASSWORD_HERE` → IoT WiFi пароль
- `TRAVEL_WIFI_PASSWORD_HERE` → travel WiFi пароль

### В AdGuard Home:

- `$2a$10$CHANGE_THIS_HASH_AFTER_INSTALL` → хэш пароля admin
- Изменить через Web UI после первого входа

### В Oracle Cloud:

- `ORACLE_SERVER_PRIVATE_KEY_HERE` → приватный ключ Oracle
- `OPENWRT_PUBLIC_KEY_HERE` → публичный ключ OpenWRT
- `OPNSENSE_PUBLIC_KEY_HERE` → публичный ключ OPNsense

## Генерация WireGuard ключей

```bash
# На каждом устройстве (OpenWRT, OPNsense, Oracle):
wg genkey | tee privatekey | wg pubkey > publickey

# Приватный ключ идёт в [Interface] PrivateKey
# Публичный ключ идёт в [Peer] PublicKey на другой стороне
```

## Проверка после установки

### Дома:
```bash
# Проверить доступ к OPNsense
ping 192.168.10.1

# Проверить доступ к OpenWRT
ping 192.168.20.1

# Проверить DNS (AdGuard)
nslookup google.com 192.168.20.1

# Проверить доступ к LXC
ping 10.0.30.1
```

### В поездке:
```bash
# Подключиться к OpenWRT
ssh root@192.168.100.1

# Проверить WireGuard
wg show

# Проверить доступ к дому через VPN
ping 10.0.99.10
```

## Backup критичных файлов

### Сохранить локально:
- Все конфиги из этой директории
- WireGuard приватные ключи
- Backup OpenWRT (sysupgrade -b)
- Backup OPNsense (System → Configuration → Backups)
- Пароли WiFi и Web UI

### Хранить в безопасном месте:
- Encrypted USB drive
- Password manager (BitWarden, 1Password)
- Git репозиторий (private, без приватных ключей)

## Поддерживаемые версии

- **Proxmox VE:** 8.0+
- **OPNsense:** 23.7+
- **OpenWRT:** 23.05+
- **AdGuard Home:** 0.107+
- **Ubuntu (Oracle):** 22.04 LTS

## Быстрые ссылки

- Proxmox: https://YOUR_IP:8006
- OPNsense: https://192.168.10.1
- OpenWRT дома: http://192.168.20.1
- OpenWRT поездка: http://192.168.100.1
- AdGuard Home: http://192.168.20.1:3000

## Получение помощи

1. Проверьте README.md → раздел Troubleshooting
2. Просмотрите логи: `logread -f` (OpenWRT) или System → Log (OPNsense)
3. Проверьте сетевую связность: `ping`, `traceroute`, `wg show`
4. Создайте issue в репозитории с подробным описанием проблемы

---

**Все файлы готовы к использованию!** Начните с установки Proxmox, затем OPNsense, затем OpenWRT.
