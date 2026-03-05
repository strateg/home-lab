# NetInstall CLI Provisioning: Complete Setup Guide

## Quick Start (Choose One)

### Option 1: Bash Script (⚡ FASTEST - Recommended)
```bash
cd deploy
make setup-control-node
```

### Option 2: Ansible Playbook
```bash
cd deploy
make setup-control-node-ansible
```

### Option 3: Docker Container
```bash
docker-compose -f local/bootstrap/docker-compose.yml build
docker-compose -f local/bootstrap/docker-compose.yml run --rm control-node
```

### Option 4: Manual (If neither above works)
```bash
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
tar xzf netinstall-7.20.8.tar.gz
sudo mv netinstall /usr/local/bin/netinstall-cli
sudo chmod +x /usr/local/bin/netinstall-cli
```

---

## What Each Method Does

### 1. Bash Script (`deploy/phases/00-bootstrap-setup-control-node.sh`)

**Pros:**
- ✅ Single command execution
- ✅ Auto-detects OS (Linux, macOS, Windows WSL2)
- ✅ Minimal dependencies
- ✅ Shows detailed verification output
- ✅ Downloads netinstall-cli from MikroTik

**Cons:**
- Requires sudo access
- Bash/shell environment

**Execution:**
```bash
cd deploy
make setup-control-node
```

**What it installs:**
- `netinstall-cli` (from MikroTik download mirrors)
- `python3`, `pip3`
- `wget`, `curl`
- `git`
- `terraform` (optional)
- `ansible` (optional)

---

### 2. Ansible Playbook (`deploy/playbooks/provision-control-node.yml`)

**Pros:**
- ✅ Idempotent (safe to run multiple times)
- ✅ Better for automation/CI
- ✅ Works with Ansible Tower
- ✅ Detailed logging

**Cons:**
- Requires Ansible pre-installed
- Slightly slower

**Execution:**
```bash
# Via Make
cd deploy
make setup-control-node-ansible

# Or direct
ansible-playbook deploy/playbooks/provision-control-node.yml
```

**What it installs:**
- Same as bash script
- Plus: Detailed task reporting
- Can set custom variables: `-e netinstall_version=7.20.8`

---

### 3. Docker Container (`local/bootstrap/Dockerfile.control-node`)

**Pros:**
- ✅ Completely isolated environment
- ✅ No dependency pollution on host
- ✅ Reproducible across all machines
- ✅ Easy to clean up (just delete container)
- ✅ Works on Windows/macOS/Linux without WSL

**Cons:**
- Requires Docker/Docker Desktop
- Slight performance overhead

**Build:**
```bash
docker build -f local/bootstrap/Dockerfile.control-node -t home-lab:control-node .
```

**Run Interactive:**
```bash
docker run -it --rm --net=host \
  -v $(pwd):/workspace \
  home-lab:control-node \
  bash
```

**Using Docker Compose (easier):**
```bash
cd local/bootstrap
docker-compose build
docker-compose run --rm control-node
```

**Inside container:**
```bash
cd /workspace/deploy
make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"
```

---

### 4. Manual Installation

**When to use:**
- You prefer full control
- Scripting doesn't work on your system
- You want to pick specific versions

**Steps:**
```bash
# Download netinstall-cli
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz

# Extract
tar xzf netinstall-7.20.8.tar.gz

# Install
sudo mv netinstall /usr/local/bin/netinstall-cli
sudo chmod +x /usr/local/bin/netinstall-cli

# Verify
netinstall-cli --version

# Then install other tools manually:
sudo apt-get install python3 terraform ansible curl wget git
```

---

## Platform-Specific Notes

### Linux (Ubuntu/Debian)
```bash
# Option 1: Bash script (recommended)
make setup-control-node

# Option 2: Manual with apt
sudo apt-get install netinstall-cli python3 terraform ansible

# Option 3: Docker (no system packages needed)
docker run -it --rm --net=host -v $(pwd):/workspace home-lab:control-node
```

### Linux (RedHat/CentOS/Fedora)
```bash
# Bash script auto-detects and uses yum/dnf
make setup-control-node

# Or manual
sudo yum install netinstall-cli python3 terraform ansible
sudo dnf install netinstall-cli python3 terraform ansible  # Fedora
```

### macOS
```bash
# Option 1: Bash script (recommended)
# Requires Homebrew installed first: https://brew.sh
make setup-control-node

# Option 2: Manual with Homebrew
brew install terraform ansible curl wget python3
brew install mikrotik-netinstall  # If available

# Option 3: Docker Desktop
docker run -it --rm -v $(pwd):/workspace home-lab:control-node
```

### Windows (WSL2 or Git Bash)
```bash
# WSL2 (recommended - acts like Linux)
wsl bash
cd /mnt/c/path/to/project/deploy
make setup-control-node

# Docker Desktop (if WSL2 not available)
docker run -it --rm -v C:\path\to\project:/workspace home-lab:control-node
```

### Windows (Native Command Prompt)
```cmd
REM Use Docker Desktop
docker run -it --rm -v C:\path\to\project:/workspace home-lab:control-node

REM Or install via Scoop/Chocolatey
scoop install netinstall-cli terraform ansible
```

---

## Verification After Installation

### Check Installation Status
```bash
# Show all tools and versions
cd deploy
make setup-control-node  # Re-run shows status

# Or manually verify each
which netinstall-cli
which python3
which terraform
which ansible

# Get versions
netinstall-cli --version
python3 --version
terraform version
ansible --version
```

### Run Preflight Checks
```bash
cd deploy
make bootstrap-preflight RESTORE_PATH=minimal
```

This validates:
- ✓ netinstall-cli installed
- ✓ Python 3 available
- ✓ Terraform configured
- ✓ Ansible available
- ✓ Bootstrap scripts exist
- ✓ RouterOS package available

---

## Complete Bootstrap Workflow

```bash
# Step 1: Install tools
cd deploy
make setup-control-node

# Step 2: Validate prerequisites
make bootstrap-preflight RESTORE_PATH=minimal

# Step 3: Prepare MikroTik hardware
# - Put router into Etherboot/Netinstall mode
# - Get router MAC address
# - Note the control node's management network interface (eth0, en0, etc.)

# Step 4: Run bootstrap
make bootstrap-netinstall \
  RESTORE_PATH=minimal \
  MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"

# Step 5: Wait for reboot and verify
make bootstrap-postcheck \
  MIKROTIK_MGMT_IP="192.168.88.1" \
  MIKROTIK_TERRAFORM_PASSWORD_FILE="local/terraform/mikrotik/password.txt" # pragma: allowlist secret
make bootstrap-terraform-check

# Step 6: Proceed with full deployment
cd ..
make plan
make deploy-all
```

---

## Troubleshooting

### "netinstall-cli: command not found"

**Solution 1:** Check if it's installed
```bash
which netinstall-cli
# If not found, run setup again
cd deploy && make setup-control-node
```

**Solution 2:** Add to PATH manually
```bash
export PATH="/usr/local/bin:$PATH"
netinstall-cli --version
```

**Solution 3:** Check installation location
```bash
find / -name "netinstall-cli" 2>/dev/null
# Then create symlink
sudo ln -s /actual/path/netinstall /usr/local/bin/netinstall-cli
```

### "Permission denied" on bootstrap script

```bash
# Fix script permissions
chmod +x deploy/phases/00-bootstrap-*.sh

# Or use make (handles this automatically)
cd deploy && make setup-control-node
```

### Docker build fails with network timeout

```bash
# Build without netinstall-cli download (pull it separately)
DOCKER_BUILDKIT=0 docker build \
  -f local/bootstrap/Dockerfile.control-node \
  --build-arg NETINSTALL_VERSION=7.20.8 \
  -t home-lab:control-node .

# Or download netinstall-cli outside container
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
# Then manually install in container
```

### "sudo: not found" in Docker container

Docker container runs as root by default, no sudo needed:
```bash
# Don't use sudo inside container
netinstall-cli --version  # ✓ Works
sudo netinstall-cli --version  # ✗ May fail
```

### Python version mismatch

```bash
# Use python3 explicitly (not python/python2)
python3 --version  # Should be 3.8+

# Check topology-tools
cd topology-tools
python3 validate-topology.py
```

---

## Environment Variables Reference

Customize provisioning with these variables:

```bash
# Bash script
export NETINSTALL_VERSION="7.20.8"
export INSTALL_PREFIX="/usr/local/bin"
make setup-control-node

# Ansible playbook
ansible-playbook deploy/playbooks/provision-control-node.yml \
  -e "netinstall_version=7.20.8"

# Docker build
docker build \
  --build-arg TERRAFORM_VERSION=1.7.0 \
  --build-arg NETINSTALL_VERSION=7.20.8 \
  -f local/bootstrap/Dockerfile.control-node \
  -t home-lab:control-node .
```

---

## Files Created/Modified

### New Files
```
deploy/phases/00-bootstrap-setup-control-node.sh     # Bash setup script
deploy/playbooks/provision-control-node.yml          # Ansible playbook
local/bootstrap/Dockerfile.control-node               # Docker image
local/bootstrap/docker-compose.yml                    # Docker Compose config
docs/NETINSTALL-CLI-PROVISIONING.md                   # Full guide
docs/NETINSTALL-CLI-QUICK-REFERENCE.md                # Quick reference
docs/NETINSTALL-CLI-SETUP-OPTIONS.md                  # This file
```

### Modified Files
```
deploy/Makefile                                       # Added setup targets
deploy/phases/00-bootstrap.sh                         # (No changes needed)
```

---

## Next Steps

1. **Choose your method** (1 of 4 above)

2. **Run setup**
   ```bash
   # Most users: Option 1 (Bash)
   cd deploy && make setup-control-node
   ```

3. **Verify installation**
   ```bash
   cd deploy && make bootstrap-preflight RESTORE_PATH=minimal
   ```

4. **Execute bootstrap**
   ```bash
   make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC="<mac>"
   ```

5. **Continue with full deployment**
   ```bash
   make deploy-all
   ```

---

## Support & Documentation

- **Quick Reference:** `docs/NETINSTALL-CLI-QUICK-REFERENCE.md`
- **Full Guide:** `docs/NETINSTALL-CLI-PROVISIONING.md`
- **Bootstrap Info:** `make bootstrap-info`
- **Architecture Decisions:** `adr/0057-*` (ADR for netinstall bootstrap)
- **Playbook:** `deploy/playbooks/bootstrap-netinstall.yml`
- **Preflight Script:** `deploy/phases/00-bootstrap-preflight.sh`
