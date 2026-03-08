# ADR 0060: YAML-to-JSON Compiler and Diagnostics Contract

**Date:** 2026-03-06
**Status:** Superseded by ADR 0062 (Harmonized with ADR 0064 on 2026-03-09)
**Related:** ADR 0058 (Core Abstraction Layer), ADR 0059 (Repository Split and Class-Object-Instance Module Contract), ADR 0061 (Base Repo with Versioned Class-Object-Instance and Test Profiles)
**Superseded By:** [ADR 0062](0062-modular-topology-architecture-consolidation.md)
**Harmonized With:** ADR 0064 (Firmware + OS Two-Entity Model)

---

## Context

The project keeps YAML as a human-friendly source format. At the same time, we need strict machine checks for:

- class-object-instance linkage integrity
- firmware/OS instance linkage integrity (`firmware_ref`, `os_refs[]`)
- stable AI repair loops
- deterministic validation and error triage

`validate-topology.py` already performs broad checks, but diagnostic output is mostly plain text and is not optimized for:

- automated patch planning by AI agents
- root-cause-oriented feedback cycles
- consistent machine-readable error transport between pipeline stages

---

## Decision

### 1. Keep YAML as Source, JSON as Canonical Build Artifact

Adopt a formal compile pipeline:

1. `load` (YAML + include resolution)
2. `normalize` (deterministic canonical structure)
3. `resolve` (ID/reference checks + class-object-instance linkage checks)
4. `validate` (schema + semantic checks, including capability contract and software-instance checks)
5. `emit` (canonical JSON and diagnostics artifacts)

Source remains editable YAML. Canonical machine contract is JSON.

### 2. Introduce Structured Diagnostics as First-Class Artifact

Compiler must always emit diagnostics to:

- JSON for AI systems
- text report for humans

Diagnostic record contract includes:

- `code`, `severity`, `stage`, `message`
- `path` (JSONPath)
- `source` (`file`, `line`, `column` when available)
- `hint` and optional `autofix`
- `root_cause_rank` for prioritized remediation

### 3. Standardize Error Catalog

Add a versioned error catalog with stable codes:

- `E1xxx` load/include/parse errors
- `E2xxx` resolve and ID/reference contract errors
- `E3xxx` emit/report errors
- `E4xxx/W4xxx` model-lock/profile/capability contract errors and warnings
- `W2xxx/W3xxx` non-fatal contract and semantic warnings
- `I9xxx` informational messages

### 4. Add Initial Compiler Entry Point

Introduce `v5/topology-tools/compile-topology.py` as orchestration entry point for:

- canonical `effective-topology.json`
- diagnostics (`report.json`, `report.txt`)

The compiler integrates existing semantic validation runner and adds machine-first diagnostics envelope.

Capability-focused diagnostics are required for:

- missing object support for class required capabilities
- invalid capability identifiers outside catalog (except `vendor.*`)
- profile replacement that violates required capability signature

Software-focused diagnostics are required for:

- missing or unresolved `firmware_ref` when class policy requires firmware
- unresolved or class-incompatible `os_refs[]`
- `multi_boot`/cardinality violations
- architecture/install-model incompatibility between device, firmware, and OS instances

---

## Consequences

### Positive

1. AI agents can deterministically locate and patch topology defects
2. Human operators get concise and actionable text reports
3. Validation results become stable artifacts in CI/CD
4. Clear separation of authoring format (YAML) and execution format (JSON)

### Negative

1. Additional maintenance surface (compiler + diagnostics schema + catalog)
2. Need to keep error-code taxonomy stable across releases
3. Initial overlap with legacy validation CLI until full convergence

### Risks and Mitigations

1. Risk: duplicate/contradicting errors from different checks
   - Mitigation: deduplicate diagnostics by fingerprint and rank root causes
2. Risk: weak source localization for some semantic checks
   - Mitigation: gradually enrich validators with source mapping metadata
3. Risk: drift between diagnostics schema and runtime output
   - Mitigation: validate report against `diagnostics.schema.json` during emit

---

## References

- Compiler entry point: `v5/topology-tools/compile-topology.py`
- Capability diagnostics checker: `v5/topology-tools/check-capability-contract.py`
- Error catalog: `v5/topology-tools/data/error-catalog.yaml`
- Lane validator entry: `v5/scripts/lane.py`
- ADR register: `adr/REGISTER.md`
- Commit: harmonization pending
