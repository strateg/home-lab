# UUID Flow Analysis - Reinstall Prevention System

## Overview

This document traces the UUID through the entire system lifecycle to identify where it gets created, stored, read, and compared.

---

## 1. USB Creation Phase

### Step 1.1: Generate UUID
```bash
# Location: create-usb.sh line ~295
TIMEZONE=$(date +%Z)
TIMESTAMP=$(date +%Y_%m_%d_%H_%M)
INSTALL_UUID="${TIMEZONE}_${TIMESTAMP}"
# Example: EEST_2025_10_10_21_43
```

**Storage**: `/tmp/install-uuid-$$` (temporary)

---

### Step 1.2: Embed UUID in First-Boot Script
```bash
# Location: create-usb.sh line ~308-370
FIRST_BOOT_SCRIPT="/tmp/first-boot-$$.sh"
cat > "$FIRST_BOOT_SCRIPT" << 'SCRIPTEOF'
INSTALL_ID="INSTALL_UUID_PLACEHOLDER"
...
SCRIPTEOF

# Replace placeholder
sed -i "s/INSTALL_UUID_PLACEHOLDER/$INSTALL_UUID/" "$FIRST_BOOT_SCRIPT"
```

**Storage**: UUID hardcoded in first-boot script → passed to `prepare-iso`

---

### Step 1.3: Prepare ISO with First-Boot Script
```bash
# Location: create-usb.sh line ~388
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file "$TEMP_ANSWER" \
    --on-first-boot "$FIRST_BOOT_SCRIPT"
```

**Result**: ISO created with embedded first-boot script containing UUID

---

### Step 1.4: Write ISO to USB
```bash
# Location: create-usb.sh line ~502
dd if="$PREPARED_ISO" of="$USB_DEVICE" bs=4M
```

**Result**: USB now has ISO with:
- First-boot script (contains UUID)
- GRUB bootloader (will be modified next)

---

### Step 1.5: Embed UUID on USB EFI Partition
```bash
# Location: create-usb.sh line ~617-648
# Current implementation:
for part in "${USB_DEVICE}"[0-9]*; do
    FSTYPE=$(blkid -s TYPE -o value "$part")
    [ "$FSTYPE" != "vfat" ] && continue

    PARTLABEL=$(blkid -s PARTLABEL -o value "$part")

    # Check if EFI partition
    if [[ "$PARTLABEL" =~ [Ee][Ff][Ii] ]] || [[ "$PARTLABEL" =~ [Bb]oot ]]; then
        if mount -o rw "$part" "$MOUNT_POINT"; then
            if [ -f "$MOUNT_POINT/EFI/BOOT/grub.cfg" ]; then
                echo -n "$INSTALL_UUID" > "$MOUNT_POINT/EFI/BOOT/install-id"
                # Modify grub.cfg...
            fi
        fi
    fi
done
```

**Expected Storage**: `/EFI/BOOT/install-id` on EFI partition (PARTLABEL="EFI boot partition")

**Question**: Does this correctly identify the EFI partition?

---

## 2. Installation Phase

### Step 2.1: Proxmox Installs
- User boots from USB
- GRUB loads from USB (should check for existing UUID, but on first install none exists)
- Proxmox installer runs
- System installed to `/dev/sda`

---

### Step 2.2: First-Boot Script Executes
```bash
# First-boot script embedded in ISO
# Location: in first-boot-$$.sh (embedded at creation time)

INSTALL_ID="EEST_2025_10_10_21_43"  # Hardcoded from USB creation

# Write to system
echo -n "$INSTALL_ID" > /etc/proxmox-install-id

# Find and mount EFI partition
if mountpoint -q /efi; then
    EFI_MOUNT="/efi"
elif mountpoint -q /boot/efi; then
    EFI_MOUNT="/boot/efi"
else
    # Try to find and mount EFI partition
    for disk in /dev/sda /dev/nvme0n1; do
        for part in "${disk}"[0-9]*; do
            PART_TYPE=$(blkid -s TYPE -o value "$part")
            if [ "$PART_TYPE" = "vfat" ]; then
                mkdir -p /efi
                mount "$part" /efi && EFI_MOUNT="/efi" && break 2
            fi
        done
    done
fi

# Write UUID to EFI partition
echo -n "$INSTALL_ID" > "$EFI_MOUNT/proxmox-installed"
```

**Expected Storage**: `/efi/proxmox-installed` on system's EFI partition (typically `/dev/sda2`)

**Question**: Does first-boot correctly find the SYSTEM's EFI partition and not USB?

---

## 3. Reboot Phase (UUID Check)

### Step 3.1: GRUB Loads from USB
```grub
# Location: GRUB config created on USB (create-usb.sh line ~676-783)

set install_detected=0
set found_marker=0

# Check for UUID on HARD DISK (hd0)
if [ -f (hd0,gpt2)/proxmox-installed ]; then
    cat --set=installed_id (hd0,gpt2)/proxmox-installed
    set found_marker=1
fi

if [ $found_marker -eq 0 ]; then
    if [ -f (hd0,gpt1)/proxmox-installed ]; then
        cat --set=installed_id (hd0,gpt1)/proxmox-installed
        set found_marker=1
    fi
fi

# Check for UUID on USB ($root)
if [ $found_marker -eq 1 ]; then
    if [ -f ($root)/EFI/BOOT/install-id ]; then
        cat --set=usb_id ($root)/EFI/BOOT/install-id

        if [ "$installed_id" = "$usb_id" ]; then
            set install_detected=1
        fi
    fi
fi
```

**Expected Behavior**:
- Read UUID from HDD: `/dev/sda2/proxmox-installed` → `EEST_2025_10_10_21_43`
- Read UUID from USB: `($root)/EFI/BOOT/install-id` → `EEST_2025_10_10_21_43`
- Compare: Match → boot from disk

**Question**: Does GRUB `$root` point to the correct EFI partition on USB?

---

## 4. Potential Issues

### Issue 1: Multiple EFI Partitions on USB
Proxmox ISO may have multiple partitions after `prepare-iso`:
- Gap0 (non-mountable)
- **EFI boot partition** (PARTLABEL="EFI boot partition") ← CORRECT
- HFSPLUS (macOS boot)
- Others

**Problem**: Script may find wrong vfat partition

**Solution**:
- ✅ Already implemented: Check PARTLABEL
- ❓ Verify: Does it work?

---

### Issue 2: GRUB $root Variable
When GRUB boots from USB, `$root` is set by GRUB automatically.

**Question**: Does `$root` point to the EFI boot partition or somewhere else?

**Test**: Check what `$root` resolves to in GRUB.

**Possible Issue**: If USB has multiple partitions, GRUB might set `$root` to the ISO partition (hfsplus/iso9660), not the EFI partition!

**Solution**: Instead of `($root)/EFI/BOOT/install-id`, explicitly specify the USB EFI partition.

**But how?** GRUB doesn't know which USB device it booted from!

---

### Issue 3: First-Boot Finds USB Instead of System Disk
```bash
# First-boot tries to find EFI partition:
for disk in /dev/sda /dev/nvme0n1; do
    for part in "${disk}"[0-9]*; do
        if [ "$PART_TYPE" = "vfat" ]; then
            mount "$part" /efi  # Could mount USB if it's still connected!
        fi
    done
done
```

**Problem**: If USB is still connected, it might mount `/dev/sdc2` (USB EFI) instead of `/dev/sda2` (system EFI)!

**Solution**:
- ✅ Already checks `/dev/sda` first
- ❓ But does it check if partition is on SYSTEM disk?

---

## 5. Diagnosis Commands

To verify current state, run on installed Proxmox:

```bash
# Check UUID files
cat /etc/proxmox-install-id
cat /efi/proxmox-installed

# Check what's mounted at /efi
mount | grep /efi
findmnt /efi

# Check disk UUID (not partition UUID!)
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL /dev/sda
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,PARTLABEL /dev/sdc

# Check if UUID file exists on USB (when connected)
mkdir -p /mnt/usb-check
mount /dev/sdc2 /mnt/usb-check
cat /mnt/usb-check/EFI/BOOT/install-id
cat /mnt/usb-check/EFI/BOOT/grub.cfg | grep "install-id"
umount /mnt/usb-check
```

---

## 6. Root Cause Hypothesis

Based on symptoms:
1. ✅ First-boot executes successfully
2. ✅ UUID written to `/efi/proxmox-installed`
3. ❌ System still reinstalls on reboot

**Most Likely Cause**: GRUB cannot read UUID from USB

**Why?**
- GRUB's `$root` may not point to the EFI partition
- GRUB may be searching in wrong location
- File path `/EFI/BOOT/install-id` may not exist on GRUB's `$root`

**Test**: Boot from USB, press 'c' in GRUB, run:
```grub
ls ($root)/EFI/BOOT/
cat ($root)/EFI/BOOT/install-id
```

This will show what `$root` actually is!

---

## 7. Proposed Fix

### Option A: Use Search in GRUB Instead of $root
```grub
# Instead of assuming $root is correct:
if [ -f ($root)/EFI/BOOT/install-id ]; then
    cat --set=usb_id ($root)/EFI/BOOT/install-id
fi

# Use search to find the file:
search --no-floppy --set=usbpart --file /EFI/BOOT/install-id
if [ -n "$usbpart" ]; then
    cat --set=usb_id ($usbpart)/EFI/BOOT/install-id
fi
```

**Problem**: This will find ANY partition with that file (could be old USB!)

---

### Option B: Hardcode USB Device in GRUB
```grub
# Try known USB device locations
if [ -f (hd1,gpt2)/EFI/BOOT/install-id ]; then
    cat --set=usb_id (hd1,gpt2)/EFI/BOOT/install-id
elif [ -f (hd2,gpt2)/EFI/BOOT/install-id ]; then
    cat --set=usb_id (hd2,gpt2)/EFI/BOOT/install-id
fi
```

**Problem**: USB device order may vary!

---

### Option C: Store UUID in GRUB Config Itself
```grub
# At the top of grub.cfg (written by create-usb.sh):
set usb_id="EEST_2025_10_10_21_43"

# Then just compare:
if [ "$installed_id" = "$usb_id" ]; then
    set install_detected=1
fi
```

**Advantage**: No need to read file from disk!
**Disadvantage**: Less flexible, UUID embedded in GRUB config.

**This is probably the best solution!**

---

## 8. Recommended Solution

**Store UUID directly in GRUB config**:

```bash
# In create-usb.sh, when creating grub.cfg:
cat > grub.cfg << GRUBEOF
# Reinstall Prevention Check
set usb_uuid="$INSTALL_UUID"  # ← EMBED UUID HERE

# Check hard disk
if [ -f (hd0,gpt2)/proxmox-installed ]; then
    cat --set=installed_id (hd0,gpt2)/proxmox-installed
    set found_marker=1
fi

# Compare
if [ "\$installed_id" = "\$usb_uuid" ]; then
    set install_detected=1
fi
GRUBEOF
```

**Benefits**:
- No file I/O needed in GRUB
- No ambiguity about partition locations
- Simple and reliable

---

## Status
- ❌ Current implementation: Reads UUID from file on USB (unreliable)
- ✅ Proposed fix: Embed UUID directly in GRUB config
