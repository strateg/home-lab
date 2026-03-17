# Подготовка Среды Исполнения `topology-tools` (Linux / Windows)

Этот документ описывает минимальную подготовку среды для запуска:

- `v5/topology-tools/compile-topology.py`
- режима секретов `--secrets-mode inject|strict` (SOPS + age)

## 1. Базовые требования

- Python 3.11+ (рекомендуется 3.12+)
- Доступ к репозиторию `home-lab`
- Для `inject/strict`: установленный `sops` и `age`-совместимый инструмент

Проверка:

```bash
python --version
```

## 2. Linux (Ubuntu/Debian)

### 2.1 Установка `age`

```bash
sudo apt update
sudo apt install -y age curl
age --version
age-keygen --version
```

### 2.2 Установка `sops`

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

`rage` и `rage-keygen` полностью подходят для SOPS age-бэкенда.

Проверка после перезапуска PowerShell:

```powershell
sops --version
rage --version
rage-keygen --version
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

## 5. Проверка `topology-tools`

Из корня репозитория:

```powershell
python v5/topology-tools/compile-topology.py --secrets-mode passthrough
python v5/topology-tools/compile-topology.py --secrets-mode inject
```

Ожидаемо:

- `passthrough` работает без SOPS-ключей.
- `inject` требует корректную установку `sops` и доступ к age-ключу.

## 6. Официальные источники

- SOPS: https://github.com/getsops/sops
- age (rage): https://github.com/age-sops/age
- WinGet install: https://learn.microsoft.com/windows/package-manager/winget/install
