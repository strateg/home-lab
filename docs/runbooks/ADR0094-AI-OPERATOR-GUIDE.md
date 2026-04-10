# ADR0094 AI Operator Guide

**Status:** Active  
**Updated:** 2026-04-07  
**Scope:** Advisory/assisted AI generation flow (`compile-topology.py`)

---

## 1. Operating Modes

- `--ai-advisory`: read-only, recommendations only, no artifact mutation.
- `--ai-assisted`: candidate artifacts in sandbox, human approval required for promotion.

Both modes:
- run only `discover, compile, validate` stages,
- emit audit events to `.work/ai-audit/<project>/<YYYY-MM-DD>/ai-advisory-audit.jsonl`,
- use sandbox at `.work/ai-sandbox/<project>/<request_id>/`.

---

## 2. Standard Commands

```bash
task generate:ai-advisory
task generate:ai-assisted
```

With external AI payload:

```bash
task generate:ai-advisory -- AI_OUTPUT_JSON=/tmp/ai-output.json
task generate:ai-assisted -- AI_OUTPUT_JSON=/tmp/ai-output.json
```

Promote approved candidates:

```bash
task generate:ai-assisted-promote -- AI_OUTPUT_JSON=/tmp/ai-output.json AI_APPROVE_PATHS=generated/home-lab/docs/overview.md
```

Promote all valid candidates:

```bash
task generate:ai-assisted-promote -- AI_OUTPUT_JSON=/tmp/ai-output.json AI_APPROVE_ALL=true
```

---

## 3. Audit Review Process

Minimum review cadence: weekly (recommended daily for active AI usage windows).

1. Confirm audit chain integrity:
```bash
python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "topology-tools")
from plugins.generators.ai_audit import verify_ai_audit_log_integrity
for p in sorted(Path(".work/ai-audit").rglob("ai-advisory-audit.jsonl")):
    ok, reason = verify_ai_audit_log_integrity(p)
    print(f"{'OK' if ok else 'FAIL'} {p} {reason}")
PY
```
2. Review `event_type` sequence per request (`ai_request_sent`, `ai_response_received`, promotion/rollback events).
3. Record anomalies in incident log and attach log file path + request_id.

---

## 4. Incident Response (Secrets Exposure Suspicion)

Trigger examples:
- suspected secret-like payload in AI input/output,
- suspicious audit event payload content,
- external report of leaked token/password/key.

Containment:
1. Stop AI runs (`--ai-advisory`/`--ai-assisted`) for affected branch/environment.
2. Preserve evidence: copy relevant audit logs and sandbox session to incident bundle.
3. Rotate potentially exposed credentials.

Recovery:
1. Roll back AI-promoted files if needed (`task generate:ai-assisted-rollback`).
2. Re-run `task validate:default` and required project gates.
3. Re-enable AI mode only after root-cause and redaction rule update.

Post-incident:
1. Add or tighten redaction paths/patterns.
2. Add regression test reproducing the leak vector.
3. Document incident timeline and closure criteria.

---

## 5. Opt-in Usage Metrics

AI metrics are opt-in and derived from local audit logs only.

```bash
python3 scripts/validation/report_ai_usage_metrics.py --output-json build/diagnostics/ai-usage-metrics.json
```

No network export is performed by this script.
