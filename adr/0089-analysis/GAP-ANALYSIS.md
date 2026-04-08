# Gap Analysis: ADR 0089-0091 SOHO Product Contracts

**Analysis Date:** 2026-04-08
**Scope:** ADR 0089 (Product Profile), ADR 0090 (Operator Lifecycle), ADR 0091 (Readiness Evidence)
**Status:** Initial review

---

## Executive Summary

ADR 0089-0091 establish the SOHO product contract foundation but contain **8 critical ambiguities** and **12 medium-priority gaps** that block implementation.

**Risk Level:** 🔴 **High** — Core contracts (bundle resolution, migration states, evidence semantics) are under-specified.

**Recommended Action:** Address all P0 issues before implementation begins.

---

## Critical Issues (P0) — Blocking

### C1. Bundle Resolution Ambiguity (ADR 0089 D4)

**Location:** ADR 0089, D4 "SOHO bundle resolution is profile-driven"

**Problem:**
The relationship between "Core bundles" and "Class overlays" is ambiguous.

For `managed-soho`, is the effective bundle set:
- **Option A:** Only overlays? (7 bundles)
- **Option B:** Core + overlays? (10 bundles)
- **Option C:** Overlays override core?

**Current Text:**
```
Core bundles (all deployment classes):
- bundle.edge-routing
- bundle.network-segmentation
- bundle.secrets-governance

Class overlays:
- managed-soho:
  - bundle.remote-access
  - bundle.backup-restore
  ...
```

**Impact:**
- Bundle graph generation will fail or produce incorrect results
- Profile validation cannot verify completeness
- Operator expectations misaligned

**Required Fix:**
Add explicit effective bundle set per deployment class:

```yaml
# Effective bundle resolution for managed-soho:
effective_bundles:
  - bundle.edge-routing              # from core
  - bundle.network-segmentation      # from core
  - bundle.secrets-governance        # from core
  - bundle.remote-access             # from overlay
  - bundle.backup-restore            # from overlay
  - bundle.observability             # from overlay
  - bundle.operator-workflows        # from overlay
  - bundle.update-management         # from overlay
```

**Verification:**
- [ ] Effective bundle set is deterministic from profile + deployment_class
- [ ] No manual interpretation required
- [ ] Bundle count matches expectations

---

### C2. Missing Contract File Examples (ADR 0089 D5)

**Location:** ADR 0089, D5 "New canonical contracts"

**Problem:**
Three critical contract files are referenced but not defined:
- `topology/product-profiles/soho.standard.v1.yaml`
- `topology/product-bundles/*.yaml`
- `schemas/product-profile.schema.json`

**Impact:**
- Implementers cannot validate contract structure
- Profile resolution cannot be implemented without schema
- Bundle contracts are not discoverable

**Required Fix:**
Create example contracts in `adr/0089-analysis/examples/`:

1. `product-profile-soho-standard-v1.yaml` — full profile contract
2. `product-bundle-example.yaml` — bundle definition contract
3. `product-profile.schema.json` — JSON schema draft

**Verification:**
- [ ] All D5 contracts have working examples
- [ ] Examples pass schema validation
- [ ] Examples cover all deployment classes

---

### C3. TUC Undefined (ADR 0091 D5)

**Location:** ADR 0091, D5 "Release gate is normative"

**Problem:**
"required TUC evidence set" — acronym not defined anywhere in ADR set.

**Current Text:**
```
SOHO build/publish is blocked when any of the following is true:
- ...
- required TUC evidence set is missing.
```

**Impact:**
- Release gate cannot be implemented
- Evidence requirements incomplete
- Ambiguous acceptance criteria

**Possible Interpretations:**
1. **TUC = Typical Use Cases** (most likely)
2. TUC = Test Under Conditions
3. TUC = undocumented internal term

**Required Fix:**
Either:
- **Option A:** Replace with explicit term: "required acceptance evidence set (ADR 0091 D3)"
- **Option B:** Define TUC acronym and provide evidence mapping

**Verification:**
- [ ] No undefined acronyms in release gate criteria
- [ ] Evidence set is traceable to D3

---

## Important Issues (P1) — High Priority

### I1. Migration State Pipeline Binding (ADR 0089 D6-D7)

**Location:** ADR 0089, D6 "Pipeline binding" + D7 "Validation behavior and migration states"

**Problem:**
D6 declares pipeline stages, D7 introduces migration states, but **how state affects stage execution is not defined**.

**Gap:**
No explicit mapping of:
```
migration_state → stage behavior (blocking vs advisory)
```

**Impact:**
- Validators cannot implement state-aware checks
- Legacy projects may be blocked unexpectedly
- State transitions are not mechanically enforceable

**Required Fix:**
Add explicit stage × state behavior table:

| Migration State | Discover Stage | Compile Stage | Validate Stage |
|---|---|---|---|
| `legacy` | profile resolution **advisory** | bundle resolution **advisory** | compatibility checks **advisory** |
| `migrated-soft` | profile resolution **required** | bundle resolution **required** | warnings allowed, critical only blocking |
| `migrated-hard` | profile resolution **required** | bundle resolution **required** | **all profile requirements blocking** |

**Verification:**
- [ ] Stage behavior deterministic from migration_state
- [ ] State transitions have explicit gates
- [ ] Validators can read state and adjust blocking behavior

---

### I2. `product:init` Semantics Unclear (ADR 0090 D4)

**Location:** ADR 0090, D4 "Task semantics are explicit", `product:init` row

**Problem:**
"creates/initializes product-scoped baseline" is too abstract.

**Questions:**
- Does it create infrastructure (VMs, networks)?
- Does it only initialize local state?
- Does it run Terraform init or Terraform apply?
- Is it safe to rerun?

**Impact:**
- Operator cannot predict side effects
- Idempotency guarantees unclear
- Failure recovery undefined

**Required Fix:**
Expand `product:init` definition:

```markdown
### product:init Detailed Semantics

**Purpose:** Initialize project workspace and validate preconditions without deploying infrastructure.

**Side Effects:**
1. Validates `project.yaml` product_profile contract
2. Creates `.work/deploy/state/<project>/init-state.json`
3. Runs `terraform init` for required providers (downloads plugins only)
4. Verifies secrets access (does NOT decrypt, only checks age keys available)
5. **Does NOT:** create VMs, apply configs, or modify remote state

**Idempotency:** Safe to rerun. Re-validates and updates init-state.json timestamp.

**Preconditions:**
- Valid `project.yaml` with `product_profile` field
- Age keys available at `~/.config/sops/age/keys.txt`

**Postconditions:**
- `.work/deploy/state/<project>/init-state.json` exists with status: "initialized"
- Terraform providers downloaded to `.terraform/`
```

**Verification:**
- [ ] Operator can predict all side effects
- [ ] Idempotency guarantee explicit
- [ ] No infrastructure creation in init phase

---

### I3. "Partial" Evidence State Undefined (ADR 0091 D4)

**Location:** ADR 0091, D4 "Evidence completeness state is normalized"

**Problem:**
States `missing`, `partial`, `complete` are defined, but **what makes evidence "partial" is not specified** per domain.

**Example Ambiguity:**
For `backup-and-restore` domain:
- Is a 30-day-old backup "partial" or "complete"?
- Is an untested backup "partial" or "complete"?
- Is a backup without restore drill "partial"?

**Impact:**
- Readiness state derivation is subjective
- Different operators will classify evidence differently
- Release gate becomes non-deterministic

**Required Fix:**
Add evidence state criteria table:

| Evidence Domain | Missing | Partial | Complete |
|---|---|---|---|
| **greenfield-first-install** | No installation evidence | Install evidence exists but > 90 days old | Fresh install evidence < 90 days |
| **backup-and-restore** | No backup exists | Backup exists but > 7 days old OR no restore drill | Valid backup < 7 days + restore drill passed < 30 days |
| **operator-handover** | No handover package | Package exists but missing ≥1 D1 artifacts | All D1 artifacts present + schema-validated |
| **secret-rotation** | No rotation evidence | Last rotation > 180 days | Last rotation < 90 days |
| **scheduled-update** | No update evidence | Last update > 90 days OR failed | Last successful update < 60 days |

**Verification:**
- [ ] Evidence state is mechanically derivable
- [ ] Criteria include time bounds and quality gates
- [ ] No operator interpretation required

---

## Medium-Priority Issues (P2)

### M1. Circular Out-of-Scope References

**Location:** All three ADRs, "Out of scope" sections

**Problem:**
- ADR 0089 Out-of-scope → references ADR 0090, 0091
- ADR 0090 Out-of-scope → references ADR 0089, 0091
- ADR 0091 Out-of-scope → references ADR 0089, 0090

Creates circular reference loop.

**Impact:**
- Dependency graph unclear
- ADR reading order ambiguous

**Fix:**
Remove "Out of scope" from ADR 0089 (base contract). Only 0090/0091 reference 0089.

---

### M2. No End-to-End Example

**Problem:**
No walkthrough showing how all three ADRs integrate.

**Impact:**
- Operator workflow unclear
- Integration points not validated

**Fix:**
Create `E2E-SCENARIO.md` with complete workflow (see Implementation Plan).

---

### M3. Hardware Matrix Not Defined (ADR 0089)

**Problem:**
"hardware class" and "hardware compatibility matrix" mentioned but not specified.

**Fix:**
Either:
- Add to D5 contract list: `schemas/hardware-compatibility-matrix.schema.json`
- Or defer to future ADR and mark explicitly

---

### M4. No Dry-Run Mode (ADR 0090)

**Problem:**
Tasks with side effects lack explicit dry-run semantics.

**Fix:**
Add to D4 table:

```
All tasks with side effects support --dry-run flag:
- product:apply --dry-run → plan-only mode
- product:restore --dry-run → validation-only mode
- product:update --dry-run → preflight-only mode
- product:backup --dry-run → check backup targets reachable
```

---

### M5. Precondition Verification Not Specified (ADR 0090 D7)

**Problem:**
Preconditions listed but verification method not specified.

**Example:**
"validated topology" — how is this verified?

**Fix:**
Expand D7 table with "How verified" column (see I2 fix example).

---

### M6. Missing JSON Schema Files (ADR 0091 D6)

**Problem:**
Four schemas referenced but not created:
- `schemas/operator-readiness.schema.json`
- `schemas/backup-status.schema.json`
- `schemas/restore-readiness.schema.json`
- `schemas/support-bundle-manifest.schema.json`

**Fix:**
Create schema stubs (see Implementation Plan task #11).

---

### M7. .md/.csv Artifacts Not Schema-Validated (ADR 0091 D1 + D6)

**Problem:**
D1 requires operator-facing artifacts in Markdown/CSV:
- `SYSTEM-SUMMARY.md`
- `ASSET-INVENTORY.csv`

But D6 only defines schemas for JSON reports.

**Impact:**
- Handover completeness check cannot verify .md/.csv structure
- Quality drift possible

**Fix:**
Either:
- Add schemas (e.g., frontmatter validation for .md, column schemas for .csv)
- Or explicitly state: "Markdown/CSV artifacts are operator-facing and not schema-validated"

---

### M8. Secret Sanitization Rules Not Specified (ADR 0091 D8)

**Problem:**
"deterministic redaction/sanitization" mentioned but rules not defined.

**Fix:**
Reference ADR 0072 explicitly or add example:
```
Sanitization rules:
- Passwords → [REDACTED]
- API tokens → first 4 chars + "..." (e.g., "sk_t...")
- IP addresses → preserve subnet, mask host (e.g., "10.0.10.xxx")
```

---

## Risk Assessment

| Risk Area | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bundle resolution produces wrong set | High | Critical | Fix C1 before implementation |
| Profile validation cannot be implemented | High | Critical | Fix C2 (create schemas) |
| Release gate non-deterministic | High | High | Fix C3 (TUC), I3 (partial states) |
| Migration state not enforceable | Medium | High | Fix I1 (pipeline binding) |
| Operator workflow unclear | Medium | Medium | Fix M2 (E2E scenario) |

---

## Compliance Issues

### Against CLAUDE.md ADR Policy

**Policy Requirement:**
> One architectural decision → one ADR file.
> No architecture change is considered complete without an ADR entry.

**Findings:**
✅ ADR 0089-0091 are properly structured
⚠️ Missing analysis directory (being created now per policy)
⚠️ Large implementation plans should not be inlined (moving to analysis/)

### Against Infrastructure-as-Data Principles

**Principle:**
> Deterministic generation, machine-validatable contracts

**Findings:**
❌ Bundle resolution not deterministic (C1)
❌ Evidence state subjective (I3)
✅ Schema contracts referenced (but not created yet)

---

## Summary of Required Fixes

| ID | Issue | ADR | Priority | Effort | Risk if Not Fixed |
|---|---|---|---|---|---|
| C1 | Bundle resolution ambiguity | 0089 | P0 | Medium | Generation failures |
| C2 | Missing contract examples | 0089 | P0 | High | Implementation blocked |
| C3 | TUC undefined | 0091 | P0 | Low | Release gate broken |
| I1 | Migration state → pipeline | 0089 | P1 | Medium | Validation inconsistent |
| I2 | product:init semantics | 0090 | P1 | Low | Operator confusion |
| I3 | Partial evidence criteria | 0091 | P1 | Medium | Non-deterministic readiness |
| M1 | Circular out-of-scope | All | P2 | Low | Documentation quality |
| M2 | No E2E example | All | P2 | Medium | Integration unclear |
| M3-M8 | Various medium issues | Mixed | P2 | Low-Med | Quality degradation |

---

## Next Steps

1. **Immediate (P0):** Fix C1-C3 in ADR files + create contract examples
2. **Short-term (P1):** Add missing tables/semantics (I1-I3)
3. **Medium-term (P2):** Address M1-M8 + create schema stubs
4. **Validation:** Review updated ADRs against CLAUDE.md policy + framework contracts

**Estimated Total Effort:** 2-3 days for P0+P1 fixes, 1 day for P2+schemas

---

## Appendix: Analysis Methodology

**Sources Reviewed:**
- ADR 0089 (225 lines)
- ADR 0090 (189 lines)
- ADR 0091 (186 lines)
- CLAUDE.md ADR policy
- ADR 0063, 0070, 0072, 0074, 0075, 0077, 0080, 0085 (dependencies)

**Review Criteria:**
- Contract completeness (all referenced files defined)
- Determinism (no subjective interpretation required)
- Operator clarity (task semantics explicit)
- Schema-first design (contracts machine-validatable)
- Migration safety (state transitions explicit)

**Review Date:** 2026-04-08
**Reviewer Role:** Independent architectural analyst
