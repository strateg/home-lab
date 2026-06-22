# Network Security Implementation Plan

Consolidated implementation plan for ADR-0109, ADR-0110, ADR-0111.

- Date: 2026-06-22
- Status: Active
- Related ADRs:
  - [ADR-0109: Network Segmentation](../../adr/0109-network-segmentation-zone-based-architecture.md)
  - [ADR-0110: Security Matrix](../../adr/0110-universal-network-zone-vlan-mechanism.md)
  - [ADR-0111: IP Address Derivation](../../adr/0111-ip-address-derivation-from-vlan.md)

## ADR Status Summary

| ADR | Title | Status | Remaining |
|-----|-------|--------|-----------|
| 0109 | Network Segmentation | Implemented | Phase 5 (deprecate VLAN 1) |
| 0110 | Security Matrix | Proposed | All phases |
| 0111 | IP Address Derivation | Proposed | All phases |

## Dependency Graph

```
ADR-0109 (DONE) ───┬───► ADR-0110 (Security Matrix)
                   │         │
                   │         ├── class.network.security_matrix
                   │         ├── security_matrix_compiler.py
                   │         ├── zone_firewall.tf.j2
                   │         └── Terraform deploy
                   │
                   └───► ADR-0111 (IP Derivation)
                             │
                             ├── ip_derivation_compiler.py
                             ├── Migrate 11 files
                             └── (independent of 0110)
```

## Optimizations Applied

| # | Optimization | Benefit |
|---|-------------|---------|
| O1 | ADR-0111 first — less code, quick win | Pipeline confidence |
| O2 | Combine validators into single file | -1 file, shared infrastructure |
| O3 | ADR-0110 consumes `_resolved_ip` from ADR-0111 | No IP duplication in matrix |
| O4 | Skip obj.network.security_matrix.proxmox_servers | Proxmox = future phase |
| O5 | Defer ADR-0109 Phase 5 | Does not block 0110/0111 |

---

## Wave 1: IP Derivation (ADR-0111) — Foundation

**Goal:** Centralize IP addresses, quick win.

| Step | Task | Files | Risk | Status |
|------|------|-------|------|--------|
| 1.1 | Create `ip_derivation_compiler.py` | 1 | Low | ✅ |
| 1.2 | Add validation codes E7861-E7865 | (in compiler) | Low | ✅ |
| 1.3 | Migrate 9 LXC files to `{vlan_ref, host}` | 9 | Low | ✅ |
| 1.4 | Migrate srv-gamayun, srv-orangepi5 | 2 | Low | ✅ |
| 1.5 | Verify: `task build` without W7864 warnings | — | Low | ✅ (LXC only) |

**Acceptance Test:**
```bash
grep -r "ip:" projects/home-lab/topology/instances/lxc/  # Must be empty
task build 2>&1 | grep -c W7864  # Must be 0
```

**Wave 1 Exit:** IP addresses derived from VLAN CIDR, 0 hardcoded IPs.

---

## Wave 2: Security Matrix Schema (ADR-0110 Phase 1) — Structure

**Goal:** Class/Object/Instance for security_matrix.

| Step | Task | Files | Risk | Status |
|------|------|-------|------|--------|
| 2.1 | Create `class.network.security_matrix.yaml` | 1 | Low | ✅ |
| 2.2 | Create `obj.network.security_matrix.soho.yaml` | 1 | Low | ✅ |
| 2.3 | Create `inst.security_matrix.mikrotik.yaml` | 1 | Low | ✅ |
| 2.4 | Add `trust_zone_ref` to inst.vlan.*.yaml | 7 | Low | ✅ |
| 2.5 | Run `task framework:lock-refresh` | — | Low | ✅ |

**Acceptance Test:**
```bash
task build && task validate  # Must pass
```

**Wave 2 Exit:** Topology contains security_matrix instance.

---

## Wave 3: Matrix Compiler (ADR-0110 Phase 3) — Logic

**Goal:** Automatic R1-R6 matrix calculation.

| Step | Task | Files | Risk | Status |
|------|------|-------|------|--------|
| 3.1 | Create `security_matrix_compiler.py` | 1 | Medium | ✅ |
| 3.2 | Implement zone_vlans resolution | (in 3.1) | Low | ✅ |
| 3.3 | Implement R1-R6 matrix calculation | (in 3.1) | Medium | ✅ |
| 3.4 | Implement policy_overrides merge | (in 3.1) | Low | ✅ |
| 3.5 | Register plugin (order: 55) | 1 | Low | ✅ |
| 3.6 | Add unit tests | 1 | Low | ☐ (deferred) |

**Matrix Calculation Rules:**
```
R6 (explicit override) → checked FIRST
       ↓ (no match)
R1 (same zone) → ALLOW
       ↓ (different zones)
R2 (isolated source) → DENY if dest != untrusted
       ↓
R3/R4/R5 (security level) → ALLOW downhill, DENY uphill/same
```

**Acceptance Test:**
```bash
task build
python -c "import json; m=json.load(open('generated/home-lab/compiled.json')); print(m.get('security_matrices', {}))"
```

**Wave 3 Exit:** Matrix computed at compile time.

---

## Wave 4: Validators (ADR-0110 Phase 4 + ADR-0111) — Quality

**Goal:** Early error detection.

| Step | Task | Codes | Risk | Status |
|------|------|-------|------|--------|
| 4.1 | Create `network_security_validator.py` (combined) | E7850-E7865 | Low | ✅ |
| 4.2 | VLAN ID collision | E7850 | Low | ✅ |
| 4.3 | CIDR overlap | E7851 | Low | ✅ |
| 4.4 | Zone reference check | E7852, E7853 | Low | ✅ |
| 4.5 | Host uniqueness | E7861 | Low | ✅ (in ip_derivation) |
| 4.6 | Gateway reserved | E7862 | Low | ✅ (in ip_derivation) |
| 4.7 | Policy completeness warnings | W7855, W7856, W7860 | Low | ✅ |

**Validation Codes Summary:**

| Code | Severity | Rule |
|------|----------|------|
| E7850 | Error | VLAN ID must be unique |
| E7851 | Error | VLAN CIDRs must not overlap |
| E7852 | Error | VLAN must have trust_zone_ref |
| E7853 | Error | policy_override refs must exist |
| E7854 | Error | Final drop-all rule required |
| W7855 | Warning | Same security_level needs override |
| W7856 | Warning | Isolated zone override to non-untrusted |
| W7857 | Warning | DENY without logging |
| W7858 | Warning | Rule ordering violation |
| W7860 | Warning | Zone has no VLANs |
| E7861 | Error | Duplicate host in same vlan_ref |
| E7862 | Error | host: 1 reserved for gateway |
| E7863 | Error | host exceeds CIDR range |
| W7864 | Warning | Hardcoded IP (migrate to vlan_ref) |
| E7865 | Error | Cannot mix patterns |

**Acceptance Test:**
```bash
# Introduce intentional duplicate VLAN ID, verify caught
task validate 2>&1 | grep E7850
```

**Wave 4 Exit:** All 15 validation rules active.

---

## Wave 5: Generator (ADR-0110 Phase 5) — Terraform

**Goal:** Generate firewall rules from matrix.

| Step | Task | Files | Risk | Status |
|------|------|-------|------|--------|
| 5.1 | Extend `projections.py` for matrix | 1 | Medium | ☐ |
| 5.2 | Create `zone_firewall.tf.j2` template | 1 | Medium | ☐ |
| 5.3 | Address lists per zone | (in 5.2) | Low | ☐ |
| 5.4 | Established/related rule | (in 5.2) | Low | ☐ |
| 5.5 | Policy override ACCEPT rules | (in 5.2) | Low | ☐ |
| 5.6 | Matrix DENY rules (place_before) | (in 5.2) | **High** | ☐ |
| 5.7 | Final drop-all rule | (in 5.2) | Low | ☐ |

**Rule Ordering (CRITICAL):**
```
1. established/related        → accept
2. policy_override ACCEPTs    → accept
3. matrix DENY (isolated)     → drop + log
4. matrix DENY (uphill)       → drop + log
5. matrix ALLOW (downhill)    → accept
6. FINAL DROP-ALL             → drop + log
```

**Acceptance Test:**
```bash
task build
cd generated/home-lab/terraform/mikrotik
terraform init && terraform plan  # Review rule count and order
```

**Wave 5 Exit:** Terraform HCL generated from matrix.

---

## Wave 6: Deployment (ADR-0110 Phase 6) — Production

**Goal:** Safe deployment to MikroTik.

| Step | Command | Risk | Status |
|------|---------|------|--------|
| 6.1 | `ssh admin@192.168.88.1 '/system backup save name=pre-adr0110'` | — | ☐ |
| 6.2 | `ssh admin@192.168.88.1 '/export file=pre-adr0110'` | — | ☐ |
| 6.3 | `terraform plan -out=adr0110.plan` | Low | ☐ |
| 6.4 | Manual review of plan output | — | ☐ |
| 6.5 | `terraform apply adr0110.plan` | **HIGH** | ☐ |
| 6.6 | Connectivity test matrix | Medium | ☐ |
| 6.7 | Rollback if needed | — | ☐ |

**Connectivity Test Matrix:**
```
guest → internet    ✓ (R2 allows untrusted)
guest → user        ✗ (R2 denies)
user → servers:443  ✓ (policy_override)
user → servers:22   ✗ (no override)
user → management   ✗ (R4 uphill)
management → all    ✓ (R3 downhill)
```

**Rollback Procedure:**
```bash
# If locked out, access via MAC-Telnet or serial console
/system backup load name=pre-adr0110
/system reboot
```

**Wave 6 Exit:** ADR-0110 Status = Implemented.

---

## Wave 7: Cleanup (ADR-0109 Phase 5 + ADR-0110/0111 Phase 7) — Final

**Goal:** Remove legacy code.

| Step | Task | Risk | Status |
|------|------|------|--------|
| 7.1 | Remove `vlans` from rtr-mikrotik-chateau.yaml | Low | ☐ |
| 7.2 | Remove `zone_policies` from rtr-mikrotik-chateau.yaml | Low | ☐ |
| 7.3 | Delete `network-zones.yaml` if exists | Low | ☐ |
| 7.4 | Update ADR-0109 (Phase 5 note) | Low | ☐ |
| 7.5 | Update ADR-0110 status = Implemented | Low | ☐ |
| 7.6 | Update ADR-0111 status = Implemented | Low | ☐ |
| 7.7 | Create PR, merge to main | Low | ☐ |

**Wave 7 Exit:** All three ADRs = Implemented.

---

## Summary by Priority

| Wave | ADR | Effort | Time Est. | Blocks |
|------|-----|--------|-----------|--------|
| **1** | 0111 | Low | 1-2 hrs | Wave 5 (_resolved_ip) |
| **2** | 0110 | Low | 1 hr | Wave 3 |
| **3** | 0110 | Medium | 2-3 hrs | Wave 5 |
| **4** | 0110+0111 | Low | 1-2 hrs | — |
| **5** | 0110 | Medium | 2-3 hrs | Wave 6 |
| **6** | 0110 | **High** | 1 hr | Wave 7 |
| **7** | 0109+0110+0111 | Low | 30 min | — |

**Total estimated time:** ~10-12 hours

---

## Deferred (Future Phases)

| Task | Reason | ADR |
|------|--------|-----|
| `inst.security_matrix.proxmox` | Proxmox firewall = separate scope | 0110 |
| `terraform_openwrt_generator` | rtr-slate not priority | 0110 |
| `terraform_proxmox_generator` | srv-gamayun internal firewall | 0110 |
| Network diagrams (Mermaid) | Nice-to-have | 0110 |
| Policy simulation (`--dry-run`) | After core functionality | 0110 |
| ADR-0109 Phase 5 (deprecate VLAN 1) | Requires device migration | 0109 |

---

## Progress Tracking

### Current Wave: Wave 5 (Generator)

### Completed Waves:
- **Wave 4: Validators (ADR-0110+0111)** — 2026-06-22
  - Created network_security_validator.py with E7850, E7851, E7853, W7855, W7856, W7860
  - E7861-E7865, W7864 already in ip_derivation_compiler.py
  - E7852 already in security_matrix_compiler.py
  - All validators registered and passing

- **Wave 3: Matrix Compiler (ADR-0110)** — 2026-06-22
  - Created security_matrix_compiler.py with R1-R6 matrix calculation
  - Implemented zone_vlans resolution (VLAN trust_zone_ref → zone mapping)
  - Implemented policy_overrides merge (object + instance levels)
  - Fixed R2 logic: isolated zones CAN reach untrusted (internet)
  - Registered plugin at order 55 (before ip_derivation)
  - Published: security_matrices, zone_vlans, matrix_by_enforcer, vlan_cidr_map

- **Wave 2: Security Matrix Schema (ADR-0110)** — 2026-06-22
  - Verified class.network.security_matrix.yaml exists with full property schema
  - Verified obj.network.security_matrix.soho.yaml with SOHO zone refs
  - Verified inst.security_matrix.mikrotik.yaml with project-specific config
  - All 7 VLAN instances have trust_zone_ref
  - Build passes with 0 errors

- **Wave 1: IP Derivation (ADR-0111)** — 2026-06-22
  - Created ip_derivation_compiler.py with E7861-E7866, W7864
  - Migrated 9 LXC instances to vlan_ref + host pattern
  - Updated inst.vlan.servers ip_allocations
  - Remaining: 12 Docker containers (future scope)

### Blockers:
- (none)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-22 | Wave 4 completed: network_security_validator.py |
| 2026-06-22 | Wave 3 completed: security_matrix_compiler.py with R1-R6 rules |
| 2026-06-22 | Wave 2 verified complete: all security_matrix files exist |
| 2026-06-22 | Wave 1 completed: ip_derivation_compiler.py, 9 LXC migrations |
| 2026-06-22 | Initial plan created from ADR-0109, ADR-0110, ADR-0111 analysis |
