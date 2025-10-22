# Disk Selection Error Fix

## Проблема

При автоматической установке возникла ошибка:
```
disk in 'disk-selection' not found
```

Установка не могла найти диск для установки системы.

## Причина

В `answer.toml` было указано:
```toml
disk_list = ["first"]  # ❌ НЕ РАБОТАЕТ!
```

Параметр `"first"` **не поддерживается** Proxmox автоматической установкой.

## Решение

Нужно указать **конкретное имя диска**:
```toml
disk_list = ["sda"]  # ✅ РАБОТАЕТ!
```

### Дополнительные изменения

Также изменен формат LVM параметров на официальный стиль:

**Было (НЕ РАБОТАЛО)**:
```toml
[disk-setup.lvm]
hdsize = 50
swapsize = 2
maxroot = 50
minfree = 10
```

**Стало (РАБОТАЕТ)**:
```toml
lvm.swapsize = 2
lvm.maxroot = 50
lvm.minfree = 10
lvm.maxvz = 0
```

## Итоговая конфигурация диска

```toml
[disk-setup]
filesystem = "ext4"

# ⚠️  DISK CONFIGURATION FOR DUAL-DISK SETUP
# SSD (sda): System disk - WILL BE ERASED
# HDD (sdb): Data disk - PRESERVED (not touched)

disk_list = ["sda"]

# LVM configuration
lvm.swapsize = 2      # 2 GB swap
lvm.maxroot = 50      # 50 GB for root
lvm.minfree = 10      # 10 GB reserve
lvm.maxvz = 0         # Use all remaining space for VMs/LXC

# Calculation for 180GB SSD:
# 180 - 2 (swap) - 50 (root) - 10 (minfree) = 118GB for VMs/LXC
```

## Важно: Dual-Disk Setup

У Dell XPS L701X два диска:
- **SSD 180GB** (`/dev/sda`) - для системы и VMs/LXC
- **HDD 500GB** (`/dev/sdb`) - для бэкапов, ISO, шаблонов

### Что происходит при установке

1. ✅ **SSD (`sda`)** - будет **ПОЛНОСТЬЮ СТЁРТ** и отформатирован
   - 2 GB → Swap
   - 50 GB → Root filesystem (Proxmox OS)
   - 10 GB → Reserve (minfree)
   - ~118 GB → LVM thin pool (для VMs/LXC)

2. ✅ **HDD (`sdb`)** - **НЕ ЗАТРАГИВАЕТСЯ** установщиком
   - Сохраняются все существующие данные
   - Будет смонтирован post-install скриптами
   - Используется для:
     - Backups
     - ISO images
     - VM/LXC templates
     - Архивы

## Определение дисков

### Во время установки

Proxmox установщик видит диски как:
- `/dev/sda` - SSD 180GB
- `/dev/sdb` - HDD 500GB

### После установки

Проверить диски:
```bash
lsblk
```

Вывод:
```
NAME                 SIZE TYPE MOUNTPOINT
sda                  180G disk
├─sda1               512M part /boot/efi
├─sda2                50G part /
└─sda3               118G part
  └─pve-data         118G lvm
sdb                  500G disk  (not mounted - for post-install)
```

## Валидация

После исправления:
```bash
proxmox-auto-install-assistant validate-answer answer.toml
```

Результат:
```
The answer file was parsed successfully, no errors found!
```

## Альтернативные варианты disk_list

### ✅ Правильные способы указания диска

```toml
# Вариант 1: По имени устройства (рекомендуется)
disk_list = ["sda"]

# Вариант 2: Полный путь
disk_list = ["/dev/sda"]

# Вариант 3: Несколько дисков (для RAID/ZFS)
disk_list = ["sda", "sdb"]  # Оба диска будут использованы для ZFS mirror
```

### ❌ НЕправильные способы

```toml
# Не работает: магическое значение "first"
disk_list = ["first"]  # ❌

# Не работает: пустой список
disk_list = []  # ❌

# Не работает: без disk_list
# (поле обязательное)  # ❌
```

## Как избежать ошибки

1. **Всегда указывайте конкретный диск**: `["sda"]`
2. **Проверяйте перед созданием USB**:
   ```bash
   proxmox-auto-install-assistant validate-answer answer.toml
   ```
3. **Используйте рабочий пример** из `old_system/proxmox/install/answer.toml`

## Ссылки

- Официальная документация: https://pve.proxmox.com/wiki/Automated_Installation
- Рабочий пример: `old_system/proxmox/install/answer.toml`
- Исправленный файл: `new_system/bare-metal/answer.toml`

---

**Дата исправления**: 2025-10-09
**Статус**: ✅ ИСПРАВЛЕНО И ПРОВЕРЕНО
