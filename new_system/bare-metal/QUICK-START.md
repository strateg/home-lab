# Quick Start - Proxmox Auto-Install USB

Краткая шпаргалка для создания автоматической установки Proxmox.

## TL;DR

```bash
# 1. Установить утилиту (один раз)
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg
echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  sudo tee /etc/apt/sources.list.d/pve-install-repo.list
sudo apt update && sudo apt install proxmox-auto-install-assistant

# 2. Создать USB
cd new_system/bare-metal
sudo ./create-usb.sh /dev/sdX proxmox-ve_9.0-1.iso

# 3. Загрузиться с USB (F12 → UEFI: USB)
# 4. Ждать 10 секунд → Автоматическая установка!
```

## Установка утилиты (Debian/Ubuntu)

```bash
# Добавить репозиторий Proxmox
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  sudo tee /etc/apt/sources.list.d/pve-install-repo.list

# Установить
sudo apt update
sudo apt install proxmox-auto-install-assistant

# Проверить
proxmox-auto-install-assistant --version
```

## Смена пароля в answer.toml

```bash
# Сгенерировать хэш
openssl passwd -6 "YourPassword"

# Или
mkpasswd -m sha-512 "YourPassword"

# Вставить в answer.toml
vim answer.toml
# Найти: root_password = "..."
# Заменить на: root_password = "$6$rounds=..."
```

## Определение USB устройства

```bash
# Показать все диски
lsblk

# Пример вывода:
# sda    232.9G  ← SSD (НЕ ТРОГАТЬ!)
# sdb      7.5G  ← USB накопитель (ИСПОЛЬЗОВАТЬ)

# USB устройство = /dev/sdb (в этом примере)
```

## Создание USB

```bash
cd new_system/bare-metal

# Если ISO скачан
sudo ./create-usb.sh /dev/sdb /path/to/proxmox-ve_9.0-1.iso

# Если ISO нужно скачать
sudo ./create-usb.sh /dev/sdb proxmox.iso
# → Скрипт предложит скачать
```

## Загрузка и установка (Dell XPS L701X)

```
1. Подключить внешний монитор → Mini DisplayPort
2. Включить монитор
3. Вставить USB
4. Включить ноутбук
5. F12 → Boot Menu
6. Выбрать: "UEFI: USB..." (НЕ "USB Storage Device")
7. Ждать 10 секунд
8. ☕ Кофе (10-15 мин)
9. Перезагрузка автоматически
```

## После установки

### Найти IP адрес

```bash
# Вариант 1: DHCP leases на роутере
# Вариант 2: Подключить монитор
ip a | grep "inet "
```

### SSH подключение

```bash
ssh root@<ip-address>
# Пароль: из answer.toml
```

### Web UI

```
https://<ip-address>:8006
User: root
Password: из answer.toml
```

## Post-Install (Автоматизация)

```bash
# 1. Скопировать скрипты
scp -r new_system/bare-metal/post-install/ root@<ip>:/root/

# 2. SSH
ssh root@<ip>

# 3. Запустить setup
cd /root/post-install
./01-install-terraform.sh
./02-install-ansible.sh
./03-configure-storage.sh
./04-configure-network.sh
./05-init-git-repo.sh
reboot

# 4. После reboot
ssh root@10.0.99.1  # Новый IP
cd /root/home-lab/new_system

# 5. Развернуть инфраструктуру
python3 scripts/generate-terraform.py
cd terraform && terraform init && terraform apply

cd ..
python3 scripts/generate-ansible-inventory.py
cd ansible && ansible-playbook -i inventory/production/hosts.yml site.yml
```

## Troubleshooting

### `proxmox-auto-install-assistant: command not found`

→ Установите утилиту (см. выше)

### Загружается обычная установка

→ Выбирайте `UEFI: USB...`, а не `USB Storage Device`

### Внешний монитор не работает

→ Включите монитор ДО загрузки ноутбука

### Ошибка валидации answer.toml

```bash
proxmox-auto-install-assistant validate-answer answer.toml
# Покажет ошибку
```

## Конфигурация (answer.toml)

```toml
[global]
keyboard = "en-us"
country = "us"
timezone = "UTC"
root_password = "$6$rounds=..."  # ← Изменить!
mailto = "admin@home.local"
fqdn = "gamayun.home.local"

[disk-setup]
filesystem = "ext4"
disk_list = ["sda"]    # ⚠️ Конкретный диск, НЕ "first"!

# LVM configuration
lvm.swapsize = 2       # 2 GB swap
lvm.maxroot = 50       # 50 GB root
lvm.minfree = 10       # 10 GB reserve
lvm.maxvz = 0          # Use all remaining space

[network]
source = "from-dhcp"   # Use DHCP for initial setup
```

## Что происходит при установке

```
1. Boot → GRUB menu
2. "Automated Installation" (10 sec countdown)
3. Чтение answer.toml из ISO
4. Разметка диска:
   - 50 GB → root (ext4)
   - 2 GB → swap
   - ~128 GB → LVM thin pool
5. Установка Proxmox VE
6. Настройка сети (DHCP)
7. Установка пакетов (vim, git, curl, wget, htop, tmux)
8. Отключение enterprise repo
9. Включение no-subscription repo
10. Автоматическая перезагрузка
```

## Полезные команды

```bash
# Проверить утилиту
proxmox-auto-install-assistant --version

# Валидация answer.toml
proxmox-auto-install-assistant validate-answer answer.toml

# Список USB устройств
lsblk -o NAME,SIZE,TYPE,TRAN | grep usb

# Размонтировать USB
sudo umount /dev/sdX*

# Сгенерировать пароль hash
openssl passwd -6

# Проверить ISO
file proxmox-ve_9.0-1.iso
```

## Важные файлы

```
new_system/bare-metal/
├── create-usb.sh              ← Главный скрипт
├── answer.toml                ← Конфигурация (ИЗМЕНИТЬ ПАРОЛЬ!)
├── post-install/              ← Post-install скрипты
│   ├── 01-install-terraform.sh
│   ├── 02-install-ansible.sh
│   ├── 03-configure-storage.sh
│   ├── 04-configure-network.sh
│   └── 05-init-git-repo.sh
├── USB-CREATION-GUIDE.md      ← Полная документация
├── QUICK-START.md             ← Эта шпаргалка
└── CHANGELOG-USB-FIX.md       ← История исправлений
```

## Ссылки

- Официальная документация: https://pve.proxmox.com/wiki/Automated_Installation
- Примеры answer.toml: https://pve.proxmox.com/wiki/Automated_Installation#example_answer_files
- Скачать Proxmox: https://www.proxmox.com/en/downloads/proxmox-virtual-environment/iso

---

**Версия**: 2.0
**Дата**: 2025-10-09
