# GL.iNet UI vs OpenWRT LuCI - Руководство по использованию

## Обзор

GL.iNet GL-AX1800 (Flint) имеет **два веб-интерфейса**, работающих параллельно:

1. **GL.iNet UI** - удобный графический интерфейс (порт 80)
2. **OpenWRT LuCI** - стандартный OpenWRT интерфейс (порт 81)

**Оба используют одинаковый логин и пароль!**

## Доступ

```
GL.iNet UI:    http://192.168.20.1       (дома)
               http://192.168.100.1      (в поездке)

OpenWRT LuCI:  http://192.168.20.1:81    (дома)
               http://192.168.100.1:81   (в поездке)

Логин: root
Пароль: ваш пароль
```

## Когда использовать GL.iNet UI

### ✅ Повседневные задачи

**1. WiFi управление**
- Изменить SSID и пароль
- Включить/отключить гостевую сеть
- Настроить расписание WiFi
- Просмотр подключенных клиентов

```
GL.iNet UI → Wireless → Settings
```

**2. VPN клиент**
- Подключение к VPN серверу одним кликом
- Поддержка WireGuard, OpenVPN
- Авто-reconnect при обрыве

```
GL.iNet UI → VPN → VPN Dashboard
```

**3. Мониторинг трафика**
- Графики использования в реальном времени
- Топ приложений по трафику
- История использования

```
GL.iNet UI → More Settings → Traffic Statistics
```

**4. Firewall (базовый)**
- Port forwarding одним кликом
- DMZ настройка
- Блокировка по MAC адресу

```
GL.iNet UI → Firewall
```

**5. AdGuard Home**
- Включение/отключение блокировки рекламы
- Статистика заблокированных запросов
- Whitelist/Blacklist управление

```
GL.iNet UI → Applications → AdGuard Home
```

**6. Repeater режим**
- Подключение к WiFi сети одним кликом
- Автоматическая настройка моста

```
GL.iNet UI → Internet → Repeater
```

**7. Обновление прошивки**
- One-click обновление
- Автоматическая проверка новых версий

```
GL.iNet UI → System → Upgrade
```

## Когда использовать OpenWRT LuCI

### ✅ Расширенные настройки

**1. Сетевая конфигурация**
- Редактирование /etc/config/network
- Создание VLAN
- Настройка статических маршрутов
- Bridge и bond интерфейсы

```
LuCI → Network → Interfaces
```

**2. Установка пакетов**
- Поиск и установка через opkg
- Удаление ненужных пакетов
- Обновление списка пакетов

```
LuCI → System → Software
opkg update
opkg install wireguard-tools
```

**3. Firewall (детальный)**
- Создание сложных правил
- Зоны и forwarding
- Custom iptables правила
- Traffic shaping (SQM)

```
LuCI → Network → Firewall
```

**4. Применение наших конфигураций**
- Копирование содержимого из файлов конфигурации
- Редактирование /etc/config/*
- Проверка синтаксиса

```
LuCI → System → Startup → Local Startup
```

**5. SSH и доступ**
- Управление SSH ключами
- Настройка dropbear
- HTTPS сертификаты

```
LuCI → System → Administration
```

**6. Cron задачи**
- Автоматизация задач
- Scheduled backup
- Мониторинг скрипты

```
LuCI → System → Scheduled Tasks
```

**7. Логи и диагностика**
- Системные логи (dmesg, logread)
- Kernel logs
- Диагностика сети

```
LuCI → Status → System Log
LuCI → Status → Kernel Log
```

**8. WiFi расширенные настройки**
- Точная настройка каналов
- TX power
- WiFi 6 параметры (HE80, beamforming)
- 802.11r (fast roaming)

```
LuCI → Network → Wireless
```

## Сравнительная таблица

| Задача | GL.iNet UI | OpenWRT LuCI | Рекомендация |
|--------|-----------|--------------|--------------|
| Изменить WiFi пароль | ✅ Просто | ✅ Возможно | GL.iNet UI |
| VPN клиент (подключение к серверу) | ✅ One-click | ⚠️ Сложно | GL.iNet UI |
| VPN сервер (WireGuard) | ⚠️ Базовый | ✅ Полный контроль | LuCI |
| Просмотр трафика | ✅ Графики | ⚠️ Только текст | GL.iNet UI |
| Port forwarding | ✅ Простой | ✅ Детальный | GL.iNet UI (простой) |
| Firewall правила (сложные) | ❌ Ограничен | ✅ Полный | LuCI |
| AdGuard включить/выключить | ✅ One-click | ⚠️ Через SSH | GL.iNet UI |
| Установка пакетов | ❌ Нет | ✅ opkg | LuCI |
| Редактирование /etc/config/* | ❌ Нет | ✅ Есть | LuCI |
| VLAN настройка | ❌ Нет | ✅ Есть | LuCI |
| Обновление прошивки | ✅ Автоматическое | ⚠️ Ручное | GL.iNet UI |
| Backup настроек | ✅ Простой | ✅ Детальный | GL.iNet UI |
| Repeater режим | ✅ One-click | ⚠️ Сложно | GL.iNet UI |
| Логи системы | ⚠️ Базовые | ✅ Полные | LuCI |
| SSH ключи | ❌ Нет | ✅ Есть | LuCI |
| Cron задачи | ❌ Нет | ✅ Есть | LuCI |

## Практические примеры

### Пример 1: Изменить WiFi пароль

**Через GL.iNet UI (проще):**
1. Открыть http://192.168.20.1
2. Wireless → Modify
3. Изменить Password
4. Apply

**Через LuCI (дольше):**
1. Открыть http://192.168.20.1:81
2. Network → Wireless
3. Edit → Wireless Security
4. Изменить Key
5. Save & Apply

**Вердикт:** GL.iNet UI быстрее ✅

### Пример 2: Установить AdGuard Home

**Через GL.iNet UI:**
1. Applications → AdGuard Home
2. Install (one-click)

**Через LuCI:**
1. System → Software → Update lists
2. Найти adguardhome
3. Install
4. Настроить /etc/config/adguardhome

**Вердикт:** GL.iNet UI намного проще ✅

### Пример 3: Применить наши конфигурации

**Через GL.iNet UI:**
- ❌ Невозможно (нет доступа к /etc/config/*)

**Через LuCI:**
1. System → Administration → SSH
2. SSH в роутер
3. Скопировать файлы конфигурации
4. Или через LuCI → Edit /etc/config/network

**Вердикт:** Только LuCI ✅

### Пример 4: Настроить VPN клиент для подключения к дому

**Через GL.iNet UI:**
1. VPN → VPN Dashboard → Set Up WireGuard Client
2. Вставить конфиг или QR код
3. Connect

**Через LuCI:**
1. Установить wireguard через opkg
2. Создать /etc/config/network interface
3. Настроить firewall
4. Добавить в startup

**Вердикт:** GL.iNet UI в 10 раз быстрее ✅

## Важные заметки

### ⚠️ Изменения могут не синхронизироваться

Изменения сделанные через **GL.iNet UI** могут **не отображаться** в **LuCI** (и наоборот).

**Пример:**
```bash
# Если вы изменили /etc/config/network через LuCI
# GL.iNet UI может показывать старые настройки

# Решение: используйте один интерфейс для конкретной настройки
```

### ⚠️ GL.iNet UI использует обёртки

GL.iNet UI не редактирует /etc/config/* напрямую. Он использует свои скрипты (`gl-*`), которые затем генерируют конфигурацию.

**Поэтому:**
- Простые задачи → GL.iNet UI (он всё настроит правильно)
- Кастомные конфигурации → LuCI или SSH (полный контроль)

### ✅ Backup работает с обоими

Backup созданный через:
- GL.iNet UI → сохраняет настройки обоих UI
- LuCI (sysupgrade) → тоже сохраняет всё

## Рекомендуемый workflow

### Для обычных пользователей

```
90% времени: GL.iNet UI
10% времени: LuCI (только для специфических задач)
```

### Для продвинутых пользователей (вы)

```
60% времени: GL.iNet UI (WiFi, VPN клиент, мониторинг)
40% времени: LuCI (конфигурации, пакеты, firewall)
```

### Для нашей конфигурации

**Первичная настройка (LuCI):**
1. SSH в роутер
2. Скопировать файлы конфигурации:
   - openwrt-home-network → /etc/config/network
   - openwrt-home-wireless → /etc/config/wireless
   - openwrt-home-dhcp → /etc/config/dhcp
   - openwrt-home-firewall → /etc/config/firewall
3. Установить AdGuard через GL.iNet UI
4. Reboot

**Повседневное использование (GL.iNet UI):**
- Мониторинг трафика
- Изменение WiFi паролей
- AdGuard статистика
- VPN клиент для подключения к дому

**Обслуживание (LuCI):**
- Обновление пакетов (opkg upgrade)
- Проверка логов
- Тонкая настройка firewall

## Быстрый доступ

### Избранное для GL.iNet UI

```
Главная                     http://192.168.20.1
Wireless настройки          http://192.168.20.1/#/wireless
VPN Dashboard              http://192.168.20.1/#/vpn
Traffic Statistics         http://192.168.20.1/#/traffic
AdGuard Home              http://192.168.20.1/#/adguard
Clients (подключенные)     http://192.168.20.1/#/clients
System → Upgrade          http://192.168.20.1/#/upgrade
```

### Избранное для LuCI

```
Главная                     http://192.168.20.1:81
Network → Interfaces       http://192.168.20.1:81/cgi-bin/luci/admin/network/network
Network → Wireless         http://192.168.20.1:81/cgi-bin/luci/admin/network/wireless
Network → Firewall         http://192.168.20.1:81/cgi-bin/luci/admin/network/firewall
System → Software          http://192.168.20.1:81/cgi-bin/luci/admin/system/opkg
System → Startup          http://192.168.20.1:81/cgi-bin/luci/admin/system/startup
Status → System Log        http://192.168.20.1:81/cgi-bin/luci/admin/status/logs
```

## Заключение

**Используйте оба интерфейса!**

- 🎯 **GL.iNet UI** - для скорости и удобства
- 🔧 **OpenWRT LuCI** - для контроля и гибкости

Не нужно выбирать между ними - используйте преимущества каждого!

---

**См. также:**
- `GL-AX1800-NOTES.md` - Детальное руководство по GL-AX1800
- `QUICK-REFERENCE.md` - Быстрые команды
- `README.md` - Общая документация
