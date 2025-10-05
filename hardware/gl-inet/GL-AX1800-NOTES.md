# GL.iNet GL-AX1800 (Flint) - Специфичные настройки

## Технические характеристики

**Процессор:** MediaTek MT7621A (880 MHz, dual-core)
**RAM:** 512 MB DDR3
**Flash:** 128 MB NAND
**WiFi:** MediaTek MT7915 (WiFi 6, 802.11ax)
- 5GHz: до 1200 Mbps (2×2 MU-MIMO)
- 2.4GHz: до 574 Mbps (2×2 MU-MIMO)

**Ethernet:** 5x Gigabit (1 WAN + 4 LAN)
**USB:** 1x USB 3.0
**Прошивка:** GL.iNet firmware на базе OpenWRT 21.02+

## Физические порты

```
[Антенны]
     │
┌────┴────────────────────────┐
│   GL.iNet GL-AX1800         │
│                             │
│  Передняя панель:           │
│  - LED индикаторы           │
│  - Reset кнопка             │
│                             │
│  Задняя панель:             │
│  ┌─────────────────────┐    │
│  │ WAN (синий порт)    │    │ ← Подключить к OPNsense дома
│  │ LAN1 LAN2 LAN3 LAN4 │    │ ← Ваши устройства
│  │ (желтые порты)      │    │
│  │ POWER   USB 3.0     │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
```

## Особенности GL.iNet прошивки

### 1. Dual Firmware System
GL-AX1800 имеет две системы прошивки:
- **GL.iNet UI** (порт 80/83) - удобный Web UI от GL.iNet
- **OpenWRT LuCI** (порт 81) - стандартный OpenWRT интерфейс

**Доступ:**
```bash
GL.iNet UI:   http://192.168.20.1 (или http://192.168.8.1 по умолчанию)
OpenWRT LuCI: http://192.168.20.1:81
```

### 2. DSA (Distributed Switch Architecture)

GL-AX1800 использует **современную DSA архитектуру**, а не старый swconfig.

**Порты:**
- `wan` - физический WAN порт (синий)
- `lan1` - физический LAN порт 1 (желтый)
- `lan2` - физический LAN порт 2 (желтый)
- `lan3` - физический LAN порт 3 (желтый)
- `lan4` - физический LAN порт 4 (желтый)

**Проверка портов:**
```bash
# Показать все сетевые интерфейсы
ip link show

# Проверить DSA bridge
bridge link show

# Статус портов
cat /sys/class/net/wan/operstate
cat /sys/class/net/lan1/operstate
```

### 3. WiFi интерфейсы

**Radio0 (5GHz):**
- Path: `platform/soc/1e140000.pcie/pci0000:00/0000:00:01.0/0000:02:00.0`
- Интерфейс: `wlan0`
- Стандарт: 802.11ax (WiFi 6)
- Макс скорость: 1200 Mbps

**Radio1 (2.4GHz):**
- Path: `platform/soc/1e140000.pcie/pci0000:00/0000:00:00.0/0000:01:00.0`
- Интерфейс: `wlan1`
- Стандарт: 802.11ax (WiFi 6)
- Макс скорость: 574 Mbps

**Проверка WiFi:**
```bash
# Показать статус WiFi
wifi status

# Сканирование каналов
iw dev wlan0 scan
iw dev wlan1 scan

# Показать подключенных клиентов
iw dev wlan0 station dump
iw dev wlan1 station dump
```

### 4. WiFi 6 особенности

GL-AX1800 поддерживает:
- ✅ MU-MIMO (Multi-User MIMO)
- ✅ OFDMA (Orthogonal Frequency-Division Multiple Access)
- ✅ BSS Coloring (для уменьшения интерференции)
- ✅ Target Wake Time (TWT) для экономии энергии клиентов
- ✅ 1024-QAM модуляция
- ✅ Beamforming (направленная передача)

**Оптимальные настройки htmode:**
- 5GHz: `HE80` (80 MHz каналы) - рекомендуется
- 5GHz: `HE160` (160 MHz) - максимальная скорость, но меньше каналов
- 2.4GHz: `HE40` (40 MHz) - рекомендуется
- 2.4GHz: `HE20` (20 MHz) - для максимальной совместимости

### 5. GL.iNet специфичные пакеты

GL.iNet добавляет дополнительные пакеты:
- `gl-ui` - GL.iNet Web UI (удобный графический интерфейс)
- `gl-sdk4-*` - SDK пакеты
- `gl-tertf` - Traffic statistics
- `gl-wan-monitor` - WAN мониторинг

**Рекомендация:** Использовать оба интерфейса вместе!

**GL.iNet UI** - для:
- ✅ Быстрая настройка WiFi, VPN, firewall
- ✅ Графические графики трафика
- ✅ Удобный VPN клиент
- ✅ One-click функции (AdGuard, VPN, repeater mode)

**OpenWRT LuCI** - для:
- ✅ Расширенные настройки сети
- ✅ Детальная конфигурация firewall
- ✅ Ручное редактирование /etc/config/*
- ✅ Установка дополнительных пакетов

**Доступ к обоим интерфейсам:**
```bash
# GL.iNet UI (основной, удобный)
http://192.168.20.1

# OpenWRT LuCI (расширенный)
http://192.168.20.1:81

# Оба используют одинаковый логин/пароль
```

### 6. LED индикаторы

GL-AX1800 имеет RGB LED:
- **Белый** - нормальная работа
- **Синий** - подключение WAN
- **Красный** - ошибка/нет интернета
- **Зеленый** - VPN активен (можно настроить)

**Управление LED:**
```bash
# Статус LED
ls /sys/class/leds/

# Примеры управления
echo 1 > /sys/class/leds/blue:power/brightness
echo 0 > /sys/class/leds/blue:power/brightness
```

### 7. Reset и Recovery

**Мягкий сброс (через интерфейс):**
- GL.iNet UI → More Settings → Reset Firmware

**Аппаратный сброс:**
1. Включить роутер
2. Удерживать кнопку Reset 10 секунд
3. LED замигает - отпустить кнопку
4. Роутер вернется к заводским настройкам

**U-Boot Recovery Mode:**
1. Выключить роутер
2. Зажать кнопку Reset
3. Включить питание (держать Reset)
4. Когда LED начнет мигать - отпустить
5. Роутер в режиме U-Boot (192.168.1.1)
6. Загрузить прошивку через http://192.168.1.1

## Подключение к домашней сети

### Дома (режим роутера)

```
OPNsense LAN ──► WAN порт (синий) GL-AX1800
                       │
                  LAN порты (желтые) + WiFi
                       │
                  Ваши устройства
```

**Важно:**
- WAN порт GL-AX1800 → в OPNsense LAN (192.168.10.1)
- Получит IP: 192.168.10.2 (static)
- LAN сеть GL-AX1800: 192.168.20.0/24

### В поездке (VPN режим)

**Вариант 1: Проводное подключение**
```
Hotel Ethernet ──► WAN порт (синий) GL-AX1800
                         │
                    VPN туннель
                         │
                    Домашняя сеть
```

**Вариант 2: WiFi клиент**
```
Hotel WiFi (беспроводное подключение)
       │
       ↓
GL-AX1800 WiFi Client Mode
       │
  VPN туннель
       │
  Домашняя сеть
```

Для WiFi клиента добавьте в `/etc/config/wireless`:
```
config wifi-iface 'wwan'
	option device 'radio0'
	option mode 'sta'
	option network 'wan'
	option ssid 'Hotel_WiFi_Name'
	option encryption 'psk2'
	option key 'hotel_password'
```

## Оптимизация производительности

### 1. NAT Hardware Offloading
```bash
# Проверить статус
cat /sys/module/xt_FLOWOFFLOAD/parameters/module_disabled

# Включить в /etc/config/firewall
config defaults
	option flow_offloading '1'
	option flow_offloading_hw '1'
```

### 2. WiFi оптимизация
```bash
# В /etc/config/wireless добавить:
config wifi-device 'radio0'
	option noscan '1'              # Ускорение запуска
	option amsdu '1'               # A-MSDU aggregation
	option mu_beamformer '1'       # MU-MIMO
```

### 3. Производительность WireGuard
```bash
# Установить оптимизированную версию
opkg update
opkg install wireguard-tools kmod-wireguard

# Проверить загрузку модуля
lsmod | grep wireguard
```

### 4. SQM QoS (для стабильного интернета)
```bash
# Установить
opkg install luci-app-sqm sqm-scripts

# Настроить через LuCI:
# Network → SQM QoS
# Interface: wan
# Download/Upload: укажите 90% от скорости провайдера
```

## Обновление прошивки

### GL.iNet официальная прошивка
```bash
# Скачать с https://dl.gl-inet.com/firmware/ax1800/release/
# System → Upgrade → Upload .tar файл

# Или через SSH:
sysupgrade -n /tmp/openwrt-*.tar
```

### OpenWRT snapshot (latest)
```bash
# Скачать с https://downloads.openwrt.org/snapshots/targets/mediatek/mt7621/
# Только для опытных пользователей!
```

## Известные проблемы и решения

### Проблема 1: WiFi 6 клиенты не подключаются
**Решение:** Изменить `htmode` на более старый стандарт
```bash
option htmode 'VHT80'  # Вместо HE80 для 5GHz
option htmode 'HT40'   # Вместо HE40 для 2.4GHz
```

### Проблема 2: WAN порт не поднимается
**Решение:** Проверить DSA интерфейс
```bash
ip link set wan up
ip link show wan
```

### Проблема 3: После обновления слетели настройки
**Решение:** Всегда делать backup перед обновлением
```bash
# Backup
sysupgrade -b /tmp/backup.tar.gz

# Restore после обновления
sysupgrade -r /tmp/backup.tar.gz
```

### Проблема 4: Какой интерфейс использовать - GL.iNet UI или LuCI?
**Решение:** Используйте оба! Они дополняют друг друга.

**Стратегия использования:**
```bash
# Для обычных задач - GL.iNet UI (удобнее)
http://192.168.20.1
  - Изменение WiFi пароля
  - Включение VPN
  - Просмотр статистики
  - Быстрые настройки

# Для расширенных настроек - OpenWRT LuCI
http://192.168.20.1:81
  - Редактирование /etc/config/network
  - Детальная настройка firewall
  - Установка пакетов (opkg)
  - Применение наших конфигураций
```

**Важно:** Изменения через LuCI могут не отображаться в GL.iNet UI (и наоборот).
Используйте один интерфейс для конкретной настройки.

## Полезные команды для GL-AX1800

```bash
# Информация о системе
cat /proc/cpuinfo
cat /proc/meminfo
ubus call system board

# Температура (если доступна)
cat /sys/class/thermal/thermal_zone0/temp

# Версия прошивки
cat /etc/glversion
cat /etc/openwrt_release

# Статистика портов
ethtool wan
ethtool lan1

# Перезагрузка отдельных служб
/etc/init.d/network restart
/etc/init.d/firewall restart
/etc/init.d/dnsmasq restart
wifi reload
```

## Рекомендуемые пакеты

```bash
opkg update
opkg install \
  htop \
  iperf3 \
  tcpdump \
  ethtool \
  mtr \
  nano \
  curl \
  wget-ssl
```

## Ссылки

- [GL.iNet официальный сайт](https://www.gl-inet.com/products/gl-ax1800/)
- [GL.iNet форум](https://forum.gl-inet.com/)
- [GL.iNet документация](https://docs.gl-inet.com/router/en/4/)
- [OpenWRT wiki - GL-AX1800](https://openwrt.org/toh/gl.inet/gl-ax1800)
- [Firmware downloads](https://dl.gl-inet.com/firmware/ax1800/)

---

**Важно:** GL-AX1800 - отличный выбор для portable VPN роутера благодаря WiFi 6, хорошей производительности и компактному размеру!
