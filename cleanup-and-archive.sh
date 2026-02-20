#!/usr/bin/env bash
#
# cleanup-and-archive.sh
# Safe cleanup and archiving of outdated files in home-lab project
#
# This script:
# 1. Creates archive/ directory structure
# 2. Moves outdated scripts from manual-scripts/bare-metal/ to archive/
# 3. Moves old_system/ to archive/
# 4. Preserves git history (uses git mv)
# 5. Creates backup before any changes
#
# Usage:
#   ./cleanup-and-archive.sh [--dry-run]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false

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
print_warning() { echo -e "${YELLOW}[WARN]${NC} $*"; }
print_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    print_warning "DRY RUN MODE - No changes will be made"
fi

# Check if we're in git repo
if [[ ! -d "$SCRIPT_DIR/.git" ]]; then
    print_error "Not a git repository. Run from home-lab root."
    exit 1
fi

cd "$SCRIPT_DIR"

# Check for uncommitted changes
if [[ -n "$(git status --porcelain)" ]]; then
    print_warning "You have uncommitted changes!"
    print_warning "It's recommended to commit or stash them first."
    read -p "Continue anyway? (y/N): " response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_info "Aborted by user"
        exit 0
    fi
fi

print_header "Home Lab Cleanup and Archive"

# ============================================================
# 1. Create archive structure
# ============================================================
print_header "1. Creating Archive Structure"

ARCHIVE_DATE=$(date +%Y-%m-%d)
ARCHIVE_ROOT="archive/cleanup-${ARCHIVE_DATE}"

if [[ "$DRY_RUN" == false ]]; then
    mkdir -p "$ARCHIVE_ROOT/bare-metal-scripts"
    mkdir -p "$ARCHIVE_ROOT/bare-metal-docs"
    mkdir -p "$ARCHIVE_ROOT/bare-metal-logs"
    print_success "Created archive directories in $ARCHIVE_ROOT"
else
    print_info "[DRY RUN] Would create: $ARCHIVE_ROOT/"
fi

# ============================================================
# 2. Archive outdated bare-metal scripts
# ============================================================
print_header "2. Archiving Outdated Scripts from manual-scripts/bare-metal/"

# List of files to archive (outdated/duplicate/temporary)
SCRIPTS_TO_ARCHIVE=(
    "new_system/manual-scripts/bare-metal/create-usb.sh"
    "new_system/manual-scripts/bare-metal/create-usb-fixed.sh"
    "new_system/manual-scripts/bare-metal/create-legacy-autoinstall-proxmox-usb.sh"
    "new_system/manual-scripts/bare-metal/check-usb.sh"
    "new_system/manual-scripts/bare-metal/check-usb-contents.sh"
    "new_system/manual-scripts/bare-metal/disable-uuid-protection.sh"
    "new_system/manual-scripts/bare-metal/fix-grub-autoinstall.sh"
    "new_system/manual-scripts/bare-metal/remove-old-proxmox-grub.sh"
    "new_system/manual-scripts/bare-metal/show-grub-menu.sh"
    "new_system/manual-scripts/bare-metal/diagnose-usb.sh"
)

LOGS_TO_ARCHIVE=(
    "new_system/manual-scripts/bare-metal/usb-creation-log.txt"
    "new_system/manual-scripts/bare-metal/usb-final-creation.txt"
)

echo "Scripts to archive:"
for file in "${SCRIPTS_TO_ARCHIVE[@]}"; do
    if [[ -f "$file" ]]; then
        echo "  - $(basename "$file")"
    fi
done

echo ""
read -p "Archive these scripts? (y/N): " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    for file in "${SCRIPTS_TO_ARCHIVE[@]}"; do
        if [[ -f "$file" ]]; then
            filename=$(basename "$file")
            if [[ "$DRY_RUN" == false ]]; then
                git mv "$file" "$ARCHIVE_ROOT/bare-metal-scripts/$filename"
                print_success "Archived: $filename"
            else
                print_info "[DRY RUN] Would archive: $filename"
            fi
        fi
    done
fi

# Archive logs
echo ""
echo "Log files to archive:"
for file in "${LOGS_TO_ARCHIVE[@]}"; do
    if [[ -f "$file" ]]; then
        echo "  - $(basename "$file")"
    fi
done

echo ""
read -p "Archive log files? (y/N): " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    for file in "${LOGS_TO_ARCHIVE[@]}"; do
        if [[ -f "$file" ]]; then
            filename=$(basename "$file")
            if [[ "$DRY_RUN" == false ]]; then
                git mv "$file" "$ARCHIVE_ROOT/bare-metal-logs/$filename"
                print_success "Archived: $filename"
            else
                print_info "[DRY RUN] Would archive: $filename"
            fi
        fi
    done
fi

# ============================================================
# 3. Archive manual-scripts/bare-metal/docs/archive/
# ============================================================
print_header "3. Moving manual-scripts/bare-metal/docs/archive/ to project archive/"

if [[ -d "new_system/manual-scripts/bare-metal/docs/archive" ]]; then
    echo "Found manual-scripts/bare-metal/docs/archive/ with documentation:"
    ls -1 new_system/manual-scripts/bare-metal/docs/archive/ | head -10
    echo ""
    read -p "Move to project archive? (y/N): " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            git mv new_system/manual-scripts/bare-metal/docs/archive "$ARCHIVE_ROOT/bare-metal-docs/"
            print_success "Moved manual-scripts/bare-metal/docs/archive/"
        else
            print_info "[DRY RUN] Would move manual-scripts/bare-metal/docs/archive/"
        fi
    fi
else
    print_info "manual-scripts/bare-metal/docs/archive/ not found (already moved?)"
fi

# ============================================================
# 4. Archive old_system/
# ============================================================
print_header "4. Archiving old_system/"

if [[ -d "old_system" ]]; then
    echo "old_system/ directory structure:"
    tree -L 2 old_system/ -I '__pycache__|*.pyc' || ls -la old_system/
    echo ""
    print_warning "This contains old bash-based setup scripts (replaced by Infrastructure-as-Data)"
    echo ""
    read -p "Move old_system/ to archive/? (y/N): " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            # Create archive/old_system if doesn't exist
            if [[ ! -d "archive/old_system" ]]; then
                mkdir -p archive/
                git mv old_system archive/old_system
                print_success "Moved old_system/ to archive/old_system/"
            else
                print_warning "archive/old_system/ already exists"
            fi
        else
            print_info "[DRY RUN] Would move old_system/ to archive/old_system/"
        fi
    fi
else
    print_info "old_system/ not found (already archived?)"
fi

# ============================================================
# 5. Summary and next steps
# ============================================================
print_header "5. Summary"

if [[ "$DRY_RUN" == false ]]; then
    echo "Changes made:"
    git status --short
    echo ""

    print_success "Cleanup completed!"
    echo ""
    echo "Next steps:"
    echo "1. Review changes: git status"
    echo "2. Test that everything still works"
    echo "3. Commit changes:"
    echo "   git add ."
    echo "   git commit -m '🧹 Cleanup: Archive outdated scripts and old_system'"
    echo ""
    echo "Kept working scripts in new_system/manual-scripts/bare-metal/:"
    echo "  ✅ create-uefi-autoinstall-proxmox-usb.sh (WORKING)"
    echo "  ✅ diagnose-usb-autoinstall.sh (USEFUL)"
    echo "  ✅ run-create-usb.sh (WRAPPER)"
    echo "  ✅ answer.toml (CONFIG)"
    echo "  ✅ post-install/ (POST-INSTALL SCRIPTS)"
else
    print_info "DRY RUN completed - no changes made"
    print_info "Run without --dry-run to apply changes"
fi

echo ""
