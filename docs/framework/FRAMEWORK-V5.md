# Framework V5: Руководство

**Статус:** Production-ready
**Последнее обновление:** 2026-03-20
**Связанные ADR:** 0074, 0075, 0076

---

## 1. Что такое framework в v5

В v5 framework — это общая часть платформы, независимая от конкретного стенда.

Framework включает:

- компилятор и plugin runtime (`topology-tools/`)
- class/object модули (`topology/class-modules`, `topology/object-modules`)
- контракты и каталоги (`model.lock`, `layer-contract`, capability catalog/packs)
- общие шаблоны генерации Terraform/Ansible/bootstrap

Framework **не включает** проектные данные (instance shards, secrets, project overrides).

---

## 2. Граница framework vs project

### Framework (общий код и модель)

- `topology/topology.yaml` (секции `framework` и `project`)
- `topology/**`
- `topology-tools/**`

### Project (экземпляры и runtime-состояние)

- `projects/<project>/project.yaml`
- `projects/<project>/instances/**`
- `projects/<project>/secrets/**`
- `projects/<project>/ansible/inventory-overrides/**`

---

## 3. Контракт манифестов

### 3.1 Topology manifest

Файл: `topology/topology.yaml`

Обязательные секции:

- `framework:` пути к class/object/modules/contract данным
- `project:` `active` + `projects_root`

Legacy-секция `paths:` запрещена. При наличии выдается `E7808`.

### 3.2 Project manifest

Файл: `projects/<project>/project.yaml`

Ключевые поля:

- `instances_root`
- `secrets_root`
- `project` (идентификатор проекта)
- `project_schema_version`

---

## 4. Пути генерации и runtime

Генераторы пишут только в project-qualified roots:

- `generated/<project>/terraform/...`
- `generated/<project>/ansible/...`
- `generated/<project>/bootstrap/...`

Ansible runtime assembly:

- generated input: `generated/<project>/ansible/inventory/<env>`
- manual overrides: `projects/<project>/ansible/inventory-overrides/<env>`
- runtime output: `generated/<project>/ansible/runtime/<env>`

---

## 5. Секреты и аннотации

Секреты хранятся в project scope:

- `projects/<project>/secrets/instances/*.yaml`
- `projects/<project>/secrets/terraform/*.yaml`
- `projects/<project>/secrets/ansible/*.yaml`

Разрешение секретов выполняется plugin-компиляторами:

- `base.compiler.annotation_resolver`
- `base.compiler.instance_rows`

Режимы:

- `passthrough` — без расшифровки
- `inject` — с подстановкой расшифрованных значений
- `strict` — жесткий режим для secret-annotated unresolved путей

---

## 6. Стандартные команды

### Task-first orchestration (ADR0077)

```powershell
task framework:strict
task framework:release-preflight
task framework:release-candidate FRAMEWORK_VERSION=1.0.8
```

### Валидация lane

```powershell
$env:V5_SECRETS_MODE='passthrough'
python scripts/orchestration/lane.py validate-v5
```

### Полная компиляция + генерация

```powershell
python topology-tools/compile-topology.py `
  --repo-root . `
  --topology topology/topology.yaml `
  --strict-model-lock `
  --secrets-mode passthrough `
  --artifacts-root v5-generated
```

Для external project-репозитория через submodule:

```powershell
if (Test-Path .\framework\topology-tools\compile-topology.py) {
  $frameworkTools = ".\framework\topology-tools"
  $frameworkManifest = ".\framework\framework.yaml"
} else {
  $frameworkTools = ".\framework\v5\topology-tools"
  $frameworkManifest = ".\framework\v5\topology\framework.yaml"
}

python "$frameworkTools/verify-framework-lock.py" `
  --repo-root . `
  --project-root . `
  --project-manifest .\project.yaml `
  --framework-root .\framework `
  --framework-manifest "$frameworkManifest" `
  --lock-file .\framework.lock.yaml `
  --strict

python "$frameworkTools/compile-topology.py" `
  --repo-root . `
  --topology .\topology.yaml `
  --secrets-mode passthrough
```

### Сборка ansible runtime inventory

```powershell
python topology-tools/assemble-ansible-runtime.py `
  --topology topology/topology.yaml `
  --project home-lab `
  --env production
```

### Генерация patch-шаблонов hardware identity

```powershell
python topology-tools/discover-hardware-identity.py `
  --topology topology/topology.yaml `
  --project home-lab
```

### Сборка framework distribution

```powershell
task framework:release-build FRAMEWORK_VERSION=1.0.8
task framework:release-bootstrap

python topology-tools/build-framework-distribution.py `
  --version 1.0.0 `
  --archive-format both

python topology-tools/extract-framework-worktree.py `
  --output-root build/framework-extract `
  --include-tests `
  --force

python topology-tools/extract-framework-history.py `
  --output-root build/infra-topology-framework-history `
  --include-tests `
  --force

python topology-tools/bootstrap-framework-repo.py `
  --output-root build/infra-topology-framework-bootstrap `
  --include-tests `
  --preserve-history `
  --force
```

### Генерация и проверка framework lock

```powershell
python topology-tools/generate-framework-lock.py --force
python topology-tools/verify-framework-lock.py --strict
python topology-tools/rehearse-framework-rollback.py
python topology-tools/validate-framework-compatibility-matrix.py
python topology-tools/audit-strict-runtime-entrypoints.py
python topology-tools/cutover-readiness-report.py --quick
```

`compile-topology.py` в strict-runtime выполняет ту же проверку lock автоматически перед загрузкой модулей.
Подробный dry-run до production cutover: `docs/framework/CUTOVER-DRY-RUN-RUNBOOK.md`.

---

## 7. Добавление нового проекта

1. Создать `projects/<new-project>/project.yaml`.
2. Создать директории:
   - `instances/`
   - `secrets/`
   - `ansible/inventory-overrides/production/`
3. Переключить `project.active` в `topology/topology.yaml`.
4. Запустить `lane.py validate-v5`.
5. Прогнать компиляцию с `--artifacts-root` и проверить `generated/<new-project>/...`.

Или использовать bootstrap helper:

```powershell
python topology-tools/bootstrap-project-repo.py `
  --framework-root . `
  --output-root build/project-bootstrap/new-project `
  --project-id new-project `
  --seed-project-root projects/home-lab `
  --init-git `
  --framework-submodule-url https://github.com/<org>/infra-topology-framework.git `
  --framework-submodule-path framework `
  --force
```

---

## 8. Диагностики и troubleshooting

Ключевые ошибки контрактного уровня:

- `E7808`: обнаружен legacy `paths.*` в topology manifest
- `E7104`: неверный формат версии shard (`version: 1.0.0` обязателен)
- `E7101/E7108/E7109`: нарушение shard path/id contract
- `E7208/E7210`: strict secrets unresolved paths
- `E7824`: `framework.lock.yaml` не совпадает с текущим содержимым framework

Быстрые исправления:

- `E7824`:
  `python topology-tools/generate-framework-lock.py --force`
  затем
  `python topology-tools/verify-framework-lock.py --strict`
- `E7200` (`Failed to execute sops`):
  установить `sops` и `age` из `topology-tools/docs/ENVIRONMENT-SETUP.md`;
  для dry-run без локального decrypt использовать `--secrets-mode passthrough`.
- `git remote add origin ...` -> `remote origin already exists`:
  использовать `git remote set-url origin <url>` (или удалить/переименовать текущий remote).
- Push отклонен ошибкой GitHub `without 'workflow' scope` при изменении `.github/workflows/*`:
  переавторизоваться токеном с правом `workflow` и повторить push.
- Push по SSH с `Permission denied (publickey)`:
  добавить SSH key в GitHub и использовать `git@github.com:<org>/<repo>.git`.

Полный каталог:

- `docs/diagnostics-catalog.md`

---

## 9. Ограничения текущей стадии

- ADR0076/ADR0077 уже являются operational baseline.
- Для релизного процесса `infra-topology-framework` использовать
  `docs/framework/INFRA-TOPOLOGY-FRAMEWORK-RELEASE-PROCESS.md`.
- Framework рассчитан на strict-only path/model contract без legacy fallback.

---

## 10. Связанные документы

- `adr/0075-framework-project-separation.md`
- `adr/0074-v5-generator-architecture.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `topology-tools/docs/ENVIRONMENT-SETUP.md`
- `topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`
- `docs/release-notes/2026-03-20-v5-framework-project-cutover.md`
- `docs/framework/SUBMODULE-ROLL-OUT.md`
- `docs/framework/OPERATOR-WORKFLOWS.md`
- `docs/framework/CUTOVER-DRY-RUN-RUNBOOK.md`
- `docs/framework/INFRA-TOPOLOGY-FRAMEWORK-RELEASE-PROCESS.md`
- `docs/framework/templates/framework-release.yml`
