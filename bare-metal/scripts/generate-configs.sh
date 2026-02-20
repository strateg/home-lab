#!/bin/bash
# Generate all infrastructure configurations from topology.yaml
# This script is called during USB creation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TOPOLOGY_FILE="$PROJECT_ROOT/topology.yaml"
OUTPUT_DIR="${1:-$PROJECT_ROOT/generated}"
INSTALL_UUID="${2:-}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    if ! command -v python3 &> /dev/null; then
        log_error "python3 is not installed"
        exit 1
    fi

    if [ ! -f "$TOPOLOGY_FILE" ]; then
        log_error "topology.yaml not found at: $TOPOLOGY_FILE"
        exit 1
    fi

    log_success "All dependencies present"
}

# Validate topology
validate_topology() {
    log_info "Validating topology.yaml..."

    if [ -f "$PROJECT_ROOT/topology-tools/validate-topology.py" ]; then
        python3 "$PROJECT_ROOT/topology-tools/validate-topology.py" --topology "$TOPOLOGY_FILE"
        log_success "Topology validation passed"
    else
        log_warn "Validator not found, skipping validation"
    fi
}

# Generate configurations
generate_all() {
    log_info "Generating configurations from topology.yaml..."

    # Run regenerate-all.py
    cd "$PROJECT_ROOT"
    python3 topology-tools/regenerate-all.py

    log_success "Configuration generation completed"
}

# Copy source files
copy_sources() {
    log_info "Copying source files to output directory..."

    # Copy topology.yaml
    cp "$TOPOLOGY_FILE" "$OUTPUT_DIR/"
    log_success "Copied topology.yaml"

    # Copy topology tools
    mkdir -p "$OUTPUT_DIR/topology-tools"
    cp -r "$PROJECT_ROOT/topology-tools/"* "$OUTPUT_DIR/topology-tools/"
    log_success "Copied topology tools"

    # Copy manual scripts
    mkdir -p "$OUTPUT_DIR/manual-scripts"
    cp -r "$PROJECT_ROOT/manual-scripts/"* "$OUTPUT_DIR/manual-scripts/"
    log_success "Copied manual scripts"
}

# Create deployment scripts
create_deployment_scripts() {
    log_info "Creating deployment scripts..."

    mkdir -p "$OUTPUT_DIR/scripts"

    # Create README
    cat > "$OUTPUT_DIR/README.md" << 'EOF'
# Home Lab Infrastructure Configurations

## Generated Files

This directory contains auto-generated infrastructure configurations:

- `topology.yaml` - Source of truth (Infrastructure-as-Data)
- `generated/terraform/` - Terraform configurations for Proxmox
- `generated/ansible/` - Ansible inventory and playbooks
- `generated/docs/` - Network diagrams and documentation
- `topology-tools/` - Topology generators and validator
- `manual-scripts/` - Manual setup/config scripts

## Deployment

See `AUTO-DEPLOY-ARCHITECTURE.md` for full documentation.

### Quick Start

```bash
# Deploy infrastructure
cd topology-tools
./deploy-infrastructure.sh

# Verify deployment
./verify-deployment.sh
```

## Regenerate Topology Artifacts

```bash
cd topology-tools
python3 regenerate-all.py
```

Generated at: $(date)
Installation UUID: ${INSTALL_UUID:-unknown}
EOF

    log_success "Created README.md"
}

# Create archive
create_archive() {
    log_info "Creating configuration archive..."

    ARCHIVE_NAME="home-lab-configs-${INSTALL_UUID:-$(date +%Y%m%d_%H%M%S)}.tar.gz"
    ARCHIVE_PATH="$PROJECT_ROOT/bare-metal/$ARCHIVE_NAME"

    cd "$OUTPUT_DIR"
    tar -czf "$ARCHIVE_PATH" .

    log_success "Created archive: $ARCHIVE_NAME"
    log_info "Archive size: $(du -h "$ARCHIVE_PATH" | cut -f1)"
    log_info "Archive path: $ARCHIVE_PATH"

    # Save archive path for later use
    echo "$ARCHIVE_PATH" > "$PROJECT_ROOT/bare-metal/.last-archive-path"
}

# Main
main() {
    echo "========================================"
    echo "  Home Lab Configuration Generator"
    echo "========================================"
    echo ""
    echo "Topology: $TOPOLOGY_FILE"
    echo "Output:   $OUTPUT_DIR"
    echo "UUID:     ${INSTALL_UUID:-not set}"
    echo ""

    check_dependencies
    validate_topology
    generate_all
    copy_sources
    create_deployment_scripts
    create_archive

    echo ""
    log_success "All configurations generated successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Archive created at: $PROJECT_ROOT/bare-metal/"
    echo "  2. Run create-usb.sh to embed configs into USB"
    echo ""
}

main "$@"
