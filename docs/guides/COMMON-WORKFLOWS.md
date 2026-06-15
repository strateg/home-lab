# Common Workflows

This guide contains common developer workflows extracted from adapter files for token efficiency.

## Compile and Generate

```bash
# Validate and compile topology
.venv/bin/python scripts/orchestration/lane.py validate-v5

# Run full compilation
.venv/bin/python topology-tools/compile-topology.py

# Parallel plugin execution (default)
.venv/bin/python topology-tools/compile-topology.py

# Sequential mode (troubleshooting only)
.venv/bin/python topology-tools/compile-topology.py --no-parallel-plugins
```

## Development Profile

During development, framework file changes invalidate `framework.lock.yaml` integrity hashes.

```bash
# Auto-regenerate with dev profile
.venv/bin/python topology-tools/compile-topology.py --profile dev

# Manual batch regeneration
task framework:lock-refresh-all
```

**Runtime profiles:**
- `production` (default) — strict validation
- `dev` — auto-regenerates framework.lock on integrity mismatch
- `modeled` — for model testing scenarios
- `test-real` — for integration tests with real data

## Lane Orchestrator

```bash
# Full validation
V5_SECRETS_MODE=passthrough .venv/bin/python scripts/orchestration/lane.py validate-v5

# Run specific phase
python scripts/orchestration/lane.py <phase-name>
```

## Deploy Bundle Workflow

```bash
# Build immutable deploy bundle
task bundle:create
task bundle:list

# Execute service-chain lanes
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id>
task deploy:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id>
```

## Node Initialization

```bash
# Check init state
task deploy:init-status

# Plan node initialization
task deploy:init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id>
```

## Run Tests

```bash
# All tests
python -m pytest tests -q

# Specific test module
python -m pytest tests/plugin_integration/ -v

# Full CI
task ci
```

## State File Locations

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |

## References

- `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`
- `docs/guides/NODE-INITIALIZATION.md`
- `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`
