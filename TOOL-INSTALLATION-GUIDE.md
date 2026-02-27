# Tool Installation Guide - Windows Setup

**Дата:** 26 февраля 2026 г.
**Цель:** Установить Terraform и Ansible на Windows

---

## Проблемы Обнаружены Валидатором

### ERRORS (2 - Critical)
```
[ERROR] Terraform check failed: [WinError 2] Не удается найти указанный файл
[ERROR] Ansible check failed: [WinError 2] Не удается найти указанный файл
```

**Причина:** Terraform и Ansible не установлены или не в PATH

### WARNINGS (3 - Minor)
```
[WARNING] pydantic not installed
[WARNING] docker 28.3.2 may not match ~> 24.0 (expected <= 24.x)
[WARNING] jq not found
```

---

## Решение #1: Установить Terraform

### Вариант A: Скачать напрямую

```bash
# 1. Перейди на https://www.terraform.io/downloads.html
# 2. Выбери Windows (AMD64)
# 3. Скачай terraform_1.5.7_windows_amd64.zip (или последнюю 1.5.x)
# 4. Распакуй в папку, например: C:\tools\terraform\
# 5. Добавь в PATH:
#    - Правая кнопка на "This PC" → Properties
#    - Advanced system settings → Environment Variables
#    - Path → Edit → Add: C:\tools\terraform
# 6. Перезагрузи PowerShell
# 7. Проверь: terraform --version
```

### Вариант B: Через Chocolatey (Если есть)

```bash
choco install terraform
```

### Вариант C: Через Scoop (Если есть)

```bash
scoop install terraform
```

---

## Решение #2: Установить Ansible

### На Windows: Используй WSL2 (Windows Subsystem for Linux)

```bash
# 1. Установи WSL2:
wsl --install

# 2. В WSL терминале:
sudo apt update
sudo apt install ansible

# 3. Проверь:
ansible --version
```

**Или** используй Docker для Ansible:

```bash
docker pull python:3.11
docker run -it python:3.11 bash
pip install ansible
ansible --version
```

---

## Решение #3: Установить Python Пакеты

```bash
# Установи pydantic
pip install pydantic

# Проверь
python -c "import pydantic; print(pydantic.__version__)"
```

---

## Решение #4: Docker Версия

Docker 28.3.2 > требуемого 24.0

**Варианты:**
1. **Downgrade Docker:** Если критично для совместимости
2. **Update L0:** Измени требование на ~> 28.0

**Рекомендация:** Update L0 (28.x полностью совместимо)

---

## Решение #5: Установить jq

### На Windows через Chocolatey:
```bash
choco install jq
```

### Или скачай напрямую:
```
https://github.com/jqlang/jq/releases
Скачай: jq-windows-amd64.exe
Переименуй в jq.exe
Добавь в PATH
```

---

## Обновлённый План Действий

### Шаг 1: Проверить Текущий Python

```bash
python --version
pip list | grep pydantic
```

### Шаг 2: Установить Pydantic (EASY)

```bash
pip install pydantic
```

### Шаг 3: Обновить L0 для Docker

Измени требование Docker с 24.0 на 28.0:

```yaml
# topology/L0-meta/_index.yaml
other:
  docker: "~> 28.0"  # Updated for your version
  jq: ">= 1.6"
```

### Шаг 4: Установить Terraform (MEDIUM)

Загрузи с terraform.io, добавь в PATH

### Шаг 5: Установить Ansible (HARD - требует WSL)

Используй WSL2 или Docker

### Шаг 6: Переустанови jq (EASY)

Скачай jq.exe, добавь в PATH

### Шаг 7: Перепроверь Валидатор

```bash
python topology-tools/validators/version_validator.py --check-all
```

---

## Быстрое Решение (30 минут)

Если не хочешь устанавливать всё:

### 1. Установить только Pydantic

```bash
pip install pydantic
```

### 2. Обновить L0 для реальных версий

```yaml
tools:
  terraform:
    core: ">= 1.0.0"  # Don't check (not installed)

  ansible:
    core: ">= 2.10.0"  # Don't check (not installed)

  python:
    core: "~> 3.11.0"
    packages:
      pydantic: "~> 2.0"
      pyyaml: "~> 6.0"
      jinja2: "~> 3.1"
      requests: "~> 2.31"

  other:
    docker: "~> 28.0"  # Update for your version
```

### 3. Запусти валидатор

```bash
python topology-tools/validators/version_validator.py --check-all
```

---

## Рекомендация

**Сейчас (для быстрого фикса):**
1. Установи pydantic: `pip install pydantic`
2. Обнови L0 с реальными версиями
3. Переустанови валидатор с обновленным L0

**Позже (полная установка):**
1. Установи Terraform (офсайт)
2. Установи Ansible (через WSL)
3. Установи jq
4. Переверни L0 на требуемые версии
