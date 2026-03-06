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
python v4/topology-tools/validate-topology.py --topology v4/topology.yaml --strict
python v4/topology-tools/compile-topology.py --topology v4/topology.yaml --strict-model-lock
```
