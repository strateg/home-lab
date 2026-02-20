#!/bin/bash
# Post-Install Script 05: Initialize Git Repository
# Proxmox VE 9 - Dell XPS L701X
# Setup Git for Infrastructure as Code management

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Initializing Git Repository${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# Project directory
PROJECT_DIR="/root/home-lab"

# ============================================================
# Check if Git is installed
# ============================================================

echo -e "${BLUE}[1/6]${NC} Checking Git installation..."

if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} Git not found, installing..."
    apt-get update -qq
    apt-get install -y -qq git
fi

GIT_VERSION=$(git --version | awk '{print $3}')
echo -e "${GREEN}✓${NC} Git installed: v${GIT_VERSION}"

# ============================================================
# Configure Git user
# ============================================================

echo ""
echo -e "${BLUE}[2/6]${NC} Configuring Git user..."

# Check if Git user is configured
if ! git config --global user.name &> /dev/null; then
    echo "Enter your Git username (e.g., 'Home Lab Admin'):"
    read -r git_username
    git config --global user.name "$git_username"
fi

if ! git config --global user.email &> /dev/null; then
    echo "Enter your Git email (e.g., 'admin@home.local'):"
    read -r git_email
    git config --global user.email "$git_email"
fi

echo -e "${GREEN}✓${NC} Git user configured:"
echo "  Name: $(git config --global user.name)"
echo "  Email: $(git config --global user.email)"

# Configure Git defaults
git config --global init.defaultBranch main
git config --global core.editor vim
git config --global pull.rebase false

# ============================================================
# Create project directory
# ============================================================

echo ""
echo -e "${BLUE}[3/6]${NC} Creating project directory..."

if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p "$PROJECT_DIR"
    echo -e "${GREEN}✓${NC} Project directory created: $PROJECT_DIR"
else
    echo -e "${GREEN}✓${NC} Project directory exists: $PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# ============================================================
# Initialize Git repository
# ============================================================

echo ""
echo -e "${BLUE}[4/6]${NC} Initializing Git repository..."

if [ ! -d ".git" ]; then
    git init
    echo -e "${GREEN}✓${NC} Git repository initialized"
else
    echo -e "${GREEN}✓${NC} Git repository already initialized"
fi

# ============================================================
# Create .gitignore
# ============================================================

echo ""
echo -e "${BLUE}[5/6]${NC} Creating .gitignore..."

cat > .gitignore <<'EOF'
# Infrastructure as Code - Home Lab
# Git Ignore Configuration

# ============================================================
# Terraform
# ============================================================

# State files
*.tfstate
*.tfstate.*
*.tfstate.backup

# Variable files (may contain secrets)
*.tfvars
*.tfvars.json
terraform.tfvars
!terraform.tfvars.example

# Crash logs
crash.log

# Terraform directories
.terraform/
.terraform.lock.hcl

# Override files
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# ============================================================
# Ansible
# ============================================================

# Vault password files
.vault_pass
.vault_password
vault_pass.txt

# Inventory files with secrets
inventory/production/host_vars/*
!inventory/production/host_vars/.gitkeep
inventory/production/group_vars/vault.yml

# Retry files
*.retry

# Ansible Galaxy
.galaxy_install_info

# ============================================================
# Proxmox & VMs
# ============================================================

# ISO images
*.iso

# VM disk images
*.qcow2
*.raw
*.vmdk

# Templates
*.ova
*.ovf

# Backups
backups/
*.vma
*.tar
*.tar.gz
*.tar.zst

# ============================================================
# SSH & Secrets
# ============================================================

# SSH keys
*.pem
*.key
id_rsa*
id_ed25519*

# Certificate files
*.crt
*.csr
*.p12
*.pfx

# Password files
passwords.txt
secrets.txt
credentials.txt

# Environment files
.env
.env.local

# ============================================================
# Logs & Temp Files
# ============================================================

# Log files
*.log
logs/

# Temporary files
*.tmp
*.temp
*.swp
*.swo
*~

# Cache
.cache/
__pycache__/
*.pyc

# ============================================================
# IDE & Editor
# ============================================================

# VSCode
.vscode/

# JetBrains IDEs
.idea/

# Sublime Text
*.sublime-project
*.sublime-workspace

# Vim
.vim/
*.vim

# ============================================================
# OS
# ============================================================

# macOS
.DS_Store
.AppleDouble
.LSOverride

# Linux
.Trash-*

# Windows
Thumbs.db
desktop.ini

# ============================================================
# Project Specific
# ============================================================

# Documentation builds
docs/_build/

# Test outputs
test-results/

# Keep directory structure
!.gitkeep
EOF

echo -e "${GREEN}✓${NC} .gitignore created"

# ============================================================
# Create initial commit
# ============================================================

echo ""
echo -e "${BLUE}[6/6]${NC} Creating initial commit..."

# Check if there's already a commit
if ! git rev-parse HEAD &> /dev/null; then
    # Create .gitkeep files for empty directories
    mkdir -p terraform/modules
    mkdir -p ansible/roles
    mkdir -p ansible/playbooks
    mkdir -p ansible/inventory/production/host_vars
    mkdir -p ansible/inventory/production/group_vars
    mkdir -p manual-scripts/bare-metal/post-install
    mkdir -p docs

    touch terraform/modules/.gitkeep
    touch ansible/playbooks/.gitkeep
    touch ansible/inventory/production/host_vars/.gitkeep
    touch docs/.gitkeep

    # Add files to Git
    git add .gitignore
    git add terraform/
    git add ansible/
    git add manual-scripts/bare-metal/
    git add docs/

    # Create initial commit
    git commit -m "Initial commit: Infrastructure as Code setup

- Added .gitignore for Terraform, Ansible, secrets
- Created directory structure for IaC
- Prepared for Terraform and Ansible configuration"

    echo -e "${GREEN}✓${NC} Initial commit created"
else
    echo -e "${GREEN}✓${NC} Repository already has commits"
fi

# ============================================================
# Display repository status
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Git Repository Status:${NC}"
echo ""
git status
echo ""
echo -e "${GREEN}Recent commits:${NC}"
git log --oneline --decorate --graph -n 5 2>/dev/null || echo "No commits yet"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"

# ============================================================
# Setup remote repository (optional)
# ============================================================

echo ""
echo -e "${BLUE}Setup remote Git repository?${NC}"
echo ""
echo "Options:"
echo "  1) GitHub"
echo "  2) GitLab"
echo "  3) Gitea (self-hosted)"
echo "  4) Skip (setup later)"
echo ""
echo "Enter choice [1-4]:"
read -r remote_choice

case $remote_choice in
    1|2|3)
        echo ""
        echo "Enter remote repository URL (e.g., git@github.com:user/home-lab.git):"
        read -r remote_url

        if [ -n "$remote_url" ]; then
            # Add remote
            if git remote | grep -q origin; then
                git remote set-url origin "$remote_url"
            else
                git remote add origin "$remote_url"
            fi

            echo -e "${GREEN}✓${NC} Remote repository configured: $remote_url"
            echo ""
            echo "Push to remote with:"
            echo "  git push -u origin main"
        fi
        ;;
    4)
        echo -e "${YELLOW}⚠${NC} Remote repository setup skipped"
        echo "You can add remote later with:"
        echo "  git remote add origin <repository-url>"
        ;;
    *)
        echo -e "${RED}✗${NC} Invalid choice, skipping remote setup"
        ;;
esac

# ============================================================
# Display next steps
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Git repository initialized successfully!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. ${BLUE}Copy Infrastructure as Code files to repository:${NC}"
echo "   scp -r ~/workspaces/projects/home-lab/* root@<proxmox-ip>:$PROJECT_DIR/"
echo ""
echo "2. ${BLUE}Configure Terraform:${NC}"
echo "   cd $PROJECT_DIR/terraform"
echo "   cp terraform.tfvars.example terraform.tfvars"
echo "   vim terraform.tfvars  # Configure your settings"
echo "   terraform init"
echo "   terraform plan"
echo ""
echo "3. ${BLUE}Configure Ansible:${NC}"
echo "   cd $PROJECT_DIR/ansible"
echo "   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml"
echo ""
echo "4. ${BLUE}Version control:${NC}"
echo "   git add ."
echo "   git commit -m 'Add IaC configuration'"
echo "   git push origin main"
echo ""
echo -e "${GREEN}Post-installation complete!${NC}"
echo ""
echo "Access Proxmox Web UI:"
echo "  https://10.0.99.1:8006"
echo ""
