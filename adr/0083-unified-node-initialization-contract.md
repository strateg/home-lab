# ADR 0083: Unified Node Initialization Contract and Pre-Pipeline Bootstrap Phase

**Date:** 2026-03-30
**Status:** Proposed
**Related:** ADR 0057 (MikroTik Netinstall Bootstrap), ADR 0074 (V5 Generator Architecture), ADR 0080 (Unified Build Pipeline)

---

## Context

### Problem

The v5 build pipeline (`discover -> compile -> validate -> generate -> assemble -> build`) assumes nodes are already reachable and manageable by Terraform or Ansible. However, real deployment requires a **day-0 initialization phase** that brings physical devices to a state where automation tools can connect.

Currently, initialization is fragmented:

| Device Type | Current Mechanism | Handover Target | Status |
|-------------|-------------------|-----------------|--------|
| MikroTik Chateau | netinstall + RouterOS script (ADR 0057) | Terraform REST API | Well-defined |
| Proxmox VE | Manual post-install script (487 lines) | Terraform Proxmox API | Ad-hoc |
| Orange Pi 5 | cloud-init placeholder | SSH + Ansible | Incomplete |
| LXC Containers | Helper-scripts | Terraform Proxmox provider | Manual |
| Cloud VMs | Provider-specific | Terraform + Ansible | Implicit |

### Identified Gaps

1. **No unified contract** - Each device has different initialization semantics
2. **No topology integration** - Initialization scripts do not consume topology.yaml
3. **No validation gates** - No pre-flight checks or post-initialization verification
4. **Mixed responsibility** - Scripts combine day-0 bootstrap with day-1 configuration
5. **Secret handling inconsistency** - Different patterns for credential injection
6. **No plugin integration** - Initialization is outside the v5 pipeline stages

### ADR 0057 Foundation

ADR 0057 establishes a solid pattern for MikroTik:
- Two-phase lifecycle (day-0 bootstrap, day-1+ Terraform)
- MAC-targeted netinstall mechanism
- Minimal handover contract (management IP, API access, terraform user)
- Secret-bearing artifacts in ignored execution roots

This pattern should be generalized to all device types.

### Constraints

- Initialization mechanisms are inherently device-specific
- Some devices require physical access (SD card, USB, console)
- Network bootstrap (PXE, netinstall) requires installation-segment access
- Cloud devices use provider APIs (no pre-bootstrap phase)
- Secrets must remain outside tracked repository roots
- Existing manual workflows must continue working during transition

---

## Decision

### D1. Separation of Concerns: Pipeline vs Deploy Domains

The v5 pipeline and deploy domain have different responsibilities and execution cadences:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  V5 PIPELINE (artifact generation, runs MANY times)                         │
│  ═══════════════════════════════════════════════════                         │
│  discover -> compile -> validate -> generate -> assemble -> build            │
│                                         │                                    │
│                                         ▼                                    │
│                              Produces artifacts:                             │
│                              • bootstrap scripts                             │
│                              • terraform configs                             │
│                              • ansible playbooks                             │
│                              • initialization manifest                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DEPLOY DOMAIN (execution, different cadences)                              │
│  ═════════════════════════════════════════════                              │
│                                                                             │
│  Pre-initialization ──► Terraform/OpenTofu ──► Ansible                      │
│  (runs ONCE)            (runs MANY times)      (runs MANY times)            │
│       │                        │                      │                      │
│       ▼                        ▼                      ▼                      │
│  netinstall              tofu apply           ansible-playbook              │
│  cloud-init              tofu plan            firewall, backup              │
│  answer.toml                                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key principle:** The v5 pipeline generates artifacts from topology. The deploy domain executes them. Pre-initialization runs once per device lifecycle reset; Terraform/Ansible run many times for configuration improvements.

**Rationale:** The v5 pipeline operates on topology data and generates artifacts. It does not execute external commands against hardware. Pre-initialization requires device-specific execution (netinstall, flash, SSH) which belongs to the deploy domain.

### D2. Define Unified Node Initialization Contract

Every compute/router object module MAY declare an `initialization_contract` specifying how instances of that object are bootstrapped:

```yaml
# topology/object-modules/<domain>/obj.<domain>.<type>.yaml
object: obj.mikrotik.chateau_lte7_ax
# ... existing fields ...

initialization_contract:
  version: "1.0"
  mechanism: netinstall          # netinstall | unattended_install | cloud_init | terraform_managed | ansible_bootstrap

  requirements:                  # Prerequisites for bootstrap execution
    - netinstall_cli_installed
    - routeros_npk_available
    - installation_segment_access

  bootstrap:
    template: templates/bootstrap/init-terraform.rsc.j2
    outputs:
      - bootstrap/{{ instance_id }}/init-terraform.rsc

  handover:
    provider: terraform-routeros/routeros
    checks:
      - type: api_reachable
        protocol: https
        port: 8443
      - type: credential_valid
        user: terraform
```

### D3. Support Multiple Initialization Mechanisms

| Mechanism | Description | Devices |
|-----------|-------------|---------|
| `netinstall` | MAC-targeted network reinstall | MikroTik |
| `unattended_install` | Answer file + post-install script | Proxmox VE |
| `cloud_init` | cloud-init user-data on boot media | Orange Pi, SBCs |
| `terraform_managed` | Terraform creates and manages entirely | LXC, Cloud VMs |
| `ansible_bootstrap` | Ansible playbook after manual OS install | Generic Linux |

### D4. Keep Bootstrap Artifact Generation in V5 Pipeline

Bootstrap generators remain within the v5 pipeline as part of the `generate` stage:

```yaml
# From ADR 0074 D4 ordering
generate_stage:
  # ... existing generators ...
  - 300-309: bootstrap_proxmox_generator
  - 310-319: bootstrap_mikrotik_generator
  - 320-329: bootstrap_orangepi_generator
  - 330-339: bootstrap_lxc_generator         # NEW
  - 340-349: bootstrap_cloud_vm_generator    # NEW
  - 390-399: initialization_manifest_generator # NEW
```

**Key principle:** The v5 pipeline generates bootstrap artifacts. A separate orchestrator executes them.

### D5. Generate Unified Initialization Manifest

Add a new generator that produces `generated/<project>/bootstrap/INITIALIZATION-MANIFEST.yaml`:

```yaml
version: "1.0"
generated_at: 2026-03-30T12:00:00Z
project: home-lab

nodes:
  - id: rtr-mikrotik-chateau
    object_ref: obj.mikrotik.chateau_lte7_ax
    mechanism: netinstall
    status: pending                          # pending | initialized | verified | failed
    artifacts:
      bootstrap_script: bootstrap/rtr-mikrotik-chateau/init-terraform.rsc
      tfvars_example: bootstrap/rtr-mikrotik-chateau/terraform.tfvars.example
    requirements:
      - name: netinstall-cli
        check: command_exists
      - name: routeros-7.x.npk
        check: file_exists
        path: /srv/routeros/
    handover:
      provider: terraform-routeros/routeros
      endpoint: https://192.168.88.1:8443
      user: terraform
      checks:
        - api_reachable
        - credential_valid

  - id: hv-proxmox-xps
    object_ref: obj.proxmox.ve
    mechanism: unattended_install
    status: pending
    artifacts:
      answer_file: bootstrap/hv-proxmox-xps/answer.toml
      post_install: bootstrap/hv-proxmox-xps/post-install.sh
    requirements:
      - name: proxmox-ve-9.x.iso
        check: file_exists
    handover:
      provider: bpg/proxmox
      endpoint: https://10.0.10.1:8006
      user: root@pam
      checks:
        - api_reachable
        - credential_valid

  - id: sbc-orangepi5
    object_ref: obj.orangepi.rk3588.debian
    mechanism: cloud_init
    status: pending
    artifacts:
      user_data: bootstrap/sbc-orangepi5/user-data
      meta_data: bootstrap/sbc-orangepi5/meta-data
    requirements:
      - name: debian-12-arm64.img
        check: file_exists
    handover:
      provider: ansible
      endpoint: ssh://10.0.10.5:22
      user: opi
      checks:
        - ssh_reachable
        - python_installed
```

### D6. Pre-Initialization Orchestrator in Deploy Domain

Create `scripts/deploy/init-node.py` as part of the deploy domain (separate from v5 pipeline):

```
scripts/
  orchestration/
    lane.py              # V5 pipeline orchestrator (artifact generation)
  deploy/
    init-node.py         # Pre-initialization orchestrator (runs ONCE)
    apply-terraform.py   # Terraform wrapper (runs MANY times)
    run-ansible.py       # Ansible wrapper (runs MANY times)
```

**Execution cadence:**

| Script | Domain | Cadence | Purpose |
| ------ | ------ | ------- | ------- |
| `lane.py` | Pipeline | Many times | Generate artifacts from topology |
| `init-node.py` | Deploy | Once per device | Bootstrap new/reset device |
| `apply-terraform.py` | Deploy | Many times | Apply topology configuration |
| `run-ansible.py` | Deploy | Many times | Apply operational configuration |

**init-node.py responsibilities:**
1. Read `INITIALIZATION-MANIFEST.yaml` (generated by pipeline)
2. Check prerequisites per device
3. Execute device-specific bootstrap (netinstall, flash, etc.)
4. Run handover verification
5. Update manifest status
6. Output ready-for-terraform/ansible confirmation

**Usage pattern:**
```bash
# Initialize specific node (runs ONCE when device is new/reset)
python scripts/deploy/init-node.py --node rtr-mikrotik-chateau

# Initialize all pending nodes
python scripts/deploy/init-node.py --all-pending

# Verify handover only (no bootstrap)
python scripts/deploy/init-node.py --verify-only --node hv-proxmox-xps
```

### D7. Decompose Large Bootstrap Scripts

Existing monolithic scripts (e.g., `proxmox-post-install.sh`) must be decomposed:

**Proxmox VE decomposition:**

| Phase | Scope | Mechanism |
|-------|-------|-----------|
| Phase 0: Bootstrap | Minimal API access | `answer.toml` + `post-install-minimal.sh` |
| Phase 1: Infrastructure | Storage pools, bridges | Terraform |
| Phase 2: Configuration | Packages, KSM, sensors | Ansible |

**Bootstrap boundary rule:** Day-0 scripts prepare ONLY what Terraform needs to connect. Everything else is day-1 configuration.

### D8. Standardize Handover Verification

Each initialization contract must specify verifiable handover checks:

| Check Type | Description | Implementation |
|------------|-------------|----------------|
| `api_reachable` | HTTP(S) endpoint responds | `curl --connect-timeout 5` |
| `ssh_reachable` | SSH port open | `nc -z -w 5` |
| `credential_valid` | Auth succeeds | Provider-specific API call |
| `python_installed` | Python available for Ansible | `ssh <host> python3 --version` |
| `terraform_plan_succeeds` | Terraform can plan | `terraform plan -input=false` |

### D9. Keep Secret Contract Consistent with ADR 0072

Bootstrap secrets follow the unified secrets model (ADR 0072):

- Tracked templates remain secret-free
- Secret values come from `projects/<project>/secrets/` (SOPS-encrypted)
- Secret-bearing rendered artifacts exist only in ignored execution roots (`.work/native/`)

### D10. Add Initialization Contract Validator

Add a new validator to verify initialization contracts in object modules:

```yaml
# plugins.yaml
- id: base.validator.initialization_contract
  kind: validator_json
  stages: [validate]
  phase: post
  order: 180
  description: Validates initialization contracts for compute/router objects
  schema: schemas/initialization-contract.schema.json
```

### D11. Define Post-Handover Lifecycle Phases

After bootstrap handover, devices proceed through day-1+ configuration phases in the deploy domain. The initialization contract MAY specify `post_handover` to define the full IaC lifecycle:

```yaml
initialization_contract:
  # ... bootstrap and handover fields ...

  post_handover:
    terraform:
      provider: terraform-routeros/routeros
      modules:
        - mikrotik-base
        - mikrotik-vlans
        - mikrotik-wireguard
        - mikrotik-routing
    ansible:
      collection: community.routeros
      playbooks:
        - mikrotik-postconfig
        - mikrotik-firewall
        - mikrotik-validate
```

**Lifecycle phases and execution cadence:**

| Phase | Tool | Cadence | Responsibility |
| ----- | ---- | ------- | -------------- |
| Day-0: Bootstrap | Device-specific | **ONCE** | Minimal management access |
| Day-1+: Topology | OpenTofu/Terraform | **MANY** | State-managed objects (bridges, VLANs, IPs, routing) |
| Day-1+: Operations | Ansible | **MANY** | Ordered rules, scripts, hardening |
| Ongoing: Backup | Ansible | **MANY** | Text export + binary backup |

**Key insight:** Pre-initialization prepares the device ONCE. After that, the Terraform/Ansible improvement cycle runs MANY times as configuration evolves.

**Golden Rule:** One object must NOT be managed by both Terraform and Ansible simultaneously.

---

## Schema

### Initialization Contract Schema (JSONSchema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Node Initialization Contract",
  "type": "object",
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+$"
    },
    "mechanism": {
      "enum": ["netinstall", "unattended_install", "cloud_init", "terraform_managed", "ansible_bootstrap"]
    },
    "requirements": {
      "type": "array",
      "items": { "type": "string" }
    },
    "bootstrap": {
      "type": "object",
      "properties": {
        "template": { "type": "string" },
        "post_install": {
          "type": "array",
          "items": { "type": "string" }
        },
        "outputs": {
          "type": "array",
          "items": { "type": "string" }
        }
      },
      "required": ["template"]
    },
    "handover": {
      "type": "object",
      "properties": {
        "provider": { "type": "string" },
        "checks": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "type": { "type": "string" },
              "protocol": { "type": "string" },
              "port": { "type": "integer" },
              "user": { "type": "string" }
            },
            "required": ["type"]
          }
        }
      },
      "required": ["provider", "checks"]
    }
  },
  "required": ["version", "mechanism", "handover"]
}
```

---

## Device-Specific Patterns

### MikroTik (Reference: ADR 0057)

Full IaC pipeline: `Netinstall → Bootstrap .rsc → OpenTofu/Terraform → Ansible`

See detailed pattern: `adr/0083-analysis/MIKROTIK-IAC-PATTERN.md`

```yaml
initialization_contract:
  version: "1.0"
  mechanism: netinstall
  requirements:
    - netinstall_cli_installed
    - routeros_npk_available
    - installation_segment_access
  bootstrap:
    template: templates/bootstrap/init-terraform.rsc.j2
  handover:
    provider: terraform-routeros/routeros
    checks:
      - type: api_reachable
        protocol: https
        port: 8443
      - type: credential_valid
        user: terraform
  post_handover:
    terraform:
      provider: terraform-routeros/routeros
      modules:
        - mikrotik-base
        - mikrotik-vlans
        - mikrotik-wireguard
        - mikrotik-routing
    ansible:
      collection: community.routeros
      playbooks:
        - mikrotik-postconfig
        - mikrotik-firewall
        - mikrotik-validate
        - mikrotik-backup
```

**Object ownership:**

| Owner | Objects |
| ----- | ------- |
| OpenTofu | bridge, VLAN, IP address, interface list, WireGuard, DHCP, routing, address-list |
| Ansible | firewall filter/nat/mangle, scripts, scheduler, backup jobs, hardening |

### Proxmox VE

```yaml
initialization_contract:
  version: "1.0"
  mechanism: unattended_install
  requirements:
    - proxmox_iso_available
    - answer_toml_rendered
    - installation_media_prepared
  bootstrap:
    template: templates/bootstrap/answer.toml.j2
    post_install:
      - templates/bootstrap/post-install-minimal.sh.j2
  handover:
    provider: bpg/proxmox
    checks:
      - type: api_reachable
        protocol: https
        port: 8006
      - type: credential_valid
        user: root@pam
```

### Orange Pi 5 (SBC with cloud-init)

```yaml
initialization_contract:
  version: "1.0"
  mechanism: cloud_init
  requirements:
    - base_image_available
    - cloud_init_user_data_rendered
  bootstrap:
    template: templates/bootstrap/user-data.j2
    outputs:
      - bootstrap/{{ instance_id }}/user-data
      - bootstrap/{{ instance_id }}/meta-data
  handover:
    provider: ansible
    checks:
      - type: ssh_reachable
        port: 22
      - type: python_installed
```

### LXC Containers (Terraform-managed)

```yaml
initialization_contract:
  version: "1.0"
  mechanism: terraform_managed
  requirements: []
  bootstrap:
    template: null  # No separate bootstrap - Terraform creates container
  handover:
    provider: bpg/proxmox
    checks:
      - type: terraform_plan_succeeds
```

---

## Migration Path

### Phase 1: Contract Definition

1. Create `schemas/initialization-contract.schema.json`
2. Add `initialization_contract` to object module schema
3. Update MikroTik object module with contract (already ADR 0057 compliant)
4. Document contract in CLAUDE.md

### Phase 2: Generator Enhancement

1. Update existing bootstrap generators to read contract from object modules
2. Add `base.generator.initialization_manifest` generator
3. Ensure all generators use projection-first pattern (ADR 0074)

### Phase 3: Add Missing Device Support

1. Refactor Proxmox `post-install.sh` into minimal bootstrap + day-1 config
2. Complete Orange Pi cloud-init template
3. Add LXC/Cloud VM bootstrap patterns

### Phase 4: Orchestration

1. Create `scripts/orchestration/init-node.py`
2. Implement device adapters for each mechanism
3. Add handover verification suite
4. Integration tests with mock devices

### Phase 5: Documentation

1. Create `docs/guides/NODE-INITIALIZATION.md`
2. Add Taskfile targets for initialization workflow
3. Update operator runbooks

---

## Consequences

### Positive

1. **Unified contract** across all device types
2. **Clear day-0/day-1 boundary** prevents configuration drift
3. **Topology-driven bootstrap** - artifacts generated from single source of truth
4. **Verifiable handover** - automated checks before Terraform/Ansible takeover
5. **Consistent with ADR 0057** - extends proven MikroTik pattern
6. **Plugin architecture alignment** - bootstrap generation uses v5 generators

### Negative and Trade-offs

1. **Additional complexity** - new schema, validator, orchestrator
2. **Device-specific adapters** - each mechanism needs implementation
3. **Hardware testing** - full E2E requires physical devices
4. **Migration effort** - existing scripts need decomposition
5. **Parallel paths** - current manual workflows must work during transition

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bootstrap scripts become complex | Maintenance burden | Strict day-0/day-1 boundary |
| Device-specific logic leaks to core | Plugin boundary violation | Contract validates templates in object modules |
| Secret handling inconsistency | Security risk | Enforce `.work/native/` for all secrets |
| Testing requires real hardware | CI gaps | Mock adapters for CI; hardware E2E as release gate |

---

## References

- ADR 0057: MikroTik Chateau Netinstall Bootstrap and Terraform Handover
- ADR 0072: Unified Secrets Management with SOPS and age
- ADR 0074: V5 Generator Architecture
- ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle
- `adr/0083-analysis/GAP-ANALYSIS.md` - Current vs target state analysis
- `adr/0083-analysis/IMPLEMENTATION-PLAN.md` - Phased implementation plan
- `adr/0083-analysis/CUTOVER-CHECKLIST.md` - Migration gate checklist
- `adr/0083-analysis/MIKROTIK-IAC-PATTERN.md` - MikroTik full IaC pipeline pattern
- `archive/migrated-and-archived/old_system/proxmox/scripts/proxmox-post-install.sh`
- `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2`
- [terraform-routeros/routeros provider](https://registry.terraform.io/providers/terraform-routeros/routeros)
- [community.routeros Ansible collection](https://galaxy.ansible.com/community/routeros)
