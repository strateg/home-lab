# Home Lab Infrastructure as Code

Infrastructure as Code (IaC) для home lab на базе Proxmox VE 9 с использованием Terraform и Ansible.

> 📖 **Старая документация**: Документация по предыдущей конфигурации сети доступна в [README-old-network-setup.md](README-old-network-setup.md)

---

## 🏗️ Обзор

**Оборудование**: Dell XPS L701X
- CPU: Intel Core i3-M370 (2 ядра, 2.4 GHz)
- RAM: 8 GB DDR3
- Накопители: SSD 180GB + HDD 500GB
- Сеть: 2x 1Gb/s Ethernet (USB + Встроенный), WiFi

**Стек технологий**:
- **Гипервизор**: Proxmox VE 9 (Debian 12 Bookworm)
- **Инфраструктура**: Terraform v1.7.0 (провайдер bpg/proxmox)
- **Конфигурация**: Ansible v2.14+ с cloud-init
- **Контроль версий**: Git
- **⭐ Источник истины**: new_system/topology.yaml (Infrastructure-as-Data)

### Infrastructure-as-Data подход

**Единый источник истины**: `new_system/topology.yaml` — YAML файл, описывающий всю инфраструктуру:
- Физические интерфейсы и сетевые мосты
- IP адресация всех сетей
- Определения VM и LXC контейнеров
- Конфигурация хранилища
- Правила маршрутизации и firewall

**Автогенерация из topology.yaml**:
```bash
# Редактируем топологию
vim new_system/topology.yaml

# Валидируем
python3 new_system/topology-tools/validate-topology.py

# Генерируем Terraform конфигурации
python3 new_system/topology-tools/generate-terraform.py

# Генерируем Ansible inventory
python3 new_system/topology-tools/generate-ansible-inventory.py

# Генерируем документацию (диаграммы, таблицы IP)
python3 new_system/topology-tools/generate-docs.py

# Применяем изменения
cd new_system/terraform && terraform apply  # terraform -> symlink to generated/terraform
cd ../ansible && ansible-playbook site.yml  # inventory configured in ansible.cfg
```

**Преимущества**:
- ✅ Единый источник истины — вся инфраструктура в одном файле
- ✅ Верифицируемые планы — Terraform plan показывает изменения
- ✅ Автогенерация документации — диаграммы и таблицы всегда актуальны
- ✅ Легко парсится — Claude Code может анализировать и модифицировать YAML
- ✅ Воспроизводимость — идемпотентные Terraform и Ansible

## 📁 Структура проекта

```
home-lab/
├── README.md                  # Этот файл
├── CLAUDE.md                  # ⭐ Руководство для Claude Code
├── MIGRATION.md               # Руководство по миграции
├── TESTING.md                 # Процедуры тестирования
├── .gitignore                 # Защита секретов
│
├── new_system/                # ⭐ Infrastructure-as-Data (новая система)
│   ├── topology.yaml          # ⭐ ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ
│   ├── scripts/               # ⭐ Генераторы из topology.yaml
│   │   ├── validate-topology.py
│   │   ├── generate-terraform.py
│   │   ├── generate-ansible-inventory.py
│   │   ├── generate-docs.py
│   │   └── README.md
│   ├── generated/             # ⚠️ Автогенерация (НЕ РЕДАКТИРОВАТЬ)
│   │   ├── terraform/         # Terraform конфиги
│   │   ├── ansible/           # Ansible inventory
│   │   └── docs/              # Документация
│   ├── terraform -> generated/terraform/  # Symlink для удобства
│   ├── ansible/               # Configuration management
│   │   ├── ansible.cfg
│   │   ├── requirements.yml
│   │   ├── inventory/
│   │   ├── playbooks/
│   │   └── roles/
│   └── bare-metal/            # Установка на bare-metal
│       ├── README.md
│       ├── answer.toml
│       ├── create-uefi-autoinstall-proxmox-usb.sh  # Main USB creation script
│       ├── run-create-usb.sh   # Interactive wrapper
│       └── post-install/
│
├── old_system/                # Script-based система (legacy, archived)
│   ├── proxmox/scripts/       # Bash скрипты автоматизации
│   ├── services/              # Скрипты развёртывания сервисов
│   └── vpn-servers/           # Конфиги VPN серверов
└── archive/                   # Архивы legacy кода
    └── legacy-terraform/      # Архив ручных Terraform модулей
```

## 🚀 Быстрый старт

### Вариант 1: Свежая установка (Рекомендуется)

**Для новой установки Proxmox на bare metal:**

1. **Создание загрузочного USB**
   ```bash
   cd new_system/bare-metal/
   sudo ./run-create-usb.sh  # Interactive wrapper
   # Or: sudo ./create-uefi-autoinstall-proxmox-usb.sh /dev/sdX proxmox-ve_9.0-1.iso
   ```

2. **Установка Proxmox**
   - Загрузитесь с USB на Dell XPS L701X
   - Автоустановка завершится (~15 минут)
   - Система перезагрузится

3. **Запуск Post-Install скриптов**
   ```bash
   ssh root@<proxmox-ip>
   cd /root/post-install
   ./01-install-terraform.sh
   ./02-install-ansible.sh
   ./03-configure-storage.sh
   ./04-configure-network.sh
   ./05-init-git-repo.sh
   reboot
   ```

4. **Копирование IaC файлов**
   ```bash
   scp -r ~/workspaces/projects/home-lab/* root@10.0.99.1:/root/home-lab/
   ```

5. **Развёртывание инфраструктуры**
   ```bash
   ssh root@10.0.99.1
   cd /root/home-lab/new_system/terraform  # symlink to generated/terraform
   cp terraform.tfvars.example terraform.tfvars
   vim terraform.tfvars  # Настройка
   terraform init
   terraform apply
   ```

6. **Конфигурация системы**
   ```bash
   cd /root/home-lab/new_system/ansible
   ansible-playbook playbooks/proxmox-setup.yml  # inventory configured in ansible.cfg
   ```

Подробности в [new_system/bare-metal/README.md](new_system/bare-metal/README.md)

---

### Вариант 2: Существующий Proxmox

**Для существующей установки Proxmox:**

1. **Установка Terraform и Ansible**
   ```bash
   cd new_system/bare-metal/post-install
   ./01-install-terraform.sh
   ./02-install-ansible.sh
   ```

2. **Копирование IaC файлов**
   ```bash
   scp -r ~/workspaces/projects/home-lab/* root@<proxmox-ip>:/root/home-lab/
   ```

3. **Настройка и применение**
   ```bash
   # Terraform
   cd /root/home-lab/new_system/terraform  # symlink to generated/terraform
   terraform init
   terraform apply

   # Ansible
   cd /root/home-lab/new_system/ansible
   ansible-playbook playbooks/proxmox-setup.yml  # inventory configured in ansible.cfg
   ```

Руководство по миграции: [MIGRATION.md](MIGRATION.md)

## 🏛️ Архитектура v3.0

### Сетевая топология

```
┌──────────────────────────────────────────────────────────────────┐
│                      ISP (Fiber/ADSL)                            │
└────────────────────────────┬─────────────────────────────────────┘
                             │
         ┌───────────────────▼──────────────────────┐
         │    MikroTik Chateau LTE7 ax              │
         │    (Central Router + WiFi 6 + LTE)       │
         │                                          │
         │    ether1 (WAN) ─────────────── ISP      │
         │    ether2 (LAN) ─────────────── Proxmox  │
         │    ether3 (LAN) ─────────────── Orange Pi 5
         │    wlan1/wlan2 ─────────────── WiFi clients
         │    lte1 ────────────────────── LTE failover
         │                                          │
         │    Containers (USB storage):             │
         │    - AdGuard Home (DNS filtering)        │
         │    - Tailscale (Mesh VPN)                │
         │                                          │
         │    IP: 192.168.88.1/24 (LAN)             │
         └───────────────────┬──────────────────────┘
                             │
         ┌───────────────────┼───────────────────────┐
         │                   │                       │
    ┌────▼────┐         ┌────▼────┐           ┌─────▼─────┐
    │ Proxmox │         │Orange Pi│           │  WiFi     │
    │ Gamayun │         │    5    │           │ Clients   │
    │         │         │         │           └───────────┘
    │.88.10   │         │ .88.20  │
    └────┬────┘         └────┬────┘
         │                   │
         │                   │
┌────────▼────────┐   ┌──────▼───────────────────────────┐
│ LXC Containers  │   │     Application Services         │
│ vmbr0 bridge    │   │     (Docker on Armbian)          │
│ 10.0.30.0/24    │   │                                  │
│                 │   │ - Nextcloud (file sharing)       │
│ - PostgreSQL.10 │   │ - Jellyfin (media, HW transcode) │
│ - Redis     .20 │   │ - Prometheus (monitoring)        │
│                 │   │ - Grafana (visualization)        │
└─────────────────┘   │ - Home Assistant (optional)      │
                      └──────────────────────────────────┘
```

**Преимущества v3 архитектуры:**
- Нет OPNsense VM → +2GB RAM на Proxmox для dev/lab VMs
- Нет GL.iNet → один роутер вместо двух
- MikroTik containers = меньше ресурсов чем полный AdGuard VM
- Orange Pi 5 RK3588S = аппаратное транскодирование для Jellyfin

### Хранилище

**SSD 180GB** (`/dev/sda` - local-lvm):
```
├── Root partition: 50 GB    (Proxmox OS)
├── Swap: 2 GB               (Память)
└── LVM thin pool: ~128 GB   (VMs & LXC)
```

**HDD 500GB** (`/dev/sdb` - local-hdd):
```
/mnt/hdd/
├── backup/      # Бэкапы VM/LXC
├── iso/         # ISO образы
├── template/    # Шаблоны VM
├── snippets/    # Cloud-init snippets
└── dump/        # Дампы конфигураций
```

## 🔧 Конфигурация

### Terraform

**Основные переменные** (terraform.tfvars):
```hcl
# Proxmox API
proxmox_api_url = "https://192.168.88.10:8006/api2/json"
proxmox_api_token_id = "root@pam!terraform"
proxmox_api_token_secret = "your-token-secret"

# Node
proxmox_node_name = "gamayun"

# Network (v3: direct to MikroTik LAN)
lan_interface = "eth-builtin"  # Connected to MikroTik ether2

# Storage
storage_ssd_id = "local-lvm"
storage_hdd_id = "local-hdd"
```

**Использование**:
```bash
cd new_system/terraform/

# Инициализация
terraform init

# Планирование изменений
terraform plan

# Применение изменений
terraform apply

# Уничтожение ресурсов
terraform destroy
```

---

### Ansible

**Основные переменные** (group_vars/all.yml):
```yaml
# Repository
proxmox_use_no_subscription_repo: true

# Network
proxmox_wan_interface: eth-usb
proxmox_lan_interface: eth-builtin

# Optimization
proxmox_ksm_enabled: true
proxmox_swappiness: 10
proxmox_cpu_governor: ondemand
```

**Использование**:
```bash
cd new_system/ansible/

# Тест подключения (inventory path configured in ansible.cfg)
ansible all -m ping

# Запуск плейбука
ansible-playbook playbooks/proxmox-setup.yml

# Запуск конкретных задач
ansible-playbook playbooks/proxmox-setup.yml --tags repositories

# Dry run
ansible-playbook playbooks/proxmox-setup.yml --check
```

> **Note**: `ansible.cfg` использует сгенерированный inventory из `../generated/ansible/inventory/production/hosts.yml`

## 📚 Документация

- **[MIGRATION.md](MIGRATION.md)**: Руководство по миграции
  - Стратегия миграции
  - Пошаговые инструкции
  - Планы отката
  - Процедуры проверки

- **[TESTING.md](TESTING.md)**: Руководство по тестированию
  - Unit тестирование
  - Integration тестирование
  - System тестирование (end-to-end)
  - Performance тестирование
  - Security тестирование

- **[new_system/bare-metal/README.md](new_system/bare-metal/README.md)**: Установка bare-metal
  - Создание USB
  - Конфигурация auto-install
  - Post-install скрипты

- **[new_system/deploy/Makefile](new_system/deploy/Makefile)**: Оркестрация развертывания
  - `make validate generate` - валидация и генерация
  - `make plan-mikrotik plan-proxmox` - Terraform plan
  - `make deploy-all` - полное развертывание

## 🔐 Безопасность

### Управление секретами

**Защищённые файлы** (.gitignore):
- `*.tfvars` - Переменные Terraform
- `*.tfstate` - Состояние Terraform
- `.vault_pass` - Пароль Ansible vault
- `*.pem`, `*.key` - SSH ключи
- `.env` - Переменные окружения

**Best practices**:
- Никогда не коммитить секреты в Git
- Использовать Ansible Vault для чувствительных данных
- Использовать переменные Terraform для секретов
- Регулярно ротировать API токены
- Использовать SSH ключи (не пароли)

## 🛠️ Обслуживание

### Ежедневно

- Мониторинг здоровья системы через Proxmox UI
- Проверка статуса сервисов
- Просмотр логов на наличие ошибок

### Еженедельно

- Запуск бэкапов
- Тест восстановления из бэкапа
- Обновление пакетов: `apt update && apt upgrade`
- Проверка drift: `terraform plan`
- Проверка Ansible: `ansible-playbook ... --check`

### Ежемесячно

- Обзор использования ресурсов
- Оптимизация хранилища (очистка бэкапов)
- Обзор логов безопасности
- Обновление документации

## 🐛 Устранение неполадок

Подробные процедуры в [TESTING.md](TESTING.md#troubleshooting)

## 🧪 Тестирование

### End-to-End Тест Регенерации

Для проверки корректности всего workflow регенерации используйте автоматизированный тест-скрипт:

```bash
cd new_system
./scripts/test-regeneration.sh
```

**Что проверяет скрипт**:
- ✓ Валидация topology.yaml (JSON Schema)
- ✓ Генерация Terraform конфигурации
- ✓ Валидация синтаксиса Terraform (terraform validate)
- ✓ Генерация Ansible inventory
- ✓ Валидация синтаксиса Ansible playbooks
- ✓ Генерация документации
- ✓ Проверка идемпотентности генераторов
- ✓ Отчет об изменениях в git

**Пример вывода**:
```
============================================================
Infrastructure-as-Data Regeneration Test Suite
============================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Test 1: Validate topology.yaml
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ topology.yaml exists
✓ topology.yaml validation passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Test 2: Generate Terraform Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Terraform generation completed
✓ Generated: provider.tf
✓ Generated: bridges.tf
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ ALL TESTS PASSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Рекомендация**: Запускайте этот тест после каждого изменения topology.yaml перед коммитом.

---

## 📊 Мониторинг

**Метрики для отслеживания**:
- CPU usage: `htop`, `mpstat`
- Memory usage: `free -h`, KSM stats
- Disk I/O: `iostat`
- Network throughput: `iperf3`
- Service status: `systemctl status`

## 🎯 Roadmap

### Завершено ✅

- [x] IaC структура директорий
- [x] Базовая конфигурация Terraform (Proxmox)
- [x] Модуль сети Terraform (bridges)
- [x] Модуль хранилища Terraform
- [x] Базовая конфигурация Ansible
- [x] Роль Proxmox в Ansible
- [x] Автоматизация bare-metal установки (Proxmox)
- [x] Документация по миграции
- [x] Процедуры тестирования
- [x] topology.yaml v3.0 с модульной структурой
- [x] Генераторы: Terraform, Ansible inventory, Docs

### В процессе 🔄

- [ ] Terraform для MikroTik (terraform-routeros provider)
- [ ] Модуль LXC в Terraform (PostgreSQL, Redis)
- [ ] Ansible playbooks для Orange Pi 5
- [ ] deploy/Makefile для оркестрации развертывания

### Планируется 📋

- [ ] Настройка мониторинга (Prometheus + Grafana на Orange Pi 5)
- [ ] Автоматизация бэкапов (Proxmox vzdump + rsync)
- [ ] MikroTik containers (AdGuard, Tailscale)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Тестирование disaster recovery

## 📄 Лицензия

MIT

## 📞 Поддержка

- Документация по [Proxmox](https://pve.proxmox.com/wiki/)
- [Terraform Proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Ansible Proxmox Module](https://docs.ansible.com/ansible/latest/collections/community/general/proxmox_module.html)

---

**Статус проекта**: Активная разработка (v3.0)
**Последнее обновление**: 2026-02-17
**Сопровождение**: Home Lab Administrator
