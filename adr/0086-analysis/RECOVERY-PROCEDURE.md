# ADR 0086 — Recovery Procedure

Recovery procedure for rollback readiness gates in ADR0086.

## Prerequisites

- Clean working tree (except optional `.coverage` changes).
- Python environment used by normal V5 validation flow.
- `projects/home-lab/framework.lock.yaml` present.

## Procedure

1. Rehearse lock rollback/regeneration in strict mode:

```bat
python topology-tools/utils/rehearse-framework-rollback.py
```

2. Run baseline compile gates:

```bat
python topology-tools/compile-topology.py
python topology-tools/compile-topology.py --no-parallel-plugins
```

3. Run end-to-end validation lane:

```bat
set V5_SECRETS_MODE=passthrough
python scripts/orchestration/lane.py validate-v5
```

4. If rollback is needed, restore target files directly from Git history at rollback boundaries:
   - `bd24c6e` (pre-Wave2 validator consolidation baseline)
   - `2a5aa5c` (post-Wave2 manifest baseline)
   - `9dd6675` (post-Wave3 layout baseline)

   Example:

```bat
git show 2a5aa5c:topology/object-modules/network/plugins.yaml > topology/object-modules/network/plugins.yaml
```

5. Re-run steps 1-3 to verify recovery state.

## Dry-Run Evidence

Execution date: **2026-04-02**

- `python topology-tools/utils/rehearse-framework-rollback.py` -> `Framework rollback rehearsal: OK`
- `python topology-tools/compile-topology.py` -> success
- `python topology-tools/compile-topology.py --no-parallel-plugins` -> success
- `python scripts/orchestration/lane.py validate-v5` with `V5_SECRETS_MODE=passthrough` -> success
