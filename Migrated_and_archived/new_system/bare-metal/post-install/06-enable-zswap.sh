#!/bin/bash
#
# Enable ZSwap for Proxmox VE
# Improves performance when RAM is constrained by compressing swap in memory
#
# Usage: ./06-enable-zswap.sh

set -euo pipefail

SCRIPT_NAME="Enable ZSwap"
LOG_FILE="/var/log/proxmox-post-install-zswap.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo ""
    echo "======================================================================" | tee -a "$LOG_FILE"
    echo "  $1" | tee -a "$LOG_FILE"
    echo "======================================================================" | tee -a "$LOG_FILE"
    echo ""
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
   exit 1
fi

header "$SCRIPT_NAME"

# ============================================================
# Step 1: Check current kernel parameters
# ============================================================

log "Checking current kernel parameters..."
CURRENT_CMDLINE=$(cat /proc/cmdline)
log "Current cmdline: $CURRENT_CMDLINE"

if grep -q "zswap.enabled=1" /proc/cmdline; then
    warn "ZSwap is already enabled in kernel cmdline"
    log "Current ZSwap status:"
    cat /sys/module/zswap/parameters/* 2>/dev/null || true
    exit 0
fi

# ============================================================
# Step 2: Configure ZSwap kernel parameters
# ============================================================

header "Configuring ZSwap Kernel Parameters"

ZSWAP_PARAMS="zswap.enabled=1 zswap.compressor=zstd zswap.max_pool_percent=25 zswap.zpool=z3fold"

log "Adding ZSwap parameters: $ZSWAP_PARAMS"

# Get current kernel cmdline from Proxmox config
if [[ ! -f /etc/kernel/cmdline ]]; then
    error "/etc/kernel/cmdline not found. Are you running Proxmox VE?"
    exit 1
fi

CURRENT_CONFIG=$(cat /etc/kernel/cmdline)
log "Current /etc/kernel/cmdline: $CURRENT_CONFIG"

# Backup original cmdline
cp /etc/kernel/cmdline /etc/kernel/cmdline.bak
log "Backed up to /etc/kernel/cmdline.bak"

# Add ZSwap parameters
echo "$CURRENT_CONFIG $ZSWAP_PARAMS" > /etc/kernel/cmdline

log "Updated /etc/kernel/cmdline:"
cat /etc/kernel/cmdline | tee -a "$LOG_FILE"

# ============================================================
# Step 3: Refresh Proxmox boot configuration
# ============================================================

header "Updating Boot Configuration"

log "Running proxmox-boot-tool refresh..."
proxmox-boot-tool refresh

if [[ $? -ne 0 ]]; then
    error "Failed to refresh boot configuration"
    log "Restoring backup..."
    mv /etc/kernel/cmdline.bak /etc/kernel/cmdline
    exit 1
fi

log "Boot configuration updated successfully"

# ============================================================
# Step 4: Install zstd compressor module
# ============================================================

header "Installing ZStd Compression Module"

log "Ensuring zstd module is available..."
modprobe zstd 2>/dev/null || warn "zstd module not available (will be loaded on next boot)"

# Add to modules for autoload
if ! grep -q "^zstd$" /etc/modules; then
    echo "zstd" >> /etc/modules
    log "Added zstd to /etc/modules for autoload"
fi

# ============================================================
# Step 5: Verify configuration
# ============================================================

header "ZSwap Configuration Summary"

log "ZSwap will be enabled with the following settings:"
echo "  - Enabled: yes" | tee -a "$LOG_FILE"
echo "  - Compressor: zstd (high compression, fast)" | tee -a "$LOG_FILE"
echo "  - Max pool: 25% of RAM (~2GB)" | tee -a "$LOG_FILE"
echo "  - Pool type: z3fold (memory efficient)" | tee -a "$LOG_FILE"

warn "REBOOT REQUIRED to activate ZSwap"

# ============================================================
# Step 6: Create verification script
# ============================================================

cat > /usr/local/bin/check-zswap.sh << 'VERIFY_SCRIPT'
#!/bin/bash
echo "ZSwap Status:"
echo "============="
if [[ -d /sys/module/zswap/parameters ]]; then
    echo "Enabled: $(cat /sys/module/zswap/parameters/enabled)"
    echo "Compressor: $(cat /sys/module/zswap/parameters/compressor)"
    echo "Max Pool Percent: $(cat /sys/module/zswap/parameters/max_pool_percent)"
    echo "Zpool: $(cat /sys/module/zswap/parameters/zpool)"
    echo ""
    if [[ -f /sys/kernel/debug/zswap/pool_total_size ]]; then
        echo "Pool Size: $(cat /sys/kernel/debug/zswap/pool_total_size) bytes"
        echo "Stored Pages: $(cat /sys/kernel/debug/zswap/stored_pages)"
    fi
else
    echo "ZSwap is NOT active"
fi
VERIFY_SCRIPT

chmod +x /usr/local/bin/check-zswap.sh
log "Created verification script: /usr/local/bin/check-zswap.sh"

# ============================================================
# Completion
# ============================================================

header "Configuration Complete"

echo ""
log "${GREEN}✅ ZSwap has been configured successfully${NC}"
echo ""
log "Next steps:"
echo "  1. Reboot the system: reboot"
echo "  2. After reboot, verify ZSwap: /usr/local/bin/check-zswap.sh"
echo ""
log "Expected benefits:"
echo "  - Reduced swap I/O to disk"
echo "  - Faster swap performance (RAM compression vs disk)"
echo "  - Better overall system responsiveness under memory pressure"
echo ""

log "Script completed at $(date)" | tee -a "$LOG_FILE"
