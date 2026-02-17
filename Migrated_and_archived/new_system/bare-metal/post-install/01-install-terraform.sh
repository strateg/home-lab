#!/bin/bash
# Post-Install Script 01: Install Terraform
# Proxmox VE 9 - Dell XPS L701X

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Installing Terraform${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# Terraform version
TERRAFORM_VERSION="1.7.0"

# Check if already installed
if command -v terraform &> /dev/null; then
    INSTALLED_VERSION=$(terraform version -json | jq -r '.terraform_version')
    echo -e "${GREEN}✓${NC} Terraform already installed: v${INSTALLED_VERSION}"

    if [ "$INSTALLED_VERSION" == "$TERRAFORM_VERSION" ]; then
        echo -e "${GREEN}✓${NC} Version matches, skipping installation"
        exit 0
    else
        echo -e "${YELLOW}⚠${NC} Different version detected, reinstalling..."
    fi
fi

# Install prerequisites
echo -e "${BLUE}[1/5]${NC} Installing prerequisites..."
apt-get update -qq
apt-get install -y -qq \
    gnupg \
    software-properties-common \
    curl \
    wget \
    unzip \
    jq

# Add HashiCorp GPG key
echo -e "${BLUE}[2/5]${NC} Adding HashiCorp GPG key..."
wget -O- https://apt.releases.hashicorp.com/gpg | \
    gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

# Add HashiCorp repository
echo -e "${BLUE}[3/5]${NC} Adding HashiCorp repository..."
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    tee /etc/apt/sources.list.d/hashicorp.list

# Update package list
echo -e "${BLUE}[4/5]${NC} Updating package list..."
apt-get update -qq

# Install Terraform
echo -e "${BLUE}[5/5]${NC} Installing Terraform v${TERRAFORM_VERSION}..."
apt-get install -y -qq terraform

# Verify installation
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
if terraform version; then
    echo -e "${GREEN}✓ Terraform installed successfully!${NC}"
else
    echo -e "${YELLOW}⚠ Terraform installation failed${NC}"
    exit 1
fi
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# Enable tab completion
echo -e "${BLUE}Enabling Terraform tab completion...${NC}"
terraform -install-autocomplete 2>/dev/null || true

echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Next: Run ./02-install-ansible.sh"
