# infra-topology-framework Release Process

**Status:** Active  
**Updated:** 2026-03-21  
**ADRs:** 0076, 0077

---

## Scope

Документ фиксирует релизный процесс `infra-topology-framework` после:

1. ADR0076 (multi-repo distribution + lock/trust contract),
2. ADR0077 (Task-first developer orchestration).

Пошаговая операторская инструкция: `docs/framework/FRAMEWORK-RELEASE-GUIDE.md`.

---

## Release Principles

1. Release candidate в source monorepo проходит strict-gates ADR0076 (`E781x/E782x` блокируют выпуск).
2. Локальный preflight запускается через `task` (ADR0077).
3. CI-релиз работает в режиме `task-first` с явным fallback на legacy commands.
4. Каждый релиз публикует обязательные артефакты доверия: `checksums`, `signature`, `certificate`, `SBOM`, `provenance`.

---

## Local Pre-Release (Source Monorepo)

Из корня `home-lab`:

```powershell
task framework:release-preflight
task framework:release-build FRAMEWORK_VERSION=1.0.8
task framework:release-bootstrap
```

Или единым прогоном:

```powershell
task framework:release-candidate FRAMEWORK_VERSION=1.0.8
```

Что делает pipeline:

1. `framework:release-preflight` -> v5 lane validate + strict lock gates + framework-focused tests.
2. `framework:release-build` -> сборка дистрибутива (`zip`, `tar.gz`, `checksums`, dist manifest).
3. `framework:release-bootstrap` -> подготовка standalone `infra-topology-framework` кандидата с release workflow шаблоном.

Артефакты по умолчанию:

1. `v5-dist/framework/<framework-id>/<version>/...`
2. `v5-build/infra-topology-framework-bootstrap/...`

---

## CI Release Pipeline (Framework Repo)

Шаблон workflow: `docs/framework/templates/framework-release.yml`.

Триггеры:

1. `push` tag `v*` (канонический production release),
2. `workflow_dispatch` (ручной прогон; для не-tag запуска обязателен input `version`).

Порядок шагов:

1. Resolve framework layout (`extracted` vs `monorepo-style`).
2. Resolve release version (`vX.Y.Z` -> `X.Y.Z`).
3. Preflight gates (`task framework:release-ci`, fallback на legacy chain).
4. Build distribution (`task framework:release-build`, fallback на script).
5. Generate SBOM.
6. Generate provenance placeholder (заменяется на реальную attestation при подключении полноценной provenance pipeline).
7. Sign checksum blob (`cosign`).
8. Verify release bundle completeness и подпись checksum blob.
9. Upload workflow artifacts.
10. Publish GitHub Release assets (только для tag-run).

---

## Post-Release Consumption (Project Repo)

Для `home-lab`/другого project repo:

1. Обновить framework submodule до нового tag/revision.
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

Для package-based onboarding нового проекта можно использовать:

```powershell
task project:init-from-dist -- PROJECT_ROOT=D:/work/new-project PROJECT_ID=home-lab FRAMEWORK_DIST_ZIP=D:/artifacts/infra-topology-framework-1.0.8.zip FRAMEWORK_DIST_VERSION=1.0.8
```

---

## Release Checklist (Go/No-Go)

Go:

1. `task framework:release-preflight` passed.
2. Release artifact set complete (`zip`, `tar.gz`, `checksums`, `.sig`, `.crt`, `framework-dist-manifest.json`, `sbom.spdx.json`, `provenance.json`).
3. CI tag workflow green.

No-Go:

1. Любая ошибка strict-gates (`E781x/E782x`).
2. Отсутствует любой trust-артефакт.
3. Не прошла verify-step подписи checksum blob.

---

## Rollback / Hotfix

1. Для rollback релиза framework: выпуск следующего patch tag с revert/fix (не переписывать историю tag).
2. Для project rollback: вернуть submodule pointer + перегенерировать lock + strict verify/compile.
3. Перед rollback в change-window запускать:

```powershell
task framework:rollback-rehearsal
```
