# Orange Pi 5: Clean Armbian Installation on NVMe SSD

**Device**: Orange Pi 5 (RK3588S, 16GB RAM, NVMe 256GB)
**Target**: Clean installation of Armbian on NVMe SSD with UEFI boot
**Last Updated**: 2026-06

## Overview

This guide covers three installation methods:
1. **Standard Method** — SPI bootloader + Armbian on NVMe (recommended for first setup)
2. **UEFI Method** — EDK2 UEFI firmware + standard ARM64 images
3. **WSL Method** — Direct write from Windows 11 via WSL (fastest for reinstall)

The Orange Pi 5 has:
- SPI NOR flash (16MB) for bootloader/UEFI
- eMMC card slot (optional module)
- M.2 NVMe slot (2230/2242)
- MicroSD slot

## Requirements

### Hardware
- Orange Pi 5 board
- NVMe SSD (M.2 2230 or 2242)
- MicroSD card (8GB+) for initial boot
- Power supply (5V/4A, USB-C PD recommended)
- HDMI display + keyboard
- (Optional) USB NVMe enclosure for direct image writing

### Software
- [Armbian image for Orange Pi 5](https://www.armbian.com/orangepi-5/)
- [balenaEtcher](https://etcher.balena.io/) or Raspberry Pi Imager
- (For UEFI) [EDK2-RK3588 firmware](https://github.com/edk2-porting/edk2-rk3588/releases)

## Method 1: Standard SPI Boot (Recommended)

### Step 1: Download Armbian Image

Download from [Armbian Orange Pi 5](https://www.armbian.com/orangepi-5/):

| Image | Kernel | Size | Use Case |
|-------|--------|------|----------|
| Debian 13 Minimal | 6.1.115 (vendor) | 290 MB | Server/headless |
| Ubuntu 26.04 GNOME | 6.1.115 (vendor) | 1.1 GB | Desktop |

Verify checksum:
```bash
sha256sum Armbian_*.img.xz
# Compare with .sha file from download page
```

### Step 2: Write Image to MicroSD

```bash
# Decompress
xz -d Armbian_*.img.xz

# Write to SD card (replace sdX with your device)
sudo dd if=Armbian_*.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Or use balenaEtcher/Raspberry Pi Imager GUI.

### Step 3: Initial Boot from SD Card

1. Insert SD card into Orange Pi 5
2. Connect NVMe SSD to M.2 slot
3. Connect display, keyboard, power
4. Wait for first boot (2-3 minutes)
5. Login: `root` / `1234` (change on first login)

### Step 4: Flash SPI Bootloader

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required tools
sudo apt install -y mtools

# Run configuration utility
sudo armbian-config
```

Navigate:
```
System → Install → Install/Update the bootloader on SPI Flash
```

Wait for completion (1-2 minutes).

### Step 5: Install Armbian to NVMe

**Option A: Using armbian-config**

```bash
sudo armbian-config
```

Navigate:
```
System → Install → Install to/update boot loader → Boot from SPI - system on NVMe
```

Select target: `/dev/nvme0n1`

**Option B: Direct Write (Clean Install)**

If you have USB NVMe enclosure:

```bash
# On another Linux machine, write directly to NVMe via USB
sudo dd if=Armbian_*.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Then install NVMe into Orange Pi 5.

### Step 6: Verify and Reboot

```bash
# Check NVMe is detected
lsblk

# Should show:
# nvme0n1     259:0    0 238.5G  0 disk
# ├─nvme0n1p1 259:1    0   256M  0 part  /boot
# └─nvme0n1p2 259:2    0 238.2G  0 part  /

# Reboot without SD card
sudo shutdown -h now
```

Remove SD card and power on. System should boot from NVMe via SPI bootloader.

### Step 7: Expand Filesystem

```bash
# Filesystem should auto-expand, verify:
df -h /

# If not expanded:
sudo armbian-config
# System → Manage or change RootFS properties → Resize
```

---

## Method 2: UEFI Boot (EDK2)

UEFI provides a PC-like boot experience with boot menu, secure boot capability, and compatibility with standard ARM64 images.

### Step 1: Download EDK2 UEFI Firmware

From [edk2-rk3588 releases](https://github.com/edk2-porting/edk2-rk3588/releases):

```bash
# Download latest release for Orange Pi 5
wget https://github.com/edk2-porting/edk2-rk3588/releases/download/vX.X/orangepi-5_UEFI_Release_vX.X.img
```

### Step 2: Flash UEFI to SPI

**Option A: From running Armbian (SD boot)**

```bash
# Flash to SPI NOR
sudo dd if=orangepi-5_UEFI_Release_*.img of=/dev/mtdblock0 bs=4M
sudo sync
```

**Option B: Using UEFI Shell**

1. Copy firmware to FAT32 USB drive
2. Boot existing UEFI, press F1 for Shell
3. Execute:
```
fs0:
sf updatefile orangepi-5_UEFI_Release_vX.X.img 0x0
```

**Option C: Using RKDevTool (Windows)**

1. Enter MaskROM mode (hold BOOT button during power-on)
2. Use RKDevTool with:
   - Loader: `rk3588_spl_loader.bin`
   - Image: UEFI .img file
   - Target: SPINOR

### Step 3: Prepare NVMe with Armbian

Write Armbian image to NVMe:

```bash
# Using USB enclosure on another machine
sudo dd if=Armbian_*.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Or use Armbian generic UEFI image:
```bash
wget https://dl.armbian.com/uefi-arm64/Bookworm_current
```

### Step 4: Boot and Configure

1. Install NVMe, power on
2. Press **Esc** during boot logo for UEFI Setup
3. Configure boot order: NVMe first
4. Save and reboot

### UEFI Boot Keys

| Key | Action |
|-----|--------|
| Esc | UEFI Setup |
| F1 | UEFI Shell |
| F4 | MaskROM Recovery |

---

## Method 3: WSL on Windows 11 (Quick Reinstall)

**Prerequisites**: SPI bootloader already configured on Orange Pi 5.

This is the fastest method for clean reinstall when you have a Windows 11 laptop with:
- WSL2 installed (Ubuntu/Debian)
- USB NVMe enclosure or M.2 to USB adapter
- SD card reader (optional, for SD card images)

### Step 1: Connect SSD to Windows Laptop

1. Remove NVMe SSD from Orange Pi 5
2. Connect via USB NVMe enclosure to Windows laptop
3. Windows will detect but may not mount (no driver for ext4)

### Step 2: Mount Disk in WSL

Open PowerShell as Administrator:

```powershell
# List available disks
wmic diskdrive list brief

# Find the Orange Pi SSD (look for size ~256GB)
# Note the DeviceID, e.g., \\.\PHYSICALDRIVE2

# Mount disk in WSL
wsl --mount \\.\PHYSICALDRIVE2 --bare
```

### Step 3: Download Armbian in WSL

Open WSL terminal:

```bash
# Create working directory
mkdir -p ~/orangepi && cd ~/orangepi

# Download latest Armbian for Orange Pi 5
wget https://dl.armbian.com/orangepi5/Trixie_vendor_minimal

# Or use curl
curl -L -o armbian.img.xz https://dl.armbian.com/orangepi5/Trixie_vendor_minimal

# Decompress
xz -d *.img.xz
```

### Step 4: Identify Disk in WSL

```bash
# List block devices
lsblk

# The USB-connected SSD appears as /dev/sdX (e.g., /dev/sdc)
# Verify by size (should be ~256GB)
sudo fdisk -l /dev/sdc
```

**Important**: Double-check the device! Wrong device = data loss.

### Step 5: Write Image to SSD

```bash
# Write Armbian image (replace sdX with your device)
sudo dd if=Armbian_*.img of=/dev/sdX bs=4M status=progress conv=fsync

# Sync to ensure all data written
sync
```

Expected output:
```
1887+1 records in
1887+1 records out
7918845952 bytes (7.9 GB, 7.4 GiB) copied, 45.2 s, 175 MB/s
```

### Step 6: Safely Eject

In WSL:
```bash
sync
```

In PowerShell (Admin):
```powershell
wsl --unmount \\.\PHYSICALDRIVE2
```

Then use Windows "Safely Remove Hardware" for the USB enclosure.

### Step 7: Install SSD and Boot

1. Disconnect SSD from laptop
2. Install NVMe back into Orange Pi 5
3. Power on — boots from SSD via pre-configured SPI bootloader
4. First boot: login `root` / `1234`

### Step 8: Expand Filesystem

```bash
# Check current size
df -h /

# Expand to full SSD
sudo armbian-config
# System → Manage or change RootFS properties → Resize
```

### WSL Troubleshooting

**Disk not appearing in WSL:**
```powershell
# Ensure disk is online in Windows
diskpart
> list disk
> select disk X
> online disk
> exit

# Re-mount in WSL
wsl --mount \\.\PHYSICALDRIVEX --bare
```

**Permission denied in WSL:**
```bash
# Run with sudo
sudo dd if=image.img of=/dev/sdX ...
```

**Slow write speed:**
```bash
# Use larger block size
sudo dd if=image.img of=/dev/sdX bs=16M status=progress conv=fsync
```

**Verify image integrity:**
```bash
# After writing, verify
sudo dd if=/dev/sdX bs=4M count=1887 | sha256sum
# Compare with original image checksum
```

---

## Post-Installation

### System Update

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### Performance Check

```bash
# Check NVMe speed
sudo hdparm -Tt /dev/nvme0n1

# Expected: ~350-400 MB/s read
```

### Configure Network

```bash
sudo nmtui
# Or
sudo armbian-config → Network
```

### Set Hostname

```bash
sudo hostnamectl set-hostname orangepi5
```

### Install Essential Packages

```bash
sudo apt install -y \
  htop \
  curl \
  git \
  vim \
  python3-pip \
  docker.io \
  docker-compose
```

---

## Troubleshooting

### NVMe Not Detected

```bash
# Check PCIe
lspci | grep -i nvme

# Check dmesg
dmesg | grep -i nvme
```

If not detected:
- Verify M.2 SSD is NVMe (not SATA)
- Check physical connection
- Try different NVMe drive

### Boot Fails After SPI Flash

1. Hold BOOT button, power on → MaskROM mode
2. Re-flash SPI using RKDevTool
3. Or boot from SD card and reflash

### Slow NVMe Performance

```bash
# Check if TRIM is enabled
sudo fstrim -v /

# Enable in fstab
# Add 'discard' option to NVMe mount
```

### Return to Stock Bootloader

```bash
# Download original u-boot
wget https://github.com/orangepi-xunlong/orangepi-build/raw/main/external/cache/sources/rkbin-tools/rk3588/rk3588_spl_loader.bin

# Flash to SPI
sudo dd if=rk3588_spl_loader.bin of=/dev/mtdblock0 bs=4M
```

---

## References

- [Armbian Orange Pi 5](https://www.armbian.com/orangepi-5/)
- [EDK2-RK3588 UEFI Firmware](https://github.com/edk2-porting/edk2-rk3588)
- [James Chambers: Orange Pi 5 SSD Boot Guide](https://jamesachambers.com/orange-pi-5-ssd-boot-guide/)
- [Armbian Forums: Orange Pi 5](https://forum.armbian.com/forum/196-orange-pi-5/)
- [Crosstalk Solutions: Orange Pi 5 Overview](https://www.crosstalksolutions.com/orange-pi-5-simple-overview-and-installation-with-m-2-ssd/)
