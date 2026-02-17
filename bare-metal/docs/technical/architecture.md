# Auto-Deploy Architecture
# Complete Infrastructure Automation from USB to Running Services

## 🎯 Goal

Create fully automated infrastructure deployment:
1. **USB Creation**: Generate all configs from topology.yaml
2. **Proxmox Install**: Automatic installation with UUID marker
3. **Auto-Deploy**: Automatic infrastructure deployment after first boot

## 📋 Workflow

### Phase 1: USB Creation (create-usb.sh)

```bash
./create-usb.sh /dev/sdX proxmox.iso
```

**Steps**:
1. ✅ Generate Installation UUID (timestamp-based)
2. ✅ Validate topology.yaml
3. 🆕 Generate all configurations:
   - Terraform (VMs, LXC, networks, storage)
   - Ansible (inventory, playbooks, variables)
   - Documentation (diagrams, IP tables)
4. 🆕 Package configs into archive: `home-lab-configs.tar.gz`
5. 🆕 Embed archive into ISO (via custom partition or ISO modification)
6. ✅ Create first-boot script (UUID marker + config copy)
7. 🆕 Create second-boot script (infrastructure deployment)
8. ✅ Write prepared ISO to USB

**Output**:
- Bootable USB with Proxmox installer
- Embedded configs archive
- First-boot: UUID + config copy
- Second-boot: Auto-deployment

---

### Phase 2: Proxmox Installation (Automatic)

```
Boot from USB → Auto-install Proxmox (15 min) → Reboot
```

**Steps**:
1. GRUB loads from USB
2. Checks for existing installation (UUID comparison)
3. If no UUID found → Runs auto-installer
4. Proxmox installed to `/dev/sda`
5. First-boot script executes:
   - ✅ Saves UUID to `/efi/proxmox-installed`
   - 🆕 Mounts HDD (`/dev/sdb` → `/mnt/pve/hdd`)
   - 🆕 Extracts configs to `/mnt/pve/hdd/home-lab/`
   - 🆕 Creates systemd service for second-boot
6. System reboots

**File Structure on HDD** (`/mnt/pve/hdd/home-lab/`):
```
/mnt/pve/hdd/home-lab/
├── topology.yaml              # Source of truth
├── generated/                 # Auto-generated configs
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── proxmox.tf
│   │   └── modules/
│   ├── ansible/
│   │   ├── inventory/
│   │   │   └── production/
│   │   │       ├── hosts.yml
│   │   │       ├── group_vars/
│   │   │       └── host_vars/
│   │   ├── playbooks/
│   │   │   ├── site.yml
│   │   │   ├── postgresql.yml
│   │   │   └── ...
│   │   └── roles/
│   └── docs/
│       ├── network-diagram.md
│       ├── ip-allocation.md
│       └── services.md
├── scripts/
│   ├── deploy-infrastructure.sh    # Main orchestrator
│   ├── install-tools.sh            # Install Terraform/Ansible
│   └── verify-deployment.sh        # Post-deploy checks
└── logs/
    ├── deployment-$(date).log
    └── terraform.log
```

---

### Phase 3: Second Boot - Auto-Deployment

```
System boots → Systemd service runs → Infrastructure deployed
```

**Systemd Service**: `/etc/systemd/system/home-lab-deploy.service`

```ini
[Unit]
Description=Home Lab Infrastructure Auto-Deployment
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/mnt/pve/hdd/home-lab/scripts/deploy-infrastructure.sh
StandardOutput=journal
StandardError=journal
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

**Deployment Script** (`deploy-infrastructure.sh`):

```bash
#!/bin/bash
# Main orchestrator for infrastructure deployment

set -e
LOG_FILE="/mnt/pve/hdd/home-lab/logs/deployment-$(date +%Y%m%d_%H%M%S).log"
exec 1> >(tee -a "$LOG_FILE") 2>&1

echo "===== Home Lab Auto-Deployment Started at $(date) ====="

# 1. Install dependencies
echo "[1/5] Installing Terraform and Ansible..."
/mnt/pve/hdd/home-lab/scripts/install-tools.sh

# 2. Configure Proxmox API access
echo "[2/5] Configuring Proxmox API..."
# Create API token, save to terraform.tfvars

# 3. Apply Terraform (create infrastructure)
echo "[3/5] Deploying infrastructure with Terraform..."
cd /mnt/pve/hdd/home-lab/generated/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 4. Apply Ansible (configure services)
echo "[4/5] Configuring services with Ansible..."
cd /mnt/pve/hdd/home-lab/generated/ansible
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml

# 5. Verify deployment
echo "[5/5] Verifying deployment..."
/mnt/pve/hdd/home-lab/scripts/verify-deployment.sh

# 6. Disable this service (one-time execution)
echo "Disabling auto-deployment service..."
systemctl disable home-lab-deploy.service

echo "===== Home Lab Auto-Deployment Completed at $(date) ====="
echo "✅ Infrastructure is ready!"
```

---

## 🗂️ Files Created/Modified

### New Files:

1. **bare-metal/scripts/generate-configs.sh**
   - Calls Python generators (Terraform, Ansible, Docs)
   - Creates tarball with all configs

2. **bare-metal/scripts/embed-configs.sh**
   - Extracts ISO
   - Adds configs tarball to ISO
   - Rebuilds ISO

3. **bare-metal/scripts/first-boot-extended.sh**
   - ✅ UUID marker (existing)
   - 🆕 Mount HDD
   - 🆕 Extract configs
   - 🆕 Setup systemd service

4. **bare-metal/scripts/deploy-infrastructure.sh**
   - Main deployment orchestrator

5. **bare-metal/scripts/install-tools.sh**
   - Install Terraform (via HashiCorp repo)
   - Install Ansible (via pip)
   - Install Python dependencies

6. **bare-metal/scripts/verify-deployment.sh**
   - Check VMs are running
   - Check LXC containers accessible
   - Ping test all services

### Modified Files:

1. **bare-metal/create-usb.sh**
   - Add config generation step
   - Add config embedding step
   - Update first-boot script

---

## 🔒 Security Considerations

### Secrets Management

**Problem**: Terraform needs Proxmox API credentials

**Solutions**:

**Option 1: Interactive Setup** (Manual, first boot)
```bash
# After Proxmox boots, user runs:
pveum user add terraform@pve -password <password>
pveum aclmod / -user terraform@pve -role Administrator
# Save to terraform.tfvars
```

**Option 2: Embedded Secrets** (Automated, less secure)
```bash
# Generate API token during first-boot
# Save to /mnt/pve/hdd/home-lab/generated/terraform/terraform.tfvars
```

**Option 3: Ansible Vault** (Recommended)
```bash
# Encrypt secrets in topology.yaml
ansible-vault encrypt topology.yaml
# Provide vault password during USB creation
```

---

## 📊 Monitoring & Logs

### Log Files:

- `/var/log/proxmox-first-boot.log` - First-boot execution
- `/mnt/pve/hdd/home-lab/logs/deployment-YYYYMMDD_HHMMSS.log` - Deployment log
- `journalctl -u home-lab-deploy.service` - Systemd service log

### Verification Commands:

```bash
# Check deployment service status
systemctl status home-lab-deploy.service

# View deployment log
tail -f /mnt/pve/hdd/home-lab/logs/deployment-*.log

# Check Terraform state
cd /mnt/pve/hdd/home-lab/generated/terraform
terraform show

# Check Ansible inventory
cd /mnt/pve/hdd/home-lab/generated/ansible
ansible-inventory -i inventory/production/hosts.yml --list
```

---

## ⏱️ Timeline Estimate

| Phase | Duration | Description |
|-------|----------|-------------|
| USB Creation | 5-10 min | Generate configs + Write USB |
| Proxmox Install | 10-15 min | Automatic installation |
| First Boot | 1-2 min | UUID marker + Config copy |
| Second Boot | 15-30 min | Tool install + Infrastructure deploy |
| **Total** | **30-60 min** | From USB creation to running infrastructure |

---

## 🧪 Testing Strategy

### Test 1: USB Creation
```bash
cd bare-metal
./create-usb.sh /dev/sdX proxmox.iso
# Verify: configs embedded, first-boot script updated
```

### Test 2: Installation
```bash
# Boot from USB
# Wait for installation
# SSH after first boot
ls -la /mnt/pve/hdd/home-lab/
# Should see: topology.yaml, generated/, scripts/, logs/
```

### Test 3: Auto-Deployment
```bash
# Check service
systemctl status home-lab-deploy.service

# Monitor logs
journalctl -u home-lab-deploy.service -f

# After completion
pvesh get /cluster/resources --type vm
# Should show all VMs/LXC from topology.yaml
```

---

## 🚀 Future Enhancements

1. **Multi-stage deployment**
   - Stage 1: Core infrastructure (networking, storage)
   - Stage 2: Base services (DNS, DHCP)
   - Stage 3: Applications (Nextcloud, etc.)

2. **Rollback capability**
   - Terraform state backups
   - Snapshot before deployment

3. **Web UI for monitoring**
   - Real-time deployment progress
   - Interactive configuration

4. **Multi-host support**
   - Deploy across multiple Proxmox nodes
   - Cluster configuration

---

**Status**: 🚧 Architecture Designed - Implementation in Progress
**Version**: 1.0
**Last Updated**: 2025-10-10
