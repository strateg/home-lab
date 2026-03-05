#!/bin/bash
# Move all ADR 0057 analysis files to adr0057-analysis folder

set -e

echo "Moving ADR 0057 analysis files to adr0057-analysis/"

# Create phase1 subfolder if not exists
mkdir -p adr/adr0057-analysis/phase1/

# Move Phase 1 files
echo "Moving Phase 1 progress files..."
mv adr/0057-PHASE1-COMPLETE.md adr/adr0057-analysis/phase1/complete.md 2>/dev/null || true
mv adr/0057-PHASE1-DAY1-SUMMARY.md adr/adr0057-analysis/phase1/day1-summary.md 2>/dev/null || true
mv adr/0057-PHASE1-DAY2-SUMMARY.md adr/adr0057-analysis/phase1/day2-summary.md 2>/dev/null || true
mv adr/0057-PHASE1-DAY3-COMPLETION.md adr/adr0057-analysis/phase1/day3-completion.md 2>/dev/null || true
mv adr/0057-PHASE1-FILE-PREP.md adr/adr0057-analysis/phase1/file-prep.md 2>/dev/null || true
mv adr/0057-PHASE1-FIXED-COMMITTED.md adr/adr0057-analysis/phase1/fixed-committed.md 2>/dev/null || true
mv adr/0057-PHASE1-MINIMAL-TEMPLATE.md adr/adr0057-analysis/phase1/minimal-template.md 2>/dev/null || true
mv adr/0057-PHASE1-PROGRESS.md adr/adr0057-analysis/phase1/progress.md 2>/dev/null || true
mv adr/0057-PHASE1-QUICK-STATUS.md adr/adr0057-analysis/phase1/quick-status.md 2>/dev/null || true
mv adr/0057-PHASE1-QUICK-UPDATE.md adr/adr0057-analysis/phase1/quick-update.md 2>/dev/null || true
mv adr/0057-PHASE1-SANITIZATION-COMPLETE.md adr/adr0057-analysis/phase1/sanitization-complete.md 2>/dev/null || true
mv adr/0057-PHASE1-SECRET-INTEGRATION.md adr/adr0057-analysis/phase1/secret-integration.md 2>/dev/null || true
mv adr/0057-PHASE1-SECURITY-ISSUE.md adr/adr0057-analysis/phase1/security-issue.md 2>/dev/null || true
mv adr/0057-PHASE1-TEMPLATE-AUDIT.md adr/adr0057-analysis/phase1/template-audit.md 2>/dev/null || true
mv adr/0057-PHASE1-TOOL-SELECTION.md adr/adr0057-analysis/phase1/tool-selection.md 2>/dev/null || true

# Move other analysis files
echo "Moving other analysis files..."
mv adr/0057-DETECT-SECRETS-FIXED.md adr/adr0057-analysis/detect-secrets-fixed.md 2>/dev/null || true
mv adr/0057-FINAL-FIX.md adr/adr0057-analysis/final-fix.md 2>/dev/null || true
mv adr/README-0057-PHASE1.md adr/adr0057-analysis/phase1-readme-original.md 2>/dev/null || true

# Note: QUICK-REVIEW and COMPLETION-REPORT already moved
echo "Note: 0057-QUICK-REVIEW.md already in 04-historical-quick-review-2026-03-02.md"
echo "Note: ADR-0057-COMPLETION-REPORT.md already in 05-historical-completion-report-2026-03-02.md"

echo ""
echo "✅ Done! All analysis files moved to adr/adr0057-analysis/"
echo ""
echo "Remaining in adr/:"
ls adr/0057-*.md 2>/dev/null || echo "  (all moved)"
