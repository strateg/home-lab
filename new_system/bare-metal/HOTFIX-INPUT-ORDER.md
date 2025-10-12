# Hotfix #2: INPUT должен быть последним аргументом

## Проблема

```bash
proxmox-auto-install-assistant prepare-iso "$iso_src" \
    --fetch-from iso \
    --answer-file "$answer" \
    --output "$output_iso"
# ❌ ISO не создается
```

**Причина:** Позиционный аргумент `<INPUT>` должен быть **после всех опций**.

---

## Правильный синтаксис

### Usage из --help:

```
Usage: proxmox-auto-install-assistant prepare-iso [OPTIONS] --fetch-from <FETCH_FROM> <INPUT>
                                                    ^^^^^^^                            ^^^^^
                                                    ОПЦИИ                              ПОСЛЕДНИЙ
```

### Неправильно ❌

```bash
proxmox-auto-install-assistant prepare-iso "$iso_src" \  # ❌ INPUT первым
    --fetch-from iso \
    --answer-file "$answer" \
    --output "$output_iso"
```

### Правильно ✅

```bash
proxmox-auto-install-assistant prepare-iso \
    --fetch-from iso \
    --answer-file "$answer" \
    --output "$output_iso" \
    --tmp "$TMPDIR" \
    "$iso_src"  # ✅ INPUT последним
```

---

## Исправленные файлы

### 1. create-usb-final.sh ✅

```bash
# Было:
proxmox-auto-install-assistant prepare-iso "$iso_src" \
    --fetch-from iso \
    --answer-file "$answer"

# Стало:
proxmox-auto-install-assistant prepare-iso \
    --fetch-from iso \
    --answer-file "$answer" \
    --output "$output_iso" \
    --tmp "$TMPDIR" \
    "$iso_src"  # INPUT последним
```

### 2. create-usb-fixed.sh ✅

Аналогичное исправление.

### 3. create-usb.sh ✅

```bash
# Было:
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file ./answer.toml \
    --on-first-boot "$FIRST_BOOT_SCRIPT"

# Стало:
proxmox-auto-install-assistant prepare-iso \
    --fetch-from iso \
    --answer-file ./answer.toml \
    --on-first-boot "$FIRST_BOOT_SCRIPT" \
    "$ISO_FILE"  # INPUT последним
```

---

## Список всех исправлений

| Hotfix | Проблема | Исправление |
|--------|----------|-------------|
| #1 | IFS syntax error | `IFS=\n\t'` → `IFS=$'\n\t'` |
| #2 | cleanup() unmount | glob patterns → цикл with mountpoint check |
| #3 | add_graphics sed | 2 sed → 1 sed с правильным паттерном |
| #4 | unquoted for loop | `for p in $parts` → `while read` |
| #5 | grep mount check | `grep` → `findmnt` |
| #6 | --outdir | `--outdir "$TMPDIR"` → `--output "$file" --tmp "$dir"` |
| **#7** | **INPUT order** | `prepare-iso "$INPUT" --options` → `prepare-iso --options "$INPUT"` |

---

## Проверка

```bash
# Синтаксис OK:
bash -n create-usb-final.sh
# ✅ Syntax OK

# Тест команды вручную:
proxmox-auto-install-assistant prepare-iso \
    --fetch-from iso \
    --answer-file answer.toml \
    --output /tmp/test.iso \
    ~/Downloads/proxmox-ve_9.0-1.iso
# ✅ Должно работать

# Запуск скрипта:
sudo ./create-usb-final.sh ~/Загрузки/proxmox-ve_9.0-1.iso answer.toml /dev/sdb
# ✅ Должно работать
```

---

## Почему это произошло?

**Позиционные аргументы в CLI:**
- Стандартная практика: позиционные аргументы ПОСЛЕ опций
- Причина: опции с аргументами (--option value) могут быть перепутаны с позиционными

**Примеры правильного порядка:**
```bash
# GNU стиль:
ls -la /path/to/dir  # OPTIONS → INPUT
cp -r source dest    # OPTIONS → INPUTS
dd if=input of=output bs=4M  # OPTIONS (named) → без позиционных

# Proxmox style:
proxmox-auto-install-assistant prepare-iso [OPTIONS] <INPUT>
```

**Старые версии инструмента:**
- Могли принимать INPUT первым
- Документация изменилась без обратной совместимости

---

## Улучшенная диагностика

В `create-usb-final.sh` добавлена диагностика:

```bash
# Показывает точную команду:
print_info "Command: proxmox-auto-install-assistant prepare-iso ..."

# Логирует вывод:
... 2>&1 | tee /tmp/paa-output.log

# При ошибке показывает:
print_info "Contents of $TMPDIR:"
ls -la "$TMPDIR"
print_info "Looking for any ISO files:"
find "$TMPDIR" -type f -name "*.iso"
```

---

## Теперь попробуйте:

```bash
sudo ./create-usb-final.sh ~/Загрузки/proxmox-ve_9.0-1.iso answer.toml /dev/sdb
```

**Ожидаемый вывод:**
```
INFO: Validated target: /dev/sdb (device: sdb)
The answer file was parsed successfully, no errors found!
INFO: answer.toml validated successfully
INFO: Using tempdir /tmp/pmxiso.XXXX
INFO: Embedding answer.toml using proxmox-auto-install-assistant...
INFO: Command: proxmox-auto-install-assistant prepare-iso --fetch-from iso ...
[proxmox-auto-install-assistant output]
INFO: Prepared ISO located at: /tmp/pmxiso.XXXX/proxmox-ve_9.0-1-auto-from-iso.iso
WARNING: About to write ISO to /dev/sdb - THIS WILL DESTROY ALL DATA
Type YES to confirm:
```

---

## Если все еще не работает

Запустите команду вручную для отладки:

```bash
# 1. Создать temp directory:
TMPDIR=$(mktemp -d -t test.XXXX)
echo "TMPDIR: $TMPDIR"

# 2. Запустить prepare-iso:
proxmox-auto-install-assistant prepare-iso \
    --fetch-from iso \
    --answer-file answer.toml \
    --output "$TMPDIR/test-output.iso" \
    --tmp "$TMPDIR" \
    ~/Загрузки/proxmox-ve_9.0-1.iso

# 3. Проверить результат:
ls -lh "$TMPDIR/"
file "$TMPDIR/test-output.iso"

# 4. Cleanup:
rm -rf "$TMPDIR"
```

Если это работает вручную, значит скрипт исправлен правильно.
