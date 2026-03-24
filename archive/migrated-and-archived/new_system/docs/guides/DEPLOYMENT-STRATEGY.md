# Deployment Strategy Guide

This guide describes the complete deployment strategy for the home lab infrastructure, from bare metal to running services.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        topology/*.yaml (Source of Truth)                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Python Generators                                                       │
│  ├── generate-terraform.py           → generated/terraform/             │
│  ├── generate-terraform-mikrotik.py  → generated/terraform-mikrotik/    │
│  ├── generate-ansible-inventory.py   → generated/ansible/               │
│  └── generate-docs.py                → generated/docs/                  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  deploy/                                                                 │
│  ├── Makefile              ← Orchestration commands                     │
│  └── phases/                                                             │
│      ├── 00-bootstrap.sh   ← Manual bootstrap instructions              │
│      ├── 01-network.sh     ← MikroTik Terraform                         │
│      ├── 02-compute.sh     ← Proxmox Terraform                          │
│      ├── 03-services.sh    ← Ansible playbooks                          │
│      └── 04-verify.sh      ← Health checks                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Phases

### Phase 0: Bootstrap (Manual, One-Time)

**Purpose**: Enable automation access to all devices.

| Device | Action | Tool |
|--------|--------|------|
| MikroTik | Enable REST API, create terraform user | WinBox/SSH |
| Proxmox | Install from USB with answer.toml | Auto-installer |
| Orange Pi 5 | Flash Armbian with cloud-init | USB/SD card |

#### MikroTik Bootstrap

```bash
# View bootstrap instructions
cd deploy && make bootstrap-info

# Or run the script directly
./phases/00-bootstrap.sh
```

The bootstrap script shows:
1. How to import `bootstrap/mikrotik/bootstrap.rsc`
2. How to change the terraform password
3. How to verify REST API access

#### Proxmox Bootstrap

See [PROXMOX-USB-AUTOINSTALL.md](PROXMOX-USB-AUTOINSTALL.md) for creating auto-install USB.

---

### Phase 1: Network (MikroTik via Terraform)

**Purpose**: Configure network infrastructure.

```bash
cd deploy && make apply-mikrotik
```

**Resources Created**:

| Order | Resource | Description |
|-------|----------|-------------|
| 1 | `routeros_interface_bridge` | Main LAN bridge |
| 2 | `routeros_interface_vlan` | VLAN interfaces (30, 40, 50, 99) |
| 3 | `routeros_interface_bridge_port` | LAN ports to bridge |
| 4 | `routeros_interface_bridge_vlan` | VLAN filtering |
| 5 | `routeros_ip_address` | Gateway IP addresses |
| 6 | `routeros_ip_dhcp_server` | DHCP servers |
| 7 | `routeros_ip_dns` | DNS settings |
| 8 | `routeros_ip_firewall_filter` | Firewall rules |
| 9 | `routeros_ip_firewall_nat` | NAT rules |
| 10 | `routeros_queue_tree` | QoS configuration |
| 11 | `routeros_interface_wireguard` | WireGuard VPN |
| 12 | `routeros_container` | AdGuard, Tailscale |

**Script**: `deploy/phases/01-network.sh`

```bash
#!/bin/bash
# Creates backup before applying
# Runs terraform plan for review
# Applies with confirmation
```

---

### Phase 2: Compute (Proxmox via Terraform)

**Purpose**: Create VMs and LXC containers.

```bash
cd deploy && make apply-proxmox
```

**Resources Created**:

| Resource | Description |
|----------|-------------|
| `proxmox_virtual_environment_network_linux_bridge` | Network bridges |
| `proxmox_virtual_environment_container` | PostgreSQL LXC |
| `proxmox_virtual_environment_container` | Redis LXC |

**Script**: `deploy/phases/02-compute.sh`

---

### Phase 3: Services (Ansible)

**Purpose**: Configure services inside VMs/LXC.

```bash
cd deploy && make configure
```

**Playbooks Executed**:

| Order | Playbook | Target | Purpose |
|-------|----------|--------|---------|
| 1 | common.yml | all | Base configuration |
| 2 | postgresql.yml | lxc-postgresql | Database setup |
| 3 | redis.yml | lxc-redis | Cache setup |
| 4 | orangepi5.yml | orangepi5 | Docker + services |
| 5 | monitoring.yml | all | Prometheus, exporters |

**Script**: `deploy/phases/03-services.sh`

---

### Phase 4: Verification

**Purpose**: Verify deployment health.

```bash
cd deploy && make test
```

**Checks Performed**:

| Category | Check | Expected |
|----------|-------|----------|
| Network | Ping MikroTik (192.168.88.1) | Reachable |
| Network | Ping Proxmox (192.168.88.2) | Reachable |
| Network | Ping PostgreSQL LXC (10.0.30.10) | Reachable |
| Network | Ping Redis LXC (10.0.30.20) | Reachable |
| Services | MikroTik WebFig (HTTPS) | Accessible |
| Services | Proxmox Web UI (8006) | Accessible |
| Services | AdGuard Home (3000) | Accessible |
| Database | PostgreSQL port (5432) | Open |
| Database | Redis port (6379) | Open |
| DNS | Internal resolution | Working |
| DNS | External resolution | Working |
| VPN | WireGuard port (51820/UDP) | Open |

**Script**: `deploy/phases/04-verify.sh`

---

## Quick Commands

### Full Deployment

```bash
cd deploy

# Generate all configurations
make generate

# Preview changes
make plan

# Deploy everything (with confirmations)
make deploy-all
```

### Individual Steps

```bash
# Validation & Generation
make validate           # Check topology.yaml
make generate           # Generate all configs

# Planning (dry-run)
make plan-mikrotik      # Show MikroTik changes
make plan-proxmox       # Show Proxmox changes

# Deployment
make apply-mikrotik     # Apply MikroTik config
make apply-proxmox      # Apply Proxmox config
make configure          # Run Ansible

# Verification
make test               # Run health checks
```

### Utilities

```bash
make help               # Show all commands
make bootstrap-info     # Bootstrap instructions
make clean              # Clean generated files
```

---

## Configuration Files

### terraform.tfvars (MikroTik)

```hcl
# generated/terraform-mikrotik/terraform.tfvars
mikrotik_host     = "https://192.168.88.1:8443"
mikrotik_username = "terraform"
mikrotik_password = "secure_password"
mikrotik_insecure = true

wireguard_private_key = "generated_key"
wireguard_peers = [
  { name = "phone", public_key = "...", allowed_ips = ["10.0.200.10/32"] }
]

tailscale_authkey = "tskey-..."
```

### terraform.tfvars (Proxmox)

```hcl
# generated/terraform/terraform.tfvars
proxmox_api_url      = "https://192.168.88.2:8006/api2/json"
proxmox_api_token_id = "terraform@pam!terraform"
proxmox_api_token    = "secret_token"
```

### Ansible Vault

```bash
# Create vault password file
echo "your_vault_password" > ~/.vault_pass
chmod 600 ~/.vault_pass

# Encrypt sensitive variables
ansible-vault encrypt ansible/group_vars/all/vault.yml
```

---

## Workflow: Adding New Infrastructure

### 1. Edit Topology

```bash
# Edit the relevant module
vim topology/compute.yaml     # Add VMs/LXC
vim topology/logical.yaml     # Add networks
vim topology/services.yaml    # Add services
```

### 2. Validate

```bash
cd deploy && make validate
```

### 3. Generate

```bash
make generate
```

### 4. Review Changes

```bash
make plan
```

### 5. Apply

```bash
make apply-mikrotik   # If network changes
make apply-proxmox    # If compute changes
make configure        # If service changes
```

### 6. Verify

```bash
make test
```

---

## Rollback Procedures

### MikroTik Rollback

```bash
# Restore from backup created by 01-network.sh
ssh admin@192.168.88.1 "/import file=pre-terraform-backup.rsc"
```

### Terraform State Recovery

```bash
# Restore previous state
cd generated/terraform-mikrotik
cp terraform.tfstate.backup terraform.tfstate
terraform plan  # Verify state matches reality
```

### Full Reset

```bash
# Reset MikroTik to defaults
ssh admin@192.168.88.1 "/system reset-configuration"

# Re-run bootstrap
./phases/00-bootstrap.sh
# Follow instructions...

# Re-apply configuration
make deploy-all
```

---

## Monitoring Deployment

### Real-Time Logs

```bash
# Watch Terraform output
terraform apply 2>&1 | tee deploy.log

# Watch Ansible output
ansible-playbook site.yml -v 2>&1 | tee ansible.log
```

### Post-Deployment

```bash
# Check service status on MikroTik
ssh admin@192.168.88.1 "/system resource print"
ssh admin@192.168.88.1 "/ip service print"
ssh admin@192.168.88.1 "/container print"

# Check LXC status on Proxmox
ssh root@192.168.88.2 "pct list"
ssh root@192.168.88.2 "pvesh get /cluster/resources --type vm"
```

---

## Troubleshooting

### Deployment Fails at Phase 1 (Network)

1. **Check MikroTik REST API**:
   ```bash
   curl -k -u terraform:password https://192.168.88.1:8443/rest/system/identity
   ```

2. **Verify credentials** in `terraform.tfvars`

3. **Check firewall** allows port 8443

### Deployment Fails at Phase 2 (Compute)

1. **Check Proxmox API**:
   ```bash
   curl -k "https://192.168.88.2:8006/api2/json/version"
   ```

2. **Verify API token** permissions

3. **Check storage** availability

### Deployment Fails at Phase 3 (Services)

1. **Check SSH connectivity**:
   ```bash
   ansible all -m ping
   ```

2. **Check inventory** in `generated/ansible/inventory/`

3. **Run with verbose**:
   ```bash
   ansible-playbook site.yml -vvv
   ```

### Verification Fails

1. **Check network connectivity**:
   ```bash
   ping 192.168.88.1
   ping 10.0.30.10
   ```

2. **Check service ports**:
   ```bash
   nc -zv 10.0.30.10 5432  # PostgreSQL
   nc -zv 10.0.30.20 6379  # Redis
   ```

3. **Check DNS**:
   ```bash
   nslookup router.home.local 192.168.88.1
   ```

---

## Best Practices

1. **Always run `make plan` before `make apply`**
2. **Keep backups** before major changes
3. **Test in phases** rather than full deployment
4. **Review Terraform output** carefully
5. **Use version control** for topology changes
6. **Document custom changes** in topology comments

---

## References

- [MikroTik Terraform Guide](MIKROTIK-TERRAFORM.md)
- [Proxmox USB Auto-Install](PROXMOX-USB-AUTOINSTALL.md)
- [Ansible Vault Guide](ANSIBLE-VAULT-GUIDE.md)
- [Bridges Configuration](BRIDGES.md)

---

**Last Updated**: 2026-02-17
