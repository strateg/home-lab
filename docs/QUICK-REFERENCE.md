# Quick Reference - Команды и проверки

## Генерация WireGuard ключей

```bash
# На любом устройстве с WireGuard
wg genkey | tee privatekey | wg pubkey > publickey

# Просмотр ключей
cat privatekey  # Идет в конфиг [Interface] PrivateKey
cat publickey   # Идет в конфиг [Peer] PublicKey на другой стороне
```

## AmneziaWG - VPN с обфускацией (для обхода DPI в РФ)

### Генерация ключей AmneziaWG

```bash
# На сервере/роутере с AmneziaWG
awg genkey | tee privatekey | awg pubkey > publickey
awg genpsk > preshared_key

# Просмотр ключей
cat privatekey       # [Interface] PrivateKey
cat publickey        # [Peer] PublicKey на другой стороне
cat preshared_key    # [Peer] PresharedKey (опционально, но рекомендуется)
```

### Управление AmneziaWG

```bash
# Запустить туннель
awg-quick up awg0

# Остановить туннель
awg-quick down awg0

# Проверить статус
awg show awg0

# Показать handshake
awg show awg0 latest-handshakes

# Показать трафик
awg show awg0 transfer

# Показать peers
awg show awg0 peers
```

### Автоматическое переключение WireGuard ↔ AmneziaWG

```bash
# Запустить failover (приоритет: AmneziaWG → WireGuard)
/root/amneziawg-failover.sh start

# Проверить текущее состояние
/root/amneziawg-failover.sh status

# Проверка и автопереключение
/root/amneziawg-failover.sh check

# Остановить все VPN
/root/amneziawg-failover.sh stop

# Перезапустить с автовыбором
/root/amneziawg-failover.sh restart
```

### Проверка какой VPN активен

```bash
# Проверить интерфейсы
ip link show | grep -E 'awg0|wg0'

# Если awg0 UP → AmneziaWG активен
# Если wg0 UP → WireGuard активен

# Проверить маршруты
ip route show | grep -E 'awg0|wg0'

# Проверить внешний IP
curl ifconfig.me
# Должен показать IP Oracle Cloud, если VPN работает

# Посмотреть логи failover
tail -f /var/log/vpn-failover.log
```

### Сравнение протоколов

```bash
# WireGuard статус
wg show wg0

# AmneziaWG статус
awg show awg0

# Speedtest с WireGuard
wg-quick up wg0
curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 -
wg-quick down wg0

# Speedtest с AmneziaWG
awg-quick up awg0
curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 -
awg-quick down awg0
```

## OpenWRT - Управление режимами

### Проверка текущего режима
```bash
cat /etc/openwrt-mode
# Вывод: "home" или "travel"
```

### Ручное переключение
```bash
# Запустить детектор режима
/usr/bin/openwrt-mode-switcher.sh

# Принудительно в HOME режим
cp /etc/openwrt-configs/home/* /etc/config/
/etc/init.d/network restart
/etc/init.d/firewall restart
wifi reload

# Принудительно в TRAVEL режим
cp /etc/openwrt-configs/travel/* /etc/config/
/etc/init.d/network restart
/etc/init.d/firewall restart
/etc/init.d/wireguard start
```

### VPN Failover
```bash
# Проверить активный VPN
cat /tmp/active-vpn
# Вывод: "home", "oracle", или "direct"

# Запустить failover вручную
/usr/bin/openwrt-vpn-failover.sh

# Проверить WireGuard статус
wg show

# Проверить доступность через VPN
ping -c 3 10.0.99.10  # Proxmox через VPN
```

## OpenWRT - Сеть и WiFi

### Сетевая диагностика
```bash
# Показать все интерфейсы
ip addr show

# Показать маршруты
ip route show
ip route show table 100  # Policy routing table

# Показать правила маршрутизации
ip rule show

# Тест DNS
nslookup google.com
nslookup google.com 192.168.20.1  # Через AdGuard

# Проверить доступность gateway
ping -c 3 192.168.10.1  # OPNsense (дома)
ping -c 3 10.0.200.1    # OPNsense через VPN (поездка)
```

### WiFi управление
```bash
# Показать статус WiFi
wifi status

# Сканировать каналы
wifi survey radio0  # 5GHz
wifi survey radio1  # 2.4GHz

# Перезапустить WiFi
wifi reload
wifi up
wifi down

# Показать подключенных клиентов
iw dev wlan0 station dump  # 5GHz
iw dev wlan1 station dump  # 2.4GHz
```

### DHCP и клиенты
```bash
# Показать DHCP leases
cat /tmp/dhcp.leases

# Показать подключенных клиентов
arp -a

# Очистить DHCP leases
rm /tmp/dhcp.leases
/etc/init.d/dnsmasq restart
```

## OpenWRT - Логи и мониторинг

```bash
# Непрерывный просмотр логов
logread -f

# Фильтр по службе
logread | grep wireguard
logread | grep mode-switcher
logread | grep vpn-failover
logread | grep firewall

# Последние 50 строк
logread | tail -50

# Очистить логи
logread -c
```

## AdGuard Home

### Управление службой
```bash
# Статус
/etc/init.d/AdGuardHome status

# Старт/стоп/рестарт
/etc/init.d/AdGuardHome start
/etc/init.d/AdGuardHome stop
/etc/init.d/AdGuardHome restart

# Включить автозапуск
/etc/init.d/AdGuardHome enable

# Просмотр логов
tail -f /var/log/adguardhome.log
```

### Web UI
```bash
# Дома
http://192.168.20.1:3000

# Через VPN в поездке
ssh -L 3000:192.168.20.1:3000 root@192.168.100.1
# Затем открыть: http://localhost:3000
```

## OPNsense

### SSH доступ
```bash
# Дома из локальной сети
ssh root@192.168.10.1

# Из MGMT сети
ssh root@10.0.99.10

# Через VPN в поездке (через OpenWRT)
ssh root@10.0.99.10
```

### Базовые команды
```bash
# Показать интерфейсы
ifconfig

# Показать правила firewall
pfctl -sr

# Показать NAT правила
pfctl -sn

# Показать состояния соединений
pfctl -ss

# Перезапустить firewall
/etc/rc.reload_all

# Просмотр логов
tail -f /var/log/filter.log
tail -f /var/log/system.log
```

### WireGuard на OPNsense
```bash
# Показать конфигурацию
wg show

# Показать конкретный интерфейс
wg show wg0

# Перезапустить WireGuard
service wireguard restart
```

## Proxmox

### Сеть
```bash
# Показать bridges
brctl show

# Показать интерфейсы
ip addr show

# Применить изменения сети (осторожно!)
ifreload -a

# Проверить связность
ping 192.168.10.1  # OPNsense LAN
ping 10.0.30.10    # LXC container
```

### VM управление
```bash
# Список VM
qm list

# Запустить OPNsense VM (ID 100)
qm start 100

# Остановить VM
qm stop 100

# Перезапустить VM
qm reboot 100

# Консоль VM
qm terminal 100

# Статус VM
qm status 100
```

### LXC управление
```bash
# Список контейнеров
pct list

# Запустить контейнер
pct start 200

# Остановить контейнер
pct stop 200

# Войти в контейнер
pct enter 200

# Выполнить команду в контейнере
pct exec 200 -- ls -la
```

## Oracle Cloud

### SSH доступ
```bash
# Прямой доступ
ssh ubuntu@ORACLE_PUBLIC_IP

# Через ключ
ssh -i ~/.ssh/oracle_key ubuntu@ORACLE_PUBLIC_IP
```

### WireGuard на Oracle
```bash
# Показать статус
sudo systemctl status wg-quick@wg0

# Перезапустить
sudo systemctl restart wg-quick@wg0

# Показать конфигурацию
sudo wg show

# Просмотр логов
sudo journalctl -u wg-quick@wg0 -f

# Проверить доступность peers
ping 10.8.1.2  # OpenWRT travel (WireGuard)
```

### AmneziaWG на Oracle (обход DPI блокировок)
```bash
# Показать статус
sudo systemctl status awg-quick@awg0

# Запустить
sudo systemctl start awg-quick@awg0

# Остановить
sudo systemctl stop awg-quick@awg0

# Перезапустить
sudo systemctl restart awg-quick@awg0

# Включить автозапуск
sudo systemctl enable awg-quick@awg0

# Показать конфигурацию
sudo awg show awg0

# Показать handshake (проверить что клиент подключен)
sudo awg show awg0 latest-handshakes

# Показать трафик
sudo awg show awg0 transfer

# Просмотр логов
sudo journalctl -u awg-quick@awg0 -f

# Проверить доступность peer
ping 10.8.2.2  # OpenWRT travel (AmneziaWG)

# Отладка: показать пакеты на порту 51821
sudo tcpdump -i ens3 udp port 51821 -v
```

### Сравнение WireGuard vs AmneziaWG на Oracle
```bash
# Оба могут работать одновременно
sudo awg show awg0    # AmneziaWG (10.8.2.0/24, порт 51821)
sudo wg show wg0      # WireGuard  (10.8.1.0/24, порт 51820)

# Проверить оба порта открыты
sudo ss -ulnp | grep -E '51820|51821'
```

### Firewall (iptables)
```bash
# Показать правила
sudo iptables -L -n -v
sudo iptables -t nat -L -n -v

# Разрешить WireGuard порт
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT

# Разрешить AmneziaWG Oracle порт
sudo iptables -A INPUT -p udp --dport 51821 -j ACCEPT

# Разрешить AmneziaWG Russia порт
sudo iptables -A INPUT -p udp --dport 51822 -j ACCEPT

# Сохранить правила
sudo netfilter-persistent save
```

## Russia VPS (Российский IP)

### SSH доступ
```bash
# Прямой доступ
ssh root@RUSSIA_VPS_IP

# Если изменён порт SSH
ssh -p 2222 root@RUSSIA_VPS_IP

# Через ключ
ssh -p 2222 -i ~/.ssh/russia_key root@RUSSIA_VPS_IP
```

### AmneziaWG на Russia VPS

```bash
# Показать статус
sudo systemctl status awg-quick@awg1

# Запустить
sudo systemctl start awg-quick@awg1

# Остановить
sudo systemctl stop awg-quick@awg1

# Перезапустить
sudo systemctl restart awg-quick@awg1

# Включить автозапуск
sudo systemctl enable awg-quick@awg1

# Показать конфигурацию
sudo awg show awg1

# Показать handshake (проверить подключенных клиентов)
sudo awg show awg1 latest-handshakes

# Показать трафик
sudo awg show awg1 transfer

# Показать peers
sudo awg show awg1 peers

# Просмотр логов
sudo journalctl -u awg-quick@awg1 -f

# Проверить доступность клиента
ping 10.9.1.2  # GL-AXT1800

# Отладка: показать пакеты на порту 51822
sudo tcpdump -i eth0 udp port 51822 -v

# Проверить что порт слушает
sudo ss -ulnp | grep 51822
```

### Мониторинг Russia VPS

```bash
# Нагрузка сервера
htop

# Использование памяти
free -h

# Использование диска
df -h

# Сетевая статистика
ifconfig
ip -s link

# Логи системы
tail -f /var/log/syslog

# Логи AmneziaWG
journalctl -u awg-quick@awg1 -n 100
```

## VPN Selector (переключение между 3 VPN)

### Базовое использование

```bash
# Подключиться к Russia VPS (российский IP)
vpn russia
# или
/root/vpn-selector.sh russia

# Подключиться к Oracle Cloud (обход DPI РФ)
vpn oracle

# Подключиться к домашней сети
vpn home

# Отключить все VPN
vpn off

# Проверить статус
vpn status
```

### Расширенные команды VPN Selector

```bash
# Показать помощь
vpn help

# Проверить какой VPN активен
cat /tmp/active_vpn

# Посмотреть логи
tail -f /var/log/vpn-selector.log

# Проверить все интерфейсы
ip link show | grep -E 'awg0|awg1|wg0'

# Если awg0 → Oracle Cloud активен
# Если awg1 → Russia VPS активен
# Если wg0 → Home VPN активен
```

### Сценарии использования VPN Selector

```bash
# Сценарий 1: Вы за границей, нужен доступ к Сбербанку
vpn russia
# Открыть браузер → https://online.sberbank.ru

# Сценарий 2: Вы в России, нужен обход блокировок
vpn oracle
# Доступ к заблокированным сайтам

# Сценарий 3: Нужен доступ к домашнему Proxmox
vpn home
# http://10.0.99.10

# Сценарий 4: Проверить внешний IP
vpn status
curl ifconfig.me
curl ipinfo.io
```

### Проверка какой VPN работает

```bash
# Метод 1: Через VPN selector
vpn status

# Метод 2: Проверить интерфейсы
if ip link show awg0 2>/dev/null | grep -q "state UP"; then
    echo "Oracle Cloud VPN активен"
elif ip link show awg1 2>/dev/null | grep -q "state UP"; then
    echo "Russia VPS VPN активен"
elif ip link show wg0 2>/dev/null | grep -q "state UP"; then
    echo "Home VPN активен"
else
    echo "VPN не активен"
fi

# Метод 3: Проверить внешний IP
curl ifconfig.me
curl ipinfo.io/country
# RU = Россия (Russia VPS)
# Другое = Oracle Cloud или прямое подключение
```

## Диагностика подключения

### Тест связности (дома)
```bash
# С компьютера в локальной сети
ping 192.168.20.1     # OpenWRT
ping 192.168.10.1     # OPNsense
ping 10.0.30.10       # LXC container
ping 10.0.99.1        # Proxmox
ping 8.8.8.8          # Internet

# Traceroute
traceroute 10.0.30.10
traceroute google.com
```

### Тест связности (в поездке)
```bash
# С устройства подключенного к OpenWRT
ping 192.168.100.1    # OpenWRT local
ping 10.0.99.10       # OPNsense через VPN
ping 10.0.30.10       # LXC через VPN

# Проверить VPN туннель
ssh root@192.168.100.1
wg show
ping -I wg-home 10.0.99.10
```

### DNS тесты
```bash
# Тест разрешения
nslookup google.com

# Через конкретный DNS сервер
nslookup google.com 192.168.20.1  # AdGuard
nslookup google.com 1.1.1.1       # Cloudflare

# Dig для подробностей
dig google.com
dig @192.168.20.1 google.com

# Проверка DoH
curl -H 'accept: application/dns-json' 'https://cloudflare-dns.com/dns-query?name=google.com&type=A'
```

## Производительность

### Скорость сети
```bash
# Установка iperf3 (на OpenWRT)
opkg update
opkg install iperf3

# Сервер
iperf3 -s

# Клиент (с другого устройства)
iperf3 -c 192.168.20.1

# Тест через VPN
iperf3 -c 10.0.99.10
```

### Bandwidth мониторинг
```bash
# OpenWRT - установить vnstat
opkg install vnstat luci-app-vnstat

# Показать статистику
vnstat -i eth0
vnstat -i br-lan

# Непрерывный мониторинг
vnstat -l -i eth0
```

### Нагрузка системы
```bash
# OpenWRT / Linux
top
htop  # если установлен

# Использование памяти
free -h

# Использование диска
df -h

# Сетевые соединения
netstat -tulpn
ss -tulpn
```

## Backup

### OpenWRT
```bash
# Создать backup
sysupgrade -b /tmp/backup-$(date +%Y%m%d).tar.gz

# Скачать backup
scp root@192.168.20.1:/tmp/backup-*.tar.gz ./

# Восстановить backup
scp backup-20250101.tar.gz root@192.168.20.1:/tmp/
ssh root@192.168.20.1
sysupgrade -r /tmp/backup-20250101.tar.gz
```

### OPNsense
```bash
# Через Web UI:
# System → Configuration → Backups → Download configuration

# Восстановление:
# System → Configuration → Backups → Restore configuration
```

### Proxmox
```bash
# Backup VM
vzdump 100 --mode snapshot --storage local

# Backup LXC
vzdump 200 --mode snapshot --storage local

# Список backups
ls -lh /var/lib/vz/dump/
```

## Обновления

### OpenWRT
```bash
# Обновить список пакетов
opkg update

# Показать обновления
opkg list-upgradable

# Обновить конкретный пакет
opkg upgrade wireguard-tools

# Обновить все пакеты
opkg upgrade $(opkg list-upgradable | awk '{print $1}')

# Обновление прошивки (осторожно!)
sysupgrade -v /tmp/openwrt-*.bin
```

### OPNsense
```bash
# Через Web UI:
# System → Firmware → Updates → Check for updates

# Через SSH
opnsense-update -c  # Check for updates
opnsense-update     # Install updates
```

### Proxmox
```bash
# Обновить список пакетов
apt update

# Показать обновления
apt list --upgradable

# Установить обновления
apt upgrade

# Обновление Proxmox (осторожно!)
apt dist-upgrade
```

### AdGuard Home
```bash
# Через Web UI:
# Settings → General settings → Update channel → Check for updates

# Или вручную:
wget https://static.adguard.com/adguardhome/release/AdGuardHome_linux_arm64.tar.gz
tar -xvf AdGuardHome_linux_arm64.tar.gz
./AdGuardHome/AdGuardHome -s stop
cp AdGuardHome/AdGuardHome /usr/bin/AdGuardHome
/etc/init.d/AdGuardHome start
```

## Безопасность

### Изменить пароли
```bash
# OpenWRT
passwd

# Proxmox (root)
passwd

# OPNsense - через Web UI
# System → Access → Users → Edit

# Изменить WiFi пароль
vi /etc/config/wireless
# Найти option key и изменить
wifi reload
```

### Проверка открытых портов
```bash
# Сканирование с внешнего хоста
nmap -sV YOUR_PUBLIC_IP

# Локально
netstat -tulpn
ss -tulpn

# Только listening порты
netstat -tln
```

### Логи безопасности
```bash
# OpenWRT - firewall drops
logread | grep -i "drop"
logread | grep -i "reject"

# OPNsense
tail -f /var/log/filter.log | grep -i "block"

# Failed SSH attempts
logread | grep -i "failed password"
```

## Полезные алиасы (добавить в ~/.profile)

```bash
# На OpenWRT
alias ll='ls -lah'
alias logs='logread -f'
alias wgs='wg show'
alias mode='cat /etc/openwrt-mode'
alias vpncheck='/usr/bin/openwrt-vpn-failover.sh'
alias wificlients='iw dev wlan0 station dump && iw dev wlan1 station dump'
```

## Emergency Recovery

### OpenWRT не загружается
```bash
# Failsafe mode при загрузке
# Нажимать кнопку reset или быстро нажимать Enter в serial console

# Войти в failsafe
telnet 192.168.1.1

# Примонтировать filesystem
mount_root

# Восстановить конфигурацию
cp /rom/etc/config/* /etc/config/
reboot
```

### Забыт пароль OpenWRT
```bash
# Войти в failsafe mode
# Сбросить пароль
passwd root

# Или полный reset
firstboot
reboot
```

### OPNsense не доступен
```bash
# Подключиться через Proxmox console
qm terminal 100

# Войти как root
# Выбрать: Reset root password (опция 8)

# Или сбросить конфигурацию
# Выбрать: Factory reset (опция 4)
```

### Proxmox недоступен
```bash
# Подключиться через физическую консоль или IPMI
# Проверить сеть
ip addr show

# Перезапустить сетевые службы
systemctl restart networking

# Проверить Proxmox службы
systemctl status pve-cluster
systemctl status pvedaemon
systemctl status pveproxy
```

## GL.iNet GL-AXT1800 специфичные команды

### Доступ к интерфейсам

**GL.iNet UI и OpenWRT LuCI работают параллельно - используйте оба!**

```bash
# GL.iNet Web UI - удобный интерфейс для повседневных задач
http://192.168.20.1
# Логин: root / пароль который вы установили

# Используйте GL.iNet UI для:
# - Изменения WiFi настроек
# - Включения/отключения VPN
# - Просмотра графиков трафика
# - Быстрой настройки firewall
# - One-click функций (AdGuard, VPN клиент, Repeater)

# OpenWRT LuCI - расширенный контроль
http://192.168.20.1:81
# Те же логин/пароль

# Используйте LuCI для:
# - Редактирования /etc/config/* файлов
# - Установки пакетов через opkg
# - Применения наших конфигураций
# - Детальной настройки сети и firewall
# - SSH ключи, cron задачи, advanced settings
```

**Совет:** Начинайте с GL.iNet UI, переходите в LuCI когда нужны расширенные настройки.

### Проверка портов DSA
```bash
# Показать все DSA порты
ip link show | grep -E "wan|lan[1-4]"

# Статус портов
cat /sys/class/net/wan/operstate
cat /sys/class/net/lan1/operstate
cat /sys/class/net/lan2/operstate
cat /sys/class/net/lan3/operstate
cat /sys/class/net/lan4/operstate

# Проверить bridge
bridge link show
```

### WiFi 6 настройки
```bash
# Проверить поддержку WiFi 6
iw list | grep -A 10 "HE cap"

# Показать WiFi статус с HE (802.11ax)
iw dev wlan0 info
iw dev wlan1 info

# Подключенные WiFi 6 клиенты
iw dev wlan0 station dump | grep -E "Station|rx bitrate|tx bitrate"
```

### GL.iNet службы
```bash
# Статус GL.iNet UI
/etc/init.d/gl_ui status

# Перезапустить GL.iNet UI (если нужно)
/etc/init.d/gl_ui restart

# Статус GL.iNet WAN monitor
/etc/init.d/gl-tertf status

# Примечание: GL.iNet UI и OpenWRT LuCI работают параллельно
# GL.iNet UI: http://192.168.20.1
# LuCI:       http://192.168.20.1:81
# Используйте оба для разных задач!
```

### Информация о системе
```bash
# Модель устройства
cat /tmp/sysinfo/model
# Вывод: GL.iNet GL-AXT1800

# Версия прошивки GL.iNet
cat /etc/glversion

# OpenWRT release
cat /etc/openwrt_release

# Температура (если доступна)
cat /sys/class/thermal/thermal_zone0/temp
```

### LED управление
```bash
# Показать доступные LED
ls /sys/class/leds/

# Примеры (зависят от версии прошивки)
echo 1 > /sys/class/leds/blue:power/brightness
echo 0 > /sys/class/leds/blue:power/brightness
```

### Hardware offloading (производительность)
```bash
# Проверить статус flow offloading
uci show firewall.@defaults[0].flow_offloading
uci show firewall.@defaults[0].flow_offloading_hw

# Включить (если отключено)
uci set firewall.@defaults[0].flow_offloading='1'
uci set firewall.@defaults[0].flow_offloading_hw='1'
uci commit firewall
/etc/init.d/firewall restart
```

### Производительность тест
```bash
# Установить iperf3
opkg update && opkg install iperf3

# Сервер на GL-AXT1800
iperf3 -s

# Клиент (с другого устройства)
iperf3 -c 192.168.20.1
```

### Reset и recovery
```bash
# Программный сброс (через SSH)
firstboot && reboot

# Для U-Boot recovery:
# 1. Выключить роутер
# 2. Зажать Reset, включить питание
# 3. Когда LED мигает - отпустить
# 4. Открыть http://192.168.1.1
# 5. Загрузить прошивку
```

---

**Важно:** Всегда делайте backup перед внесением изменений!

```bash
# Быстрый backup всех конфигов
cd ~
mkdir backup-$(date +%Y%m%d)
# Скопировать файлы конфигурации в backup директорию

# Backup GL-AXT1800 (создает .tar.gz)
sysupgrade -b /tmp/backup-$(date +%Y%m%d).tar.gz
scp root@192.168.20.1:/tmp/backup-*.tar.gz ./
```

## Дополнительные ресурсы

- 📖 См. `GL-AXT1800-NOTES.md` для подробной информации о GL-AXT1800
- 📖 См. `README.md` для полной документации
- 📖 См. `NETWORK-DIAGRAM.txt` для визуализации сети
