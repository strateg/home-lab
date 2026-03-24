#!/bin/bash
# =============================================================================
# Phase 0: Bootstrap Instructions
# =============================================================================
# This script displays bootstrap instructions for manual setup
# Bootstrap must be completed before automated deployment can begin
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                     PHASE 0: BOOTSTRAP                               ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}Bootstrap is a manual process that prepares devices for automation.${NC}"
echo ""

echo -e "${GREEN}1. MikroTik Chateau LTE7 ax${NC}"
echo "   ───────────────────────────────────────────────────────────────────"
echo "   a) Connect to router via WinBox (192.168.88.1)"
echo "   b) Enable REST API:"
echo ""
echo "      /certificate add name=local-cert common-name=mikrotik.home.local days-valid=3650"
echo "      /ip service set www-ssl certificate=local-cert disabled=no port=8443"
echo "      /user group add name=terraform policy=api,read,write,policy,sensitive,test"
echo "      /user add name=terraform group=terraform password=YOUR_SECURE_PASSWORD"
echo ""
echo "   c) Or import bootstrap script:"
echo "      /import bootstrap/mikrotik/bootstrap.rsc"
echo ""

echo -e "${GREEN}2. Proxmox VE (Dell XPS L701X)${NC}"
echo "   ───────────────────────────────────────────────────────────────────"
echo "   a) Create bootable USB:"
echo "      cd bare-metal && sudo ./create-uefi-autoinstall-proxmox-usb.sh /dev/sdX proxmox-ve_9.0.iso"
echo ""
echo "   b) Boot from USB, installation is automatic"
echo ""
echo "   c) After reboot, run post-install scripts:"
echo "      ssh root@<proxmox-ip>"
echo "      cd /root/post-install"
echo "      ./01-install-terraform.sh"
echo "      ./02-install-ansible.sh"
echo "      ./03-configure-storage.sh"
echo "      ./04-configure-network.sh"
echo ""

echo -e "${GREEN}3. Orange Pi 5${NC}"
echo "   ───────────────────────────────────────────────────────────────────"
echo "   a) Flash Armbian to NVMe with cloud-init:"
echo "      - Download Armbian for Orange Pi 5"
echo "      - Flash to NVMe using balenaEtcher"
echo "      - Add cloud-init config to boot partition"
echo ""
echo "   b) Cloud-init handles:"
echo "      - SSH key injection"
echo "      - Network configuration"
echo "      - Docker installation"
echo ""

echo -e "${CYAN}───────────────────────────────────────────────────────────────────────${NC}"
echo ""
echo -e "${YELLOW}After completing bootstrap for all devices:${NC}"
echo ""
echo "   1. Verify connectivity:"
echo "      ping 192.168.88.1   # MikroTik"
echo "      ping 192.168.88.2   # Proxmox"
echo "      ping 192.168.88.3   # Orange Pi 5"
echo ""
echo "   2. Copy terraform.tfvars.example files and configure:"
echo "      cp generated/terraform-mikrotik/terraform.tfvars.example generated/terraform-mikrotik/terraform.tfvars"
echo "      cp generated/terraform/terraform.tfvars.example generated/terraform/terraform.tfvars"
echo ""
echo "   3. Run deployment:"
echo "      cd deploy && make deploy-all"
echo ""

echo -e "${GREEN}Bootstrap checklist:${NC}"
echo "   [ ] MikroTik REST API enabled"
echo "   [ ] Proxmox installed and post-install completed"
echo "   [ ] Orange Pi 5 booted with cloud-init"
echo "   [ ] All devices reachable via SSH"
echo "   [ ] terraform.tfvars files configured"
