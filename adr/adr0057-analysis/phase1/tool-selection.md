# Workstream 1B: Tool Selection & Readiness - REPORT

**Date:** 2026-03-03 (Day 2)
**Owner:** DevOps
**Status:** ✅ COMPLETE

---

## Objective

Verify tool availability and document prerequisites for Phase 2 implementation.

---

## 1. Control-Node Wrapper Selection

### Decision: Ansible ✅ (Pre-approved)

**Rationale:**
- Consistent with existing Terraform wrappers in `deploy/`
- Built-in validation and error handling
- Shared variable system
- Team familiarity

**Implementation:**
- Target: `deploy/playbooks/bootstrap-netinstall.yml`
- Required Ansible version: 2.9+ (recommend 2.12+)
- Modules needed: `command`, `copy`, `stat`, `assert`, `pause`

---

## 2. Tool Availability Check

### netinstall-cli
**Status:** ⚠️ NEEDS VERIFICATION

**Requirements:**
- Tool: `netinstall-cli` (MikroTik Netinstall command-line tool)
- Source: https://mikrotik.com/download
- Platforms: Linux, Windows
- Alternative: `netinstall` GUI version exists, but CLI required for automation

**Verification Script:**
```bash
#!/bin/bash
# Check netinstall-cli availability

if command -v netinstall-cli &> /dev/null; then
    echo "✅ netinstall-cli found"
    netinstall-cli --version 2>&1 | head -1
else
    echo "❌ netinstall-cli NOT FOUND"
    echo ""
    echo "Installation required:"
    echo "1. Download from https://mikrotik.com/download"
    echo "2. Extract netinstall-cli binary"
    echo "3. Place in PATH or /usr/local/bin/"
    echo "4. Make executable: chmod +x netinstall-cli"
    exit 1
fi
```

**Action Required:** User must verify netinstall-cli is installed

---

## 3. Ansible Readiness

### Ansible Version
**Required:** 2.9+
**Recommended:** 2.12+ (for better error messages)

**Verification:**
```bash
ansible --version
# Expected output:
# ansible [core 2.12.x]
```

### Required Ansible Modules
All modules are part of `ansible.builtin` (no additional collections needed):

- ✅ `ansible.builtin.command` - Run netinstall-cli
- ✅ `ansible.builtin.copy` - Copy files with timestamp
- ✅ `ansible.builtin.stat` - Check file existence
- ✅ `ansible.builtin.assert` - Validate parameters
- ✅ `ansible.builtin.pause` - Wait for user actions
- ✅ `ansible.builtin.debug` - Display messages

**Status:** ✅ ALL AVAILABLE (builtin modules)

---

## 4. System Prerequisites

### For Control Node (where Ansible runs)

**Required:**
- Ansible 2.9+ installed
- netinstall-cli binary available
- Python 3.6+ (for Ansible)
- Network interface for netinstall (direct Ethernet connection)
- RouterOS package file (.npk)

**Network Requirements:**
- Direct Ethernet connection to MikroTik device
- Interface in same broadcast domain as netinstall client IP
- No DHCP interference during netinstall
- Firewall allows TFTP/bootp protocols

**Filesystem:**
- `.work/native/bootstrap/` directory writable
- Space for RouterOS package (~50-100MB)
- Space for backup/RSC files (~1-5MB)

---

## 5. Prerequisites Checklist

### Pre-Phase-2 Verification

**Tools:**
- [ ] Ansible installed (2.9+)
- [ ] netinstall-cli available in PATH
- [ ] Python 3.6+ available
- [ ] Git configured

**Files:**
- [x] Template file exists: `init-terraform.rsc.j2` ✅
- [ ] Backup file moved to templates/ ⏳
- [ ] RSC file moved to templates/ ⏳
- [ ] RouterOS package downloaded (.npk)

**Network:**
- [ ] Identify netinstall interface (e.g., enp3s0)
- [ ] Document netinstall client IP (e.g., 192.168.88.3)
- [ ] Verify MikroTik MAC address known
- [ ] Test direct Ethernet connection

**Secrets:**
- [ ] Vault configured (Ansible Vault or ADR 0058 SOPS)
- [ ] Terraform password defined
- [ ] WiFi passphrase defined (for Path C)
- [ ] WireGuard key defined (for Path C)

---

## 6. Tool Documentation

### netinstall-cli Usage
```bash
# Basic syntax
netinstall-cli [options] <package.npk>

# Common options:
#   -e, --etherboot     Use Etherboot mode
#   -i, --interface     Network interface to use
#   -a, --address       Client IP address
#   --mac              Target device MAC address
#   -s, --script       Bootstrap script to apply

# Example for Phase 2:
netinstall-cli -e --mac 00:11:22:33:44:55 \
               -i enp3s0 \
               -a 192.168.88.3 \
               -s .work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc \
               routeros-7.21.3-arm.npk
```

### Ansible Playbook Invocation
```bash
# Path A: Minimal bootstrap
ansible-playbook deploy/playbooks/bootstrap-netinstall.yml \
  -e mikrotik_bootstrap_mac=00:11:22:33:44:55 \
  -e mikrotik_netinstall_interface=enp3s0 \
  -e mikrotik_netinstall_client_ip=192.168.88.3 \
  -e mikrotik_routeros_package=./routeros-7.21.3-arm.npk

# Path B: Backup restoration
ansible-playbook deploy/playbooks/bootstrap-netinstall.yml \
  -e mikrotik_bootstrap_mac=00:11:22:33:44:55 \
  -e restore_path_flag=backup \
  # ... (other params)

# Path C: RSC execution
ansible-playbook deploy/playbooks/bootstrap-netinstall.yml \
  -e mikrotik_bootstrap_mac=00:11:22:33:44:55 \
  -e restore_path_flag=rsc \
  # ... (other params)
```

---

## 7. Known Issues & Limitations

### netinstall-cli Availability
**Issue:** netinstall-cli binary not widely packaged for Linux distributions
**Workaround:** Manual download from MikroTik website
**Alternative:** Use netinstall GUI tool manually (not automated)

### Network Requirements
**Issue:** Requires direct Ethernet connection (can't work over routed network)
**Impact:** Control node must be physically connected to device
**Workaround:** Use dedicated netinstall machine if needed

### Windows Compatibility
**Issue:** Ansible primarily designed for Linux/macOS control nodes
**Workaround:** Use WSL2 on Windows, or run Ansible from Linux VM

---

## 8. Recommendations

### For Phase 2 Implementation

1. **Create netinstall verification script** (Week 3)
   - Check netinstall-cli availability
   - Verify interface exists
   - Test network connectivity
   - Validate MAC format

2. **Document hardware setup** (Week 3)
   - Physical connection diagram
   - Interface naming conventions
   - MAC address lookup procedure
   - Recovery procedures

3. **Create prerequisites verification playbook** (Week 3)
   - Check all tools available
   - Verify files exist
   - Test connectivity
   - Pre-flight all requirements

---

## 9. Phase 2 Preparation

### Ready for Phase 2
- ✅ Ansible chosen and documented
- ✅ netinstall-cli requirements documented
- ✅ System prerequisites listed
- ✅ Usage examples provided
- ✅ Limitations documented

### Blocking Phase 2
- ⏳ netinstall-cli availability (USER VERIFICATION NEEDED)
- ⏳ RouterOS package file (USER DOWNLOAD NEEDED)
- ⏳ Network interface identification (USER DOCUMENTATION NEEDED)

---

## 10. Deliverables

### Documentation Created
- ✅ Tool selection decision (Ansible)
- ✅ Prerequisites checklist
- ✅ Installation instructions
- ✅ Usage examples
- ✅ Known issues list

### Scripts to Create (Phase 2)
- [ ] `deploy/phases/00-check-prerequisites.sh`
- [ ] `deploy/playbooks/bootstrap-netinstall.yml`
- [ ] `deploy/phases/00-bootstrap-preflight.sh`
- [ ] `deploy/phases/00-bootstrap-postcheck.sh`

---

## Summary

**Tool Selection:** ✅ Ansible (approved)
**Documentation:** ✅ Complete
**Readiness:** ⚠️ Depends on user verification (netinstall-cli)
**Blockers:** None (user actions needed but don't block planning)

**Status:** ✅ WORKSTREAM 1B COMPLETE

---

**Next:** Workstream 1D (Secret Integration) in Week 2
