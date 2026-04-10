# Backup and Restore Procedures

**Status:** Active
**Updated:** 2026-03-28
**Scope:** Operational procedure for topology artifacts and runtime state

---

## 1. Backup Scope

1. Topology source and project manifests:
   - `topology/`
   - `projects/home-lab/`
2. Framework and governance state:
   - `framework.lock.yaml`
   - `adr/`
3. Generated deployment artifacts:
   - `generated/home-lab/terraform/`
   - `generated/home-lab/ansible/`
   - `generated/home-lab/bootstrap/`
4. Diagnostics evidence:
   - `build/diagnostics/`

Secrets must be backed up in encrypted form only.

---

## 2. Pre-Backup Integrity Gate

```powershell
task framework:strict
task validate:default
```

Capture current commit SHA and change record ID before taking backup snapshot.

---

## 3. Backup Procedure

```powershell
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated
task framework:cutover-readiness-quick
```

Then archive:

1. repository snapshot (git tag or immutable archive),
2. generated artifacts,
3. diagnostics outputs,
4. external secrets storage snapshot.

---

## 4. Restore Procedure

1. Checkout target commit/tag.
2. Restore encrypted secrets material from approved secret store.
3. Rebuild generated artifacts from source:

```powershell
.venv/bin/python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated
```

4. Re-run strict and validation gates:

```powershell
task framework:strict
task validate:default
task framework:cutover-readiness
```

5. Compare restored diagnostics with backup baseline.

---

## 5. Acceptance Criteria

- restored state passes strict lock and validation gates,
- generated artifacts are reproducible,
- no unresolved placeholder diagnostics in strict profiles,
- rollback target is deployable without manual patching.
