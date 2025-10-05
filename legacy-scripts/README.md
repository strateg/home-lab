# Legacy Scripts - DO NOT USE

These scripts are **failed attempts** from development process. They are kept for reference only.

## ❌ Why These Scripts Don't Work

### ISO Rebuild Scripts
- `prepare-proxmox-usb-auto.sh`
- `prepare-proxmox-usb-auto-v2.sh`
- `prepare-proxmox-usb-hybrid.sh`

**Problem**: Rebuilding ISO with xorriso breaks the hybrid boot structure
**Result**: USB doesn't boot ("PXE ROM system not found")

### Manual GRUB Modification Scripts
- `prepare-proxmox-usb-simple-dd.sh`
- `prepare-proxmox-usb-efi-modify.sh`
- `create-proxmox-usb-simple.sh`

**Problem**: GRUB loader sources config from read-only ISO9660 partition
**Result**: Modifications don't apply, auto-install doesn't start

### GRUB Loader Replacement Scripts
- `fix-usb-grub-complete.sh`
- `fix-usb-grub-loader.sh`
- `create-proxmox-usb-complete.sh`

**Problem**: Replacing GRUB loader breaks the boot chain
**Result**: USB doesn't boot

### Non-Existent Tool Scripts
- `create-proxmox-usb-official.sh`

**Problem**: Uses `proxmox-auto-install-assistant` which doesn't exist in public repos
**Result**: Script fails with "command not found"

## ✅ Use This Instead

**`create-proxmox-usb.sh`** (in parent directory)

This is the **correct, working script** that:
- Writes ISO with `dd` (preserves boot structure)
- Adds `auto-installer.yaml` to FAT32 partition
- Uses built-in Proxmox 8+ auto-installer
- Actually works!

See `README-AUTOINSTALL.md` or `ИНСТРУКЦИЯ.md` for instructions.
