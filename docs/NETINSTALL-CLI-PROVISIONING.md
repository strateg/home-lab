# NetInstall CLI: Automatic Provisioning Guide

## Overview

This guide explains how to automatically provision (install/download) `netinstall-cli` for MikroTik RouterOS bootstrapping in your home-lab infrastructure.

## Table of Contents

1. [What is NetInstall CLI?](#what-is-netinstall-cli)
2. [Installation Methods](#installation-methods)
3. [Automated Provisioning](#automated-provisioning)
4. [Integration with Your Infrastructure](#integration-with-your-infrastructure)
5. [Troubleshooting](#troubleshooting)

---

## What is NetInstall CLI?

`netinstall-cli` is a command-line tool provided by MikroTik that allows you to:
- Install RouterOS from network boot (netinstall)
- Flash RouterOS images to MikroTik devices
- Apply initial bootstrap configuration scripts
- Automate day-0 provisioning of MikroTik routers

**Current version in your setup**: RouterOS 7.20.8

---

## Installation Methods

### Method 1: Manual Download

```bash
# Download from MikroTik mirrors
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz

# Extract
tar xzf netinstall-7.20.8.tar.gz
sudo mv netinstall /usr/local/bin/
sudo chmod +x /usr/local/bin/netinstall

# Or install netinstall-cli package directly (if available on your distro)
sudo apt-get install netinstall-cli  # Debian/Ubuntu
sudo yum install netinstall-cli      # RedHat/CentOS
```

### Method 2: Using Package Manager

**Linux (Debian/Ubuntu)**:
```bash
sudo apt-get update
sudo apt-get install netinstall-cli
```

**macOS**:
```bash
brew install mikrotik-netinstall  # if available
# Or download from MikroTik directly
```

**Windows**:
- Download from: https://mikrotik.com/download
- Extract to a location in your `PATH` (e.g., `C:\Program Files\netinstall\`)

---

## Automated Provisioning

### Option A: Bootstrap Integration (Recommended)

Your project already has bootstrap automation in place. The `netinstall-cli` tool should be installed on your **control node** (the machine running Ansible/Terraform).

#### Step 1: Prepare the Control Node

Create a setup script that installs all dependencies:

```bash
# File: deploy/phases/00-bootstrap-setup-control-node.sh
#!/bin/bash

set -e

echo "Setting up control node for MikroTik bootstrap..."

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    distro=$(lsb_release -si)

    if [[ "$distro" == "Ubuntu" ]] || [[ "$distro" == "Debian" ]]; then
        echo "Installing netinstall-cli on Debian/Ubuntu..."
        sudo apt-get update
        sudo apt-get install -y netinstall-cli wget curl
    fi

elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Installing netinstall-cli on macOS..."
    # Try Homebrew first
    if command -v brew &> /dev/null; then
        brew install mikrotik-netinstall 2>/dev/null || {
            echo "Brew formula not available, downloading from MikroTik..."
            install_netinstall_manual
        }
    fi
fi

# Verify installation
if command -v netinstall-cli &> /dev/null; then
    echo "✓ netinstall-cli installed successfully"
    netinstall-cli --version
else
    echo "✗ netinstall-cli installation failed"
    exit 1
fi
```

#### Step 2: Add to Makefile

Add this target to `deploy/Makefile`:

```makefile
# Control node preparation
setup-control-node:
	@echo "$(YELLOW)📦 Setting up control node for bootstrap...$(NC)"
	chmod +x $(TOPOLOGY_DIR)/deploy/phases/00-bootstrap-setup-control-node.sh
	$(TOPOLOGY_DIR)/deploy/phases/00-bootstrap-setup-control-node.sh
	@echo "$(GREEN)✓ Control node ready for bootstrap$(NC)"

bootstrap-all: bootstrap-preflight bootstrap-netinstall bootstrap-postcheck bootstrap-terraform-check
	@echo "$(GREEN)✓ Full bootstrap sequence completed$(NC)"
```

#### Step 3: Usage

```bash
cd deploy

# Install netinstall-cli and dependencies
make setup-control-node

# Run preflight checks
make bootstrap-preflight RESTORE_PATH=minimal

# Execute bootstrap
make bootstrap-netinstall \
  RESTORE_PATH=minimal \
  MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"

# Verify bootstrap success
make bootstrap-postcheck \
  MIKROTIK_MGMT_IP="192.168.88.1" \
  MIKROTIK_TERRAFORM_PASSWORD_FILE="local/terraform/mikrotik/password.txt" # pragma: allowlist secret
make bootstrap-terraform-check
```

---

### Option B: Docker Container Approach

Create a container image with all bootstrap tools pre-installed:

```dockerfile
# File: local/bootstrap/Dockerfile.control-node
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install core tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ansible \
    terraform \
    netinstall-cli \
    wget \
    curl \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy bootstrap scripts
COPY deploy/ /home/deployer/deploy/
COPY topology-tools/ /home/deployer/topology-tools/
COPY ansible/ /home/deployer/ansible/

WORKDIR /home/deployer

RUN useradd -m deployer && chown -R deployer:deployer /home/deployer

USER deployer

ENTRYPOINT ["/bin/bash"]
```

Build and use:

```bash
# Build image
docker build -f local/bootstrap/Dockerfile.control-node \
  -t home-lab:control-node .

# Run bootstrap
docker run -it --rm \
  --net=host \
  --volume $(pwd):/workspace \
  home-lab:control-node \
  /bin/bash

# Inside container:
cd /workspace/deploy
make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"
```

---

### Option C: Ansible Playbook

Create an Ansible playbook to provision the control node:

```yaml
# File: deploy/playbooks/provision-control-node.yml
---
- name: Provision Control Node for Bootstrap
  hosts: localhost
  connection: local
  become: yes

  vars:
    netinstall_version: "7.20.8"
    netinstall_arch: "x86_64"

  tasks:
    - name: Detect OS
      debug:
        msg: "OS: {{ ansible_os_family }}, Version: {{ ansible_distribution_version }}"

    - name: Install netinstall-cli (Ubuntu/Debian)
      block:
        - name: Update apt cache
          apt:
            update_cache: yes
            cache_valid_time: 3600

        - name: Install netinstall-cli package
          apt:
            name: netinstall-cli
            state: present

        - name: Install dependencies
          apt:
            name:
              - wget
              - curl
              - python3
              - python3-pip
            state: present
      when: ansible_os_family == "Debian"

    - name: Install netinstall-cli (RedHat/CentOS)
      block:
        - name: Install netinstall-cli package
          yum:
            name: netinstall-cli
            state: present

        - name: Install dependencies
          yum:
            name:
              - wget
              - curl
              - python3
              - python3-pip
            state: present
      when: ansible_os_family == "RedHat"

    - name: Install netinstall-cli (macOS)
      block:
        - name: Check if brew is installed
          command: which brew
          register: brew_installed
          ignore_errors: yes

        - name: Install via Homebrew
          shell: "brew install mikrotik-netinstall"
          when: brew_installed.rc == 0
          ignore_errors: yes

        - name: Fallback to manual download
          block:
            - name: Download netinstall tarball
              get_url:
                url: "https://download.mikrotik.com/routeros/{{ netinstall_version }}/netinstall-{{ netinstall_version }}.tar.gz"
                dest: "/tmp/netinstall-{{ netinstall_version }}.tar.gz"
                timeout: 60

            - name: Extract netinstall
              unarchive:
                src: "/tmp/netinstall-{{ netinstall_version }}.tar.gz"
                dest: /tmp
                remote_src: yes

            - name: Install netinstall-cli
              copy:
                src: "/tmp/netinstall"
                dest: "/usr/local/bin/netinstall-cli"
                mode: "0755"
                remote_src: yes

            - name: Clean up
              file:
                path: "/tmp/netinstall-{{ netinstall_version }}.tar.gz"
                state: absent
          when: brew_installed.rc != 0
      when: ansible_os_family == "Darwin"

    - name: Verify netinstall-cli installation
      command: netinstall-cli --version
      register: netinstall_version_output
      changed_when: false

    - name: Display installation result
      debug:
        msg: "netinstall-cli installed: {{ netinstall_version_output.stdout }}"
```

Usage:

```bash
# Install Ansible first if needed
sudo apt-get install ansible  # or pip3 install ansible

# Run provisioning playbook
ansible-playbook deploy/playbooks/provision-control-node.yml
```

---

## Integration with Your Infrastructure

### Step 1: Add to Generate Phase

Update `deploy/Makefile` to include control node setup in the generate phase:

```makefile
# In the 'all' target, add:
all: setup-control-node validate generate plan
```

### Step 2: Document in Bootstrap Guide

Your `deploy/phases/00-bootstrap.sh` should mention:

```bash
echo "Prerequisites check..."
if ! command -v netinstall-cli &> /dev/null; then
    echo "netinstall-cli not found. Install it:"
    echo "  cd deploy && make setup-control-node"
    exit 1
fi
```

### Step 3: Environment Variables

Define RouterOS package location in `.env.local` or topology:

```bash
# File: local/.env.bootstrap (git-ignored)
ROUTEROS_PACKAGE_URL="https://download.mikrotik.com/routeros/7.20.8/routeros-7.20.8-arm64.npk"
ROUTEROS_PACKAGE_PATH="/srv/routeros/routeros-7.20.8-arm64.npk"
NETINSTALL_TIMEOUT=300
```

Use in playbook:

```yaml
vars:
  routeros_package: "{{ lookup('env', 'ROUTEROS_PACKAGE_PATH') | default('/srv/routeros/routeros-7.20.8-arm64.npk') }}"
```

---

## Troubleshooting

### Problem: netinstall-cli not found in PATH

```bash
# Find where it's installed
which netinstall-cli

# If not in PATH, create symlink
sudo ln -s /path/to/netinstall /usr/local/bin/netinstall-cli
```

### Problem: Permission denied

```bash
# Ensure it has execute permissions
sudo chmod +x /usr/local/bin/netinstall-cli
```

### Problem: Download fails

Check network connectivity and mirror availability:

```bash
# Test connectivity
curl -I https://download.mikrotik.com/routeros/7.20.8/

# Use alternative mirror if available
wget --tries=3 --waitretry=10 https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
```

### Problem: Wrong architecture

Verify your system architecture:

```bash
uname -m  # x86_64, arm64, etc.

# Download correct version:
# - x86_64: netinstall-7.20.8.tar.gz
# - arm64:  netinstall-7.20.8-arm64.tar.gz (if available)
```

---

## Quick Reference Commands

```bash
# Install on Ubuntu/Debian
sudo apt-get install netinstall-cli

# Install on macOS
brew install mikrotik-netinstall

# Verify installation
netinstall-cli --version

# Download manually
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
tar xzf netinstall-7.20.8.tar.gz
sudo mv netinstall /usr/local/bin/netinstall-cli
sudo chmod +x /usr/local/bin/netinstall-cli

# Test netinstall (dry-run)
netinstall-cli --help

# Full bootstrap in your setup
cd deploy
make setup-control-node
make bootstrap-preflight RESTORE_PATH=minimal
make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"
make bootstrap-postcheck MIKROTIK_MGMT_IP=192.168.88.1 MIKROTIK_TERRAFORM_PASSWORD_FILE=local/terraform/mikrotik/password.txt
make bootstrap-terraform-check
```

---

## References

- [MikroTik Download Center](https://mikrotik.com/download)
- Your ADR: `adr/0057-*` (MikroTik Netinstall Bootstrap)
- Bootstrap Playbook: `deploy/playbooks/bootstrap-netinstall.yml`
- Bootstrap Phases: `deploy/phases/00-bootstrap*.sh`
- Makefile Targets: `deploy/Makefile` (bootstrap-* targets)

---

## Next Steps

1. Choose an installation method (A, B, or C above)
2. Run `make setup-control-node` to install prerequisites
3. Execute `make bootstrap-preflight` to validate everything
4. Proceed with `make bootstrap-netinstall` when ready
5. Validate handover with `make bootstrap-postcheck` and `make bootstrap-terraform-check`
