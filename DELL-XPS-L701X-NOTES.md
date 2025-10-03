# Dell XPS L701X - Proxmox конфигурация

## Характеристики оборудования

**Модель:** Dell XPS L701X (Studio XPS 17)
**CPU:** Intel Core i5/i7 (1st gen, 2 ядра + HT = 4 потока)
**RAM:** 8 GB DDR3
**Дисплей:** 17.3" (удобно для локального управления)

### Накопители

**SSD:** 250 GB (быстрый)
- Использование: Proxmox система + VM/LXC которым нужна скорость

**HDD:** 500 GB (медленный)
- Использование: Backup, ISO образы, архив

### Сеть

**Встроенный Ethernet:** 1x Gigabit Ethernet (Broadcom/Intel)
- Использование: **LAN** → к OpenWRT

**USB-Ethernet адаптер:** 1x Gigabit Ethernet (USB 2.0/3.0)
- Использование: **WAN** → к ISP Router
- ⚠️ Особенность: может иметь проблемы со стабильностью

### Ограничения

⚠️ **RAM 8GB** - ограниченный ресурс для:
- Proxmox (512 MB)
- OPNsense VM (2-4 GB)
- LXC контейнеры (оставшееся)

⚠️ **USB-Ethernet** - может иметь:
- Меньшую производительность (особенно USB 2.0)
- Проблемы со стабильностью при нагрузке
- Необходимость правильных драйверов

⚠️ **Старый CPU** - первое поколение Core i5/i7:
- Поддержка виртуализации (VT-x) есть
- Производительность ниже современных CPU

## Оптимальная конфигурация Proxmox

### 1. Разделение дисков

#### SSD 250 GB (быстрый) - /dev/sda

```
Раздел                  Размер    Назначение
/dev/sda1 (EFI)         1 GB      Boot partition
/dev/sda2 (ext4)        30 GB     Proxmox root (/)
/dev/sda3 (LVM)         219 GB    VM и критичные LXC

LVM на /dev/sda3:
  - pve/root            8 GB      Proxmox система
  - pve/swap            8 GB      Swap (1x RAM)
  - pve/data            ~203 GB   Thin pool для VM/LXC
```

**Что хранить на SSD:**
- ✅ OPNsense VM (главный firewall - нужна скорость)
- ✅ AdGuard LXC (если отдельный контейнер)
- ✅ Database LXC (PostgreSQL, Redis)
- ✅ Критичные сервисы

#### HDD 500 GB (медленный) - /dev/sdb

```
/dev/sdb1 (ext4)        500 GB    local-hdd (directory)
```

**Что хранить на HDD:**
- ✅ ISO образы (Proxmox templates)
- ✅ Backup VM и LXC
- ✅ LXC контейнеры с файлами (Nextcloud, Gitea)
- ✅ Media storage
- ✅ Архив и логи

### 2. Storage конфигурация в Proxmox

```bash
# Список storage
pvesm status

# Добавить HDD как directory storage
pvesm add dir local-hdd --path /mnt/hdd --content backup,iso,vztmpl,rootdir

# Создать mount point для HDD
mkdir -p /mnt/hdd
echo "/dev/sdb1 /mnt/hdd ext4 defaults 0 2" >> /etc/fstab
mount -a
```

**Итоговые storage:**

| Storage | Тип | Устройство | Содержимое |
|---------|-----|------------|------------|
| local | dir | SSD | Proxmox config |
| local-lvm | lvmthin | SSD | VM disks (fast) |
| local-hdd | dir | HDD | ISO, backup, templates |
| local-hdd-lxc | dir | HDD | LXC containers (slow) |

### 3. Сетевые интерфейсы

**Определение интерфейсов:**

```bash
# Показать все сетевые интерфейсы
ip link show

# Встроенный Ethernet (обычно)
enp9s0 или eth0 или eno1

# USB-Ethernet (может меняться!)
enx001122334455 или eth1 или usb0
```

⚠️ **Проблема:** USB-Ethernet может менять имя при переподключении!

**Решение:** Использовать udev rules для фиксации имени

#### Создание стабильного имени для USB-Ethernet

```bash
# 1. Найти MAC адрес USB-Ethernet
ip link show | grep -A 1 "usb\|enx"

# Пример вывода:
# 4: enxe86a64d3f1a2: <BROADCAST,MULTICAST,UP,LOWER_UP>
#    link/ether e8:6a:64:d3:f1:a2

# 2. Создать udev rule
cat > /etc/udev/rules.d/70-persistent-net.rules <<EOF
# Встроенный Ethernet
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="XX:XX:XX:XX:XX:XX", NAME="eth-builtin"

# USB-Ethernet адаптер
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="e8:6a:64:d3:f1:a2", NAME="eth-usb"
EOF

# Замените MAC адреса на ваши!

# 3. Применить правила
udevadm control --reload-rules
udevadm trigger
```

#### Конфигурация /etc/network/interfaces для Dell XPS

```bash
# Loopback
auto lo
iface lo inet loopback

# ============================================================
# Встроенный Ethernet - LAN (к OpenWRT)
# ============================================================
auto eth-builtin
iface eth-builtin inet manual

# ============================================================
# USB-Ethernet адаптер - WAN (к ISP Router)
# ============================================================
auto eth-usb
iface eth-usb inet manual

# ============================================================
# WAN Bridge - к ISP Router (через USB-Ethernet)
# ============================================================
auto vmbr0
iface vmbr0 inet manual
    bridge-ports eth-usb
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094
    comment WAN - to ISP Router via USB-Ethernet

# ============================================================
# LAN Bridge - к OpenWRT WAN (встроенный Ethernet)
# ============================================================
auto vmbr1
iface vmbr1 inet manual
    bridge-ports eth-builtin
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094
    comment LAN - to OpenWRT via built-in Ethernet

# ============================================================
# Internal Bridge - для LXC контейнеров
# ============================================================
auto vmbr2
iface vmbr2 inet static
    address 10.0.30.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    comment Internal - LXC containers

# ============================================================
# Management Bridge - для emergency доступа
# ============================================================
auto vmbr99
iface vmbr99 inet static
    address 10.0.99.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    comment Management - emergency access
```

### 4. Оптимизация для 8GB RAM

#### Распределение памяти

```
Proxmox host:        1 GB  (резерв системы)
OPNsense VM:         2 GB  (минимум для firewall)
AdGuard (опция 1):   512 MB (если в LXC)
AdGuard (опция 2):   встроен в OpenWRT (экономия RAM)
LXC контейнеры:      4-5 GB (остаток)
```

**Рекомендация:** Запускать AdGuard на OpenWRT, а не в отдельном LXC!

#### OPNsense VM оптимизация

```bash
# Создание OPNsense VM с минимальными ресурсами
qm create 100 \
  --name OPNsense \
  --memory 2048 \
  --cores 2 \
  --cpu host \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:32 \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr1 \
  --net2 virtio,bridge=vmbr2 \
  --net3 virtio,bridge=vmbr99 \
  --boot order=scsi0 \
  --onboot 1 \
  --startup order=1
```

#### LXC контейнеры - рекомендуемые размеры

**На SSD (fast storage):**
```
PostgreSQL:     512 MB RAM, 8 GB disk
Redis:          256 MB RAM, 2 GB disk
AdGuard (опц):  512 MB RAM, 4 GB disk
```

**На HDD (slow storage):**
```
Nextcloud:      1 GB RAM, 20 GB disk
Gitea:          512 MB RAM, 10 GB disk
Media server:   1 GB RAM, 100+ GB disk
Backup tools:   256 MB RAM, 50 GB disk
```

**Пример создания LXC на HDD:**
```bash
pct create 201 local-hdd:vztmpl/debian-12-standard_12.0-1_amd64.tar.zst \
  --hostname nextcloud \
  --memory 1024 \
  --swap 512 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr2,ip=10.0.30.30/24,gw=10.0.30.1 \
  --nameserver 192.168.10.2 \
  --storage local-hdd \
  --rootfs local-hdd:20 \
  --unprivileged 1 \
  --onboot 1
```

#### Включить Swap и KSM (экономия RAM)

```bash
# Проверить swap
free -h

# KSM (Kernel Samepage Merging) - дедупликация памяти
echo 1 > /sys/kernel/mm/ksm/run

# Автозапуск KSM
cat > /etc/systemd/system/ksm.service <<EOF
[Unit]
Description=Enable Kernel Same-page Merging
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo 1 > /sys/kernel/mm/ksm/run'
ExecStart=/bin/sh -c 'echo 1000 > /sys/kernel/mm/ksm/pages_to_scan'

[Install]
WantedBy=multi-user.target
EOF

systemctl enable ksm
systemctl start ksm

# Проверить KSM
cat /sys/kernel/mm/ksm/pages_sharing
```

### 5. USB-Ethernet стабильность

#### Проверка USB-Ethernet адаптера

```bash
# Показать USB устройства
lsusb

# Детальная информация
lsusb -v | grep -A 20 "Ethernet"

# Проверить драйвер
ethtool -i eth-usb

# Скорость и статус
ethtool eth-usb
```

#### Известные проблемы и решения

**Проблема 1: Адаптер отключается под нагрузкой**

```bash
# Отключить USB autosuspend для Ethernet адаптера
echo 'on' > /sys/bus/usb/devices/*/power/control

# Постоянно (добавить в /etc/rc.local)
cat >> /etc/rc.local <<EOF
# Disable USB autosuspend for Ethernet
for i in /sys/bus/usb/devices/*/power/control; do
  echo on > \$i
done
EOF

chmod +x /etc/rc.local
```

**Проблема 2: Низкая производительность**

```bash
# Проверить, подключен ли к USB 3.0
lsusb -t

# Если USB 2.0 - максимум ~480 Mbps (реально ~300 Mbps)
# Рекомендация: использовать USB 3.0 порт если доступен

# Включить offloading (если поддерживается)
ethtool -K eth-usb rx on tx on gso on tso on gro on
```

**Проблема 3: Интерфейс исчезает после перезагрузки**

```bash
# Решение: udev rules (см. выше)
# Или использовать MAC-based naming в Proxmox
```

### 6. Рекомендуемая конфигурация VM/LXC

#### Минимальная (экономия RAM):

```
Proxmox:        512 MB (system reserved)
OPNsense:       2 GB
AdGuard:        на OpenWRT (0 MB на Proxmox)
PostgreSQL:     512 MB
Redis:          256 MB
Nextcloud:      1 GB
Gitea:          512 MB
─────────────────────────
TOTAL:          ~4.7 GB
Свободно:       ~3.3 GB
```

#### Оптимальная (баланс):

```
Proxmox:        1 GB
OPNsense:       2 GB
PostgreSQL:     512 MB
Redis:          256 MB
Nextcloud:      1 GB
─────────────────────────
TOTAL:          ~4.7 GB
Свободно:       ~3.3 GB для доп. сервисов
```

### 7. Мониторинг ресурсов

```bash
# Использование RAM
free -h
pvesh get /nodes/localhost/status

# Использование дисков
df -h
pvesm status

# Загрузка CPU
top
htop  # если установлен

# Температура (если доступна)
sensors  # установить: apt install lm-sensors

# Статус VM и LXC
qm list
pct list

# Использование памяти по VM/LXC
for i in $(qm list | awk '{if(NR>1) print $1}'); do
  echo "VM $i: $(qm status $i | grep mem)";
done

for i in $(pct list | awk '{if(NR>1) print $1}'); do
  echo "CT $i: $(pct status $i)";
done
```

## Проблемы и решения

### Proxmox медленно работает

**Причины:**
- Swap активно используется (недостаток RAM)
- VM/LXC на медленном HDD

**Решения:**
```bash
# 1. Включить KSM (см. выше)

# 2. Уменьшить память VM/LXC
qm set 100 --memory 2048

# 3. Переместить критичные VM на SSD
qm migrate 100 --targetstorage local-lvm
```

### USB-Ethernet не стабилен

**Решения:**
```bash
# 1. Отключить power management
echo on > /sys/bus/usb/devices/.../power/control

# 2. Использовать другой USB порт (желательно USB 3.0)

# 3. Обновить драйвер (если возможно)
apt update && apt upgrade

# 4. Альтернатива: PCIe Ethernet адаптер через ExpressCard (если есть слот)
```

### Недостаточно места на SSD

**Решения:**
```bash
# 1. Удалить старые snapshot и backup
pvesm list local
pvesm list local-lvm

# 2. Переместить большие LXC на HDD
pct move-volume 200 rootfs local-hdd

# 3. Очистка apt cache
apt clean
```

## Бенчмарки производительности

### Диски

```bash
# SSD speed test
dd if=/dev/zero of=/tmp/test bs=1M count=1000 oflag=direct
# Ожидаемо: ~200-400 MB/s (SATA II/III)

# HDD speed test
dd if=/dev/zero of=/mnt/hdd/test bs=1M count=1000 oflag=direct
# Ожидаемо: ~80-120 MB/s

# Очистка
rm /tmp/test /mnt/hdd/test
```

### Сеть

```bash
# Между Proxmox и OpenWRT
apt install iperf3

# На Proxmox (сервер)
iperf3 -s

# На OpenWRT (клиент)
opkg install iperf3
iperf3 -c 192.168.10.1

# USB-Ethernet ожидаемо:
# USB 2.0: ~300 Mbps
# USB 3.0: ~900 Mbps
```

## Рекомендации

✅ **ДЕЛАТЬ:**
- Использовать SSD для OPNsense VM (критично)
- Использовать HDD для бэкапов и больших файлов
- Включить KSM для экономии памяти
- Мониторить температуру лаптопа
- Настроить автоматические backup на HDD
- Использовать USB 3.0 порт для Ethernet адаптера

❌ **НЕ ДЕЛАТЬ:**
- Запускать много тяжелых VM одновременно
- Хранить ISO и backup на SSD (тратить место)
- Использовать swap на HDD (очень медленно)
- Закрывать крышку лаптопа (перегрев)
- Использовать WiFi как основной интерфейс

## Охлаждение и питание

### Охлаждение

```bash
# Установить lm-sensors
apt install lm-sensors
sensors-detect

# Мониторинг температуры
watch -n 2 sensors

# Если перегрев:
# 1. Очистить вентиляционные отверстия
# 2. Заменить термопасту
# 3. Использовать подставку для лаптопа
# 4. Уменьить нагрузку (меньше VM/LXC)
```

### Питание

⚠️ **Важно:** Лаптоп должен быть постоянно подключен к сети!

```bash
# Настроить поведение при закрытии крышки
nano /etc/systemd/logind.conf

# Изменить:
HandleLidSwitch=ignore
HandleLidSwitchDocked=ignore

# Применить
systemctl restart systemd-logind
```

## Альтернативные варианты

Если 8GB RAM недостаточно:

1. **Upgrade RAM** до 16GB (проверить совместимость)
2. **Использовать external server** для тяжелых сервисов
3. **Урезать количество** запущенных LXC
4. **Oracle Cloud** для части сервисов (Always Free tier)

## Полезные ссылки

- [Dell XPS L701X спецификации](https://www.dell.com/support/home/product-support/product/studio-xps-17-l701x)
- [Proxmox минимальные требования](https://www.proxmox.com/en/proxmox-ve/requirements)
- [USB Ethernet adapter compatibility](https://www.linux-usb.org/usb.ids)

---

**Вывод:** Dell XPS L701X подходит для home lab, но с учетом ограничений по RAM и использованием USB-Ethernet. Оптимизация необходима!
