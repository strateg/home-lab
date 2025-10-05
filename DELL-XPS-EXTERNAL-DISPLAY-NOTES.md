# Dell XPS L701X - External Display Boot Configuration

## Problem

Dell XPS L701X with broken internal screen requires external monitor via Mini DisplayPort. **Mini DisplayPort only works in graphical/GUI mode**, not in console/text mode.

## Solution

Boot with special kernel parameters that force graphical framebuffer mode.

---

## Required Boot Parameters

```bash
# Essential parameters for Mini DisplayPort output:
video=vesafb:ywrap,mtrr   # Enable VESA framebuffer
vga=791                    # Set 1024x768 16-bit color mode
nomodeset                  # Prevent kernel mode setting (keeps framebuffer active)
```

### Alternative VGA Modes

If `vga=791` doesn't work, try these:

| Code | Resolution | Color Depth |
|------|------------|-------------|
| 788  | 800x600    | 16-bit (65k colors) |
| 791  | 1024x768   | 16-bit (recommended) |
| 794  | 1280x1024  | 16-bit |
| 775  | 1024x768   | 24-bit |

---

## Hardware Connection Sequence

**CRITICAL ORDER:**

1. **Connect external monitor** to Mini DisplayPort
2. **Power ON external monitor** first
3. **Insert USB** drive
4. **Power ON laptop**
5. **Press F12** for boot menu

❌ **Don't:** Power on laptop first, then connect monitor (won't work)
✅ **Do:** Connect monitor first, then power on laptop

---

## BIOS Configuration

Press **F2** during boot to enter BIOS:

### Required Settings:

```
Advanced → Video:
  Primary Display: Auto (or External if available)

Boot:
  Boot Mode: Legacy/UEFI (try both)
  Secure Boot: DISABLED

Boot Sequence:
  1. USB Storage Device
  2. Internal Hard Drive
```

### Important Notes:

- **Legacy Boot** tends to work better with external displays
- **UEFI Boot** may require GOP (Graphics Output Protocol) support
- Try **BOTH** boot modes if one doesn't work

---

## Boot Menu Options (F12)

When you press F12, you'll see multiple USB options:

```
Boot Options:
  USB Storage Device           ← Try this (Legacy/BIOS boot)
  UEFI: USB SanDisk...        ← Try this (UEFI boot)
  Hard Drive
  CD/DVD
```

**Try BOTH USB options** - one may work when the other doesn't.

---

## Proxmox Installation Boot Process

### What You Should See:

```
1. GRUB Menu appears on external display:
   ┌─────────────────────────────────────────────┐
   │ Install Proxmox VE (Automated - GUI Mode)   │ ← Auto-selected
   │ Install Proxmox VE (Manual)                 │
   └─────────────────────────────────────────────┘

2. Press ENTER or wait 5 seconds

3. Graphical installer loads:
   - Proxmox logo appears
   - Progress bar visible
   - Installation proceeds automatically

4. Installation completes (~10-15 min)

5. System reboots automatically
```

### If External Display Stays Black:

**Troubleshooting steps:**

1. **Wait 30 seconds** - boot may be slow
2. **Check monitor input** - ensure it's set to Mini DisplayPort
3. **Try other boot mode:**
   - Reboot → F12 → Select **other** USB option (UEFI vs Legacy)
4. **Check BIOS video settings:**
   - F2 → Video → Primary Display → External
5. **Try different VGA mode:**
   - Edit boot parameters (see below)

---

## Manual Boot Parameter Edit

If you need to manually add parameters:

### At GRUB Menu:

1. **Press 'e'** to edit boot entry
2. Find line starting with: `linux /boot/linux26`
3. Add at the end:
   ```
   video=vesafb:ywrap,mtrr vga=791 nomodeset
   ```
4. **Press Ctrl+X** or **F10** to boot

### Example:

```bash
# Before:
linux /boot/linux26 ro quiet

# After:
linux /boot/linux26 ro quiet video=vesafb:ywrap,mtrr vga=791 nomodeset
```

---

## After Installation

### First Boot Issues:

After installation completes and system reboots, the external display may:

**Go black during reboot** - This is normal:
1. Wait for Proxmox to boot (~30 seconds)
2. Display should activate when Proxmox kernel loads
3. You'll see Proxmox boot screen

**Stay black** - Fix with kernel parameters:

```bash
# On another computer, create file on USB:
# /etc/default/grub

GRUB_CMDLINE_LINUX_DEFAULT="quiet video=vesafb:ywrap,mtrr vga=791 nomodeset"

# Then SSH into Proxmox and run:
update-grub
```

---

## Permanent Fix for Proxmox

After successful installation, make graphics settings permanent:

### SSH into Proxmox:

```bash
ssh root@<proxmox-ip>
```

### Edit GRUB config:

```bash
nano /etc/default/grub

# Find line:
GRUB_CMDLINE_LINUX_DEFAULT="quiet"

# Change to:
GRUB_CMDLINE_LINUX_DEFAULT="quiet video=vesafb:ywrap,mtrr vga=791 nomodeset"

# Save (Ctrl+O, Enter, Ctrl+X)
```

### Update GRUB:

```bash
update-grub
reboot
```

Now external display will work on every boot.

---

## Testing Display Output

### Before Installation:

Create a test USB with any Linux live distro and boot with:
```
linux ... video=vesafb:ywrap,mtrr vga=791 nomodeset
```

If you see output, the parameters work.

### Check Framebuffer:

```bash
# After boot, check if framebuffer is active:
cat /proc/fb

# Should show:
0 VESA VGA
```

---

## Alternative: Serial Console Access

If external display still doesn't work, you can use serial console:

### Boot Parameters:

```bash
console=tty0 console=ttyS0,115200n8
```

Connect USB-to-Serial adapter to laptop's serial port (if available) and use:

```bash
# From another computer:
screen /dev/ttyUSB0 115200
```

---

## Known Issues & Solutions

### Issue: Display works in GRUB but not installer

**Solution:** Installer may be using different graphics mode
```bash
# Add to boot parameters:
vga=ask

# This will prompt for VGA mode
# Try different modes until one works
```

### Issue: Display flickers or corrupted

**Solution:** Try different VESA mode
```bash
# Instead of vga=791, try:
vga=788    # 800x600
vga=775    # 1024x768 24-bit
```

### Issue: Display works but very slow

**Solution:** Disable unnecessary graphics features
```bash
# Add:
nofb nomodeset video=vesa:off
```

---

## Quick Reference Card

**Print this and keep near laptop:**

```
╔══════════════════════════════════════════════════╗
║  Dell XPS L701X External Display Boot Guide     ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  1. Connect monitor to Mini DisplayPort         ║
║  2. Power ON monitor                            ║
║  3. Insert USB                                  ║
║  4. Power ON laptop                             ║
║  5. Press F12 → Select USB                      ║
║  6. Press ENTER on "Automated - GUI Mode"       ║
║                                                  ║
║  Boot Parameters (if manual needed):            ║
║  video=vesafb:ywrap,mtrr vga=791 nomodeset     ║
║                                                  ║
║  Troubleshooting:                               ║
║  - Black screen? Try OTHER USB option in F12    ║
║  - Still black? F2 → Boot Mode → Legacy         ║
║  - Still black? Edit parameters → vga=788       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

---

## References

- Dell XPS L701X Service Manual
- Linux Framebuffer Documentation: `/usr/src/linux/Documentation/fb/`
- VESA BIOS Extensions: https://en.wikipedia.org/wiki/VESA_BIOS_Extensions

---

**Created:** 2024-10-05
**For:** Dell XPS L701X Home Lab Project
**Issue:** Broken internal display, Mini DisplayPort only works in GUI mode
