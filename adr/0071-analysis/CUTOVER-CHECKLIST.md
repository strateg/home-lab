# ADR 0071 Cutover Checklist

**ADR:** `adr/0071-sharded-instance-files-and-flat-instances-root.md`
**Date:** 2026-03-11
**Status:** Completed
**Implementation Plan:** `adr/0071-analysis/IMPLEMENTATION-PLAN.md`

## 1) Runtime and Ownership

- [x] Runtime runs in `sharded-only` mode (auto resolves to sharded-only).
- [x] Loader is the only component reading shard files.
- [x] Downstream plugins consume assembled payload only.
- [x] Plugin discovery does not scan `instances_root` (no instance-modules).
- [x] Legacy manifest path removed from active runtime contract.

## 2) Contract Enforcement

- [x] `basename(file) == instance` is enforced.
- [x] Global uniqueness of `instance` is enforced.
- [x] One-row-per-file is enforced.
- [x] Required keys (`schema_version`, `instance`, `group`, `layer`, `object_ref`) + supported `schema_version` are enforced.
- [x] `class_ref` is derived/verified from `object_ref` in compile normalization.
- [x] Group/layer consistency checks are enforced.

## 3) Parity Gates

- [x] Payload parity passed (`production`).
- [x] Payload parity passed (`modeled`).
- [x] Payload parity passed (`test-real`).
- [x] Diagnostics parity passed (`code`, `severity`, `path`).

## 4) Determinism Gates

- [x] Discovery ordering is deterministic.
- [x] In-group row ordering is deterministic.
- [x] Diagnostics ordering is deterministic.
- [x] Repeated runs produce no noisy diff.

## 5) Operational Gates

- [x] Baseline CLI flows remain stable.
- [x] Rollback path is repository-level (git revert), no runtime legacy mode.
- [x] No unresolved critical migration incidents.

## 6) Evidence Bundle (Required)

- [x] Parity report bundle (all profiles).
- [x] Diagnostics parity report.
- [x] Determinism report (repeat-run diff).
- [x] CLI compatibility log.
- [x] Rollback readiness documented (git revert strategy).

## GO / NO-GO Rule

GO only when sections 1-6 are fully green with evidence.

NO-GO on any parity mismatch, deterministic regression, critical CLI regression, or missing evidence.

## Cleanup Readiness

- [x] Default mode switched to `sharded-only`.
- [x] Legacy single-file path removed or hard-disabled.
- [x] Docs/guides reference `paths.instances_root` as canonical.
- [x] ADR0071 promoted to `Accepted`.
