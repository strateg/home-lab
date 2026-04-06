# ADR 0091: SOHO Readiness Evidence and Handover Artifacts

- Status: Proposed
- Date: 2026-04-05
- Depends on: ADR 0070, ADR 0072, ADR 0074, ADR 0080, ADR 0085, ADR 0089, ADR 0090

---

## Context

SOHO readiness needs objective evidence, not only successful generation.  
Operator-facing outputs and machine-readable readiness reports are required for repeatable support and handover.

---

## Problem

There is no canonical evidence contract for SOHO release readiness:

- backup/restore evidence format is undefined;
- handover package completeness is not contract-checked;
- product diagnostics range for readiness is missing.

---

## Decision

Define mandatory SOHO readiness evidence contract and handover artifact set.

### 1. Operator-facing artifact contract

Generated in product output scope:

```text
artifacts/<project>/
  handover/
    SYSTEM-SUMMARY.md
    NETWORK-SUMMARY.md
    ACCESS-RUNBOOK.md
    BACKUP-RUNBOOK.md
    RESTORE-RUNBOOK.md
    UPDATE-RUNBOOK.md
    INCIDENT-CHECKLIST.md
    ASSET-INVENTORY.csv
    CHANGELOG-SNAPSHOT.md
  reports/
    health-report.json
    drift-report.json
    backup-status.json
    restore-readiness.json
    support-bundle-manifest.json
```

### 2. Product readiness diagnostics range

- hard errors: `E7831..E7839`
- warnings: `W7831..W7839`

Initial mapping:

- `E7831` unsupported product profile
- `E7832` required lifecycle bundle missing
- `E7833` backup policy missing
- `E7834` restore evidence missing
- `E7835` handover package incomplete
- `E7836` unsupported deployment class combination

### 3. Acceptance evidence is mandatory

SOHO readiness requires evidence for:

- greenfield-first-install
- brownfield-adoption
- router-replacement
- secret-rotation
- scheduled-update
- failed-update-rollback
- backup-and-restore
- operator-handover

### 4. Release gate (normative)

SOHO build/publish is blocked when any of the following is missing:

- complete handover package
- backup/restore evidence
- critical readiness diagnostics
- required TUC evidence set

### 5. Security rule

Operator artifacts must satisfy ADR0072 secret hygiene:

- no plaintext tracked secrets
- deterministic redaction/sanitization in handover outputs

---

## Consequences

### Positive

- Product claims become evidence-backed and auditable.
- Handover quality becomes measurable and repeatable.
- Incident and recovery workflows become contract-driven.

### Trade-offs

- More generated artifacts to maintain.
- Higher acceptance-test and evidence upkeep cost.

