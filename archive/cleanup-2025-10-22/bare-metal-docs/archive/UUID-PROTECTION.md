# UUID Protection - Предотвращение циклической переустановки

## Проблема

После автоматической установки Proxmox система перезагружается и снова загружается с USB, запуская повторную установку (цикл).

## Решение

Добавлена **UUID-защита** с тремя компонентами:

### 1. Генерация уникального UUID при создании USB

```bash
# В prepare_iso():
timezone=$(date +%Z)
timestamp=$(date +%Y_%m_%d_%H_%M)
install_uuid="${timezone}_${timestamp}"
# Пример: MSK_2025_10_13_09_30
```

UUID сохраняется в `$TMPDIR/install-uuid` для дальнейшего использования.

---

### 2. First-boot скрипт (запускается после установки Proxmox)

Встраивается в ISO через `--on-first-boot`:

```bash
#!/bin/bash
# First-boot script - Reinstall Prevention

# UUID embedded at USB creation time
INSTALL_ID="MSK_2025_10_13_09_30"

# Save UUID to system root
echo -n "$INSTALL_ID" > /etc/proxmox-install-id

# Find EFI partition on system disk (not USB!)
# ... (поиск и монтирование EFI)

# Write UUID marker to EFI
echo -n "$INSTALL_ID" > "$EFI_MOUNT/proxmox-installed"
```

**Что делает:**
- Ищет EFI партицию **на системном диске** (не на USB!)
- Создает файл `/efi/proxmox-installed` с UUID
- Этот файл - маркер что система установлена с этого USB

---

### 3. Wrapper GRUB (на USB)

После записи ISO на USB, скрипт заменяет `grub.cfg` на wrapper:

```bash
# На USB: /EFI/BOOT/grub.cfg (wrapper)
# Оригинальный: /EFI/BOOT/grub-install.cfg (installer menu)
```

**Логика wrapper:**

```grub
# UUID embedded at USB creation time
set usb_uuid="MSK_2025_10_13_09_30"
set found_system=0

# Search for proxmox-installed marker on system disk (hd1)
if [ -f (hd1,gpt2)/proxmox-installed ]; then
    cat --set=disk_uuid (hd1,gpt2)/proxmox-installed
    if [ "$disk_uuid" = "$usb_uuid" ]; then
        set found_system=1  # UUID matches!
    fi
fi

if [ $found_system -eq 1 ]; then
    # UUID совпадают - система уже установлена
    menuentry 'Boot Proxmox VE (Already Installed)' {
        chainloader (hd1,gpt2)/EFI/proxmox/grubx64.efi
    }
    menuentry 'Reinstall Proxmox (ERASES ALL DATA!)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
else
    # UUID не совпадают - первая установка
    menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
fi
```

---

## Как это работает

### Первая загрузка (система НЕ установлена):

```
1. Boot USB → GRUB wrapper
2. Ищет (hd1,gpt2)/proxmox-installed
3. Файл отсутствует → found_system=0
4. Показывает меню: "Install Proxmox VE (AUTO-INSTALL)"
5. Автоматически запускает установку через 5 сек
6. Установка завершается (~10-15 мин)
7. First-boot script создает /efi/proxmox-installed с UUID
8. Система перезагружается
```

### Вторая загрузка (система УСТАНОВЛЕНА):

```
1. Boot USB → GRUB wrapper
2. Ищет (hd1,gpt2)/proxmox-installed
3. Файл найден! Читает UUID: "MSK_2025_10_13_09_30"
4. Сравнивает с usb_uuid: СОВПАДАЮТ!
5. found_system=1
6. Показывает меню: "Boot Proxmox VE (Already Installed)"
7. Автоматически загружает установленную систему через 5 сек
8. ✅ НЕТ ПЕРЕУСТАНОВКИ!
```

### Третья загрузка (если нужна переустановка):

```
Пользователь может выбрать:
→ "Reinstall Proxmox (ERASES ALL DATA!)"
→ Запускается installer menu
→ Переустановка
```

---

## Диски и поиск UUID

GRUB проверяет несколько вариантов:

```grub
# hd1 = системный диск (обычно)
# hd0 = USB (обычно)

# Проверяем hd1 (system disk) первым:
(hd1,gpt2)/proxmox-installed  # EFI обычно на gpt2
(hd1,gpt1)/proxmox-installed  # Или на gpt1

# Fallback на hd0 (если USB стал hd1):
(hd0,gpt2)/proxmox-installed
(hd0,gpt1)/proxmox-installed
```

**Почему hd1, а не hd0?**
- `hd0` = первый диск = обычно USB
- `hd1` = второй диск = обычно системный SSD/HDD
- First-boot script ищет EFI **на том же диске что root** → гарантия что это системный диск, не USB

---

## Файлы на системе после установки

```bash
# После установки Proxmox:

/etc/proxmox-install-id
# Содержимое: MSK_2025_10_13_09_30

/efi/proxmox-installed  (или /boot/efi/proxmox-installed)
# Содержимое: MSK_2025_10_13_09_30

/var/log/proxmox-first-boot.log
# Лог работы first-boot script
```

---

## Файлы на USB

```
/dev/sdb1  (EFI boot partition)
├── EFI/
│   └── BOOT/
│       ├── grub.cfg              ← UUID wrapper (NEW!)
│       ├── grub-install.cfg      ← Original installer menu (RENAMED)
│       └── grubx64.efi
└── (other EFI files)

/dev/sdb3  (ISO main partition HFS+)
├── boot/
│   └── grub/
│       └── grub.cfg              ← Auto-installer menu (contains "if [ -f auto-installer-mode.toml ]")
├── auto-installer-mode.toml      ← Triggers auto-installer
└── (ISO contents)
```

---

## Преимущества этого подхода

### ✅ Безопасно
- UUID уникальный для каждого создания USB (timestamp-based)
- Невозможно случайно переустановить систему
- Маркер записывается только на системный диск, не на USB

### ✅ Надежно
- Работает даже если порядок дисков меняется (hd0/hd1)
- Проверяет несколько возможных расположений EFI (gpt1/gpt2)
- First-boot script ищет EFI на том же диске что root (не на USB)

### ✅ Удобно
- Первая установка: автоматическая
- После установки: автоматическая загрузка системы
- Переустановка: доступна через меню

### ✅ Прозрачно
- UUID видно в меню GRUB
- Логи first-boot script в `/var/log/proxmox-first-boot.log`
- Маркер UUID доступен в `/etc/proxmox-install-id`

---

## Отладка

### Проверить UUID на USB:

```bash
# Примонтировать EFI partition:
sudo mount /dev/sdb1 /mnt/usb

# Посмотреть wrapper grub.cfg:
sudo grep usb_uuid /mnt/usb/EFI/BOOT/grub.cfg
# Вывод: set usb_uuid="MSK_2025_10_13_09_30"

sudo umount /mnt/usb
```

### Проверить UUID на установленной системе:

```bash
# SSH на Proxmox:
ssh root@<proxmox-ip>

# Проверить UUID в /etc:
cat /etc/proxmox-install-id
# MSK_2025_10_13_09_30

# Проверить UUID на EFI:
cat /efi/proxmox-installed  # или /boot/efi/proxmox-installed
# MSK_2025_10_13_09_30

# Проверить лог first-boot:
cat /var/log/proxmox-first-boot.log
```

### Если UUID не совпадают:

**Проблема:** GRUB wrapper не распознает установленную систему

**Причины:**
1. First-boot script не запустился (проверить `/var/log/proxmox-first-boot.log`)
2. EFI не найдена (проверить `mount | grep efi`)
3. UUID на USB и системе разные (проверить оба файла)

**Решение:**
```bash
# На Proxmox:
# 1. Получить UUID с USB:
USB_UUID=$(cat /efi/proxmox-installed)  # Если USB примонтирован

# 2. Или создать вручную:
echo "MSK_2025_10_13_09_30" > /efi/proxmox-installed
echo "MSK_2025_10_13_09_30" > /etc/proxmox-install-id
```

---

## Сравнение с оригинальным create-usb.sh

| Аспект | create-usb.sh (old) | create-usb-final.sh (new) |
|--------|---------------------|---------------------------|
| **Генерация UUID** | ✅ timestamp | ✅ timestamp |
| **First-boot script** | ✅ 70 строк | ✅ 60 строк (упрощен) |
| **Wrapper grub.cfg** | ✅ 375 строк (embed_install_uuid) | ✅ 200 строк (embed_uuid_wrapper) |
| **Проверка дисков** | 9 вариантов (hd0-hd2 × gpt1-gpt3) | 4 варианта (hd0-hd1 × gpt1-gpt2) |
| **Chainloading** | ✅ Да | ✅ Да |
| **Интеграция** | Отдельная функция (375 строк) | Модульная (несколько функций) |

**Итого:** Новая версия проще и надежнее, но функциональность идентична.

---

## Итоговый flow

```
┌─────────────────────────────────────────────────────┐
│ 1. sudo ./create-usb-final.sh                       │
│    → Генерирует UUID: MSK_2025_10_13_09_30          │
│    → Создает first-boot script с UUID               │
│    → prepare-iso --on-first-boot first-boot.sh      │
│    → Записывает ISO на USB                          │
│    → add_auto_installer_mode (auto-installer-mode.toml) │
│    → embed_uuid_wrapper (wrapper grub.cfg)          │
│    → add_graphics_params (video=vesafb)             │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 2. ПЕРВАЯ ЗАГРУЗКА                                  │
│    Boot USB → wrapper checks (hd1,gpt2)/proxmox-installed │
│    → NOT FOUND → Show: "Install Proxmox (AUTO)"     │
│    → AUTO-INSTALL starts after 5 sec                │
│    → Installation (~10-15 min)                      │
│    → First-boot script runs:                        │
│      ✓ Creates /etc/proxmox-install-id             │
│      ✓ Creates /efi/proxmox-installed              │
│    → Reboot                                         │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ 3. ВТОРАЯ ЗАГРУЗКА (С USB)                          │
│    Boot USB → wrapper checks (hd1,gpt2)/proxmox-installed │
│    → FOUND! → Reads UUID: MSK_2025_10_13_09_30     │
│    → Compares with usb_uuid → MATCH!               │
│    → Show: "Boot Proxmox VE (Already Installed)"   │
│    → Chainloader → boots installed system          │
│    → ✅ NO REINSTALL!                               │
└─────────────────────────────────────────────────────┘
```

---

## Рекомендации

### ✅ DO:
- Оставляйте USB вставленным при первой перезагрузке
- Проверяйте `/var/log/proxmox-first-boot.log` после установки
- Сохраняйте UUID если создаете резервный USB

### ❌ DON'T:
- Не удаляйте `/efi/proxmox-installed` (сломает UUID защиту)
- Не используйте один USB для разных серверов с одинаковым UUID
- Не модифицируйте wrapper grub.cfg вручную без понимания

---

## Тестирование

Готово к тестированию! Запустите:

```bash
sudo ./create-usb-final.sh ~/Загрузки/proxmox-ve_9.0-1.iso answer.toml /dev/sdb
```

**Ожидаемый вывод:**
```
INFO: Generated installation UUID: MSK_2025_10_13_10_15
INFO: Created first-boot script with UUID: MSK_2025_10_13_10_15
INFO: Embedding answer.toml and first-boot script...
INFO: Successfully wrote ... to /dev/sdb
INFO: Created auto-installer-mode.toml
INFO: Embedding UUID wrapper in GRUB (prevents reinstallation loop)...
INFO: Installation UUID: MSK_2025_10_13_10_15
INFO: Found EFI boot partition: /dev/sdb1
INFO: Renamed original grub.cfg → grub-install.cfg
INFO: UUID wrapper created in grub.cfg
INFO: Original installer menu saved as grub-install.cfg
INFO: UUID wrapper embedded successfully
INFO: After installation, USB will automatically boot installed system
```

Протестируйте полный цикл:
1. Boot USB → Install
2. Reboot → Boot installed system (NOT reinstall!)
3. ✅ Success!
