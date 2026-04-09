# Distribution Plane Upgrade Runbook

Runbook для типового обновления framework distribution в production (artifact-first).

---

## 0. Scope and Safety

- Этот runbook применим для **artifact-first** режима (ADR0076/ADR0081).
- Все операции выполняются через distribution zip + `framework.lock.yaml`.
- Выполняйте шаги последовательно. Не пропускайте strict/trust проверки.

---

## 1. Preparation

1. Получите новый distribution артефакт `dist/framework/infra-topology-framework-<version>.zip`.
2. Убедитесь, что release notes доступны.
3. Зафиксируйте текущую версию framework и commit проекта.

---

## 2. Preflight

```bash
# Validate базовая готовность
task framework:release-preflight
```

Ожидаемый результат: без ошибок, все strict/validate/release-tests зеленые.

---

## 3. Update Framework Lock

```bash
.venv/bin/python topology-tools/generate-framework-lock.py \
  --topology topology/topology.yaml \
  --project-root . \
  --framework-dist-zip dist/framework/infra-topology-framework-<version>.zip \
  --framework-dist-version <version>
```

Проверить, что обновился `projects/<project>/framework.lock.yaml`.

---

## 4. Trust Verification

```bash
.venv/bin/python topology-tools/verify-framework-lock.py --strict
.venv/bin/python topology-tools/verify-framework-lock.py --strict --enforce-package-trust --verify-package-artifact-files --verify-package-signature
```

Ожидаемый результат: OK без критических диагностик.

---

## 5. Compile/Validate

```bash
# Полная проверка в passthrough режиме
task validate:passthrough

# Строгая компиляция
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough
```

---

## 6. Product Sanity (SOHO)

```bash
# Snapshot readiness
task product:doctor

# Handover пакет (должен быть complete)
task product:handover
```

---

## 7. Phase13 Evidence (если это cutover окно)

```bash
task framework:phase13-evidence
task framework:phase13-go-no-go
```

Проверить `build/diagnostics/phase13/summary.json` и `split-rehearsal.json`.

---

## 8. Publish and Promote

1. Закоммитьте обновленный `framework.lock.yaml`.
2. Обновите release notes (если требуется по процессу).
3. Задеплойте изменения в production pipeline.

---

## 9. Post-Upgrade Validation

```bash
# Повторить строгие проверки после обновления
task framework:strict

task validate:passthrough
```

---

## 10. Rollback Plan

Если обнаружены критические дефекты:

1. Откатить `framework.lock.yaml` на предыдущую версию.
2. Повторить strict/validate проверки.
3. Зафиксировать rollback в release notes.

---

## Outputs to Archive

- `build/diagnostics/phase13/*` (если выполнялись cutover шаги)
- `build/diagnostics/report.txt`
- `projects/<project>/framework.lock.yaml`

