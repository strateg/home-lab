# Proxmox Auto-Install USB - Quick Start Guide

## ✅ The Working Solution

Use `create-proxmox-usb-official.sh` - this is the **official, supported method** that actually works.

---

## Prerequisites

### 1. Install the Official Tool

On Ubuntu/Debian machine where you're creating the USB:

```bash
apt update
apt install proxmox-auto-install-assistant
```

### 2. Prepare Files

You need these files in the same directory:
- `proxmox-auto-install-answer.toml` ✅ (already exists)
- `create-proxmox-usb-official.sh` ✅ (already exists)
- Proxmox VE 9 ISO file (download if needed)

---

## Create the USB

### Step 1: Identify USB Device

```bash
# Before inserting USB
lsblk

# Insert USB drive

# After inserting
lsblk

# Your USB is the new device (e.g., /dev/sdb, /dev/sdc)
# DO NOT use /dev/sda (your main disk)
```

### Step 2: Run the Script

```bash
sudo ./create-proxmox-usb-official.sh /dev/sdX path/to/proxmox.iso
```

Replace:
- `/dev/sdX` with your actual USB device (e.g., `/dev/sdb`)
- `path/to/proxmox.iso` with path to your Proxmox ISO

### Step 3: Wait

The script will:
1. ✅ Embed answer file into ISO (using official tool)
2. ✅ Write modified ISO to USB
3. ✅ Add graphics parameters for external display
4. ✅ Verify everything

Time: ~5-10 minutes depending on USB speed

---

## Boot the USB

### On Dell XPS L701X:

1. **Connect external monitor** to Mini DisplayPort
2. **Power ON** the external monitor first
3. **Insert USB** into laptop
4. **Power on** laptop
5. **Press F12** when Dell logo appears
6. **Select**: `UEFI: USB...` (NOT "USB Storage Device")

### Expected Behavior:

- GRUB menu appears on **external display** ✅
- First option: **"Automated Installation"** or **"Proxmox VE - Automated Install"**
- Timeout: 3 seconds
- Press **Enter** or wait 3 seconds
- Installation starts **automatically** ✅

### Installation Progress:

- Partitioning disk (sda)
- Installing base system
- Configuring network
- Installing Proxmox packages
- Setting up boot loader
- **Total time: ~10-15 minutes**
- System reboots when complete

---

## After Installation

### Find IP Address

Option 1: Check on laptop console (if you can see it)
```bash
ip addr show
```

Option 2: Check your router's DHCP leases

Option 3: Scan network
```bash
nmap -sn 192.168.1.0/24 | grep -B 2 Proxmox
```

### First Login

```bash
ssh root@<ip-address>
# Password: Homelab2025!
```

### Run Post-Install Script

```bash
# If you copied proxmox-post-install.sh to USB, it's in /root
bash /root/proxmox-post-install.sh

# Or upload it:
scp proxmox-post-install.sh root@<ip-address>:/root/
ssh root@<ip-address>
bash /root/proxmox-post-install.sh
```

### Access Web Interface

Open browser:
```
https://<ip-address>:8006
```

Login:
- Username: `root`
- Password: `Homelab2025!`

---

## Troubleshooting

### USB Doesn't Boot

**Check**: Did you select `UEFI: USB...` (not "USB Storage Device")?
- UEFI boot is required
- Legacy boot won't work

**Check**: Is external monitor connected and powered on?

### External Display Stays Black

**Check**: Graphics parameters should be automatically added by script
- Verify script completed successfully
- Look for: "✓ Graphics parameters added"

### Auto-Install Doesn't Start

**Check**: Did the script complete all steps?
```
✓ Used proxmox-auto-install-assistant to embed answer file
✓ Auto-install boot entry created by official tool
✓ Graphics parameters added for external display
```

**Check**: Is answer.toml file valid?
```bash
# Test answer file
proxmox-auto-install-assistant validate-answer proxmox-auto-install-answer.toml
```

### Installation Hangs or Fails

**Check**: Is external display showing the installation progress?
- If display is black, graphics parameters might not be applied

**Check**: Network connection
- Installation needs network to download packages
- Use built-in Ethernet or USB-Ethernet adapter

---

## Why This Works (vs Previous Attempts)

This script uses the **official Proxmox tool** (`proxmox-auto-install-assistant`) which:

✅ Properly embeds the answer file into the ISO structure
✅ Adds the auto-install boot entry correctly
✅ Preserves the hybrid boot structure (MBR + GPT + EFI)
✅ Is the **recommended method** by Proxmox documentation

All previous attempts failed because they tried to manually modify GRUB configs, which:
- Either broke the boot structure (ISO rebuild)
- Or couldn't modify the read-only ISO9660 partition
- Or broke the GRUB boot chain

See `SOLUTION-COMPARISON.md` for detailed analysis.

---

## Summary

```bash
# 1. Install tool
apt install proxmox-auto-install-assistant

# 2. Create USB
sudo ./create-proxmox-usb-official.sh /dev/sdX proxmox.iso

# 3. Boot from USB
# - F12 → UEFI: USB
# - Select "Automated Installation"
# - Wait 10-15 minutes

# 4. Login and enjoy!
ssh root@<ip-address>
```

**This is the working solution.** 🎉
