# ADR 0040: L0-L5 Canonical Ownership and Refactoring Plan

- Status: Accepted
- Date: 2026-02-23
- Updated: 2026-02-24
- Harmonized With: ADR 0064 (Firmware + OS Two-Entity Model)

## Context

Harmonization note (2026-03-09):
- Layer ownership/refactoring decisions remain valid.
- v5 software semantics map legacy `host_os_ref` intent to resolved OS instances from `os_refs[]` (ADR 0064).
- L1/L2/L5 ownership boundaries are unchanged by the firmware/OS entity split.

Topology `v4.0.0` is structurally valid and passes strict validation, but architecture review showed
drift risks across `L0-L5`:

1. **Layer ownership leaks**:
   - Non-physical service hints could appear in `L1` device modules (not currently present, but no guardrail).
2. **Duplicate source-of-truth fields in L5**:
   - `container: true` duplicates `runtime.type: docker` (10 instances in services.yaml).
   - `native: true` duplicates `runtime.type: baremetal` (1 instance).
   - `config.docker.host_ip` duplicates network binding intent (5 instances).
3. **IP ownership split across layers**:
   - `L2.networks[].ip_allocations` — physical host IPs with `host_os_ref`.
   - `L4.workloads[].networks[].ip` — LXC/VM IPs.
   - `L5.services[].config.docker.host_ip` — docker service binding (unclear ownership).
4. **Governance quality issues**:
   - Metadata freshness and migration intent are not formalized into a phased refactor contract.
   - No validator rules prevent legacy field authoring.

Without an explicit contract, changes remain locally valid but globally inconsistent.

## Decision

Adopt the following canonical ownership contract and phased migration:

### 1. L1 is strictly physical

- Keep only physical inventory, links, slot/media attachment, and hardware capability.
- `firmware.features` is allowed (hardware capabilities like "Container support").
- Remove any `services`, `applications`, `runtime` keys if found.
- Add validator rule to prevent non-physical keys in L1 devices.

### 2. L5 `services[].runtime` is canonical for placement

Canonical fields in `runtime`:
- `type`: `docker` | `lxc` | `vm` | `baremetal`
- `target_ref`: device or workload ID
- `network_binding_ref`: network ID for service binding
- `image`: container image (for docker/container runtime)

Legacy fields to remove from authored data:
| Field | Replacement | Instances |
|-------|-------------|-----------|
| `container: true` | `runtime.type: docker` | 10 |
| `native: true` | `runtime.type: baremetal` | 1 |
| `config.docker.host_ip` | derive from `runtime.network_binding_ref` | 5 |

### 3. IP ownership boundaries

| Layer | IP ownership scope | Example |
|-------|-------------------|---------|
| L2 | Physical hosts, network infrastructure | `ip_allocations[].host_os_ref` |
| L4 | Workload instances (LXC, VM) | `workloads[].networks[].ip` |
| L5 | Service binding (derived, not authored) | via `runtime.network_binding_ref` |

Decision: `L5.services[].config.docker.host_ip` is deprecated. Service IP binding is derived from:
1. `runtime.target_ref` → resolves to L4 workload or L1 device
2. `runtime.network_binding_ref` → resolves to L2 network
3. Generator looks up IP from L2 or L4 based on target type

### 4. Generator compatibility is phased out for removed L5 runtime hints

- Projection happens in tooling (`generate-*.py`), not in source topology authoring.
- During transition, generators may synthesize structural runtime projections (`device_ref/lxc_ref/network_ref/ip`) for docs.
- Compatibility projections for removed L5 runtime hints (`container`, `native`, `container_image`) are eliminated in P2 cleanup.

### 5. Refactor by priority

- **P0** (Immediate): Remove active duplication/leaks that create immediate drift risk.
- **P1** (Near-term): Reduce modeling ambiguity (IP ownership, security intent).
- **P2** (Hardening): Tighten governance and complete cleanup.

## Consequences

### Benefits

- Lower drift risk between declared intent and generated artifacts.
- Clear per-layer ownership aligned with `topology/MODULAR-GUIDE.md`.
- Safer future migrations due to explicit phased contract.
- Validator rules prevent regression to legacy patterns.

### Trade-offs

- Transitional updates in generators/templates are required while compatibility fields are phased out.
- Some docs views still use structural runtime projections until full runtime-only templating is complete.
- P1 IP ownership change requires generator updates before topology cleanup.

### Migration impact

- Backward compatibility is preserved by generator-side projection.
- Source topology authoring is tightened around canonical runtime and physical-only L1 model.
- Rollback is possible via git revert and validation gate.

## Validation Requirements

### P0 validator rules (new)

```python
# Block legacy fields in authored L5 services
def check_no_legacy_service_fields(service):
    forbidden = ['container', 'native']
    for field in forbidden:
        if field in service:
            raise ValidationError(
                f"Legacy field '{field}' in {service['id']}. "
                f"Use runtime.type instead."
            )

# Block non-physical keys in L1 devices
def check_l1_physical_only(device):
    forbidden = ['services', 'applications', 'runtime']
    for field in forbidden:
        if field in device:
            raise ValidationError(
                f"Non-physical field '{field}' in L1 device {device['id']}"
            )
```

### Validation gate (run after each batch)

```bash
# Strict validation
python topology-tools/validate-topology.py --topology topology.yaml --strict

# Regenerate and verify
python topology-tools/regenerate-all.py
git diff --stat generated/

# Mermaid diagram validation
python topology-tools/validate-mermaid-render.py --docs-dir generated/docs
```

### Fixture matrix governance gate

```bash
# Enforces baseline migration item counts:
# legacy-only=62, mixed=6, new-only=0
python topology-tools/run-fixture-matrix.py

# Temporary bypass for intentional fixture migration updates
python topology-tools/run-fixture-matrix.py --allow-migration-drift
```

## References

- Contracts:
  - `topology/MODULAR-GUIDE.md`
- Related ADRs:
  - `adr/0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md`
  - `adr/0038-network-binding-contracts-phase1.md`
- Topology modules:
  - `topology/L1-foundation/devices/`
  - `topology/L5-application/services.yaml`
- Validators and generators:
  - `topology-tools/scripts/validators/checks/references.py`
  - `topology-tools/scripts/generators/docs/generator.py`
  - `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- Execution plan:
  - `docs/architecture/L0-L5-REFACTORING-PLAN.md`
