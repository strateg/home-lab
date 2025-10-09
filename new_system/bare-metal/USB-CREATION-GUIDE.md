# Proxmox Auto-Install USB Creation Guide

## Проблема и решение

### ❌ Что было не так (старая версия в new_system)

Предыдущая версия `create-usb.sh` **не работала** для автоматической установки:

1. Просто копировала ISO на USB через `dd`
2. Пыталась вручную добавить `answer.toml` на смонтированную партицию
3. **НЕ использовала официальный метод Proxmox**
4. Результат: обычная интерактивная установка, а не автоматическая

### ✅ Что работает (исправленная версия)

Новая версия использует **официальный метод Proxmox** через утилиту `proxmox-auto-install-assistant`:

```bash
# Официальный процесс:
1. proxmox-auto-install-assistant validate-answer answer.toml
   ↓ Проверяет корректность конфигурации

2. proxmox-auto-install-assistant prepare-iso original.iso --fetch-from iso --answer-file answer.toml
   ↓ Встраивает answer.toml ВНУТРЬ ISO
   ↓ Создает новое меню загрузки с опцией "Automated Installation"
   ↓ Настраивает автоматический запуск через 10 секунд

3. dd if=prepared.iso of=/dev/sdX
   ↓ Записывает ПОДГОТОВЛЕННЫЙ ISO на USB

4. Модифицирует GRUB для внешнего дисплея (Dell XPS L701X)
```

**Результат**: При загрузке с USB автоматически запускается установка!

## Установка proxmox-auto-install-assistant

Эта утилита **обязательна** для создания автоматической установки.

### Debian/Ubuntu (рекомендуется)

```bash
# 1. Добавить GPG ключ Proxmox
sudo wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

# 2. Добавить репозиторий Proxmox
echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  sudo tee /etc/apt/sources.list.d/pve-install-repo.list

# 3. Установить утилиту
sudo apt update
sudo apt install proxmox-auto-install-assistant
```

### Проверка установки

```bash
proxmox-auto-install-assistant --version
```

Если команда работает - всё готово!

## Использование create-usb.sh

### Предварительные требования

1. **USB накопитель** (минимум 2 GB, будет полностью стёрт)
2. **Proxmox VE ISO** (скачан или будет загружен автоматически)
3. **answer.toml** (в директории `new_system/bare-metal/`)
4. **proxmox-auto-install-assistant** (установлен, см. выше)
5. **Root права** (sudo)

### Шаг 1: Подготовка конфигурации

Отредактируйте `answer.toml` (если нужно):

```bash
cd new_system/bare-metal
vim answer.toml
```

**Важно**: Измените пароль root! По умолчанию используется `Homelab2025!`

Генерация нового хэша пароля:

```bash
# Вариант 1: openssl
openssl passwd -6 "YourStrongPassword"

# Вариант 2: mkpasswd
mkpasswd -m sha-512 "YourStrongPassword"
```

Вставьте полученный хэш в `answer.toml`:

```toml
[global]
root_password = "$6$rounds=656000$YourNewHash..."
```

### Шаг 2: Определение USB устройства

**ОСТОРОЖНО**: USB будет полностью стёрт!

```bash
# Показать все устройства
lsblk

# Пример вывода:
# NAME   MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
# sda      8:0    0 232.9G  0 disk       ← Ваш SSD (НЕ ИСПОЛЬЗУЙТЕ!)
# sdb      8:16   1   7.5G  0 disk       ← USB накопитель
# └─sdb1   8:17   1   7.5G  0 part
```

В примере выше USB устройство: `/dev/sdb`

### Шаг 3: Создание USB

```bash
cd new_system/bare-metal

# Если ISO уже скачан:
sudo ./create-usb.sh /dev/sdb /path/to/proxmox-ve_9.0-1.iso

# Если ISO нужно скачать:
sudo ./create-usb.sh /dev/sdb proxmox.iso
# (скрипт предложит скачать, если файл не найден)
```

### Что происходит во время выполнения

```
[1/7] Checking Requirements
  ✓ Root privileges
  ✓ Required tools (dd, lsblk, sync, mkpasswd)
  ✓ proxmox-auto-install-assistant installed

[2/7] Validating USB Device: /dev/sdb
  ✓ Device exists
  ✓ Size sufficient (7.5 GB)

[3/7] Validating ISO File
  ✓ File exists
  ✓ Valid ISO 9660 format

[4/7] Validating answer.toml
  • Checking for default password... OK
  • Running official validation...
  ✓ answer.toml is valid

[5/7] Preparing ISO with embedded answer.toml
  • Running: proxmox-auto-install-assistant prepare-iso...
  ✓ Prepared ISO created: proxmox-ve_9.0-1-automated.iso
  ✓ This ISO includes 'Automated Installation' boot entry
  ✓ Auto-selects after 10 seconds

[6/7] Writing prepared ISO to USB
  WARNING: This will ERASE all data on /dev/sdb
  Continue? (yes/no) yes

  • Writing prepared ISO to USB...
  [====================] 1.2 GB / 1.2 GB
  ✓ Prepared ISO written to USB

[7/7] Adding graphics parameters for external display
  • Modifying GRUB configuration...
  ✓ Graphics parameters added (video=vesafb:ywrap,mtrr vga=791 nomodeset)

[8/7] Verifying USB Drive
  ✓ USB verification complete

╔════════════════════════════════════════════════════════╗
║  USB READY FOR AUTOMATED INSTALLATION!                 ║
╚════════════════════════════════════════════════════════╝
```

## Загрузка и установка

### Шаг 1: Подготовка оборудования (Dell XPS L701X)

1. **Подключите внешний монитор** к Mini DisplayPort
2. **Включите монитор** (важно сделать ДО загрузки!)
3. Вставьте USB накопитель
4. Включите ноутбук

### Шаг 2: Загрузка с USB

1. При старте нажмите **F12** (Boot Menu)
2. Выберите: **`UEFI: USB...`** (**НЕ** `USB Storage Device`)
3. Нажмите Enter

### Шаг 3: Автоматическая установка

**Что вы увидите:**

```
╔════════════════════════════════════════════════════════╗
║ GRUB Boot Menu                                         ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  → Automated Installation ⏱ 10 seconds                ║  ← АВТОМАТИЧЕСКИ
║    Install Proxmox VE (Graphical)                     ║
║    Install Proxmox VE (Terminal UI)                   ║
║    Advanced Options                                    ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
```

**Через 10 секунд** автоматически запустится "Automated Installation"!

**Процесс установки (10-15 минут):**

1. ✅ Загрузка ядра Linux
2. ✅ Чтение `answer.toml` из ISO
3. ✅ Разметка диска (SSD):
   - 50 GB → root (ext4)
   - 2 GB → swap
   - ~128 GB → LVM thin pool (для VMs/LXC)
4. ✅ Установка Proxmox VE
5. ✅ Настройка сети (DHCP)
6. ✅ Установка базовых пакетов
7. ✅ Автоматическая перезагрузка

**НЕ ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО!** Установка полностью автоматическая.

### Шаг 4: После установки

После перезагрузки:

1. **Извлеките USB** накопитель
2. Найдите IP адрес:
   - Посмотрите DHCP leases на роутере
   - Или подключите монитор и выполните: `ip a`

3. **Подключитесь по SSH**:

```bash
ssh root@<ip-address>
# Пароль: тот, что вы установили в answer.toml
```

4. **Проверьте Web UI**:

```
https://<ip-address>:8006
```

## Post-Install Automation

После успешной установки Proxmox, запустите post-install скрипты:

```bash
# 1. Скопируйте скрипты на Proxmox
scp -r new_system/bare-metal/post-install/ root@<ip>:/root/

# 2. SSH на Proxmox
ssh root@<ip>

# 3. Запустите установку
cd /root/post-install
./01-install-terraform.sh
./02-install-ansible.sh
./03-configure-storage.sh
./04-configure-network.sh
./05-init-git-repo.sh

# 4. Перезагрузите для применения сетевых настроек
reboot

# 5. После перезагрузки - разверните инфраструктуру
ssh root@10.0.99.1  # Новый IP после конфигурации
cd /root/home-lab/new_system

# Сгенерировать Terraform конфигурацию
python3 scripts/generate-terraform.py

# Применить инфраструктуру
cd terraform
terraform init
terraform apply

# Сгенерировать Ansible inventory
cd ../
python3 scripts/generate-ansible-inventory.py

# Настроить сервисы
cd ansible
ansible-playbook -i inventory/production/hosts.yml site.yml
```

## Устранение неполадок

### Проблема: `proxmox-auto-install-assistant: command not found`

**Решение**: Установите утилиту (см. раздел "Установка" выше)

### Проблема: Загружается обычная установка, а не автоматическая

**Причины:**

1. **Не был использован `proxmox-auto-install-assistant prepare-iso`**
   - Проверьте, что скрипт создал "prepared ISO"
   - Должно быть сообщение: `✓ Prepared ISO created`

2. **Выбран неправильный режим загрузки**
   - Выбирайте **`UEFI: USB...`**, НЕ `USB Storage Device`

3. **answer.toml не прошел валидацию**
   - Проверьте вывод: `proxmox-auto-install-assistant validate-answer answer.toml`

### Проблема: Внешний монитор не показывает изображение

**Причины:**

1. **Монитор не включен ДО загрузки**
   - Dell XPS L701X отключает внешний выход, если монитор не обнаружен при старте

2. **Не добавлены графические параметры**
   - Проверьте вывод скрипта: `✓ Graphics parameters added`
   - Если нет - скрипт не смог изменить GRUB

**Решение**: Переподключите USB, включите монитор, запустите скрипт снова

### Проблема: Установка останавливается с ошибкой диска

**Причины:**

1. **Неправильный диск в answer.toml**
   - Проверьте `disk_list = ["first"]` в answer.toml
   - Или явно укажите: `disk_list = ["/dev/sda"]`

2. **Диск уже используется**
   - Загрузитесь с USB в Live режим
   - Сотрите разделы: `wipefs -a /dev/sda`

## Сравнение методов

| Аспект | Старый метод (НЕ РАБОТАЕТ) | Новый метод (РАБОТАЕТ) |
|--------|---------------------------|------------------------|
| Инструмент | `dd` + ручное копирование | `proxmox-auto-install-assistant` |
| answer.toml | Копируется отдельно | Встраивается в ISO |
| GRUB меню | Стандартное | "Automated Installation" опция |
| Автозапуск | ❌ Нет | ✅ Через 10 секунд |
| Официальный | ❌ Нет | ✅ Да |
| Результат | Интерактивная установка | Автоматическая установка |

## Дополнительные ресурсы

- **Официальная документация Proxmox**: https://pve.proxmox.com/wiki/Automated_Installation
- **answer.toml примеры**: https://pve.proxmox.com/wiki/Automated_Installation#example_answer_files
- **proxmox-auto-install-assistant**: https://git.proxmox.com/?p=pve-installer.git

## Примечания

- **HDD (sdb) НЕ ЗАТРАГИВАЕТСЯ**: Установка только на SSD (sda)
- **Сеть DHCP**: Изначально используется DHCP, настраивается post-install скриптами
- **Пароль**: Храните в безопасности! Не коммитьте answer.toml с реальным паролем в Git
- **Очистка**: Скрипт автоматически удаляет временный prepared ISO после записи на USB

---

**Дата обновления**: 2025-10-09
**Версия**: 2.0 (исправлена с использованием официального метода Proxmox)
