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
- **⭐ Источник истины**: `topology.yaml` (Infrastructure-as-Data)

### Infrastructure-as-Data подход

**Единый источник истины**: `topology.yaml` — YAML файл, описывающий всю инфраструктуру:
- Физические интерфейсы и сетевые мосты
- IP адресация всех сетей
- Определения VM и LXC контейнеров
- Конфигурация хранилища
- Правила маршрутизации и firewall

**Автогенерация из topology.yaml**:
```cmd
:: Редактируем топологию
notepad topology.yaml

:: Валидируем
python topology-tools\validate-topology.py --topology topology.yaml

:: Генерируем Terraform конфигурации
python topology-tools\generate-terraform-proxmox.py --topology topology.yaml --output generated\terraform\proxmox
python topology-tools\generate-terraform-mikrotik.py --topology topology.yaml --output generated\terraform\mikrotik

:: Генерируем Ansible inventory
python topology-tools\generate-ansible-inventory.py --topology topology.yaml --output generated\ansible

:: Генерируем документацию (диаграммы, таблицы IP)
python topology-tools\generate-docs.py --topology topology.yaml --output generated\docs
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
├── topology.yaml              # ⭐ ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ
├── topology-tools/            # ⭐ Генераторы и валидаторы
│   ├── validate-topology.py
│   ├── generate-terraform-proxmox.py
│   ├── generate-terraform-mikrotik.py
│   ├── generate-ansible-inventory.py
│   ├── generate-docs.py
│   └── scripts/generators/    # Реализация генераторов
│
├── generated/                 # ⚠️ Автогенерация (НЕ РЕДАКТИРОВАТЬ)
│   ├── terraform/             # Terraform конфиги
│   ├── ansible/               # Ansible inventory
│   └── docs/                  # Документация
│
├── terraform/                 # Модули Terraform (источники/шаблоны)
├── ansible/                   # Configuration management
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── inventory/
│   ├── playbooks/
│   └── roles/
│
├── manual-scripts/            # Скрипты установки/обслуживания
│   ├── bare-metal/
│   └── post-install/
│
├── old_system/                # Script-based система (legacy, archived)
└── archive/                   # Архивы legacy кода
```

## 🚀 Быстрый старт

### Вариант 1: Свежая установка (Рекомендуется)

**Для новой установки Proxmox на bare metal:**

1. **Создание загрузочного USB**
   ```cmd
   cd manual-scripts\bare-metal
   run-create-usb.sh
   ```

2. **Установка Proxmox**
   - Загрузитесь с USB на Dell XPS L701X
   - Автоустановка завершится (~15 минут)
   - Система перезагрузится

3. **Запуск Post-Install скриптов**
   ```cmd
   cd manual-scripts\bare-metal\post-install
   01-install-terraform.sh
   02-install-ansible.sh
   03-configure-storage.sh
   04-configure-network.sh
   05-init-git-repo.sh
   ```

4. **Генерация и применение IaC**
   ```cmd
   python topology-tools\validate-topology.py --topology topology.yaml
   python topology-tools\generate-terraform-proxmox.py --topology topology.yaml --output generated\terraform\proxmox
   python topology-tools\generate-ansible-inventory.py --topology topology.yaml --output generated\ansible

   cd terraform
   terraform init
   terraform apply

   cd ..\ansible
   ansible-playbook playbooks\proxmox-setup.yml
   ```

Подробности в [manual-scripts/bare-metal/README.md](manual-scripts/bare-metal/README.md)

---

### Вариант 2: Существующий Proxmox

**Для существующей установки Proxmox:**

1. **Установка Terraform и Ansible**
   ```cmd
   cd manual-scripts\bare-metal\post-install
   01-install-terraform.sh
   02-install-ansible.sh
   ```

2. **Генерация и применение**
   ```cmd
   python topology-tools\generate-terraform-proxmox.py --topology topology.yaml --output generated\terraform\proxmox
   python topology-tools\generate-ansible-inventory.py --topology topology.yaml --output generated\ansible

   cd terraform
   terraform init
   terraform apply

   cd ..\ansible
   ansible-playbook playbooks\proxmox-setup.yml
   ```

Руководство по миграции: [MIGRATION.md](MIGRATION.md)

## 📚 Документация

- **[MIGRATION.md](MIGRATION.md)**: Руководство по миграции
- **[TESTING.md](TESTING.md)**: Руководство по тестированию
- **[adr/](adr/)**: Architecture Decision Records
- **[manual-scripts/bare-metal/README.md](manual-scripts/bare-metal/README.md)**: Установка bare-metal
- **[GENERATORS_REFACTORING_INDEX.md](GENERATORS_REFACTORING_INDEX.md)**: Документы по рефакторингу генераторов

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

```cmd
bash topology-tools/test-regeneration.sh
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

**Статус проекта**: Активная разработка (v3.0) | Generators refactoring Phase 2 ✅ Complete
**Последнее обновление**: 2026-02-26
**Сопровождение**: Home Lab Administrator
