# 🚀 Proxmox VE 9 - Автоматическая установка (ПРАВИЛЬНЫЙ метод)

## ✅ ОФИЦИАЛЬНЫЙ метод Proxmox

**Используется официальный инструмент `proxmox-auto-install-assistant`**

Этот инструмент:
- Встраивает `answer.toml` В ISO
- Добавляет "Automated Installation" в GRUB автоматически
- Автозапуск через 10 секунд (официальное поведение)

---

## 📋 Подготовка

### Шаг 0: Установить proxmox-auto-install-assistant

**На Ubuntu/Debian машине, где создаёте USB:**

```bash
# Добавить GPG ключ Proxmox
sudo wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

# Добавить репозиторий Proxmox (используем tee для sudo)
echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  sudo tee /etc/apt/sources.list.d/pve-install-repo.list

# Установить инструмент
sudo apt update
sudo apt install proxmox-auto-install-assistant
```

**Проверка установки:**
```bash
proxmox-auto-install-assistant --version
```

---

## 🚀 Создание USB (3 шага)

### 1️⃣ Создайте USB

```bash
sudo ./create-proxmox-usb.sh /dev/sdX proxmox-ve_9.0.iso
```

⚠️ Замените `/dev/sdX` на ваше USB устройство (например `/dev/sdb`)

**Скрипт автоматически:**
1. Проверит наличие `proxmox-auto-install-assistant`
2. Валидирует `answer.toml`
3. Подготовит ISO с встроенным answer файлом
4. Запишет подготовленный ISO на USB
5. Добавит графические параметры для внешнего дисплея

### 2️⃣ Загрузитесь с USB

1. Вставьте USB в Dell XPS L701X
2. Подключите внешний монитор к Mini DisplayPort
3. Нажмите **F12** при загрузке
4. Выберите **`UEFI: USB...`**

### 3️⃣ Ждите автозапуск

- GRUB покажет "Automated Installation" как первую опцию
- **Автозапуск через 10 секунд** (ничего не нажимайте!)
- Установка завершится через 10-15 минут

---

## 📁 Файлы

| Файл | Описание |
|------|----------|
| **`create-proxmox-usb.sh`** | ⭐ Основной скрипт (использует prepare-iso) |
| **`answer.toml`** | Конфигурация установки (TOML формат) |
| **`proxmox-post-install.sh`** | Скрипт пост-установки |

---

## ⚙️ Настройка answer.toml

Перед созданием USB отредактируйте `answer.toml`:

### Для России

```toml
[global]
country = "RU"  # Верхний регистр!
timezone = "Europe/Moscow"
```

### Для статического IP

```toml
[network]
source = "from-answer"
cidr = "192.168.1.100/24"
gateway = "192.168.1.1"
dns = "8.8.8.8"
```

### Для другого диска

```toml
[disk-setup]
filesystem = "ext4"
disk_list = ["/dev/nvme0n1"]  # Полный путь с /dev/
```

### LVM параметры (для ext4)

```toml
[disk-setup]
filesystem = "ext4"
disk_list = ["/dev/sda"]
lvm.swapsize = 8    # ВАЖНО: префикс lvm.
lvm.maxroot = 30
lvm.minfree = 8
lvm.maxvz = 0
```

---

## 🔧 Устранение проблем

### Автоустановка не запускается

**Причина**: ISO не был подготовлен с `prepare-iso`

**Решение**:
1. Убедитесь, что `proxmox-auto-install-assistant` установлен
2. Скрипт должен показать "✓ Prepared ISO created"
3. Пересоздайте USB

### answer.toml validation failed

**Причина**: Неправильный формат TOML

**Решение**:
1. Для ext4 LVM параметры должны иметь префикс `lvm.`:
   ```toml
   lvm.swapsize = 8  # НЕ просто swapsize
   ```
2. Country в верхнем регистре: `country = "EE"` (не "ee")
3. Диски с полным путём: `disk_list = ["/dev/sda"]`
4. Проверка: `proxmox-auto-install-assistant validate-answer answer.toml`

### proxmox-auto-install-assistant not found

**Решение**: Установите инструмент (см. Шаг 0 выше)

**Важно**: Используйте `tee` для sudo:
```bash
echo "deb..." | sudo tee /etc/apt/sources.list.d/pve-install-repo.list
```
НЕ `echo "deb..." > /etc/apt/...` (отказано в доступе)

### USB не загружается

**Решение**: Выбирайте **`UEFI: USB...`** (НЕ "USB Storage Device")

### Внешний монитор не работает

**Решение**: Скрипт должен показать "✓ Graphics parameters added". Если нет - пересоздайте USB.

---

## 📚 Документация

- 🇷🇺 **Русский**: [ИНСТРУКЦИЯ.md](ИНСТРУКЦИЯ.md)
- 🇬🇧 **English**: [README-AUTOINSTALL.md](README-AUTOINSTALL.md)
- 🖥️ **Dell XPS**: [DELL-XPS-EXTERNAL-DISPLAY-NOTES.md](DELL-XPS-EXTERNAL-DISPLAY-NOTES.md)

---

## 🎯 Краткая справка

```bash
# 0. Установить инструмент (один раз)
sudo apt install proxmox-auto-install-assistant

# 1. Создать USB
sudo ./create-proxmox-usb.sh /dev/sdX proxmox.iso

# 2. Загрузиться: F12 → UEFI: USB

# 3. Ждать 10 секунд → автоустановка!

# 4. После установки
ssh root@<ip>  # Пароль: Homelab2025!
```

---

## ✅ Что делает скрипт

**Официальный метод Proxmox:**

1. ✅ Проверяет `proxmox-auto-install-assistant`
2. ✅ Валидирует `answer.toml`
3. ✅ **Подготавливает ISO** командой `prepare-iso` (встраивает answer.toml)
4. ✅ Записывает **подготовленный ISO** на USB
5. ✅ Добавляет графические параметры для внешнего дисплея

**Результат:**
- "Automated Installation" запись в GRUB (добавлена автоматически)
- Автозапуск через 10 секунд (официальное поведение)
- Внешний дисплей работает

---

## 🎉 Готово!

После установки:
- ✅ Proxmox VE 9 установлен
- ✅ Внешний дисплей работал
- ✅ Сеть настроена (DHCP)
- ✅ Готов для VM

**Следующий шаг**: [README.md](README.md) - настройка сети

---

**Метод**: Официальный Proxmox prepare-iso
**Версия**: 2.0
**Дата**: 2025-10-05
