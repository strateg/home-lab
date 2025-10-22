# Migration Plan: old_system → new_system (Infrastructure-as-Data)

**Status**: In Progress
**Date**: 2025-10-22
**Version**: 1.0

## 🎯 Overview

This document tracks the migration from script-based setup (`old_system/`) to Infrastructure-as-Data approach (`new_system/`) with modular `topology.yaml`.

---

## ✅ Completed Migrations

### 1. Proxmox Installation (100% Complete)
- **Old**: Manual installation + bash scripts (`old_system/proxmox/install/`)
- **New**: Automated USB creation + auto-install (`new_system/bare-metal/`)
- **Status**: ✅ **WORKING** - `create-uefi-autoinstall-proxmox-usb.sh` successfully creates auto-installing USB
- **Remaining Issue**: UUID-based reinstall prevention (optional feature, not critical)

### 2. Network Configuration (100% Complete)
- **Old**: Bash scripts in `old_system/proxmox/scripts/configure-network.sh`
- **New**: Defined in `topology/logical.yaml` → generated Terraform in `generated/terraform/bridges.tf`
- **Status**: ✅ Complete - Bridges auto-created from topology

### 3. LXC Containers (100% Complete)
- **Old**: Bash scripts in `old_system/proxmox/scripts/install-lxc-containers.sh`
- **New**: Defined in `topology/compute.yaml` → generated Terraform in `generated/terraform/lxc.tf`
- **Status**: ✅ Complete - LXC definitions in topology, Terraform creates them

### 4. Virtual Machines (100% Complete)
- **Old**: Manual creation scripts in `old_system/proxmox/scripts/vms/`
- **New**: Defined in `topology/compute.yaml` → generated Terraform in `generated/terraform/vms.tf`
- **Status**: ✅ Complete - VM definitions in topology (OPNsense)

### 5. Service Deployment (90% Complete)
- **Old**: Individual service scripts in `old_system/proxmox/scripts/services/`
- **New**: Ansible playbooks in `new_system/ansible/playbooks/`
- **Status**: ✅ Framework ready - Ansible roles created, needs per-service playbooks

### 6. Documentation (100% Complete)
- **Old**: Scattered markdown files in multiple locations
- **New**: Organized structure in `new_system/docs/` + `bare-metal/docs/`
- **Status**: ✅ Complete - Documentation reorganized (commit cea0b53)

---

## 🔄 In Progress

### 7. Storage Configuration (80% Complete)
- **Old**: Bash scripts for storage setup
- **New**: Defined in `topology/storage.yaml`
- **Status**: ⏳ Topology defined, post-install scripts working, needs Terraform generation

### 8. Post-Install Automation (90% Complete)
- **Old**: `old_system/proxmox/scripts/proxmox-post-install.sh`
- **New**: `new_system/bare-metal/post-install/*.sh` (modular scripts)
- **Status**: ⏳ Scripts created and working, needs integration testing

---

## ❌ Not Migrated / Not Needed

### 9. OpenWrt Configuration (Obsolete)
- **Location**: `old_system/openwrt/`
- **Status**: ❌ **NOT NEEDED** - Replaced by GL.iNet Slate AX (vendor firmware)
- **Action**: Archive to `archive/old_system/openwrt/`

### 10. VPN Server Setup (Needs Decision)
- **Location**: `old_system/vpn-servers/`
- **Status**: ❓ **NEEDS REVIEW** - VPN servers on external VPS
- **Options**:
  - Keep as-is (external to home-lab)
  - Document in topology as external services
  - Archive if no longer used

---

## 📊 Migration Progress

| Component | Old System | New System | Status |
|-----------|-----------|------------|--------|
| Proxmox Install | Bash scripts | Auto-install USB | ✅ 100% |
| Network | Bash scripts | topology.yaml → Terraform | ✅ 100% |
| LXC | Bash scripts | topology.yaml → Terraform | ✅ 100% |
| VMs | Manual scripts | topology.yaml → Terraform | ✅ 100% |
| Services | Bash scripts | Ansible playbooks | ✅ 90% |
| Storage | Bash scripts | topology.yaml + post-install | ⏳ 80% |
| Documentation | Scattered | Organized docs/ | ✅ 100% |
| OpenWrt | Bash scripts | N/A (GL.iNet instead) | ❌ Obsolete |
| VPN Servers | Bash scripts | External? | ❓ Review needed |

**Overall Progress**: ~85% Complete

---

## 🧹 Cleanup Tasks

### Phase 1: Archive Outdated Scripts (Ready)
Run: `./cleanup-and-archive.sh --dry-run` (preview)
Then: `./cleanup-and-archive.sh` (execute)

**Will archive**:
- `new_system/bare-metal/create-usb.sh` (old version)
- `new_system/bare-metal/create-usb-fixed.sh` (intermediate)
- `new_system/bare-metal/create-legacy-autoinstall-proxmox-usb.sh` (not working)
- Various debug/temporary scripts (`check-usb.sh`, `fix-grub-autoinstall.sh`, etc.)
- Log files (`usb-creation-log.txt`, etc.)
- `new_system/bare-metal/docs/archive/` → move to project `archive/`

**Will keep**:
- `new_system/bare-metal/create-uefi-autoinstall-proxmox-usb.sh` ✅ (WORKING)
- `new_system/bare-metal/diagnose-usb-autoinstall.sh` ✅ (USEFUL)
- `new_system/bare-metal/run-create-usb.sh` ✅ (WRAPPER)
- `new_system/bare-metal/answer.toml` ✅ (CONFIG)
- `new_system/bare-metal/post-install/` ✅ (POST-INSTALL)

### Phase 2: Archive old_system (Ready)
Move `old_system/` → `archive/old_system/`

**Rationale**:
- All functionality replaced by Infrastructure-as-Data
- Bash scripts replaced by Terraform + Ansible
- OpenWrt setup obsolete (using GL.iNet)
- Keep in archive for reference only

---

## 📝 Remaining Tasks

### High Priority
1. ✅ ~~Fix UEFI USB auto-install~~ (COMPLETED - working!)
2. ⏳ Test full infrastructure deployment from scratch
3. ⏳ Document service-specific Ansible playbooks
4. ⏳ Complete storage Terraform generation

### Medium Priority
5. ⏳ Decide on VPN servers migration strategy
6. ⏳ Create backup/restore procedures documentation
7. ⏳ Test reinstall prevention (UUID mechanism) - currently not working but non-critical

### Low Priority
8. ⏳ Performance optimization documentation
9. ⏳ Disaster recovery procedures
10. ⏳ Monitoring setup (if not already in topology)

---

## 🚀 Next Steps

### Step 1: Run Cleanup (Today)
```bash
# Preview changes
./cleanup-and-archive.sh --dry-run

# Execute cleanup
./cleanup-and-archive.sh

# Commit
git add .
git commit -m "🧹 Cleanup: Archive outdated scripts and old_system"
git push
```

### Step 2: Verify Infrastructure (This Week)
```bash
# Validate topology
python3 new_system/scripts/validate-topology.py

# Regenerate all configs
python3 new_system/scripts/generate-terraform.py
python3 new_system/scripts/generate-ansible-inventory.py

# Test Terraform plan
cd new_system/terraform
terraform init
terraform plan  # Should show no changes or only expected changes

# Test Ansible
cd ../ansible
ansible all -i inventory/production/hosts.yml -m ping
```

### Step 3: Document Remaining Items (Next Week)
- Create service deployment guide
- Document any manual steps still required
- Update CLAUDE.md with final architecture

---

## 📚 References

- **Main Documentation**: `CLAUDE.md`
- **Topology Guide**: `TOPOLOGY-MODULAR.md`
- **USB Creation**: `new_system/docs/guides/PROXMOX-USB-AUTOINSTALL.md`
- **Bare-metal Setup**: `new_system/bare-metal/README.md`
- **Old System Archive**: `archive/old_system/` (after cleanup)

---

## 🎓 Lessons Learned

### What Worked Well
1. **Modular topology** - Splitting topology.yaml into 13 modules made it much easier to manage
2. **Infrastructure-as-Data** - Single source of truth eliminates configuration drift
3. **Auto-generated configs** - Terraform and Ansible configs generated from topology are always in sync
4. **UEFI auto-install** - Proxmox USB auto-installation works reliably

### What Needs Improvement
1. **UUID reinstall prevention** - Complex mechanism, not yet working, may not be worth the effort
2. **Documentation scattered** - Still some docs in multiple places (being cleaned up)
3. **Testing procedures** - Need more automated tests for infrastructure changes

### Key Decisions
1. ✅ Chose UEFI over Legacy BIOS (more reliable, modern)
2. ✅ Chose modular topology over monolithic (easier to maintain)
3. ✅ Chose Infrastructure-as-Data over bash scripts (reproducible, version-controlled)
4. ✅ Chose GL.iNet over OpenWrt (vendor support, easier maintenance)

---

**Last Updated**: 2025-10-22
**Next Review**: After cleanup completion
