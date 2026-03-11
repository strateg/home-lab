# ADR 0070: Acceptance Testing TUC Framework

- Status: Accepted
- Date: 2026-03-11
- Related: ADR 0062, ADR 0063, ADR 0066, ADR 0069, ADR 0071

## Context

The project is moving to plugin-first topology compilation and needs repeatable acceptance-level scenarios that validate end-to-end behavior:

1. class/object/instance modeling
2. plugin discovery and execution
3. compile/validate/generate pipeline outputs
4. deterministic diagnostics and artifacts

Acceptance artifacts were previously scattered across ADR analysis folders and ad-hoc notes, making execution and evidence tracking inconsistent.

## Decision

Introduce a dedicated Acceptance Testing structure based on **Testing Use Case (TUC)** folders.

### 1. Canonical Root

All acceptance use cases live under:

- `acceptance-testing/`

### 2. One Folder Per Use Case

Each use case is stored in:

- `acceptance-testing/TUC-XXXX-short-name/`

Where:

- `XXXX` is a zero-padded sequence
- `short-name` is lowercase kebab-case

### 3. Mandatory Use Case Artifacts

Each TUC folder must contain:

1. `TUC.md` (scope, objective, acceptance criteria, risks)
2. `IMPLEMENTATION-PLAN.md`
3. `TEST-MATRIX.md`
4. `EVIDENCE-LOG.md`
5. `artifacts/` (outputs, logs, reports)

### 4. Reusable Template

Provide a reusable template at:

- `acceptance-testing/TUC-TEMPLATE/`

New TUCs are created by copying this template and filling metadata/content.

### 5. Co-location Rule

All plans, implementation notes, and evidence for a specific acceptance scenario must remain inside its TUC folder. Do not split TUC execution artifacts across ADR analysis directories.

### 6. Initial Seed Use Case

Create first scenario:

- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/`

for router-to-router data-channel modeling on plugin-first pipeline.

### 7. Execution Evidence Contract

Each TUC must capture evidence for:

1. positive compile path (`effective*.json` + diagnostics),
2. negative validation checks (automated tests and/or diagnostics),
3. determinism report (at minimum: comparison policy and result),
4. regression gate (`pytest` suites or equivalent).

Evidence files are stored under the same TUC `artifacts/` folder.

## Consequences

### Positive

1. Acceptance scenarios become discoverable and executable from one place.
2. Evidence traceability improves (commands, logs, artifacts linked per TUC).
3. New plugin/model features can be validated with consistent criteria.
4. Better CI onboarding path for scenario-based regression suites.

### Trade-offs

1. Additional documentation maintenance overhead per feature.
2. Requires discipline to keep artifacts inside TUC folders.

### Migration Impact

1. Existing ad-hoc acceptance notes should be moved into TUC folders when touched.
2. New acceptance scenarios must follow TUC layout by default.
3. TUC status must be kept in sync with matrix/evidence (`planned`, `in_progress`, `passed`, `failed`).

## References

- `acceptance-testing/README.md`
- `acceptance-testing/TUC-TEMPLATE/TUC.md`
- `acceptance-testing/TUC-TEMPLATE/IMPLEMENTATION-PLAN.md`
- `acceptance-testing/TUC-TEMPLATE/TEST-MATRIX.md`
- `acceptance-testing/TUC-TEMPLATE/EVIDENCE-LOG.md`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TUC.md`
