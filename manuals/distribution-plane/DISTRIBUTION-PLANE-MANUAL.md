# Distribution Plane Manual

Руководство для работы с продуктом в режиме distribution-plane: выпуск framework distribution, проверка доверия, bootstrap отдельного project-репозитория и обновление версии framework.

**Scope:** выпуск и потребление framework distribution (ADR0076/ADR0081), контроль trust metadata, project bootstrap/upgrade.

---

**Quick Links**

- `manuals/distribution-plane/COMMAND-REFERENCE.md`
- `manuals/distribution-plane/RELEASE-CHECKLIST.md`
- `manuals/distribution-plane/UPGRADE-RUNBOOK.md`
- `manuals/distribution-plane/UPGRADE-REPORT-TEMPLATE.md`
- `manuals/distribution-plane/UPGRADE-REPORT-SAMPLE.md`
- `manuals/distribution-plane/GO-NO-GO-TEMPLATE.md`
- `manuals/distribution-plane/GO-NO-GO-SAMPLE.md`
- `manuals/distribution-plane/RELEASE-LOG.md`
- `manuals/distribution-plane/RELEASE-LOG-ENTRY-SAMPLE.md`

---

**Key Concepts**

- Distribution artifact: zip-архив framework, собранный по `topology/framework.yaml`.
- Trust metadata: signature/provenance/SBOM, обязательны для strict verification в package-mode.
- Framework lock: `projects/<project>/framework.lock.yaml` фиксирует ревизию и trust metadata.
- Artifact-first: project использует framework как внешний артефакт, без доступа к исходникам.

---

**Prerequisites**

- Активная виртуальная среда `.venv`.
- Доступ к `task` и python-утилитам из `topology-tools/`.
- Наличие `framework.lock.yaml` для текущего проекта.

---

**1. Build Distribution**

Сборка release-артефакта framework по контракту distribution.

```bash
# Preflight: обновить lock + strict + validate + release-tests
task framework:release-preflight

# Сборка distribution архива
task framework:release-build FRAMEWORK_VERSION=5.0.0-rc1
```

Артефакты по умолчанию попадают в `dist/framework/`.

---

**2. Verify Distribution Trust**

Проверка подписи, provenance и целостности package-mode.

```bash
# Полная проверка trust-метаданных и подписи
task framework:verify-lock-package-trust-signature

# Локальная проверка артефактов и sha256
task framework:verify-lock-package-trust-artifacts
```

---

**3. Bootstrap Project from Distribution**

Рекомендуемый путь для нового project-репозитория.

```bash
# Инициализация standalone project из distribution zip
task project:init-from-dist -- \
  PROJECT_ROOT=build/project-bootstrap/home-lab \
  PROJECT_ID=home-lab \
  FRAMEWORK_DIST_ZIP=dist/framework/infra-topology-framework-5.0.0-rc1.zip \
  FRAMEWORK_DIST_VERSION=5.0.0-rc1
```

После bootstrap:

- Проверь `projects/<project>/framework.lock.yaml`.
- Убедись, что каталоги `topology/product-bundles` и `topology/product-profiles` присутствуют.
- Запусти строгую проверку в standalone layout.

```bash
task framework:strict
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough
```

---

**4. Project Upgrade to New Distribution**

Обновление framework версии в уже существующем project-репозитории.

```bash
# Обновить lock под новую версию framework
.venv/bin/python topology-tools/generate-framework-lock.py \
  --topology topology/topology.yaml \
  --project-root . \
  --framework-dist-zip dist/framework/infra-topology-framework-5.0.0-rc2.zip \
  --framework-dist-version 5.0.0-rc2

# Проверить strict lock + trust
.venv/bin/python topology-tools/verify-framework-lock.py --strict
.venv/bin/python topology-tools/verify-framework-lock.py --strict --enforce-package-trust --verify-package-artifact-files --verify-package-signature
```

---

**5. Cutover Evidence**

Сбор evidence-пакета и Go/No-Go решения для физического cutover.

```bash
task framework:cutover-evidence
task framework:cutover-go-no-go
```

Evidence-файлы сохраняются в `build/diagnostics/cutover/`.

---

**6. Product Task Surface (SOHO)**

Работа с продуктом через канонические `product:*` задачи.

```bash
# Инициализация baseline
task product:init

# Диагностика и readiness
task product:doctor

# Планирование изменений
task product:plan

# Применение (требует ALLOW_APPLY=YES и BUNDLE)
task product:apply BUNDLE=<bundle_id> ALLOW_APPLY=YES

# Backup/Restore проверки
task product:backup
task product:restore

# Handover пакет
task product:handover
```

---

**7. Troubleshooting**

- `E781x/E782x` в strict-режиме: запусти `task framework:lock-refresh` и повтори `task framework:strict`.
- Trust verification failures: проверь наличие signature/provenance/SBOM в артефакте, пересобери `framework:release-build`.
- Несоответствие артефактов в standalone: пересоздай проект через `project:init-from-dist` и сравни `build/diagnostics/cutover/split-rehearsal.json`.

---

**References**

- `manuals/distribution-plane/COMMAND-REFERENCE.md`
- `manuals/distribution-plane/RELEASE-CHECKLIST.md`
- `manuals/distribution-plane/UPGRADE-RUNBOOK.md`
- `manuals/distribution-plane/UPGRADE-REPORT-TEMPLATE.md`
- `manuals/distribution-plane/UPGRADE-REPORT-SAMPLE.md`
- `manuals/distribution-plane/GO-NO-GO-TEMPLATE.md`
- `manuals/distribution-plane/GO-NO-GO-SAMPLE.md`
- `manuals/distribution-plane/RELEASE-LOG.md`
- `manuals/distribution-plane/RELEASE-LOG-ENTRY-SAMPLE.md`
- `docs/framework/INFRA-TOPOLOGY-FRAMEWORK-RELEASE-PROCESS.md`
- `docs/framework/FRAMEWORK-RELEASE-GUIDE.md`
- `docs/framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md`
- `adr/plan/0076-phase13-physical-extraction-plan.md`
- `adr/plan/0081-framework-artifact-first-execution-plan.md`
