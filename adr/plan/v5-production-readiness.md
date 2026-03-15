# V5 Production Readiness Plan

**Created:** 2026-03-15
**Goal:** Enable real home network modeling and deployment through v5 lane
**Current State:** v5 compiles topology to effective JSON, but cannot generate deployable artifacts

---

## Executive Summary

v5 architecture is model-complete with:
- 14 plugins (6 compilers, 6 validators, 2 generators)
- 33 classes, 62 objects, 68+ instances
- 7 cross-layer relations enforced
- Plugin microkernel operational

**Blocking Gap:** No Terraform/Ansible/Bootstrap generators in v5.

This plan delivers v5 generator plugins to achieve deployment parity with v4.

---

## Phase 1: Generator Plugin Framework

**Duration estimate:** 1 week
**Prerequisite:** None
**Deliverables:**

### 1.1 Generator Plugin Base Infrastructure

- [ ] Create `v5/topology-tools/plugins/generators/base_generator.py`
  - Abstract base for all generator plugins
  - Template loading helpers (Jinja2)
  - Output file management
  - Deterministic ordering utilities

- [ ] Define generator plugin contract in `plugins.yaml`
  - Stage: generate
  - Order: 200+ (after effective_json/yaml)
  - Input: `ctx.compiled_json` from compile stage

- [ ] Add generator integration tests
  - `v5/tests/plugin_integration/test_generator_base.py`

### 1.2 Template Migration Strategy

- [ ] Analyze v4 templates in `v4/topology-tools/templates/`
  - `terraform/proxmox/` (6 templates)
  - `terraform/mikrotik/` (7 templates)
  - `ansible/` (inventory templates)

- [ ] Create v5 template directory structure
  ```
  v5/topology-tools/templates/
  ├── terraform/
  │   ├── proxmox/
  │   └── mikrotik/
  └── ansible/
  ```

- [ ] Document template variable mapping (v4 topology → v5 effective model)

---

## Phase 2: Terraform Proxmox Generator

**Duration estimate:** 1 week
**Prerequisite:** Phase 1
**Deliverables:**

### 2.1 Generator Plugin Implementation

- [ ] Create `v5/topology-tools/plugins/generators/terraform_proxmox_generator.py`
  - Read L4 LXC/VM instances from effective model
  - Read L2 bridges from effective model
  - Read L3 storage pools from effective model
  - Generate: `provider.tf`, `bridges.tf`, `lxc.tf`, `vms.tf`, `variables.tf`, `outputs.tf`

- [ ] Register in `plugins.yaml`
  ```yaml
  - id: base.generator.terraform_proxmox
    kind: generator
    entry: plugins/generators/terraform_proxmox_generator.py:TerraformProxmoxGenerator
    api_version: "1.x"
    stages: [generate]
    order: 210
    depends_on: [base.generator.effective_json]
  ```

### 2.2 Template Adaptation

- [ ] Port templates from v4, adapting to v5 effective model structure
- [ ] Handle Class→Object→Instance resolution in templates
- [ ] Preserve v4 output format for parity testing

### 2.3 Parity Testing

- [ ] Create `v5/tests/plugin_regression/test_terraform_proxmox_parity.py`
- [ ] Compare v5-generated vs v4-generated Terraform
- [ ] Document intentional differences

---

## Phase 3: Terraform MikroTik Generator

**Duration estimate:** 1 week
**Prerequisite:** Phase 1
**Deliverables:**

### 3.1 Generator Plugin Implementation

- [ ] Create `v5/topology-tools/plugins/generators/terraform_mikrotik_generator.py`
  - Read L1 router instances with capabilities
  - Read L2 network configuration (VLANs, bridges, firewall)
  - Generate: `provider.tf`, `interfaces.tf`, `firewall.tf`, `dhcp.tf`, `vpn.tf`, `qos.tf`, `containers.tf`

- [ ] Register in `plugins.yaml`
  ```yaml
  - id: base.generator.terraform_mikrotik
    kind: generator
    entry: plugins/generators/terraform_mikrotik_generator.py:TerraformMikrotikGenerator
    api_version: "1.x"
    stages: [generate]
    order: 220
    depends_on: [base.generator.effective_json]
  ```

### 3.2 Capability-Driven Generation

- [ ] Use router capabilities from effective model to conditionally generate resources
- [ ] Handle MikroTik-specific vs GL.iNet-specific features

### 3.3 Parity Testing

- [ ] Create `v5/tests/plugin_regression/test_terraform_mikrotik_parity.py`

---

## Phase 4: Ansible Inventory Generator

**Duration estimate:** 1 week
**Prerequisite:** Phase 1
**Deliverables:**

### 4.1 Generator Plugin Implementation

- [ ] Create `v5/topology-tools/plugins/generators/ansible_inventory_generator.py`
  - Read L4 workloads (LXC, VMs) from effective model
  - Read L5 services and their deployment targets
  - Generate: `hosts.yml`, `group_vars/`, `host_vars/`

- [ ] Register in `plugins.yaml`
  ```yaml
  - id: base.generator.ansible_inventory
    kind: generator
    entry: plugins/generators/ansible_inventory_generator.py:AnsibleInventoryGenerator
    api_version: "1.x"
    stages: [generate]
    order: 230
    depends_on: [base.generator.effective_json]
  ```

### 4.2 Runtime Inventory Assembly

- [ ] Implement runtime inventory assembly (ADR 0051 compliance)
- [ ] Handle secret placeholders for Ansible Vault integration

### 4.3 Parity Testing

- [ ] Create `v5/tests/plugin_regression/test_ansible_inventory_parity.py`

---

## Phase 5: Bootstrap Generators

**Duration estimate:** 1 week
**Prerequisite:** Phases 2-4
**Deliverables:**

### 5.1 Proxmox Bootstrap Generator

- [ ] Create `v5/topology-tools/plugins/generators/bootstrap_proxmox_generator.py`
- [ ] Generate: `answer.toml`, post-install scripts
- [ ] Register in `plugins.yaml` (order: 240)

### 5.2 MikroTik Bootstrap Generator

- [ ] Create `v5/topology-tools/plugins/generators/bootstrap_mikrotik_generator.py`
- [ ] Generate: `init-terraform.rsc`, `terraform.tfvars.example`
- [ ] Register in `plugins.yaml` (order: 250)

### 5.3 Orange Pi Bootstrap Generator

- [ ] Create `v5/topology-tools/plugins/generators/bootstrap_orangepi_generator.py`
- [ ] Generate: cloud-init `user-data`, `meta-data`
- [ ] Register in `plugins.yaml` (order: 260)

---

## Phase 6: Hardware Identity Capture

**Duration estimate:** 3 days
**Prerequisite:** None (can run in parallel)
**Deliverables:**

### 6.1 Discovery Script

- [ ] Create `v5/topology-tools/discover-hardware-identity.py`
  - SSH to devices, capture MACs, serials
  - Output YAML patch for instance files
  - Support: MikroTik (SSH/API), Linux (SSH), Proxmox (SSH)

### 6.2 Instance Updates

- [ ] Replace placeholders in `v5/topology/instances/l1_devices/`
  - `rtr-mikrotik-chateau.yaml`: real MACs, serial
  - `rtr-slate.yaml`: real MACs, serial
  - `srv-gamayun.yaml`: real MACs, serial
  - `srv-orangepi5.yaml`: real MACs, serial

### 6.3 Enable E6806 Enforcement

- [ ] Update `instance_placeholder_validator.py` enforcement mode
- [ ] Verify no unresolved `@required:*` placeholders remain

---

## Phase 7: Integration and Validation

**Duration estimate:** 1 week
**Prerequisite:** Phases 2-6
**Deliverables:**

### 7.1 V4/V5 Parity Gate

- [ ] Create unified parity test suite
- [ ] Document all intentional differences
- [ ] Add CI job for parity validation

### 7.2 End-to-End Workflow

- [ ] Test full pipeline: `compile-topology.py` → generators → artifacts
- [ ] Validate generated Terraform with `terraform validate`
- [ ] Validate generated Ansible with `ansible-inventory --list`

### 7.3 Deployment Dry-Run

- [ ] `terraform plan` against test environment
- [ ] Ansible `--check` mode validation
- [ ] Document any blockers

---

## Phase 8: Documentation and Cutover

**Duration estimate:** 3 days
**Prerequisite:** Phase 7
**Deliverables:**

### 8.1 Update CLAUDE.md

- [ ] Make v5 primary lane for new work
- [ ] Document v5 workflow commands
- [ ] Mark v4 as maintenance-only

### 8.2 Operational Runbook

- [ ] Create `v5/docs/DEPLOYMENT.md`
- [ ] Document secret management workflow
- [ ] Document rollback procedures

### 8.3 ADR Updates

- [ ] Create ADR for v5 generator architecture
- [ ] Update ADR 0062 with cutover milestone
- [ ] Archive superseded v4 ADRs

---

## Success Criteria

1. **Generator Parity:** v5 generates equivalent Terraform/Ansible to v4
2. **No Placeholders:** All instance files have real hardware identities
3. **CI Green:** All parity and integration tests pass
4. **Deployable:** `terraform apply` and `ansible-playbook` succeed on real hardware

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Template incompatibility | Maintain v4 templates as reference; incremental porting |
| Model structure mismatch | Create mapping layer in generator plugins |
| Secret leakage | Add secret detection to CI; use placeholders in committed files |
| Regression in v4 | Keep v4 frozen; no changes during v5 development |

---

## Dependencies

```
Phase 1 (Framework)
    ├── Phase 2 (Proxmox TF)
    ├── Phase 3 (MikroTik TF)
    └── Phase 4 (Ansible)
            └── Phase 5 (Bootstrap)
                    └── Phase 7 (Integration)
                            └── Phase 8 (Cutover)

Phase 6 (Hardware) ──────────────────┘
```

Phase 6 can run in parallel with Phases 2-5.

---

## Tracking

Progress will be tracked in:
- GitHub Issues (one per phase)
- This document (checkbox updates)
- ADR status updates as milestones complete
