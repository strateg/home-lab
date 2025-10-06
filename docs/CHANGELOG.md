# Changelog

## v2.4.1 - Home Mode Russia VPN (2025-10-04)

### Добавлено

✅ **Home Mode поддержка для Russia VPN** - Использование Russia VPN когда роутер находится дома за OPNsense firewall:

**Новые файлы:**
- ✅ `openwrt-home-russia-vpn.conf` (15K) - Клиентская конфигурация для Home Mode
  - Использование Russia VPN через OPNsense firewall
  - Та же AmneziaWG конфигурация как в Travel Mode
  - Маршрутизация через OPNsense (192.168.10.1)
  - Комментарии о разнице Home vs Travel режимов

- ✅ `opnsense-russia-vpn-firewall.txt` (20K) - Настройка OPNsense firewall для Russia VPN
  - Подробная инструкция для OPNsense Web UI
  - 3 варианта настройки (простой, безопасный, с alias)
  - Alias для Russia VPS IP и VPN портов
  - Проверка правил и мониторинг
  - NAT конфигурация (автоматическая)
  - CLI и API конфигурация (дополнительно)
  - Troubleshooting для firewall

- ✅ `HOME-RUSSIA-VPN-SETUP.md` (22K) - Полное руководство для Home Mode Russia VPN
  - Архитектура: OpenWRT → OPNsense → Russia VPS
  - Настройка OPNsense firewall (Web UI)
  - Использование Russia VPN дома
  - Интеграция с VPN Selector (работает в обоих режимах)
  - Мониторинг через OPNsense (firewall logs, states)
  - Troubleshooting (handshake, routing, скорость)
  - Сравнение Home vs Travel режимов
  - Когда использовать Russia VPN дома (тестирование, РФ сервисы, geo-блокировки)

### Обновлено

**Firewall конфигурации:**
- ✏️ `openwrt-home-firewall`
  - Добавлена Russia VPN зона (`russiavpn`)
  - Forwarding правило LAN → Russia VPN
  - Правило для исходящего UDP 51822
  - Комментарии о маршрутизации через OPNsense

**Документация:**
- ✏️ `README.md`
  - Обновлена секция "5. Russia VPS" (указаны конфигурации для Home и Travel)
  - Добавлена информация "Использование дома (через OPNsense)"
  - Новый FAQ "Можно ли использовать Russia VPN находясь дома?"
  - Ссылки на `HOME-RUSSIA-VPN-SETUP.md` и `opnsense-russia-vpn-firewall.txt`

### Архитектура Home Mode с Russia VPN

```
Internet → ISP Router → Proxmox WAN bridge
                           ↓
                      OPNsense VM
                      (Firewall: Pass UDP 51822)
                           ↓
                    Proxmox LAN bridge
                           ↓
                      OpenWRT Router (192.168.10.2)
                      (Russia VPN: awg1)
                           ↓
                  Трафик → OPNsense → Internet → Russia VPS
```

### Сценарии использования дома

- ✅ **Тестирование** перед поездкой (проверка Russia VPN)
- ✅ **Доступ к РФ сервисам** находясь дома (банки, стриминг)
- ✅ **Обход geo-блокировок** (сервисы только для РФ)
- ✅ **Отладка** конфигурации Russia VPN

### VPN Selector работает в Home Mode

```bash
# В режиме Home (за OPNsense):
vpn russia  # → через OPNsense → Russia VPS
vpn oracle  # → через OPNsense → Oracle Cloud
vpn home    # → к OPNsense WireGuard (не нужен, уже дома)
vpn status  # → показывает активный VPN
```

---

## v2.4 - Russia VPS для российского IP (2025-10-03)

### Добавлено

✅ **Russia VPS конфигурации** - Получение российского IP адреса для доступа к РФ сервисам из-за границы:

**Новые файлы:**
- ✅ `russia-vps-amneziawg.conf` (6.8K) - Серверная конфигурация AmneziaWG для Russia VPS
  - Подсеть 10.9.1.0/24 (отличается от Oracle 10.8.2.0/24)
  - Порт 51822 (отличается от Oracle 51821)
  - Уникальные обфускация параметры (Jc=7, H1-H4 инверсия от Oracle)
  - Инструкция по установке на Timeweb/REG.RU/Selectel
  - Firewall и systemd настройки

- ✅ `openwrt-travel-russia-client.conf` (9.7K) - Клиентская конфигурация
  - Настройка для GL-AXT1800 → Russia VPS
  - Получение российского IP адреса
  - DNS конфигурация (8.8.8.8 или Яндекс DNS)
  - Routing через VPN
  - Интеграция с /etc/config/network

- ✅ `openwrt-vpn-selector.sh` (12K) - Скрипт переключения между 3 VPN
  - **Oracle Cloud** (`vpn oracle`) - обход DPI блокировок РФ
  - **Russia VPS** (`vpn russia`) - российский IP адрес
  - **Home** (`vpn home`) - домашняя сеть Proxmox
  - Команды: start/stop/status/help
  - Цветной вывод и детальная диагностика
  - Автоматическая проверка handshake и external IP
  - Alias для удобства: `vpn russia` вместо `/root/vpn-selector.sh russia`

- ✅ **RUSSIA-VPS-SETUP.md** (17K) - Полное руководство по настройке российского VPS
  - Выбор хостинга (Timeweb/REG.RU/Selectel)
  - Пошаговая установка VPS (Ubuntu 22.04)
  - Настройка безопасности (SSH порт, Fail2ban, ufw)
  - Установка и настройка AmneziaWG
  - Настройка клиента GL-AXT1800
  - Production запуск с systemd
  - Мониторинг и обслуживание
  - Troubleshooting
  - FAQ

### Обновлено

**Документация:**
- ✏️ `README.md`
  - Новая секция "5. Russia VPS (Российский IP адрес)"
  - Обновлена секция "6. VPN Протоколы" (разделение Oracle vs Russia)
  - Обновлена таблица "VPN Серверы" (3 сервера)
  - Новые FAQ: "Зачем нужен российский VPS?", "Сколько стоит?", "Как переключаться?"
  - Добавлена информация о VPN Selector скрипте

- ✏️ `QUICK-REFERENCE.md`
  - Новая секция "Russia VPS (Российский IP)"
  - Команды для управления AmneziaWG на Russia VPS
  - Мониторинг Russia VPS
  - Новая секция "VPN Selector (переключение между 3 VPN)"
  - Базовое использование VPN selector
  - Сценарии использования (Сбербанк, блокировки, Proxmox)
  - Проверка активного VPN (3 метода)
  - Firewall правила для порта 51822

### Архитектура с 3 VPN

```
GL-AXT1800 Travel Router
  │
  ├─ awg0 → Oracle Cloud (10.8.2.2, порт 51821)
  │         └─ Обход DPI блокировок РФ
  │         └─ Когда: В России, нужен обход
  │
  ├─ awg1 → Russia VPS (10.9.1.2, порт 51822)
  │         └─ Российский IP адрес
  │         └─ Когда: За границей, нужен РФ IP
  │
  └─ wg0 → Home (10.0.200.10, порт 51820)
            └─ Домашняя сеть Proxmox
            └─ Когда: Нужен доступ к дому
```

### Переключение VPN одной командой

```bash
vpn russia  # Российский IP (Сбербанк, Госуслуги, стриминг)
vpn oracle  # Обход блокировок (в России)
vpn home    # Доступ к домашним сервисам
vpn status  # Проверить текущий VPN
vpn off     # Отключить все VPN
```

### Сервисы с российским IP

**После `vpn russia` будет доступно:**
- 🏦 Банки РФ: Сбербанк, Тинькофф, ВТБ, Альфа-банк
- 🏛️ Госуслуги (gosuslugi.ru)
- 📺 Стриминг: Okko, Kinopoisk, START, Match TV
- 🛍️ Маркетплейсы: Wildberries, Ozon
- 🎵 Яндекс.Музыка, Яндекс.Диск, Яндекс сервисы
- 📱 ВКонтакте, Одноклассники
- 📰 Российские новостные сайты

### Рекомендованные хостинги для Russia VPS

| Хостинг | Цена/мес | RAM | Оплата | Рейтинг |
|---------|----------|-----|--------|---------|
| **Timeweb VPS-1** | 200₽ (~$2) | 2GB | Карта РФ, Крипта | 🏆 #1 |
| **REG.RU VPS Linux-1** | 150₽ (~$1.5) | 2GB | Карта РФ, Крипта | ⭐ #2 |
| **Selectel Cloud** | 500₽ (~$5) | 2GB | Карта РФ | ⭐ #3 |

**Выбор:** Timeweb VPS-1 (оптимальное соотношение цена/качество)

### Установка (краткая)

**1. Заказать VPS:**
- Timeweb → VPS-1 → Ubuntu 22.04 → Москва/СПб

**2. Настроить сервер:**
```bash
ssh root@VPS_IP
wget https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/latest/download/amneziawg-install.sh
./amneziawg-install.sh
cp russia-vps-amneziawg.conf /etc/amnezia/amneziawg-russia/awg1.conf
systemctl enable awg-quick@awg1
systemctl start awg-quick@awg1
```

**3. Настроить клиент:**
```bash
# На GL-AXT1800
mkdir -p /etc/amnezia/amneziawg-russia
awg genkey | tee client_privatekey | awg pubkey > client_publickey
# Добавить public key на сервер
cp openwrt-travel-russia-client.conf /etc/amnezia/amneziawg-russia/awg1.conf
```

**4. Установить VPN Selector:**
```bash
cp openwrt-vpn-selector.sh /root/vpn-selector.sh
chmod +x /root/vpn-selector.sh
echo "alias vpn='/root/vpn-selector.sh'" >> /etc/profile
```

**5. Использовать:**
```bash
vpn russia   # Подключиться к Russia VPS
vpn status   # Проверить IP
curl ifconfig.me  # Должен показать российский IP
```

### Безопасность

**Обязательные меры на Russia VPS:**
- ✅ Смена SSH порта (22 → 2222)
- ✅ Установка Fail2ban
- ✅ Настройка ufw firewall (только 51822 UDP + SSH)
- ✅ Автообновления безопасности
- ✅ Мониторинг через cron

### Когда использовать какой VPN?

| Где вы? | Что нужно? | Какой VPN? | Команда |
|---------|------------|------------|---------|
| **В России** | Обход блокировок | Oracle Cloud | `vpn oracle` |
| **За границей** | Сбербанк, Госуслуги | Russia VPS | `vpn russia` |
| **В поездке** | Домашний Proxmox | Home | `vpn home` |
| **Проверка** | Какой VPN активен? | - | `vpn status` |

### Стоимость

- **Oracle Cloud:** Free Forever (Always Free tier)
- **Russia VPS:** 200₽/мес (~$2)
- **Домашний Proxmox:** Стоимость электричества
- **Итого:** ~$2/мес для всех 3 VPN

### Совместимость

- ✅ GL.iNet GL-AXT1800 (OpenWRT 21.02+)
- ✅ Oracle Cloud (Ubuntu 22.04 LTS)
- ✅ Timeweb / REG.RU / Selectel VPS (Ubuntu 22.04)
- ✅ Домашний Proxmox + OPNsense
- ✅ Android/iOS/Desktop (через Amnezia VPN клиенты)

---

## v2.3 - AmneziaWG для обхода DPI блокировок (2025-10-03)

### Добавлено

✅ **AmneziaWG конфигурации** - VPN с обфускацией для обхода блокировок в России:

**Новые файлы:**
- ✅ `oracle-cloud-amneziawg.conf` (7.2K) - Серверная конфигурация AmneziaWG
  - Обфускация параметры (Jc, Jmin, Jmax, S1, S2, H1-H4)
  - Подсеть 10.8.2.0/24 (параллельно с WireGuard 10.8.1.0/24)
  - Порт 51821 (отличается от WireGuard 51820)
  - Полная инструкция по установке на Oracle Cloud
  - Настройка firewall и systemd

- ✅ `openwrt-travel-amneziawg-client.conf` (5.8K) - Клиентская конфигурация
  - Настройка для GL-AXT1800
  - Те же обфускация параметры что и на сервере
  - Инструкция по установке AmneziaWG на OpenWRT
  - Интеграция с /etc/config/network и firewall
  - Автозапуск через init script

- ✅ `openwrt-amneziawg-failover.sh` (6.5K) - Скрипт автоматического переключения
  - Приоритет: AmneziaWG (primary) → WireGuard (fallback)
  - Проверка handshake и доступности
  - Автоматический retry при сбоях
  - Логирование в /var/log/vpn-failover.log
  - Команды: start/stop/restart/status/check

- ✅ **AMNEZIAWG-SETUP.md** (18K) - Полное руководство по настройке
  - Пошаговая установка сервера (Oracle Cloud)
  - Пошаговая установка клиента (GL-AXT1800)
  - Генерация ключей и обфускация параметров
  - Диагностика и troubleshooting
  - Сравнение производительности WireGuard vs AmneziaWG
  - FAQ и полезные ссылки

### Обновлено

**Документация:**
- ✏️ `README.md` - Добавлена секция "VPN Протоколы"
  - Описание WireGuard и AmneziaWG
  - Обновлена секция "В поездке" с приоритетом AmneziaWG
  - Обновлена секция "Oracle Cloud" с двумя VPN серверами
  - Новые FAQ: "Будет ли VPN работать в России?"
  - Обновлена IP адресация (10.8.1.0/24 и 10.8.2.0/24)

- ✏️ `QUICK-REFERENCE.md` - Команды для AmneziaWG
  - Новая секция "AmneziaWG - VPN с обфускацией"
  - Генерация ключей (`awg genkey`, `awg genpsk`)
  - Управление туннелями (`awg-quick up/down`, `awg show`)
  - Автоматическое переключение через failover скрипт
  - Проверка активного VPN (awg0 vs wg0)
  - Speedtest сравнение протоколов
  - Команды для Oracle Cloud (systemd, journalctl, tcpdump)
  - Firewall правила для порта 51821

### Ключевые особенности AmneziaWG

#### 1. Обфускация трафика
```
Обычный WireGuard:
Router → WG packets → ISP DPI → "Это VPN!" → БЛОКИРОВКА

AmneziaWG:
Router → AWG packets → ISP DPI → "Обычный UDP" → ПРОПУСК
```

#### 2. Параметры обфускации
- **Jc = 5** - количество мусорных пакетов
- **Jmin/Jmax** - размеры мусорных пакетов (50-1000 bytes)
- **S1/S2** - размер мусора в init/response пакетах
- **H1-H4** - магические заголовки (маскируют WireGuard signature)

#### 3. Dual VPN архитектура
```
GL-AXT1800 Travel Router
  ├─ AmneziaWG (awg0) → 10.8.2.2 → Priority 1
  │  └─ Обход DPI, работает в РФ
  │
  └─ WireGuard (wg0) → 10.8.1.2 → Priority 2
     └─ Fallback, если AWG заблокирован
```

#### 4. Автоматическое переключение
- Failover скрипт проверяет соединение каждые 5 минут
- Если AmneziaWG не работает → переключается на WireGuard
- Если оба не работают → пытается переподключиться
- Логи в /var/log/vpn-failover.log

### Производительность

| Протокол | Скорость | Latency | DPI Bypass |
|----------|----------|---------|------------|
| WireGuard | 90-95 Mbps | 15-20 ms | ❌ Блокируется |
| AmneziaWG | 85-90 Mbps | 20-25 ms | ✅ Работает |

**Вывод:** AmneziaWG ~5-10% медленнее из-за обфускации, но работает там, где WireGuard заблокирован.

### Совместимость

- ✅ Работает параллельно с WireGuard (разные порты и подсети)
- ✅ GL.iNet GL-AXT1800 (OpenWRT 21.02+)
- ✅ Oracle Cloud (Ubuntu 22.04 LTS)
- ✅ Россия, Китай, Иран, страны с DPI

### Установка (краткая)

**Сервер:**
```bash
wget https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/latest/download/amneziawg-install.sh
sudo ./amneziawg-install.sh
sudo cp oracle-cloud-amneziawg.conf /etc/amnezia/amneziawg/awg0.conf
sudo systemctl enable awg-quick@awg0
```

**Клиент:**
```bash
opkg install kmod-amneziawg_*.ipk amneziawg-tools_*.ipk
cp openwrt-travel-amneziawg-client.conf /etc/amnezia/amneziawg/awg0.conf
awg-quick up awg0
```

**Failover:**
```bash
cp openwrt-amneziawg-failover.sh /root/
chmod +x /root/amneziawg-failover.sh
/root/amneziawg-failover.sh start
```

### Зачем использовать AmneziaWG?

**Для пользователей в России:**
- WireGuard активно блокируется DPI с 2024 года
- AmneziaWG маскирует VPN трафик → обходит блокировки
- Специально разработан для обхода цензуры

**Преимущества:**
- ✅ Та же криптография что и WireGuard (безопасно)
- ✅ Почти такая же скорость (~5-10% overhead)
- ✅ Open source (https://github.com/amnezia-vpn)
- ✅ Активно развивается

---

## v2.2 - Dual UI стратегия для GL.iNet (2025-10-03)

### Изменено

✏️ **Стратегия использования GL.iNet UI:**
- **БЫЛО:** Рекомендация удалить GL.iNet UI, использовать только LuCI
- **СТАЛО:** Использовать оба интерфейса параллельно!
  - GL.iNet UI (http://192.168.20.1) - для повседневных задач
  - OpenWRT LuCI (http://192.168.20.1:81) - для расширенных настроек

**Обновлённые файлы:**
- ✏️ `GL-AXT1800-NOTES.md` - Раздел "GL.iNet специфичные пакеты"
  - Добавлены рекомендации по использованию обоих UI
  - Список задач для GL.iNet UI vs LuCI
  - Удалены инструкции по удалению GL.iNet UI

- ✏️ `QUICK-REFERENCE.md` - Секция "GL.iNet GL-AXT1800 специфичные команды"
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

## v2.0 - Обновление для GL.iNet GL-AXT1800 (2025-10-03)

### Добавлено

✅ **GL-AXT1800-NOTES.md** (11K) - Полное руководство по GL.iNet GL-AXT1800:
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
  - DSA порты для GL-AXT1800
  - WAN порт: `wan` (синий порт)
  - LAN порты: `lan1-lan4` (желтые порты)

- ✅ `openwrt-travel-wireless` (2.7K)
  - WiFi 6 настройки для портативного режима
  - Оптимизация для публичных сетей

#### Документация

- ✅ `README.md` (17K)
  - Добавлена секция о GL.iNet GL-AXT1800
  - Обновлена секция "Рекомендуемое оборудование"
  - Добавлены ссылки на GL-AXT1800-NOTES.md

- ✅ `FILES-INDEX.md` (9.1K)
  - Добавлен GL-AXT1800-NOTES.md в индекс
  - Добавлена информация о DSA портах
  - Обновлены описания WiFi 6 конфигураций

- ✅ `QUICK-REFERENCE.md` (17K)
  - Новая секция "GL.iNet GL-AXT1800 специфичные команды"
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

### Физические порты GL-AXT1800

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

✅ Все конфигурации оптимизированы для GL.iNet GL-AXT1800 (Flint)
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

После применения конфигурации на GL-AXT1800:

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
  - GL-AXT1800-NOTES.md (11K) ⭐ NEW
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

1. Прочитайте `GL-AXT1800-NOTES.md` для понимания устройства
2. Примените конфигурации согласно `README.md`
3. Используйте `QUICK-REFERENCE.md` для диагностики
4. Сделайте backup перед изменениями!

---

**Автор:** Configuration Generator
**Версия:** 2.0 (GL-AXT1800 optimized)
**Дата:** 2025-10-03
