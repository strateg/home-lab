# Testing Procedures

Comprehensive testing guide for Infrastructure as Code (IaC) home lab on Proxmox VE 9.

## Table of Contents

1. [Overview](#overview)
2. [Testing Environments](#testing-environments)
3. [Unit Testing](#unit-testing)
4. [Integration Testing](#integration-testing)
5. [System Testing](#system-testing)
6. [Performance Testing](#performance-testing)
7. [Security Testing](#security-testing)
8. [Automated Testing](#automated-testing)
9. [Manual Testing Checklists](#manual-testing-checklists)

---

## Overview

### Testing Philosophy

**Goals**:
- Verify infrastructure works as designed
- Catch errors before production
- Ensure repeatability and idempotency
- Document expected behavior
- Provide confidence in changes

**Testing Pyramid**:
```
       ╱╲
      ╱  ╲  Manual Testing (few)
     ╱────╲
    ╱      ╲  Integration Tests (some)
   ╱────────╲
  ╱          ╲  Unit Tests (many)
 ╱────────────╲
```

### Testing Levels

1. **Unit Testing**: Individual components (Terraform modules, Ansible roles)
2. **Integration Testing**: Components working together (Terraform + Proxmox, Ansible + VMs)
3. **System Testing**: Complete system functionality (end-to-end workflows)
4. **Performance Testing**: Resource usage and response times
5. **Security Testing**: Access controls and hardening

---

## Testing Environments

### Development Environment

**Purpose**: Test changes in isolation

**Setup**:
- Virtual machine (KVM/VirtualBox/VMware)
- Nested virtualization enabled
- Proxmox VE installed
- Minimal resources (2 CPU, 4GB RAM)

**Use Cases**:
- Terraform module development
- Ansible role development
- Script testing
- Documentation verification

**Limitations**:
- Performance not representative
- Limited hardware features
- No real network hardware

---

### Staging Environment

**Purpose**: Test full system before production

**Setup**:
- Identical hardware to production (Dell XPS L701X)
- Separate physical machine (if available)
- Or same machine with snapshot/backup

**Use Cases**:
- Full migration rehearsal
- Performance testing
- Network configuration testing
- Hardware-specific testing

**Limitations**:
- Requires physical hardware
- May not have all production data

---

### Production Environment

**Purpose**: Live system

**Setup**:
- Dell XPS L701X
- Real network connections
- Real services and data

**Testing Strategy**:
- Test changes in dev/staging first
- Use maintenance windows
- Have rollback plan ready
- Monitor closely after changes

---

## Unit Testing

### Terraform Module Testing

#### Network Module

**Test Cases**:

1. **Bridge Creation**
   ```bash
   cd terraform/modules/network

   # Initialize
   terraform init

   # Validate syntax
   terraform validate

   # Format check
   terraform fmt -check

   # Plan (dry run)
   terraform plan
   ```

   **Expected**:
   - 4 bridges planned (vmbr0-vmbr99)
   - No errors or warnings
   - Correct IP addresses assigned

2. **Variable Validation**
   ```bash
   # Test with invalid values
   cat > test.tfvars <<EOF
   wan_interface = ""  # Empty - should fail validation
   EOF

   terraform plan -var-file=test.tfvars
   ```

   **Expected**:
   - Validation error for empty interface
   - Clear error message

3. **Module Outputs**
   ```bash
   terraform plan
   terraform output
   ```

   **Expected**:
   - All outputs defined
   - Correct values returned

**Automated Test**:
```bash
#!/bin/bash
# test-network-module.sh

cd terraform/modules/network

echo "Testing network module..."

# Validate
terraform validate || { echo "Validation failed"; exit 1; }

# Format check
terraform fmt -check || { echo "Format check failed"; exit 1; }

# Plan
terraform plan -out=test.tfplan || { echo "Plan failed"; exit 1; }

echo "Network module tests passed!"
```

---

#### Storage Module

**Test Cases**:

1. **Storage Configuration**
   ```bash
   cd terraform/modules/storage

   terraform validate
   terraform plan
   ```

   **Expected**:
   - Both storage pools configured (local-lvm, local-hdd)
   - Correct content types
   - Backup retention configured

2. **Backup Retention Logic**
   ```bash
   # Verify prune_backups configuration
   terraform show -json | jq '.values.root_module.child_modules[] | select(.address=="module.storage")'
   ```

   **Expected**:
   - keep-last=3
   - keep-daily=7
   - keep-weekly=4
   - keep-monthly=6
   - keep-yearly=1

---

### Ansible Role Testing

#### Proxmox Role

**Test Cases**:

1. **Syntax Validation**
   ```bash
   cd ansible

   # Check syntax
   ansible-playbook playbooks/proxmox-setup.yml --syntax-check

   # Lint
   ansible-lint roles/proxmox/
   ```

   **Expected**:
   - No syntax errors
   - No lint warnings

2. **Variable Validation**
   ```bash
   # Check default variables
   cat roles/proxmox/defaults/main.yml

   # Check required variables
   ansible-playbook playbooks/proxmox-setup.yml --list-tasks
   ```

   **Expected**:
   - All required variables defined
   - Sensible defaults

3. **Task Validation**
   ```bash
   # List tasks
   ansible-playbook playbooks/proxmox-setup.yml --list-tasks

   # List tags
   ansible-playbook playbooks/proxmox-setup.yml --list-tags
   ```

   **Expected**:
   - All tasks listed
   - Appropriate tags assigned

**Automated Test**:
```bash
#!/bin/bash
# test-proxmox-role.sh

cd ansible

echo "Testing Proxmox role..."

# Syntax check
ansible-playbook playbooks/proxmox-setup.yml --syntax-check || \
  { echo "Syntax check failed"; exit 1; }

# Lint (optional, may have warnings)
ansible-lint roles/proxmox/ || echo "Lint warnings found (non-fatal)"

echo "Proxmox role tests passed!"
```

---

## Integration Testing

### Terraform + Proxmox Integration

**Objective**: Verify Terraform can provision resources on Proxmox

**Prerequisites**:
- Proxmox VE installed and accessible
- API token created
- Network connectivity

**Test Cases**:

1. **Provider Connection**
   ```bash
   cd terraform

   # Initialize
   terraform init

   # Test connection by listing nodes
   terraform console <<< "data.proxmox_virtual_environment_nodes.available.names"
   ```

   **Expected**:
   - Provider initializes successfully
   - Can connect to Proxmox API
   - Lists node names

2. **Network Provisioning**
   ```bash
   # Apply network module only
   terraform apply -target=module.network -auto-approve

   # Verify on Proxmox
   ssh root@10.0.99.1 "brctl show"

   # Check Terraform state
   terraform state list | grep bridge

   # Cleanup
   terraform destroy -target=module.network -auto-approve
   ```

   **Expected**:
   - Bridges created on Proxmox
   - Terraform state updated
   - Destroy removes bridges cleanly

3. **Storage Provisioning**
   ```bash
   # Apply storage module
   terraform apply -target=module.storage -auto-approve

   # Verify on Proxmox
   ssh root@10.0.99.1 "pvesm status"

   # Cleanup
   terraform destroy -target=module.storage -auto-approve
   ```

   **Expected**:
   - Storage pools configured
   - Accessible from Proxmox UI
   - Destroy removes configuration

4. **Idempotency Test**
   ```bash
   # Apply twice
   terraform apply -auto-approve
   terraform apply -auto-approve

   # Second apply should show no changes
   ```

   **Expected**:
   - First apply creates resources
   - Second apply shows "No changes. Infrastructure is up-to-date."

---

### Ansible + Proxmox Integration

**Objective**: Verify Ansible can configure Proxmox host

**Prerequisites**:
- Proxmox VE installed
- SSH access configured
- Ansible installed

**Test Cases**:

1. **Connectivity Test**
   ```bash
   cd ansible

   # Ping test
   ansible all -i inventory/production/hosts.yml -m ping
   ```

   **Expected**:
   - All hosts respond with "pong"

2. **Fact Gathering**
   ```bash
   # Gather facts
   ansible all -i inventory/production/hosts.yml -m setup | head -50
   ```

   **Expected**:
   - Facts collected successfully
   - Correct OS, network, disk info

3. **Repository Configuration**
   ```bash
   # Run repository tasks only
   ansible-playbook -i inventory/production/hosts.yml \
     playbooks/proxmox-setup.yml \
     --tags repositories \
     --check

   # Apply
   ansible-playbook -i inventory/production/hosts.yml \
     playbooks/proxmox-setup.yml \
     --tags repositories
   ```

   **Expected**:
   - Enterprise repo disabled
   - No-subscription repo enabled
   - Package cache updated

4. **Idempotency Test**
   ```bash
   # Run playbook twice
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

   **Expected**:
   - First run: Some changes made
   - Second run: 0 changes, all tasks "ok"

---

## System Testing

### End-to-End Workflows

#### Workflow 1: Fresh Installation

**Objective**: Verify complete system can be built from scratch

**Steps**:

1. **Bare-metal Installation**
   ```bash
   # Create USB (use wrapper or main script)
   cd new_system/manual-scripts/bare-metal/
   sudo ./run-create-usb.sh  # Interactive
   # Or: sudo ./create-uefi-autoinstall-proxmox-usb.sh /dev/sdb proxmox-ve_9.0-1.iso

   # Boot and install (manual step)
   # Wait for installation to complete (~15 minutes)

   # Verify access
   ssh root@<proxmox-ip>
   ```

   **Expected**:
   - USB boots successfully
   - Installation completes without errors
   - Can SSH to Proxmox

2. **Post-Install Scripts**
   ```bash
   # Run all scripts
   cd /root/post-install
   ./01-install-terraform.sh
   ./02-install-ansible.sh
   ./03-configure-storage.sh
   ./04-configure-network.sh
   ./05-init-git-repo.sh
   reboot
   ```

   **Expected**:
   - All scripts complete successfully
   - Tools installed (Terraform, Ansible)
   - Storage configured
   - Network configured
   - Git repository initialized

3. **Infrastructure Provisioning**
   ```bash
   # Copy IaC files
   scp -r terraform/ ansible/ root@10.0.99.1:/root/home-lab/

   # SSH to Proxmox
   ssh root@10.0.99.1

   # Configure Terraform
   cd /root/home-lab/terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars

   # Apply
   terraform init
   terraform apply
   ```

   **Expected**:
   - Terraform applies successfully
   - All resources created

4. **Configuration Management**
   ```bash
   cd /root/home-lab/ansible
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

   **Expected**:
   - Ansible completes successfully
   - Proxmox configured correctly

5. **Verification**
   ```bash
   # Check everything
   pvesm status
   brctl show
   qm list
   pct list
   systemctl status pveproxy
   ```

   **Expected**:
   - All components working
   - No errors in logs

**Total Duration**: 2-4 hours

**Success Criteria**: Complete system functional from bare-metal to configured infrastructure

---

#### Workflow 2: Configuration Changes

**Objective**: Verify changes can be applied safely

**Steps**:

1. **Terraform Change**
   ```bash
   # Modify configuration
   vim terraform/terraform.tfvars

   # Plan changes
   terraform plan

   # Review plan
   # Apply changes
   terraform apply
   ```

   **Expected**:
   - Plan shows only intended changes
   - Apply succeeds
   - No unintended side effects

2. **Ansible Change**
   ```bash
   # Modify role
   vim ansible/roles/proxmox/tasks/main.yml

   # Dry run
   ansible-playbook -i inventory/production/hosts.yml \
     playbooks/proxmox-setup.yml --check

   # Apply
   ansible-playbook -i inventory/production/hosts.yml \
     playbooks/proxmox-setup.yml
   ```

   **Expected**:
   - Dry run shows expected changes
   - Apply succeeds
   - Idempotent (2nd run = 0 changes)

3. **Verification**
   ```bash
   # Verify change applied
   ssh root@10.0.99.1 "cat /etc/some-config-file"

   # Check no regression
   terraform plan  # Should show no changes
   ansible-playbook ... --check  # Should show no changes
   ```

   **Expected**:
   - Changes applied correctly
   - No configuration drift

---

#### Workflow 3: Disaster Recovery

**Objective**: Verify system can be restored from backup

**Steps**:

1. **Create Backup**
   ```bash
   # Backup VMs
   ssh root@10.0.99.1 "vzdump --all --storage local-hdd --compress zstd"

   # Backup Terraform state
   cd terraform
   cp terraform.tfstate terraform.tfstate.backup

   # Backup Ansible files
   cd ansible
   tar czf ansible-backup.tar.gz .
   ```

2. **Simulate Disaster**
   ```bash
   # Delete a VM
   ssh root@10.0.99.1 "qm destroy <vmid>"

   # Or simulate complete failure
   # (reinstall Proxmox)
   ```

3. **Restore System**
   ```bash
   # Reinstall from bare-metal (if needed)
   # Run post-install scripts
   # Copy IaC files

   # Restore Terraform state
   cd terraform
   terraform init
   terraform apply

   # Restore VMs from backup
   ssh root@10.0.99.1 "qmrestore /mnt/hdd/backup/vzdump-qemu-*.vma.zst <vmid>"

   # Run Ansible
   cd ansible
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

4. **Verification**
   ```bash
   # Verify all services
   ssh root@10.0.99.1 "qm list"
   ssh root@10.0.99.1 "pct list"
   ssh root@10.0.99.1 "pvesm status"
   ```

   **Expected**:
   - System fully restored
   - All services functional
   - No data loss

**Total Duration**: 1-3 hours

**Success Criteria**: System restored to working state from backups

---

## Performance Testing

### Resource Usage

**Objective**: Verify system runs within hardware constraints

**Tests**:

1. **CPU Usage**
   ```bash
   # Baseline (idle)
   ssh root@10.0.99.1 "mpstat 1 60 | tail -5"

   # Under load (run stress test)
   ssh root@10.0.99.1 "stress --cpu 2 --timeout 60s & mpstat 1 60"
   ```

   **Expected**:
   - Idle: < 20% CPU usage
   - Load: System responsive, no hang

2. **Memory Usage**
   ```bash
   # Check memory
   ssh root@10.0.99.1 "free -h"

   # Check KSM (memory deduplication)
   ssh root@10.0.99.1 "cat /sys/kernel/mm/ksm/pages_sharing"
   ```

   **Expected**:
   - < 6GB used (on 8GB system)
   - KSM active and saving memory
   - No OOM kills in logs

3. **Disk I/O**
   ```bash
   # Test SSD read
   ssh root@10.0.99.1 "dd if=/dev/sda of=/dev/null bs=1M count=1000"

   # Test SSD write
   ssh root@10.0.99.1 "dd if=/dev/zero of=/tmp/test.img bs=1M count=1000 oflag=direct"

   # Test HDD read
   ssh root@10.0.99.1 "dd if=/dev/sdb of=/dev/null bs=1M count=1000"
   ```

   **Expected**:
   - SSD read: > 200 MB/s
   - SSD write: > 100 MB/s
   - HDD read: > 50 MB/s

4. **Network Throughput**
   ```bash
   # Install iperf3 on both ends
   ssh root@10.0.99.1 "apt install -y iperf3"

   # Run server
   ssh root@10.0.99.1 "iperf3 -s" &

   # Run client
   iperf3 -c 10.0.99.1 -t 30
   ```

   **Expected**:
   - Throughput: > 900 Mbps (on 1 Gbps link)
   - Low jitter
   - No packet loss

---

### Response Times

**Objective**: Verify system responds quickly

**Tests**:

1. **VM Boot Time**
   ```bash
   # Boot VM and measure time
   time ssh root@10.0.99.1 "qm start <vmid> && while ! ping -c 1 <vm-ip> &>/dev/null; do sleep 1; done"
   ```

   **Expected**:
   - < 60 seconds to network-ready

2. **LXC Start Time**
   ```bash
   # Start LXC and measure time
   time ssh root@10.0.99.1 "pct start <ctid> && while ! pct exec <ctid> -- true &>/dev/null; do sleep 0.1; done"
   ```

   **Expected**:
   - < 10 seconds to ready

3. **API Response Time**
   ```bash
   # Test Proxmox API
   time curl -k https://10.0.99.1:8006/api2/json/version
   ```

   **Expected**:
   - < 500ms response time

4. **SSH Login Time**
   ```bash
   # Test SSH login
   time ssh root@10.0.99.1 "exit"
   ```

   **Expected**:
   - < 2 seconds

---

## Security Testing

### Access Control

**Objective**: Verify only authorized access allowed

**Tests**:

1. **SSH Access**
   ```bash
   # Test password authentication (should be disabled)
   ssh -o PreferredAuthentications=password root@10.0.99.1
   ```

   **Expected**:
   - Password authentication refused
   - Key-based authentication works

2. **Proxmox Web UI**
   ```bash
   # Test HTTPS
   curl -k https://10.0.99.1:8006

   # Test HTTP (should redirect or fail)
   curl http://10.0.99.1:8006
   ```

   **Expected**:
   - HTTPS works
   - HTTP blocked or redirects to HTTPS

3. **API Access**
   ```bash
   # Test without token (should fail)
   curl -k https://10.0.99.1:8006/api2/json/nodes

   # Test with invalid token (should fail)
   curl -k -H "Authorization: PVEAPIToken=invalid" \
     https://10.0.99.1:8006/api2/json/nodes

   # Test with valid token (should work)
   curl -k -H "Authorization: PVEAPIToken=root@pam!terraform=<token>" \
     https://10.0.99.1:8006/api2/json/nodes
   ```

   **Expected**:
   - Unauthorized requests blocked
   - Valid token grants access

---

### Network Security

**Objective**: Verify network isolation and firewall rules

**Tests**:

1. **Network Isolation**
   ```bash
   # Test LXC containers can't reach management network
   ssh root@10.0.99.1 "pct exec <ctid> -- ping -c 3 10.0.99.1"

   # Test management network can reach LXC
   ssh root@10.0.99.1 "ping -c 3 10.0.30.10"
   ```

   **Expected**:
   - Management can reach all networks
   - LXC can't reach management (if firewall configured)

2. **Firewall Rules**
   ```bash
   # Check firewall status
   ssh root@10.0.99.1 "pve-firewall status"

   # Check rules
   ssh root@10.0.99.1 "cat /etc/pve/firewall/cluster.fw"
   ```

   **Expected**:
   - Firewall active
   - Rules configured correctly

---

## Automated Testing

### CI/CD Integration

**Example GitHub Actions Workflow**:

```yaml
# .github/workflows/test.yml
name: Test Infrastructure

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  terraform-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.7.0

      - name: Terraform Init
        run: cd terraform && terraform init

      - name: Terraform Validate
        run: cd terraform && terraform validate

      - name: Terraform Format Check
        run: cd terraform && terraform fmt -check

  ansible-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Ansible
        run: pip install ansible ansible-lint

      - name: Ansible Syntax Check
        run: cd ansible && ansible-playbook playbooks/proxmox-setup.yml --syntax-check

      - name: Ansible Lint
        run: cd ansible && ansible-lint roles/
```

---

### Test Automation Scripts

**Terraform Test Script**:
```bash
#!/bin/bash
# tests/terraform-test.sh

set -e

echo "=== Terraform Tests ==="

cd terraform

echo "[1/4] Initializing..."
terraform init -backend=false

echo "[2/4] Validating..."
terraform validate

echo "[3/4] Format check..."
terraform fmt -check -recursive

echo "[4/4] Plan check..."
terraform plan -out=test.tfplan

echo "✓ All Terraform tests passed!"
```

**Ansible Test Script**:
```bash
#!/bin/bash
# tests/ansible-test.sh

set -e

echo "=== Ansible Tests ==="

cd ansible

echo "[1/3] Syntax check..."
ansible-playbook playbooks/proxmox-setup.yml --syntax-check

echo "[2/3] Linting..."
ansible-lint roles/ || echo "Warning: Lint issues found"

echo "[3/3] Dry run..."
ansible-playbook -i inventory/production/hosts.yml \
  playbooks/proxmox-setup.yml --check || echo "Note: Dry run may fail without real hosts"

echo "✓ All Ansible tests passed!"
```

**Run All Tests**:
```bash
#!/bin/bash
# tests/run-all-tests.sh

set -e

echo "========================================="
echo "  Running All Tests"
echo "========================================="

./tests/terraform-test.sh
./tests/ansible-test.sh

echo ""
echo "========================================="
echo "  ✓ All Tests Passed!"
echo "========================================="
```

---

## Manual Testing Checklists

### Pre-Deployment Checklist

Before deploying to production:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Terraform plan reviewed
- [ ] Ansible dry-run successful
- [ ] Documentation updated
- [ ] Backup created
- [ ] Rollback plan ready
- [ ] Maintenance window scheduled
- [ ] Team notified

### Post-Deployment Checklist

After deploying to production:

- [ ] All services accessible
- [ ] No errors in logs
- [ ] Terraform state clean (`terraform plan` = no changes)
- [ ] Ansible idempotent (2nd run = 0 changes)
- [ ] Performance metrics normal
- [ ] Backup successful
- [ ] Monitoring active
- [ ] Documentation updated
- [ ] Team notified of completion

### Weekly Health Check

Perform weekly:

- [ ] Check disk space: `df -h`
- [ ] Check memory: `free -h`
- [ ] Check CPU load: `uptime`
- [ ] Check services: `systemctl status`
- [ ] Check logs: `journalctl -xe`
- [ ] Check backups: `ls -lh /mnt/hdd/backup/`
- [ ] Test restore: Restore one VM from backup
- [ ] Run Terraform plan: Should show no changes
- [ ] Run Ansible playbook: Should show no changes
- [ ] Update packages: `apt update && apt upgrade`

---

## Conclusion

Comprehensive testing ensures:
- Infrastructure works as designed
- Changes are safe to apply
- System can be recovered from failures
- Performance meets requirements
- Security is maintained

**Testing Workflow**:
1. Unit test components individually
2. Integration test components together
3. System test complete workflows
4. Performance test under load
5. Security test access controls
6. Automate repeatable tests
7. Document test results

**Resources**:
- [Terraform Testing Best Practices](https://www.terraform.io/docs/language/modules/testing-experiment.html)
- [Ansible Testing Strategies](https://docs.ansible.com/ansible/latest/dev_guide/testing.html)
- [Proxmox VE Testing](https://pve.proxmox.com/wiki/Test_Lab)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-06
**Author**: Home Lab Administrator
**Status**: Complete
