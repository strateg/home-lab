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
- **⭐ Источник истины**: topology.yaml (Infrastructure-as-Data)

### Infrastructure-as-Data подход

**Единый источник истины**: `topology.yaml` — YAML файл, описывающий всю инфраструктуру:
- Физические интерфейсы и сетевые мосты
- IP адресация всех сетей
- Определения VM и LXC контейнеров
- Конфигурация хранилища
- Правила маршрутизации и firewall

**Автогенерация из topology.yaml**:
```bash
# Редактируем топологию
vim topology.yaml

# Валидируем
python3 scripts/validate-topology.py

# Генерируем Terraform конфигурации
python3 scripts/generate-terraform.py

# Генерируем Ansible inventory
python3 scripts/generate-ansible-inventory.py

# Генерируем документацию (диаграммы, таблицы IP)
python3 scripts/generate-docs.py

# Применяем изменения
cd terraform && terraform apply
cd ../ansible && ansible-playbook -i inventory/production/hosts.yml site.yml
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
├── topology.yaml              # ⭐ ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ
├── MIGRATION.md               # Руководство по миграции
├── TESTING.md                 # Процедуры тестирования
├── .gitignore                 # Защита секретов
│
├── scripts/                   # ⭐ Генераторы из topology.yaml
│   ├── validate-topology.py   # Валидация топологии
│   ├── generate-terraform.py  # Генерация Terraform (TODO)
│   ├── generate-ansible-inventory.py  # Генерация Ansible inventory (TODO)
│   ├── generate-docs.py       # Генерация документации (TODO)
│   └── README.md              # Документация генераторов
│
├── terraform/                 # Provisioning инфраструктуры (⚠️ автогенерация)
│   ├── providers.tf           # Конфигурация Proxmox provider
│   ├── versions.tf            # Версии провайдеров
│   ├── variables.tf           # Переменные (85+)
│   ├── outputs.tf             # Выходные значения
│   ├── terraform.tfvars.example  # Шаблон переменных
│   └── modules/
│       ├── network/           # Сетевые мосты (vmbr0-vmbr99)
│       └── storage/           # Пулы хранения (SSD + HDD)
│
├── ansible/                   # Configuration management
│   ├── ansible.cfg            # Конфигурация Ansible
│   ├── requirements.yml       # Коллекции и роли
│   ├── inventory/
│   │   └── production/
│   │       ├── hosts.yml      # Inventory
│   │       └── group_vars/
│   │           └── all.yml    # Глобальные переменные
│   ├── playbooks/             # Плейбуки
│   │   └── proxmox-setup.yml  # Настройка Proxmox
│   └── roles/
│       └── proxmox/           # Роль Proxmox
│           ├── defaults/      # Переменные по умолчанию
│           ├── tasks/         # Задачи
│           ├── meta/          # Метаданные роли
│           └── README.md      # Документация роли
│
└── bare-metal/                # Установка на bare-metal
    ├── README.md              # Руководство по установке
    ├── answer.toml            # Конфигурация auto-install
    ├── create-usb.sh          # Скрипт создания USB
    └── post-install/          # Скрипты post-install
        ├── README.md
        ├── 01-install-terraform.sh
        ├── 02-install-ansible.sh
        ├── 03-configure-storage.sh
        ├── 04-configure-network.sh
        └── 05-init-git-repo.sh
```

## 🚀 Быстрый старт

### Вариант 1: Свежая установка (Рекомендуется)

**Для новой установки Proxmox на bare metal:**

1. **Создание загрузочного USB**
   ```bash
   cd bare-metal/
   sudo ./create-usb.sh /dev/sdX proxmox-ve_9.0-1.iso
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
   cd /root/home-lab/terraform
   cp terraform.tfvars.example terraform.tfvars
   vim terraform.tfvars  # Настройка
   terraform init
   terraform apply
   ```

6. **Конфигурация системы**
   ```bash
   cd /root/home-lab/ansible
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

Подробности в [bare-metal/README.md](bare-metal/README.md)

---

### Вариант 2: Существующий Proxmox

**Для существующей установки Proxmox:**

1. **Установка Terraform и Ansible**
   ```bash
   cd bare-metal/post-install
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
   cd /root/home-lab/terraform
   terraform init
   terraform apply

   # Ansible
   cd /root/home-lab/ansible
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

Руководство по миграции: [MIGRATION.md](MIGRATION.md)

## 🏛️ Архитектура

### Сетевая топология

```
┌──────────────────────────────────────────────────────────────────┐
│                        ISP Router (DHCP)                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ USB Ethernet     │
                    │ (eth-usb)        │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ vmbr0 (WAN)      │
                    │ DHCP             │
                    └────────┬─────────┘
                             │
         ┌───────────────────▼──────────────────────┐
         │         OPNsense Firewall VM             │
         │  WAN: vmbr0 (DHCP from ISP)              │
         │  LAN: vmbr1 (192.168.10.254/24)          │
         └───────────────────┬──────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ Built-in Ethernet│
                    │ (eth-builtin)    │
                    └────────┬─────────┘
                             │
         ┌───────────────────▼──────────────────────┐
         │       GL.iNet Slate AX Router            │
         │       192.168.10.1 (Travel/Home)         │
         │       WiFi, VPN, AdGuard                 │
         └──────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                 LXC Containers Network                           │
│               vmbr2 (10.0.30.1/24)                               │
│  ┌────────────┬────────────┬────────────┬────────────┐          │
│  │ PostgreSQL │ Redis      │ Nextcloud  │ Jellyfin   │          │
│  │ .10        │ .20        │ .30        │ .40        │          │
│  └────────────┴────────────┴────────────┴────────────┘          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                   Management Network                             │
│                 vmbr99 (10.0.99.1/24)                            │
│  ┌──────────────────────┬──────────────────────┐                │
│  │ Proxmox Web UI       │ OPNsense Web UI      │                │
│  │ 10.0.99.1:8006       │ 10.0.99.10           │                │
│  └──────────────────────┴──────────────────────┘                │
└──────────────────────────────────────────────────────────────────┘
```

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
proxmox_api_url = "https://10.0.99.1:8006/api2/json"
proxmox_api_token_id = "root@pam!terraform"
proxmox_api_token_secret = "your-token-secret"

# Node
proxmox_node_name = "pve-xps"

# Network
wan_interface = "eth-usb"
lan_interface = "eth-builtin"

# Storage
storage_ssd_id = "local-lvm"
storage_hdd_id = "local-hdd"
```

**Использование**:
```bash
cd terraform/

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
cd ansible/

# Тест подключения
ansible all -i inventory/production/hosts.yml -m ping

# Запуск плейбука
ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml

# Запуск конкретных задач
ansible-playbook ... --tags repositories

# Dry run
ansible-playbook ... --check
```

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

- **[bare-metal/README.md](bare-metal/README.md)**: Установка bare-metal
  - Создание USB
  - Конфигурация auto-install
  - Post-install скрипты

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
- [x] Базовая конфигурация Terraform
- [x] Модуль сети Terraform
- [x] Модуль хранилища Terraform
- [x] Базовая конфигурация Ansible
- [x] Роль Proxmox в Ansible
- [x] Автоматизация bare-metal установки
- [x] Документация по миграции
- [x] Процедуры тестирования

### В процессе 🔄

- [ ] Модуль VM в Terraform (OPNsense)
- [ ] Модуль LXC в Terraform (PostgreSQL, Redis, Nextcloud, и т.д.)
- [ ] Плейбуки Ansible для VMs/LXC
- [ ] Автоматизация развёртывания сервисов

### Планируется 📋

- [ ] Настройка мониторинга (Prometheus + Grafana)
- [ ] Автоматизация бэкапов
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Тестирование disaster recovery

## 📄 Лицензия

MIT

## 📞 Поддержка

- Документация по [Proxmox](https://pve.proxmox.com/wiki/)
- [Terraform Proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Ansible Proxmox Module](https://docs.ansible.com/ansible/latest/collections/community/general/proxmox_module.html)

---

**Статус проекта**: Активная разработка
**Последнее обновление**: 2025-10-06
**Сопровождение**: Home Lab Administrator
