# ADR 0091: SOHO Readiness Evidence and Handover Artifacts

- Status: Implemented (complete)
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
generated/<project>/product/
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

Deploy-bundle mapping:

- in bundle mode, these artifacts are copied under `artifacts/generated/<project>/product/...` without semantic changes.

#### Artifact validation scope

| Artifact type | Validation method | Scope |
|---|---|---|
| **JSON reports** (`reports/*.json`) | Schema-validated per ADR 0091 D6 | Full structural validation |
| **Markdown artifacts** (`handover/*.md`) | Presence + non-empty check | Operator-facing, not schema-validated |
| **CSV artifacts** (`handover/*.csv`) | Header structure check | Column names validated, content operator responsibility |

Handover completeness check (ADR 0091 D5) verifies:

1. All required files present (filename check)
2. JSON reports pass schema validation
3. Markdown/CSV files are non-empty and have expected structure (header/frontmatter presence)

Quality assurance for Markdown/CSV content is operator responsibility during handover review.

### D2. Readiness diagnostics namespace is reserved

- hard errors: `E7941..E7949`
- warnings: `W7941..W7949`

Initial mapping:

- `E7941` unsupported product profile
- `E7942` required lifecycle bundle missing
- `E7943` backup policy missing
- `E7944` restore evidence missing
- `E7945` handover package incomplete
- `E7946` unsupported deployment class combination

### D3. Acceptance evidence is mandatory

SOHO readiness requires documented evidence for the following acceptance scenarios:

- **greenfield-first-install** — initial deployment to new hardware
- **brownfield-adoption** — migration from existing network
- **router-replacement** — hardware swap without topology change
- **secret-rotation** — key/password rotation procedure
- **scheduled-update** — routine update workflow
- **failed-update-rollback** — rollback after failed update
- **backup-and-restore** — backup creation and restore drill
- **operator-handover** — knowledge transfer and runbook validation

Each evidence domain must have:
- procedure documentation
- execution logs or artifacts
- validation checkpoints
- last-execution timestamp

Evidence domains map to lifecycle phases (ADR 0090 D1) and must cover all operator-facing workflows.

### D4. Evidence completeness state is normalized

Each required evidence domain is classified as:

- `missing` — no evidence artifacts exist
- `partial` — evidence exists but fails quality/recency criteria
- `complete` — evidence exists and meets all quality/recency criteria

#### Evidence state criteria (deterministic)

| Evidence Domain | Missing | Partial | Complete |
|---|---|---|---|
| **greenfield-first-install** | No installation logs/artifacts | Install evidence > 90 days old OR missing validation checkpoints | Fresh install evidence < 90 days + all checkpoints passed |
| **brownfield-adoption** | No migration evidence | Migration evidence > 90 days old OR incomplete cutover checklist | Migration evidence < 90 days + cutover checklist 100% |
| **router-replacement** | No replacement procedure docs | Procedure exists but not tested OR last test > 180 days | Procedure tested < 180 days + runbook validated |
| **secret-rotation** | No rotation logs | Last rotation > 180 days OR incomplete rotation checklist | Last rotation < 90 days + all secrets rotated |
| **scheduled-update** | No update logs | Last successful update > 90 days OR update failed | Last successful update < 60 days + release notes archived |
| **failed-update-rollback** | No rollback evidence | Rollback procedure exists but not tested OR test > 180 days | Rollback drill passed < 180 days + runbook validated |
| **backup-and-restore** | No backup exists | Backup > 7 days old OR no restore drill OR drill > 30 days | Valid backup < 7 days + restore drill passed < 30 days |
| **operator-handover** | No handover package | Package exists but missing ≥1 required artifact (ADR 0091 D1) | All D1 artifacts present + schema-validated + reviewed |

**Quality criteria:**

- **Recency**: Time-based thresholds ensure evidence is current
- **Completeness**: All required artifacts/checkpoints present
- **Validation**: Evidence has been tested/verified (not just documented)

**Machine readability:**

Evidence state must be derivable from:

- File timestamps (for recency checks)
- JSON report fields (for validation status)
- Artifact inventory (for completeness checks)

No subjective operator interpretation required.

#### Readiness status derivation

Readiness status is derived as:

- `green` — no critical diagnostics, all required evidence complete
- `yellow` — no critical diagnostics, but one or more evidence domains partial
- `red` — one or more critical diagnostics or mandatory evidence missing

### D5. Release gate is normative

SOHO build/publish is blocked when any of the following is true:

- handover package is missing or incomplete;
- backup/restore evidence is missing;
- critical readiness diagnostics exist;
- required acceptance evidence (ADR 0091 D3) is incomplete.

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

Operator artifacts must satisfy ADR 0072 secret hygiene discipline:

- no plaintext tracked secrets in handover outputs,
- deterministic redaction/sanitization in summaries, reports, and manifests,
- no unsafe leakage through logs or diagnostic artifacts.

#### Sanitization rules (ADR 0072 compliance)

| Secret type | Sanitization rule | Example output |
|---|---|---|
| Passwords / Passphrases | Full redaction | `[REDACTED]` |
| API tokens / keys | First 4 chars + ellipsis | `sk_test...` (from `sk_test_abc123xyz`) |
| IP addresses (internal) | Preserve subnet, mask host | `10.0.10.xxx` (from `10.0.10.42`) |
| SSH keys | Key type + fingerprint only | `ssh-ed25519 SHA256:abc...` |
| Age public keys | Full key (safe to expose) | `age1abc...` |
| Age private keys | Never include | `[PRIVATE KEY REDACTED]` |

**Enforcement:**

- Sanitization must be applied during artifact generation, not as post-processing
- Handover package completeness check (ADR 0091 D5) must verify no plaintext secrets leaked
- Violation of secret hygiene blocks release (same severity as missing evidence)

**Reference:** ADR 0072 for full secret management discipline.

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
