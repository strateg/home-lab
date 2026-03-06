# home-lab

Repository is split into two migration lanes:

- `v4/` - legacy operational topology/runtime (frozen except critical fixes)
- `v5/` - new Class -> Object -> Instance architecture (active migration)

Generated artifacts are versioned by lane:

- `v4-generated/`, `v4-build/`, `v4-dist/`
- `v5-generated/`, `v5-build/`, `v5-dist/`

Main documents:

- `adr/0062-modular-topology-architecture-consolidation.md`
- `v4/README.md`

Quick commands:

```powershell
make validate-v4
make validate-v5
make build-v4
make build-v5
make phase1-bootstrap
make phase1-reconcile
make phase1-backlog
make phase1-gate
make phase4-sync-lock
make phase4-export
```
