# Distribution Plane Upgrade Report (Template)

Заполните после выполнения upgrade по runbook.

---

## 1. Summary

- **Date:** YYYY-MM-DD
- **Operator:** <name/role>
- **Project:** <project_id>
- **Framework Version (from):** <version>
- **Framework Version (to):** <version>
- **Change Window:** <window id>
- **Decision:** GO | NO-GO

---

## 2. Inputs

- **Distribution Zip:** `dist/framework/infra-topology-framework-<version>.zip`
- **Commit (before):** <git sha>
- **Commit (after):** <git sha>
- **Lock File Updated:** `projects/<project>/framework.lock.yaml`

---

## 3. Preflight Results

- `task framework:release-preflight`: PASS | FAIL
- `task framework:strict`: PASS | FAIL
- `task validate:passthrough`: PASS | FAIL
- `task framework:release-tests`: PASS | FAIL

Notes:
- <details>

---

## 4. Trust Verification

- `verify-framework-lock --strict`: PASS | FAIL
- `verify-framework-lock --strict --enforce-package-trust --verify-package-artifact-files --verify-package-signature`: PASS | FAIL

Notes:
- <details>

---

## 5. Compile/Validate

- `compile-topology --strict-model-lock --secrets-mode passthrough`: PASS | FAIL
- Diagnostics report: `build/diagnostics/report.txt`

Notes:
- <details>

---

## 6. Product Sanity (SOHO)

- `task product:doctor`: PASS | FAIL
- `task product:handover`: PASS | FAIL

Notes:
- <details>

---

## 7. Phase13 Evidence (если применимо)

- `task framework:phase13-evidence`: PASS | FAIL
- `task framework:phase13-go-no-go`: GO | NO-GO
- Evidence: `build/diagnostics/phase13/summary.json`

Notes:
- <details>

---

## 8. Publication

- Release notes updated: YES | NO
- Production pipeline updated: YES | NO

---

## 9. Post-Upgrade Validation

- `task framework:strict`: PASS | FAIL
- `task validate:passthrough`: PASS | FAIL

---

## 10. Rollback (if any)

- Rollback executed: YES | NO
- Rollback reason:
- Actions taken:

---

## 11. Attachments

- `build/diagnostics/report.txt`
- `build/diagnostics/phase13/*` (if applicable)
- `projects/<project>/framework.lock.yaml`

