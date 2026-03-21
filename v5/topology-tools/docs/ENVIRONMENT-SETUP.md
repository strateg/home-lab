# Подготовка Среды Исполнения `topology-tools` (Linux / Windows)

Этот документ описывает минимальную подготовку среды для запуска:

- `v5/topology-tools/compile-topology.py`
- режима секретов `--secrets-mode inject|strict` (SOPS + age)

## 1. Базовые требования

- Python 3.11+ (рекомендуется 3.12+)
- Доступ к репозиторию `home-lab`
- Для `inject/strict`: установленный `sops` и `age`-совместимый инструмент
- Для orchestration ADR0077: установленный `go-task` (`task`)
- Минимальная поддерживаемая версия `go-task`: `3.45.4` (в CI зафиксирована та же версия)

Проверка:

```bash
python --version
```

## 1.1 Автоматический setup (рекомендуется)

Linux/macOS:

```bash
./v5/scripts/environment/setup-dev-environment.sh
```

Windows (PowerShell):

```powershell
./v5/scripts/environment/setup-dev-environment.ps1
```

Скрипты устанавливают `sops`, `age/rage`, `task` и Python dev-зависимости (`pip install -e .[dev]`).

## 2. Linux (Ubuntu/Debian)

### 2.1 Установка `age`

```bash
sudo apt update
sudo apt install -y age curl
age --version
age-keygen --version
```

### 2.3 Установка `task` (go-task)

```bash
sudo apt install -y go-task || true
task --version
```

Если установленная версия ниже `3.45.4`, используйте установочный скрипт c pinned-версией:

```bash
TASK_VERSION=3.45.4 ./v5/scripts/environment/setup-dev-environment.sh
```

Если пакет `go-task` отсутствует в репозитории, используйте `./v5/scripts/environment/setup-dev-environment.sh`.

### 2.4 Установка `sops`

Вариант с фиксированной версией (пример):

```bash
SOPS_VERSION="3.11.0"
curl -Lo /tmp/sops "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64"
sudo install -m 0755 /tmp/sops /usr/local/bin/sops
rm /tmp/sops
sops --version
```

## 3. Windows (PowerShell)

### 3.1 Установка `sops`

```powershell
winget install --id SecretsOPerationS.SOPS -e --accept-package-agreements --accept-source-agreements
```

### 3.2 Установка age-совместимого инструмента

```powershell
winget install --id str4d.rage -e --accept-package-agreements --accept-source-agreements
```

### 3.3 Установка `task`

```powershell
winget install --id Task.Task -e --accept-package-agreements --accept-source-agreements
```

`rage` и `rage-keygen` полностью подходят для SOPS age-бэкенда.

Проверка после перезапуска PowerShell:

```powershell
sops --version
rage --version
rage-keygen --version
task --version
```

## 4. Файл ключа для SOPS age

### Linux/macOS

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force "$env:APPDATA\sops\age" | Out-Null
rage-keygen -o "$env:APPDATA\sops\age\keys.txt"
```

При необходимости явно задайте путь:

```powershell
$env:SOPS_AGE_KEY_FILE = "$env:APPDATA\sops\age\keys.txt"
```

## 5. Рабочие скрипты secret workflow (Linux / Windows)

Скрипты в `scripts/` теперь доступны в двух вариантах:

- Linux/macOS (`bash`): `*.sh`
- Windows (`PowerShell`): `*.ps1`

Разблокировка ключа:

```bash
./v5/scripts/secrets/unlock-secrets.sh
```

```powershell
./v5/scripts/secrets/unlock-secrets.ps1
```

Блокировка ключа:

```bash
./v5/scripts/secrets/lock-secrets.sh
```

```powershell
./v5/scripts/secrets/lock-secrets.ps1
```

Recovery unlock:

```bash
./v5/scripts/secrets/unlock-secrets-recovery.sh
```

```powershell
./v5/scripts/secrets/unlock-secrets-recovery.ps1
```

Генерация terraform tfvars из SOPS:

```bash
./v5/scripts/terraform/generate-tfvars.sh proxmox
```

```powershell
./v5/scripts/terraform/generate-tfvars.ps1 proxmox
```

## 6. Проверка `topology-tools`

Из корня репозитория:

```powershell
python v5/topology-tools/compile-topology.py --secrets-mode passthrough
python v5/topology-tools/compile-topology.py --secrets-mode inject
```

Ожидаемо:

- `passthrough` работает без SOPS-ключей.
- `inject` требует корректную установку `sops` и доступ к age-ключу.
- В `inject/strict` секретные поля резолвятся по аннотациям (`@secret`, `@*_secret:<type>`) через `base.compiler.annotation_resolver`.
- Типовые несоответствия расшифрованных значений возвращают диагностику `E7213`; конфликт plaintext vs side-car — `E7212`.
- `make validate-v5` использует `inject` по умолчанию (через `v5/scripts/orchestration/lane.py`).
  Для локального override можно задать `V5_SECRETS_MODE=passthrough`.

## 7. Официальные источники

- SOPS: https://github.com/getsops/sops
- age (rage): https://github.com/age-sops/age
- WinGet install: https://learn.microsoft.com/windows/package-manager/winget/install
