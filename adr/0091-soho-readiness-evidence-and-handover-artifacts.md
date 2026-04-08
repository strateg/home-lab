# ADR 0091: SOHO Readiness Evidence and Handover Artifacts

- Status: Proposed
- Date: 2026-04-05
- Depends on: ADR 0070, ADR 0072, ADR 0074, ADR 0080, ADR 0085, ADR 0089, ADR 0090

---

## Context

SOHO readiness cannot be asserted by successful generation alone.

Repeatable support, handover, audit, and recovery require:
- operator-facing artifacts,
- machine-readable readiness reports,
- readiness diagnostics,
- release gating based on evidence.

The framework already has deterministic generation and acceptance building blocks, but the evidence contract for SOHO readiness is not yet canonical.

---

## Problem

There is no canonical evidence contract for SOHO release readiness:

- backup/restore evidence format is undefined;
- handover package completeness is not contract-checked;
- readiness diagnostics are not normalized enough;
- release decisions are not bound to a machine-readable evidence state model.

---

## Decision

Define mandatory SOHO readiness evidence contract and handover artifact set.

### D1. Operator-facing artifact contract is mandatory

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

### D2. Readiness diagnostics namespace is reserved

- hard errors: `E7831..E7839`
- warnings: `W7831..W7839`

Initial mapping:

- `E7831` unsupported product profile
- `E7832` required lifecycle bundle missing
- `E7833` backup policy missing
- `E7834` restore evidence missing
- `E7835` handover package incomplete
- `E7836` unsupported deployment class combination

### D3. Acceptance evidence is mandatory

SOHO readiness requires evidence for:

- greenfield-first-install
- brownfield-adoption
- router-replacement
- secret-rotation
- scheduled-update
- failed-update-rollback
- backup-and-restore
- operator-handover

### D4. Evidence completeness state is normalized

Each required evidence domain is classified as:

- `missing`
- `partial`
- `complete`

Readiness status is derived as:

- `green` — no critical diagnostics, all required evidence complete
- `yellow` — no critical diagnostics, but one or more evidence domains partial
- `red` — one or more critical diagnostics or mandatory evidence missing

### D5. Release gate is normative

SOHO build/publish is blocked when any of the following is true:

- handover package is missing or incomplete;
- backup/restore evidence is missing;
- critical readiness diagnostics exist;
- required TUC evidence set is missing.

### D6. Machine-readable report contracts are required

The following contracts must exist and be versioned:

- `schemas/operator-readiness.schema.json`
- `schemas/backup-status.schema.json`
- `schemas/restore-readiness.schema.json`
- `schemas/support-bundle-manifest.schema.json`

### D7. Provenance and retention

Evidence artifacts must:
- be attributable to a specific project and build/run context,
- record generation timestamp and schema version,
- be suitable for operator handover and support review,
- support deterministic regeneration where applicable.

### D8. Secret hygiene is mandatory

Operator artifacts must satisfy ADR 0072 secret hygiene:

- no plaintext tracked secrets,
- deterministic redaction/sanitization in handover outputs,
- no unsafe leakage through summaries, reports, or manifests.

### D9. Invariants

- Product readiness claims must be evidence-backed.
- Handover completeness must be machine-checkable.
- Readiness state must be derivable from machine-readable reports.
- Sanitization must be deterministic and repeatable.

---

## Out of scope

This ADR does not define:
- product profile/bundle contract — see ADR 0089
- operator lifecycle/task namespace — see ADR 0090

---

## Consequences

### Positive
- Product claims become evidence-backed and auditable.
- Handover quality becomes measurable and repeatable.
- Recovery and incident workflows become contract-driven.
- Release readiness becomes machine-checkable.

### Trade-offs
- More generated artifacts to maintain.
- Higher acceptance-test and evidence upkeep cost.
- More schema/version management.

### Risks
- Artifact completeness may degrade into checklist theater without strict gates.
- Overly loose redaction rules can leak sensitive context.
- Evidence drift can appear if schemas and producers evolve independently.

### Mitigations
- Make readiness blocking for release.
- Version evidence schemas explicitly.
- Couple evidence generation to acceptance/build stages.
- Test sanitization and completeness rules in CI.

---

## Decision summary

Adopt a mandatory SOHO readiness evidence contract with explicit operator-facing artifacts, diagnostics, completeness states, and release-blocking readiness rules.
