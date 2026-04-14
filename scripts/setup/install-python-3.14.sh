#!/usr/bin/env bash
# ADR 0098 Phase A: Python 3.14 Installation Script
#
# This script installs Python 3.14 on Ubuntu 25.04+ systems
#
# Usage:
#   ./install-python-3.14.sh [--method=apt|pyenv|source]
#
# Options:
#   --method=apt     Use deadsnakes PPA (default for Ubuntu)
#   --method=pyenv   Use pyenv to install and manage
#   --method=source  Build from source (fallback)
#
# Exit codes:
#   0 - Success
#   1 - Installation failed
#   2 - Python 3.14 already installed

set -euo pipefail

PYTHON_VERSION="3.14.4"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
METHOD="apt"
for arg in "$@"; do
    case $arg in
        --method=*)
            METHOD="${arg#*=}"
            shift
            ;;
    esac
done

# Check if Python 3.14 already installed
check_existing() {
    if command -v python3.14 &> /dev/null; then
        local version
        version=$(python3.14 --version 2>&1)
        log_info "Python 3.14 already installed: ${version}"
        return 0
    fi
    return 1
}

# Install via deadsnakes PPA (Ubuntu)
install_apt() {
    log_info "Installing Python ${PYTHON_VERSION} via deadsnakes PPA..."

    # Add deadsnakes PPA if not present
    if ! grep -q "deadsnakes" /etc/apt/sources.list.d/* 2>/dev/null; then
        log_info "Adding deadsnakes PPA..."
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt-get update
    fi

    # Install Python 3.14
    log_info "Installing python3.14 packages..."
    sudo apt-get install -y \
        python3.14 \
        python3.14-venv \
        python3.14-dev \
        python3.14-distutils 2>/dev/null || true

    # Verify installation
    if command -v python3.14 &> /dev/null; then
        log_info "Installation successful: $(python3.14 --version)"
        return 0
    else
        log_error "Installation failed via apt"
        return 1
    fi
}

# Install via pyenv
install_pyenv() {
    log_info "Installing Python ${PYTHON_VERSION} via pyenv..."

    # Install pyenv if not present
    if ! command -v pyenv &> /dev/null; then
        log_info "Installing pyenv..."
        curl https://pyenv.run | bash

        # Add to PATH for current session
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    fi

    # Install build dependencies
    log_info "Installing build dependencies..."
    sudo apt-get install -y \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libffi-dev \
        liblzma-dev

    # Install Python via pyenv
    log_info "Building Python ${PYTHON_VERSION}..."
    pyenv install "${PYTHON_VERSION}"

    # Set local version for project
    cd "${PROJECT_ROOT}"
    pyenv local "${PYTHON_VERSION}"

    # Verify
    if python --version | grep -q "3.14"; then
        log_info "Installation successful via pyenv"
        return 0
    else
        log_error "Installation failed via pyenv"
        return 1
    fi
}

# Build from source
install_source() {
    log_info "Building Python ${PYTHON_VERSION} from source..."

    local build_dir="/tmp/python-build"
    mkdir -p "${build_dir}"
    cd "${build_dir}"

    # Install build dependencies
    log_info "Installing build dependencies..."
    sudo apt-get install -y \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libffi-dev \
        liblzma-dev

    # Download source
    log_info "Downloading Python ${PYTHON_VERSION}..."
    wget "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz"
    tar -xf "Python-${PYTHON_VERSION}.tar.xz"
    cd "Python-${PYTHON_VERSION}"

    # Configure and build
    log_info "Configuring..."
    ./configure --enable-optimizations --with-ensurepip=install

    log_info "Building (this may take 10-20 minutes)..."
    make -j "$(nproc)"

    log_info "Installing..."
    sudo make altinstall

    # Cleanup
    cd /
    rm -rf "${build_dir}"

    # Verify
    if command -v python3.14 &> /dev/null; then
        log_info "Installation successful: $(python3.14 --version)"
        return 0
    else
        log_error "Installation failed from source"
        return 1
    fi
}

# Create test virtual environment
create_test_venv() {
    local venv_path="${PROJECT_ROOT}/.venv-3.14"

    log_info "Creating test virtual environment at ${venv_path}..."

    python3.14 -m venv "${venv_path}"

    # Activate and install dependencies
    source "${venv_path}/bin/activate"
    pip install --upgrade pip
    pip install -e "${PROJECT_ROOT}[dev]"

    log_info "Test virtual environment created successfully"
    log_info "Activate with: source ${venv_path}/bin/activate"
}

# Main
main() {
    log_info "ADR 0098 Phase A: Python 3.14 Installation"
    log_info "Target version: ${PYTHON_VERSION}"
    log_info "Installation method: ${METHOD}"
    echo

    # Check if already installed
    if check_existing; then
        log_warn "Python 3.14 is already installed"
        read -p "Create test virtual environment? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_test_venv
        fi
        exit 2
    fi

    # Install based on method
    case $METHOD in
        apt)
            install_apt
            ;;
        pyenv)
            install_pyenv
            ;;
        source)
            install_source
            ;;
        *)
            log_error "Unknown method: ${METHOD}"
            log_info "Valid methods: apt, pyenv, source"
            exit 1
            ;;
    esac

    # Create test venv after successful installation
    if [[ $? -eq 0 ]]; then
        read -p "Create test virtual environment? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_test_venv
        fi
    fi

    log_info "Installation complete!"
    log_info "Next steps:"
    log_info "  1. Run dependency verification: ./scripts/setup/verify-deps-3.14.sh"
    log_info "  2. Run test suite: pytest tests/ -v"
    log_info "  3. Document evidence in adr/0098-analysis/evidence/"
}

main "$@"
