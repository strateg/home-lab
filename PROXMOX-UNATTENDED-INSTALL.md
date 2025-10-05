# Proxmox VE 9 - Unattended Installation Guide
## Dell XPS L701X Home Lab

Complete guide for automated Proxmox VE 9 installation on Dell XPS L701X using answer file for hands-free deployment.

---

## Overview

This guide automates Proxmox VE 9 installation using:
- **Answer file** (`proxmox-auto-install-answer.toml`) - Automated installation configuration
- **USB preparation script** (`prepare-proxmox-usb.sh`) - Creates bootable USB with auto-install
- **Post-install script** (`proxmox-post-install.sh`) - Configures system for home-lab use

**Benefits:**
- ✅ Zero interaction during installation
- ✅ Consistent configuration every time
- ✅ Automatic disk partitioning (SSD for system, HDD for storage)
- ✅ Pre-configured network bridges
- ✅ Optimizations for 8GB RAM applied automatically

---

## Prerequisites

### Hardware Requirements
- ✅ Dell XPS L701X with:
  - 8 GB RAM minimum
  - 250 GB SSD (will be used for Proxmox)
  - 500 GB HDD (will be configured post-install)
  - Built-in Gigabit Ethernet
  - USB-Ethernet adapter (optional during install, required for final setup)

### Software Requirements
- Another computer to prepare the USB (Linux, Mac, or Windows with WSL)
- Proxmox VE 9 ISO image
- USB flash drive (8GB or larger)
- Files from this repository:
  - `proxmox-auto-install-answer.toml`
  - `prepare-proxmox-usb.sh`
  - `proxmox-post-install.sh`

---

## Step 1: Customize the Answer File

Before creating the USB, customize the installation settings:

### 1.1 Edit Answer File

```bash
nano proxmox-auto-install-answer.toml
```

### 1.2 Required Changes

**Change the root password:**
```toml
[global]
root_password = "YourStrongPasswordHere!"  # ⚠️ CHANGE THIS!
```

**Adjust timezone and country:**
```toml
[global]
country = "us"         # Change to your country code (e.g., "ru", "de", "uk")
timezone = "UTC"       # Change to your timezone (e.g., "Europe/Moscow", "America/New_York")
```

**Optional: Set static IP instead of DHCP:**
```toml
[network]
source = "from_answer_file"  # Change from "from_dhcp"

# Uncomment and configure:
hostname = "proxmox.home.lan"
domain = "home.lan"
address = "192.168.1.100"
netmask = "255.255.255.0"
gateway = "192.168.1.1"
dns = "8.8.8.8"
```

**Email for notifications:**
```toml
[global]
mailto = "your-email@example.com"  # Change to your email
```

### 1.3 Verify Disk Selection

Ensure the installation targets the correct disk:
```toml
[disk-setup]
disk_list = ["sda"]  # SSD (250GB) - verify this is correct!
```

⚠️ **IMPORTANT:** The answer file is configured for:
- `/dev/sda` = 250GB SSD (Proxmox system + VMs)
- `/dev/sdb` = 500GB HDD (configured post-install for backups/ISOs)

Make sure your SSD is `/dev/sda`!

---

## Step 2: Download Proxmox VE 9 ISO

### 2.1 Download from Official Source

```bash
# Visit Proxmox downloads page
# https://www.proxmox.com/en/downloads/category/iso-images-pve

# Or download directly (replace X with actual version):
wget https://www.proxmox.com/en/downloads?task=callelement&format=raw&item_id=XXX&element=f85c494b-2b32-4109-b8c1-083cca2b7db6
```

### 2.2 Verify ISO Checksum

```bash
# Download checksum file
wget https://www.proxmox.com/en/downloads/category/iso-images-pve -O checksums.txt

# Verify
sha256sum -c checksums.txt --ignore-missing
```

---

## Step 3: Prepare Bootable USB

### 3.1 Identify USB Drive

```bash
# List all drives
lsblk

# Or use:
sudo fdisk -l
```

**Example output:**
```
NAME   SIZE TYPE
sda    250G disk   # Your computer's SSD - DO NOT USE
sdb    500G disk   # Your computer's HDD - DO NOT USE
sdc     16G disk   # USB drive - THIS IS WHAT WE WANT
```

⚠️ **WARNING:** Make absolutely sure you identify the correct device! Using the wrong device will erase your data!

### 3.2 Run USB Preparation Script

```bash
# Make script executable (if not already)
chmod +x prepare-proxmox-usb.sh

# Run the script (replace /dev/sdX with your USB drive)
sudo ./prepare-proxmox-usb.sh /dev/sdc proxmox-ve_9.0-1.iso
```

**The script will:**
1. ✅ Write Proxmox ISO to USB
2. ✅ Add answer file to USB root
3. ✅ Copy post-install script to USB
4. ✅ Modify bootloader for auto-install
5. ✅ Set auto-install as default boot option

### 3.3 Verify USB Contents

```bash
# Mount USB to verify
sudo mkdir -p /mnt/usb
sudo mount /dev/sdc2 /mnt/usb  # Or /dev/sdc1 depending on partition

# Check files
ls -la /mnt/usb/
# Should see: answer.toml, proxmox-post-install.sh

sudo umount /mnt/usb
```

---

## Step 4: Prepare Dell XPS L701X

### 4.1 BIOS Configuration

1. **Boot into BIOS:**
   - Power on laptop
   - Press **F2** repeatedly during boot

2. **Configure settings:**
   ```
   Virtualization Technology (VT-x): Enabled
   VT-d (if available):              Enabled
   Boot Mode:                        UEFI
   Secure Boot:                      Disabled
   Boot Priority:                    USB First, then SSD
   ```

3. **Save and Exit:** F10

### 4.2 Hardware Setup

**CRITICAL - Disk Order:**
```
/dev/sda = 250GB SSD (this MUST be the boot disk)
/dev/sdb = 500GB HDD (optional during install)
```

If your disks are in different order, you MUST:
- Either swap them physically
- Or modify the answer file's `disk_list` setting

**Network:**
- Built-in Ethernet: Connected or disconnected (auto-detected)
- USB-Ethernet: Can be connected later

**Power:**
- Laptop must be plugged into AC power
- Recommended: Keep lid open during installation for cooling

---

## Step 5: Install Proxmox (Automated)

### 5.1 Boot from USB

1. **Insert USB drive** into Dell XPS L701X
2. **Power on** laptop
3. **Press F12** for boot menu
4. **Select USB drive** from boot menu

### 5.2 Auto-Install Process

The modified bootloader will show:
```
Proxmox VE (Auto Install)        <-- Will auto-select after 5 seconds
Proxmox VE (Install)
...
```

**What happens automatically:**
1. ✅ Reads answer file from USB
2. ✅ Partitions SSD (/dev/sda):
   - 1GB EFI partition
   - 30GB root partition
   - 8GB swap
   - Remaining space for VM storage
3. ✅ Installs Proxmox VE 9
4. ✅ Configures network (DHCP or static based on answer file)
5. ✅ Sets root password
6. ✅ Reboots automatically

**Duration:** Approximately 10-15 minutes

### 5.3 Verify Installation

After reboot:
1. Remove USB drive
2. System should boot from SSD
3. Proxmox boot screen appears
4. Login prompt appears

---

## Step 6: Post-Installation Configuration

### 6.1 Find Proxmox IP Address

**On the Proxmox host (direct access):**
```bash
# Login as root with the password from answer file
# Then check IP:
ip addr show
```

**Or check your router's DHCP leases**

### 6.2 Copy Post-Install Script to Proxmox

**Option A: From USB drive**
```bash
# On Proxmox, mount USB
mkdir -p /mnt/usb
mount /dev/sdb2 /mnt/usb  # Adjust partition number

# Copy script
cp /mnt/usb/proxmox-post-install.sh /root/
chmod +x /root/proxmox-post-install.sh

umount /mnt/usb
```

**Option B: Via SCP from another computer**
```bash
# From your computer
scp proxmox-post-install.sh root@<proxmox-ip>:/root/
```

**Option C: Download from repository**
```bash
# On Proxmox
wget https://raw.githubusercontent.com/yourusername/home-lab/master/proxmox-post-install.sh
chmod +x proxmox-post-install.sh
```

### 6.3 Run Post-Install Script

```bash
# SSH into Proxmox
ssh root@<proxmox-ip>

# Run the configuration script
bash /root/proxmox-post-install.sh
```

**The script will:**
1. ✅ Configure repositories (disable enterprise, enable no-subscription)
2. ✅ Install essential packages
3. ✅ Detect and configure network interfaces
4. ✅ Create udev rules for persistent interface names (eth-builtin, eth-usb)
5. ✅ Configure network bridges:
   - `vmbr0` - WAN Bridge (USB-Ethernet → ISP)
   - `vmbr1` - LAN Bridge (Built-in Ethernet → OpenWRT)
   - `vmbr2` - Internal Bridge (LXC containers)
   - `vmbr99` - Management Bridge (emergency access)
6. ✅ Configure HDD (/dev/sdb) for storage
7. ✅ Enable optimizations:
   - KSM (Kernel Samepage Merging) for RAM efficiency
   - Disable USB autosuspend for USB-Ethernet stability
   - Configure laptop lid behavior (no suspend)
   - Setup temperature monitoring

### 6.4 Reboot

```bash
# Reboot to apply network changes
systemctl reboot
```

---

## Step 7: Verify Configuration

### 7.1 Web Interface Access

After reboot, access Proxmox web interface:
```
https://<proxmox-ip>:8006
```

**Login:**
- Username: `root`
- Password: (from answer file)

### 7.2 Verify Network Bridges

**Via Web UI:**
- System → Network
- Should see: vmbr0, vmbr1, vmbr2, vmbr99

**Via CLI:**
```bash
# SSH into Proxmox
brctl show

# Should show:
# vmbr0: eth-usb (WAN)
# vmbr1: eth-builtin (LAN)
# vmbr2: no ports (internal)
# vmbr99: no ports (management)
```

### 7.3 Verify Storage

**Via Web UI:**
- Datacenter → Storage
- Should see:
  - `local` - Proxmox config (SSD)
  - `local-lvm` - VM disks (SSD)
  - `local-hdd` - Backups/ISOs (HDD)

**Via CLI:**
```bash
pvesm status

# Output:
# local        active
# local-lvm    active
# local-hdd    active
```

### 7.4 Verify Optimizations

```bash
# Check KSM (memory deduplication)
cat /sys/kernel/mm/ksm/pages_sharing
# If > 0, KSM is working

# Check USB power management
cat /sys/bus/usb/devices/*/power/control
# Should show "on" (not "auto")

# Check memory
free -h
# Should show ~8GB total with minimal usage

# Temperature monitoring
sensors
```

---

## Step 8: Next Steps

### 8.1 Download OPNsense ISO

```bash
# On Proxmox
cd /var/lib/vz/template/iso/
wget https://mirror.ams1.nl.leaseweb.net/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2
bunzip2 OPNsense-*.iso.bz2
```

### 8.2 Create OPNsense VM

```bash
qm create 100 \
  --name OPNsense \
  --memory 2048 \
  --cores 2 \
  --cpu host \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:32 \
  --ide2 local:iso/OPNsense-24.7-dvd-amd64.iso,media=cdrom \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr1 \
  --net2 virtio,bridge=vmbr2 \
  --net3 virtio,bridge=vmbr99 \
  --boot order=scsi0 \
  --onboot 1 \
  --startup order=1

# Start VM
qm start 100
```

### 8.3 Configure OPNsense

Follow the OPNsense installation wizard, then configure according to:
- `opnsense-interfaces-config.txt` - Interface configuration
- See `README.md` for complete OPNsense setup

### 8.4 Configure OpenWRT

Connect and configure OpenWRT router:
- See `GL-AX1800-NOTES.md` - Hardware specifics
- See `openwrt-home-*` files - Home mode configuration
- See `openwrt-travel-*` files - Travel mode configuration

---

## Troubleshooting

### Issue: Auto-install doesn't start

**Solution:**
```bash
# Manual boot parameter
# At Proxmox boot menu, press 'e' to edit
# Add to kernel line:
auto-install-cfg=/dev/disk/by-label/PROXMOX/answer.toml
```

### Issue: Wrong disk selected during install

**Problem:** Installation goes to HDD instead of SSD

**Solution:**
1. Check BIOS boot order - SSD should be first
2. Verify answer file `disk_list = ["sda"]`
3. Check actual disk names: `lsblk`

### Issue: Network interfaces not detected

**Solution:**
```bash
# On Proxmox after install
ip link show

# Find actual names, then:
nano /etc/network/interfaces
# Update interface names manually

# Apply:
ifreload -a
```

### Issue: USB-Ethernet unstable

**Solutions:**
```bash
# 1. Check USB port (prefer USB 3.0)
lsusb -t

# 2. Disable power management (already done by post-install)
cat /sys/bus/usb/devices/*/power/control

# 3. Check driver
ethtool -i eth-usb

# 4. Monitor link
ethtool eth-usb | grep "Link detected"
```

### Issue: Out of memory with 8GB RAM

**Solutions:**
```bash
# 1. Verify KSM is running
systemctl status ksm
cat /sys/kernel/mm/ksm/pages_sharing

# 2. Check actual usage
free -h
htop

# 3. Reduce VM/LXC memory
qm set 100 --memory 2048  # OPNsense
pct set 200 --memory 512  # LXC container

# 4. Don't run too many VMs simultaneously
```

### Issue: Post-install script fails

**Solution:**
```bash
# Run manually with debug
bash -x /root/proxmox-post-install.sh

# Or step-by-step sections:
# Repositories
rm /etc/apt/sources.list.d/pve-enterprise.list
echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list
apt update

# Network (review before applying!)
nano /etc/network/interfaces
ifreload -a
```

### Issue: Can't access Web UI

**Solutions:**
```bash
# 1. Check service status
systemctl status pveproxy
systemctl status pvedaemon

# 2. Restart services
systemctl restart pveproxy pvedaemon

# 3. Check firewall
iptables -L -n

# 4. Try from Proxmox host
curl -k https://localhost:8006
```

---

## Advanced Configuration

### Custom Disk Layout

To use a different disk layout, modify the answer file:

```toml
[disk-setup]
# Use ZFS mirror instead of ext4
filesystem = "zfs (RAID1)"
disk_list = ["sda", "sdb"]  # Mirror across both disks

# Or ZFS single disk
filesystem = "zfs (RAID0)"
disk_list = ["sda"]
```

### Multiple Network Interfaces

If you have additional NICs, modify post-install network config:

```bash
# Add to /etc/network/interfaces
auto eth2
iface eth2 inet manual

auto vmbr3
iface vmbr3 inet static
    address 10.0.40.1/24
    bridge-ports eth2
    bridge-stp off
    bridge-fd 0
```

### Storage Optimization

```bash
# Add additional storage locations
pvesm add dir local-nvme --path /mnt/nvme --content images,rootdir
pvesm add nfs backup-nas --server 192.168.1.10 --export /backup --content backup
```

---

## Security Hardening

### Post-Installation Security Steps

```bash
# 1. Update system
apt update && apt full-upgrade -y

# 2. Setup SSH key authentication
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
# Paste your public key

# 3. Disable password authentication (after testing key!)
nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
systemctl restart sshd

# 4. Setup firewall
apt install ufw
ufw allow 22/tcp    # SSH
ufw allow 8006/tcp  # Proxmox Web
ufw enable

# 5. Enable automatic updates (optional)
apt install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

---

## Files Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `proxmox-auto-install-answer.toml` | Installation automation | Edit before creating USB |
| `prepare-proxmox-usb.sh` | USB creation script | Run on preparation computer |
| `proxmox-post-install.sh` | Post-install config | Run on Proxmox after first boot |
| `proxmox-network-interfaces` | Network config reference | Manual comparison |
| `DELL-XPS-L701X-NOTES.md` | Hardware specifics | Troubleshooting, optimization |
| `DELL-XPS-SETUP-GUIDE.md` | Manual install guide | Alternative to auto-install |

---

## FAQ

**Q: Can I use this on different hardware?**
A: Yes, but review and modify:
- Answer file `disk_list` (target disk)
- Post-install script interface detection
- RAM optimizations if you have more/less than 8GB

**Q: Does this work with Proxmox 8?**
A: The answer file format changed in Proxmox 9. For Proxmox 8, use the legacy answer file format (different syntax).

**Q: Can I customize the answer file for RAID?**
A: Yes, change `filesystem` to `zfs (RAID1)` or `zfs (RAID10)` and add multiple disks to `disk_list`.

**Q: What if I don't have a USB-Ethernet adapter during install?**
A: Fine! The post-install script will work without it. Configure USB-Ethernet later by re-running the script or manually updating `/etc/network/interfaces`.

**Q: How do I redo the installation?**
A: Boot from USB again. The installer will overwrite the existing Proxmox installation.

**Q: Can I use WiFi instead of Ethernet?**
A: Not recommended for WAN/LAN, but you can use WiFi for management by:
1. Adding WiFi to vmbr99 bridge
2. Configuring WiFi with `wpa_supplicant`

---

## Related Documentation

- 📖 `README.md` - Complete home-lab overview
- 📖 `DELL-XPS-L701X-NOTES.md` - Hardware optimization guide
- 📖 `DELL-XPS-SETUP-GUIDE.md` - Manual installation guide
- 📖 `GL-AX1800-NOTES.md` - OpenWRT router configuration
- 📖 `QUICK-REFERENCE.md` - Command quick reference

---

## Support

**Issues with:**
- **Proxmox VE:** https://forum.proxmox.com
- **This setup:** Create issue in repository
- **OPNsense:** https://forum.opnsense.org
- **OpenWRT:** https://forum.openwrt.org

---

**Created:** 2024-10-05
**For:** Dell XPS L701X Home Lab Project
**Proxmox Version:** VE 9.x
