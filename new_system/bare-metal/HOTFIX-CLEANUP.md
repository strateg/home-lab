# Hotfix #10-11: Temporary ISO cleanup improvements

## Проблемы и решения

### Hotfix #10: Недостаточно места в /tmp

**Проблема:**
```
Error: No space left on device (os error 28)
```

`proxmox-auto-install-assistant` копирует ISO (~1.6GB) в `/tmp`, который часто является tmpfs (RAM-диск) с ограниченным размером.

**Решение:**
- Используется `/var/tmp/` вместо `/tmp/` (обычно на реальном диске)
- Автоматический fallback на текущую директорию если `/var/tmp` недостаточно

```bash
# Проверка свободного места (>2GB):
if [[ $(df --output=avail /var/tmp | tail -1) -gt 2000000 ]]; then
    TMPDIR=$(mktemp -d /var/tmp/pmxiso.XXXX)
else
    TMPDIR=$(mktemp -d ./pmxiso.XXXX)  # Fallback на текущую директорию
fi
```

---

### Hotfix #11: Автоматическое удаление временного ISO

**Проблема:**
Временный ISO (~1.6GB) оставался в `/tmp` или `/var/tmp` после завершения скрипта.

**Решение:**
Улучшен `cleanup()`:

```bash
cleanup() {
    # 1. Удаляет TMPDIR (включая временный ISO)
    if [[ -n "${TMPDIR:-}" && -d "${TMPDIR:-}" ]]; then
        printf '%s\n' "INFO: Cleaning up temporary files in $TMPDIR..." >&2
        rm -rf "${TMPDIR}"
    fi

    # 2. Очищает остатки от предыдущих запусков
    for pattern in /tmp/pmxiso.* /var/tmp/pmxiso.* ./pmxiso.*; do
        for dir in $pattern; do
            [[ -d "$dir" ]] && rm -rf "$dir" 2>/dev/null || true
        done
    done

    # 3. Размонтирует временные mount points
    for dir in /tmp/usbmnt.* /tmp/usb-uuid.*; do
        if [[ -d "$dir" ]] && mountpoint -q "$dir" 2>/dev/null; then
            umount "$dir" 2>/dev/null || true
        fi
        [[ -d "$dir" ]] && rmdir "$dir" 2>/dev/null || true
    done
}
```

**Когда cleanup() вызывается:**
- При успешном завершении (EXIT)
- При прерывании Ctrl+C (INT)
- При получении SIGTERM (TERM)
- При ошибке (EXIT с кодом != 0)

---

## Полный список всех Hotfix

| # | Проблема | Решение | Критичность |
|---|----------|---------|-------------|
| 1 | IFS syntax error | `IFS=$'\n\t'` | 🔴 КРИТИЧНО |
| 2 | cleanup() unmount glob | Цикл с mountpoint check | ⚠️ ВАЖНО |
| 3 | add_graphics два sed | Один sed с правильным паттерном | ⚠️ ВАЖНО |
| 4 | unquoted for loop | `while read` | ⚠️ ВАЖНО |
| 5 | grep вместо findmnt | `findmnt` | ⚠️ ВАЖНО |
| 6 | --outdir не существует | `--output "$file" --tmp "$dir"` | 🔴 КРИТИЧНО |
| 7 | INPUT порядок аргументов | INPUT последним | 🔴 КРИТИЧНО |
| 8 | pipe теряет exit code | Захват в переменную | 🔴 КРИТИЧНО |
| 9 | auto-installer-mode.toml отсутствует | Новая функция `add_auto_installer_mode()` | 🔴 КРИТИЧНО |
| **10** | **No space left (tmpfs)** | **Использовать /var/tmp** | **🔴 КРИТИЧНО** |
| **11** | **Временный ISO не удаляется** | **Улучшен cleanup()** | **⚠️ ВАЖНО** |

---

## Тестирование

### Проверка cleanup:

```bash
# Запустить скрипт:
sudo ./create-usb-final.sh proxmox.iso answer.toml /dev/sdX

# После завершения проверить что temp файлы удалены:
ls -la /var/tmp/pmxiso.* 2>/dev/null
# Ожидается: No such file or directory

ls -la ./pmxiso.* 2>/dev/null
# Ожидается: No such file or directory
```

### Проверка места на диске:

```bash
# До запуска:
df -h /var/tmp

# Должно быть > 2GB свободного места

# Во время работы:
watch -n 1 "df -h /var/tmp; ls -lh /var/tmp/pmxiso.*"

# После завершения:
df -h /var/tmp
# Должно вернуться к исходному значению
```

---

## Если все еще недостаточно места

### Вариант 1: Очистить /var/tmp

```bash
# Посмотреть что занимает место:
sudo du -sh /var/tmp/* 2>/dev/null | sort -h | tail -10

# Удалить старые файлы:
sudo find /var/tmp -type f -mtime +7 -delete
```

### Вариант 2: Увеличить размер tmpfs

```bash
# Временно (до перезагрузки):
sudo mount -o remount,size=4G /tmp

# Постоянно (добавить в /etc/fstab):
tmpfs /tmp tmpfs defaults,size=4G 0 0
```

### Вариант 3: Использовать домашнюю директорию

```bash
# Запустить скрипт из директории с достаточным местом:
cd ~/Downloads
sudo /path/to/create-usb-final.sh proxmox.iso answer.toml /dev/sdX

# Скрипт автоматически использует ./pmxiso.* если /var/tmp мало
```

---

## Сообщения скрипта

**При успешном завершении:**
```
INFO: Successfully wrote ... to /dev/sdb
INFO: Adding auto-installer-mode.toml to USB...
INFO: auto-installer-mode.toml is present on USB
INFO: Adding graphics parameters...
INFO: GRUB configuration updated
========================================
USB READY FOR AUTOMATED INSTALLATION
========================================
Note: Temporary ISO will be automatically cleaned up on exit.
INFO: Cleaning up temporary files in /var/tmp/pmxiso.XXXX...
```

**При ошибке:**
```
ERROR: ...
create-usb-final.sh: ERROR: Exited with status 9
INFO: Cleaning up temporary files in /var/tmp/pmxiso.XXXX...
```

---

## Размер временных файлов

**Требуется место:**
- Исходный ISO: ~1.6 GB
- Промежуточные файлы: ~1.6 GB (копия ISO)
- Выходной ISO: ~1.6 GB
- **Итого: ~3.2 GB** во время работы

**После завершения:**
- Все временные файлы удалены
- Остается только USB с записанным ISO

---

## Резюме

✅ **Hotfix #10**: Использовать `/var/tmp` вместо `/tmp` для избежания tmpfs limits
✅ **Hotfix #11**: Автоматическое удаление временных файлов через улучшенный `cleanup()`

**Результат:**
- Скрипт работает даже при малом размере `/tmp`
- Временные файлы всегда удаляются
- Очистка работает при любом сценарии завершения (успех/ошибка/Ctrl+C)
