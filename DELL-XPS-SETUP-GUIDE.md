# Dell XPS L701X - Пошаговая установка Proxmox

Краткое руководство по установке и настройке Proxmox на Dell XPS L701X для использования в home lab.

## Предварительные требования

### Оборудование
- ✅ Dell XPS L701X (Studio XPS 17)
- ✅ 8 GB RAM (минимум)
- ✅ SSD 250 GB установлен
- ✅ HDD 500 GB установлен
- ✅ USB-Ethernet адаптер (Gigabit)
- ✅ USB флешка 8GB+ (для установки Proxmox)

### Подключения
- ✅ Встроенный Ethernet → будет использоваться для LAN
- ✅ USB-Ethernet адаптер → будет использоваться для WAN
- ✅ Лаптоп подключен к питанию (постоянно!)

## Шаг 1: Подготовка установочной флешки

### На другом компьютере:

```bash
# Скачать Proxmox VE ISO
# https://www.proxmox.com/en/downloads/category/iso-images-pve

# Создать загрузочную флешку (Linux/Mac)
sudo dd if=proxmox-ve_*.iso of=/dev/sdX bs=1M status=progress
# Замените /dev/sdX на вашу флешку!

# Или используйте Rufus/Etcher на Windows
```

## Шаг 2: Установка Proxmox VE

### BIOS настройки Dell XPS L701X

1. Включите лаптоп и нажмите **F2** для входа в BIOS
2. Настройки:
   - **Virtualization**: Enabled (Intel VT-x)
   - **VT-d**: Enabled (если доступно)
   - **Boot Mode**: UEFI
   - **Secure Boot**: Disabled
   - **Boot Order**: USBFirst, затем SSD

### Установка Proxmox

1. Загрузитесь с USB флешки
2. Выберите **Install Proxmox VE**
3. **Target Harddisk**: Выберите **SSD 250GB** (/dev/sda)
   - ⚠️ **Важно:** Убедитесь что выбран SSD, а не HDD!
4. Настройки диска:
   - Filesystem: **ext4** или **ZFS (RAID0)** если хотите snapshot
   - hdsize: **оставьте по умолчанию** (использует весь диск)

5. **Country, Time zone, Keyboard**: выберите ваши настройки
6. **Password**: установите **надёжный пароль** для root
7. **Email**: ваш email (для уведомлений)
8. **Network Configuration**:
   - **Management Interface**: Выберите **встроенный Ethernet**
     - Обычно `eno1`, `enp9s0`, или `eth0`
   - **Hostname (FQDN)**: `proxmox.home.lan`
   - **IP Address**: `192.168.1.100/24` (временный, изменим позже)
   - **Gateway**: `192.168.1.1` (ваш роутер)
   - **DNS Server**: `8.8.8.8`

9. Нажмите **Install** и дождитесь окончания
10. После установки: **Reboot** и **извлеките флешку**

## Шаг 3: Первичная настройка Proxmox

### Подключение к Proxmox Web UI

1. Подключите лаптоп к вашей сети через встроенный Ethernet
2. На другом компьютере откройте браузер:
   ```
   https://192.168.1.100:8006
   ```
3. Примите self-signed сертификат
4. Логин: `root`
5. Пароль: тот что установили при установке

### Базовая настройка

#### 1. Отключить Enterprise репозиторий

```bash
# SSH в Proxmox
ssh root@192.168.1.100

# Отключить enterprise repo
rm /etc/apt/sources.list.d/pve-enterprise.list

# Добавить no-subscription repo
echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list

# Обновить систему
apt update && apt upgrade -y
```

#### 2. Определить сетевые интерфейсы

```bash
# Показать все интерфейсы
ip link show

# Пример вывода:
# 1: lo: ...
# 2: eno1: ... (встроенный Ethernet)
# 3: enx001122334455: ... (USB-Ethernet)

# Запишите имена:
# Встроенный: eno1 (или enp9s0, eth0)
# USB-Ethernet: enx001122334455 (или eth1)
```

#### 3. Создать udev rules для USB-Ethernet

```bash
# Найти MAC адрес USB-Ethernet
ip link show | grep -A 1 "enx\|usb"
# Пример: link/ether e8:6a:64:d3:f1:a2

# Создать udev rule
cat > /etc/udev/rules.d/70-persistent-net.rules <<'EOF'
# Встроенный Ethernet (замените MAC на ваш)
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="aa:bb:cc:dd:ee:ff", NAME="eth-builtin"

# USB-Ethernet адаптер (замените MAC на ваш)
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="e8:6a:64:d3:f1:a2", NAME="eth-usb"
EOF

# Применить правила
udevadm control --reload-rules
udevadm trigger

# Проверить (может потребоваться reboot)
ip link show
```

#### 4. Настроить сеть согласно конфигурации

```bash
# Скопировать конфигурацию из репозитория
nano /etc/network/interfaces

# Вставить содержимое из файла proxmox-network-interfaces
# Замените eth-builtin и eth-usb на реальные имена если нужно

# После изменения:
ifreload -a

# Или перезагрузитесь
reboot
```

## Шаг 4: Настройка storage

### Добавить HDD для backup и ISO

```bash
# Найти HDD
lsblk

# Должно быть примерно так:
# sda  250GB  (SSD - уже используется Proxmox)
# sdb  500GB  (HDD - нужно настроить)

# Создать раздел на HDD
fdisk /dev/sdb
# n (new partition)
# p (primary)
# 1 (partition number)
# Enter (first sector - default)
# Enter (last sector - default)
# w (write)

# Создать filesystem
mkfs.ext4 /dev/sdb1

# Создать mount point
mkdir -p /mnt/hdd

# Добавить в fstab
echo "/dev/sdb1 /mnt/hdd ext4 defaults 0 2" >> /etc/fstab

# Смонтировать
mount -a

# Проверить
df -h | grep hdd
```

### Добавить storage в Proxmox

```bash
# Через CLI
pvesm add dir local-hdd --path /mnt/hdd --content backup,iso,vztmpl,rootdir

# Или через Web UI:
# Datacenter → Storage → Add → Directory
# ID: local-hdd
# Directory: /mnt/hdd
# Content: Disk image, ISO image, Container template, VZDump backup file
```

## Шаг 5: Оптимизация для 8GB RAM

### Включить KSM (экономия памяти)

```bash
cat > /etc/systemd/system/ksm.service <<'EOF'
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

# Проверить
cat /sys/kernel/mm/ksm/pages_sharing
```

### Отключить USB autosuspend (для стабильности USB-Ethernet)

```bash
# Создать скрипт
cat > /etc/rc.local <<'EOF'
#!/bin/sh -e
# Disable USB autosuspend
for i in /sys/bus/usb/devices/*/power/control; do
  echo on > $i
done
exit 0
EOF

chmod +x /etc/rc.local

# Запустить сейчас
bash /etc/rc.local
```

### Настроить поведение при закрытии крышки

```bash
nano /etc/systemd/logind.conf

# Изменить:
HandleLidSwitch=ignore
HandleLidSwitchDocked=ignore

# Применить
systemctl restart systemd-logind
```

## Шаг 6: Создание OPNsense VM

### Скачать OPNsense ISO

```bash
# В Proxmox Web UI:
# Datacenter → Storage → local → ISO Images → Download from URL
# URL: https://mirror.ams1.nl.leaseweb.net/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2

# Или через SSH:
cd /var/lib/vz/template/iso/
wget https://mirror.ams1.nl.leaseweb.net/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2
bunzip2 OPNsense-*.iso.bz2
```

### Создать VM через CLI

```bash
qm create 100 \
  --name OPNsense \
  --memory 2048 \
  --cores 2 \
  --cpu host \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:32 \
  --ide2 local:iso/OPNsense-24.7-dvd-amd64.iso,media=cdrom \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr1 \
  --net2 virtio,bridge=vmbr2 \
  --net3 virtio,bridge=vmbr99 \
  --boot order=scsi0 \
  --onboot 1 \
  --startup order=1

# Запустить VM
qm start 100
```

### Установить OPNsense

1. В Proxmox Web UI: VM 100 → Console
2. Следовать инструкциям установки OPNsense
3. После установки: настроить согласно `opnsense-interfaces-config.txt`

## Шаг 7: Проверка

### Тест сети

```bash
# На Proxmox host
ping 192.168.10.1  # OPNsense LAN (после настройки OPNsense)
ping 8.8.8.8       # Internet через OPNsense

# Проверить bridges
brctl show

# Статус VM
qm list
```

### Тест памяти

```bash
free -h
# Должно показать ~8GB total

# KSM статус
cat /sys/kernel/mm/ksm/pages_sharing
# Если > 0, то KSM работает
```

### Тест дисков

```bash
df -h
# Должны видеть:
# /dev/mapper/pve-root (SSD)
# /mnt/hdd (HDD)

pvesm status
# Должны видеть:
# local, local-lvm (SSD)
# local-hdd (HDD)
```

## Следующие шаги

1. ✅ Настроить OPNsense согласно `opnsense-interfaces-config.txt`
2. ✅ Настроить OpenWRT согласно конфигурации
3. ✅ Создать LXC контейнеры на подходящем storage
4. ✅ Настроить backup на HDD

## Troubleshooting

### USB-Ethernet не работает

```bash
# Проверить подключен ли адаптер
lsusb | grep -i ethernet

# Проверить драйвер
ethtool -i eth-usb

# Проверить link
ethtool eth-usb | grep "Link detected"

# Если проблемы - попробовать другой USB порт (желательно USB 3.0)
```

### Proxmox медленный

```bash
# Проверить swap usage
free -h

# Если swap активно используется:
# 1. Уменьшить память VM/LXC
# 2. Убедиться что KSM включен
# 3. Не запускать слишком много VM одновременно
```

### Перегрев

```bash
# Установить мониторинг
apt install lm-sensors
sensors-detect  # Ответить Yes на все

# Мониторить температуру
watch -n 2 sensors

# Если перегрев:
# 1. Очистить вентиляцию
# 2. Заменить термопасту
# 3. Использовать подставку для лаптопа
# 4. Уменьшить нагрузку
```

## Полезные ссылки

- 📖 `DELL-XPS-L701X-NOTES.md` - Полное руководство по оптимизации
- 📖 `README.md` - Общая документация проекта
- 📖 `QUICK-REFERENCE.md` - Быстрые команды
- [Proxmox VE документация](https://pve.proxmox.com/pve-docs/)
- [OPNsense документация](https://docs.opnsense.org/)

---

**Готово!** Теперь у вас есть работающий Proxmox на Dell XPS L701X 🚀
