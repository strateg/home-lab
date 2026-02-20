# Reinstall Prevention System

## Problem Statement

При установке Proxmox с автоматической USB-флешки возникала проблема:
- После завершения установки система перезагружается
- Если флешка не вынута, автоматическая установка запускается снова
- **Результат**: Бесконечный цикл переустановок, уничтожение данных

## Solution Overview

Реализована система проверки установки через **Installation ID (читаемый штамп с датой/временем)**:
1. При создании USB генерируется ID с датой и временем создания
2. Формат ID: `TIMEZONE_YYYY_MM_DD_HH_MM` (например: `UTC_2025_10_10_14_30`)
3. ID сохраняется на флешке и на установленной системе
4. При загрузке GRUB проверяет наличие ID на диске и показывает дату создания
5. Если ID совпадают → загружается установленная система (не переустановка!)
6. Если ID нет или другой → запускается установка

**Преимущество**: Можно сразу увидеть когда была создана флешка!

## How It Works

### Phase 1: USB Creation

**Script**: `create-uefi-autoinstall-proxmox-usb.sh` (UEFI mode only)

> **Note**: Reinstall prevention is **only available in UEFI mode**. Legacy BIOS does not support this feature due to read-only ISO filesystem limitations. See [USB Creation Guide](usb-creation.md) for details.

```bash
# 1. Generate readable installation ID with timestamp
TIMEZONE=$(date +%Z)
TIMESTAMP=$(date +%Y_%m_%d_%H_%M)
INSTALL_UUID="${TIMEZONE}_${TIMESTAMP}"
# Example: UTC_2025_10_10_14_30

# 2. Embed ID on USB
/EFI/BOOT/install-id
→ Contains: UTC_2025_10_10_14_30

/EFI/BOOT/install-info.txt
→ Human-readable info with parsed date/time

# 3. Add first-boot commands to answer.toml
[first-boot]
post-installation-commands = [
    "echo 'UTC_2025_10_10_14_30' > /etc/proxmox-install-id",
    "echo 'UTC_2025_10_10_14_30' > /boot/efi/proxmox-installed"
]

# 4. Create GRUB check script on USB with date display
/EFI/BOOT/reinstall-check.cfg
→ Detects if system already installed
→ Shows readable date/time in GRUB menu
```

### Phase 2: First Installation

**Timeline**: First boot from USB (no system on disk)

1. **GRUB boots from USB**
2. **reinstall-check.cfg runs**:
   - Searches for `/boot/efi/proxmox-installed` on disk
   - File NOT found (clean disk)
   - `install_detected = 0`
3. **Menu**: Shows standard "Automated Installation" (10s countdown)
4. **Installation proceeds automatically**
5. **After installation**:
   - First-boot commands execute
   - UUID saved to `/etc/proxmox-install-id`
   - UUID saved to `/boot/efi/proxmox-installed`
6. **System reboots** (USB still inserted)

### Phase 3: Second Boot (Reinstall Prevention)

**Timeline**: Second boot from USB (system already installed)

1. **GRUB boots from USB**
2. **reinstall-check.cfg runs**:
   - Searches for `/boot/efi/proxmox-installed` on disk
   - File FOUND! Reads UUID from it
   - Reads UUID from USB (`/EFI/BOOT/install-id`)
   - **Compares UUIDs**:
     - USB UUID: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
     - Disk UUID: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
     - **Match!** → `install_detected = 1`
3. **Menu changes automatically**:
   ```
   Proxmox already installed from this USB
   Press 'd' to boot installed system (auto in 10s)
   Press 'r' to REINSTALL (will ERASE all data!)

   1. Boot Proxmox from disk (Already Installed) [DEFAULT]
   2. Reinstall Proxmox (ERASES DISK!)
   ```
4. **After 10 seconds** → Chainloads installed system (no reinstall!)
5. **User can press 'r'** → Force reinstallation if needed

## File Locations

### On USB Drive (FAT32 EFI partition)

```
/EFI/BOOT/
├── install-id                  # Installation ID: UTC_2025_10_10_14_30
├── install-info.txt            # Human-readable info (timezone, date, time)
├── reinstall-check.cfg         # GRUB detection script (shows date in menu)
└── grub.cfg                    # Standard GRUB config (called if no installation detected)
```

### On Installed System

```
/etc/proxmox-install-id         # Installation ID: UTC_2025_10_10_14_30
/boot/efi/proxmox-installed     # ID marker on EFI partition (checked by GRUB)
/var/log/proxmox-install.log    # Installation log with ID
```

## ID Comparison Logic

```grub
# GRUB script logic (reinstall-check.cfg)

# Read ID from disk
cat --set=installed_id ($efipart)/proxmox-installed

# Read ID from USB
cat --set=usb_id ($root)/EFI/BOOT/install-id

# Compare
if [ "$installed_id" = "$usb_id" ]; then
    # SAME USB that installed system
    set install_detected=1
    → Show "Boot from disk" menu with date/time
    → Display: "Installation ID: UTC_2025_10_10_14_30"
    → Display: "Created: UTC 2025-10-10 14:30"
    → Prevent reinstall
else
    # DIFFERENT USB or no installation
    set install_detected=0
    → Show "Install" menu (allow installation)
fi
```

## Use Cases

### Case 1: Normal Installation (First Time)

**Scenario**: Clean laptop, installing Proxmox for the first time

1. Boot from USB
2. No installation marker on disk
3. **Result**: Automatic installation proceeds
4. After reboot: System boots from disk (even if USB still inserted)

**Status**: ✅ Installation successful, no accidental reinstall

---

### Case 2: Reinstall with SAME USB

**Scenario**: System already installed from USB-A, booting from USB-A again

1. Boot from USB-A
2. ID marker found on disk
3. IDs match (both from USB-A)
4. **GRUB shows**:
   ```
   Installation ID: UTC_2025_10_10_14_30
   Created: UTC 2025-10-10 14:30

   Press 'd' to boot installed system (auto in 10s)
   Press 'r' to REINSTALL (will ERASE all data!)
   ```
5. **Result**: Boots installed system (no reinstall)

**User action**: Press 'r' to force reinstall if needed

**Status**: ✅ Reinstallation prevented, date/time visible

---

### Case 3: Install with DIFFERENT USB

**Scenario**: System installed from USB-A, booting from USB-B (different dates)

1. Boot from USB-B
2. ID marker found on disk (from USB-A)
3. IDs DON'T match:
   - Disk ID: `UTC_2025_10_10_14_30` (USB-A, created Oct 10 14:30)
   - USB ID: `UTC_2025_10_15_09_00` (USB-B, created Oct 15 09:00)
4. **Result**: Shows installation menu (allows fresh install)

**Note**: Can see both USB creation dates!

**Status**: ✅ Can reinstall with different USB

---

### Case 4: Disk Moved to Another Laptop

**Scenario**: SSD with installed Proxmox moved to another Dell XPS

1. Boot from any USB
2. ID marker found on disk
3. IDs may match or not (depends on USB used)
4. **GRUB shows installation date from original USB**
5. **Result**:
   - If same USB (same date) → boots installed system
   - If different USB (different date) → allows reinstallation

**Advantage**: Can see when system was originally installed!

**Status**: ✅ Portable, date-based detection

## Technical Details

### GRUB Commands Used

```grub
# Load required modules
insmod part_gpt       # GPT partition table support
insmod part_msdos     # MBR partition table support
insmod fat            # FAT32 filesystem support
insmod ext2           # ext2/3/4 filesystem support

# Search for EFI partition on disk
search --no-floppy --fs-uuid --set=efipart

# Read file to variable
cat --set=var_name ($partition)/path/to/file

# Chainload to installed system
set root=(hd0,gpt2)   # EFI partition on first disk
chainloader /EFI/proxmox/grubx64.efi
```

### First-Boot Commands (answer.toml)

```toml
[first-boot]
post-installation-commands = [
    "echo 'UUID' > /etc/proxmox-install-id",
    "mkdir -p /boot/efi",
    "echo 'UUID' > /boot/efi/proxmox-installed",
    "echo 'Installation UUID marker created' >> /var/log/proxmox-install.log"
]
```

## Security Considerations

### ID Uniqueness

- Format: `TIMEZONE_YYYY_MM_DD_HH_MM`
- Example: `UTC_2025_10_10_14_30`
- Based on creation timestamp (minute precision)
- Collision: Only if two USBs created in same minute (unlikely)
- Human-readable: Can see exact creation date/time

### Tampering Prevention

- IDs stored in plain text (not encrypted)
- **Not a security feature** - это механизм удобства, не безопасности
- Any user with disk access can modify IDs
- Purpose: Prevent **accidental** reinstallation, not malicious reinstallation
- **Bonus**: IDs are human-readable, showing creation date

### Force Reinstallation

User can always force reinstallation by:
1. Pressing 'r' in GRUB menu, OR
2. Deleting `/boot/efi/proxmox-installed` on disk, OR
3. Creating USB with different date (new USB or wait 1 minute)

## Troubleshooting

### Issue 1: System Always Reinstalls (ID not working)

**Symptoms**: Every boot starts installation, ID check doesn't work

**Diagnosis**:
```bash
# Check if ID was saved during installation
ssh root@proxmox-ip
cat /etc/proxmox-install-id
# Should show: UTC_2025_10_10_14_30

cat /boot/efi/proxmox-installed
# Should show: UTC_2025_10_10_14_30
```

**Fix**:
- If files missing: first-boot commands failed
- Get USB ID:
  ```bash
  # Mount USB and check
  cat /mnt/EFI/BOOT/install-id
  ```
- Manually create markers:
  ```bash
  USB_ID="UTC_2025_10_10_14_30"  # From USB
  echo "$USB_ID" > /etc/proxmox-install-id
  echo "$USB_ID" > /boot/efi/proxmox-installed
  ```

---

### Issue 2: Cannot Boot from Disk (Chainloader Fails)

**Symptoms**: Menu shows "Boot from disk" but fails to boot

**Diagnosis**:
```grub
# In GRUB menu, press 'c' for console
ls
ls (hd0,gpt2)/EFI
```

**Fix**:
- Check EFI partition number (may be gpt1, gpt2, gpt3)
- Update `reinstall-check.cfg` on USB:
  ```grub
  set root=(hd0,gpt1)  # Change number if needed
  ```

---

### Issue 3: Want to Force Reinstall but Menu Doesn't Show Option

**Symptoms**: UUID detected, but need to reinstall

**Solution 1**: Press 'r' in GRUB menu (Reinstall option)

**Solution 2**: Delete UUID marker from disk:
```bash
# Boot to rescue mode or live USB
mount /dev/sda2 /mnt       # Mount EFI partition
rm /mnt/proxmox-installed
reboot
```

**Solution 3**: Create new USB (different UUID)

---

### Issue 4: ID Mismatch but Should Match

**Symptoms**: Different IDs on USB and disk, but should be same

**Diagnosis**:
```bash
# On USB (mount it)
cat /mnt/EFI/BOOT/install-id
# Shows: UTC_2025_10_10_14_30

# Show human-readable info
cat /mnt/EFI/BOOT/install-info.txt
# Shows parsed date/time

# On installed system
cat /boot/efi/proxmox-installed
# Shows: UTC_2025_10_10_14_30

# Compare - should match!
```

**Fix**:
- Update disk ID to match USB:
  ```bash
  USB_ID=$(cat /mnt/EFI/BOOT/install-id)
  echo "$USB_ID" > /boot/efi/proxmox-installed
  ```

## Testing Checklist

- [ ] **Test 1**: Fresh installation on clean disk
  - UUID marker created on disk
  - Second boot doesn't reinstall

- [ ] **Test 2**: Force reinstall with 'r' key
  - Menu shows reinstall option
  - Reinstallation proceeds when 'r' pressed

- [ ] **Test 3**: Different USB
  - Create two USBs with different UUIDs
  - Install with USB-A
  - Boot with USB-B → should offer installation

- [ ] **Test 4**: Chainload to disk
  - Install system
  - Remove USB after installation
  - Insert USB again → should boot from disk

- [ ] **Test 5**: Manual UUID deletion
  - Delete `/boot/efi/proxmox-installed`
  - Boot from USB → should reinstall

## Improvements and Future Work

### Potential Enhancements

1. ~~**Visual indicator of creation date**~~ → ✅ **IMPLEMENTED!**
   - Shows full date/time in GRUB menu
   - Format: `UTC 2025-10-10 14:30`
   - Also saved in readable `install-info.txt` file

2. **Installation counter**:
   - Track how many times system was installed
   - Save to `/etc/proxmox-install-count`

3. **Multiple ID support**:
   - Allow list of trusted USB IDs
   - Example: `/etc/proxmox-install-ids` (one per line)

4. **GRUB password protection**:
   - Require password to force reinstall
   - Prevent accidental 'r' key press

5. **USB write-protection**:
   - Mark USB as read-only after creation
   - Prevent ID modification

6. **Installation history**:
   - Log all installation attempts with dates
   - Show in GRUB: "Last installed: 2025-10-10"

### Compatibility

- **Proxmox VE**: 9.x (tested)
- **GRUB**: 2.x (UEFI mode)
- **Filesystems**: ext4, FAT32
- **Partition tables**: GPT, MBR

## References

- **GRUB Manual**: https://www.gnu.org/software/grub/manual/
- **Proxmox Auto-Install**: https://pve.proxmox.com/wiki/Automated_Installation
- **UUID RFC 4122**: https://datatracker.ietf.org/doc/html/rfc4122
- **Project Repository**: `manual-scripts/bare-metal/create-usb.sh`

---

**Status**: ✅ Implemented and documented
**Last Updated**: 2025-10-10
**Version**: 1.0
