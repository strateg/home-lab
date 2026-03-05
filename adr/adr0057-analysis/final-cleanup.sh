#!/bin/bash
# Final cleanup: Remove duplicate ADR 0057 files from adr/ folder
# Files have been copied to adr0057-analysis/, now remove originals

set -e

echo "========================================"
echo "ADR 0057 Final Cleanup"
echo "========================================"
echo ""
echo "This will DELETE the following files from adr/:"
echo "  - 15 Phase 1 progress files"
echo "  - 2 other analysis files"
echo "  - 2 commit helper scripts"
echo ""
echo "Files are already backed up in adr/adr0057-analysis/"
echo ""
read -p "Continue? (yes/no): " confirm

if [[ "$confirm" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Deleting Phase 1 files..."
rm -f adr/0057-PHASE1-*.md
echo "  Phase 1 files deleted"

echo ""
echo "Deleting other analysis files..."
rm -f adr/0057-DETECT-SECRETS-FIXED.md
rm -f adr/0057-FINAL-FIX.md

echo ""
echo "Deleting commit helper scripts..."
rm -f adr/0057-commit-phase1.bat
rm -f adr/0057-commit-phase1.sh

echo ""
echo "========================================"
echo "Cleanup Complete!"
echo "========================================"
echo ""
echo "Remaining ADR 0057 files in adr/:"
ls adr/0057-*.md 2>/dev/null || echo "  (none - all moved to analysis folder)"

echo ""
echo "Expected: Only core ADR files should remain:"
echo "  - 0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md"
echo "  - 0057-migration-plan.md"
echo ""
