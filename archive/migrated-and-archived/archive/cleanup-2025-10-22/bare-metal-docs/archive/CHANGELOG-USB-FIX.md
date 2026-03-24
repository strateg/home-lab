# USB Creation Script Fix - Changelog

## Дата: 2025-10-09

## Проблема

`create-usb.sh` создавал USB, но **автоматическая установка не работала**:
- Загружалась обычная интерактивная установка Proxmox
- Требовался ручной ввод всех параметров
- `answer.toml` игнорировался

## Причина

Скрипт **не использовал официальный метод Proxmox** для автоматической установки:
- Просто копировал ISO через `dd`
- Пытался вручную добавить `answer.toml` на USB
- НЕ создавал "Automated Installation" опцию в GRUB меню

## Решение

Полностью переписан `create-usb.sh` с использованием **официального метода Proxmox**:

### Что изменено

#### 1. Добавлена проверка утилиты (строка 73-91)

```bash
# Check for proxmox-auto-install-assistant (CRITICAL for auto-install)
if ! command -v proxmox-auto-install-assistant &> /dev/null; then
    print_error "proxmox-auto-install-assistant not found"
    # ... инструкции по установке
    exit 1
fi
```

#### 2. Заменена функция подготовки (строка 236-280)

**Было**: `prepare_answer_file()` - просто проверка и обновление пароля

**Стало**: `validate_answer_file()` - проверка + **официальная валидация**:

```bash
# Validate answer.toml using official tool
if proxmox-auto-install-assistant validate-answer "$ANSWER_FILE"; then
    print_success "answer.toml is valid"
else
    print_error "answer.toml validation failed"
    exit 1
fi
```

#### 3. Добавлена функция prepare-iso (строка 286-326)

**НОВАЯ ФУНКЦИЯ** - ключевая для автоматической установки:

```bash
prepare_iso() {
    # Встраивает answer.toml ВНУТРЬ ISO
    proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
        --fetch-from iso \
        --answer-file ./answer.toml

    # Создает ISO с опцией "Automated Installation"
    # ...
}
```

#### 4. Разделена функция записи USB (строка 332-359)

**Было**: `create_bootable_usb()` - писал оригинальный ISO

**Стало**: `write_usb()` - пишет **ПОДГОТОВЛЕННЫЙ** ISO:

```bash
# Write PREPARED ISO (not original!)
dd if="$PREPARED_ISO" of="$USB_DEVICE" ...
```

#### 5. Переименована функция графики (строка 365-424)

**Было**: `add_autoinstall_config()` - копировала answer.toml на USB

**Стало**: `add_graphics_params()` - только модификация GRUB для внешнего дисплея

**УДАЛЕНО**: ручное копирование answer.toml (больше не нужно!)

#### 6. Обновлены инструкции (строка 449-533)

Добавлены детальные инструкции:
- Что происходит при загрузке
- Поведение автоматической установки
- Post-install шаги
- Полный workflow от USB до развёрнутой инфраструктуры

#### 7. Обновлен main() (строка 539-557)

**Новый порядок вызова функций**:

```bash
main() {
    check_requirements       # + проверка proxmox-auto-install-assistant
    validate_usb_device      # без изменений
    validate_iso_file        # без изменений
    validate_answer_file     # + официальная валидация
    prepare_iso              # НОВАЯ - prepare-iso
    write_usb                # измененная - пишет prepared ISO
    add_graphics_params      # переименованная
    verify_usb               # без изменений
    display_instructions     # обновленные инструкции
}
```

## Результат

### До исправления

```
Загрузка с USB
    ↓
GRUB menu (обычное)
    ↓
Выбор: Install Proxmox VE (Graphical)
    ↓
❌ ИНТЕРАКТИВНАЯ установка
    ↓
Требуется ручной ввод всех параметров
```

### После исправления

```
Загрузка с USB
    ↓
GRUB menu (модифицированное)
    ↓
Первая опция: "Automated Installation" ⏱ 10 sec
    ↓
✅ АВТОМАТИЧЕСКАЯ установка
    ↓
Читает answer.toml из ISO
    ↓
Установка без вмешательства (10-15 мин)
    ↓
Автоматическая перезагрузка
```

## Требования

### Новая зависимость (обязательно!)

**proxmox-auto-install-assistant** - официальная утилита Proxmox

Установка (Debian/Ubuntu):

```bash
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  tee /etc/apt/sources.list.d/pve-install-repo.list

apt update && apt install proxmox-auto-install-assistant
```

## Файлы изменены

- ✅ `new_system/bare-metal/create-usb.sh` - полностью переписан
- ✅ `new_system/bare-metal/USB-CREATION-GUIDE.md` - новая документация
- ✅ `new_system/bare-metal/CHANGELOG-USB-FIX.md` - этот файл

## Файлы без изменений

- `new_system/bare-metal/answer.toml` - конфигурация (без изменений)
- `new_system/bare-metal/post-install/*` - скрипты (без изменений)

## Тестирование

Для проверки исправления:

```bash
# 1. Убедитесь, что утилита установлена
proxmox-auto-install-assistant --version

# 2. Создайте USB
sudo ./create-usb.sh /dev/sdX proxmox-ve_9.0-1.iso

# 3. Загрузитесь с USB
# Должна появиться опция "Automated Installation"
# Автоматический запуск через 10 секунд

# 4. Установка должна пройти БЕЗ вмешательства
```

## Обратная совместимость

**ВНИМАНИЕ**: Старый метод (из `old_system/proxmox/install/create-proxmox-usb.sh`) УЖЕ использовал официальный метод и работал правильно!

Это исправление приводит `new_system` в соответствие со **старым рабочим методом**.

## Ссылки

- Старый рабочий скрипт: `old_system/proxmox/install/create-proxmox-usb.sh`
- Официальная документация: https://pve.proxmox.com/wiki/Automated_Installation
- Git repository утилиты: https://git.proxmox.com/?p=pve-installer.git

## Автор исправления

Claude Code (AI Assistant)

## Заметки

- Скрипт автоматически удаляет временный prepared ISO после записи
- HDD (sdb) не затрагивается - только SSD (sda)
- Графические параметры добавляются для Dell XPS L701X (внешний дисплей)
- Пароль из answer.toml будет запрошен, если используется placeholder

---

**Версия**: 2.0 (с официальным методом Proxmox)
**Дата**: 2025-10-09
