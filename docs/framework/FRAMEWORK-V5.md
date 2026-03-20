# Framework V5: Руководство

**Статус:** Production-ready  
**Последнее обновление:** 2026-03-20  
**Связанные ADR:** 0074, 0075, 0076

---

## 1. Что такое framework в v5

В v5 framework — это общая часть платформы, независимая от конкретного стенда.

Framework включает:

- компилятор и plugin runtime (`v5/topology-tools/`)
- class/object модули (`v5/topology/class-modules`, `v5/topology/object-modules`)
- контракты и каталоги (`model.lock`, `layer-contract`, capability catalog/packs)
- общие шаблоны генерации Terraform/Ansible/bootstrap

Framework **не включает** проектные данные (instance shards, secrets, project overrides).

---

## 2. Граница framework vs project

### Framework (общий код и модель)

- `v5/topology/topology.yaml` (секции `framework` и `project`)
- `v5/topology/**`
- `v5/topology-tools/**`

### Project (экземпляры и runtime-состояние)

- `v5/projects/<project>/project.yaml`
- `v5/projects/<project>/instances/**`
- `v5/projects/<project>/secrets/**`
- `v5/projects/<project>/ansible/inventory-overrides/**`

---

## 3. Контракт манифестов

### 3.1 Topology manifest

Файл: `v5/topology/topology.yaml`

Обязательные секции:

- `framework:` пути к class/object/modules/contract данным
- `project:` `active` + `projects_root`

Legacy-секция `paths:` запрещена. При наличии выдается `E7808`.

### 3.2 Project manifest

Файл: `v5/projects/<project>/project.yaml`

Ключевые поля:

- `instances_root`
- `secrets_root`
- `project` (идентификатор проекта)
- `project_schema_version`

---

## 4. Пути генерации и runtime

Генераторы пишут только в project-qualified roots:

- `v5-generated/<project>/terraform/...`
- `v5-generated/<project>/ansible/...`
- `v5-generated/<project>/bootstrap/...`

Ansible runtime assembly:

- generated input: `v5-generated/<project>/ansible/inventory/<env>`
- manual overrides: `v5/projects/<project>/ansible/inventory-overrides/<env>`
- runtime output: `v5-generated/<project>/ansible/runtime/<env>`

---

## 5. Секреты и аннотации

Секреты хранятся в project scope:

- `v5/projects/<project>/secrets/instances/*.yaml`
- `v5/projects/<project>/secrets/terraform/*.yaml`
- `v5/projects/<project>/secrets/ansible/*.yaml`

Разрешение секретов выполняется plugin-компиляторами:

- `base.compiler.annotation_resolver`
- `base.compiler.instance_rows`

Режимы:

- `passthrough` — без расшифровки
- `inject` — с подстановкой расшифрованных значений
- `strict` — жесткий режим для secret-annotated unresolved путей

---

## 6. Стандартные команды

### Валидация lane

```powershell
$env:V5_SECRETS_MODE='passthrough'
python v5/scripts/lane.py validate-v5
```

### Полная компиляция + генерация

```powershell
python v5/topology-tools/compile-topology.py `
  --topology v5/topology/topology.yaml `
  --strict-model-lock `
  --secrets-mode passthrough `
  --artifacts-root v5-generated
```

### Сборка ansible runtime inventory

```powershell
python v5/topology-tools/assemble-ansible-runtime.py `
  --topology v5/topology/topology.yaml `
  --project home-lab `
  --env production
```

### Генерация patch-шаблонов hardware identity

```powershell
python v5/topology-tools/discover-hardware-identity.py `
  --topology v5/topology/topology.yaml `
  --project home-lab
```

### Сборка framework distribution

```powershell
python v5/topology-tools/build-framework-distribution.py `
  --version 1.0.0 `
  --archive-format both
```

### Генерация и проверка framework lock

```powershell
python v5/topology-tools/generate-framework-lock.py --force
python v5/topology-tools/verify-framework-lock.py --strict
python v5/topology-tools/rehearse-framework-rollback.py
```

`compile-topology.py` в strict-runtime выполняет ту же проверку lock автоматически перед загрузкой модулей.

---

## 7. Добавление нового проекта

1. Создать `v5/projects/<new-project>/project.yaml`.
2. Создать директории:
   - `instances/`
   - `secrets/`
   - `ansible/inventory-overrides/production/`
3. Переключить `project.active` в `v5/topology/topology.yaml`.
4. Запустить `lane.py validate-v5`.
5. Прогнать компиляцию с `--artifacts-root` и проверить `v5-generated/<new-project>/...`.

---

## 8. Диагностики и troubleshooting

Ключевые ошибки контрактного уровня:

- `E7808`: обнаружен legacy `paths.*` в topology manifest
- `E7104`: неверный формат версии shard (`version: 1.0.0` обязателен)
- `E7101/E7108/E7109`: нарушение shard path/id contract
- `E7208/E7210`: strict secrets unresolved paths

Полный каталог:

- `docs/diagnostics-catalog.md`

---

## 9. Ограничения текущей стадии

- ADR0076 multi-repository extraction не входит в этот runtime contract.
- Framework рассчитан на strict-only path/model contract без legacy fallback.

---

## 10. Связанные документы

- `adr/0075-framework-project-separation.md`
- `adr/0074-v5-generator-architecture.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `v5/topology-tools/docs/ENVIRONMENT-SETUP.md`
- `v5/topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`
- `docs/release-notes/2026-03-20-v5-framework-project-cutover.md`
- `docs/framework/SUBMODULE-ROLL-OUT.md`
- `docs/framework/OPERATOR-WORKFLOWS.md`
