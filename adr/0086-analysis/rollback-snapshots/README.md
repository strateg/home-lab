# ADR 0086 — Rollback Snapshots

Snapshot set for fast ADR0086 rollback and forensic comparison.

## Stored Baselines

| Baseline commit | Scope | Snapshot root |
|---|---|---|
| `bd24c6e` | Pre-Wave2 validator consolidation | `adr/0086-analysis/rollback-snapshots/bd24c6e/` |
| `2a5aa5c` | Post-Wave2 / pre-Wave3-minimization manifests | `adr/0086-analysis/rollback-snapshots/2a5aa5c/` |
| `9dd6675` | Post-Wave3 cutover before `_shared` relocation | `adr/0086-analysis/rollback-snapshots/9dd6675/` |

## Included Files

- Router wrapper validators and module validators removed in Wave2.
- Router/GL.iNet/network manifests affected by Wave2/Wave3.
- `_shared` helper/projection modules moved to framework generators in follow-up cutover.

## Fast Revert (Targeted)

Prefer targeted restore in a disposable branch/worktree:

```bat
git switch -c adr0086-rollback-test
```

Then copy only needed files from a selected snapshot root (`bd24c6e`, `2a5aa5c`, or `9dd6675`), for example:

```bat
copy adr\0086-analysis\rollback-snapshots\2a5aa5c\topology\class-modules\router\plugins.yaml topology\class-modules\router\plugins.yaml
copy adr\0086-analysis\rollback-snapshots\2a5aa5c\topology\object-modules\glinet\plugins.yaml topology\object-modules\glinet\plugins.yaml
```

## Integrity Note

Each snapshot file is exported directly from Git object history via:

```bat
git show <commit>:<path>
```
