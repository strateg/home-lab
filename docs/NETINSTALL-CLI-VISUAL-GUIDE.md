# NetInstall CLI Provisioning: Visual Setup Guide

## 🎯 The Goal
Automatically install `netinstall-cli` and bootstrap your MikroTik router

```
┌─────────────────────────────────────────────┐
│  Your Control Node (Laptop/Desktop/Server)  │
│                                             │
│  ✓ netinstall-cli                          │
│  ✓ Python 3                                 │
│  ✓ Terraform                                │
│  ✓ Ansible                                  │
│  ✓ curl, wget, git                          │
└──────────────┬──────────────────────────────┘
               │
               │ Bootstrap via Netinstall
               │ (all automatic)
               ▼
┌─────────────────────────────────────────────┐
│  MikroTik Chateau LTE7 ax (Router)          │
│                                             │
│  ✓ RouterOS 7.20.8                         │
│  ✓ Terraform management user                │
│  ✓ Initial configuration                    │
└─────────────────────────────────────────────┘
```

---

## 🚀 Setup Paths (Choose One)

```
┌──────────────────────────────────────────────────────────────┐
│           How to Install netinstall-cli?                     │
└──────────────────────────────────────────────────────────────┘

     ┌────────────────────────┐
     │  What's your OS?       │
     └────────────┬───────────┘
                  │
        ┌─────────┼─────────┬─────────┐
        │         │         │         │
    Linux      macOS    Windows    Docker
        │         │         │         │
        ▼         ▼         ▼         ▼
   ┌─────────┬────────┬─────────┬──────────┐
   │  apt/   │Homebrew│WSL2/    │ Docker   │
   │  yum/   │        │Docker   │ Desktop  │
   │  dnf    │        │         │          │
   └────┬────┴───┬────┴───┬─────┴─────┬────┘
        │        │        │           │
        └────────┼────────┼───────────┘
                 │        │
            ┌────┴────┬───┴────┐
            │         │        │
            ▼         ▼        ▼
        ┌──────┬─────────┬──────────┐
        │Bash  │ Ansible │  Docker  │
        │Setup │ Playbook│ Compose  │
        └──┬───┴────┬────┴────┬─────┘
           │        │         │
           ▼        ▼         ▼
    ✅ FASTEST  BEST FOR   ISOLATED
           RECOMMENDED    AUTOMATION
```

---

## 📊 Setup Method Comparison

```
╔═══════════════════════════════════════════════════════════════════╗
║                    SETUP METHOD COMPARISON                        ║
╠═══════════════════════════════════════════════════════════════════╣
║ Method        │ Speed  │ Complexity │ Best For                   ║
║───────────────┼────────┼────────────┼──────────────────────────  ║
║ Bash Script   │ ⚡⚡⚡  │ Simple     │ Most users (RECOMMENDED)   ║
║ Ansible       │ ⚡⚡   │ Medium     │ Automation/CI pipelines    ║
║ Docker        │ ⚡    │ Simple     │ Isolated environments      ║
║ Manual        │ ⏱️ ⏱️  │ Complex    │ Troubleshooting/control    ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## ⚡ Quick Start (90 seconds)

```bash
# 1. Navigate to deploy directory
cd deploy

# 2. Run ONE of these commands:

# OPTION A: Bash script (RECOMMENDED - fastest)
make setup-control-node

# OPTION B: Ansible playbook
make setup-control-node-ansible

# OPTION C: Docker
cd ../local/bootstrap
docker-compose build && docker-compose run --rm control-node

# OPTION D: Manual (if above don't work)
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
tar xzf netinstall-7.20.8.tar.gz
sudo mv netinstall /usr/local/bin/netinstall-cli
sudo chmod +x /usr/local/bin/netinstall-cli
```

---

## 🔄 Complete Bootstrap Workflow

```
STEP 1: Install netinstall-cli and tools
│
├─ Run: make setup-control-node
├─ Wait: 2-5 minutes depending on your internet
└─ Output: Shows all installed tools and versions

                    ✓ DONE
                      │
                      ▼
STEP 2: Validate prerequisites
│
├─ Run: make bootstrap-preflight RESTORE_PATH=minimal
├─ Checks:
│  ✓ netinstall-cli installed
│  ✓ Python 3 available
│  ✓ Terraform configured
│  ✓ Bootstrap scripts exist
│  ✓ RouterOS package available
└─ Output: All checks PASS

                    ✓ DONE
                      │
                      ▼
STEP 3: Prepare MikroTik hardware
│
├─ Put router in Etherboot/Netinstall mode:
│  Option 1: Hold reset button during power-up
│  Option 2: Use bootloader menu if available
├─ Get router MAC address (e.g., 00:11:22:33:44:55)
└─ Note the management network interface on control node

                    ✓ READY
                      │
                      ▼
STEP 4: Run bootstrap
│
├─ Run: make bootstrap-netinstall \
│          RESTORE_PATH=minimal \
│          MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"
├─ Watch:
│  - netinstall-cli connects to router
│  - RouterOS image flashes
│  - Initial config applies
│  - Router reboots (wait 1-2 minutes)
└─ Output: Bootstrap complete

                    ✓ DONE
                      │
                      ▼
STEP 5: Verify bootstrap success
│
├─ Run: make bootstrap-postcheck \
│          MIKROTIK_MGMT_IP="192.168.88.1" \
│          MIKROTIK_TERRAFORM_PASSWORD="terraform"
├─ Checks:
│  ✓ MikroTik API accessible
│  ✓ Terraform user configured
│  ✓ Initial config applied
└─ Output: Bootstrap verified ✓

                    ✓ DONE
                      │
                      ▼
STEP 6: Continue with full deployment
│
├─ Run: make plan         # Show what will be deployed
├─ Run: make deploy-all   # Deploy everything
└─ Output: Full infrastructure deployed

                    ✓ COMPLETE
```

---

## 🎛️ Choose Your Method

### Method 1: Bash Script (⭐ FASTEST)
```
One command:  make setup-control-node

What happens:
  1. Detects your OS automatically
  2. Downloads netinstall-cli from MikroTik
  3. Installs all dependencies
  4. Shows verification summary
  5. You're done! ✓

Platform support:
  ✓ Linux (Ubuntu, Debian, RedHat, CentOS, Fedora)
  ✓ macOS (requires Homebrew)
  ✓ Windows (WSL2 only)
```

### Method 2: Ansible Playbook
```
One command:  make setup-control-node-ansible

What happens:
  1. Runs Ansible playbook locally
  2. Installs all required packages
  3. Downloads netinstall-cli if needed
  4. Shows task-by-task output
  5. You're done! ✓

Best for:
  - Automation pipelines
  - CI/CD systems
  - Multiple machines
```

### Method 3: Docker Container
```
Two commands:
  docker-compose -f local/bootstrap/docker-compose.yml build
  docker-compose -f local/bootstrap/docker-compose.yml run --rm control-node

What happens:
  1. Builds Docker image (takes 2-3 minutes)
  2. Pre-installs all tools
  3. Mounts your project
  4. Ready to run bootstrap
  5. You're done! ✓

Best for:
  - Windows users (no WSL2 needed)
  - Complete isolation
  - Fresh machines
```

### Method 4: Manual Installation
```
For when nothing else works:

  wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
  tar xzf netinstall-7.20.8.tar.gz
  sudo mv netinstall /usr/local/bin/netinstall-cli
  sudo chmod +x /usr/local/bin/netinstall-cli

What you get:
  ✓ netinstall-cli installed

Still need to install:
  - Python 3
  - Terraform
  - Ansible
  - curl, wget, git
```

---

## 📋 What Gets Installed

```
┌────────────────────────────────────────────────┐
│           All Setup Methods Install:            │
├────────────────────────────────────────────────┤
│                                                │
│  ✓ netinstall-cli (MikroTik bootstrap tool)   │
│  ✓ Python 3.8+ (for topology-tools)           │
│  ✓ pip3 (Python package manager)              │
│  ✓ Terraform (infrastructure as code)         │
│  ✓ Ansible (configuration management)         │
│  ✓ curl (HTTP client)                         │
│  ✓ wget (file downloader)                     │
│  ✓ git (version control)                      │
│  ✓ openssh-client (SSH access)                │
│                                                │
│  Plus platform-specific:                      │
│  ✓ build-essential (Linux)                    │
│  ✓ Development headers (Linux)                │
│                                                │
└────────────────────────────────────────────────┘
```

---

## ✅ Verification Checklist

After setup, verify everything:

```bash
# 1. Check netinstall-cli
netinstall-cli --version
# Expected: netinstall-7.20.8 or similar

# 2. Check Python
python3 --version
# Expected: Python 3.8 or higher

# 3. Check Terraform
terraform version
# Expected: Terraform v1.7.0 or similar

# 4. Check Ansible
ansible --version
# Expected: ansible 2.14+ or higher

# 5. All at once:
cd deploy && make bootstrap-preflight RESTORE_PATH=minimal
# Expected: All checks PASS ✓
```

---

## 🔧 Makefile Integration

All new commands work in your existing workflow:

```bash
cd deploy

# Show all options
make help

# Setup control node (NEW)
make setup-control-node

# Or use Ansible (NEW)
make setup-control-node-ansible

# Run preflight checks (existing)
make bootstrap-preflight RESTORE_PATH=minimal

# Run bootstrap (existing, now with ready control node)
make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC="<mac>"

# Verify success (existing)
make bootstrap-postcheck MIKROTIK_MGMT_IP=192.168.88.1

# Continue with deployment (existing)
make plan
make deploy-all
```

---

## 📁 What Was Created

```
New Files:
  ✓ deploy/phases/00-bootstrap-setup-control-node.sh
  ✓ deploy/playbooks/provision-control-node.yml
  ✓ local/bootstrap/Dockerfile.control-node
  ✓ local/bootstrap/docker-compose.yml
  ✓ local/bootstrap/README.md
  ✓ docs/NETINSTALL-CLI-PROVISIONING.md
  ✓ docs/NETINSTALL-CLI-QUICK-REFERENCE.md
  ✓ docs/NETINSTALL-CLI-SETUP-OPTIONS.md
  ✓ NETINSTALL-CLI-IMPLEMENTATION-SUMMARY.md (this file's summary)

Modified Files:
  ✓ deploy/Makefile (added setup targets + help text)
```

---

## 🎯 30-Second TL;DR

```
JUST RUN THIS:

  cd deploy && make setup-control-node

THAT'S IT! Your control node is ready.

Then run bootstrap when you're ready:

  make bootstrap-netinstall RESTORE_PATH=minimal \
    MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"

Done. ✓
```

---

## 📚 Full Documentation

For detailed guides, see:
- `docs/NETINSTALL-CLI-QUICK-REFERENCE.md` - All commands at a glance
- `docs/NETINSTALL-CLI-PROVISIONING.md` - Complete 300+ line guide
- `docs/NETINSTALL-CLI-SETUP-OPTIONS.md` - Detailed method comparison
- `local/bootstrap/README.md` - Bootstrap directory overview

---

## 🎬 Start Now

Pick your method and run one command:

```bash
# Bash (FASTEST - RECOMMENDED)
cd deploy && make setup-control-node

# OR Ansible
cd deploy && make setup-control-node-ansible

# OR Docker
docker-compose -f local/bootstrap/docker-compose.yml build

# OR Manual (if above don't work)
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
tar xzf netinstall-7.20.8.tar.gz && sudo mv netinstall /usr/local/bin/netinstall-cli
```

**That's all you need to do to provision netinstall-cli! 🎉**
