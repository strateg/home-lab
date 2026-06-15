# AI Rule Pack: Testing and CI

> **Version:** 1.0 | **Updated:** 2026-06-15 | **ADRs:** See `ADR-RULE-MAP.yaml` → `testing-ci.source_adr`

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Use task commands | Prefer `task` over raw commands |
| Test with changes | Add/update tests for behavior changes |
| Targeted first | Run specific tests before broad gates |
| Evidence required | No validation claims without output |
| CI before merge | Run `task ci` for integration closure |

## Load When

- `tests/**`
- `taskfiles/**`
- `.github/workflows/**`
- Runtime contracts, validation entrypoints

## Test Hierarchy

| Level | Scope | Command |
|-------|-------|---------|
| Unit | Single function/class | `pytest tests/unit/` |
| Integration | Plugin interactions | `pytest tests/plugin_integration/` |
| Contract | API boundaries | `pytest tests/contract/` |
| CI gate | Full validation | `task ci` |

## Validation Commands

| Purpose | Command |
|---------|---------|
| Quick quality | `task validate:quality-fast` |
| Framework lock | `task framework:strict` |
| Full CI | `task ci` |
| Specific test | `pytest tests/path/test_file.py -v` |

## When to Run What

| Change Type | Required Tests |
|-------------|----------------|
| Plugin code | `task test:plugin-contract` + targeted |
| Topology | `task validate:default` |
| Framework | `task framework:strict` + `task ci` |
| CI workflow | `task ci` (verify it still works) |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Claim without evidence | Unverified | Show command output |
| Skip targeted tests | Miss specific failures | Run targeted first |
| Ignore CI aliases | Breaks developer contract | Preserve or deprecate |
| Stale framework.lock | Validation will fail | `task framework:lock-refresh` |

## Validation

```bash
task validate:quality-fast
task framework:strict
task ci
```
