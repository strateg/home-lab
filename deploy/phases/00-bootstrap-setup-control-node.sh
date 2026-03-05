#!/bin/bash
# =============================================================================
# Phase 0: Bootstrap Control Node Setup (netinstall-cli and dependencies)
# =============================================================================
# Automatically installs all required tools for MikroTik bootstrap on the
# control node (the machine running Terraform, Ansible, and netinstall-cli)
#
# Usage:
#   ./00-bootstrap-setup-control-node.sh
#
# Exit codes:
#   0 = all tools installed successfully
#   1 = installation failed, review output
#
# Supports:
#   - Debian/Ubuntu (apt-based)
#   - RedHat/CentOS/Fedora (yum/dnf-based)
#   - macOS (Homebrew)
#   - Windows (with Git Bash or WSL2)
#
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
NETINSTALL_VERSION="${NETINSTALL_VERSION:-7.20.8}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local/bin}"

# Counters
INSTALLED=0
SKIPPED=0
FAILED=0

# =============================================================================
# Helper Functions
# =============================================================================

log_header() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║  Phase 0: Bootstrap Control Node Setup                               ║"
    echo "║  Installing: netinstall-cli, Terraform, Ansible, Python3, curl, wget ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ -f /etc/os-release ]]; then
            . /etc/os-release
            OS_TYPE="$ID"
            OS_VERSION="$VERSION_ID"
        else
            OS_TYPE="linux"
            OS_VERSION="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS_TYPE="macos"
        OS_VERSION=$(sw_vers -productVersion)
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        OS_TYPE="windows"
        OS_VERSION="$(cmd /c ver 2>/dev/null)"
    else
        OS_TYPE="unknown"
        OS_VERSION="unknown"
    fi
}

log_info() {
    echo -e "${YELLOW}ℹ️${NC}  $1"
}

log_success() {
    echo -e "${GREEN}✓${NC}  $1"
    ((INSTALLED++))
}

log_skip() {
    echo -e "${CYAN}⊘${NC}  $1"
    ((SKIPPED++))
}

log_error() {
    echo -e "${RED}✗${NC}  $1"
    ((FAILED++))
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

get_tool_version() {
    local tool="$1"
    local flag="${2:---version}"

    if command -v "$tool" &> /dev/null; then
        "$tool" "$flag" 2>/dev/null | head -n1 || echo "installed"
    fi
}

require_sudo() {
    if [[ $EUID -ne 0 ]]; then
        echo "This operation requires sudo. Please enter your password."
        sudo -v
        # Keep sudo alive
        while true; do sudo -n true; sleep 60; kill -0 $$ 2>/dev/null || exit; done &
    fi
}

# =============================================================================
# Installation Functions
# =============================================================================

install_ubuntu_debian() {
    echo -e "${CYAN}Installing on Debian/Ubuntu${NC}"

    require_sudo

    echo "Updating package lists..."
    sudo apt-get update -qq

    echo "Installing netinstall-cli..."
    if sudo apt-get install -y netinstall-cli &>/dev/null; then
        log_success "netinstall-cli installed"
    else
        log_info "netinstall-cli package not available in apt, will install manually"
        install_netinstall_manual
    fi

    echo "Installing dependencies..."
    local packages=(
        "wget"
        "curl"
        "python3"
        "python3-pip"
        "git"
        "openssh-client"
        "ansible"
        "terraform"
    )

    for pkg in "${packages[@]}"; do
        if sudo apt-get install -y "$pkg" &>/dev/null 2>&1; then
            log_success "$pkg installed"
        elif check_command "$pkg"; then
            log_skip "$pkg already installed"
        else
            log_error "$pkg installation failed"
        fi
    done
}

install_redhat_fedora() {
    echo -e "${CYAN}Installing on RedHat/CentOS/Fedora${NC}"

    require_sudo

    echo "Installing netinstall-cli..."
    if sudo yum install -y netinstall-cli &>/dev/null 2>&1 || \
       sudo dnf install -y netinstall-cli &>/dev/null 2>&1; then
        log_success "netinstall-cli installed"
    else
        log_info "netinstall-cli package not available in yum/dnf, will install manually"
        install_netinstall_manual
    fi

    echo "Installing dependencies..."
    local packages=(
        "wget"
        "curl"
        "python3"
        "python3-pip"
        "git"
        "openssh-clients"
        "ansible"
        "terraform"
    )

    for pkg in "${packages[@]}"; do
        if sudo yum install -y "$pkg" &>/dev/null 2>&1 || \
           sudo dnf install -y "$pkg" &>/dev/null 2>&1; then
            log_success "$pkg installed"
        elif check_command "$pkg"; then
            log_skip "$pkg already installed"
        else
            log_error "$pkg installation failed"
        fi
    done
}

install_macos() {
    echo -e "${CYAN}Installing on macOS${NC}"

    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        log_error "Homebrew not found. Please install from: https://brew.sh"
        return 1
    fi

    log_info "Using Homebrew for macOS installation"

    echo "Installing netinstall-cli..."
    if brew install mikrotik-netinstall &>/dev/null 2>&1; then
        log_success "netinstall-cli installed via Homebrew"
    else
        log_info "netinstall-cli formula not available, will install manually"
        install_netinstall_manual
    fi

    echo "Installing dependencies..."
    local packages=(
        "wget"
        "curl"
        "python3"
        "terraform"
        "ansible"
    )

    for pkg in "${packages[@]}"; do
        if brew install "$pkg" &>/dev/null 2>&1; then
            log_success "$pkg installed"
        elif check_command "$pkg"; then
            log_skip "$pkg already installed"
        else
            log_error "$pkg installation failed"
        fi
    done
}

install_windows() {
    echo -e "${CYAN}Installing on Windows (Git Bash/WSL2)${NC}"
    log_info "For native Windows, use: chocolatey, scoop, or WSL2 with Linux installation"
    log_info "Attempting WSL2 installation..."

    # Try to detect WSL2
    if grep -qi microsoft /proc/version 2>/dev/null; then
        log_success "WSL2 detected, using apt installation"
        install_ubuntu_debian
    else
        log_error "Cannot automatically install on native Windows"
        log_info "Please use one of these alternatives:"
        echo "  1. WSL2: wsl --install && wsl bash script.sh"
        echo "  2. Scoop: scoop install netinstall-cli terraform ansible"
        echo "  3. Chocolatey: choco install netinstall-cli terraform ansible"
        echo "  4. Download manually from https://mikrotik.com/download"
        return 1
    fi
}

install_netinstall_manual() {
    echo -e "${YELLOW}Installing netinstall-cli manually from MikroTik download site...${NC}"

    local temp_dir="/tmp/netinstall-install-$$"
    mkdir -p "$temp_dir"

    local url="https://download.mikrotik.com/routeros/${NETINSTALL_VERSION}/netinstall-${NETINSTALL_VERSION}.tar.gz"
    local archive="$temp_dir/netinstall-${NETINSTALL_VERSION}.tar.gz"

    echo "Downloading from: $url"
    if wget --timeout=30 --tries=3 -q -O "$archive" "$url"; then
        echo "Extracting..."
        tar xzf "$archive" -C "$temp_dir"

        local netinstall_binary="$temp_dir/netinstall"
        if [[ -f "$netinstall_binary" ]]; then
            require_sudo
            sudo install -m 0755 "$netinstall_binary" "${INSTALL_PREFIX}/netinstall-cli"
            log_success "netinstall-cli installed from source"
        else
            log_error "netinstall binary not found in archive"
        fi
    else
        log_error "Failed to download netinstall from: $url"
        log_info "Manual installation: Download from https://mikrotik.com/download"
    fi

    # Cleanup
    rm -rf "$temp_dir"
}

# =============================================================================
# Verification
# =============================================================================

verify_installation() {
    echo ""
    echo -e "${CYAN}Verification Results:${NC}"
    echo "────────────────────────────────────────────"

    local required_tools=(
        "netinstall-cli:netinstall-cli"
        "python3:python3"
        "wget:wget"
        "curl:curl"
    )

    local optional_tools=(
        "terraform:terraform"
        "ansible:ansible"
        "git:git"
    )

    local all_ok=true

    echo ""
    echo "Required tools:"
    for tool_pair in "${required_tools[@]}"; do
        IFS=: read -r cmd_name display_name <<< "$tool_pair"
        if check_command "$cmd_name"; then
            local version=$(get_tool_version "$cmd_name")
            log_success "$display_name: $version"
        else
            log_error "$display_name: NOT INSTALLED"
            all_ok=false
        fi
    done

    echo ""
    echo "Optional tools (recommended):"
    for tool_pair in "${optional_tools[@]}"; do
        IFS=: read -r cmd_name display_name <<< "$tool_pair"
        if check_command "$cmd_name"; then
            local version=$(get_tool_version "$cmd_name")
            log_success "$display_name: $version"
        else
            log_skip "$display_name: not installed (optional)"
        fi
    done

    echo ""
    echo "────────────────────────────────────────────"
    echo -e "${CYAN}Summary:${NC}"
    echo "  Installed:    $INSTALLED"
    echo "  Skipped:      $SKIPPED"
    echo "  Failed:       $FAILED"

    if [[ $all_ok == true ]]; then
        echo ""
        log_success "All required tools installed!"
        return 0
    else
        echo ""
        log_error "Some required tools are missing"
        return 1
    fi
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    log_header

    detect_os
    log_info "Detected OS: $OS_TYPE ($OS_VERSION)"
    echo ""

    case "$OS_TYPE" in
        ubuntu|debian)
            install_ubuntu_debian
            ;;
        fedora|rhel|centos)
            install_redhat_fedora
            ;;
        macos)
            install_macos
            ;;
        windows|msys|cygwin)
            install_windows
            ;;
        *)
            log_error "Unsupported OS: $OS_TYPE"
            echo ""
            echo "Please install the following tools manually:"
            echo "  - netinstall-cli (https://mikrotik.com/download)"
            echo "  - Python 3"
            echo "  - wget or curl"
            echo "  - Terraform (https://www.terraform.io/downloads.html)"
            echo "  - Ansible (https://docs.ansible.com/ansible/latest/installation_guide/)"
            exit 1
            ;;
    esac

    echo ""
    if verify_installation; then
        echo ""
        log_success "Control node setup complete!"
        echo ""
        echo "Next steps:"
        echo "  1. Run bootstrap preflight checks:"
        echo "     cd deploy && make bootstrap-preflight RESTORE_PATH=minimal"
        echo ""
        echo "  2. Execute bootstrap when ready:"
        echo "     make bootstrap-netinstall RESTORE_PATH=minimal \\"
        echo "       MIKROTIK_BOOTSTRAP_MAC='00:11:22:33:44:55'"
        exit 0
    else
        echo ""
        log_error "Control node setup incomplete"
        echo ""
        echo "Please resolve the missing tools manually and retry."
        exit 1
    fi
}

main "$@"
