#!/bin/bash
#
# diagnose-installation.sh - Analyze installed Proxmox to understand installation type
#

echo "=========================================="
echo "Proxmox Installation Diagnostics"
echo "=========================================="
echo ""

echo "1. Installation UUID:"
echo "===================="
sudo cat /mnt/proxmox-root/etc/proxmox-install-id
echo ""

echo "2. First-boot script log:"
echo "========================="
sudo cat /mnt/proxmox-root/var/log/proxmox-first-boot.log
echo ""

echo "3. Root password hash:"
echo "======================"
sudo cat /mnt/proxmox-root/etc/shadow | grep "^root:"
echo ""
echo "Expected hash (from answer.toml):"
echo '$6$c9bAqQzrLw2iQRC4$dEOmTMWdoZ20ar/IE2TQjkv3olE4jw6plQvfIFvLUcI4r.VF3R.iNuCYVvPNnoz0yQFIYxxEW8wYo4gMsjt1H1'
echo ""

echo "4. Hostname:"
echo "============"
sudo cat /mnt/proxmox-root/etc/hostname 2>/dev/null || echo "Error reading hostname"
echo ""

echo "5. Network configuration:"
echo "========================="
sudo cat /mnt/proxmox-root/etc/network/interfaces 2>/dev/null | head -30
echo ""

echo "6. Check for auto-installer log:"
echo "================================="
sudo find /mnt/proxmox-root/var/log -name "*auto*" -o -name "*install*" 2>/dev/null
echo ""

echo "7. Check systemd journal for auto-installer:"
echo "============================================="
if [ -d /mnt/proxmox-root/var/log/journal ]; then
    sudo journalctl --directory=/mnt/proxmox-root/var/log/journal --no-pager | grep -i "auto-install" | head -20
    echo ""
fi

echo "8. Check kernel command line (from first boot):"
echo "================================================"
if [ -d /mnt/proxmox-root/var/log/journal ]; then
    sudo journalctl --directory=/mnt/proxmox-root/var/log/journal --boot 0 --no-pager | grep -i "command line" | head -5
fi
echo ""

echo "9. EFI partition check:"
echo "======================="
if [ -d /mnt/proxmox-root/boot/efi ]; then
    echo "EFI mounted at /boot/efi"
    sudo ls -la /mnt/proxmox-root/boot/efi/
else
    echo "No EFI partition mounted in chroot"
fi
echo ""

echo "=========================================="
echo "Analysis:"
echo "=========================================="
echo ""

ACTUAL_HASH=$(sudo cat /mnt/proxmox-root/etc/shadow | grep "^root:" | cut -d: -f2)
EXPECTED_HASH='$6$c9bAqQzrLw2iQRC4$dEOmTMWdoZ20ar/IE2TQjkv3olE4jw6plQvfIFvLUcI4r.VF3R.iNuCYVvPNnoz0yQFIYxxEW8wYo4gMsjt1H1'

if [[ "$ACTUAL_HASH" == "$EXPECTED_HASH"* ]]; then
    echo "✓ Password hash MATCHES answer.toml (auto-installer was used)"
    echo "  Hash type: SHA-512 (\$6\$...)"
else
    echo "✗ Password hash DOES NOT MATCH answer.toml"
    echo "  This means graphical installer was used, not auto-installer"

    if [[ "$ACTUAL_HASH" == '$y$'* ]]; then
        echo "  Hash type: yescrypt (\$y\$...) - confirms graphical installer"
    elif [[ "$ACTUAL_HASH" == '$6$'* ]]; then
        echo "  Hash type: SHA-512 (\$6\$...) - but different hash than expected"
    fi
fi
echo ""

echo "Next steps:"
echo "==========="
if [[ "$ACTUAL_HASH" != "$EXPECTED_HASH"* ]]; then
    echo "1. Auto-installer did NOT activate"
    echo "2. Need to check USB GRUB configuration"
    echo "3. Verify auto-installer-mode.toml is accessible to GRUB"
    echo "4. Check if GRUB path resolution is correct"
fi
