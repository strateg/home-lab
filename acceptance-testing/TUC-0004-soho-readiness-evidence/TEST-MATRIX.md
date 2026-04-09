# Test Matrix

| ID | Scenario | Type | Input | Expected | Status |
|---|---|---|---|---|---|
| T1 | Doctor reads operator-readiness report first | integration | `operator-readiness.json` present | `status` and `source=operator-readiness` | implemented |
| T2 | Doctor fallback to profile-state evidence | integration | operator report absent, `product-profile-state.json` present | `source=product-profile-state` | implemented |
| T3 | Doctor red when no evidence | negative | no evidence files | `status=red` | implemented |
| T4 | Handover check passes on full package | integration | complete handover/reports files | exit code 0 | implemented |
| T5 | Handover check fails when file missing | negative | remove mandatory handover file | non-zero exit | implemented |
| T6 | SOHO readiness builder emits reports/package | integration | build-stage inputs with readiness evidence | package exists in `generated/<project>/product/` | implemented |
| T7 | SOHO readiness builder blocks on missing restore/backup evidence | negative | no readiness evidence payload | `E7943`, `E7944` emitted | implemented |
| T8 | Sanitization guard for handover placeholders | security | generated handover templates | no secret-like tokens | implemented |
| T9 | ADR0091 evidence domain mapping coverage | governance | TUC + tests + scripts | all D3 domains have mapped artifacts/checks | implemented |
