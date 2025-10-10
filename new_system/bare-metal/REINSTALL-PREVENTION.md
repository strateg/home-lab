# Reinstall Prevention System

## Problem Statement

При установке Proxmox с автоматической USB-флешки возникала проблема:
- После завершения установки система перезагружается
- Если флешка не вынута, автоматическая установка запускается снова
- **Результат**: Бесконечный цикл переустановок, уничтожение данных

## Solution Overview

Реализована система проверки установки через **Installation UUID (штамп)**:
1. При создании USB генерируется уникальный UUID
2. UUID сохраняется на флешке и на установленной системе
3. При загрузке GRUB проверяет наличие UUID на диске
4. Если UUID совпадают → загружается установленная система (не переустановка!)
5. Если UUID нет или другой → запускается установка

## How It Works

### Phase 1: USB Creation

**Script**: `create-usb.sh`

```bash
# 1. Generate unique installation UUID
INSTALL_UUID=$(uuidgen)
# Example: a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 2. Embed UUID on USB
/EFI/BOOT/install-id
→ Contains: a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 3. Add first-boot commands to answer.toml
[first-boot]
post-installation-commands = [
    "echo 'UUID' > /etc/proxmox-install-id",
    "echo 'UUID' > /boot/efi/proxmox-installed"
]

# 4. Create GRUB check script on USB
/EFI/BOOT/reinstall-check.cfg
→ Detects if system already installed
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
├── install-id                  # Installation UUID (plain text)
├── reinstall-check.cfg         # GRUB detection script
└── grub.cfg                    # Standard GRUB config (called if no installation detected)
```

### On Installed System

```
/etc/proxmox-install-id         # Installation UUID (for reference)
/boot/efi/proxmox-installed     # UUID marker on EFI partition (checked by GRUB)
/var/log/proxmox-install.log    # Installation log with UUID
```

## UUID Comparison Logic

```grub
# GRUB script logic (reinstall-check.cfg)

# Read UUID from disk
cat --set=installed_uuid ($efipart)/proxmox-installed

# Read UUID from USB
cat --set=usb_uuid ($root)/EFI/BOOT/install-id

# Compare
if [ "$installed_uuid" = "$usb_uuid" ]; then
    # SAME USB that installed system
    set install_detected=1
    → Show "Boot from disk" menu (prevent reinstall)
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
2. UUID marker found on disk
3. UUIDs match (both from USB-A)
4. **Result**: Boots installed system (no reinstall)

**User action**: Press 'r' to force reinstall if needed

**Status**: ✅ Reinstallation prevented

---

### Case 3: Install with DIFFERENT USB

**Scenario**: System installed from USB-A, booting from USB-B (different UUID)

1. Boot from USB-B
2. UUID marker found on disk (from USB-A)
3. UUIDs DON'T match:
   - Disk UUID: `aaaa-bbbb-cccc...` (from USB-A)
   - USB UUID: `1111-2222-3333...` (from USB-B)
4. **Result**: Shows installation menu (allows fresh install)

**Status**: ✅ Can reinstall with different USB

---

### Case 4: Disk Moved to Another Laptop

**Scenario**: SSD with installed Proxmox moved to another Dell XPS

1. Boot from any USB
2. UUID marker found on disk
3. UUIDs may match or not (depends on USB used)
4. **Result**:
   - If same USB → boots installed system
   - If different USB → allows reinstallation

**Status**: ✅ Portable, UUID-based detection

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

### UUID Uniqueness

- Generated with `uuidgen` (RFC 4122)
- Example: `550e8400-e29b-41d4-a716-446655440000`
- Collision probability: ~1 in 10^36 (negligible)

### Tampering Prevention

- UUIDs stored in plain text (not encrypted)
- **Not a security feature** - это механизм удобства, не безопасности
- Any user with disk access can modify UUIDs
- Purpose: Prevent **accidental** reinstallation, not malicious reinstallation

### Force Reinstallation

User can always force reinstallation by:
1. Pressing 'r' in GRUB menu, OR
2. Deleting `/boot/efi/proxmox-installed` on disk, OR
3. Creating USB with different UUID (new USB)

## Troubleshooting

### Issue 1: System Always Reinstalls (UUID not working)

**Symptoms**: Every boot starts installation, UUID check doesn't work

**Diagnosis**:
```bash
# Check if UUID was saved during installation
ssh root@proxmox-ip
cat /etc/proxmox-install-id
cat /boot/efi/proxmox-installed
```

**Fix**:
- If files missing: first-boot commands failed
- Manually create markers:
  ```bash
  echo "YOUR-USB-UUID" > /etc/proxmox-install-id
  echo "YOUR-USB-UUID" > /boot/efi/proxmox-installed
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

### Issue 4: UUID Mismatch but Should Match

**Symptoms**: Different UUIDs on USB and disk, but should be same

**Diagnosis**:
```bash
# On USB (mount it)
cat /mnt/EFI/BOOT/install-id

# On installed system
cat /boot/efi/proxmox-installed

# Compare
```

**Fix**:
- Update disk UUID to match USB:
  ```bash
  USB_UUID=$(cat /mnt/EFI/BOOT/install-id)
  echo "$USB_UUID" > /boot/efi/proxmox-installed
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

1. **Visual indicator of UUID**:
   - Show last 8 chars of UUID in GRUB menu
   - Example: "Installed by USB ...67890"

2. **Installation counter**:
   - Track how many times system was installed
   - Save to `/etc/proxmox-install-count`

3. **Multiple UUID support**:
   - Allow list of trusted USB UUIDs
   - Example: `/etc/proxmox-install-ids` (one per line)

4. **GRUB password protection**:
   - Require password to force reinstall
   - Prevent accidental 'r' key press

5. **USB write-protection**:
   - Mark USB as read-only after creation
   - Prevent UUID modification

### Compatibility

- **Proxmox VE**: 9.x (tested)
- **GRUB**: 2.x (UEFI mode)
- **Filesystems**: ext4, FAT32
- **Partition tables**: GPT, MBR

## References

- **GRUB Manual**: https://www.gnu.org/software/grub/manual/
- **Proxmox Auto-Install**: https://pve.proxmox.com/wiki/Automated_Installation
- **UUID RFC 4122**: https://datatracker.ietf.org/doc/html/rfc4122
- **Project Repository**: `bare-metal/create-usb.sh`

---

**Status**: ✅ Implemented and documented
**Last Updated**: 2025-10-10
**Version**: 1.0
