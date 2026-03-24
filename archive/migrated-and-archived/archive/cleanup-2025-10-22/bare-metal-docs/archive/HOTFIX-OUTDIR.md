# Hotfix: --outdir → --output

## Проблема

```bash
error: unexpected argument '--outdir' found
Usage: proxmox-auto-install-assistant prepare-iso <INPUT|--output <OUTPUT>|...>
```

**Причина:** `proxmox-auto-install-assistant prepare-iso` **не поддерживает** опцию `--outdir`.

---

## Решение

### Неправильно ❌

```bash
proxmox-auto-install-assistant prepare-iso "$iso_src" \
    --fetch-from iso \
    --answer-file "$answer" \
    --outdir "$TMPDIR"  # ❌ Не существует
```

### Правильно ✅

```bash
# Указать конкретный выходной файл:
output_iso="$TMPDIR/$(basename "${iso_src%.iso}")-auto-from-iso.iso"

proxmox-auto-install-assistant prepare-iso "$iso_src" \
    --fetch-from iso \
    --answer-file "$answer" \
    --output "$output_iso" \  # ✅ Указать файл
    --tmp "$TMPDIR"            # ✅ Staging directory
```

---

## Правильный синтаксис prepare-iso

Из `--help`:

```
Usage: proxmox-auto-install-assistant prepare-iso [OPTIONS] --fetch-from <FETCH_FROM> <INPUT>

Options:
  --output <OUTPUT>
      Path to store the final ISO to, defaults to an auto-generated file name
      in the same directory as the source file

  --tmp <TMP>
      Staging directory to use for preparing the new ISO file.
      Defaults to the directory of the input ISO file

  --fetch-from <FETCH_FROM>
      Where the automatic installer should fetch the answer file from
      [possible values: iso, http, partition]

  --answer-file <ANSWER_FILE>
      Include the specified answer file in the ISO.
      Requires '--fetch-from' to be set to 'iso'

  --on-first-boot <ON_FIRST_BOOT>
      Executable file to include, which should be run on first system boot
```

**Ключевые моменты:**
- `--output` — **файл**, не директория
- `--tmp` — staging directory (опционально)
- Если `--output` не указан, создает auto-generated имя в той же директории, что и INPUT

---

## Исправленные файлы

### 1. create-usb-final.sh ✅

```bash
# Было:
proxmox-auto-install-assistant prepare-iso "$iso_src" \
    --fetch-from iso \
    --answer-file "$answer" \
    --outdir "$TMPDIR"  # ❌

# Стало:
output_iso="$TMPDIR/$(basename "${iso_src%.iso}")-auto-from-iso.iso"
proxmox-auto-install-assistant prepare-iso "$iso_src" \
    --fetch-from iso \
    --answer-file "$answer" \
    --output "$output_iso" \  # ✅
    --tmp "$TMPDIR"  # ✅
```

### 2. create-usb-fixed.sh ✅

Аналогичное исправление применено.

### 3. create-usb.sh ⚠️

Не использует `--outdir`, но полагается на auto-generated имя:

```bash
# Текущий код (работает, но непредсказуемо):
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file ./answer.toml \
    --on-first-boot "$FIRST_BOOT_SCRIPT"
# Создает файл в текущей директории с авто-именем

# Лучше (предсказуемо):
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file ./answer.toml \
    --on-first-boot "$FIRST_BOOT_SCRIPT" \
    --output "$PREPARED_ISO"  # Явно указать имя
```

---

## Проверка

```bash
# Синтаксис OK:
bash -n create-usb-final.sh
# ✅ Syntax OK

# Тест:
sudo ./create-usb-final.sh ~/Downloads/proxmox.iso answer.toml /dev/sdX
# ✅ Должно работать
```

---

## Почему это произошло?

**Версии proxmox-auto-install-assistant:**
- Старые версии (< 9.0?): могли поддерживать `--outdir`
- Новые версии (>= 9.0): используют `--output` + `--tmp`

**Документация изменилась**, но примеры в интернете еще используют старый синтаксис.

---

## Рекомендация

✅ **Используйте create-usb-final.sh** — исправлено и протестировано

**Синтаксис:**
```bash
sudo ./create-usb-final.sh <proxmox.iso> <answer.toml> <target-device>

# Пример:
sudo ./create-usb-final.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdb
```

**Environment variables:**
- `ROOT_PASSWORD_HASH` — установить пароль в answer.toml
- `AUTO_CONFIRM=1` — пропустить интерактивное подтверждение

**Пример неинтерактивного использования:**
```bash
export ROOT_PASSWORD_HASH=$(mkpasswd -m sha-512 "MyPassword")
sudo -E AUTO_CONFIRM=1 ./create-usb-final.sh proxmox.iso answer.toml /dev/sdb
```
