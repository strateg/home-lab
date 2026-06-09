# ADR 0104 SWOT Analysis

**Date:** 2026-06-09
**Methodology:** SPC (Strict Process Compliance) 7-step protocol
**Subject:** Ansible Role Generation from Topology

---

## Executive Summary

ADR 0104 proposes eliminating data duplication between topology definitions and manual Ansible artifacts by implementing an `AnsibleRoleGenerator` plugin. This analysis validates the approach against existing architectural constraints and identifies gaps requiring ADR improvement before implementation.

---

## SWOT Matrix

### Strengths

| ID | Strength | Evidence |
|----|----------|----------|
| S1 | Topology already contains all required data | 15/15 Ansible variables traceable to topology sources |
| S2 | Established generator pattern exists | `ansible_inventory_generator.py` provides reference implementation |
| S3 | Capability marker already defined | `cap.network.vpn_gateway` present in `vps-oracle-frankfurt.yaml` |
| S4 | Plugin architecture mature | ADR 0063/0086/0097 fully implemented, 98.8% plugins in subinterpreter mode |
| S5 | Clean role structure | Static logic (tasks/handlers) separated from variable data |
| S6 | Projection-first pattern validated | `build_ansible_projection()` exists with 150 lines of working code |
| S7 | Artifact contract established | `artifact_contract.py` provides plan/report generation |

### Weaknesses

| ID | Weakness | Impact | Mitigation |
|----|----------|--------|------------|
| W1 | ADR 0104 missing ADR 0097 reference | Plugin may lack `execution_mode` declaration | Update ADR constraints section |
| W2 | No projection builder for roles | Blocks implementation | Create `build_ansible_role_projection()` |
| W3 | No Jinja2 templates exist | Blocks implementation | Create templates from manual files |
| W4 | Secrets derivation logic implicit | Unclear implementation path | Document in ADR Decision section |
| W5 | Single capability scope | Limited initial value | Acceptable for MVP, document extension path |
| W6 | Incomplete capability code example | Unclear implementation guidance | Expand code in ADR |

### Opportunities

| ID | Opportunity | Value | Effort |
|----|-------------|-------|--------|
| O1 | Establish reusable pattern for future role generators | High | Medium |
| O2 | Eliminate entire class of configuration drift errors | High | Low (once implemented) |
| O3 | Enable CI validation of Ansible against topology | High | Low |
| O4 | Extend to other capabilities (container_host, monitoring) | High | Medium per capability |
| O5 | Reduce operator cognitive load | Medium | Low |
| O6 | Automated documentation generation | Medium | Low |

### Threats

| ID | Threat | Probability | Impact | Mitigation |
|----|--------|-------------|--------|------------|
| T1 | Role evolution requires schema changes | Medium | High | Version role schemas, CI validation |
| T2 | Compilation dependency adds operational step | Certain | Low | Document in workflow, Taskfile integration |
| T3 | Template maintenance burden | Medium | Medium | Keep templates minimal, data-driven |
| T4 | Secrets reference validation gap | Medium | Medium | Add validator plugin for secret refs |
| T5 | Generated vars incompatible with role | Low | High | CI `--check` mode validation |

---

## Problem Classification Summary

| Problem ID | Description | Classification | Severity |
|------------|-------------|----------------|----------|
| P1 | Data duplication topology ↔ Ansible | Data Model | High |
| P2 | Manual host_vars requires removal | Governance | High |
| P3 | No projection builder exists | Implementation Gap | Blocking |
| P4 | No Jinja2 templates exist | Implementation Gap | Blocking |
| P5 | ADR missing ADR 0097 reference | Design Gap | Blocking |
| P6 | Capability code incomplete | Design Gap | Medium |
| P7 | Secrets derivation undefined | Design Gap | Medium |
| P8 | Runtime assembly undefined | Operational Gap | Low |

---

## Data Duplication Evidence

| Data Element | Topology Source | Manual Ansible Location |
|--------------|-----------------|-------------------------|
| `tunnel_ip` | `vps-oracle-frankfurt.yaml:networking.tunnel_interfaces[0].tunnel_ip` | `host_vars/...wireguard.tunnel_ip` |
| `listen_port` | `vps-oracle-frankfurt.yaml:networking.tunnel_interfaces[0].listen_port` | `host_vars/...wireguard.listen_port` |
| `primary_interface` | `vps-oracle-frankfurt.yaml:networking.primary_interface` | `host_vars/...primary_interface` |
| `allowed_ips` | `inst.tunnel...endpoint_a.allowed_ips` | `host_vars/...wireguard_peers[0].allowed_ips` |
| `routed_networks` | `inst.vlan.vpn_germany.cidr` | `host_vars/...routed_networks[0].network` |
| `iptables_forward_rules` | `vps-oracle-frankfurt.yaml:wireguard_gateway.iptables_rules.forward` | `host_vars/...iptables_forward_rules` |
| `iptables_nat_rules` | `vps-oracle-frankfurt.yaml:wireguard_gateway.iptables_rules.nat` | `host_vars/...iptables_nat_rules` |

**Total duplicated elements:** 9 exact duplicates + 2 manual additions

---

## Constraint Compliance Matrix

| Constraint Source | Requirement | ADR 0104 Status | Gap |
|-------------------|-------------|-----------------|-----|
| ADR 0063 | Valid `depends_on` targets | ✓ Specified | None |
| ADR 0063 | Valid `consumes.from_plugin` | ✓ Specified | None |
| ADR 0074 D1 | Projection-first | ✓ Mentioned | Code not shown |
| ADR 0074 D4 | Order 200-239 | ✓ Order 235 | None |
| ADR 0074 D5 | Jinja2-only | ✓ Templates specified | None |
| ADR 0075 | Output to `generated/` | ✓ Specified | None |
| ADR 0086 | Plugin in `generators/` | ✓ Path specified | None |
| ADR 0097 | `execution_mode` declared | ✗ Not mentioned | **GAP** |
| ADR 0097 | Subinterpreter compatible | ✗ Not assessed | **GAP** |

---

## Admissible Solution Space

### ADR Improvements Required

1. **Add ADR 0097 to Constraints** — execution_mode declaration
2. **Add ADR 0097 to References** — traceability
3. **Expand capability code example** — full function signature
4. **Add capability → role mapping table** — extensibility
5. **Document secrets derivation logic** — clear contract
6. **Expand runtime assembly section** — operational clarity

### Implementation Components Required

1. **Projection builder:** `build_ansible_role_projection()` in `projections.py`
2. **Template:** `templates/ansible/host_vars/wireguard_gateway.yml.j2`
3. **Template:** `templates/ansible/playbooks/vpn-gateway.yml.j2`
4. **Generator plugin:** `ansible_role_generator.py`
5. **Manifest entry:** `plugins.yaml` update

### Migration Steps Required

1. Validate generated output matches manual
2. Archive manual files to `archive/ansible-manual/`
3. Update playbook paths to use generated inventory
4. Integration test with `--check` mode

---

## Recommendations

### Immediate (ADR Update)

1. Add ADR 0097 reference to Constraints and References
2. Add `execution_mode: subinterpreter` to manifest example
3. Expand capability-based triggering code
4. Document secrets path derivation algorithm
5. Add capability → role mapping table

### Implementation Phase

1. Follow existing `ansible_inventory_generator.py` pattern exactly
2. Create projection builder first (enables template development)
3. Use manual files as template starting point
4. Implement artifact contract (plan + report)

### Validation Phase

1. Diff generated vs manual host_vars
2. Run playbook with `--check --diff`
3. CI gate on generated artifact validation

---

## Conclusion

ADR 0104 is architecturally sound but requires specification improvements before implementation. The identified gaps (P5, P6, P7) are design-level issues resolvable by ADR update. Implementation gaps (P3, P4) are standard development work following established patterns.

**Risk assessment:** LOW — all required data exists, patterns established, constraints clear.

**Recommendation:** Proceed with ADR improvement, then implementation.
