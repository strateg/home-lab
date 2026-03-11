# ADR 0071 Cutover Checklist

**ADR:** `adr/0071-sharded-instance-files-and-flat-instances-root.md`
**Date:** 2026-03-11
**Status:** Draft
**Implementation Plan:** `adr/0071-analysis/IMPLEMENTATION-PLAN.md`

## 1) Runtime and Ownership

- [ ] Runtime supports `legacy-only`, `dual-read`, `sharded-only`.
- [ ] Loader is the only component reading shard files.
- [ ] Downstream plugins consume assembled payload only.
- [ ] Plugin discovery does not scan `instances_root` (no instance-modules).
- [ ] Legacy path usage produces explicit deprecation signal.

## 2) Contract Enforcement

- [ ] `basename(file) == instance` is enforced.
- [ ] Global uniqueness of `instance` is enforced.
- [ ] One-row-per-file is enforced.
- [ ] Required keys (`schema_version`, `instance`, `group`, `layer`, `object_ref`) + supported `schema_version` are enforced.
- [ ] `class_ref` is derived from `object_ref` in assembled payload.
- [ ] Group/layer consistency checks are enforced.

## 3) Parity Gates

- [ ] Payload parity passed (`production`).
- [ ] Payload parity passed (`modeled`).
- [ ] Payload parity passed (`test-real`).
- [ ] Diagnostics parity passed (`code`, `severity`, `path`).

## 4) Determinism Gates

- [ ] Discovery ordering is deterministic.
- [ ] In-group row ordering is deterministic.
- [ ] Diagnostics ordering is deterministic.
- [ ] Repeated runs produce no noisy diff.

## 5) Operational Gates

- [ ] Baseline CLI flows remain stable.
- [ ] Rollback drill (`legacy-only`) succeeds.
- [ ] No unresolved critical migration incidents.

## 6) Evidence Bundle (Required)

- [ ] Parity report bundle (all profiles).
- [ ] Diagnostics parity report.
- [ ] Determinism report (repeat-run diff).
- [ ] CLI compatibility log.
- [ ] Rollback drill log.

## GO / NO-GO Rule

GO only when sections 1-6 are fully green with evidence.

NO-GO on any parity mismatch, deterministic regression, critical CLI regression, or missing evidence.

## Cleanup Readiness

- [ ] Default mode switched to `sharded-only`.
- [ ] Legacy single-file path removed or hard-disabled.
- [ ] Docs/guides reference `paths.instances_root` as canonical.
- [ ] ADR0071 can be promoted to `Accepted`.
