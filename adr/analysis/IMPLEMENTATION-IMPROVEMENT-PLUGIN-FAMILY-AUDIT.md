# Plugin Family Audit

**Date:** 2026-04-10
**Scope:** Wave 6 / PR16 from `adr/analysis/IMPLEMENTATION-IMPROVEMENT-PLAN.md`
**Type:** Audit report only, no runtime behavior change

---

## Purpose

Зафиксировать текущее состояние plugin family layout перед любыми low-priority перемещениями модулей.

Этот документ не меняет архитектурное решение сам по себе. Он фиксирует, где сейчас есть наблюдаемый перекос, и какие действия безопасно отложить.

---

## Snapshot

Инвентаризация `topology-tools/plugins/` на 2026-04-10:

| Family | Python files | Notes |
|---|---:|---|
| `discoverers/` | 1 | `discover_compiler.py` содержит 4 discoverer-класса |
| `compilers/` | 8 | stage-entry modules |
| `validators/` | 49 | самая крупная family |
| `generators/` | 26 | из них 7 `ai_*.py` helper modules |
| `assemblers/` | 2 | stage-entry modules |
| `builders/` | 2 | stage-entry modules |

Дополнительные наблюдения по manifest inventory:

- validator plugins across framework + object manifests: **49**
- validator plugins with explicit `when:` predicate: **0**
- AI helper modules under `topology-tools/plugins/generators/ai_*.py`: **7**
- AI helper modules referenced directly as manifest entrypoints: **0**

---

## Findings

### 1. Discoverers remain consolidated in one file

Current state:

- `topology-tools/plugins/discoverers/discover_compiler.py`
- classes:
  - `DiscoverManifestLoaderCompiler`
  - `DiscoverInventoryCompiler`
  - `DiscoverBoundaryCompiler`
  - `DiscoverCapabilityPreflightCompiler`

Assessment:

- This is still a single-file concentration point.
- However, all four classes belong to the same stage family and are small, tightly related entrypoints.
- Splitting them now would be mostly structural churn with limited operational payoff.

Decision for now:

- Keep current file layout unchanged.
- Revisit only if discover-stage code volume or per-class ownership pressure grows further.

---

### 2. AI helpers are generator-family helpers, not generator plugins

Current state:

- `topology-tools/plugins/generators/ai_advisory_contract.py`
- `topology-tools/plugins/generators/ai_ansible.py`
- `topology-tools/plugins/generators/ai_assisted.py`
- `topology-tools/plugins/generators/ai_audit.py`
- `topology-tools/plugins/generators/ai_promotion.py`
- `topology-tools/plugins/generators/ai_rollback.py`
- `topology-tools/plugins/generators/ai_sandbox.py`

Observed behavior:

- None of these modules are manifest entrypoints.
- They are helper/support modules consumed by compiler AI orchestration and generator-adjacent flows.

Assessment:

- The analysis concern is valid: these files are helpers, not generators in the strict artifact-producing sense.
- At the same time, relocating them now would create import churn across recently stabilized compiler/AI session code.
- There is no immediate correctness or security defect caused purely by their current directory placement.

Decision for now:

- Treat current placement as tolerated technical debt.
- Defer relocation until a dedicated package-boundary change groups AI helper modules under a new canonical namespace in one move.

---

### 3. Validator `when:` gating is not used today

Current state:

- validator plugins audited: **49**
- validator plugins with explicit `when:`: **0**

Assessment:

- This does not mean the validator layer is incorrect.
- It does mean validator execution remains predominantly controlled by stage ordering and plugin-level logic instead of manifest-level gating.
- Any future performance or selective-execution optimization should start from manifest/runtime evidence, not from blind introduction of `when:` predicates.

Decision for now:

- No manifest churn in this PR.
- Keep this as an audit baseline for future selective-gating work.

Suggested future candidates for a deeper `when:` audit:

- policy-driven validators
- rollback/sunset governance validators
- validators that consume optional external policy files or optional runtime artifacts

---

## Deferred Actions

The following items stay deferred after this audit:

1. Split `discover_compiler.py` into one class per file.
2. Relocate AI helper modules out of `plugins/generators/`.
3. Introduce `when:` predicates into validator manifests.

Reason:

- none of them currently justify runtime-risk or review churn relative to their payoff
- each needs a dedicated boundary decision, not an opportunistic cleanup commit

---

## Recommendation

Wave 6 should remain hygiene-only:

1. keep this audit as the baseline inventory
2. avoid code movement without a separate ownership/package decision
3. prioritize only narrowly-scoped linting or documentation follow-ups unless a runtime issue appears
