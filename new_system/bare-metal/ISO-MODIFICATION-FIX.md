# ISO Modification Fix - Complete Solution

## Problem Summary

Proxmox VE 9 auto-installer was not activating when booting from USB. The graphical installer ran instead, causing:
- Wrong password hash in installed system (yescrypt instead of SHA-512)
- SSH access failures (password mismatch)
- Manual installation required instead of automated

## Root Cause

**GRUB bootloader loads configuration from HFS+ partition, not EFI partition**

1. UEFI loads `/EFI/BOOT/grubx64.efi` from EFI partition
2. `grubx64.efi` has embedded `prefix=/boot/grub`
3. GRUB loads `/boot/grub/grub.cfg` from **HFS+ partition** (not our UUID wrapper!)
4. HFS+ `grub.cfg` checks: `if [ -f auto-installer-mode.toml ]`
5. File is on ISO9660 layer, **NOT on HFS+ partition** → check fails
6. Auto-installer menu entry is **NOT created**
7. Only graphical installer menu exists → loads by default
8. Wrong password gets installed

## Solution

**Modify Proxmox ISO `/boot/grub/grub.cfg` BEFORE writing to USB**

### What We Changed

1. **Remove file check**: Delete `if [ -f auto-installer-mode.toml ]` condition
2. **Enable by default**: Make auto-installer menu always available
3. **Set as default**: Auto-installer is option 0 with 10-second timeout

### How It Works

```
Original Proxmox ISO
    ↓
modify_iso_for_autoinstall()  ← New function in create-uefi-autoinstall-proxmox-usb.sh
    ├─ Check if already modified (has "AUTO-INSTALLER ENABLED BY DEFAULT" marker)
    ├─ If not modified:
    │   ├─ Extract ISO to temp directory (xorriso)
    │   ├─ Modify /boot/grub/grub.cfg:
    │   │   ├─ Remove: if [ -f auto-installer-mode.toml ]; then
    │   │   ├─ Add: set timeout_style=menu
    │   │   ├─ Add: set timeout=10
    │   │   ├─ Add: set default=0
    │   │   └─ Add: menuentry 'Install Proxmox VE (Automated)' { ... proxmox-start-auto-installer }
    │   └─ Rebuild ISO with xorriso (preserves hybrid boot: BIOS + UEFI + HFS+)
    └─ Return path to modified ISO
    ↓
proxmox-auto-install-assistant prepare-iso  ← Existing functionality
    ├─ Embed answer.toml (password, network, disk config)
    ├─ Embed auto-installer-mode.toml (enables auto-installer)
    └─ Embed first-boot script (creates UUID marker for reinstall prevention)
    ↓
Write to USB
    └─ Add UUID wrapper in /EFI/BOOT/grub.cfg (reinstall prevention)
```

## Files Modified

### 1. `create-uefi-autoinstall-proxmox-usb.sh`

**Added:**
- `modify_iso_for_autoinstall()` function (lines 353-574)
  - Checks if ISO already modified
  - Extracts ISO with xorriso
  - Modifies `/boot/grub/grub.cfg`
  - Rebuilds ISO with correct boot parameters
  - Returns path to modified (or original if already modified) ISO

**Modified:**
- `check_requirements()` - Added `xorriso` and `isoinfo` dependencies
- `main()` - Added Step 1 before prepare_iso: Modify ISO if needed
- Script header - Updated Features and How it works sections

### 2. New Files Created

**`modify-proxmox-iso.sh`** (standalone version)
- Standalone script for manual ISO modification
- Can be used independently of USB creation
- Useful for testing or creating modified ISOs for later use

**`ISO-MODIFICATION-FIX.md`** (this file)
- Complete documentation of the problem and solution

## Testing Checklist

- [x] ISO modification works (xorriso rebuild successful)
- [x] Modified ISO boots correctly
- [x] Auto-installer menu appears by default
- [x] Auto-installer activates automatically (10-sec timeout)
- [ ] Installation completes successfully
- [ ] SSH access works with password from topology/security.yaml
- [ ] Password hash in /etc/shadow is SHA-512 (not yescrypt)
- [ ] UUID marker created in /etc/proxmox-install-id and /boot/efi/proxmox-installed
- [ ] Second boot from same USB shows "Boot Installed" menu (reinstall prevention)

## Usage

### Automatic (Recommended)

```bash
cd new_system/bare-metal

# Script now automatically modifies ISO if needed
sudo ./create-uefi-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdX

# Process:
# 1. Check if ISO needs modification
# 2. If yes: modify /boot/grub/grub.cfg to enable auto-installer by default
# 3. Embed answer.toml with proxmox-auto-install-assistant
# 4. Create USB with UUID wrapper
```

### Manual ISO Modification (Optional)

```bash
# If you want to modify ISO separately and reuse it
sudo ./modify-proxmox-iso.sh ~/Downloads/proxmox-ve_9.0-1.iso ~/Downloads/proxmox-ve_9.0-1-autoinstall.iso

# Then use modified ISO with main script
sudo ./create-uefi-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1-autoinstall.iso answer.toml /dev/sdX
```

## Benefits

✅ **Single command**: Just run create-uefi-autoinstall-proxmox-usb.sh as before
✅ **Automatic detection**: Script checks if ISO already modified (idempotent)
✅ **No manual steps**: ISO modification happens automatically
✅ **Caching**: Modified ISO saved, can be reused for multiple USBs
✅ **Backward compatible**: Works with both original and pre-modified ISOs

## Technical Details

### Why HFS+ Partition?

Proxmox ISO is a hybrid ISO with multiple filesystem layers:
- **ISO9660**: Whole disk (contains all files including auto-installer data)
- **HFS+**: Partition 3 (contains installer core files, READ-ONLY)
- **EFI**: Partition 2 (contains bootloader)

GRUB bootloader (`grubx64.efi`) has embedded `prefix=/boot/grub`, which points to HFS+ partition.

### Why File Check Failed?

`proxmox-auto-install-assistant` embeds files on **ISO9660 layer** (whole disk).
GRUB loads config from **HFS+ partition** and checks for files there.
Files are NOT on HFS+ → check fails → auto-installer disabled.

### Why Not Copy Files to HFS+?

HFS+ partition is:
- **Read-only** (filesystem marked as locked)
- **No free space** (allocation file full)
- **Cannot be modified** after ISO creation

**Solution**: Modify grub.cfg to NOT check for files, enable auto-installer unconditionally.

## Commits

1. `modify-proxmox-iso.sh` - Standalone ISO modification script
2. `create-uefi-autoinstall-proxmox-usb.sh` - Integrated ISO modification
3. `ISO-MODIFICATION-FIX.md` - Complete documentation

## Next Steps

1. ✅ ISO modification implemented and integrated
2. ✅ USB created with modified ISO
3. ⏳ Test auto-installation on target hardware
4. ⏳ Verify SSH access with password from topology
5. ⏳ Confirm reinstall prevention works
