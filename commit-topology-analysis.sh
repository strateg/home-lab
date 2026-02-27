#!/bin/bash
#
# Commit L0-L6 topology analysis + L6->L7 integration design to git
#
# Usage: ./commit-topology-analysis.sh [--dry-run]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# Define files to commit
FILES=(
    "L0-L6-ANALYSIS-STEP1-CURRENT-STATE.md"
    "L0-L6-ANALYSIS-STEP2-L6-MODULARIZATION.md"
    "L0-L6-ANALYSIS-STEP3-CROSS-LAYER-REDUNDANCY.md"
    "L0-L6-ANALYSIS-STEP4-L7-INTEGRATION.md"
    "L0-L6-ANALYSIS-STEP5-10X-GROWTH.md"
    "L0-L6-TOPOLOGY-ANALYSIS-SUMMARY.md"
    "L0-L6-TOPOLOGY-ANALYSIS-INDEX.md"
    "00-COMPLETE-ANALYSIS-INDEX.md"
    "L6-L7-INTEGRATION-EXECUTIVE-ANALYSIS.md"
    "L6-L7-DEEP-INTEGRATION-ANALYSIS.md"
    "L7-IMPLEMENTATION-READY-CODE.md"
    "adr/0047-l6-observability-modularization.md"
    "adr/0048-topology-evolution-10x-growth.md"
    "COMMIT-READY-SUMMARY.md"
)

COMMIT_TITLE="Docs: Complete L0–L6 topology analysis + L6→L7 integration design"

COMMIT_BODY="Comprehensive 6-step analysis of topology layers for 10x growth preparation:

✅ STEP 1: Current state audit (L0–L6)
   - Layer-by-layer analysis of purpose, dependencies, constraints, bottlenecks
   - Identified 9 bottlenecks: L3 storage O(n²), L5 service naming coupling, L6 alert explosion
   - Growth constraints: file organization, naming collisions, data duplication

✅ STEP 2: L6 observability modularization design
   - Proposed 9-module structure: metrics, healthchecks, alerts, dashboards, SLOs, incident-response, etc.
   - Template + policy pattern for alerts (reusable, scalable to 1000+ alerts)
   - Service-observability contract + API contracts for all modules

✅ STEP 3: Cross-layer redundancy & optimization analysis
   - Identified 7 major redundancies (service naming, alert binding, ports, QoS, storage chain, certs, resources)
   - Proposed unification strategy (data-driven generation from L5 services)
   - Optimization roadmap (2–3 weeks for critical path)

✅ STEP 4: L7 operations integration mapping
   - Designed L7↔L6 contract (SLO-aware, data-driven incident response)
   - Template-based runbooks resolved at runtime from L5/L6 data
   - Policy-based escalation, dependency awareness, auto-recovery

✅ STEP 5: 10x growth readiness analysis
   - Simulated 10x growth: 300 services, 70 devices, 1000+ alerts, 100+ dashboards
   - 5 critical bottlenecks identified: validator O(n²), monolithic generator, flat files, naming collisions, duplication
   - Solutions: caching, incremental generation, hierarchical organization, auto-generation

✅ STEP 6: ADRs 0047 & 0048 drafted
   - ADR 0047: L6 Observability Modularization (structure, templates, contracts)
   - ADR 0048: Topology Evolution Strategy for 10x Growth (caching, incremental gen, hierarchical naming)

🔗 EXTENDED: L6→L7 Integration Analysis (3 documents)
   - Executive summary: MTTR 6x faster (30min → 5min), zero runbook maintenance
   - Deep integration guide: 5 use cases, operational patterns, implementation phases
   - Production-ready code: Data Loader, Incident Handler, SLO Engine, Runbook Executor + tests

📊 Key Benefits:
   - Validation: 20s → 2s at 10x (10x faster)
   - Generation: 50s → 10s at 10x (5x faster)
   - Runbooks: 50 → 1 template (zero maintenance)
   - MTTR: 30min → 5min (6x faster)
   - Escalation: manual → policy-based (100% consistent)
   - Incident logging: manual → automatic (100% audit trail)

📁 Files created (14 total):
   - 5 step analysis documents (150+ pages)
   - 3 executive summaries + indices
   - 3 L6→L7 integration documents
   - 2 new ADRs (0047, 0048)
   - 1 commit-ready summary

Status: Ready for architecture review & implementation planning
Next: Phase 1 execution (2–3 weeks) → 10x scaling enabled

Phase: Topology Analysis & Design Complete ✅
Date: 2026-02-26"

# Helper functions
header() {
    echo ""
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}

step() {
    echo -e "${CYAN}→ $1${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

error() {
    echo -e "${RED}✗ $1${NC}"
}

# Main execution
header "Topology Analysis Commit Script"

# Check if git is available
step "Checking git availability..."
if ! command -v git &> /dev/null; then
    error "Git not found. Please install Git and try again."
    exit 1
fi
success "Git found: $(git --version)"

# Check if we're in a git repository
step "Checking git repository..."
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    error "Not in a git repository. Please run this script from the root of your git project."
    exit 1
fi
success "In git repository"

# Verify all files exist
step "Verifying files exist..."
MISSING_FILES=()
for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (NOT FOUND)"
        MISSING_FILES+=("$file")
    fi
done

if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    error "Missing files: ${MISSING_FILES[*]}"
    echo "Please create these files before committing."
    exit 1
fi
success "All files verified"

# Show current git status
step "Current git status..."
git status -short

# Add files to staging
step "Staging files..."
for file in "${FILES[@]}"; do
    git add "$file"
    echo -e "  ${GREEN}+${NC} $file"
done
success "All files staged"

# Show staged changes
step "Staged changes:"
git status --short | grep "^A "

# If dry-run, stop here
if [[ "$DRY_RUN" == true ]]; then
    header "DRY RUN MODE - Changes not committed"
    echo "To actually commit, run: ./commit-topology-analysis.sh"
    exit 0
fi

# Confirm before committing
header "Ready to commit"
echo "Commit message preview:"
echo ""
echo "$COMMIT_TITLE"
echo ""
echo "$COMMIT_BODY"
echo ""
read -p "Do you want to proceed with the commit? (yes/no) " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    error "Commit cancelled by user"
    git reset  # Unstage files
    exit 1
fi

# Create commit
step "Creating commit..."
git commit -m "$COMMIT_TITLE" -m "$COMMIT_BODY"
success "Commit created successfully"

# Show commit details
step "Commit details:"
git log -1 --stat

# Final summary
header "✓ Commit Complete!"

echo ""
echo -e "${CYAN}Summary:${NC}"
echo "  Files committed: ${#FILES[@]}"
echo "  Commit title: $COMMIT_TITLE"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Review commit: git log -1"
echo "  2. Check branch: git branch -v"
echo "  3. Push (if ready): git push origin <branch-name>"
echo ""
echo -e "${CYAN}Documentation index:${NC}"
echo "  📖 Start here: 00-COMPLETE-ANALYSIS-INDEX.md"
echo "  🎯 For architects: L6-L7-INTEGRATION-EXECUTIVE-ANALYSIS.md"
echo "  👨‍💻 For developers: L7-IMPLEMENTATION-READY-CODE.md"
echo ""
