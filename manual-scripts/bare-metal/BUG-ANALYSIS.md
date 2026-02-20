# Auto-Installer Bug Analysis and Fix

## Problem Summary

Proxmox auto-installer was not activating when booting from USB. Instead, the graphical installer ran, causing:
- Wrong password hash in installed system (yescrypt instead of SHA-512)
- SSH access failed (password mismatch)
- Manual installation required

## Root Cause

**GRUB path resolution bug** in UUID protection wrapper (create-uefi-autoinstall-proxmox-usb.sh:806)

### The Bug

```grub
menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
    search --no-floppy --fs-uuid --set=root 2025-08-05-10-48-40-00
    set prefix=($root)/boot/grub              # ← BUG: This breaks file checks!
    linux $prefix/../linux26 ... proxmox-start-auto-installer
    initrd $prefix/../initrd.img
}
```

**Problem**: Setting `prefix=($root)/boot/grub` changes GRUB's working directory.

### Why It Failed

1. **GRUB boots** and loads `grub.cfg` (UUID wrapper)
2. **Wrapper sets** `prefix=($root)/boot/grub`
3. **Wrapper chains** to `grub-install.cfg`
4. **grub-install.cfg chains** to Proxmox's `boot/grub/grub.cfg`
5. **Proxmox grub.cfg checks**: `if [ -f auto-installer-mode.toml ]`
6. **File check looks** in `/boot/grub/auto-installer-mode.toml` (WRONG!)
7. **File not found** → Auto-installer menu entry NOT created
8. **Only graphical installer** menu entry exists
9. **User boots** with graphical installer
10. **Wrong password** hash gets installed

## Evidence

### Kernel Command Line (from installed system)

```bash
$ sudo journalctl --directory=/mnt/proxmox-root/var/log/journal | grep "Command line"
окт 23 14:21:23 gamayun kernel: Command line: BOOT_IMAGE=/boot/vmlinuz-6.14.8-2-pve root=/dev/mapper/pve-root ro quiet
```

**MISSING**: `proxmox-start-auto-installer` parameter

**Proves**: Auto-installer never activated.

### Password Hash Comparison

**Expected** (from answer.toml):
```
$6$c9bAqQzrLw2iQRC4$dEOmTMWdoZ20ar/IE2TQjkv3olE4jw6plQvfIFvLUcI4r.VF3R.iNuCYVvPNnoz0yQFIYxxEW8wYo4gMsjt1H1
```
Type: SHA-512 (`$6$...`) - Auto-installer

**Actual** (from /etc/shadow):
```
$y$j9T$WDwWUUJa9EhwnyS2RNMm2.$9g6q/miZQQidxmsprOzqMYsknCIIpDVWf4QBjwcc9A5
```
Type: yescrypt (`$y$...`) - Graphical installer

**Proves**: Graphical installer ran, not auto-installer.

### USB Files Verification

```bash
$ sudo mount -t iso9660 /dev/loop96 /mnt/usb-iso
$ ls -la /mnt/usb-iso/ | grep -E "answer|auto-installer"
-rw-r--r--  1 root root  1919 окт 23 18:36 answer.toml
-r--r--r--  1 root root     0 авг  5 13:48 auto-installer-capable
-rw-r--r--  1 root root    53 окт 23 18:36 auto-installer-mode.toml
```

**Proves**: Files ARE present on USB, but GRUB couldn't find them due to wrong working directory.

## The Fix (TWO PARTS!)

### Part 1: Fix AUTO-INSTALL menu in UUID wrapper (commit 91092be)

**Remove `set prefix` and use absolute paths**:

```grub
menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
    search --no-floppy --fs-uuid --set=root 2025-08-05-10-48-40-00
    # Removed: set prefix=($root)/boot/grub
    echo 'Loading Proxmox kernel with auto-installer...'
    linux ($root)/boot/linux26 ro ramdisk_size=16777216 rw splash=silent video=vesafb:ywrap,mtrr vga=791 nomodeset proxmox-start-auto-installer
    echo 'Loading initrd...'
    initrd ($root)/boot/initrd.img
}
```

**Why this works**:
- GRUB's working directory stays at ISO root (`($root)` = `/`)
- When Proxmox grub.cfg checks `if [ -f auto-installer-mode.toml ]`, it finds the file
- Auto-installer menu entry gets created
- `proxmox-start-auto-installer` parameter is passed to kernel
- Auto-installer activates correctly

### Part 2: Fix grub-install.cfg for Reinstall menu (commit 7a320de) ⭐ CRITICAL!

**The REAL problem discovered:**

UUID wrapper has TWO code paths:
1. **First install**: AUTO-INSTALL menu (fixed in Part 1)
2. **Reinstall**: "Reinstall Proxmox" menu → calls `configfile /EFI/BOOT/grub-install.cfg`

**grub-install.cfg** is the **RENAMED original Proxmox grub.cfg**! It contains:
```grub
set prefix=($root)/boot/grub  ← SAME BUG!
source ${prefix}/grub.cfg
```

**The complete chain (what actually happened):**
1. GRUB boots, loads UUID wrapper
2. Wrapper finds old installation marker (from previous install)
3. UUID matches → "system already installed"
4. Shows menu: "Boot Proxmox" / "**Reinstall Proxmox**"
5. User sees Proxmox auto-installer start immediately (no GRUB menu visible)
6. This means "Reinstall" was selected (auto-selected by timeout)
7. Reinstall calls: `configfile /EFI/BOOT/grub-install.cfg`
8. **grub-install.cfg sets `prefix=/boot/grub`** ← BUG!
9. Then loads Proxmox grub.cfg
10. Proxmox checks: `if [ -f auto-installer-mode.toml ]`
11. Looks in `/boot/grub/auto-installer-mode.toml` (WRONG!)
12. File not found → auto-installer menu NOT created
13. Graphical installer runs

**Fix applied:**
```bash
# After renaming grub.cfg → grub-install.cfg
if grep -q "^set prefix=" "$mount_point/EFI/BOOT/grub-install.cfg"; then
    sed -i '/^set prefix=/d' "$mount_point/EFI/BOOT/grub-install.cfg"
    print_success "Removed 'set prefix' from grub-install.cfg"
fi
```

**Now BOTH paths work:**
- ✅ First install: AUTO-INSTALL menu (direct boot, no prefix issue)
- ✅ Reinstall: grub-install.cfg (prefix removed, file detection works)

## Testing Plan

1. **Unmount USB** and remove from system
2. **Create new USB** with fixed script:
   ```bash
   sudo ./create-uefi-autoinstall-proxmox-usb.sh ~/Загрузки/proxmox-ve_9.0-1.iso answer.toml /dev/sdX
   ```
3. **Verify GRUB config** has no `set prefix` line:
   ```bash
   sudo mount /dev/sdX2 /mnt/usb-efi
   cat /mnt/usb-efi/efi/boot/grub.cfg | grep "prefix"
   # Should show ONLY grub-install.cfg with prefix, NOT in auto-install menu
   ```
4. **Boot from USB** on target machine
5. **Select "Install Proxmox VE (AUTO-INSTALL)"** from menu
6. **Wait for installation** to complete (should be automatic)
7. **Boot into Proxmox** and test SSH:
   ```bash
   ssh root@10.0.99.1
   # Password: proxmox (from topology/security.yaml)
   ```
8. **Verify password hash**:
   ```bash
   grep "^root:" /etc/shadow
   # Should start with $6$ (SHA-512), NOT $y$ (yescrypt)
   ```

## Files Changed

- `create-uefi-autoinstall-proxmox-usb.sh:806-810` - Removed `set prefix`, use absolute paths
- `diagnose-installation.sh` - Added diagnostic tool for post-installation analysis

## Commit

```
commit 91092be
🐛 Fix GRUB prefix issue preventing auto-installer activation
```

## FINAL SOLUTION: Modify ISO Before USB Creation

After discovering that `set prefix` fixes didn't work (GRUB still loaded HFS+ config), we found the **real root cause**:

### The Real Problem

1. **grubx64.efi** has **embedded** `prefix=/boot/grub` (cannot be changed without recompiling GRUB)
2. GRUB loads `/boot/grub/grub.cfg` from **HFS+ partition**, NOT our `/EFI/BOOT/grub.cfg`
3. HFS+ `grub.cfg` checks: `if [ -f auto-installer-mode.toml ]`
4. File is on ISO9660 layer, NOT on HFS+ partition → check fails
5. Auto-installer menu NOT created → graphical installer runs

### The Solution

**Modify Proxmox ISO `/boot/grub/grub.cfg` BEFORE writing to USB:**

1. Extract ISO with xorriso
2. Modify `/boot/grub/grub.cfg`:
   - Remove: `if [ -f auto-installer-mode.toml ]; then`
   - Make auto-installer menu **always available**
   - Set as default (option 0, timeout 10 sec)
3. Rebuild ISO with xorriso (preserves hybrid boot structure)
4. Use modified ISO for USB creation

### Implementation

**Two approaches:**

1. **Automatic (Integrated)**:
   - Added `modify_iso_for_autoinstall()` to `create-uefi-autoinstall-proxmox-usb.sh`
   - Script automatically checks if ISO needs modification
   - Modifies on first run, caches result for reuse
   - Single command: `sudo ./create-uefi-autoinstall-proxmox-usb.sh iso answer.toml /dev/sdX`

2. **Manual (Standalone)**:
   - Created `modify-proxmox-iso.sh` for manual ISO modification
   - Can be used independently for testing or batch processing
   - Usage: `sudo ./modify-proxmox-iso.sh input.iso output.iso`

### Commits

```
<to be committed>
✨ Automatic ISO modification: Enable auto-installer by default

Changes:
- Added modify_iso_for_autoinstall() function to create-uefi-autoinstall-proxmox-usb.sh
- Function extracts ISO, modifies /boot/grub/grub.cfg, rebuilds with xorriso
- Removes 'if [ -f auto-installer-mode.toml ]' check (file not on HFS+ partition)
- Makes auto-installer menu always available (default option, 10-sec timeout)
- Script automatically checks if ISO already modified (idempotent)
- Added xorriso and isoinfo to required dependencies
- Created modify-proxmox-iso.sh as standalone tool
- Created ISO-MODIFICATION-FIX.md documentation

Why this fixes the issue:
- GRUB loads config from HFS+ partition (embedded prefix=/boot/grub)
- auto-installer-mode.toml is on ISO9660 layer, not HFS+
- File check fails → auto-installer menu not created → graphical installer runs
- Solution: Modify grub.cfg to NOT check for file, enable auto-installer unconditionally

Testing:
✅ ISO modification successful (1.6G → 1.6G)
✅ Modified grub.cfg verified on HFS+ partition
✅ USB created successfully
⏳ Hardware test pending
```

## Next Steps

1. ✅ Root cause identified: GRUB loads HFS+ config, not EFI wrapper
2. ✅ Solution implemented: Modify ISO before USB creation
3. ✅ Scripts updated: Automatic ISO modification integrated
4. ✅ USB created with modified ISO
5. ⏳ Test auto-installation on target hardware
6. ⏳ Verify SSH access with password from topology

## Lessons Learned

1. **GRUB path resolution** is relative to `prefix`, not always ISO root
2. **Kernel command line** is key evidence for debugging boot issues
3. **Password hash type** (`$6$` vs `$y$`) indicates which installer ran
4. **Hybrid ISO structure** has two filesystem layers (ISO9660 whole disk + HFS+ partition)
5. **File checks in GRUB** (`if [ -f file ]`) depend on working directory
6. **GRUB prefix is embedded** in grubx64.efi and cannot be changed by renaming configs
7. **HFS+ partition is read-only** and cannot be modified after ISO creation
8. **Solution: Modify ISO source** before writing to USB, not after
