# AmneziaWG - Полное руководство по настройке

## Обзор

**AmneziaWG** — это форк WireGuard с обфускацией трафика, специально разработанный для обхода DPI (Deep Packet Inspection) блокировок в странах с цензурой, включая Россию.

### Почему AmneziaWG?

**Проблема с обычным WireGuard в России:**
```
Router → WireGuard packets → ISP DPI → "Это VPN!" → БЛОКИРОВКА
```

**Решение с AmneziaWG:**
```
Router → AmneziaWG packets → ISP DPI → "Обычный UDP трафик" → ПРОПУСК
```

### Ключевые отличия от WireGuard

| Характеристика | WireGuard | AmneziaWG |
|----------------|-----------|-----------|
| **Обнаружение DPI** | ✅ Легко | ❌ Сложно |
| **Скорость** | 🚀 Максимальная | 🚀 Почти максимальная |
| **Обфускация** | ❌ Нет | ✅ Есть |
| **Команды** | `wg`, `wg-quick` | `awg`, `awg-quick` |
| **Интерфейс** | `wg0` | `awg0` |
| **Порт (default)** | 51820 | 51821 |
| **Подсеть (в нашей конфиг)** | 10.8.1.0/24 | 10.8.2.0/24 |

## Архитектура

### В поездке (Travel Mode)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hotel WiFi / Мобильный интернет (РФ с DPI блокировкой)            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ Обфусцированный трафик
                              │ (выглядит как обычный UDP)
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  GL.iNet AX1800 Travel Router                                       │
│  ┌────────────────────┬────────────────────┐                        │
│  │  AmneziaWG (awg0)  │  WireGuard (wg0)   │                        │
│  │  Priority: 1       │  Priority: 2       │                        │
│  │  10.8.2.2/24       │  10.8.1.2/24       │                        │
│  └────────────────────┴────────────────────┘                        │
│         │ Primary              │ Fallback                            │
│         │ (если работает)      │ (если AWG заблокирован)            │
└─────────┼──────────────────────┼─────────────────────────────────────┘
          │                      │
          ↓                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Oracle Cloud (Публичный IP)                                        │
│  ┌────────────────────┐  ┌────────────────────┐                    │
│  │  AmneziaWG Server  │  │  WireGuard Server  │                    │
│  │  awg0: 10.8.2.1    │  │  wg0: 10.8.1.1     │                    │
│  │  Port: 51821       │  │  Port: 51820       │                    │
│  └────────────────────┘  └────────────────────┘                    │
│            │                      │                                  │
│            └──────────┬───────────┘                                 │
│                       ↓                                              │
│              WireGuard туннель                                       │
└───────────────────────┼──────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Домашняя сеть (Proxmox + OPNsense)                                 │
│  192.168.10.0/24, 192.168.20.0/24                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Установка

### Часть 1: Oracle Cloud Server

#### Шаг 1: Подключение к серверу
```bash
ssh ubuntu@your-oracle-cloud-ip
```

#### Шаг 2: Установка AmneziaWG

**Вариант A: Автоматическая установка (рекомендуется)**
```bash
wget https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/latest/download/amneziawg-install.sh
chmod +x amneziawg-install.sh
sudo ./amneziawg-install.sh
```

**Вариант B: Через PPA (Ubuntu/Debian)**
```bash
sudo add-apt-repository ppa:amnezia/ppa
sudo apt update
sudo apt install amneziawg amneziawg-tools
```

**Вариант C: Вручную (универсальный)**
```bash
# Скачать последнюю версию
cd /tmp
wget https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/download/v1.0.20231030/amneziawg-module-$(uname -r).deb
wget https://github.com/amnezia-vpn/amneziawg-tools/releases/download/v1.0.20231030/amneziawg-tools_1.0.20231030-1_amd64.deb

sudo dpkg -i amneziawg-module-*.deb
sudo dpkg -i amneziawg-tools_*.deb
```

#### Шаг 3: Проверка установки
```bash
# Проверить команду awg
which awg
awg --version

# Проверить модуль ядра
sudo modprobe amneziawg
lsmod | grep amnezia
```

#### Шаг 4: Создание ключей
```bash
sudo mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg

# Генерация ключей сервера
sudo sh -c 'umask 077; awg genkey | tee server_privatekey | awg pubkey > server_publickey'

# Генерация pre-shared key
sudo sh -c 'awg genpsk > preshared_key'

# Просмотр ключей
echo "Server Private Key:"
sudo cat server_privatekey

echo "Server Public Key:"
sudo cat server_publickey

echo "Preshared Key:"
sudo cat preshared_key
```

**⚠️ ВАЖНО: Сохраните эти ключи в безопасном месте!**

#### Шаг 5: Создание конфигурации сервера
```bash
# Скопировать готовый конфиг с компьютера
scp oracle-cloud-amneziawg.conf ubuntu@your-oracle-ip:/tmp/

# Или создать вручную на сервере
sudo nano /etc/amnezia/amneziawg/awg0.conf
```

Вставить содержимое из `oracle-cloud-amneziawg.conf` и заменить:
- `SERVER_PRIVATE_KEY_CHANGE_ME` → содержимое `server_privatekey`
- `PRESHARED_KEY_CHANGE_ME` → содержимое `preshared_key`
- `GL_AX1800_PUBLIC_KEY_CHANGE_ME` → публичный ключ клиента (создадим позже)

#### Шаг 6: Настройка firewall
```bash
# Включить IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# Открыть порт в iptables
sudo iptables -I INPUT -p udp --dport 51821 -j ACCEPT
sudo netfilter-persistent save

# Проверить правила
sudo iptables -L INPUT -n -v | grep 51821
```

#### Шаг 7: Открыть порт в Oracle Cloud Console

1. Войти в Oracle Cloud Console
2. **Networking** → **Virtual Cloud Networks**
3. Выбрать VCN → **Security Lists** → **Default Security List**
4. **Add Ingress Rule:**
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: `UDP`
   - Destination Port Range: `51821`
   - Description: `AmneziaWG VPN`
5. Save

#### Шаг 8: Запуск AmneziaWG
```bash
# Запустить вручную (для теста)
sudo awg-quick up awg0

# Проверить статус
sudo awg show awg0

# Если всё OK, добавить в автозагрузку
sudo systemctl enable awg-quick@awg0

# Посмотреть логи
sudo journalctl -u awg-quick@awg0 -f
```

### Часть 2: GL-AXT1800 Client

#### Шаг 1: Подключение к роутеру
```bash
# Дома
ssh root@192.168.20.1

# Или в поездке
ssh root@192.168.100.1
```

#### Шаг 2: Установка AmneziaWG на OpenWRT

**Определить архитектуру:**
```bash
opkg print-architecture
# Для GL-AXT1800: mipsel_24kc
```

**Скачать и установить пакеты:**
```bash
cd /tmp

# Модуль ядра для MediaTek MT7621 (GL-AXT1800)
wget https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases/download/v1.0.20231030/kmod-amneziawg_5.10.176-1_mipsel_24kc.ipk

# Утилиты
wget https://github.com/amnezia-vpn/amneziawg-tools/releases/download/v1.0.20231030/amneziawg-tools_1.0.20231030-1_mipsel_24kc.ipk

# Установить
opkg update
opkg install kmod-amneziawg_*.ipk
opkg install amneziawg-tools_*.ipk
```

**Проверка:**
```bash
which awg
awg --version
```

#### Шаг 3: Создание ключей клиента
```bash
mkdir -p /etc/amnezia/amneziawg
cd /etc/amnezia/amneziawg

# Генерация ключей
awg genkey | tee client_privatekey | awg pubkey > client_publickey

# Просмотр
echo "Client Private Key:"
cat client_privatekey

echo "Client Public Key:"
cat client_publickey
```

**⚠️ Скопируйте Client Public Key — нужно добавить на сервер!**

#### Шаг 4: Добавление клиента на сервер

На Oracle Cloud сервере:
```bash
# Открыть конфиг сервера
sudo nano /etc/amnezia/amneziawg/awg0.conf

# Найти секцию [Peer] для GL-AXT1800 и вставить:
[Peer]
PublicKey = <CLIENT_PUBLIC_KEY_ИЗ_РОУТЕРА>
PresharedKey = <PRESHARED_KEY_С_СЕРВЕРА>
AllowedIPs = 10.8.2.2/32
PersistentKeepalive = 25

# Сохранить и перезапустить
sudo awg-quick down awg0
sudo awg-quick up awg0
```

#### Шаг 5: Создание конфигурации клиента

На роутере:
```bash
nano /etc/amnezia/amneziawg/awg0.conf
```

Вставить содержимое из `openwrt-travel-amneziawg-client.conf` и заменить:
- `CLIENT_PRIVATE_KEY_CHANGE_ME` → содержимое `client_privatekey`
- `SERVER_PUBLIC_KEY_CHANGE_ME` → публичный ключ с сервера
- `PRESHARED_KEY_CHANGE_ME` → preshared key с сервера
- `ORACLE_CLOUD_IP` → публичный IP Oracle Cloud

```bash
chmod 600 /etc/amnezia/amneziawg/awg0.conf
```

#### Шаг 6: Тестирование соединения
```bash
# Запустить AmneziaWG
awg-quick up awg0

# Проверить интерфейс
ip addr show awg0
# Должен показать: inet 10.8.2.2/24

# Проверить handshake
awg show awg0
# Должен показать: latest handshake: X seconds ago

# Ping сервера
ping -c 5 10.8.2.1

# Проверить внешний IP
curl ifconfig.me
# Должен показать IP Oracle Cloud

# Traceroute
traceroute -n 8.8.8.8
# Первый hop должен быть 10.8.2.1
```

#### Шаг 7: Настройка routing через VPN

**Добавить в /etc/config/network:**
```bash
uci set network.amneziavpn=interface
uci set network.amneziavpn.proto='none'
uci set network.amneziavpn.device='awg0'
uci set network.amneziavpn.auto='0'
uci commit network
/etc/init.d/network reload
```

**Настроить firewall (/etc/config/firewall):**
```bash
# Добавить VPN зону
uci add firewall zone
uci set firewall.@zone[-1].name='vpn'
uci set firewall.@zone[-1].input='ACCEPT'
uci set firewall.@zone[-1].output='ACCEPT'
uci set firewall.@zone[-1].forward='REJECT'
uci set firewall.@zone[-1].masq='1'
uci set firewall.@zone[-1].mtu_fix='1'
uci add_list firewall.@zone[-1].network='amneziavpn'

# Forwarding LAN → VPN
uci add firewall forwarding
uci set firewall.@forwarding[-1].src='lan'
uci set firewall.@forwarding[-1].dest='vpn'

uci commit firewall
/etc/init.d/firewall restart
```

#### Шаг 8: Автозапуск

**Вариант A: Через init script (рекомендуется)**
```bash
cat > /etc/init.d/amneziawg << 'EOF'
#!/bin/sh /etc/rc.common

START=99
STOP=10

start() {
    awg-quick up awg0
}

stop() {
    awg-quick down awg0
}

restart() {
    stop
    sleep 2
    start
}
EOF

chmod +x /etc/init.d/amneziawg
/etc/init.d/amneziawg enable
```

**Вариант B: Через rc.local**
```bash
echo "awg-quick up awg0 &" >> /etc/rc.local
```

#### Шаг 9: Установка failover скрипта

```bash
# Скопировать с компьютера
scp openwrt-amneziawg-failover.sh root@192.168.100.1:/root/

# Сделать исполняемым
chmod +x /root/amneziawg-failover.sh

# Протестировать
/root/amneziawg-failover.sh status

# Добавить в cron (проверка каждые 5 минут)
echo "*/5 * * * * /root/amneziawg-failover.sh check" >> /etc/crontabs/root
/etc/init.d/cron restart
```

## Использование

### Базовые команды

**На сервере (Oracle Cloud):**
```bash
# Запуск
sudo awg-quick up awg0

# Остановка
sudo awg-quick down awg0

# Перезапуск
sudo awg-quick down awg0 && sudo awg-quick up awg0

# Статус
sudo awg show awg0

# Логи
sudo journalctl -u awg-quick@awg0 -f
```

**На клиенте (GL-AXT1800):**
```bash
# Запуск
awg-quick up awg0

# Остановка
awg-quick down awg0

# Статус
awg show awg0

# Проверка соединения
/root/amneziawg-failover.sh status
```

### Переключение между WireGuard и AmneziaWG

**Вручную:**
```bash
# AmneziaWG → WireGuard
awg-quick down awg0
wg-quick up wg0

# WireGuard → AmneziaWG
wg-quick down wg0
awg-quick up awg0
```

**Автоматически (через failover скрипт):**
```bash
# Автоматический выбор лучшего протокола
/root/amneziawg-failover.sh start

# Проверка и автопереключение
/root/amneziawg-failover.sh check
```

### Мониторинг

**Проверка handshake:**
```bash
# Сервер
sudo awg show awg0 latest-handshakes

# Клиент
awg show awg0 latest-handshakes
```

**Статистика трафика:**
```bash
awg show awg0 transfer
```

**Просмотр логов failover:**
```bash
tail -f /var/log/vpn-failover.log
```

## Troubleshooting

### Проблема: AmneziaWG не запускается

**Решение:**
```bash
# Проверить модуль ядра
lsmod | grep amnezia

# Загрузить вручную
modprobe amneziawg

# Проверить dmesg
dmesg | grep amnezia

# Проверить конфиг
awg-quick up awg0
# Смотреть ошибки
```

### Проблема: Нет handshake

**Решение:**
```bash
# На сервере
sudo tcpdump -i ens3 udp port 51821 -v

# На клиенте попробовать подключиться
awg-quick up awg0

# Проверить firewall
sudo iptables -L INPUT -n -v | grep 51821

# Проверить Oracle Cloud Security List (Web Console)
```

### Проблема: Подключается, но нет интернета

**Решение:**
```bash
# Проверить IP forwarding на сервере
sudo sysctl net.ipv4.ip_forward
# Должно быть: 1

# Проверить NAT правила
sudo iptables -t nat -L POSTROUTING -n -v

# Проверить маршруты на клиенте
ip route show

# Проверить DNS
nslookup google.com 192.168.10.1
```

### Проблема: Медленная скорость

**Решение:**
```bash
# Уменьшить обфускацию (в конфигах awg0.conf):
Jc = 3          # Было 5
Jmin = 30       # Было 50
Jmax = 500      # Было 1000

# Настроить MTU
ip link set awg0 mtu 1420

# Включить hardware offloading (если поддерживается)
ethtool -K eth1 gso on tso on
```

### Проблема: Всё равно блокируется

**Решение:**
1. Изменить порт (вместо 51821 использовать 443 или 53)
2. Изменить обфускацию параметры (H1-H4 на случайные значения)
3. Добавить Shadowsocks как fallback
4. Использовать VLESS с реальным сайтом

## Сравнение производительности

### Тестирование скорости

**Без VPN:**
```bash
curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 -
```

**С WireGuard:**
```bash
wg-quick up wg0
# запустить speedtest
wg-quick down wg0
```

**С AmneziaWG:**
```bash
awg-quick up awg0
# запустить speedtest
awg-quick down awg0
```

### Ожидаемые результаты (GL-AXT1800)

| Сценарий | Скорость Download | Скорость Upload | Latency |
|----------|-------------------|-----------------|---------|
| Без VPN | 100 Mbps | 100 Mbps | 10 ms |
| WireGuard | 90-95 Mbps | 90-95 Mbps | 15-20 ms |
| AmneziaWG | 85-90 Mbps | 85-90 Mbps | 20-25 ms |

**Вывод:** AmneziaWG ~5-10% медленнее WireGuard из-за обфускации, но всё равно очень быстрый.

## Безопасность

### Рекомендации

1. **Регулярно обновлять ключи:**
```bash
# Раз в месяц менять preshared key
awg genpsk > new_preshared_key
# Обновить на сервере и клиенте
```

2. **Использовать сильные обфускацию параметры:**
   - Изменить H1-H4 на уникальные значения
   - Увеличить Jc, Jmin, Jmax (но не слишком — влияет на скорость)

3. **Мониторить логи:**
```bash
# Сервер
sudo journalctl -u awg-quick@awg0 -f

# Клиент
tail -f /var/log/vpn-failover.log
```

4. **Firewall правила:**
   - Разрешить только необходимые порты
   - Использовать fail2ban на сервере

5. **Backup конфигурации:**
```bash
tar -czf amneziawg-backup-$(date +%Y%m%d).tar.gz /etc/amnezia/
```

## Дополнительные ресурсы

- **AmneziaWG GitHub:** https://github.com/amnezia-vpn/amneziawg-linux-kernel-module
- **AmneziaWG Tools:** https://github.com/amnezia-vpn/amneziawg-tools
- **Документация Amnezia VPN:** https://docs.amnezia.org/
- **OpenWRT форум:** https://forum.openwrt.org/

## FAQ

**Q: Можно ли использовать WireGuard и AmneziaWG одновременно?**
A: Да! Они используют разные интерфейсы (wg0 и awg0) и порты. Можно переключаться между ними.

**Q: AmneziaWG безопасен?**
A: Да, это форк WireGuard с дополнительной обфускацией. Криптография та же.

**Q: Нужно ли платить за AmneziaWG?**
A: Нет, это open source проект.

**Q: Будет ли работать на других устройствах (Android, iOS)?**
A: Да, есть клиенты Amnezia VPN для всех платформ.

**Q: Как часто обновлять?**
A: Проверяйте обновления раз в месяц: https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/releases
