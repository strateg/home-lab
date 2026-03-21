#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_VERSION="${TASK_VERSION:-3.45.4}"
SOPS_VERSION="${SOPS_VERSION:-3.12.1}"
SKIP_PYTHON_DEPS="${SKIP_PYTHON_DEPS:-0}"

log() {
    echo "[setup-dev] $*"
}

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

resolve_python() {
    if have_cmd python; then
        echo "python"
        return 0
    fi
    if have_cmd python3; then
        echo "python3"
        return 0
    fi
    echo ""
}

install_task_linux_manual() {
    local os="linux"
    local arch
    arch="$(uname -m)"
    case "$arch" in
        x86_64|amd64) arch="amd64" ;;
        aarch64|arm64) arch="arm64" ;;
        armv7l) arch="armv7" ;;
        *)
            log "Unsupported CPU architecture for manual go-task install: $arch"
            return 1
            ;;
    esac

    local tmp
    tmp="$(mktemp -d)"
    local archive="$tmp/task.tgz"
    local url="https://github.com/go-task/task/releases/download/v${TASK_VERSION}/task_${os}_${arch}.tar.gz"
    log "Downloading go-task from ${url}"
    curl -fsSL "$url" -o "$archive"
    tar -xzf "$archive" -C "$tmp"
    sudo install -m 0755 "$tmp/task" /usr/local/bin/task
    rm -rf "$tmp"
}

install_linux() {
    if ! have_cmd apt-get; then
        log "Unsupported Linux package manager. Install age, sops, and task manually."
        return 1
    fi

    log "Installing base packages (age, curl, python3, pip)"
    sudo apt-get update
    sudo apt-get install -y age curl python3 python3-pip

    if ! have_cmd sops; then
        log "Installing sops v${SOPS_VERSION}"
        local tmp_sops
        tmp_sops="$(mktemp)"
        curl -fsSL \
            "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" \
            -o "$tmp_sops"
        sudo install -m 0755 "$tmp_sops" /usr/local/bin/sops
        rm -f "$tmp_sops"
    fi

    if ! have_cmd task; then
        log "Installing go-task via apt"
        if ! sudo apt-get install -y go-task; then
            log "go-task package unavailable via apt, fallback to manual install"
            install_task_linux_manual
        fi
    fi
}

install_macos() {
    if ! have_cmd brew; then
        log "Homebrew is required on macOS. Install from https://brew.sh"
        return 1
    fi

    log "Installing packages via Homebrew (age, sops, go-task, python)"
    brew install age sops go-task/tap/go-task python || true
}

install_python_deps() {
    if [[ "$SKIP_PYTHON_DEPS" == "1" ]]; then
        log "Skipping Python dev dependencies installation (SKIP_PYTHON_DEPS=1)."
        return 0
    fi
    local py
    py="$(resolve_python)"
    if [[ -z "$py" ]]; then
        log "Python is not available. Install Python and run again."
        return 1
    fi
    log "Installing Python dev dependencies in editable mode"
    (cd "$REPO_ROOT" && "$py" -m pip install --upgrade pip && "$py" -m pip install -e '.[dev]')
}

print_versions() {
    echo
    have_cmd python && python --version || true
    have_cmd python3 && python3 --version || true
    have_cmd sops && sops --version || true
    if have_cmd rage; then
        rage --version || true
    else
        have_cmd age && age --version || true
    fi
    have_cmd task && task --version || true
}

main() {
    local os
    os="$(uname -s)"
    case "$os" in
        Linux*) install_linux ;;
        Darwin*) install_macos ;;
        *)
            log "Unsupported OS in this script: $os"
            log "For Windows use: ./v5/scripts/setup-dev-environment.ps1"
            return 1
            ;;
    esac

    install_python_deps
    print_versions
    log "Done."
}

main "$@"
