#!/bin/bash
# Post-Install Script 02: Install Ansible
# Proxmox VE 9 - Dell XPS L701X

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Installing Ansible${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# Ansible version
ANSIBLE_VERSION="2.14"

# Check if already installed
if command -v ansible &> /dev/null; then
    INSTALLED_VERSION=$(ansible --version | head -n1 | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Ansible already installed: v${INSTALLED_VERSION}"

    if [[ "$INSTALLED_VERSION" =~ ^$ANSIBLE_VERSION ]]; then
        echo -e "${GREEN}✓${NC} Version matches, skipping installation"
        exit 0
    else
        echo -e "${YELLOW}⚠${NC} Different version detected, reinstalling..."
    fi
fi

# Install Python3 and prerequisites
echo -e "${BLUE}[1/6]${NC} Installing Python3 and prerequisites..."
apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    libssl-dev \
    libffi-dev \
    build-essential \
    sshpass \
    git

# Upgrade pip
echo -e "${BLUE}[2/6]${NC} Upgrading pip..."
python3 -m pip install --upgrade pip setuptools wheel --quiet

# Install Ansible via pip
echo -e "${BLUE}[3/6]${NC} Installing Ansible core..."
python3 -m pip install ansible-core --quiet

# Install additional Python packages
echo -e "${BLUE}[4/6]${NC} Installing Python dependencies..."
python3 -m pip install \
    requests \
    jmespath \
    netaddr \
    dnspython \
    pywinrm \
    proxmoxer \
    --quiet

# Verify Ansible installation
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
if ansible --version; then
    echo -e "${GREEN}✓ Ansible installed successfully!${NC}"
else
    echo -e "${YELLOW}⚠ Ansible installation failed${NC}"
    exit 1
fi
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# Install Ansible collections
echo -e "${BLUE}[5/6]${NC} Installing Ansible collections..."

# Create temporary requirements.yml if not present
if [ ! -f /root/ansible/requirements.yml ]; then
    echo -e "${YELLOW}⚠${NC} requirements.yml not found, creating temporary one..."
    mkdir -p /root/ansible
    cat > /root/ansible/requirements.yml <<'EOF'
---
collections:
  - name: community.general
    version: ">=7.0.0"
  - name: ansible.posix
  - name: community.crypto
  - name: community.docker
  - name: community.postgresql
  - name: prometheus.prometheus

roles:
  - name: geerlingguy.postgresql
  - name: geerlingguy.redis
  - name: geerlingguy.docker
  - name: geerlingguy.nginx
EOF
fi

# Install collections from requirements.yml
ansible-galaxy collection install -r /root/ansible/requirements.yml --force

# Install roles from requirements.yml
ansible-galaxy role install -r /root/ansible/requirements.yml --force

# Display installed collections
echo -e "${BLUE}[6/6]${NC} Verifying installed collections..."
ansible-galaxy collection list

echo ""
echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Next: Run ./03-configure-storage.sh"
