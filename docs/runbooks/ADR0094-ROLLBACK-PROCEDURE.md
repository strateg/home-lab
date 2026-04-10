# ADR0094 Rollback Procedure

**Status:** Active  
**Updated:** 2026-04-07  
**Scope:** Rollback of AI-promoted artifacts from ADR0094 assisted mode

---

## Preconditions

- Rollback is executed from repository root.
- Target files were promoted by AI-assisted flow (metadata sidecar exists).
- Working tree is clean or intentionally staged for rollback.

---

## Full Rollback

```bash
task generate:ai-assisted-rollback -- AI_ROLLBACK_ALL=true AI_ROLLBACK_REF=HEAD
```

Behavior:
- discovers AI-promoted files via `.ai-metadata.json` sidecars,
- restores tracked files from `AI_ROLLBACK_REF`,
- deletes files absent in baseline ref,
- logs `rollback_result` to audit log.

---

## Selective Rollback

```bash
task generate:ai-assisted-rollback -- AI_ROLLBACK_PATHS=generated/home-lab/docs/overview.md AI_ROLLBACK_REF=HEAD
```

Use when only subset of promoted files is problematic.

---

## Validation After Rollback

```bash
task validate:default
```

Recommended additional checks by family:
- Terraform: `task terraform:validate`
- Ansible inventory: `task ansible:runtime`

---

## Evidence to Keep

- rollback command used,
- affected file list,
- audit log path under `.work/ai-audit/.../ai-advisory-audit.jsonl`,
- post-rollback validation result.
