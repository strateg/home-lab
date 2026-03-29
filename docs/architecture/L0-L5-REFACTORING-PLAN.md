# L0-L5 Refactoring Plan (ADR-0040)

Status: Maintenance (P0, P1, P2 complete)
Date: 2026-02-23
Updated: 2026-02-24
Scope: `L0` .. `L5`

## Goals

1. Remove cross-layer ownership leaks.
2. Keep one canonical source of truth for runtime placement data.
3. Preserve generator compatibility during migration.
4. Reduce long-term model drift and maintenance cost.

## Current State Analysis

### L5 Legacy Field Instances

| Field | File | Line | Service ID |
|-------|------|------|------------|
| `container: true` | services.yaml | 35 | svc-adguard |
| `container: true` | services.yaml | 79 | svc-tailscale |
| `container: true` | services.yaml | 98 | svc-nextcloud |
| `container: true` | services.yaml | 139 | svc-jellyfin |
| `container: true` | services.yaml | 182 | svc-adguard-secondary |
| `container: true` | services.yaml | 201 | svc-prometheus |
| `container: true` | services.yaml | 241 | svc-alertmanager |
| `container: true` | services.yaml | 263 | svc-loki |
| `container: true` | services.yaml | 289 | svc-grafana |
| `container: true` | services.yaml | 316 | svc-homeassistant |
| `native: true` | services.yaml | 60 | svc-wireguard |
| `config.docker.host_ip` | services.yaml | 129, 172, 231, 306, 337 | 5 services |

### IP Ownership Current State

| Layer | Location | IP Examples |
|-------|----------|-------------|
| L2 | `net-servers.yaml:ip_allocations` | 10.0.30.1, 10.0.30.2, 10.0.30.50 (hosts) |
| L4 | `lxc-postgresql.yaml:networks[].ip` | 10.0.30.10/24 |
| L4 | `lxc-redis.yaml:networks[].ip` | 10.0.30.20/24 |
| L5 | `services.yaml:config.docker.host_ip` | 10.0.30.50 (duplicated) |

## Priority Matrix

### P0 (Immediate) - Remove Active Duplication

#### P0.1: L5 runtime canonicalization

**Goal**: Remove legacy runtime-type fields from services.yaml.

**Tasks**:
- [x] Remove `container: true` from 10 services
  - File: `topology/L5-application/services.yaml`
  - Lines: 35, 79, 98, 139, 182, 201, 241, 263, 289, 316
  - Acceptance: `grep -c "container: true" topology/L5-application/services.yaml` returns 0
- [x] Remove `native: true` from 1 service
  - File: `topology/L5-application/services.yaml`
  - Line: 60
  - Acceptance: `grep -c "native: true" topology/L5-application/services.yaml` returns 0
- [x] Verify all services have `runtime.type` set
  - Acceptance: validator passes with no "missing runtime.type" errors

#### P0.2: L1 physical-only guardrail

**Goal**: Add validator rule preventing non-physical keys in L1 devices.

**Tasks**:
- [x] Add validator check `check_l1_physical_only()`
  - File: `topology-tools/scripts/validators/checks/foundation.py`
  - Forbidden keys: `services`, `applications`, `runtime`
  - Acceptance: validator fails if forbidden key added to any L1 device
- [x] Audit existing L1 devices for violations
  - Path: `topology/L1-foundation/devices/**/*.yaml`
  - Acceptance: `grep -r "^services:\|^applications:\|^runtime:" topology/L1-foundation/devices/` returns empty

#### P0.3: L5 legacy field validator

**Goal**: Add validator rule blocking legacy fields in authored services.

**Tasks**:
- [x] Add validator check `check_no_legacy_service_fields()`
  - File: `topology-tools/scripts/validators/checks/references.py`
  - Forbidden keys: `container`, `native`
  - Acceptance: validator fails if `container: true` added to any service

### P1 (Near-term) - Reduce Modeling Ambiguity

#### P1.1: IP source-of-truth consolidation

**Goal**: Clarify IP ownership between L2/L4/L5.

**Decision**:
- L2 `ip_allocations` owns physical host IPs (via `host_os_ref`)
- L4 `workloads[].networks[].ip` owns workload IPs (LXC/VM)
- L5 `config.docker.host_ip` is deprecated (derive from target resolution)

**Tasks**:
- [x] Update generators to derive service IP from target resolution
  - If `runtime.target_ref` → L1 device: look up IP in L2 `ip_allocations`
  - If `runtime.target_ref` → L4 workload: look up IP in workload networks
- [x] Remove `config.docker.host_ip` from services.yaml
  - File: `topology/L5-application/services.yaml`
  - Lines: 129, 172, 231, 306, 337
  - Acceptance: `grep -c "host_ip:" topology/L5-application/services.yaml` returns 0
- [x] Add validator warning for deprecated `host_ip` usage

#### P1.2: Security intent alignment

**Goal**: Consistent `protocol` vs certificate/TLS intent for web services.

**Tasks**:
- [x] Audit services with `protocol: https` but no `security.ssl_certificate`
- [x] Define canonical pattern: `protocol` indicates transport, `security.ssl_certificate` indicates cert source
- [x] Document in MODULAR-GUIDE.md

### P2 (Hardening) - Governance and Cleanup

#### P2.1: L3 data_assets taxonomy enrichment

**Tasks**:
- [x] Add `category` field to data_assets (config, database, media, logs)
- [x] Add `criticality` field (`low|medium|high|critical`)
- [x] Add `backup_policy_refs` where applicable

#### P2.2: Metadata governance

**Tasks**:
- [x] Define `L0.metadata.last_updated` policy
- [x] Add pre-commit hook to auto-update timestamp
- [x] Document update triggers in MODULAR-GUIDE.md

#### P2.3: Generator compatibility cleanup

**Tasks**:
- [x] Remove compatibility projections for `container`/`native` from generators
- [x] Update doc templates to use only canonical fields
- [x] Remove deprecated field handling code

#### P2.4: Fixture governance hardening

**Tasks**:
- [x] Enforce exact migration-item baselines in `run-fixture-matrix.py`
- [x] Add controlled override flag (`--allow-migration-drift`) for intentional fixture updates
- [x] Document fixture baseline contract in topology tool READMEs

## Execution Sequence

### Pre-flight checklist

```bash
# Ensure clean state
git status  # should be clean or stashed

# Create safety tag
git tag pre-adr0040-$(date +%Y%m%d)

# Verify current validation passes
python topology-tools/validate-topology.py --topology topology.yaml --strict
```

### P0 execution order

1. **P0.2 first**: Add L1 guardrail validator (no topology changes yet)
2. **P0.3 second**: Add L5 legacy field validator (will fail until P0.1 done)
3. **P0.1 third**: Remove legacy fields from services.yaml
4. **Validate**: Run full validation gate

### P1 execution order

1. **P1.1.a**: Update generators to derive IP from target resolution
2. **P1.1.b**: Verify generated output unchanged (compatibility)
3. **P1.1.c**: Remove `host_ip` from services.yaml
4. **P1.2**: Security intent alignment (can parallel with P1.1)

### P2 execution order

Execute after P0 and P1 are stable. Order is flexible.

## Validation Gate

Run after each refactor batch:

```bash
# 1. Strict validation
python topology-tools/validate-topology.py --topology topology.yaml --strict

# 2. Regenerate all outputs
python topology-tools/regenerate-all.py

# 3. Verify no unexpected changes
git diff --stat generated/

# 4. Mermaid diagram validation
python topology-tools/utils/validate-mermaid-render.py --docs-dir generated/docs

# 5. Specific acceptance checks
echo "P0.1 acceptance:"
grep -c "container: true" topology/L5-application/services.yaml || echo "PASS: 0 instances"
grep -c "native: true" topology/L5-application/services.yaml || echo "PASS: 0 instances"

echo "P0.2 acceptance:"
grep -r "^services:\|^applications:\|^runtime:" topology/L1-foundation/devices/ || echo "PASS: no violations"
```

## Rollback Procedure

If validation fails or generators break:

```bash
# 1. Restore topology from git
git checkout topology/

# 2. Restore validators if changed
git checkout topology-tools/scripts/validators/

# 3. Verify rollback
python topology-tools/validate-topology.py --topology topology.yaml --strict

# 4. Remove safety tag if not needed
git tag -d pre-adr0040-*
```

## Success Criteria

### P0 Complete When

- [x] Zero `container: true` in services.yaml
- [x] Zero `native: true` in services.yaml
- [x] Validator blocks new legacy field additions
- [x] Validator blocks non-physical keys in L1
- [x] All generators produce identical output (compatibility preserved)

### P1 Complete When

- [x] Zero `host_ip:` in services.yaml
- [x] Generators derive IP from target resolution
- [x] Security intent pattern documented

### P2 Complete When

- [x] data_assets have category/criticality
- [x] Metadata auto-update implemented
- [x] No compatibility code in generators for removed fields
- [x] Fixture matrix enforces exact migration-item baselines for `legacy-only`, `mixed`, `new-only`

## Dependencies

- Generators must be updated BEFORE removing `host_ip` (P1.1)
- Validator rules can be added BEFORE or AFTER topology cleanup
- P2 can start after P0 validation passes

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Generator output changes | Compare `generated/` before/after each change |
| Validator too strict | Add `--skip-legacy-check` flag for transition |
| Rollback needed | Safety tag + documented procedure |
| Downstream breaks | Compatibility projection in generators until P2 |
