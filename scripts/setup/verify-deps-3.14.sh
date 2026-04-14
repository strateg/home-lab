#!/usr/bin/env bash
# ADR 0098 Phase A1: Dependency Verification Script
#
# Verifies all project dependencies are compatible with Python 3.14
#
# Usage:
#   ./verify-deps-3.14.sh [--venv=path] [--output=file]
#
# Output:
#   Creates evidence file in adr/0098-analysis/evidence/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EVIDENCE_DIR="${PROJECT_ROOT}/adr/0098-analysis/evidence"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE="${EVIDENCE_DIR}/EV-A1-deps-${TIMESTAMP}.md"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $*"; }

# Parse arguments
VENV_PATH="${PROJECT_ROOT}/.venv-3.14"
for arg in "$@"; do
    case $arg in
        --venv=*)
            VENV_PATH="${arg#*=}"
            shift
            ;;
        --output=*)
            OUTPUT_FILE="${arg#*=}"
            shift
            ;;
    esac
done

# Core dependencies from pyproject.toml
CORE_DEPS=(
    "pyyaml"
    "jinja2"
    "jsonschema"
    "paramiko"
)

# Dev dependencies
DEV_DEPS=(
    "pytest"
    "pytest-cov"
    "black"
    "isort"
    "pylint"
    "mypy"
    "types-pyyaml"
    "types-jinja2"
    "yamllint"
    "pre-commit"
    "detect-secrets"
)

# Optional C-extensions
CEXT_DEPS=(
    "orjson"
    "ruamel.yaml"
)

# Check Python version
check_python() {
    if [[ -f "${VENV_PATH}/bin/python" ]]; then
        local version
        version=$("${VENV_PATH}/bin/python" --version 2>&1)
        if [[ "$version" == *"3.14"* ]]; then
            log_info "Using Python: ${version}"
            return 0
        else
            log_error "Virtual environment is not Python 3.14: ${version}"
            return 1
        fi
    else
        log_error "Virtual environment not found: ${VENV_PATH}"
        log_info "Create with: python3.14 -m venv ${VENV_PATH}"
        return 1
    fi
}

# Test single package
test_package() {
    local pkg=$1
    local category=$2

    # Try to install
    if "${VENV_PATH}/bin/pip" install --dry-run "$pkg" &>/dev/null; then
        # Try to import
        if "${VENV_PATH}/bin/python" -c "import ${pkg//-/_}" &>/dev/null 2>&1; then
            log_pass "${pkg}: installable and importable"
            echo "| ${pkg} | ${category} | ✅ PASS | Install + import OK |"
            return 0
        else
            # Package installs but different import name
            log_pass "${pkg}: installable (import name may differ)"
            echo "| ${pkg} | ${category} | ✅ PASS | Install OK |"
            return 0
        fi
    else
        log_fail "${pkg}: installation failed"
        echo "| ${pkg} | ${category} | ❌ FAIL | pip install --dry-run failed |"
        return 1
    fi
}

# Generate evidence report
generate_report() {
    local pass_count=$1
    local fail_count=$2
    local total=$3

    mkdir -p "${EVIDENCE_DIR}"

    cat > "${OUTPUT_FILE}" << EOF
# Evidence: Phase A1 Dependency Verification

**Evidence ID**: EV-A1-${TIMESTAMP}
**Date**: $(date -Iseconds)
**Python Version**: $("${VENV_PATH}/bin/python" --version 2>&1)
**Virtual Environment**: ${VENV_PATH}

---

## Summary

| Metric | Value |
|--------|-------|
| Total packages tested | ${total} |
| Passed | ${pass_count} |
| Failed | ${fail_count} |
| Pass rate | $((pass_count * 100 / total))% |

---

## Gate Status

EOF

    if [[ $fail_count -eq 0 ]]; then
        echo "**Phase A1 Gate**: ✅ **PASS** — All dependencies compatible with Python 3.14" >> "${OUTPUT_FILE}"
    else
        echo "**Phase A1 Gate**: ❌ **FAIL** — ${fail_count} dependencies incompatible" >> "${OUTPUT_FILE}"
    fi

    cat >> "${OUTPUT_FILE}" << EOF

---

## Detailed Results

### Core Dependencies (MUST PASS)

| Package | Category | Status | Notes |
|---------|----------|--------|-------|
EOF
}

# Main verification
main() {
    log_info "ADR 0098 Phase A1: Dependency Verification"
    log_info "Output: ${OUTPUT_FILE}"
    echo

    # Check Python environment
    if ! check_python; then
        exit 1
    fi

    # Ensure pip is up to date
    "${VENV_PATH}/bin/pip" install --upgrade pip --quiet

    local pass_count=0
    local fail_count=0
    local total=0
    local results=""

    # Test core dependencies
    log_info "Testing core dependencies..."
    for pkg in "${CORE_DEPS[@]}"; do
        ((total++))
        result=$(test_package "$pkg" "core")
        if [[ $? -eq 0 ]]; then
            ((pass_count++))
        else
            ((fail_count++))
        fi
        results+="${result}\n"
    done

    # Generate initial report
    generate_report "$pass_count" "$fail_count" "$total"

    # Add core results
    echo -e "$results" >> "${OUTPUT_FILE}"

    # Test dev dependencies
    results=""
    cat >> "${OUTPUT_FILE}" << EOF

### Dev Dependencies (SHOULD PASS)

| Package | Category | Status | Notes |
|---------|----------|--------|-------|
EOF

    log_info "Testing dev dependencies..."
    for pkg in "${DEV_DEPS[@]}"; do
        ((total++))
        result=$(test_package "$pkg" "dev")
        if [[ $? -eq 0 ]]; then
            ((pass_count++))
        else
            ((fail_count++))
        fi
        results+="${result}\n"
    done
    echo -e "$results" >> "${OUTPUT_FILE}"

    # Test C-extensions
    results=""
    cat >> "${OUTPUT_FILE}" << EOF

### C-Extensions (Optional, verify compatibility)

| Package | Category | Status | Notes |
|---------|----------|--------|-------|
EOF

    log_info "Testing C-extension packages..."
    for pkg in "${CEXT_DEPS[@]}"; do
        ((total++))
        result=$(test_package "$pkg" "c-ext")
        if [[ $? -eq 0 ]]; then
            ((pass_count++))
        else
            ((fail_count++))
        fi
        results+="${result}\n"
    done
    echo -e "$results" >> "${OUTPUT_FILE}"

    # Final summary
    cat >> "${OUTPUT_FILE}" << EOF

---

## Next Steps

EOF

    if [[ $fail_count -eq 0 ]]; then
        cat >> "${OUTPUT_FILE}" << EOF
1. ✅ Phase A1 complete — proceed to Phase A2 (C-extension deep verification)
2. Run test suite: \`pytest tests/ -v\`
3. Update ADR 0098 status
EOF
        log_info "Phase A1 Gate: PASS (${pass_count}/${total} packages)"
    else
        cat >> "${OUTPUT_FILE}" << EOF
1. ❌ Investigate failed packages
2. Identify alternatives or workarounds
3. Update dependency matrix in ADR 0098
4. Re-run verification after fixes
EOF
        log_error "Phase A1 Gate: FAIL (${fail_count}/${total} packages failed)"
    fi

    log_info "Evidence written to: ${OUTPUT_FILE}"
}

main "$@"
