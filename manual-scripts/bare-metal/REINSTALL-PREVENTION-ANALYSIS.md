# Reinstall Prevention System - Complete Analysis

## Overview

UUID-based reinstall prevention prevents accidental reinstallation when booting from the same USB after successful Proxmox installation.

## Components

### 1. Installation UUID Generation

**When**: Before ISO preparation (create-uefi-autoinstall-proxmox-usb.sh:1074-1078)

```bash
timezone=$(date +%Z)
timestamp=$(date +%Y_%m_%d_%H_%M)
INSTALL_UUID="${timezone}_${timestamp}"  # Example: EEST_2025_10_24_07_36
```

**Format**: `{TIMEZONE}_{YYYY}_{MM}_{DD}_{HH}_{MM}`

**Purpose**: Unique identifier for each USB creation, used to match USB with installed system.

### 2. First-Boot Script

**What**: Bash script embedded in ISO by `proxmox-auto-install-assistant`

**Runs**: After Proxmox installation completes, before first reboot

**Location in ISO**: `/proxmox-first-boot` (embedded by auto-install-assistant)

**What it does** (create-uefi-autoinstall-proxmox-usb.sh:280-343):

```bash
#!/bin/bash
# Runs after installation, creates UUID marker

INSTALL_ID="EEST_2025_10_24_07_36"  # Embedded at USB creation

# 1. Save UUID to system root
echo -n "$INSTALL_ID" > /etc/proxmox-install-id

# 2. Find EFI partition on INSTALLED DISK (not USB!)
# Checks: /efi, /boot/efi, or searches root device partitions

# 3. Write UUID marker to EFI partition
echo -n "$INSTALL_ID" > "$EFI_MOUNT/proxmox-installed"
# File: /efi/proxmox-installed or /boot/efi/proxmox-installed
```

**Key Logic**:
- Searches for EFI partition **on the same disk as root** (not USB!)
- Uses `findmnt` to find root device
- Scans partitions of root device for vfat filesystem (EFI)
- Creates marker: `/efi/proxmox-installed` containing UUID

**Logs**: `/var/log/proxmox-first-boot.log`

### 3. GRUB UUID Wrapper

**Location**: `/EFI/BOOT/grub.cfg` on USB EFI partition

**Runs**: On every boot from USB, BEFORE loading Proxmox installer

**Logic** (create-uefi-autoinstall-proxmox-usb.sh:689-823):

```grub
# 1. Embedded USB UUID
set usb_uuid="EEST_2025_10_24_07_36"

# 2. Search for marker on system disk
# Checks 4 locations:
#   - (hd1,gpt2)/proxmox-installed  ← Most common
#   - (hd1,gpt1)/proxmox-installed
#   - (hd0,gpt2)/proxmox-installed  ← Fallback if USB is hd1
#   - (hd0,gpt1)/proxmox-installed

# 3. Read UUID from marker file
if [ -f (hd1,gpt2)/proxmox-installed ]; then
    cat --set=disk_uuid (hd1,gpt2)/proxmox-installed

    # 4. Compare with USB UUID
    if [ "$disk_uuid" = "$usb_uuid" ]; then
        set found_system=1
        # Installed system matches THIS USB
    fi
fi

# 5. Decision Logic
if [ $found_system -eq 1 ]; then
    # UUID MATCH - System installed with THIS USB

    menuentry 'Boot Proxmox VE (Already Installed)' {
        # Default option (timeout=5, default=0)
        chainloader (hd1,gpt2)/EFI/proxmox/grubx64.efi
    }

    menuentry 'Reinstall Proxmox (ERASES ALL DATA!)' {
        # Manual reinstall option
        configfile /EFI/BOOT/grub-install.cfg
    }
else
    # NO MATCH - First install or different USB

    menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
        # Default option (timeout=5, default=0)
        linux ($root)/boot/linux26 ... proxmox-start-auto-installer
        initrd ($root)/boot/initrd.img
    }

    menuentry 'Install Proxmox VE (Manual - use if auto fails)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
fi
```

## Flow Diagram

```
USB Creation
    │
    ├─ Generate UUID: EEST_2025_10_24_07_36
    ├─ Embed UUID in first-boot script
    ├─ Embed UUID in GRUB wrapper
    └─ Create USB
        │
        ▼
First Boot from USB
    │
    ├─ GRUB loads UUID wrapper
    ├─ Searches for /proxmox-installed on hd0/hd1
    ├─ NOT FOUND → Show "Install" menu
    ├─ User boots → Auto-installer runs
    └─ Proxmox installs
        │
        ▼
During Installation
    │
    └─ proxmox-auto-install-assistant runs
        │
        └─ Executes first-boot script AFTER installation
            │
            ├─ Creates /etc/proxmox-install-id
            ├─ Finds EFI partition on installed disk
            └─ Writes /efi/proxmox-installed with UUID
        │
        ▼
Second Boot from USB (after installation)
    │
    ├─ GRUB loads UUID wrapper
    ├─ Searches for /proxmox-installed on hd0/hd1
    ├─ FOUND! Reads UUID: EEST_2025_10_24_07_36
    ├─ Compares with USB UUID: EEST_2025_10_24_07_36
    ├─ MATCH! → Show "Boot Installed" menu
    ├─ Default: Boot Proxmox (timeout 5 sec)
    └─ Manual: Reinstall option available
```

## Disk Naming Logic

### Why hd0 and hd1?

GRUB disk naming is **boot-order dependent**:
- **hd0** = First disk in BIOS boot order
- **hd1** = Second disk in BIOS boot order

**Problem**: Boot order varies by BIOS/firmware!

**Scenarios**:

| BIOS Boot Order | hd0 | hd1 |
|---|---|---|
| Scenario A: SSD first, USB second | SSD | USB |
| Scenario B: USB first, SSD second | USB | SSD |

**Solution**: Check **BOTH** hd0 and hd1 for marker file!

### Why gpt1 and gpt2?

EFI partition can be at **different partition numbers**:
- **gpt1**: First partition (some systems)
- **gpt2**: Second partition (most common - after BIOS boot partition)

**Solution**: Check **BOTH** gpt1 and gpt2!

### Complete Search Matrix

The wrapper checks **4 combinations**:

| Disk | Partition | Scenario |
|---|---|---|
| hd1,gpt2 | Most common | USB is hd0, SSD is hd1, EFI is 2nd partition |
| hd1,gpt1 | Less common | USB is hd0, SSD is hd1, EFI is 1st partition |
| hd0,gpt2 | Fallback | USB is hd1, SSD is hd0, EFI is 2nd partition |
| hd0,gpt1 | Fallback | USB is hd1, SSD is hd0, EFI is 1st partition |

**First match wins** → sets `found_system=1`

## Security Considerations

### Attack Scenarios

1. **Accidental reinstall**: ✅ Prevented (UUID check)
2. **Different USB reinstall**: ✅ Allowed (UUID mismatch)
3. **Manual reinstall from same USB**: ✅ Allowed (menu option)
4. **EFI partition erasure**: ✅ Safe (marker lost → allows reinstall)

### Bypass Methods

1. **Skip UUID protection at USB creation**:
   ```bash
   SKIP_UUID_PROTECTION=1 ./create-uefi-autoinstall-proxmox-usb.sh ...
   ```

2. **Delete marker from EFI partition**:
   ```bash
   mount /boot/efi
   rm /boot/efi/proxmox-installed
   ```

3. **Select "Reinstall" from GRUB menu** (if UUID matched)

## Known Issues & Edge Cases

### Issue 1: Filesystem Corruption

**Symptom**: Marker exists but filesystem corrupted

**Impact**: GRUB shows "Boot Installed" menu, but boot fails

**Mitigation**: "Reinstall" menu option available

### Issue 2: EFI Partition Not Found by First-Boot Script

**Cause**: Non-standard partition layout

**Impact**: Marker not created → reinstall allowed on next boot

**Detection**: Check `/var/log/proxmox-first-boot.log` for errors

**Fix**: Manually create marker:
```bash
echo "EEST_2025_10_24_07_36" > /boot/efi/proxmox-installed
```

### Issue 3: GRUB Can't Read Marker (Different Filesystem)

**Cause**: EFI partition not vfat (e.g., ext4)

**Impact**: Marker exists but GRUB can't read it

**Probability**: Very low (EFI spec requires vfat)

### Issue 4: System Disk Changed

**Scenario**: User moves SSD to different machine

**Impact**: New machine has no marker → reinstall allowed

**Expected**: Correct behavior (new hardware)

## Disable UUID Protection

**When needed**:
- Testing/development
- Intentional repeated reinstalls
- CI/CD automated testing

**How**:
```bash
SKIP_UUID_PROTECTION=1 ./create-uefi-autoinstall-proxmox-usb.sh iso answer.toml /dev/sdX
```

**WARNING**: USB will ALWAYS reinstall on boot (no protection!)

## Debugging

### Check if marker was created:

```bash
# On installed Proxmox system
cat /etc/proxmox-install-id
cat /boot/efi/proxmox-installed
cat /efi/proxmox-installed  # Alternative location
```

### Check first-boot script execution:

```bash
cat /var/log/proxmox-first-boot.log
```

### Check GRUB wrapper UUID:

```bash
# Mount USB EFI partition
sudo mount /dev/sdX2 /mnt
grep "set usb_uuid" /mnt/EFI/BOOT/grub.cfg
```

### Test UUID matching manually:

```bash
# On Proxmox system
INSTALL_ID=$(cat /boot/efi/proxmox-installed)
USB_UUID="EEST_2025_10_24_07_36"

if [ "$INSTALL_ID" = "$USB_UUID" ]; then
    echo "UUIDs MATCH - Reinstall prevention active"
else
    echo "UUIDs DON'T MATCH - Reinstall allowed"
fi
```

## Implementation Files

| Component | File | Lines |
|---|---|---|
| UUID Generation | create-uefi-autoinstall-proxmox-usb.sh | 1074-1078 |
| First-Boot Script Template | create-uefi-autoinstall-proxmox-usb.sh | 269-351 |
| GRUB UUID Wrapper Template | create-uefi-autoinstall-proxmox-usb.sh | 689-823 |
| ISO Preparation | create-uefi-autoinstall-proxmox-usb.sh | 353-431 |
| EFI Embedding | create-uefi-autoinstall-proxmox-usb.sh | 575-849 |

## Testing Checklist

- [ ] First install: Auto-installer activates
- [ ] First-boot script creates marker
- [ ] Marker contains correct UUID
- [ ] Second boot: "Boot Installed" menu appears
- [ ] Default boots installed system (5 sec timeout)
- [ ] "Reinstall" option works if selected
- [ ] Different USB: Allows reinstall
- [ ] Deleted marker: Allows reinstall
- [ ] SKIP_UUID_PROTECTION=1: Skips all checks

## Future Improvements

1. **Multi-boot support**: Handle multiple Proxmox installations
2. **Version tracking**: Store Proxmox version in marker
3. **Installation date**: Store timestamp for audit
4. **Encryption support**: Handle encrypted EFI partitions
5. **UEFI variable fallback**: Use UEFI vars if EFI partition unavailable
