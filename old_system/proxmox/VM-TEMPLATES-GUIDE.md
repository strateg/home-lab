# VM Templates на HDD - Руководство по клонированию

## Обзор

HDD (`local-hdd`) настроен для хранения VM templates, что позволяет:
- ✅ Создавать master-образы VM
- ✅ Быстро клонировать сервисы
- ✅ Экономить место на SSD
- ✅ Мультиплицировать идентичные окружения

## Storage Configuration

```bash
Storage: local-hdd
Path: /mnt/hdd
Content types:
  - images    ← VM disk images (templates!)
  - backup    ← Backups
  - iso       ← ISO images
  - vztmpl    ← LXC templates
  - rootdir   ← LXC disks
  - snippets  ← Scripts
```

## Workflow: Создание и использование VM Templates

### Шаг 1: Создайте базовую VM

**Вариант A: На SSD (для производительности)**
```
Proxmox Web UI → Create VM
- Storage: local-lvm (SSD)
- Установите ОС
- Настройте базовую конфигурацию
- Установите необходимый софт
```

**Вариант B: Сразу на HDD**
```
Create VM
- Storage: local-hdd (HDD)  ← Выберите HDD для диска
- Установите ОС
- Настройте
```

### Шаг 2: Подготовьте VM к клонированию

**Очистите систему:**
```bash
# Войдите в VM
ssh user@vm-ip

# Очистите логи
sudo truncate -s 0 /var/log/*.log
sudo rm -rf /var/log/*.gz

# Очистите cloud-init (если используется)
sudo cloud-init clean

# Очистите историю
history -c
cat /dev/null > ~/.bash_history

# Очистите SSH host keys (для cloud-init регенерации)
sudo rm -f /etc/ssh/ssh_host_*

# Очистите machine-id
sudo truncate -s 0 /etc/machine-id

# Выключите VM
sudo poweroff
```

### Шаг 3: Конвертируйте VM в Template

**Через Web UI:**
```
Proxmox Web UI
→ Выберите VM
→ More → Convert to template
→ Confirm
```

**Через CLI:**
```bash
# SSH на Proxmox host
ssh root@proxmox

# Конвертировать VM 100 в template
qm template 100
```

**Если VM на SSD, переместите на HDD:**
```bash
# Переместить диск VM на HDD
qm move-disk 100 scsi0 local-hdd

# Затем конвертировать в template
qm template 100
```

### Шаг 4: Клонируйте Template

**Через Web UI:**
```
Proxmox Web UI
→ Выберите template
→ Right click → Clone
→ Настройте:
   - VM ID: 201 (новый)
   - Name: my-service-01
   - Mode: Full Clone (полная копия)
   - Target Storage:
     - local-lvm (SSD) - для production
     - local-hdd (HDD) - для testing
→ Clone
```

**Через CLI:**
```bash
# Full clone на SSD (production)
qm clone 100 201 --name my-service-01 --full --storage local-lvm

# Full clone на HDD (testing)
qm clone 100 202 --name my-service-02 --full --storage local-hdd

# Linked clone (экономит место, но зависит от template)
qm clone 100 203 --name my-service-03
```

## Примеры использования

### Пример 1: Ubuntu Server Template

```bash
# 1. Создайте базовую VM (ID 100)
qm create 100 \
  --name ubuntu-22.04-template \
  --memory 2048 \
  --cores 2 \
  --net0 virtio,bridge=vmbr1 \
  --scsi0 local-hdd:32 \
  --ide2 local:iso/ubuntu-22.04.iso,media=cdrom \
  --boot order=scsi0

# 2. Установите Ubuntu через console

# 3. Настройте систему:
#    - cloud-init
#    - qemu-guest-agent
#    - базовые пакеты

# 4. Очистите и конвертируйте в template
qm template 100

# 5. Клонируйте для сервисов
qm clone 100 201 --name postgresql-db --full --storage local-lvm
qm clone 100 202 --name redis-cache --full --storage local-lvm
qm clone 100 203 --name app-server --full --storage local-lvm
```

### Пример 2: Docker Host Template

```bash
# Template с предустановленным Docker
# ID 110 - docker-host-template

# Клонируйте для разных окружений
qm clone 110 211 --name docker-dev --full --storage local-hdd
qm clone 110 212 --name docker-staging --full --storage local-lvm
qm clone 110 213 --name docker-prod --full --storage local-lvm
```

### Пример 3: OPNsense Backup Template

```bash
# Сохраните работающий OPNsense как template

# 1. Клонируйте текущий OPNsense (ID 100)
qm clone 100 150 --name opnsense-backup --full --storage local-hdd

# 2. Конвертируйте клон в template
qm template 150

# Теперь можно быстро восстановить при сбое:
qm clone 150 101 --name opnsense-restored --full --storage local-lvm
```

## Стратегии размещения

### Production (SSD - local-lvm)
```
Templates: Хранятся на HDD
Клоны: Создаются на SSD

Преимущества:
✅ Максимальная производительность
✅ Templates не занимают место на SSD
✅ Быстрый I/O для production
```

### Testing/Development (HDD - local-hdd)
```
Templates: На HDD
Клоны: На HDD

Преимущества:
✅ Экономия SSD
✅ Достаточно для тестов
✅ Можно создать много копий
```

### Hybrid подход
```
Critical services → SSD
Non-critical services → HDD
All templates → HDD
```

## Best Practices

### 1. Именование Templates

```
<os>-<version>-<purpose>-template

Примеры:
- ubuntu-22.04-base-template
- debian-12-docker-template
- opnsense-24.1-template
- alpine-3.18-minimal-template
```

### 2. Версионирование

```bash
# Создавайте версии templates
ubuntu-22.04-base-v1  (first version)
ubuntu-22.04-base-v2  (with updates)
ubuntu-22.04-base-v3  (with docker)

# Удаляйте старые после проверки новых
```

### 3. Документация

Создайте файл с описанием:
```
/mnt/hdd/templates/README.txt

Template: ubuntu-22.04-base-v2
ID: 100
Date: 2025-01-15
Packages:
- qemu-guest-agent
- cloud-init
- docker-ce
- htop, curl, vim
SSH: Disabled
User: ubuntu (password set via cloud-init)
```

### 4. Backup Templates

```bash
# Templates тоже нужно бэкапить!
vzdump 100 --storage local-hdd --mode snapshot --compress zstd

# Или автоматически через Proxmox Backup jobs
```

## Cloud-Init для автоматизации

### Настройка Cloud-Init в template

```bash
# В VM перед конвертацией в template
sudo apt install cloud-init

# Настройте cloud-init
sudo nano /etc/cloud/cloud.cfg

# При клонировании Proxmox автоматически:
# - Генерирует новый SSH host key
# - Устанавливает hostname
# - Настраивает network
# - Создаёт пользователя
```

### Использование при клонировании

```bash
# Клонировать с cloud-init параметрами
qm clone 100 201 --name web-01 --full --storage local-lvm

# Настроить cloud-init для клона
qm set 201 --ipconfig0 ip=10.0.30.10/24,gw=10.0.30.1
qm set 201 --ciuser admin
qm set 201 --cipassword secure123
qm set 201 --sshkey ~/.ssh/id_rsa.pub

# Запустить
qm start 201

# VM автоматически настроится!
```

## Мониторинг использования HDD

```bash
# Проверить использование storage
pvesm status

# Показать VM на HDD
qm list | grep local-hdd

# Размер templates
du -sh /mnt/hdd/images/*

# Топ-5 самых больших дисков
du -sh /mnt/hdd/images/* | sort -rh | head -5
```

## Troubleshooting

### Template не появляется в списке

```bash
# Проверить storage
pvesm status | grep local-hdd

# Проверить content types
cat /etc/pve/storage.cfg | grep -A 5 local-hdd

# Должно быть:
# dir: local-hdd
#     path /mnt/hdd
#     content backup,iso,vztmpl,rootdir,images,snippets
```

### Недостаточно места на HDD

```bash
# Удалить старые backups
find /mnt/hdd/dump -name "*.zst" -mtime +30 -delete

# Удалить неиспользуемые VM диски
# Через Web UI: Storage → local-hdd → Content → Remove

# Очистить старые templates
qm destroy 105  # Удалить template ID 105
```

### Клонирование медленное

```bash
# Используйте Linked clone для тестов
qm clone 100 301 --name test-vm

# Full clone только для production
qm clone 100 201 --name prod-vm --full
```

## Итоговый Checklist

✅ HDD настроен с content type `images`
✅ Создан базовый Ubuntu template
✅ Создан Docker host template
✅ Настроен cloud-init
✅ Документированы templates
✅ Настроен backup templates
✅ Протестировано клонирование на SSD
✅ Протестировано клонирование на HDD

**Теперь можно быстро мультиплицировать сервисы!** 🚀
