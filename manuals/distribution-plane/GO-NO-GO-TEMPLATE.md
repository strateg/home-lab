# Distribution Plane Go/No-Go Record (Template)

Заполняется перед публикацией/продвижением релиза.

---

## 1. Decision

- **Date:** YYYY-MM-DD
- **Decision:** GO | NO-GO
- **Approvers:** <name/role>, <name/role>
- **Change Window:** <window id>

---

## 2. Evidence Summary

- **Strict gates:** PASS | FAIL
- **Release tests:** PASS | FAIL
- **Trust verification:** PASS | FAIL
- **Phase13 evidence (if applicable):** GO | NO-GO | N/A

---

## 3. Evidence Links

- `build/diagnostics/report.txt`
- `build/diagnostics/phase13/summary.json`
- `build/diagnostics/phase13/split-rehearsal.json`
- `projects/<project>/framework.lock.yaml`

---

## 4. Risks / Notes

- <notes>

---

## 5. Next Actions

- [ ] Promote release to production pipeline
- [ ] Update release notes
- [ ] Archive evidence bundle

