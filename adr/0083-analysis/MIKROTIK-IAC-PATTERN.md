# MikroTik Full IaC Pipeline Pattern

## Overview

This document defines the complete Infrastructure-as-Code pattern for MikroTik RouterOS devices within the ADR 0083 unified initialization framework.

**Deploy sequence:** `Netinstall → Bootstrap .rsc → OpenTofu/Terraform → Ansible`

---

## Pipeline vs Deploy Domain

```
┌─────────────────────────────────────────────────────────────────┐
│ V5 PIPELINE (runs MANY times)                                   │
│ Generates: bootstrap scripts, terraform configs, ansible plays  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ DEPLOY DOMAIN                                                   │
│                                                                 │
│ Netinstall ──► OpenTofu ──► Ansible                             │
│ (ONCE)         (MANY)       (MANY)                              │
└─────────────────────────────────────────────────────────────────┘
```

The v5 pipeline generates artifacts from topology. The deploy domain executes them with different cadences.

---

## Toolchain

| Tool | Role | Source |
| ---- | ---- | ------ |
| netinstall-cli | Day-0 clean install | MikroTik official |
| terraform-routeros/routeros | Topology objects (state-managed) | OpenTofu/Terraform registry |
| community.routeros | Post-config, firewall, operations | Ansible Galaxy |
| SOPS + age | Secrets encryption | ADR 0072 |

---

## Separation of Responsibilities

### Bootstrap .rsc (Day-0)

Minimal access after clean install ONLY:

- Admin user disabled, automation user created
- SSH / API / REST API enabled
- Management IP on bridge
- Basic service restrictions

**Rule:** Bootstrap script must NOT contain any day-1 configuration.

### OpenTofu/Terraform (Day-1 Topology)

State-managed topology objects:

- bridge
- VLAN interfaces
- IP addressing
- WireGuard interfaces/peers
- DHCP pools / networks
- address-lists
- routing tables / static routes
- DNS basic settings

### Ansible (Day-1+ Operations)

Objects unsuitable for Terraform state:

- firewall filter / nat / mangle (ordered rules)
- scripts
- scheduler
- backup jobs
- log actions
- service hardening
- post-upgrade fixes

### Golden Rule

> One object must NOT be managed by both Terraform and Ansible simultaneously.

---

## Repository Structure

```text
topology/object-modules/mikrotik/
├── obj.mikrotik.chateau_lte7_ax.yaml    # Object definition with initialization_contract
├── templates/
│   └── bootstrap/
│       └── init-terraform.rsc.j2         # Minimal bootstrap template
└── schemas/
    └── mikrotik-bootstrap.schema.json    # Bootstrap validation schema

generated/home-lab/
├── bootstrap/
│   └── rtr-mikrotik-chateau/
│       ├── init-terraform.rsc            # Generated bootstrap script
│       └── terraform.tfvars.example
├── terraform/
│   └── mikrotik/
│       ├── versions.tf
│       ├── providers.tf
│       ├── variables.tf
│       ├── main.tf
│       └── modules/
│           ├── mikrotik-base/
│           ├── mikrotik-vlans/
│           ├── mikrotik-wireguard/
│           └── mikrotik-routing/
└── ansible/
    └── playbooks/
        ├── mikrotik-postconfig.yml
        ├── mikrotik-firewall.yml
        ├── mikrotik-backup.yml
        └── mikrotik-validate.yml
```

---

## Workflow Phases (Deploy Domain)

### Phase A: Clean Install (Netinstall) — runs ONCE

```bash
# From control node on installation segment
netinstall-cli \
  -e \
  --mac 00:11:22:33:44:55 \
  -i enp3s0 \
  -a 192.168.88.3 \
  -s .work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc \
  /srv/routeros/routeros-7.x-arm64.npk
```

Result: Router boots with management IP, SSH/API enabled, automation user ready.

### Phase B: Declarative Configuration (OpenTofu) — runs MANY times

```bash
cd generated/home-lab/terraform/mikrotik
tofu init
tofu plan -var-file=envs/home-lab.tfvars
tofu apply -auto-approve
```

Result: Bridges, VLANs, IPs, WireGuard, DHCP, routing configured.

### Phase C: Post-Config (Ansible) — runs MANY times

```bash
ansible-playbook -i inventory/hosts.yml playbooks/mikrotik-postconfig.yml
ansible-playbook -i inventory/hosts.yml playbooks/mikrotik-firewall.yml
ansible-playbook -i inventory/hosts.yml playbooks/mikrotik-validate.yml
```

Result: Firewall rules, scripts, scheduler, hardening applied.

### Phase D: Backup / Audit — runs MANY times

```bash
ansible-playbook -i inventory/hosts.yml playbooks/mikrotik-backup.yml
```

Result: Text export (.rsc) + binary backup (.backup) stored.

---

## Bootstrap Script Template

Minimal bootstrap for Terraform handover:

```routeros
# Disable default admin
/user set admin disabled=yes

# Create automation user
/user add name=terraform group=full password="{{ terraform_password }}"

# Enable required services
/ip service set ssh disabled=no
/ip service set api disabled=no
/ip service set api-ssl disabled=yes
/ip service set www disabled=yes
/ip service set www-ssl disabled=no port=8443

# Disable certificate CRL (simplify bootstrap)
/certificate settings set crl-use=no

# Create management bridge
/interface bridge add name=bridge-mgmt
/interface bridge port add bridge=bridge-mgmt interface=ether1

# Set management IP
/ip address add address={{ management_ip }}/{{ management_prefix }} interface=bridge-mgmt

# Restrict service access to management network
/ip neighbor discovery-settings set discover-interface-list=none
/ip service set ssh address={{ management_network }}
/ip service set api address={{ management_network }}
/ip service set www-ssl address={{ management_network }}
```

**Lines:** ~25 (target: <50)

---

## OpenTofu Configuration

### versions.tf

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    routeros = {
      source  = "terraform-routeros/routeros"
      version = "~> 1.99"
    }
  }
}
```

### providers.tf

```hcl
provider "routeros" {
  hosturl  = var.routeros_url
  username = var.routeros_username
  password = var.routeros_password
  insecure = true  # For self-signed cert during bootstrap
}
```

### variables.tf

```hcl
variable "routeros_url" {
  type        = string
  description = "RouterOS REST API URL (https://ip:port)"
}

variable "routeros_username" {
  type        = string
  description = "Automation user"
}

variable "routeros_password" {
  type        = string
  sensitive   = true
  description = "Automation password"
}

variable "lan_cidr" {
  type        = string
  description = "LAN network CIDR"
}

variable "wg_port" {
  type        = number
  description = "WireGuard listen port"
}
```

### main.tf (skeleton)

```hcl
resource "routeros_interface_bridge" "lan" {
  name = "bridge-lan"
}

resource "routeros_ip_address" "lan" {
  address   = var.lan_cidr
  interface = routeros_interface_bridge.lan.name
}

resource "routeros_interface_wireguard" "wg_mgmt" {
  name        = "wg-mgmt"
  listen_port = var.wg_port
}

# Additional resources: VLANs, DHCP, routing...
```

---

## Ansible Configuration

### requirements.yml

```yaml
collections:
  - name: community.routeros
    version: ">=2.0.0"
```

### inventory/hosts.yml

```yaml
all:
  children:
    mikrotik:
      hosts:
        rtr-mikrotik-chateau:
          ansible_host: 192.168.88.1
          ansible_user: terraform
          ansible_password: "{{ vault_mikrotik_terraform_password }}"
          ansible_connection: community.routeros.api
```

### playbooks/mikrotik-firewall.yml

```yaml
---
- name: Configure RouterOS firewall
  hosts: mikrotik
  gather_facts: false
  tasks:
    - name: Allow established/related
      community.routeros.api_modify:
        hostname: "{{ ansible_host }}"
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        path: ip firewall filter
        find:
          chain: input
          comment: allow-established
        values:
          chain: input
          action: accept
          connection-state: established,related
          comment: allow-established

    - name: Drop invalid
      community.routeros.api_modify:
        hostname: "{{ ansible_host }}"
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        path: ip firewall filter
        find:
          chain: input
          comment: drop-invalid
        values:
          chain: input
          action: drop
          connection-state: invalid
          comment: drop-invalid
```

### playbooks/mikrotik-validate.yml

```yaml
---
- name: Validate RouterOS configuration
  hosts: mikrotik
  gather_facts: false
  tasks:
    - name: Check management IP reachable
      wait_for:
        host: "{{ ansible_host }}"
        port: 8443
        timeout: 10

    - name: Check API accessible
      community.routeros.api_info:
        hostname: "{{ ansible_host }}"
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        path: system resource
      register: resource_info

    - name: Display RouterOS version
      debug:
        msg: "RouterOS {{ resource_info.result[0].version }}"

    - name: Check WireGuard interface exists
      community.routeros.api_info:
        hostname: "{{ ansible_host }}"
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        path: interface wireguard
      register: wg_info

    - name: Verify WireGuard configured
      assert:
        that: wg_info.result | length > 0
        fail_msg: "WireGuard interface not found"
```

### playbooks/mikrotik-backup.yml

```yaml
---
- name: Backup RouterOS configuration
  hosts: mikrotik
  gather_facts: false
  vars:
    backup_dir: "{{ playbook_dir }}/../backups/{{ inventory_hostname }}"
    timestamp: "{{ lookup('pipe', 'date +%Y%m%d-%H%M%S') }}"
  tasks:
    - name: Ensure backup directory exists
      local_action:
        module: file
        path: "{{ backup_dir }}"
        state: directory

    - name: Export text configuration
      community.routeros.command:
        commands:
          - /export file=backup-{{ timestamp }}
      register: export_result

    - name: Create binary backup
      community.routeros.command:
        commands:
          - /system backup save name=backup-{{ timestamp }}
      register: backup_result

    - name: Fetch text export
      community.routeros.api_info:
        hostname: "{{ ansible_host }}"
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        path: file
        query: name ~ "backup-{{ timestamp }}.rsc"
      register: export_file

    # Note: Actual file download requires additional logic
    - name: Log backup completion
      debug:
        msg: "Backup completed: backup-{{ timestamp }}"
```

---

## Object Ownership Matrix

| Object Type | Owner | Rationale |
| ----------- | ----- | --------- |
| bridge | OpenTofu | Topology primitive |
| VLAN | OpenTofu | Topology primitive |
| IP address | OpenTofu | Topology primitive |
| interface list | OpenTofu | Topology grouping |
| WireGuard interface | OpenTofu | Topology primitive |
| WireGuard peer | OpenTofu | Topology primitive |
| DHCP pool | OpenTofu | Network service |
| DHCP network | OpenTofu | Network service |
| static route | OpenTofu | Routing topology |
| address-list | OpenTofu | Reusable object |
| DNS static | OpenTofu | Network service |
| firewall filter | Ansible | Ordered rules |
| firewall nat | Ansible | Ordered rules |
| firewall mangle | Ansible | Ordered rules |
| script | Ansible | Operational |
| scheduler | Ansible | Operational |
| backup job | Ansible | Operational |
| log action | Ansible | Operational |
| service hardening | Ansible | Security policy |

---

## Handover Verification Checks

| Check | Command | Success Criteria |
| ----- | ------- | ---------------- |
| Management IP reachable | `ping -c 3 192.168.88.1` | 0% packet loss |
| REST API accessible | `curl -k https://192.168.88.1:8443/rest` | HTTP 401 (auth required) |
| SSH accessible | `nc -z -w 5 192.168.88.1 22` | Connection succeeded |
| Terraform plan succeeds | `tofu plan -var-file=...` | No errors |
| Automation user works | API call with credentials | Authentication successful |

---

## Backup Strategy

### Text Export (.rsc)

- Purpose: Git versioning, audit, diff analysis
- Frequency: After every change, daily scheduled
- Storage: Git repository (sanitized, no secrets)

### Binary Backup (.backup)

- Purpose: Emergency restore on same hardware
- Frequency: Weekly, before major changes
- Storage: Encrypted off-device storage
- Note: Binary backups are hardware-specific

---

## Secrets Management

Per ADR 0072 (SOPS + age):

```yaml
# projects/home-lab/secrets/mikrotik.enc.yaml
mikrotik_terraform_password: ENC[AES256_GCM,...]
mikrotik_wifi_password: ENC[AES256_GCM,...]
mikrotik_vpn_psk: ENC[AES256_GCM,...]
```

Decryption flow:

1. CI/CD: `sops -d secrets/mikrotik.enc.yaml > /tmp/mikrotik.yaml`
2. Terraform: reads from env or tfvars (populated by CI)
3. Ansible: reads from decrypted vars file

---

## Taskfile Integration

```yaml
# taskfiles/mikrotik.yaml
version: "3"

vars:
  ENV: "home-lab"
  MIKROTIK_HOST: "rtr-mikrotik-chateau"

tasks:
  init:
    desc: Initialize Terraform and Ansible
    cmds:
      - cd generated/{{.ENV}}/terraform/mikrotik && tofu init
      - ansible-galaxy collection install -r generated/{{.ENV}}/ansible/requirements.yml

  plan:
    desc: Terraform plan for MikroTik
    cmds:
      - cd generated/{{.ENV}}/terraform/mikrotik && tofu plan -var-file=envs/{{.ENV}}.tfvars

  apply:
    desc: Apply Terraform configuration
    cmds:
      - cd generated/{{.ENV}}/terraform/mikrotik && tofu apply -var-file=envs/{{.ENV}}.tfvars -auto-approve

  postconfig:
    desc: Run Ansible post-configuration
    cmds:
      - ansible-playbook -i generated/{{.ENV}}/ansible/inventory/hosts.yml generated/{{.ENV}}/ansible/playbooks/mikrotik-postconfig.yml

  firewall:
    desc: Apply firewall rules
    cmds:
      - ansible-playbook -i generated/{{.ENV}}/ansible/inventory/hosts.yml generated/{{.ENV}}/ansible/playbooks/mikrotik-firewall.yml

  validate:
    desc: Validate MikroTik configuration
    cmds:
      - ansible-playbook -i generated/{{.ENV}}/ansible/inventory/hosts.yml generated/{{.ENV}}/ansible/playbooks/mikrotik-validate.yml

  backup:
    desc: Backup MikroTik configuration
    cmds:
      - ansible-playbook -i generated/{{.ENV}}/ansible/inventory/hosts.yml generated/{{.ENV}}/ansible/playbooks/mikrotik-backup.yml

  full-deploy:
    desc: Full deployment pipeline
    cmds:
      - task: plan
      - task: apply
      - task: postconfig
      - task: firewall
      - task: validate
      - task: backup
```

---

## Integration with ADR 0083

### Initialization Contract

```yaml
# topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml
initialization_contract:
  version: "1.0"
  mechanism: netinstall
  requirements:
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

### Manifest Entry

```yaml
# generated/home-lab/bootstrap/INITIALIZATION-MANIFEST.yaml
nodes:
  - id: rtr-mikrotik-chateau
    object_ref: obj.mikrotik.chateau_lte7_ax
    mechanism: netinstall
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
```

```yaml
# .work/native/bootstrap/INITIALIZATION-STATE.yaml
# Canonical format per STATE-MODEL.md — tracks bootstrap state only.
# Terraform/Ansible lifecycle is outside init-node.py scope.
nodes:
  - id: rtr-mikrotik-chateau
    status: pending
    mechanism: netinstall
    contract_hash: "sha256:..."
    imported: false
    last_action: null
    last_action_at: null
    last_error: null
    attempt_count: 0
    history: []
```

---

## References

- ADR 0057: MikroTik Chateau Netinstall Bootstrap and Terraform Handover
- ADR 0072: Unified Secrets Management with SOPS and age
- ADR 0083: Unified Node Initialization Contract
- [terraform-routeros/routeros provider](https://registry.terraform.io/providers/terraform-routeros/routeros)
- [community.routeros Ansible collection](https://galaxy.ansible.com/community/routeros)
- [MikroTik Netinstall documentation](https://help.mikrotik.com/docs/display/ROS/Netinstall)
