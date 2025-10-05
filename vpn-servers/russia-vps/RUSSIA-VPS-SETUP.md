# Russia VPS Setup - Получение российского IP адреса

## Обзор

Это руководство покажет как настроить **AmneziaWG VPN на российском VPS** для получения российского IP адреса, необходимого для доступа к российским сервисам из-за границы.

### Зачем нужен российский IP?

**Сервисы требующие российский IP:**
- 🏦 Банки РФ (Сбербанк, Тинькофф, ВТБ, и т.д.)
- 🏛️ Госуслуги (gosuslugi.ru)
- 📺 Стриминг (Okko, Kinopoisk, START, Match TV)
- 🛍️ Маркетплейсы (Wildberries, Ozon)
- 📱 Социальные сети (ВКонтакте, если заблокированы в вашей стране)
- 🎵 Яндекс.Музыка, Яндекс.Диск
- 📰 Российские новостные сайты

### Архитектура

```
Вы (за границей) → GL-AX1800 → AmneziaWG → VPS Россия → Интернет
                                              (РФ IP)

Сервисы видят: Российский IP ✅
```

### Три VPN стратегия

После настройки у вас будет **3 VPN сервера**:

| VPN | IP | Назначение | Когда использовать |
|-----|----|-----------|--------------------|
| **Russia VPS** | 🇷🇺 РФ | Российский IP | За границей, нужен доступ к РФ сервисам |
| **Oracle Cloud** | 🌍 не-РФ | Обход DPI | В России, нужен обход блокировок |
| **Home** | 🏠 Дом | Домашняя сеть | Доступ к Proxmox/LXC |

**Переключение одной командой:**
```bash
vpn russia  # Российский IP
vpn oracle  # Обход блокировок
vpn home    # Домашняя сеть
```

---

## Выбор российского хостинга

### Сравнение хостингов

| Хостинг | Цена/мес | RAM | CPU | Диск | Оплата | Рейтинг |
|---------|----------|-----|-----|------|--------|---------|
| **Timeweb** | 200₽ (~$2) | 2GB | 1 | 20GB SSD | Карта РФ, Крипта | 🏆 #1 |
| **REG.RU** | 150₽ (~$1.5) | 2GB | 1 | 25GB SSD | Карта РФ, Крипта | ⭐ #2 |
| **Selectel** | 500₽ (~$5) | 2GB | 1 | 20GB SSD | Карта РФ | ⭐ #3 |
| **FirstVDS** | 200₽ (~$2) | 2GB | 1 | 20GB SSD | Карта РФ, Крипта | ⭐ #4 |

### Рекомендация: Timeweb VPS-1

**Почему Timeweb:**
- ✅ Стабильный хостинг (работает с 2006 года)
- ✅ Оптимальная цена (200₽/мес)
- ✅ Хорошая техподдержка
- ✅ Оплата криптовалютой (если нет карты РФ)
- ✅ Дата-центры в Москве и СПб
- ✅ Простая панель управления

**Альтернатива:** REG.RU (дешевле на 50₽, но чуть слабее поддержка)

---

## Часть 1: Заказ и настройка VPS

### Шаг 1.1: Регистрация на Timeweb

1. Перейти: https://timeweb.com/ru/services/vps/
2. Нажать "Заказать VPS"
3. Выбрать тариф: **VPS-1** (200₽/мес)
   - 1 vCPU
   - 2 GB RAM
   - 20 GB SSD
4. Конфигурация:
   - ОС: **Ubuntu 22.04 LTS**
   - Регион: **Москва** или **Санкт-Петербург**
   - Имя сервера: `russia-vpn`
5. Оплата:
   - **Вариант A:** Карта РФ (Mir, Visa/MC РФ)
   - **Вариант B:** Криптовалюта (Bitcoin, USDT, Ethereum)
   - **Вариант C:** Попросить друга в РФ

### Шаг 1.2: Получение доступа

После оплаты на email придёт:
- IP адрес сервера (например, `5.188.123.45`)
- Пароль root
- Ссылка на панель управления

**Сохраните эту информацию!**

### Шаг 1.3: Первое подключение

```bash
# С вашего компьютера
ssh root@5.188.123.45

# Введите пароль из email
# При первом подключении будет предложено сменить пароль
```

**Рекомендация:** Сразу смените пароль на сложный:
```bash
passwd
# Введите новый пароль (20+ символов, с цифрами и спецсимволами)
```

### Шаг 1.4: Базовая настройка безопасности

```bash
# Обновить систему
apt update && apt upgrade -y

# Установить базовые пакеты
apt install -y curl wget git htop nano ufw net-tools

# Настроить firewall
ufw allow 22/tcp      # SSH (если порт не менялся)
ufw allow 51822/udp   # AmneziaWG
ufw enable

# Подтвердить: yes

# Проверить статус
ufw status
```

### Шаг 1.5: Смена SSH порта (опционально, но рекомендуется)

```bash
# Изменить порт SSH для безопасности
nano /etc/ssh/sshd_config

# Найти строку:
# Port 22

# Изменить на:
Port 2222

# Сохранить: Ctrl+O, Enter, Ctrl+X

# Перезапустить SSH
systemctl restart sshd

# Разрешить новый порт в firewall
ufw allow 2222/tcp
ufw delete allow 22/tcp

# Отключиться
exit

# Подключиться с новым портом
ssh -p 2222 root@5.188.123.45
```

### Шаг 1.6: Установка Fail2ban (защита от брутфорса)

```bash
# Установить Fail2ban
apt install -y fail2ban

# Включить и запустить
systemctl enable fail2ban
systemctl start fail2ban

# Проверить статус
systemctl status fail2ban
```

---

## Часть 2: Установка AmneziaWG на VPS

### Шаг 2.1: Автоматическая установка

```bash
# Скачать скрипт установки
cd /tmp
wget https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/latest/download/amneziawg-install.sh

# Сделать исполняемым
chmod +x amneziawg-install.sh

# Запустить установку
./amneziawg-install.sh

# Дождаться завершения (2-5 минут)
```

**Альтернатива (через PPA):**
```bash
# Добавить репозиторий
add-apt-repository ppa:amnezia/ppa -y
apt update

# Установить пакеты
apt install -y amneziawg amneziawg-tools
```

### Шаг 2.2: Проверка установки

```bash
# Проверить команду
which awg
# Вывод: /usr/bin/awg

# Версия
awg --version

# Проверить модуль ядра
modprobe amneziawg
lsmod | grep amnezia
# Должен показать: amneziawg
```

### Шаг 2.3: Включить IP Forwarding

```bash
# Включить сейчас
sysctl -w net.ipv4.ip_forward=1

# Сделать постоянным
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Проверить
sysctl net.ipv4.ip_forward
# Должно быть: net.ipv4.ip_forward = 1
```

### Шаг 2.4: Создание ключей

```bash
# Создать директорию
mkdir -p /etc/amnezia/amneziawg-russia
cd /etc/amnezia/amneziawg-russia

# Генерация ключей сервера
umask 077
awg genkey | tee server_privatekey | awg pubkey > server_publickey
awg genpsk > preshared_key

# Показать ключи
echo "=== Server Private Key ==="
cat server_privatekey

echo "=== Server Public Key ==="
cat server_publickey

echo "=== Preshared Key ==="
cat preshared_key

# ⚠️ ВАЖНО: Сохраните эти ключи в защищённом месте!
```

**Скопируйте ключи в текстовый файл на вашем компьютере.**

### Шаг 2.5: Создание конфигурации сервера

**Вариант A: Скопировать готовый конфиг**

```bash
# На вашем компьютере (не на VPS)
scp russia-vps-amneziawg.conf root@5.188.123.45:/tmp/

# На VPS
cp /tmp/russia-vps-amneziawg.conf /etc/amnezia/amneziawg-russia/awg1.conf
```

**Вариант B: Создать вручную**

```bash
nano /etc/amnezia/amneziawg-russia/awg1.conf
```

Вставить (замените ключи):

```ini
[Interface]
Address = 10.9.1.1/24
ListenPort = 51822
PrivateKey = <ВСТАВИТЬ_server_privatekey>

Jc = 7
Jmin = 60
Jmax = 1200
S1 = 40
S2 = 60
H1 = 9876543210
H2 = 1234567890
H3 = 5544332211
H4 = 1122334455

PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = <БУДЕТ_ДОБАВЛЕН_ПОЗЖЕ_С_КЛИЕНТА>
PresharedKey = <ВСТАВИТЬ_preshared_key>
AllowedIPs = 10.9.1.2/32
PersistentKeepalive = 25
```

**Важно:** Проверьте сетевой интерфейс:
```bash
ip route | grep default
# Вывод: default via X.X.X.X dev INTERFACE_NAME

# Если не eth0, замените в PostUp/PostDown
```

Сохранить: Ctrl+O, Enter, Ctrl+X

**Установить права:**
```bash
chmod 600 /etc/amnezia/amneziawg-russia/awg1.conf
```

### Шаг 2.6: Тестовый запуск

```bash
# Запустить вручную
awg-quick up awg1

# Проверить интерфейс
awg show awg1
ip addr show awg1
# Должно показать: inet 10.9.1.1/24

# Проверить firewall правила
iptables -t nat -L POSTROUTING -n -v | grep awg1

# Остановить
awg-quick down awg1
```

Если всё OK, переходим к настройке клиента.

---

## Часть 3: Настройка клиента (GL-AX1800)

### Шаг 3.1: Подключение к роутеру

```bash
# Дома
ssh root@192.168.20.1

# В поездке
ssh root@192.168.100.1
```

### Шаг 3.2: Проверка AmneziaWG

```bash
# Должен быть уже установлен (из предыдущей настройки Oracle)
which awg
awg --version

# Если не установлен, см. AMNEZIAWG-SETUP.md
```

### Шаг 3.3: Создание директории и ключей клиента

```bash
# Создать директорию для Russia VPN
mkdir -p /etc/amnezia/amneziawg-russia
cd /etc/amnezia/amneziawg-russia

# Генерация ключей клиента
awg genkey | tee client_privatekey | awg pubkey > client_publickey

# Показать публичный ключ
cat client_publickey
# Скопируйте этот ключ!
```

### Шаг 3.4: Добавление клиента на сервер

**Вернуться на VPS:**

```bash
# На VPS
ssh -p 2222 root@5.188.123.45

# Открыть конфиг
nano /etc/amnezia/amneziawg-russia/awg1.conf

# В секции [Peer] заменить:
PublicKey = <ВСТАВИТЬ_client_publickey_С_РОУТЕРА>

# Сохранить: Ctrl+O, Enter, Ctrl+X
```

### Шаг 3.5: Создание конфигурации клиента

**На роутере:**

```bash
nano /etc/amnezia/amneziawg-russia/awg1.conf
```

Вставить (замените на свои значения):

```ini
[Interface]
PrivateKey = <ВСТАВИТЬ_client_privatekey>
Address = 10.9.1.2/24
DNS = 8.8.8.8, 1.1.1.1

Jc = 7
Jmin = 60
Jmax = 1200
S1 = 40
S2 = 60
H1 = 9876543210
H2 = 1234567890
H3 = 5544332211
H4 = 1122334455

[Peer]
PublicKey = <ВСТАВИТЬ_server_publickey_С_VPS>
PresharedKey = <ВСТАВИТЬ_preshared_key_С_VPS>
Endpoint = 5.188.123.45:51822
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

Сохранить: Ctrl+O, Enter, Ctrl+X

**Установить права:**
```bash
chmod 600 /etc/amnezia/amneziawg-russia/awg1.conf
```

### Шаг 3.6: Тестирование соединения

```bash
# Запустить AmneziaWG на роутере
awg-quick up awg1

# Проверить статус
awg show awg1

# Должен показать handshake
awg show awg1 latest-handshakes

# Ping сервера
ping -c 5 10.9.1.1

# Проверить внешний IP (должен быть российский)
curl ifconfig.me
curl ipinfo.io/country
# Должно показать: RU

# Остановить
awg-quick down awg1
```

**Если всё работает - поздравляю! Российский VPN настроен ✅**

---

## Часть 4: Запуск серверов в production

### Шаг 4.1: Автозапуск на VPS

```bash
# На VPS
ssh -p 2222 root@5.188.123.45

# Включить автозапуск
systemctl enable awg-quick@awg1
systemctl start awg-quick@awg1

# Проверить статус
systemctl status awg-quick@awg1

# Посмотреть логи
journalctl -u awg-quick@awg1 -f

# Проверить что слушает порт
ss -ulnp | grep 51822
```

### Шаг 4.2: Установка VPN Selector на роутер

```bash
# На роутере
cd /root

# Скопировать с компьютера
# scp openwrt-vpn-selector.sh root@192.168.100.1:/root/vpn-selector.sh

# Сделать исполняемым
chmod +x /root/vpn-selector.sh

# Создать alias для удобства
echo "alias vpn='/root/vpn-selector.sh'" >> /etc/profile
source /etc/profile

# Протестировать
vpn status
vpn russia
vpn status
```

### Шаг 4.3: Проверка после перезагрузки

**На VPS:**
```bash
reboot

# Подождать 1-2 минуты
ssh -p 2222 root@5.188.123.45

# Проверить что AmneziaWG запустился
systemctl status awg-quick@awg1
awg show awg1
```

---

## Использование

### Переключение между VPN

```bash
# Подключиться к Russia VPS (получить РФ IP)
vpn russia

# Подключиться к Oracle Cloud (обход блокировок РФ)
vpn oracle

# Подключиться к домашней сети
vpn home

# Отключить все VPN
vpn off

# Проверить статус
vpn status
```

### Сценарии использования

**Сценарий 1: Доступ к Сбербанку из-за границы**
```bash
vpn russia
# Открыть браузер → https://online.sberbank.ru
# Сбербанк видит российский IP ✅
```

**Сценарий 2: Просмотр Match TV за границей**
```bash
vpn russia
# Открыть https://matchtv.ru
# Работает без блокировок ✅
```

**Сценарий 3: Обход блокировок в России**
```bash
vpn oracle
# Доступ к заблокированным сайтам ✅
```

---

## Мониторинг и обслуживание

### Проверка VPS

```bash
# Подключиться к VPS
ssh -p 2222 root@5.188.123.45

# Статус сервера
awg show awg1
systemctl status awg-quick@awg1

# Показать подключенных клиентов
awg show awg1 peers

# Статистика трафика
awg show awg1 transfer

# Логи
journalctl -u awg-quick@awg1 -n 50

# Нагрузка сервера
htop
free -h
df -h
```

### Автоматический мониторинг

**Создать скрипт `/usr/local/bin/awg-monitor.sh`:**

```bash
cat > /usr/local/bin/awg-monitor.sh << 'EOF'
#!/bin/bash

if ! systemctl is-active --quiet awg-quick@awg1; then
    echo "$(date): AmneziaWG Russia не работает, перезапуск..." >> /var/log/awg-monitor.log
    systemctl restart awg-quick@awg1
fi
EOF

chmod +x /usr/local/bin/awg-monitor.sh

# Добавить в cron (проверка каждые 5 минут)
crontab -e

# Добавить строку:
*/5 * * * * /usr/local/bin/awg-monitor.sh
```

### Обновления безопасности

```bash
# На VPS, раз в неделю:
apt update && apt upgrade -y

# Автообновления (рекомендуется)
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

---

## Troubleshooting

### Проблема 1: Клиент не может подключиться

**Решение:**
```bash
# На VPS проверить firewall
ufw status | grep 51822

# Если нет, добавить
ufw allow 51822/udp

# Смотреть пакеты на сервере
tcpdump -i eth0 udp port 51822 -v
```

### Проблема 2: Подключается, но нет интернета

**Решение:**
```bash
# На VPS проверить IP forwarding
sysctl net.ipv4.ip_forward
# Должно быть: 1

# Проверить NAT правила
iptables -t nat -L POSTROUTING -n -v

# Перезапустить AmneziaWG
systemctl restart awg-quick@awg1
```

### Проблема 3: Медленная скорость

**Решение:**
```bash
# На VPS и клиенте уменьшить обфускацию
# В конфиге изменить:
Jc = 3      # было 7
Jmax = 800  # было 1200
```

### Проблема 4: VPS недоступен

**Через панель управления Timeweb:**
1. Войти в панель: https://timeweb.cloud/
2. Серверы → ваш сервер → Консоль
3. Проверить что сервер запущен
4. Перезапустить если нужно

---

## Безопасность

### Чеклист безопасности

- ✅ Сменить SSH порт (22 → 2222)
- ✅ Установить Fail2ban
- ✅ Настроить ufw firewall
- ✅ Сложный пароль root
- ✅ Автообновления безопасности
- ✅ Регулярный мониторинг логов

### Резервное копирование

```bash
# На VPS
tar -czf /tmp/awg-russia-backup-$(date +%Y%m%d).tar.gz \
  /etc/amnezia/amneziawg-russia/

# Скачать backup
scp -P 2222 root@5.188.123.45:/tmp/awg-russia-backup-*.tar.gz ./
```

---

## FAQ

**Q: Сколько стоит содержание российского VPS?**
A: 200-500₽/мес (~$2-5), в зависимости от хостинга.

**Q: Можно ли использовать один VPS и для Oracle и для Russia?**
A: Нет. Для российского IP нужен VPS в России. Oracle Cloud обычно не в РФ.

**Q: Работает ли Russia VPN для обхода блокировок В России?**
A: Нет! Российский VPS → российский IP → DPI видит всё. Для обхода используйте Oracle Cloud.

**Q: Могу ли я подключить несколько устройств?**
A: Да! Добавьте дополнительные [Peer] секции на сервере с разными IP (10.9.1.3, 10.9.1.4, и т.д.)

**Q: Как оплатить хостинг без карты РФ?**
A: Используйте криптовалюту (USDT, BTC) на Timeweb или REG.RU.

---

## Дополнительные ресурсы

- **Конфигурации:** `russia-vps-amneziawg.conf`, `openwrt-travel-russia-client.conf`
- **Скрипты:** `openwrt-vpn-selector.sh`
- **AmneziaWG:** https://github.com/amnezia-vpn
- **Timeweb:** https://timeweb.com/
- **Поддержка:** Создайте issue в вашем репозитории

---

**Автор:** Configuration Generator
**Версия:** 2.4 (Russia VPS)
**Дата:** 2025-10-03
