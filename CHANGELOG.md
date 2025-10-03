# Changelog

## v2.2 - Dual UI стратегия для GL.iNet (2025-10-03)

### Изменено

✏️ **Стратегия использования GL.iNet UI:**
- **БЫЛО:** Рекомендация удалить GL.iNet UI, использовать только LuCI
- **СТАЛО:** Использовать оба интерфейса параллельно!
  - GL.iNet UI (http://192.168.20.1) - для повседневных задач
  - OpenWRT LuCI (http://192.168.20.1:81) - для расширенных настроек

**Обновлённые файлы:**
- ✏️ `GL-AX1800-NOTES.md` - Раздел "GL.iNet специфичные пакеты"
  - Добавлены рекомендации по использованию обоих UI
  - Список задач для GL.iNet UI vs LuCI
  - Удалены инструкции по удалению GL.iNet UI

- ✏️ `QUICK-REFERENCE.md` - Секция "GL.iNet GL-AX1800 специфичные команды"
  - Расширен раздел "Доступ к интерфейсам"
  - Добавлены примеры когда использовать каждый UI
  - Обновлена секция "GL.iNet службы" (убрана команда отключения)

- ✏️ `README.md` - Описание OpenWRT роутера
  - Добавлено упоминание Dual UI
  - Ссылки на оба интерфейса с пояснениями

### Преимущества Dual UI подхода

**GL.iNet UI - для быстрых задач:**
- ✅ Визуальные графики трафика
- ✅ One-click VPN клиент
- ✅ Быстрая настройка WiFi
- ✅ Удобный интерфейс для не-технических пользователей

**OpenWRT LuCI - для продвинутых настроек:**
- ✅ Полный контроль над /etc/config/*
- ✅ Установка пакетов через opkg
- ✅ SSH ключи, cron задачи
- ✅ Применение наших кастомных конфигураций

---

## v2.1 - Оптимизация для Dell XPS L701X (2025-10-03)

### Добавлено

✅ **DELL-XPS-L701X-NOTES.md** (20K) - Полное руководство по оптимизации:
- Характеристики Dell XPS L701X (8GB RAM, SSD+HDD)
- Оптимальная конфигурация дисков (SSD для VM, HDD для backup)
- Настройка USB-Ethernet адаптера (udev rules)
- Оптимизация для 8GB RAM (распределение памяти)
- KSM и Swap настройка для экономии памяти
- Решение проблем с USB-Ethernet стабильностью
- Рекомендации по охлаждению и питанию лаптопа

### Обновлено

**Proxmox конфигурация:**
- ✅ `proxmox-network-interfaces` (3.4K)
  - Обновлено для Dell XPS L701X
  - Встроенный Ethernet → LAN (к OpenWRT)
  - USB-Ethernet → WAN (к ISP Router)
  - Инструкции по созданию udev rules для стабильного имени USB-Ethernet
  - Комментарии по WiFi (опционально)

**Документация:**
- ✅ `README.md` (18K)
  - Добавлена секция о Dell XPS L701X как Proxmox сервер
  - Обновлены параметры OPNsense VM (2GB RAM вместо 4GB)
  - Информация о storage (SSD 250GB + HDD 500GB)
  - Заметка об AdGuard на OpenWRT (экономия RAM)

- ✅ `FILES-INDEX.md` (9.5K)
  - Добавлен DELL-XPS-L701X-NOTES.md в индекс
  - Обновлено описание Proxmox конфигурации

### Ключевые оптимизации

#### 1. Распределение памяти (8GB total)
```
Proxmox host:    1 GB
OPNsense VM:     2 GB (вместо 4GB)
AdGuard:         на OpenWRT (0 GB на Proxmox)
LXC контейнеры:  4-5 GB
```

#### 2. Storage стратегия
```
SSD 250GB (fast):
  - Proxmox система
  - OPNsense VM
  - Критичные LXC (databases)

HDD 500GB (slow):
  - ISO образы
  - Backup VM/LXC
  - Большие LXC (Nextcloud, media)
```

#### 3. Сетевые интерфейсы
```
До:
  enp0s31f6 → WAN
  enp1s0 → LAN

После (Dell XPS L701X):
  eth-usb (USB-Ethernet) → WAN
  eth-builtin (встроенный) → LAN
  + udev rules для стабильности
```

---

## v2.0 - Обновление для GL.iNet GL-AX1800 (2025-10-03)

### Добавлено

✅ **GL-AX1800-NOTES.md** (11K) - Полное руководство по GL.iNet GL-AX1800:
- Технические характеристики и физические порты
- Особенности GL.iNet прошивки (dual firmware system)
- DSA (Distributed Switch Architecture) конфигурация
- WiFi 6 (802.11ax) настройки и оптимизация
- LED управление и индикаторы
- Reset и recovery процедуры
- Известные проблемы и решения
- Полезные команды и рекомендуемые пакеты

### Обновлено

#### Конфигурационные файлы OpenWRT

**Home Mode:**
- ✅ `openwrt-home-network` (2.6K)
  - Обновлено для DSA архитектуры
  - Порты: `wan`, `lan1`, `lan2`, `lan3`, `lan4`
  - Удалена устаревшая swconfig конфигурация

- ✅ `openwrt-home-wireless` (4.0K)
  - WiFi 6 (802.11ax) поддержка
  - 5GHz: `HE80` (вместо VHT80)
  - 2.4GHz: `HE40` (вместо HT40)
  - MU-MIMO beamforming включен
  - MediaTek MT7915 чипсет

**Travel Mode:**
- ✅ `openwrt-travel-network` (3.3K)
  - DSA порты для GL-AX1800
  - WAN порт: `wan` (синий порт)
  - LAN порты: `lan1-lan4` (желтые порты)

- ✅ `openwrt-travel-wireless` (2.7K)
  - WiFi 6 настройки для портативного режима
  - Оптимизация для публичных сетей

#### Документация

- ✅ `README.md` (17K)
  - Добавлена секция о GL.iNet GL-AX1800
  - Обновлена секция "Рекомендуемое оборудование"
  - Добавлены ссылки на GL-AX1800-NOTES.md

- ✅ `FILES-INDEX.md` (9.1K)
  - Добавлен GL-AX1800-NOTES.md в индекс
  - Добавлена информация о DSA портах
  - Обновлены описания WiFi 6 конфигураций

- ✅ `QUICK-REFERENCE.md` (17K)
  - Новая секция "GL.iNet GL-AX1800 специфичные команды"
  - Команды для проверки DSA портов
  - WiFi 6 диагностика
  - GL.iNet службы управление
  - Hardware offloading настройки
  - Ссылки на дополнительные ресурсы

## Ключевые изменения

### DSA vs swconfig

**Старая архитектура (swconfig):**
```
config switch
	option name 'switch0'
	option ports '0 1 2 3 6'
```

**Новая архитектура (DSA):**
```
config device
	option name 'br-lan'
	option type 'bridge'
	list ports 'lan1'
	list ports 'lan2'
	list ports 'lan3'
	list ports 'lan4'
```

### WiFi 5 → WiFi 6

**До:**
- 5GHz: `htmode 'VHT80'` (802.11ac)
- 2.4GHz: `htmode 'HT40'` (802.11n)

**После:**
- 5GHz: `htmode 'HE80'` (802.11ax WiFi 6)
- 2.4GHz: `htmode 'HE40'` (802.11ax WiFi 6)
- Beamforming: enabled
- MU-MIMO: enabled

### Физические порты GL-AX1800

```
Задняя панель:
┌──────────────────────┐
│ WAN (синий)          │ ← К OPNsense дома / Hotel WiFi в поездке
│ LAN1 LAN2 LAN3 LAN4  │ ← Ваши устройства
│ (желтые)             │
│ POWER    USB 3.0     │
└──────────────────────┘
```

## Совместимость

✅ Все конфигурации оптимизированы для GL.iNet GL-AX1800 (Flint)
✅ Совместимо с GL.iNet firmware 4.x (на базе OpenWRT 21.02+)
✅ Поддержка WiFi 6 (802.11ax)
✅ DSA (Distributed Switch Architecture)
✅ Dual firmware system (GL.iNet UI + OpenWRT LuCI)

## Альтернативные устройства

Конфигурации могут быть адаптированы для:
- GL.iNet GL-MT3000 (Beryl AX) - требуется изменение портов
- TP-Link Archer AX23 - требуется адаптация wireless config
- Другие роутеры с OpenWRT 21.02+ и DSA

## Что не изменилось

- ✅ Сетевая архитектура (Proxmox → OPNsense → OpenWRT)
- ✅ IP адресация всех сетей
- ✅ Firewall правила
- ✅ VPN конфигурации (WireGuard)
- ✅ AdGuard Home настройки
- ✅ Oracle Cloud конфигурация

## Проверка после обновления

После применения конфигурации на GL-AX1800:

```bash
# Проверить DSA порты
ip link show | grep -E "wan|lan[1-4]"

# Проверить WiFi 6
iw list | grep -A 10 "HE cap"

# Проверить bridge
bridge link show

# Статус OpenWRT
ubus call system board

# GL.iNet версия
cat /etc/glversion
```

## Файлы в директории (21 файл, ~141 KB)

```
Документация (5 файлов):
  - README.md (17K)
  - FILES-INDEX.md (9.1K)
  - GL-AX1800-NOTES.md (11K) ⭐ NEW
  - NETWORK-DIAGRAM.txt (27K)
  - QUICK-REFERENCE.md (17K)
  - CHANGELOG.md ⭐ NEW

Proxmox (1 файл):
  - proxmox-network-interfaces (2.6K)

OPNsense (1 файл):
  - opnsense-interfaces-config.txt (7.0K)

OpenWRT Home (4 файла):
  - openwrt-home-network (2.6K) ✏️ UPDATED
  - openwrt-home-wireless (4.0K) ✏️ UPDATED
  - openwrt-home-dhcp (3.5K)
  - openwrt-home-firewall (7.4K)

OpenWRT Travel (4 файла):
  - openwrt-travel-network (3.3K) ✏️ UPDATED
  - openwrt-travel-wireless (2.7K) ✏️ UPDATED
  - openwrt-travel-dhcp (2.9K)
  - openwrt-travel-firewall (6.0K)

Скрипты (4 файла):
  - openwrt-mode-switcher.sh (3.6K)
  - openwrt-init-mode-detector (752B)
  - openwrt-vpn-failover.sh (2.3K)
  - openwrt-install-script.sh (2.4K)

Дополнительно (2 файла):
  - adguardhome-config.yaml (5.2K)
  - oracle-cloud-wireguard.conf (3.2K)
```

## Следующие шаги

1. Прочитайте `GL-AX1800-NOTES.md` для понимания устройства
2. Примените конфигурации согласно `README.md`
3. Используйте `QUICK-REFERENCE.md` для диагностики
4. Сделайте backup перед изменениями!

---

**Автор:** Configuration Generator
**Версия:** 2.0 (GL-AX1800 optimized)
**Дата:** 2025-10-03
