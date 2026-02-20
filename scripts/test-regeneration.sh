#!/bin/bash
# ============================================================
# End-to-End Regeneration Workflow Test
# Home Lab Infrastructure-as-Data
# ============================================================
#
# This script validates the complete regeneration workflow:
# 1. Validate topology.yaml
# 2. Generate Terraform configuration
# 3. Generate Ansible inventory
# 4. Generate documentation
# 5. Validate Terraform syntax
# 6. Validate Ansible syntax
#
# Usage:
#   ./scripts/test-regeneration.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# ============================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT/new_system"

echo "============================================================"
echo "Infrastructure-as-Data Regeneration Test Suite"
echo "============================================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Working directory: $(pwd)"
echo ""

# ============================================================
# Helper Functions
# ============================================================

function print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

function print_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
}

function print_error() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
}

function print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

function run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
        ((TESTS_TOTAL++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        ((TESTS_FAILED++))
        ((TESTS_TOTAL++))
        return 1
    fi
}

# ============================================================
# Test 1: Validate topology.yaml
# ============================================================

print_header "Test 1: Validate topology.yaml"

if [ ! -f "topology.yaml" ]; then
    print_error "topology.yaml not found"
    exit 1
fi

print_success "topology.yaml exists"

# Check if validate script exists
if [ ! -f "scripts/topology/validate-topology.py" ]; then
    print_warning "validate-topology.py not found, skipping validation"
else
    echo ""
    echo "Running validation..."
    if python3 scripts/topology/validate-topology.py; then
        print_success "topology.yaml validation passed"
    else
        print_error "topology.yaml validation failed"
        echo ""
        echo "Fix topology.yaml errors before proceeding"
        exit 1
    fi
fi

# ============================================================
# Test 2: Generate Terraform Configuration
# ============================================================

print_header "Test 2: Generate Terraform Configuration"

if [ ! -f "scripts/topology/generate-terraform.py" ]; then
    print_error "generate-terraform.py not found"
    exit 1
fi

echo ""
echo "Generating Terraform configuration..."
if python3 scripts/topology/generate-terraform.py --output generated/terraform; then
    print_success "Terraform generation completed"
else
    print_error "Terraform generation failed"
    exit 1
fi

# Check if required files were generated
REQUIRED_TF_FILES=(
    "generated/terraform/provider.tf"
    "generated/terraform/versions.tf"
    "generated/terraform/variables.tf"
    "generated/terraform/bridges.tf"
)

for file in "${REQUIRED_TF_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "Generated: $file"
    else
        print_error "Missing: $file"
    fi
done

# ============================================================
# Test 3: Validate Terraform Syntax
# ============================================================

print_header "Test 3: Validate Terraform Syntax"

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    print_warning "Terraform not installed, skipping syntax validation"
else
    cd generated/terraform

    echo ""
    echo "Running terraform fmt check..."
    if terraform fmt -check -recursive .; then
        print_success "Terraform formatting is correct"
    else
        print_warning "Terraform formatting issues found (non-critical)"
        echo "  Run 'terraform fmt -recursive' to fix"
    fi

    echo ""
    echo "Running terraform validate..."

    # Initialize if needed
    if [ ! -d ".terraform" ]; then
        echo "Initializing Terraform..."
        if terraform init -backend=false > /dev/null 2>&1; then
            print_success "Terraform initialized"
        else
            print_warning "Terraform init failed (this is OK if providers are not available)"
        fi
    fi

    # Validate
    if terraform validate; then
        print_success "Terraform validation passed"
    else
        print_error "Terraform validation failed"
        cd ../..
        exit 1
    fi

    cd ../..
fi

# ============================================================
# Test 4: Generate Ansible Inventory
# ============================================================

print_header "Test 4: Generate Ansible Inventory"

if [ ! -f "scripts/topology/generate-ansible-inventory.py" ]; then
    print_warning "generate-ansible-inventory.py not found, skipping"
else
    echo ""
    echo "Generating Ansible inventory..."
    if python3 scripts/topology/generate-ansible-inventory.py --output generated/ansible; then
        print_success "Ansible inventory generation completed"
    else
        print_error "Ansible inventory generation failed"
        exit 1
    fi

    # Check if inventory was generated
    if [ -f "generated/ansible/inventory/hosts.yml" ]; then
        print_success "Generated: generated/ansible/inventory/hosts.yml"
    else
        print_error "Missing: generated/ansible/inventory/hosts.yml"
    fi
fi

# ============================================================
# Test 5: Validate Ansible Syntax
# ============================================================

print_header "Test 5: Validate Ansible Syntax"

# Check if Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    print_warning "Ansible not installed, skipping syntax validation"
else
    # Check if there are playbooks to validate
    if [ -d "ansible/playbooks" ] && [ "$(ls -A ansible/playbooks/*.yml 2>/dev/null)" ]; then
        echo ""
        echo "Validating Ansible playbooks..."

        for playbook in ansible/playbooks/*.yml; do
            if [ -f "$playbook" ]; then
                playbook_name=$(basename "$playbook")
                echo -n "  Checking $playbook_name... "

                if ansible-playbook "$playbook" --syntax-check > /dev/null 2>&1; then
                    echo -e "${GREEN}PASS${NC}"
                    ((TESTS_PASSED++))
                    ((TESTS_TOTAL++))
                else
                    echo -e "${RED}FAIL${NC}"
                    ((TESTS_FAILED++))
                    ((TESTS_TOTAL++))
                fi
            fi
        done
    else
        print_warning "No Ansible playbooks found, skipping validation"
    fi
fi

# ============================================================
# Test 6: Generate Documentation
# ============================================================

print_header "Test 6: Generate Documentation"

if [ ! -f "scripts/topology/generate-docs.py" ]; then
    print_warning "generate-docs.py not found, skipping"
else
    echo ""
    echo "Generating documentation..."
    if python3 scripts/topology/generate-docs.py --output generated/docs; then
        print_success "Documentation generation completed"
    else
        print_warning "Documentation generation failed (non-critical)"
    fi
fi

# ============================================================
# Test 7: Check Git Status
# ============================================================

print_header "Test 7: Check Git Status"

cd "$PROJECT_ROOT"

echo ""
echo "Checking for uncommitted changes in generated files..."

# Check if there are changes in generated/
if git diff --quiet new_system/generated/; then
    print_success "No uncommitted changes in generated/ (up to date)"
else
    print_warning "Uncommitted changes detected in generated/"
    echo ""
    echo "Changed files:"
    git diff --name-only new_system/generated/ | sed 's/^/  - /'
    echo ""
    echo "This is expected if you just modified topology.yaml"
    echo "Commit these changes with: git add new_system/generated/ && git commit"
fi

# ============================================================
# Test 8: Idempotency Check
# ============================================================

print_header "Test 8: Idempotency Check"

echo ""
echo "Running generators a second time to check idempotency..."

cd "$PROJECT_ROOT/new_system"

# Save current state
TEMP_DIR=$(mktemp -d)
cp -r generated/ "$TEMP_DIR/generated-before"

# Regenerate
python3 scripts/topology/generate-terraform.py --output generated/terraform > /dev/null 2>&1

if [ -f "scripts/topology/generate-ansible-inventory.py" ]; then
    python3 scripts/topology/generate-ansible-inventory.py --output generated/ansible > /dev/null 2>&1
fi

# Compare
if diff -r "$TEMP_DIR/generated-before" generated/ > /dev/null 2>&1; then
    print_success "Generators are idempotent (no changes on re-run)"
else
    print_error "Generators are NOT idempotent (output differs on re-run)"
    echo ""
    echo "This is a bug! Generators should produce identical output when run twice."
    rm -rf "$TEMP_DIR"
    exit 1
fi

rm -rf "$TEMP_DIR"

# ============================================================
# Summary
# ============================================================

print_header "Test Summary"

echo ""
echo "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo "Total tests:  $TESTS_TOTAL"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "✅ Full regeneration workflow is working correctly!"
    echo ""
    echo "Next steps:"
    echo "  1. Review changes: git diff new_system/generated/"
    echo "  2. Commit if needed: git add new_system/generated/ && git commit -m 'Regenerate infrastructure'"
    echo "  3. Apply with Terraform: cd new_system/terraform && terraform plan"
    echo ""
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}✗ TESTS FAILED${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "❌ Some tests failed. Review the output above and fix the issues."
    echo ""
    exit 1
fi
