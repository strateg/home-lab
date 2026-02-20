# Migration to Infrastructure as Code

Complete migration guide from script-based infrastructure to Infrastructure as Code (Terraform + Ansible) for Proxmox VE 9 home lab on Dell XPS L701X.

## Table of Contents

1. [Overview](#overview)
2. [Migration Strategy](#migration-strategy)
3. [Pre-Migration Checklist](#pre-migration-checklist)
4. [Migration Phases](#migration-phases)
5. [Testing Procedures](#testing-procedures)
6. [Rollback Plan](#rollback-plan)
7. [Post-Migration Validation](#post-migration-validation)
8. [Troubleshooting](#troubleshooting)

---

## Overview

### Current State (Script-Based)

**Location**: `old_system/` directory
- Bash scripts for configuration
- Manual execution required
- Limited idempotency
- No state tracking
- Difficult to version and test

**Components**:
- `proxmox/scripts/` - Proxmox automation scripts
- `manual-scripts/openwrt/` - OpenWRT configuration scripts
- `opnsense/` - OPNsense configs
- `services/` - Service deployment scripts
- `vpn-servers/` - VPN server configs

### Target State (IaC)

**Location**: `new_system/` directory
- Terraform for infrastructure provisioning
- Ansible for configuration management
- Declarative configuration (topology.yaml as source of truth)
- State tracking and drift detection
- Version controlled
- Automated testing possible

**Components**:
- `topology.yaml` - Single source of truth (Infrastructure-as-Data)
- `scripts/` - Generators (Python) from topology.yaml
- `terraform/` - Provisioning modules (auto-generated from topology.yaml)
- `ansible/` - Configuration roles (partially generated from topology.yaml)
- `manual-scripts/bare-metal/` - Bare-metal auto-install
- Git-based workflow

### Migration Approach

**Parallel Development** (Already implemented):
- New IaC structure created alongside existing scripts
- No disruption to current system
- Gradual migration component by component
- Testing in isolated environment before production

---

## Migration Strategy

### Phase 0: Preparation (Complete ✅)

**Goal**: Set up IaC structure without affecting current system

**Tasks**:
- ✅ Create directory structure (new_system/)
- ✅ Create topology.yaml (Infrastructure-as-Data)
- ✅ Set up Terraform base configuration (new_system/terraform/)
- ✅ Create Terraform modules (network, storage)
- ✅ Set up Ansible base configuration (new_system/ansible/)
- ✅ Create Ansible roles (proxmox)
- ✅ Create bare-metal installation scripts (new_system/manual-scripts/bare-metal/)
- ✅ Initialize Git repository structure
- ✅ Create .gitignore for secrets protection
- ✅ Move old system to old_system/ directory

**Status**: Complete

---

### Phase 1: Documentation & Testing Setup (Current)

**Goal**: Document migration process and set up testing

**Tasks**:
1. ✅ Document migration workflow (this file)
2. ⏳ Create testing environment
3. ⏳ Define test procedures
4. ⏳ Create validation scripts

**Duration**: 1-2 days

**Outcome**: Clear migration path and testing framework

---

### Phase 2: Bare-Metal Installation (Fresh Install)

**Goal**: Install Proxmox VE using automated bare-metal process

**Prerequisites**:
- USB drive (2GB+)
- Proxmox VE 9 ISO
- Dell XPS L701X ready for installation

**Steps**:

1. **Create Bootable USB**
   ```bash
   cd new_system/manual-scripts/bare-metal/
   sudo ./run-create-usb.sh  # Interactive wrapper
   # Or: sudo ./create-uefi-autoinstall-proxmox-usb.sh /dev/sdX proxmox-ve_9.0-1.iso
   ```

2. **Install Proxmox**
   - Boot from USB
   - Auto-install completes (~10-15 minutes)
   - System reboots

3. **Run Post-Install Scripts**
   ```bash
   ssh root@<proxmox-ip>
   cd /root/post-install
   ./01-install-terraform.sh
   ./02-install-ansible.sh
   ./03-configure-storage.sh
   ./04-configure-network.sh
   ./05-init-git-repo.sh
   reboot
   ```

4. **Verify Base Installation**
   ```bash
   # Check Terraform
   terraform version

   # Check Ansible
   ansible --version

   # Check storage
   pvesm status
   df -h /mnt/hdd

   # Check network
   ip -br link show type bridge
   brctl show
   ```

**Duration**: 1-2 hours

**Testing**: See [Testing Phase 2](#phase-2-testing)

---

### Phase 3: Infrastructure Provisioning (Terraform)

**Goal**: Use Terraform to provision VMs and LXC containers

**Prerequisites**:
- Phase 2 complete
- Terraform installed
- Proxmox API access configured

**Steps**:

1. **Copy IaC Files to Proxmox**
   ```bash
   # From workstation
   cd ~/workspaces/projects/home-lab
   scp -r new_system/ root@10.0.99.1:/root/home-lab/
   ```

2. **Configure Terraform Variables**
   ```bash
   # On Proxmox
   cd /root/home-lab/new_system/terraform
   cp terraform.tfvars.example terraform.tfvars
   vim terraform.tfvars
   ```

   **Key variables to configure**:
   ```hcl
   # Proxmox API
   proxmox_api_url = "https://10.0.99.1:8006/api2/json"
   proxmox_api_token_id = "root@pam!terraform"
   proxmox_api_token_secret = "your-token-secret"

   # Node name
   proxmox_node_name = "pve-xps"

   # Network interfaces
   wan_interface = "eth-usb"
   lan_interface = "eth-builtin"

   # Storage
   storage_ssd_id = "local-lvm"
   storage_hdd_id = "local-hdd"
   ```

3. **Create Proxmox API Token**
   ```bash
   # On Proxmox Web UI
   # Datacenter → Permissions → API Tokens → Add
   # Token ID: terraform
   # Privilege Separation: No
   # Copy generated secret to terraform.tfvars
   ```

4. **Initialize Terraform**
   ```bash
   cd /root/home-lab/new_system/terraform
   terraform init
   ```

5. **Plan Infrastructure**
   ```bash
   terraform plan -out=tfplan
   ```

   **Review plan for**:
   - Network bridges (vmbr0, vmbr1, vmbr2, vmbr99)
   - Storage pools (local-lvm, local-hdd)
   - VMs (if any defined)
   - LXC containers (if any defined)

6. **Apply Infrastructure**
   ```bash
   # Start with network module only
   terraform apply -target=module.network

   # Then storage module
   terraform apply -target=module.storage

   # Finally, full apply
   terraform apply tfplan
   ```

7. **Verify Infrastructure**
   ```bash
   # Check Terraform state
   terraform state list
   terraform show

   # Check Proxmox
   pvesm status
   qm list
   pct list
   ```

**Duration**: 2-4 hours

**Testing**: See [Testing Phase 3](#phase-3-testing)

---

### Phase 4: Configuration Management (Ansible)

**Goal**: Use Ansible to configure Proxmox host and VMs/LXC

**Prerequisites**:
- Phase 3 complete
- Ansible installed
- SSH access to Proxmox and VMs/LXC

**Steps**:

1. **Configure Ansible Inventory**
   ```bash
   cd /root/home-lab/new_system/ansible
   vim inventory/production/hosts.yml
   ```

   **Verify**:
   - Proxmox host IP (10.0.99.1)
   - VM IPs
   - LXC IPs
   - SSH connectivity

2. **Test Ansible Connectivity**
   ```bash
   ansible all -i inventory/production/hosts.yml -m ping
   ```

3. **Configure Proxmox Host**
   ```bash
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

   **Tasks performed**:
   - Repository configuration
   - Package installation
   - Network optimization
   - Storage optimization
   - Security hardening
   - Monitoring setup

4. **Configure VMs and LXC**
   ```bash
   # OPNsense configuration (if playbook exists)
   ansible-playbook -i inventory/production/hosts.yml playbooks/opnsense-setup.yml

   # LXC configuration
   ansible-playbook -i inventory/production/hosts.yml playbooks/lxc-setup.yml
   ```

5. **Verify Configuration**
   ```bash
   # Check Proxmox services
   systemctl status pveproxy pvedaemon pve-cluster

   # Check network bridges
   ip -br link show type bridge

   # Check storage
   pvesm status

   # Check VMs
   qm list

   # Check LXC
   pct list
   ```

**Duration**: 2-4 hours

**Testing**: See [Testing Phase 4](#phase-4-testing)

---

### Phase 5: Service Deployment

**Goal**: Deploy and configure services on VMs and LXC containers

**Components**:
- OPNsense firewall
- PostgreSQL database
- Redis cache
- Nextcloud file sharing
- Jellyfin media server
- Gitea Git server
- Miniflux RSS reader

**Steps**:

1. **Deploy OPNsense**
   - Terraform creates VM
   - Upload OPNsense ISO
   - Install OPNsense
   - Configure via Ansible (if playbook ready) or manually

2. **Deploy LXC Services**
   ```bash
   # PostgreSQL
   ansible-playbook -i inventory/production/hosts.yml playbooks/postgresql.yml

   # Redis
   ansible-playbook -i inventory/production/hosts.yml playbooks/redis.yml

   # Nextcloud
   ansible-playbook -i inventory/production/hosts.yml playbooks/nextcloud.yml

   # Jellyfin
   ansible-playbook -i inventory/production/hosts.yml playbooks/jellyfin.yml

   # Gitea
   ansible-playbook -i inventory/production/hosts.yml playbooks/gitea.yml

   # Miniflux
   ansible-playbook -i inventory/production/hosts.yml playbooks/miniflux.yml
   ```

3. **Verify Services**
   ```bash
   # Check service status
   ansible all -i inventory/production/hosts.yml -m shell -a "systemctl status <service>"

   # Check network connectivity
   ansible all -i inventory/production/hosts.yml -m shell -a "ping -c 3 1.1.1.1"

   # Check web UIs
   curl -k https://10.0.99.10    # OPNsense
   curl -k https://nextcloud.home.local
   curl -k https://jellyfin.home.local
   ```

**Duration**: 4-8 hours

**Testing**: See [Testing Phase 5](#phase-5-testing)

---

### Phase 6: Data Migration (If Upgrading)

**Goal**: Migrate data from old system to new IaC-managed system

**Only applicable if migrating from existing Proxmox installation**

**Steps**:

1. **Backup Old System**
   ```bash
   # On old Proxmox
   vzdump --all --storage local-hdd --compress zstd
   ```

2. **Copy Backups to New System**
   ```bash
   rsync -avz root@old-pve:/mnt/hdd/backup/ root@10.0.99.1:/mnt/hdd/backup/
   ```

3. **Restore VMs**
   ```bash
   # On new Proxmox
   qmrestore /mnt/hdd/backup/vzdump-qemu-*.vma.zst <vmid>
   ```

4. **Restore LXC Containers**
   ```bash
   pct restore <ctid> /mnt/hdd/backup/vzdump-lxc-*.tar.zst
   ```

5. **Verify Data**
   - Check VM disks
   - Check LXC file systems
   - Verify service data

**Duration**: 2-4 hours (depends on data size)

---

### Phase 7: Production Cutover

**Goal**: Switch from old system to new IaC-managed system

**Steps**:

1. **Final Verification**
   - All services running
   - Network connectivity working
   - Storage accessible
   - Backups configured
   - Monitoring active

2. **Update DNS/DHCP**
   - Update router configuration
   - Point domains to new IPs
   - Update DHCP reservations

3. **Monitor System**
   - Watch logs: `journalctl -f`
   - Check service status
   - Monitor resource usage: `htop`

4. **Decommission Old System** (if applicable)
   - Stop VMs/LXC on old system
   - Keep old system as backup for 1-2 weeks
   - Document any issues

**Duration**: 1-2 hours

---

## Pre-Migration Checklist

### Hardware Preparation

- [ ] Dell XPS L701X powered off and ready
- [ ] SSD 180GB installed and detected
- [ ] HDD 500GB installed and detected
- [ ] USB Ethernet adapter connected
- [ ] Built-in Ethernet port accessible
- [ ] USB drive (2GB+) available
- [ ] Power supply connected

### Network Preparation

- [ ] ISP router accessible (for WAN)
- [ ] GL.iNet Slate AX router accessible (for LAN)
- [ ] Network cables available (2x Ethernet)
- [ ] Know ISP router DHCP range
- [ ] Know GL.iNet router IP (192.168.10.1)

### Software Preparation

- [ ] Proxmox VE 9 ISO downloaded
- [ ] IaC files ready (new_system/)
- [ ] Workstation with SSH client
- [ ] Text editor for configuration files
- [ ] Password manager for secrets

### Backup Preparation (if upgrading)

- [ ] Current system backed up
- [ ] VM backups copied to external storage
- [ ] LXC backups copied to external storage
- [ ] Configuration files exported
- [ ] Certificates and keys backed up

### Documentation Preparation

- [ ] Migration guide reviewed (this file)
- [ ] Testing procedures reviewed
- [ ] Rollback plan reviewed
- [ ] Contact information for ISP (if needed)
- [ ] Proxmox documentation bookmarked

---

## Migration Phases

### Phase 1 Testing

**Objective**: Verify documentation completeness

**Tests**:
1. Review all documentation
2. Verify all prerequisites listed
3. Check all commands syntax
4. Validate all file paths
5. Confirm all IPs and networks

**Success Criteria**:
- [ ] Documentation clear and complete
- [ ] All prerequisites available
- [ ] All commands tested (syntax)
- [ ] All file paths valid

---

### Phase 2 Testing

**Objective**: Verify bare-metal installation

**Tests**:

1. **USB Creation**
   ```bash
   # Verify USB is bootable
   fdisk -l /dev/sdX

   # Verify answer.toml on USB
   mkdir /tmp/usb-test
   mount /dev/sdX2 /tmp/usb-test
   cat /tmp/usb-test/answer.toml
   umount /tmp/usb-test
   ```

2. **Proxmox Installation**
   - Boot from USB
   - Verify auto-install starts
   - Monitor installation progress
   - Verify reboot after installation

3. **Post-Install Scripts**
   ```bash
   # Test each script
   ./01-install-terraform.sh
   terraform version

   ./02-install-ansible.sh
   ansible --version

   ./03-configure-storage.sh
   pvesm status | grep local-hdd
   df -h /mnt/hdd

   ./04-configure-network.sh
   ip -br link show type bridge

   ./05-init-git-repo.sh
   cd /root/home-lab && git status
   ```

4. **System Verification**
   ```bash
   # Check Proxmox version
   pveversion

   # Check storage
   pvesm status

   # Check network
   brctl show

   # Check services
   systemctl status pveproxy pvedaemon pve-cluster

   # Check disk usage
   df -h

   # Check memory
   free -h

   # Check CPU
   lscpu
   ```

**Success Criteria**:
- [ ] USB boots successfully
- [ ] Proxmox installs without errors
- [ ] All post-install scripts run successfully
- [ ] Terraform v1.7.0 installed
- [ ] Ansible v2.14+ installed
- [ ] Storage configured (local-lvm, local-hdd)
- [ ] Network bridges created (vmbr0-vmbr99)
- [ ] Git repository initialized
- [ ] Web UI accessible at https://10.0.99.1:8006

---

### Phase 3 Testing

**Objective**: Verify Terraform infrastructure provisioning

**Tests**:

1. **Terraform Initialization**
   ```bash
   terraform init
   terraform validate
   ```

2. **Terraform Plan**
   ```bash
   terraform plan -out=tfplan
   # Review plan output
   ```

3. **Network Module**
   ```bash
   terraform apply -target=module.network

   # Verify bridges created
   brctl show
   ip addr show vmbr0
   ip addr show vmbr1
   ip addr show vmbr2
   ip addr show vmbr99
   ```

4. **Storage Module**
   ```bash
   terraform apply -target=module.storage

   # Verify storage
   pvesm status
   ```

5. **VM Module** (if defined)
   ```bash
   terraform apply -target=module.vm

   # Verify VMs
   qm list
   ```

6. **LXC Module** (if defined)
   ```bash
   terraform apply -target=module.lxc

   # Verify LXC
   pct list
   ```

7. **State Management**
   ```bash
   terraform state list
   terraform show
   terraform output
   ```

**Success Criteria**:
- [ ] Terraform initializes successfully
- [ ] Terraform plan succeeds
- [ ] Network module creates bridges
- [ ] Storage module configures storage
- [ ] VMs created (if defined)
- [ ] LXC created (if defined)
- [ ] Terraform state accurate
- [ ] No drift detected: `terraform plan` shows no changes

---

### Phase 4 Testing

**Objective**: Verify Ansible configuration management

**Tests**:

1. **Ansible Connectivity**
   ```bash
   ansible all -i inventory/production/hosts.yml -m ping
   ```

2. **Syntax Check**
   ```bash
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml --syntax-check
   ```

3. **Dry Run**
   ```bash
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml --check
   ```

4. **Proxmox Configuration**
   ```bash
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml

   # Verify changes
   cat /etc/apt/sources.list.d/pve-no-subscription.list
   systemctl status pveproxy
   ```

5. **Idempotency Test**
   ```bash
   # Run again, should show 0 changes
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

6. **Service Configuration**
   ```bash
   # Test individual service playbooks
   ansible-playbook -i inventory/production/hosts.yml playbooks/postgresql.yml --check
   ansible-playbook -i inventory/production/hosts.yml playbooks/redis.yml --check
   ```

**Success Criteria**:
- [ ] Ansible pings all hosts successfully
- [ ] Playbooks pass syntax check
- [ ] Dry run completes without errors
- [ ] Proxmox configuration applied successfully
- [ ] Playbooks are idempotent (2nd run = 0 changes)
- [ ] Services configured correctly
- [ ] No errors in ansible output

---

### Phase 5 Testing

**Objective**: Verify service deployment and functionality

**Tests**:

1. **OPNsense**
   ```bash
   # Check VM status
   qm status <vmid>

   # Check network connectivity
   ping 10.0.99.10

   # Check web UI
   curl -k https://10.0.99.10
   ```

2. **PostgreSQL**
   ```bash
   # Check container status
   pct status <ctid>

   # Check PostgreSQL service
   pct exec <ctid> -- systemctl status postgresql

   # Test connection
   pct exec <ctid> -- psql -U postgres -c "SELECT version();"
   ```

3. **Redis**
   ```bash
   # Check Redis service
   pct exec <ctid> -- systemctl status redis

   # Test connection
   pct exec <ctid> -- redis-cli ping
   ```

4. **Nextcloud**
   ```bash
   # Check web server
   pct exec <ctid> -- systemctl status nginx

   # Check PHP-FPM
   pct exec <ctid> -- systemctl status php8.2-fpm

   # Test web UI
   curl -k https://nextcloud.home.local
   ```

5. **Jellyfin**
   ```bash
   # Check service
   pct exec <ctid> -- systemctl status jellyfin

   # Test web UI
   curl -k https://jellyfin.home.local
   ```

6. **Network Connectivity**
   ```bash
   # Test inter-container connectivity
   ansible all -i inventory/production/hosts.yml -m shell -a "ping -c 3 10.0.30.10"

   # Test internet connectivity
   ansible all -i inventory/production/hosts.yml -m shell -a "ping -c 3 1.1.1.1"

   # Test DNS resolution
   ansible all -i inventory/production/hosts.yml -m shell -a "nslookup google.com"
   ```

**Success Criteria**:
- [ ] All VMs running
- [ ] All LXC containers running
- [ ] All services active
- [ ] Web UIs accessible
- [ ] Database connections working
- [ ] Redis connections working
- [ ] Inter-container connectivity working
- [ ] Internet connectivity working
- [ ] DNS resolution working

---

## Rollback Plan

### Scenario 1: USB Creation Fails

**Problem**: Unable to create bootable USB

**Rollback**:
1. Use different USB drive
2. Re-download ISO file
3. Verify ISO file integrity: `sha256sum proxmox-ve_9.0-1.iso`
4. Use alternative USB creator tool (Etcher, Rufus, dd)

**Prevention**: Test USB creation on multiple drives before migration day

---

### Scenario 2: Proxmox Installation Fails

**Problem**: Installation hangs or fails during auto-install

**Rollback**:
1. Power off system
2. Remove USB drive
3. Boot into BIOS
4. Verify hardware detection (SSD, HDD, RAM)
5. Check answer.toml configuration
6. Retry installation with corrected configuration

**Prevention**:
- Verify hardware compatibility before starting
- Test answer.toml syntax
- Have backup USB drive ready

---

### Scenario 3: Post-Install Script Fails

**Problem**: One of the post-install scripts fails

**Rollback**:
1. Review script output for error
2. Fix issue manually
3. Re-run failed script
4. Continue with remaining scripts

**Common Issues**:
- Network connectivity: Check DHCP, DNS
- Package installation: Check repositories
- Storage: Check HDD detection

**Prevention**: Test scripts in VM before production

---

### Scenario 4: Terraform Apply Fails

**Problem**: Terraform fails to create resources

**Rollback**:
1. Review Terraform error output
2. Check Proxmox API connectivity
3. Fix configuration issue
4. Destroy partial resources: `terraform destroy`
5. Re-apply: `terraform apply`

**Data Safety**:
- Terraform state file backed up automatically
- No data loss (infrastructure only)
- Can manually delete resources from Proxmox UI if needed

**Prevention**:
- Test Terraform configuration in dry-run mode
- Validate all variables before applying
- Use `-target` flag for incremental application

---

### Scenario 5: Ansible Playbook Fails

**Problem**: Ansible playbook fails during execution

**Rollback**:
1. Review Ansible error output
2. Check SSH connectivity
3. Fix configuration issue
4. Re-run playbook (Ansible is idempotent)

**Data Safety**:
- Ansible doesn't delete data
- Can manually revert changes if needed
- Proxmox backups available

**Prevention**:
- Run playbooks with `--check` flag first
- Test on isolated host before production
- Use `--step` flag for interactive execution

---

### Scenario 6: Service Deployment Fails

**Problem**: Service doesn't start or work correctly

**Rollback**:
1. Check service logs: `journalctl -u <service>`
2. Review Ansible output
3. Manually configure service
4. Or destroy and recreate container

**Data Safety**:
- Service data stored separately
- Can restore from backup if needed

**Prevention**:
- Test service configuration in VM first
- Verify all dependencies installed
- Check network connectivity

---

### Scenario 7: Complete System Failure

**Problem**: System unusable after migration

**Rollback Options**:

**Option A: Reinstall Proxmox**
1. Boot from USB again
2. Reinstall Proxmox (10-15 minutes)
3. Run post-install scripts
4. Start over from Phase 3

**Option B: Restore from Backup** (if upgrading)
1. Boot from backup system
2. Restore old Proxmox from backup
3. Restore VMs and LXC from backups
4. Troubleshoot migration issues offline

**Option C: Start Fresh** (if new install)
1. Review all configurations
2. Fix identified issues
3. Start migration process again
4. Use lessons learned from first attempt

**Data Safety**:
- All backups on external storage
- No data loss if backups were made
- Can restore to previous state completely

---

## Post-Migration Validation

### System Health Checks

Run these checks after migration:

```bash
# 1. Proxmox Version
pveversion

# 2. Storage Status
pvesm status
df -h

# 3. Network Status
brctl show
ip addr
ping 1.1.1.1

# 4. VM Status
qm list
qm status <vmid>

# 5. LXC Status
pct list
pct status <ctid>

# 6. Service Status
systemctl status pveproxy pvedaemon pve-cluster

# 7. Resource Usage
htop
free -h
df -h

# 8. Logs
journalctl -xe | tail -100
```

### Functional Tests

Test each service:

```bash
# OPNsense
curl -k https://10.0.99.10
# Expected: OPNsense login page

# PostgreSQL
pct exec <ctid> -- psql -U postgres -c "SELECT 1;"
# Expected: 1 row returned

# Redis
pct exec <ctid> -- redis-cli ping
# Expected: PONG

# Nextcloud
curl -k https://nextcloud.home.local
# Expected: Nextcloud login page

# Jellyfin
curl -k https://jellyfin.home.local
# Expected: Jellyfin UI

# DNS Resolution
nslookup google.com
# Expected: IP address returned
```

### Performance Baseline

Establish performance baseline:

```bash
# CPU Usage
top -bn1 | grep "Cpu(s)"

# Memory Usage
free -h

# Disk I/O
iostat -x 1 10

# Network Throughput
iperf3 -c <remote-host> -t 60

# Latency
ping -c 100 1.1.1.1 | tail -1
```

### Security Audit

Verify security configuration:

```bash
# Check firewall status
pct exec <opnsense-ctid> -- pfctl -si

# Check SSH configuration
cat /etc/ssh/sshd_config | grep -E "PermitRootLogin|PasswordAuthentication"

# Check open ports
ss -tuln

# Check running services
systemctl list-units --type=service --state=running

# Check failed login attempts
journalctl -u ssh | grep "Failed password"
```

---

## Troubleshooting

### Common Issues

#### Issue: Cannot SSH to Proxmox

**Symptoms**:
- Connection refused
- Connection timeout
- Host key verification failed

**Solutions**:
```bash
# Check SSH service
systemctl status ssh

# Check firewall
iptables -L -n

# Check SSH config
cat /etc/ssh/sshd_config

# Reset known_hosts
ssh-keygen -R <proxmox-ip>
```

#### Issue: Terraform Can't Connect to Proxmox API

**Symptoms**:
- Authentication failed
- Connection timeout
- SSL verification failed

**Solutions**:
```bash
# Check Proxmox API
curl -k https://10.0.99.1:8006/api2/json/version

# Check API token
pvesh get /access/users/root@pam/token/terraform

# Verify token in terraform.tfvars
cat terraform.tfvars | grep proxmox_api_token

# Test API with curl
curl -k -H "Authorization: PVEAPIToken=root@pam!terraform=<token>" \
  https://10.0.99.1:8006/api2/json/nodes
```

#### Issue: Ansible Can't Connect to Hosts

**Symptoms**:
- SSH connection refused
- Authentication failed
- Host unreachable

**Solutions**:
```bash
# Test SSH manually
ssh root@<host-ip>

# Check inventory
cat new_system/ansible/inventory/production/hosts.yml

# Test Ansible ping
cd new_system/ansible
ansible all -i inventory/production/hosts.yml -m ping -vvv

# Check SSH keys
ls -la ~/.ssh/
```

#### Issue: VMs or LXC Won't Start

**Symptoms**:
- Start command fails
- VM/LXC stuck in starting state
- Error messages in logs

**Solutions**:
```bash
# Check VM status
qm status <vmid>

# Check VM configuration
qm config <vmid>

# Check VM logs
journalctl -u qemu-server@<vmid>

# Start VM manually
qm start <vmid>

# For LXC
pct status <ctid>
pct start <ctid>
journalctl -u pve-container@<ctid>
```

#### Issue: Network Bridge Not Working

**Symptoms**:
- VMs can't reach network
- No IP address assigned
- Bridge not shown in `brctl show`

**Solutions**:
```bash
# Check bridge status
ip link show type bridge

# Check bridge configuration
cat /etc/network/interfaces

# Restart networking
systemctl restart networking

# Check UDEV rules
cat /etc/udev/rules.d/70-persistent-net.rules

# Reload UDEV
udevadm control --reload-rules
udevadm trigger

# Reboot
reboot
```

#### Issue: Storage Pool Not Available

**Symptoms**:
- Storage not shown in `pvesm status`
- Can't create VM/LXC
- Disk space errors

**Solutions**:
```bash
# Check storage status
pvesm status

# Check HDD mount
df -h /mnt/hdd
mount | grep hdd

# Check /etc/fstab
cat /etc/fstab

# Remount HDD
mount -a

# Check Proxmox storage config
cat /etc/pve/storage.cfg

# Add storage manually if needed
pvesm add dir local-hdd --path /mnt/hdd \
  --content backup,iso,vztmpl,snippets
```

---

## Success Metrics

Track these metrics to measure migration success:

### Infrastructure Metrics

- **Deployment Time**: Time from bare-metal to fully functional system
  - Target: < 4 hours
  - Current: TBD

- **Configuration Drift**: Terraform plan shows no changes
  - Target: 0 changes after apply
  - Current: TBD

- **Idempotency**: Ansible playbook 2nd run shows no changes
  - Target: 0 changes after 1st run
  - Current: TBD

### Reliability Metrics

- **System Uptime**: Time system stays running without issues
  - Target: 99.9% (43 minutes downtime/month)
  - Current: TBD

- **Service Availability**: Services accessible and functional
  - Target: 99.9%
  - Current: TBD

- **Backup Success Rate**: Backups complete successfully
  - Target: 100%
  - Current: TBD

### Performance Metrics

- **VM Boot Time**: Time for VM to boot and be accessible
  - Target: < 60 seconds
  - Current: TBD

- **LXC Start Time**: Time for LXC to start and be accessible
  - Target: < 10 seconds
  - Current: TBD

- **Network Latency**: Ping response time within network
  - Target: < 1ms
  - Current: TBD

- **Storage I/O**: Disk read/write performance
  - Target: > 100 MB/s (SSD)
  - Current: TBD

### Automation Metrics

- **Manual Steps Required**: Number of manual interventions needed
  - Target: 0 (fully automated)
  - Current: TBD

- **Documentation Coverage**: Percentage of processes documented
  - Target: 100%
  - Current: 100% ✅

- **Test Coverage**: Percentage of components tested
  - Target: 100%
  - Current: TBD

---

## Conclusion

This migration guide provides a comprehensive path from script-based infrastructure to Infrastructure as Code using Terraform and Ansible.

**Key Takeaways**:
1. Migration is phased to minimize risk
2. Testing is critical at each phase
3. Rollback plans are in place for all scenarios
4. Documentation is comprehensive and up-to-date

**Next Steps**:
1. Complete Phase 1 (testing setup)
2. Execute Phase 2 (bare-metal installation)
3. Continue through remaining phases
4. Track metrics and document lessons learned

**Resources**:
- [Terraform Proxmox Provider Docs](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Ansible Proxmox Module Docs](https://docs.ansible.com/ansible/latest/collections/community/general/proxmox_module.html)
- [Proxmox VE Documentation](https://pve.proxmox.com/wiki/Main_Page)
- [Project README](README.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-06
**Author**: Home Lab Administrator
**Status**: Complete
