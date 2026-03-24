# Правильное решение Reinstall Prevention

## Анализ проблемы

### Что НЕ работает:
1. ❌ Создание `reinstall-check.cfg` как отдельного файла - не загружается автоматически
2. ❌ Чтение UUID из файла на USB через `($root)/EFI/BOOT/install-id` - `$root` может указывать не туда
3. ❌ `search` команда в GRUB - находит не ту партицию

### Что РАБОТАЕТ:
1. ✅ First-boot скрипт **РАБОТАЕТ** - UUID сохраняется на диск в `/efi/proxmox-installed`
2. ✅ Proxmox монтирует EFI в `/efi` (не `/boot/efi`)
3. ✅ EFI партиция на диске: `/dev/sda2` (gpt2)

## Правильное решение

### Шаг 1: UUID встраивается В САМ grub.cfg

```bash
# В create-usb.sh при создании USB:

# 1. Бэкап оригинального grub.cfg
mv grub.cfg grub-install.cfg

# 2. Создать НОВЫЙ grub.cfg с проверкой UUID
cat > grub.cfg << EOF
set usb_uuid="ACTUAL_UUID_HERE"  # Встроен при создании!

# Проверить (hd0,gpt2)/proxmox-installed
if [ -f (hd0,gpt2)/proxmox-installed ]; then
    cat --set=disk_uuid (hd0,gpt2)/proxmox-installed

    if [ "$disk_uuid" = "$usb_uuid" ]; then
        # UUIDs совпадают - загрузить систему
        set timeout=5
        set default=0

        menuentry 'Boot Proxmox VE' {
            chainloader (hd0,gpt2)/EFI/proxmox/grubx64.efi
        }

        menuentry 'Reinstall' {
            configfile /EFI/BOOT/grub-install.cfg
        }
    else
        # Разные UUID - показать меню установки
        configfile /EFI/BOOT/grub-install.cfg
    fi
else
    # Нет маркера - чистый диск - установка
    configfile /EFI/BOOT/grub-install.cfg
fi
EOF
```

### Критические моменты:

1. **UUID ВСТРОЕН в grub.cfg** - не читается из файла!
2. **Проверяем ТОЛЬКО (hd0,gpt2)** - жесткий диск, не USB!
3. **grub.cfg ЗАМЕНЯЕТ оригинальный** - загружается первым!
4. **Fallback на grub-install.cfg** - оригинальный установщик

## Почему это работает

1. USB Boot → GRUB загружает `grub.cfg` (наш скрипт)
2. Скрипт знает UUID (встроен): `EEST_2025_10_10_21_43`
3. Читает UUID с диска: `(hd0,gpt2)/proxmox-installed`
4. Сравнивает БЕЗ file I/O на USB
5. Если совпадают → chainload to disk
6. Если нет → запускает установку

## Реализация

```bash
# В embed_install_uuid():

# 1. Найти правильную EFI партицию по PARTLABEL
PARTLABEL=$(blkid -s PARTLABEL -o value "$part")
if [[ "$PARTLABEL" =~ "EFI" ]] || [[ "$PARTLABEL" =~ "boot" ]]; then

    # 2. Бэкап оригинального grub.cfg
    mv grub.cfg grub-install.cfg

    # 3. Создать новый grub.cfg с UUID
    cat > grub.cfg << GRUBEOF
set usb_uuid="$INSTALL_UUID"

if [ -f (hd0,gpt2)/proxmox-installed ]; then
    cat --set=disk_uuid (hd0,gpt2)/proxmox-installed

    if [ "\$disk_uuid" = "\$usb_uuid" ]; then
        set timeout=5
        set default=0
        menuentry 'Boot Proxmox VE' {
            chainloader (hd0,gpt2)/EFI/proxmox/grubx64.efi
        }
    else
        configfile /EFI/BOOT/grub-install.cfg
    fi
else
    configfile /EFI/BOOT/grub-install.cfg
fi
GRUBEOF
fi
```

## Тестирование

```bash
# После создания USB проверить:
mount /dev/sdX2 /mnt
cat /mnt/EFI/BOOT/grub.cfg | head -20
# Должно показать: set usb_uuid="EEST_..."

# После установки:
cat /efi/proxmox-installed
# Должно показать: EEST_2025_10_10_21_43

# После перезагрузки (флешка вставлена):
# Система загрузится через 5 секунд!
```

## Что точно работает

✅ First-boot сохраняет UUID на `/efi/proxmox-installed`
✅ UUID формат: `EEST_2025_10_10_21_43`
✅ EFI на диске: `/dev/sda2` → `(hd0,gpt2)`
✅ Proxmox монтирует в `/efi`

Только нужно ПРАВИЛЬНО встроить UUID в grub.cfg!
