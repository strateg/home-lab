# Distribution Plane Release Checklist

Чеклист для выпуска framework distribution и обновления project-репозитория.

---

## A. Preflight

- [ ] `task framework:release-preflight` завершен без ошибок.
- [ ] `task framework:strict` зеленый.
- [ ] `task validate:passthrough` зеленый.
- [ ] `task framework:release-tests` зеленый.
- [ ] `projects/<project>/framework.lock.yaml` обновлен и закоммичен.

---

## B. Build & Trust

- [ ] `task framework:release-build FRAMEWORK_VERSION=...` выполнен.
- [ ] Артефакт доступен в `dist/framework/`.
- [ ] `task framework:verify-lock-package-trust-signature` проходит.
- [ ] `task framework:verify-lock-package-trust-artifacts` проходит.

---

## C. Bootstrap/Upgrade Validation

Для нового project:
- [ ] `task project:init-from-dist` выполнен с целевым `FRAMEWORK_DIST_ZIP`.
- [ ] `task framework:strict` зеленый в standalone layout.
- [ ] `compile-topology --strict-model-lock --secrets-mode passthrough` без ошибок.

Для существующего project:
- [ ] `generate-framework-lock.py` обновил lock на новую версию.
- [ ] `verify-framework-lock --strict` зеленый.
- [ ] Trust verification проходит.

---

## D. Phase13 (если cutover)

- [ ] `task framework:phase13-evidence` сформировал evidence пакет.
- [ ] `task framework:phase13-go-no-go` вернул `GO`.
- [ ] `build/diagnostics/phase13/summary.json` сохранен.

---

## E. Publication

- [ ] Release notes подготовлены.
- [ ] Версия framework опубликована.
- [ ] Project dependency обновлен на новую версию.

---

## F. Post-Release

- [ ] `task framework:strict` зеленый на целевом проекте.
- [ ] `task validate:passthrough` зеленый на целевом проекте.
- [ ] Evidence и отчеты заархивированы.

