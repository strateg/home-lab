# Framework Release Guide (infra-topology-framework)

**Status:** Active  
**Updated:** 2026-03-21  
**ADRs:** 0076, 0077

---

## 1. Цель и границы

Гайд описывает выпуск новой версии `infra-topology-framework`:

1. локальная проверка кандидата релиза;
2. запуск релизного workflow по тегу `vX.Y.Z`;
3. проверка обязательных trust-артефактов;
4. обновление project-repo (`framework.lock.yaml` + submodule pointer);
5. rollback/hotfix процедура.

---

## 2. Prerequisites

Перед релизом:

1. Чистое рабочее дерево (`git status` пустой).
2. Установлены `python`, `task`, `git`.
3. `task --version` >= `3.45.4`.
4. Пройден локальный quality gate.

Проверка:

```powershell
git status --short
task --version
```

---

## 3. Local Release Candidate

### 3.1 Синхронизировать lock перед preflight

```powershell
task framework:lock-refresh
```

### 3.2 Полный preflight

```powershell
task framework:release-preflight
```

Включает:

1. lock refresh (`framework:lock-refresh`)
2. v5 lane validate (`validate:v5-passthrough`)
3. ADR0076 strict gates (`framework:strict`)
4. framework-focused release tests (`framework:release-tests`)

### 3.3 Сборка релизного дистрибутива

```powershell
task framework:release-build FRAMEWORK_VERSION=1.0.8
```

Ожидаемые файлы:

1. `v5-dist/framework/<framework-id>/1.0.8/*.zip`
2. `v5-dist/framework/<framework-id>/1.0.8/*.tar.gz`
3. `v5-dist/framework/<framework-id>/1.0.8/checksums.sha256`
4. `v5-dist/framework/<framework-id>/1.0.8/framework-dist-manifest.json`

### 3.4 Подготовка standalone framework repo кандидата

```powershell
task framework:release-bootstrap
```

Проверить:

1. `v5-build/infra-topology-framework-bootstrap/framework.yaml`
2. `v5-build/infra-topology-framework-bootstrap/topology-tools/`
3. `v5-build/infra-topology-framework-bootstrap/.github/workflows/release.yml`

### 3.5 Один агрегированный запуск

```powershell
task framework:release-candidate FRAMEWORK_VERSION=1.0.8
```

---

## 4. Release Tag and CI

### 4.1 Создать и отправить tag

```powershell
git tag v1.0.8
git push origin v1.0.8
```

### 4.2 Workflow, который должен отработать

`docs/framework/templates/framework-release.yml`:

1. task-first preflight (fallback на legacy chain);
2. build distribution;
3. SBOM;
4. provenance;
5. checksum signing (`cosign`);
6. verify completeness/signature;
7. upload artifacts + publish GitHub Release assets.

---

## 5. Release Artifacts Checklist

В published release должны быть:

1. `*.zip`
2. `*.tar.gz`
3. `checksums.sha256`
4. `checksums.sha256.sig`
5. `checksums.sha256.crt`
6. `framework-dist-manifest.json`
7. `sbom.spdx.json`
8. `provenance/provenance.json`

No-Go:

1. отсутствует любой из файлов выше;
2. CI verify-step не прошел;
3. есть unresolved `E781x/E782x`.

---

## 6. Post-Release in Project Repo

После публикации framework:

1. Обновить submodule до нужного tag/revision.
2. Перегенерировать lock:

```powershell
python framework/topology-tools/generate-framework-lock.py --project-root . --project-manifest .\project.yaml --framework-root .\framework --framework-manifest .\framework\framework.yaml --force
```

3. Проверить strict lock + compile:

```powershell
python framework/topology-tools/verify-framework-lock.py --repo-root . --project-root . --project-manifest .\project.yaml --framework-root .\framework --framework-manifest .\framework\framework.yaml --lock-file .\framework.lock.yaml --strict
python framework/topology-tools/compile-topology.py --repo-root . --topology .\topology.yaml --secrets-mode passthrough
```

4. Закоммитить submodule pointer + `framework.lock.yaml` одним PR.

### 6.1 Bootstrap нового project repo из zip-артефакта

```powershell
task project:init-from-dist -- PROJECT_ROOT=D:/work/new-project PROJECT_ID=home-lab FRAMEWORK_DIST_ZIP=D:/artifacts/infra-topology-framework-1.0.8.zip FRAMEWORK_DIST_VERSION=1.0.8
```

Результат:

1. framework распакован в `new-project/framework/`;
2. `framework.lock.yaml` использует `framework.source: package`;
3. проект готов к strict verify/compile без git submodule.

---

## 7. Rollback / Hotfix

### 7.1 Framework rollback policy

1. Не переписывать уже опубликованный tag.
2. Выпускать новый patch release (`vX.Y.(Z+1)`) с revert/fix.

### 7.2 Project rollback policy

1. Вернуть submodule pointer на предыдущую ревизию.
2. Перегенерировать `framework.lock.yaml`.
3. Прогнать strict verify + compile.

Проверка rollback-пути:

```powershell
task framework:rollback-rehearsal
```

---

## 8. Типовые проблемы

1. `E7824 integrity mismatch`: обновить lock (`generate-framework-lock.py --force`).
2. `task` не найден в текущей shell: использовать новый терминал или полный путь к `task.exe`.
3. CI release без tag и без `version` input: workflow завершится ошибкой (ожидаемо).

---

## 9. Связанные документы

1. `docs/framework/INFRA-TOPOLOGY-FRAMEWORK-RELEASE-PROCESS.md`
2. `docs/framework/templates/framework-release.yml`
3. `docs/framework/OPERATOR-WORKFLOWS.md`
4. `adr/0076-framework-distribution-and-multi-repository-extraction.md`
5. `adr/0077-go-task-developer-orchestration.md`
