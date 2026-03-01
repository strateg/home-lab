#!/usr/bin/env bash
#
# test-prepare-iso.sh - Test proxmox-auto-install-assistant prepare-iso
# This script helps diagnose why answer.toml is not being embedded in ISO
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISO_PATH="${1:-}"
ANSWER_PATH="${2:-$SCRIPT_DIR/answer.toml}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
print_success() { echo -e "${GREEN}[OK]${NC} $*"; }
print_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ -z "$ISO_PATH" ]]; then
    print_error "Usage: $0 <proxmox-iso> [answer.toml]"
    echo "Example: $0 ~/Downloads/proxmox-ve_9.0-1.iso"
    exit 1
fi

if [[ ! -f "$ISO_PATH" ]]; then
    print_error "ISO not found: $ISO_PATH"
    exit 1
fi

if [[ ! -f "$ANSWER_PATH" ]]; then
    print_error "answer.toml not found: $ANSWER_PATH"
    exit 1
fi

print_header "Testing proxmox-auto-install-assistant prepare-iso"

print_info "ISO: $ISO_PATH"
print_info "Answer file: $ANSWER_PATH"
echo ""

# Create temp directory
TMPDIR=$(mktemp -d /tmp/test-iso.XXXX)
print_info "Temp directory: $TMPDIR"

# Create first-boot script
INSTALL_UUID="TEST_$(date +%Y_%m_%d_%H_%M)"
FIRST_BOOT="$TMPDIR/first-boot.sh"

print_info "Creating first-boot script with UUID: $INSTALL_UUID"
cat > "$FIRST_BOOT" << 'EOF'
#!/bin/bash
exec 1>>/var/log/test-first-boot.log 2>&1
echo "===== Test first-boot script started at $(date) ====="
echo "Installation ID: INSTALL_UUID_PLACEHOLDER"
echo -n "INSTALL_UUID_PLACEHOLDER" > /etc/proxmox-install-id
echo "✓ Created /etc/proxmox-install-id"
echo "===== Test first-boot completed at $(date) ====="
exit 0
EOF
sed -i "s/INSTALL_UUID_PLACEHOLDER/$INSTALL_UUID/" "$FIRST_BOOT"
chmod +x "$FIRST_BOOT"

print_success "First-boot script created"
echo ""

# Output ISO path
OUTPUT_ISO="$TMPDIR/proxmox-auto-test.iso"

print_header "Running proxmox-auto-install-assistant prepare-iso"

print_info "Command:"
echo "  proxmox-auto-install-assistant prepare-iso \\"
echo "    --fetch-from iso \\"
echo "    --answer-file '$ANSWER_PATH' \\"
echo "    --output '$OUTPUT_ISO' \\"
echo "    --tmp '$TMPDIR' \\"
echo "    --on-first-boot '$FIRST_BOOT' \\"
echo "    '$ISO_PATH'"
echo ""

# Run prepare-iso with full output
set +e
proxmox-auto-install-assistant prepare-iso \
    --fetch-from iso \
    --answer-file "$ANSWER_PATH" \
    --output "$OUTPUT_ISO" \
    --tmp "$TMPDIR" \
    --on-first-boot "$FIRST_BOOT" \
    "$ISO_PATH" 2>&1 | tee "$TMPDIR/prepare-iso.log"
EXIT_CODE=$?
set -e

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    print_success "proxmox-auto-install-assistant completed successfully"
else
    print_error "proxmox-auto-install-assistant failed with exit code: $EXIT_CODE"
    echo ""
    print_info "Full log saved to: $TMPDIR/prepare-iso.log"
    exit $EXIT_CODE
fi

print_header "Analyzing Output ISO"

if [[ ! -f "$OUTPUT_ISO" ]]; then
    print_error "Output ISO not found: $OUTPUT_ISO"
    exit 1
fi

print_success "Output ISO created: $OUTPUT_ISO"
print_info "Size: $(du -h "$OUTPUT_ISO" | cut -f1)"
echo ""

# Mount ISO and check contents
MOUNT_POINT="$TMPDIR/iso-mount"
mkdir -p "$MOUNT_POINT"

print_info "Mounting ISO to check contents..."
if sudo mount -o loop,ro "$OUTPUT_ISO" "$MOUNT_POINT" 2>/dev/null; then
    print_success "ISO mounted at: $MOUNT_POINT"
    echo ""

    print_header "Checking for auto-installer files"

    # Check for answer.toml
    if [[ -f "$MOUNT_POINT/answer.toml" ]]; then
        print_success "✓ answer.toml found in ISO root"
        echo "  First 10 lines:"
        head -10 "$MOUNT_POINT/answer.toml" | sed 's/^/    /'
    else
        print_error "✗ answer.toml NOT FOUND in ISO root"
    fi
    echo ""

    # Check for auto-installer-mode.toml
    if [[ -f "$MOUNT_POINT/auto-installer-mode.toml" ]]; then
        print_success "✓ auto-installer-mode.toml found in ISO root"
        echo "  Content:"
        cat "$MOUNT_POINT/auto-installer-mode.toml" | sed 's/^/    /'
    else
        print_error "✗ auto-installer-mode.toml NOT FOUND in ISO root"
    fi
    echo ""

    # Check for first-boot script
    if [[ -f "$MOUNT_POINT/first-boot.sh" ]]; then
        print_success "✓ first-boot.sh found in ISO root"
    else
        print_error "✗ first-boot.sh NOT FOUND in ISO root"
    fi
    echo ""

    # Check for auto-installer-capable marker
    if [[ -f "$MOUNT_POINT/auto-installer-capable" ]]; then
        print_success "✓ auto-installer-capable marker found"
    else
        print_error "✗ auto-installer-capable marker NOT FOUND"
    fi
    echo ""

    # List all files in root
    print_info "Files in ISO root (excluding directories):"
    find "$MOUNT_POINT" -maxdepth 1 -type f | sort | sed 's/^/    /'
    echo ""

    # Check GRUB config
    if [[ -f "$MOUNT_POINT/boot/grub/grub.cfg" ]]; then
        print_info "Checking GRUB config for auto-installer..."
        if grep -q "auto-installer-mode.toml" "$MOUNT_POINT/boot/grub/grub.cfg"; then
            print_success "✓ GRUB config references auto-installer-mode.toml"
        else
            print_error "✗ GRUB config does NOT reference auto-installer-mode.toml"
        fi
    fi
    echo ""

    # Unmount
    sudo umount "$MOUNT_POINT"
    print_success "ISO unmounted"
else
    print_error "Failed to mount ISO"
fi

print_header "Summary"

echo "Test completed. Files saved in: $TMPDIR"
echo ""
echo "Files:"
echo "  - Output ISO: $OUTPUT_ISO"
echo "  - Prepare-iso log: $TMPDIR/prepare-iso.log"
echo "  - First-boot script: $FIRST_BOOT"
echo ""
echo "To cleanup: rm -rf $TMPDIR"
echo ""
