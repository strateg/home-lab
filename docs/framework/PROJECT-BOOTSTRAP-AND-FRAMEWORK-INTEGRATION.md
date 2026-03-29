# Руководство: создание проекта и подключение framework

**Статус:** Active
**Updated:** 2026-03-29
**ADR:** 0076, 0081

---

## Цель

Документ описывает, как создать отдельный project-репозиторий, подключить framework (через submodule или distribution zip) и выполнить совместную компиляцию в strict-flow.

---

## One-shot инициализация (новый скрипт)

Рекомендуемый путь (ADR0081): `artifact-first` через distribution zip.
Submodule-подключение оставлено как legacy/rollback режим.

Если нужен сразу готовый skeleton с каталогами `L0..L7`, подключенным framework и compile-check:

```powershell
python topology-tools/utils/init-project-repo.py `
  --output-root D:/work/new-project `
  --project-id home-lab `
  --framework-dist-zip D:/artifacts/infra-topology-framework-1.0.8.zip `
  --framework-dist-version 1.0.8 `
  --force
```

Что делает скрипт:

1. Инициализирует git-репозиторий в `--output-root`.
2. Подключает `framework` как artifact dependency (распаковка zip в `./framework`).
3. Генерирует `topology.yaml`, `project.yaml`, `framework.lock.yaml`.
4. Создает структуру каталогов `instances/L0-meta ... instances/L7-operations` + group-каталоги из `layer-contract.yaml`.
5. Добавляет минимальный compilable starter profile.
6. Выполняет `verify-framework-lock --strict` и `compile-topology` (если не задан `--skip-compile-check`).

Legacy-режим (submodule) при необходимости:

```powershell
python topology-tools/utils/init-project-repo.py `
  --output-root D:/work/new-project `
  --project-id home-lab `
  --framework-submodule-url https://github.com/<org>/infra-topology-framework.git `
  --force
```

---

## Сценарий: новый пустой репозиторий + отдельный `infra-topology-framework`

Ниже copy-paste последовательность для случая, когда вы начинаете с пустой папки.

### 0) Предпосылки

1. Установлены `git` и `python` (>= 3.11).
2. Есть URL/путь к `infra-topology-framework`.

### 1) Создать новый проект-репозиторий

```powershell
mkdir D:/work/home-lab-project
cd D:/work/home-lab-project
git init
```

### 2) Подключить framework как submodule

```powershell
git submodule add https://github.com/<org>/infra-topology-framework.git framework
git submodule update --init --recursive
```

### 3) Установить минимальные Python-зависимости

```powershell
python -m pip install --upgrade pip
python -m pip install pyyaml jsonschema jinja2
```

### 4) Сгенерировать каркас проекта

```powershell
python framework/topology-tools/utils/bootstrap-project-repo.py `
  --framework-root ./framework `
  --output-root . `
  --project-id home-lab `
  --force
```

После команды появятся:

1. `topology.yaml`
2. `project.yaml`
3. `framework.lock.yaml`
4. `instances/`, `secrets/`, `overrides/`, `generated/`
5. `BOOTSTRAP-NOTES.md`

### 5) Strict-проверка lock

```powershell
python framework/topology-tools/verify-framework-lock.py `
  --repo-root . `
  --project-root . `
  --project-manifest ./project.yaml `
  --framework-root ./framework `
  --framework-manifest ./framework/framework.yaml `
  --lock-file ./framework.lock.yaml `
  --strict
```

### 6) Совместная компиляция framework + project

```powershell
python framework/topology-tools/compile-topology.py `
  --repo-root . `
  --topology ./topology.yaml `
  --secrets-mode passthrough `
  --strict-model-lock `
  --output-json ./generated/effective-topology.json `
  --diagnostics-json ./generated/diagnostics.json `
  --diagnostics-txt ./generated/diagnostics.txt `
  --artifacts-root ./generated-artifacts
```

---

## Вариант по умолчанию (рекомендуется)

Используйте модель:

```text
project-repo/
├── framework/              # framework artifact (zip unpack / package dependency)
├── topology.yaml
├── project.yaml
├── framework.lock.yaml
├── instances/
├── secrets/
└── overrides/
```

---

## Быстрый старт через bootstrap утилиту

```powershell
python framework/topology-tools/utils/bootstrap-project-repo.py `
  --framework-root D:/path/to/infra-topology-framework `
  --output-root D:/path/to/new-project-repo `
  --project-id home-lab `
  --seed-project-root D:/path/to/existing-project-root `
  --force
```

Что будет создано:

1. `topology.yaml`, `project.yaml`, `framework.lock.yaml`
2. каталоги `instances/`, `secrets/`, `overrides/`, `generated/`
3. `.github/workflows/validate.yml` (из шаблона, если доступен)
4. `BOOTSTRAP-NOTES.md` с командами strict-gates

---

## Ручное подключение framework (если без bootstrap утилиты)

```powershell
git init
git submodule add https://github.com/<org>/infra-topology-framework.git framework
git submodule update --init --recursive
```

После этого вручную создайте `topology.yaml`/`project.yaml` и сгенерируйте `framework.lock.yaml` через `generate-framework-lock.py`.

---

## Совместная компиляция (framework + project)

### Шаг 1: strict-проверка lock

```powershell
python framework/topology-tools/verify-framework-lock.py `
  --repo-root . `
  --project-root . `
  --project-manifest project.yaml `
  --framework-root framework `
  --framework-manifest framework/framework.yaml `
  --lock-file framework.lock.yaml `
  --strict
```

### Шаг 2: компиляция topology

```powershell
python framework/topology-tools/compile-topology.py `
  --repo-root . `
  --topology ./topology.yaml `
  --secrets-mode passthrough `
  --strict-model-lock
```

---

## Обновление framework в проекте

1. Обновить framework dependency:
   - рекомендуемо: установить новый artifact в `./framework`;
   - legacy: обновить submodule pointer до нужной ревизии/tag.
2. Перегенерировать lock:
   - `python framework/topology-tools/generate-framework-lock.py --project-root . --project-manifest project.yaml --framework-root framework --framework-manifest framework/framework.yaml --lock-file framework.lock.yaml --force`
3. Прогнать `verify-framework-lock --strict` и `compile-topology`.
4. Коммитить изменение framework dependency + `framework.lock.yaml` в одном PR.

---

## Типовые ошибки

1. `E7822` — lock не найден: проверьте `framework.lock.yaml`.
2. `E7823` — ревизия lock не совпадает с framework: обновите lock.
3. `E7824` — integrity mismatch: lock устарел или framework изменён вне ожидаемого потока.
4. `E7811/E7812/E7813` — несовместимость версий/контракта: обновите framework или project contract.

---

## Связанные документы

- `docs/framework/SUBMODULE-ROLL-OUT.md`
- `docs/framework/OPERATOR-WORKFLOWS.md`
- `docs/framework/CUTOVER-DRY-RUN-RUNBOOK.md`
- `docs/framework/templates/project-validate.yml`
