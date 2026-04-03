# Deploy Plane Scenarios

Operational scenarios and step-by-step procedures.

---

## Table of Contents

1. [Day-to-Day Operations](#day-to-day-operations)
2. [Initial Infrastructure Setup](#initial-infrastructure-setup)
3. [Node Bootstrap Scenarios](#node-bootstrap-scenarios)
4. [Maintenance Operations](#maintenance-operations)
5. [Emergency Procedures](#emergency-procedures)
6. [CI/CD Integration](#cicd-integration)
7. [Multi-Environment Workflows](#multi-environment-workflows)

---

## Day-to-Day Operations

### Scenario: Apply Configuration Changes

**Context:** You've updated topology YAML and want to apply changes to infrastructure.

```bash
# 1. Validate topology
task validate:passthrough

# 2. Build artifacts
task build:default

# 3. Create new bundle
task bundle:create
# Output: {"bundle_id": "b-abc123", ...}

# 4. Check what will change
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-abc123

# 5. Review Terraform plan output
# Check .work/evidence/ for detailed reports

# 6. Apply changes
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-abc123

# 7. Verify deployment
task deploy:init-status
```

### Scenario: Quick Configuration Check

**Context:** Verify current infrastructure matches expected state.

```bash
# Run check without apply
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-abc123

# Check for drift
# Output shows any differences between bundle and live state
```

---

## Initial Infrastructure Setup

### Scenario: Complete Greenfield Deployment

**Context:** Setting up entire home lab from scratch.

```bash
# Phase 1: Topology Definition
# Edit topology files in topology/ and projects/home-lab/topology/instances/

# Phase 2: Validation
task validate:passthrough

# Phase 3: Build
task build:default

# Phase 4: Create Initial Bundle
task bundle:create -- INJECT_SECRETS=true
# Note: INJECT_SECRETS for air-gapped deployment to physical nodes

# Phase 5: Check Initial Status
task deploy:init-status
# Shows all nodes as "pending"

# Phase 6: Plan All Initializations
task deploy:init-all-pending-plan -- BUNDLE=b-initial

# Phase 7: Initialize Nodes (One by One)
# Start with router (foundation)
task deploy:init-node-run -- \
  BUNDLE=b-initial \
  NODE=rtr-mikrotik-chateau

# Then hypervisor
task deploy:init-node-run -- \
  BUNDLE=b-initial \
  NODE=pve-gamayun

# Then SBC
task deploy:init-node-run -- \
  BUNDLE=b-initial \
  NODE=sbc-orangepi5

# Phase 8: Verify All Nodes
task deploy:init-status
# Should show all nodes as "initialized" or "verified"

# Phase 9: Run Full Service Chain
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-initial
```

### Scenario: Adding New Node to Existing Infrastructure

**Context:** Adding a new LXC container or VM.

```bash
# 1. Add instance definition
# Create: projects/home-lab/topology/instances/L4-platform/compute/new-lxc.yaml

# 2. Update topology references if needed
# Edit: topology/object-modules/...

# 3. Rebuild
task build:default

# 4. Create bundle
task bundle:create

# 5. Check new node appears
task bundle:inspect -- BUNDLE=b-new | jq '.manifest.nodes'

# 6. Initialize only new node
task deploy:init-node-run -- BUNDLE=b-new NODE=new-lxc

# 7. Apply Terraform/Ansible
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-new
```

---

## Node Bootstrap Scenarios

### Scenario: MikroTik Router Bootstrap (Netinstall)

**Context:** Factory reset MikroTik and bootstrap with Terraform API user.

```bash
# 1. Prepare bundle
task bundle:create

# 2. Check MikroTik node in manifest
task bundle:inspect -- BUNDLE=b-123 | \
  jq '.manifest.nodes[] | select(.mechanism == "netinstall")'

# 3. Plan initialization
task deploy:init-node-plan -- \
  BUNDLE=b-123 \
  NODE=rtr-mikrotik-chateau

# 4. Physical steps (manual):
#    a. Connect laptop to MikroTik via Ethernet
#    b. Run Netinstall tool
#    c. Factory reset router
#    d. Upload .rsc script from bundle:
#       .work/deploy/bundles/b-123/artifacts/generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc

# 5. After manual bootstrap, import existing
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=rtr-mikrotik-chateau \
  IMPORT_EXISTING=true

# 6. Verify handover (API reachable)
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=rtr-mikrotik-chateau \
  VERIFY_ONLY=true
```

### Scenario: Proxmox Host Bootstrap (Unattended Install)

**Context:** Install Proxmox with automated answer file.

```bash
# 1. Create bundle
task bundle:create

# 2. Get bootstrap artifacts
ls .work/deploy/bundles/b-123/artifacts/generated/bootstrap/pve-gamayun/
# answer.toml, post-install-minimal.sh

# 3. Physical steps (manual):
#    a. Create Proxmox USB installer
#    b. Copy answer.toml to USB
#    c. Boot from USB
#    d. Proxmox installs automatically

# 4. After installation, mark as imported
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=pve-gamayun \
  IMPORT_EXISTING=true

# 5. Run Ansible bootstrap playbook
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123
```

### Scenario: Orange Pi Bootstrap (Ansible)

**Context:** Bootstrap SBC with Ansible playbook.

```bash
# 1. Create bundle
task bundle:create

# 2. Check mechanism
task bundle:inspect -- BUNDLE=b-123 | \
  jq '.manifest.nodes[] | select(.id == "sbc-orangepi5")'
# Should show mechanism: "ansible_bootstrap"

# 3. Ensure SSH access to Orange Pi
ssh root@10.0.10.5 "hostname"

# 4. Run initialization
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=sbc-orangepi5

# 5. Verify
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=sbc-orangepi5 \
  VERIFY_ONLY=true
```

### Scenario: LXC Container Bootstrap (Cloud-Init)

**Context:** Create LXC with cloud-init user-data.

```bash
# 1. Ensure Proxmox is initialized
task deploy:init-status | jq '.by_status'

# 2. Create bundle with LXC artifacts
task bundle:create

# 3. Initialize LXC (Terraform creates it)
# LXC uses cloud_init mechanism
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=lxc-adguard

# 4. Apply full service chain
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123
```

---

## Maintenance Operations

### Scenario: Routine Maintenance Window

**Context:** Regular maintenance with Terraform/Ansible updates.

```bash
# 1. Pull latest changes
git pull

# 2. Rebuild
task build:default

# 3. Create maintenance bundle
task bundle:create

# 4. Pre-flight check
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-maint

# 5. Review changes (Terraform plan, Ansible check)
cat .work/evidence/latest/service-chain-report.yaml

# 6. Apply during maintenance window
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-maint

# 7. Verify post-maintenance
task deploy:init-status
```

### Scenario: Rolling Update Across Nodes

**Context:** Update multiple nodes one at a time.

```bash
# 1. Create bundle
task bundle:create

# 2. Update first node
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123

# 3. Verify first node
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=node1 \
  VERIFY_ONLY=true

# 4. Continue with next node (repeat 2-3 for each)
```

### Scenario: Dry Run Before Production

**Context:** Test changes without applying.

```bash
# Create bundle
task bundle:create

# Dry run (syntax/validation only)
task deploy:service-chain-evidence-dry-bundle -- BUNDLE=b-123

# Check run (Terraform plan, Ansible check)
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-123

# Review outputs before proceeding
```

---

## Emergency Procedures

### Scenario: Node Stuck in Failed State

```bash
# 1. Check current state
task deploy:init-status

# 2. Check error details
cat .work/deploy-state/home-lab/nodes/INITIALIZATION-STATE.yaml | \
  yq '.nodes[] | select(.status == "failed")'

# 3. Reset the failed node
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=failed-node \
  RESET=true \
  CONFIRM_RESET=true

# 4. Retry initialization
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=failed-node
```

### Scenario: Rollback to Previous Bundle

```bash
# 1. List available bundles
task bundle:list

# 2. Find previous known-good bundle
# Output shows bundle_id and created_at

# 3. Apply previous bundle
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-previous-good
```

### Scenario: Force Re-initialization

```bash
# When node is stuck but not in failed state
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=stuck-node \
  FORCE=true
```

### Scenario: Complete State Wipe

**CAUTION: Destroys all state history**

```bash
# 1. Backup current state
cp -r .work/deploy-state/home-lab .work/deploy-state/home-lab.backup

# 2. Remove state
rm -rf .work/deploy-state/home-lab/nodes/*
rm -rf .work/deploy-state/home-lab/logs/*

# 3. Rebuild and recreate
task build:default
task bundle:create

# 4. Import existing nodes (don't re-bootstrap)
task deploy:init-all-pending-run -- \
  BUNDLE=b-new \
  IMPORT_EXISTING=true
```

---

## CI/CD Integration

### Scenario: GitOps Validation Pipeline

```yaml
# .github/workflows/validate.yml
name: Validate Deploy Bundle

on:
  pull_request:
    paths:
      - 'topology/**'
      - 'projects/*/topology/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Validate topology
        run: task validate:passthrough

      - name: Build artifacts
        run: task build:default

      - name: Create bundle
        run: task bundle:create

      - name: Dry run
        run: task deploy:service-chain-evidence-dry-bundle -- BUNDLE=$(cat .work/deploy/latest-bundle)
```

### Scenario: Automated Deployment Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy Infrastructure

on:
  push:
    branches: [main]
    paths:
      - 'topology/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Build and bundle
        run: |
          task build:default
          task bundle:create

      - name: Deploy
        run: |
          task deploy:service-chain-evidence-apply-bundle -- \
            ALLOW_APPLY=YES \
            BUNDLE=$(cat .work/deploy/latest-bundle) \
            DEPLOY_RUNNER=remote
        env:
          SSH_PRIVATE_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
```

### Scenario: Docker-based CI

```bash
# Build toolchain image in CI
task deploy:docker-toolchain-build

# Run all operations in container
task bundle:create -- DEPLOY_RUNNER=docker
task deploy:service-chain-evidence-check-bundle -- \
  BUNDLE=b-123 \
  DEPLOY_RUNNER=docker
```

---

## Multi-Environment Workflows

### Scenario: Windows Developer Workstation

```bash
# 1. Ensure WSL is installed
wsl --install -d Ubuntu

# 2. Configure deploy profile
# projects/home-lab/deploy/deploy-profile.yaml:
default_runner: wsl
runners:
  wsl:
    distro: Ubuntu

# 3. Install tools in WSL
wsl -d Ubuntu -- bash -c "sudo apt update && sudo apt install -y terraform ansible"

# 4. Run operations (auto-uses WSL)
task bundle:create
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-123
```

### Scenario: Linux Developer Workstation

```bash
# 1. Configure native runner (usually auto-detected)
# projects/home-lab/deploy/deploy-profile.yaml:
default_runner: native

# 2. Run operations directly
task bundle:create
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123
```

### Scenario: Remote Control Node

```bash
# 1. Configure remote runner
# projects/home-lab/deploy/deploy-profile.yaml:
default_runner: remote
runners:
  remote:
    host: control.internal.lan
    user: deploy
    sync_method: rsync

# 2. Ensure SSH key is available
ssh-add ~/.ssh/deploy_key

# 3. Run operations (syncs bundle to remote)
task bundle:create
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123 \
  DEPLOY_RUNNER=remote
```

### Scenario: Air-Gapped Deployment

```bash
# On connected machine:
# 1. Create bundle with secrets
task bundle:create -- INJECT_SECRETS=true

# 2. Copy bundle to USB
cp -r .work/deploy/bundles/b-123 /media/usb/

# On air-gapped machine:
# 3. Copy bundle to local
cp -r /media/usb/b-123 .work/deploy/bundles/

# 4. Run with local bundle path
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=.work/deploy/bundles/b-123
```

---

## Cheat Sheet

### Quick Commands

```bash
# Build and bundle
task build:default && task bundle:create

# Check everything
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-123

# Apply everything
task deploy:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=b-123

# Status overview
task deploy:init-status | jq '.'

# Reset stuck node
task deploy:init-node-run -- BUNDLE=b-123 NODE=x RESET=true CONFIRM_RESET=true
```

### Common Patterns

```bash
# Full workflow
task build:default && \
task bundle:create && \
task deploy:service-chain-evidence-check-bundle -- BUNDLE=$(task bundle:list | jq -r '.bundles[-1].bundle_id')

# Initialize all pending
task deploy:init-all-pending-run -- BUNDLE=b-123

# Verify all initialized
for node in $(task deploy:init-status | jq -r '.nodes[] | select(.status == "initialized") | .id'); do
  task deploy:init-node-run -- BUNDLE=b-123 NODE=$node VERIFY_ONLY=true
done
```
