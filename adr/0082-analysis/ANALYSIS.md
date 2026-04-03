# ADR 0082 Analysis Refresh: Module Index as Authoritative Contract

- Date: 2026-04-03
- Status: Complete (Refreshed)
- Scope: Re-evaluation of ADR 0082 options against current repository state

---

## 1. Current State (Measured)

| Metric | Value |
|--------|-------|
| Base framework plugins (`topology-tools/plugins/plugins.yaml`) | 63 |
| Class module manifests with plugins | 0 |
| Object module manifests with plugins | 4 (`mikrotik`, `network`, `orangepi`, `proxmox`) |
| Module-level plugins | 6 |
| Total plugins | 69 |
| `topology/module-index.yaml` coverage target | 4 object manifests, 0 class manifests |
| Discovery runtime mode | Index-first with recursive fallback |

Observations:

1. Module-level surface is still small (6/69 plugins).
2. Most plugin logic remains centralized in the base framework manifest.
3. Current architecture risk is index drift, not packaging scalability.

---

## 2. Option Re-Assessment

### Option A: Keep Current Structure + Hardening

Fit for current state: **High**

Pros:

1. Zero structural migration cost.
2. Preserves current developer/AI edit loop.
3. Resolves current operational risk (index drift) with minimal change.

Cons:

1. No per-module versioning yet.
2. No native module-level integrity hash model.

### Option B: Full Module-Pack Assembly

Fit for current state: **Low**

Pros:

1. Strong structural boundaries and per-module metadata from day one.
2. Better long-term scaling at high module counts.

Cons:

1. High complexity increase for current scale.
2. Additional manifests and build assembly pipeline now provide low immediate value.

### Option C: Hybrid Metadata Extension

Fit for current state: **Medium**

Pros:

1. Adds module metadata without full assembly migration.
2. Can evolve toward Option B later.

Cons:

1. Introduces metadata management overhead before it is needed.
2. Does not solve the immediate risk better than Option A hardening.

---

## 3. Recommended Target Model

### Recommendation: **A+ (Option A with strict index governance now)**

Why A+ is optimal now:

1. It directly addresses the real issue: `module-index.yaml` drift.
2. It keeps runtime and workflows stable while tightening correctness.
3. It avoids premature complexity from module-pack orchestration.

Implemented in this refresh:

1. `topology/module-index.yaml` aligned to actual manifests (removed stale `router`/`glinet` entries).
2. Added bidirectional index consistency validation (`index -> filesystem` and `filesystem -> index`).
3. Wired consistency checks into validation tasks and compiler manifest loading path.
4. Added contract tests for consistency checks.

---

## 4. Decision Gates for Future Evolution

Stay on A+ until at least one gate is hit:

1. Active module manifests > 15.
2. Need for per-module release cadence/versioning.
3. Repeated incidents where module-level integrity provenance is required.

If gates are hit:

1. Move to C (metadata-enriched index) first.
2. Move to B only when metadata-only model becomes operationally insufficient.

---

## 5. Practical Next Steps

1. Keep `module-index.yaml` authoritative in CI and local validation.
2. Track module growth trend quarterly.
3. Prepare a minimal schema-v2 proposal only when the first gate is reached.

---

## 6. References

- ADR 0082: `adr/0082-plugin-module-pack-composition-and-index-first-discovery-analysis.md`
- Discovery implementation: `topology-tools/plugin_manifest_discovery.py`
- Compiler integration: `topology-tools/compile-topology.py`
- Module index: `topology/module-index.yaml`
- Contract tests: `tests/plugin_contract/test_manifest_discovery.py`
