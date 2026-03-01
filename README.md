# Home Lab Infrastructure as Code

Infrastructure as Code (IaC) для home lab на базе Proxmox VE 9 с использованием Terraform, Ansible и topology-driven generators.

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
- **⭐ Источник истины**: `topology/` + `topology.yaml` entry point (Infrastructure-as-Data)

### Infrastructure-as-Data подход

**Единый источник истины**: layered topology в `topology/`, подключаемая через `topology.yaml`:
- Физические интерфейсы и сетевые мосты
- IP адресация всех сетей
- Определения VM и LXC контейнеров
- Конфигурация хранилища
- Правила маршрутизации и firewall

**Автогенерация из topology**:
```cmd
:: Редактируем topology layers
notepad topology\L4-platform.yaml

:: Валидируем
python topology-tools\validate-topology.py

:: Генерируем всё и собираем runtime inventory
python topology-tools\regenerate-all.py

:: Опционально: собираем deploy packages
python topology-tools\assemble-deploy.py
python topology-tools\validate-dist.py
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
├── topology.yaml              # Entry point with !include
├── topology/                  # ⭐ ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ (layered topology)
├── topology-tools/            # ⭐ Генераторы и валидаторы
│   ├── validate-topology.py
│   ├── regenerate-all.py
│   ├── assemble-ansible-runtime.py
│   ├── assemble-deploy.py
│   ├── validate-dist.py
│   └── ...
│
├── generated/                 # ⚠️ Автогенерация (НЕ РЕДАКТИРОВАТЬ)
│   ├── terraform/             # Generated Terraform roots
│   ├── ansible/               # Raw inventory + assembled runtime
│   └── docs/                  # Документация
├── dist/                      # Deploy-ready packages and manifests
│
├── ansible/                   # Configuration management
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── inventory-overrides/
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
   python topology-tools\generate-proxmox-bootstrap.py
   mkdir local\bootstrap\srv-gamayun
   notepad local\bootstrap\srv-gamayun\answer.override.toml
   cd deploy && make materialize-native-inputs
   cd ..\generated\bootstrap\srv-gamayun
   create-uefi-autoinstall-proxmox-usb.sh C:\path\to\proxmox-ve.iso answer.toml \\.\PhysicalDriveN
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
   python topology-tools\regenerate-all.py
   python topology-tools\assemble-deploy.py
   python topology-tools\validate-dist.py

   cd deploy
   make plan-proxmox
   make apply-proxmox
   make configure
   ```

Подробности в [docs/guides/PROXMOX-USB-AUTOINSTALL.md](docs/guides/PROXMOX-USB-AUTOINSTALL.md)

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
   python topology-tools\regenerate-all.py
   python topology-tools\assemble-deploy.py

   cd deploy
   make plan-proxmox
   make apply-proxmox
   make configure
   ```

Руководство по миграции: [MIGRATION.md](MIGRATION.md)

## 📚 Документация

- **[MIGRATION.md](MIGRATION.md)**: Руководство по миграции
- **[TESTING.md](TESTING.md)**: Руководство по тестированию
- **[adr/](adr/)**: Architecture Decision Records
- **[docs/guides/DEPLOYMENT-STRATEGY.md](docs/guides/DEPLOYMENT-STRATEGY.md)**: current generate, dist, and deploy workflow
- **[docs/guides/PROXMOX-USB-AUTOINSTALL.md](docs/guides/PROXMOX-USB-AUTOINSTALL.md)**: Установка bare-metal через generated bootstrap package
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
- ✓ Сборка runtime inventory для Ansible (ADR 0051)
- ✓ Сборка `dist/` packages (ADR 0052)
- ✓ Валидация синтаксиса Ansible playbooks
- ✓ Генерация документации
- ✓ Проверка идемпотентности генераторов
- ✓ Отчет об изменениях в git

### Dist Workflow

```cmd
cd deploy
make generate
make assemble-dist
make validate-dist
make check-parity
make check-native-ready
make check-dist-ready
make materialize-dist-inputs
make clean-generated-managed
```

Что это делает:
- `make generate` обновляет generated outputs, assembled Ansible runtime и materialize-ит native local inputs из `local/`
- `make assemble-dist` собирает deploy-ready packages в `dist/`
- `make validate-dist` проверяет manifests, release-safe policy и доступные внешние validators
- `make check-parity` сравнивает `native` и `dist` execution roots для Terraform и Ansible
- `make check-native-ready` проверяет canonical local inputs для native execution
- `make check-dist-ready` проверяет, что для `dist` execution материализованы package-local local inputs
- `make materialize-native-inputs` копирует canonical local inputs из `local/` в native execution roots
- `make materialize-dist-inputs` копирует canonical local inputs из `local/` и Ansible vault inputs из `ansible/` в `dist/`
- `make clean-generated-managed` очищает reproducible managed roots в `generated/`, не трогая `local/`
- `terraform-overrides/` содержит tracked additive Terraform exceptions поверх generated baseline
- `dist/control/ansible` требует локальные `.vault_pass` и `group_vars/all/vault.yml`, но не тащит legacy `group_vars/all/vars.yml`

### Deploy Modes

`ADR 0053` вводит два явных execution mode для `deploy/`:
- `native` — текущий default, использует `generated/terraform/*` и `ansible/`
- `dist` — opt-in mode, исполняется только из `dist/control/**`

```cmd
cd deploy

:: Native workflow
make plan
make apply-proxmox
make configure

:: Dist-first workflow
make plan-dist
make materialize-dist-inputs
make check-dist-ready
make apply-mikrotik-dist
make apply-proxmox-dist
make configure-dist
make deploy-all-dist
```

В `dist` mode deploy tooling не делает fallback на native roots. Если package manifest требует локальные inputs, phase script завершится с явной ошибкой до запуска Terraform или Ansible.

Рекомендуемый цикл для `dist` mode:

```cmd
cd deploy
make generate
make assemble-dist
make validate-dist
make check-parity
make materialize-dist-inputs
make check-dist-ready
make plan-dist
```

Примечание:
- Terraform local inputs должны жить в `local/terraform/**`, затем materialize-иться в execution roots
- Proxmox bootstrap override должен жить в `local/bootstrap/srv-gamayun/answer.override.toml`
- bootstrap packages в `dist/` теперь перечисляются явно через manifests
- `generated/bootstrap/rtr-mikrotik-chateau` и `generated/bootstrap/srv-gamayun` уже materialize canonical bootstrap payloads
- если canonical generated bootstrap source ещё не готов, пакет остаётся видимым с `status=skipped`

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
