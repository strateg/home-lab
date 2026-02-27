# ADR 0048: Topology v4 Architecture Consolidation

**Date:** 2026-02-28
**Status:** Accepted
**Supersedes:** ADR 0049 (all variants), 0050
**Related:** ADR 0047 (L6 Observability Modularization)

---

## Context

This ADR consolidates multiple related architectural decisions into a single coherent document:
- L0 Meta Layer architecture (abstract policies only)
- Tool version management
- L6 Observability structure
- Scalability strategy

**Current State:**
- Home-lab has ~10 devices, ~10 services, ~20 alerts
- Topology v4.0.0 with 8-layer OSI-like structure
- Generators and validators functional but not optimized

**Goal:** Establish clear architectural principles that scale from current size to 10x growth without over-engineering.

---

## Decisions

### 1. L0 Meta Layer: Abstract Policies Only

**Principle:** L0 defines WHAT (policies), not HOW (implementations).

**L0 Contains:**
- Version and metadata
- Security policies (baseline/strict/relaxed)
- Global defaults (abstract values only)
- Tool version requirements
- Naming conventions

**L0 Does NOT Contain:**
- Device references (L1)
- IP addresses (L2)
- Port numbers (L5)
- Hostnames
- Any references to L1-L7

**Dependency Direction:** One-way only: L1-L7 read from L0, never vice versa.

```yaml
# L0-meta/_index.yaml - ALLOWED
version: 4.0.0
security_constraints:
  encryption_required: true      # Policy (abstract)
  min_tls_version: "1.2"         # Standard (abstract)
tools:
  terraform:
    core: ">= 1.0.0"             # Requirement (abstract)

# NOT ALLOWED in L0
primary_router_ip: 192.168.88.1  # Concrete value!
device_ref: mikrotik-chateau     # Reference to L1!
```

### 2. Tool Version Management

**Location:** `L0-meta/_index.yaml` under `tools:` key

**Purpose:**
- Single source of truth for tool versions
- Validators check compatibility before generation
- Generated code includes version metadata

**Implementation:**

```yaml
# L0-meta/_index.yaml
tools:
  terraform:
    core: ">= 1.0.0"
    providers:
      proxmox: "~> 0.45.0"
      routeros: "~> 1.40.0"
  ansible:
    core: ">= 2.10.0"
  python:
    core: "~> 3.11.0"
```

**Validator:** `topology-tools/validators/version_validator.py`
- Checks installed versions against L0 requirements
- Reports mismatches before generation fails
- Breaking changes database: `topology-tools/data/breaking-changes.yaml`

**Usage:**
```bash
python topology-tools/validators/version_validator.py --check-all
```

### 3. L6 Observability Structure

**Current Structure (sufficient for <50 alerts):**
```
L6-observability/
├── healthchecks.yaml
├── alerts.yaml
└── dashboards.yaml
```

**Future Structure (when alerts > 50):**
```
L6-observability/
├── healthchecks/
│   ├── by-service/
│   └── by-component/
├── alerts/
│   ├── definitions/     # Reusable templates
│   └── policies/        # Service-specific bindings
├── dashboards/
└── sla-slo/
```

**Template + Policy Pattern (deferred):**
- Alert templates define reusable conditions
- Alert policies bind templates to services
- Implement when alert count exceeds 50

### 4. Naming Conventions

**Hierarchical Naming (ready for scale):**

| Entity | Pattern | Example |
|--------|---------|---------|
| Service | `svc-<domain>.<name>` | `svc-web.nextcloud` |
| Alert | `alert-<domain>.<service>-<type>` | `alert-web.nextcloud-down` |
| Dashboard | `dash-<layer>-<domain>` | `dash-app-web` |

**Validator Enforcement:**
```python
NAMING_PATTERNS = {
    'service_id': r'^svc-[a-z]+\.[a-z0-9_-]+$',
    'alert_id': r'^alert-[a-z]+\.[a-z0-9_-]+-[a-z-]+$',
}
```

### 5. Scalability Strategy (Phased)

**Phase 1: Current (n < 30 devices)**
- Simple flat file structure
- Basic validators (O(n) acceptable)
- Manual alert/dashboard definitions

**Phase 2: Medium Scale (30 < n < 100)**
- Hierarchical file organization
- Naming convention enforcement
- Template-based alerts

**Phase 3: Large Scale (n > 100)**
- Validator caching (O(n) index lookups)
- Incremental generation (component-based)
- Auto-generated L6 from L5 service definitions

**Decision:** Implement Phase 1 now. Defer Phase 2/3 until actual growth requires it.

---

## Implementation

### Completed

1. **L0 Structure:** `L0-meta/_index.yaml` with tool versions
2. **Version Validator:** `topology-tools/validators/version_validator.py`
3. **Breaking Changes DB:** `topology-tools/data/breaking-changes.yaml`
4. **Version validator integrated:** `validate-topology.py --check-tools`
5. **Security policy:** `L0-meta/security/baseline.yaml`
6. **Naming conventions:** Documented in `CLAUDE.md`

### Pending

1. **Naming convention validator** (when services > 20)

---

## Consequences

### Positive
- Clear L0 abstraction boundary
- Tool version mismatches caught early
- Naming conventions prevent collisions
- Scalability path defined without over-engineering

### Trade-offs
- Additional validator complexity
- Breaking changes DB requires maintenance
- Phased approach means some refactoring later

### Risks Mitigated
- No premature optimization for 10x scale
- No over-engineering for current home-lab size
- Clear decision points for future phases

---

## Success Criteria

- [x] L0 contains only abstract policies (no device refs, no IPs)
- [x] Tool versions defined in L0 and validated
- [x] Breaking changes database exists
- [x] Version validator integrated into pipeline
- [x] Naming conventions documented

---

## References

- `topology/L0-meta/_index.yaml` - Current L0 implementation
- `topology-tools/validators/version_validator.py` - Version validator
- `topology-tools/data/breaking-changes.yaml` - Breaking changes DB
- `CLAUDE.md` - Layer architecture documentation

---

## Appendix: Version Constraint Syntax

| Syntax | Meaning | Example |
|--------|---------|---------|
| `>= X.Y.Z` | Any version >= specified | `>= 1.0.0` |
| `~> X.Y.Z` | Same major, minor >= specified | `~> 1.5.0` allows 1.5.x, 1.6.x |
| `X.Y.Z` | Exact version | `1.5.7` |

---

**Approval:** Accepted
**Review Date:** 2026-02-27
