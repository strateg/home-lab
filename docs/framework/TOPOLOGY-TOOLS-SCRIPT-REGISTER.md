# topology-tools Script Register

**Статус:** normative register для ADR 0081 §2.3
**Дата:** 2026-03-29
**Назначение:** единый реестр, чтобы человек и AI одинаково понимали ответственность каждого script/module и его принадлежность к framework artifact.

## Правила

1. `Artifact = MUST` — компонент обязателен в framework runtime artifact (TRE).
2. `Artifact = MUST NOT` — компонент относится к framework source/development и не должен быть runtime-зависимостью project execution.
3. Реестр описывает **должное состояние**; фактическая упаковка проверяется отдельными artifact-content контрактами.

## Runtime Entry Points (TRE)

| Script | Ответственность | Stage / роль | Artifact |
|---|---|---|---|
| `topology-tools/compile-topology.py` | Основной orchestrator pipeline, исполнение discover/compile/validate/generate/assemble/build цепочки | runtime compile orchestration | MUST |
| `topology-tools/check-capability-contract.py` | Проверка capability contract class/object модулей | runtime contract gate | MUST |
| `topology-tools/assemble-ansible-runtime.py` | Сборка runtime inventory для Ansible из generated + overrides | runtime assemble | MUST |
| `topology-tools/generate-framework-lock.py` | Генерация `framework.lock.yaml` | runtime dependency lock | MUST |
| `topology-tools/verify-framework-lock.py` | Верификация lock/integrity/compatibility (+ package trust/signature опционально) перед compile | runtime dependency verify | MUST |

## Runtime Support Modules (TRE)

| Module | Ответственность | Artifact |
|---|---|---|
| `topology-tools/compiler_contract.py` | Контракт compiled model + digest helpers | MUST |
| `topology-tools/compiler_decisions.py` | Политики выбора effective payload | MUST |
| `topology-tools/compiler_ownership.py` | Ownership policy core vs plugin | MUST |
| `topology-tools/compiler_plugin_context.py` | Конструирование `PluginContext` | MUST |
| `topology-tools/compiler_reporting.py` | Сортировка/summary/emit diagnostics | MUST |
| `topology-tools/compiler_runtime.py` | Runtime helpers загрузки/применения compile inputs/outputs | MUST |
| `topology-tools/framework_lock.py` | Общая логика lock generation/verification | MUST |
| `topology-tools/plugin_manifest_discovery.py` | Детерминированный discovery manifests (base→class→object→project) | MUST |
| `topology-tools/field_annotations.py` | Парсер/реестр field annotations | MUST |
| `topology-tools/capability_derivation.py` | Shared capability derivation helpers | MUST |
| `topology-tools/identifier_policy.py` | Политики идентификаторов и filename safety | MUST |

## Framework Source Only (Not TRE Runtime)

| Script / module | Ответственность | Artifact |
|---|---|---|
| `topology-tools/utils/build-framework-distribution.py` | Сборка release artifact по `framework.yaml` | MUST NOT |
| `topology-tools/utils/generate-framework-provenance.py` | Генерация provenance attestation payload по release bundle | MUST NOT |
| `topology-tools/utils/bootstrap-framework-repo.py` | Bootstrap standalone framework repo из monorepo | MUST NOT |
| `topology-tools/utils/extract-framework-history.py` | Историческое extraction с сохранением git history | MUST NOT |
| `topology-tools/utils/extract-framework-worktree.py` | Быстрый framework-only export worktree | MUST NOT |
| `topology-tools/utils/init-project-repo.py` | Инициализация нового project repo scaffold | MUST NOT |
| `topology-tools/utils/bootstrap-project-repo.py` | Bootstrap project repo из seed + framework dependency wiring | MUST NOT |
| `topology-tools/utils/cutover-readiness-report.py` | Cutover readiness gates/report | MUST NOT |
| `topology-tools/utils/rehearse-framework-rollback.py` | Репетиция rollback lock/dependency flow | MUST NOT |
| `topology-tools/utils/validate-framework-compatibility-matrix.py` | Матрица совместимости framework/project contracts | MUST NOT |
| `topology-tools/utils/audit-strict-runtime-entrypoints.py` | Аудит strict-only runtime entrypoints (no legacy fallback) | MUST NOT |
| `topology-tools/utils/discover-hardware-identity.py` | Генерация patch templates для hardware identity capture | MUST NOT |
| `topology-tools/utils/split-instance-bindings.py` | Миграция legacy instance-bindings в sharded instances | MUST NOT |
| `topology-tools/utils/bootstrap-phase1-mapping.py` | Bootstrap v4→v5 Phase 1 mapping inventory | MUST NOT |
| `topology-tools/utils/record-service-chain-evidence.py` | CLI entrypoint evidence flow (wrapper) | MUST NOT |
| `topology-tools/utils/service_chain_evidence.py` | Реализация service-chain evidence execution/reporting | MUST NOT |
| `topology-tools/utils/validate-mermaid-render.py` | Проверка Mermaid render в generated docs | MUST NOT |

## Directory Boundary

| Path | Роль | Artifact |
|---|---|---|
| `topology-tools/kernel/` | Plugin microkernel contracts/runtime | MUST |
| `topology-tools/plugins/` | Base plugins manifests + implementations | MUST |
| `topology-tools/schemas/` | Runtime schemas | MUST |
| `topology-tools/templates/` | Runtime generation templates | MUST |
| `topology-tools/data/` | Runtime static data (diagnostics, formats) | MUST |
| `topology-tools/utils/` | Source-only utilities (bootstrap/migration/cutover/evidence) | MUST NOT |
| `topology-tools/docs/` | Development/operational documentation | MUST NOT |

## Source of Truth

1. Архитектурное правило: `adr/0081-framework-runtime-artifact-and-1-n-project-repository-model.md` (§2.3).
2. Distribution spec: `topology/framework.yaml`.
3. Этот реестр — операционный список для людей/AI при изменении `topology-tools`.
