# Russia VPN из дома (через OPNsense)

## Обзор

Это руководство показывает как использовать **Russia VPN находясь дома**, когда OpenWRT роутер стоит за OPNsense firewall.

### Зачем нужно?

**Сценарии использования:**
- Тестирование Russia VPN перед поездкой
- Доступ к российским сервисам (банки, стриминг) находясь дома
- Обход geo-блокировок некоторых сервисов
- Отладка конфигурации Russia VPN

### Архитектура

**Travel Mode (в поездке):**
```
OpenWRT → Hotel WiFi → Internet → Russia VPN
(прямое подключение)
```

**Home Mode (дома):**
```
OpenWRT → OPNsense → ISP → Internet → Russia VPN
(через домашний firewall)
```

**Полная схема дома:**
```
Internet
  ↓
ISP Router
  ↓
Proxmox (WAN bridge)
  ↓
OPNsense VM ← Firewall правила для Russia VPN
  ↓
Proxmox (LAN bridge)
  ↓
OpenWRT (192.168.10.2) ← Russia VPN клиент
  ↓
Домашние устройства (192.168.20.0/24)
```

---

## Предварительные требования

✅ **Уже должно быть настроено:**
1. Russia VPS с AmneziaWG (см. `RUSSIA-VPS-SETUP.md`)
2. OpenWRT в Home Mode (см. `README.md`)
3. OPNsense firewall работает

✅ **Проверка:**
```bash
# На OpenWRT проверить режим
ssh root@192.168.20.1
cat /etc/openwrt-mode
# Должно показать: home

# Проверить доступность OPNsense
ping 192.168.10.1

# Проверить интернет
ping 8.8.8.8
```

---

## Часть 1: Настройка OPNsense Firewall

### Шаг 1.1: Войти в OPNsense Web UI

```
URL: http://192.168.10.1
Логин: root
Пароль: ваш пароль
```

### Шаг 1.2: Создать Alias для Russia VPS

**Firewall → Aliases**

Нажать: **+ Add**

```
Enabled: ✓
Name: Russia_VPS_Servers
Type: Host(s)
Content: 5.188.123.45  (ваш Russia VPS IP)
Description: Russia VPS AmneziaWG Server
```

Нажать: **Save** → **Apply**

### Шаг 1.3: Добавить Firewall правило

**Firewall → Rules → LAN**

Нажать: **+ Add** (вверху справа)

```
Action: Pass
Interface: LAN
Direction: in
TCP/IP Version: IPv4
Protocol: UDP

Source:
  Source: Single host or Network
  Address: 192.168.10.2/32  (OpenWRT IP)

Destination:
  Destination: Russia_VPS_Servers  (из выпадающего списка)
  Destination port range: 51822 to 51822

Description: Allow Russia VPN from OpenWRT
Category: VPN
```

Нажать: **Save** → **Apply Changes**

### Шаг 1.4: Проверка правила

**Firewall → Rules → LAN**

Должно появиться правило:
```
✓ | Pass | LAN | UDP | * | 192.168.10.2 | * | Russia_VPS_Servers | 51822
```

---

## Часть 2: Настройка OpenWRT

### Шаг 2.1: Подключение к роутеру

```bash
ssh root@192.168.20.1
```

### Шаг 2.2: Проверка AmneziaWG

```bash
# Должен быть установлен (из предыдущих настроек)
which awg
awg --version

# Проверить директорию Russia VPN
ls -la /etc/amnezia/amneziawg-russia/

# Если директория существует - конфиг уже создан в Travel Mode
# Можно использовать тот же конфиг!
```

### Шаг 2.3: Проверка/Создание конфигурации

```bash
# Проверить существующий конфиг
cat /etc/amnezia/amneziawg-russia/awg1.conf

# Если конфига нет, скопировать с компьютера
# scp openwrt-home-russia-vpn.conf root@192.168.20.1:/etc/amnezia/amneziawg-russia/awg1.conf

# Проверить права
chmod 600 /etc/amnezia/amneziawg-russia/awg1.conf
```

**Важно:** Конфиг для Home и Travel mode ОДИНАКОВЫЙ! Разница только в маршрутизации:
- Travel: OpenWRT WAN → прямо в Internet
- Home: OpenWRT WAN (192.168.10.2) → OPNsense (192.168.10.1) → Internet

### Шаг 2.4: Тестирование подключения

```bash
# Запустить Russia VPN
awg-quick up awg1

# Проверить интерфейс
awg show awg1
ip addr show awg1
# Должно показать: inet 10.9.1.2/24

# Проверить handshake (подождать 5-10 секунд)
awg show awg1 latest-handshakes
# Должно показать: недавний handshake (несколько секунд назад)

# Ping Russia VPS сервера
ping -c 5 10.9.1.1

# Проверить внешний IP
curl ifconfig.me
# Должно показать: IP вашего Russia VPS

# Проверить страну
curl ipinfo.io/country
# Должно показать: RU

# Остановить
awg-quick down awg1
```

---

## Часть 3: Использование VPN Selector

### Установка (если ещё не установлен)

```bash
# Скопировать скрипт
scp openwrt-vpn-selector.sh root@192.168.20.1:/root/vpn-selector.sh

# Сделать исполняемым
chmod +x /root/vpn-selector.sh

# Создать alias
echo "alias vpn='/root/vpn-selector.sh'" >> /etc/profile
source /etc/profile
```

### Использование

```bash
# Подключиться к Russia VPS (через OPNsense)
vpn russia

# Проверить статус
vpn status
# Должно показать: Russia VPS активен, российский IP

# Проверить через curl
curl ifconfig.me

# Отключить
vpn off

# Или переключиться на Oracle (обход блокировок)
vpn oracle

# Или на Home (локальная сеть)
vpn home
```

---

## Проверка работы через OPNsense

### Мониторинг Firewall

**На OPNsense Web UI:**

**Firewall → Log Files → Live View**

Фильтры:
- Interface: LAN
- Protocol: UDP
- Port: 51822

Должны быть записи:
```
Pass | LAN | UDP | 192.168.10.2:xxxxx → RUSSIA_VPS_IP:51822
```

**Firewall → Diagnostics → States**

Поиск: `192.168.10.2` и `51822`

Должны быть UDP states:
```
UDP 192.168.10.2:random → RUSSIA_VPS_IP:51822 → OPNsense_WAN_IP:random
```

---

## Troubleshooting

### Проблема 1: Handshake не происходит

**Симптомы:**
```bash
awg show awg1 latest-handshakes
# Показывает: 0 или очень старый handshake
```

**Решение:**

1. Проверить firewall на OPNsense:
   ```
   Firewall → Log Files → Live View
   # Искать блокировки (Block) для порта 51822
   ```

2. Проверить правило:
   ```
   Firewall → Rules → LAN
   # Правило должно быть ВЫШЕ любых блокирующих правил
   ```

3. Проверить доступность Russia VPS с OPNsense:
   ```
   Diagnostics → Ping
   Host: RUSSIA_VPS_IP
   # Должен отвечать
   ```

4. Проверить что порт 51822 открыт на VPS:
   ```bash
   # На Russia VPS
   sudo ss -ulnp | grep 51822
   # Должно показать: awg слушает на 51822
   ```

### Проблема 2: Handshake есть, но нет интернета

**Симптомы:**
```bash
awg show awg1 latest-handshakes  # OK
ping 10.9.1.1  # OK
ping 8.8.8.8  # FAIL
curl ifconfig.me  # timeout
```

**Решение:**

1. Проверить DNS:
   ```bash
   nslookup google.com
   # Должен резолвиться
   ```

2. Проверить маршруты:
   ```bash
   ip route show | grep awg1
   # Должны быть маршруты через awg1
   ```

3. Проверить на Russia VPS:
   ```bash
   # SSH к VPS
   sudo sysctl net.ipv4.ip_forward
   # Должно быть: 1

   sudo iptables -t nat -L POSTROUTING -n -v
   # Должно быть MASQUERADE правило
   ```

### Проблема 3: Медленная скорость

**Причины:**
- Двойной NAT (ISP → OPNsense → Russia VPN)
- Загрузка OPNsense VM
- Ограничения Russia VPS хостинга

**Решение:**

1. Проверить нагрузку OPNsense:
   ```
   Dashboard → System Information
   # CPU и Memory usage
   ```

2. Уменьшить MTU на OpenWRT:
   ```bash
   ip link set awg1 mtu 1400
   ```

3. Уменьшить обфускацию (в конфиге):
   ```ini
   Jc = 3      # было 7
   Jmax = 800  # было 1200
   ```

4. Проверить скорость Russia VPS напрямую:
   ```bash
   # SSH к VPS
   curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 -
   ```

---

## Сравнение Home vs Travel Mode

| Параметр | Home Mode | Travel Mode |
|----------|-----------|-------------|
| **Подключение** | Через OPNsense firewall | Напрямую в Internet |
| **Маршрут** | OpenWRT → OPNsense → ISP → VPS | OpenWRT → WiFi → VPS |
| **Firewall** | Нужны правила на OPNsense | Не нужны |
| **NAT** | Двойной (OPNsense + ISP) | Одинарный (WiFi) |
| **Скорость** | Чуть медленнее | Быстрее |
| **Безопасность** | Выше (OPNsense контроль) | Базовая (только AmneziaWG) |
| **Конфигурация** | Та же | Та же |

**Важно:** Конфигурация AmneziaWG (`awg1.conf`) ОДИНАКОВАЯ для обоих режимов!

---

## Автоматическое переключение (опционально)

### Определение режима

```bash
# Скрипт автоопределения режима
cat > /root/detect-mode.sh << 'EOF'
#!/bin/sh

# Проверить доступность OPNsense
if ping -c 1 -W 2 192.168.10.1 > /dev/null 2>&1; then
    echo "home"
else
    echo "travel"
fi
EOF

chmod +x /root/detect-mode.sh
```

### Автонастройка при загрузке

```bash
# Добавить в /etc/rc.local
cat >> /etc/rc.local << 'EOF'

# Автоопределение режима и настройка
MODE=$(/root/detect-mode.sh)
echo $MODE > /etc/openwrt-mode

if [ "$MODE" = "home" ]; then
    logger "OpenWRT in HOME mode (behind OPNsense)"
else
    logger "OpenWRT in TRAVEL mode (direct Internet)"
fi

exit 0
EOF
```

---

## Мониторинг

### На OpenWRT

```bash
# Статус Russia VPN
vpn status

# Детальная информация
awg show awg1

# Логи
logread | grep -i amnezia
logread | grep -i awg

# Маршруты
ip route show
ip route get RUSSIA_VPS_IP
# Должно показать: via 192.168.10.1 (OPNsense)
```

### На OPNsense

```bash
# SSH к OPNsense
ssh root@192.168.10.1

# Firewall states
pfctl -ss | grep 51822

# Firewall logs
clog /var/log/filter.log | grep 51822

# Network connections
netstat -an | grep 51822
```

---

## Когда использовать Russia VPN дома?

### ✅ Используйте когда:
- Тестирование перед поездкой
- Нужен российский IP для доступа к сервисам (банки, госуслуги)
- Проверка geo-ограничений
- Отладка VPN конфигурации

### ❌ Не используйте когда:
- Нужен обход блокировок В России (используйте Oracle Cloud)
- Нужна максимальная скорость (локальный интернет быстрее)
- Не нужен российский IP (используйте прямое подключение)

---

## Быстрая справка

### Включить Russia VPN дома
```bash
vpn russia
# или
awg-quick up awg1
```

### Проверить
```bash
vpn status
curl ifconfig.me  # Должен показать Russia VPS IP
curl ipinfo.io/country  # Должно показать: RU
```

### Выключить
```bash
vpn off
# или
awg-quick down awg1
```

### Переключиться на Oracle (обход блокировок)
```bash
vpn oracle
```

### Вернуться к прямому подключению
```bash
vpn off
```

---

## Дополнительные ресурсы

- **Конфигурации:**
  - `openwrt-home-russia-vpn.conf` - клиент для home mode
  - `opnsense-russia-vpn-firewall.txt` - правила firewall
  - `russia-vps-amneziawg.conf` - сервер на VPS

- **Руководства:**
  - `RUSSIA-VPS-SETUP.md` - настройка Russia VPS сервера
  - `README.md` - общая архитектура сети
  - `QUICK-REFERENCE.md` - быстрые команды

- **Скрипты:**
  - `openwrt-vpn-selector.sh` - переключение между VPN

---

**Автор:** Configuration Generator
**Версия:** 2.4.1 (Home Russia VPN)
**Дата:** 2025-10-03
