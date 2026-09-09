# Peripheral Secrets Migration Guide

## New Secrets Structure

All peripheral secrets files should follow this structure:

### USB Network Adapter / Hub with Ethernet
```yaml
# File: usb-wifi-asus-001.yaml or usb-hub-bluecloud-001.yaml
device_id: "ASUS-AX55-XXXXXX"  # Serial number or asset tag
mac_address: "AA:BB:CC:DD:EE:FF"
linux_interface: "enx..."  # Derived from MAC, predictable name
```

### Bluetooth HID Device
```yaml
# File: bt-hid-logitech-m720-001.yaml
device_id: "LOGI-M720-XXXXXX"  # Serial number
pairing_mac: "AA:BB:CC:DD:EE:FF"  # BT MAC address
# Optional: pairing info for each host
paired_hosts:
  host1: "paired"
  host2: "paired"
```

## Migration Steps

1. Rename existing files to match new naming convention:
   ```bash
   cd projects/home-lab/secrets/peripherals/

   # Decrypt, rename, re-encrypt
   sops -d usb-hub-eth-bluecloud-001.yaml > /tmp/hub.yaml
   # Add device_id field to /tmp/hub.yaml
   sops -e /tmp/hub.yaml > usb-hub-bluecloud-001.yaml
   rm /tmp/hub.yaml

   sops -d usb-wifi-asus-ax55-nano-001.yaml > /tmp/wifi.yaml
   # Add device_id field to /tmp/wifi.yaml
   sops -e /tmp/wifi.yaml > usb-wifi-asus-001.yaml
   rm /tmp/wifi.yaml
   ```

2. Create new secrets file for Logitech M720:
   ```bash
   cat > /tmp/m720.yaml << 'EOF'
   device_id: "YOUR-SERIAL-HERE"
   pairing_mac: "YOUR-BT-MAC-HERE"
   EOF
   sops -e /tmp/m720.yaml > bt-hid-logitech-m720-001.yaml
   rm /tmp/m720.yaml
   ```

3. Remove old files after verification:
   ```bash
   rm usb-hub-eth-bluecloud-001.yaml
   rm usb-wifi-asus-ax55-nano-001.yaml
   ```

## Migration Status (Updated 2026-09-09)

| Old File | New File | Status |
|----------|----------|--------|
| usb-hub-eth-bluecloud-001.yaml | usb-hub-bluecloud-001.yaml | **RENAMED** |
| usb-wifi-asus-ax55-nano-001.yaml | usb-wifi-asus-001.yaml | **RENAMED** |
| (new) | bt-hid-logitech-m720-001.yaml | **TODO** - see .TODO file |

Note: Files renamed but content not modified. Verify device_id fields are present.
