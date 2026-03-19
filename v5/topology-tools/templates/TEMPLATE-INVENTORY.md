# V5 Template Inventory

**Purpose:** Track template migration from v4 to v5 generators.

---

## Directory Structure

```
v5/topology-tools/templates/
├── terraform/
│   ├── proxmox/           # Proxmox VE Terraform templates
│   └── mikrotik/          # MikroTik RouterOS Terraform templates
├── ansible/
│   └── inventory/         # Ansible inventory templates
└── bootstrap/
    ├── proxmox/           # Proxmox bootstrap templates
    ├── mikrotik/          # MikroTik bootstrap templates
    └── orangepi/          # Orange Pi cloud-init templates
```

---

## Terraform Proxmox Templates

| Template | V4 Source | V5 Status | Generator |
|----------|-----------|-----------|-----------|
| `provider.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/provider.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `versions.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/versions.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `bridges.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/bridges.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `vms.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/vms.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `lxc.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/lxc.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `variables.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/variables.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `outputs.tf.j2` | `v4/topology-tools/templates/terraform/proxmox/outputs.tf.j2` | Complete | `terraform_proxmox_generator.py` |
| `terraform.tfvars.example.j2` | `v4/topology-tools/templates/terraform/proxmox/terraform.tfvars.example.j2` | Complete | `terraform_proxmox_generator.py` |

---

## Terraform MikroTik Templates

| Template | V4 Source | V5 Status | Generator |
|----------|-----------|-----------|-----------|
| `provider.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/provider.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `interfaces.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/interfaces.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `firewall.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/firewall.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `dhcp.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/dhcp.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `dns.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/dns.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `addresses.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/addresses.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `qos.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/qos.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `vpn.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/vpn.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `containers.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/containers.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `variables.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/variables.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `outputs.tf.j2` | `v4/topology-tools/templates/terraform-mikrotik/outputs.tf.j2` | Complete | `terraform_mikrotik_generator.py` |
| `terraform.tfvars.example.j2` | `v4/topology-tools/templates/terraform-mikrotik/terraform.tfvars.example.j2` | Complete | `terraform_mikrotik_generator.py` |

---

## Ansible Templates

| Template | V4 Source | V5 Status | Generator |
|----------|-----------|-----------|-----------|
| `hosts.yml.j2` | `v4/topology-tools/templates/ansible/hosts.yml.j2` | Complete | `ansible_inventory_generator.py` |
| `group_vars_all.yml.j2` | `v4/topology-tools/templates/ansible/group_vars_all.yml.j2` | Complete | `ansible_inventory_generator.py` |
| `host_vars.yml.j2` | `v4/topology-tools/templates/ansible/host_vars.yml.j2` | Complete | `ansible_inventory_generator.py` |

---

## Bootstrap Templates

### Proxmox

| Template | V4 Source | V5 Status | Generator |
|----------|-----------|-----------|-----------|
| `answer.toml.example.j2` | `v4/topology-tools/templates/bootstrap/proxmox/answer.toml.j2` | Complete | `bootstrap_proxmox_generator.py` |
| `post-install/*.sh.j2` | `v4/topology-tools/templates/bootstrap/proxmox/post-install/` | Complete | `bootstrap_proxmox_generator.py` |

### MikroTik

| Template | V4 Source | V5 Status | Generator |
|----------|-----------|-----------|-----------|
| `init-terraform.rsc.j2` | `v4/topology-tools/templates/bootstrap/mikrotik/init-terraform.rsc.j2` | Complete | `bootstrap_mikrotik_generator.py` |
| `terraform.tfvars.example.j2` | `v4/topology-tools/templates/bootstrap/mikrotik/terraform.tfvars.example.j2` | Complete | `bootstrap_mikrotik_generator.py` |

### Orange Pi 5

| Template | V4 Source | V5 Status | Generator |
|----------|-----------|-----------|-----------|
| `user-data.example.j2` | `v4/topology-tools/templates/bootstrap/orangepi5/user-data.j2` | Complete | `bootstrap_orangepi_generator.py` |
| `meta-data.j2` | `v4/topology-tools/templates/bootstrap/orangepi5/meta-data.j2` | Complete | `bootstrap_orangepi_generator.py` |

---

## Migration Notes

### Template Adaptation Requirements

1. **Data Source Change:**
   - V4: Templates consume `topology` dict loaded directly from YAML
   - V5: Templates consume **projection views** built from compiled model

2. **Naming Convention:**
   - V4: Various naming patterns
   - V5: Consistent `{target}/{resource}.tf.j2` pattern

3. **Variable Access:**
   - V4: Direct dict access (`{{ topology.networks }}`
   - V5: Projection namespace (`{{ proxmox.bridges }}`, `{{ mikrotik.interfaces }}`)

### Projection Layer Contract

Templates should NOT access:
- Raw `ctx.compiled_json` internals
- Instance/object/class internal structures

Templates SHOULD access:
- Stable projection views with guaranteed schema
- Pre-sorted, deterministic collections
- Pre-resolved references

---

## Status Legend

| Status | Meaning |
|--------|---------|
| Complete | Not started |
| In Progress | Template being adapted |
| Migrated | Template adapted, not tested |
| Tested | Template passes parity tests |
| Complete | Template in production use |
