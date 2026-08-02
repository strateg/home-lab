#!/usr/bin/env bash
set -euo pipefail

# Runs mcp-server-mikrotik using credentials decrypted from SOPS at runtime.
# Supports automatic network detection:
#   - Direct connection when on Chateau network (WiFi/Ethernet)
#   - WireGuard tunnel through Frankfurt when on external network
#
# Expected to be started from Claude Code via: wsl -e bash -lc "<script>"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Secret file paths
SECRET_FILE_DEFAULT="${REPO_ROOT}/projects/home-lab/secrets/instances/rtr-mikrotik-chateau.yaml"
RUNTIME_VENV_DEFAULT="${REPO_ROOT}/.work/mcp/mikrotik/.venv"
MCP_PACKAGE_DEFAULT="mcp-server-mikrotik"

# WireGuard configuration
WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_CONFIG_PATH="${WG_CONFIG_PATH:-/etc/wireguard/${WG_INTERFACE}.conf}"
CHATEAU_DIRECT_IP="192.168.88.1"
CHATEAU_TUNNEL_IP="192.168.88.1"  # Same IP, routed via tunnel when WG active

# Connection detection timeouts (ms)
PING_TIMEOUT_MS="${PING_TIMEOUT_MS:-500}"
PING_COUNT="${PING_COUNT:-1}"

SECRET_FILE="${MIKROTIK_BOOTSTRAP_SECRET_FILE:-${SECRET_FILE_DEFAULT}}"
RUNTIME_VENV="${MIKROTIK_MCP_VENV:-${RUNTIME_VENV_DEFAULT}}"
MCP_PACKAGE="${MIKROTIK_MCP_PACKAGE:-${MCP_PACKAGE_DEFAULT}}"

# Color output for status messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "[mikrotik-mcp][${BLUE}info${NC}] $*" >&2; }
log_ok() { echo -e "[mikrotik-mcp][${GREEN}ok${NC}] $*" >&2; }
log_warn() { echo -e "[mikrotik-mcp][${YELLOW}warn${NC}] $*" >&2; }
log_err() { echo -e "[mikrotik-mcp][${RED}error${NC}] $*" >&2; }

usage() {
  cat <<'EOF'
Usage:
  run-mikrotik-mcp.sh [OPTIONS]

Options:
  --check           Validate dependencies and print connection summary
  --status          Show network detection and WireGuard status
  --direct          Force direct connection (skip tunnel detection)
  --tunnel          Force tunnel connection (requires WireGuard active)
  --help, -h        Show this help message

Environment:
  MIKROTIK_BOOTSTRAP_SECRET_FILE  Override SOPS secret file path
  MIKROTIK_MCP_VENV               Override runtime venv path
  MIKROTIK_MCP_PACKAGE            Override package spec (default: mcp-server-mikrotik)
  WG_INTERFACE                    WireGuard interface name (default: wg0)
  PING_TIMEOUT_MS                 Network detection timeout in ms (default: 500)

Network Detection:
  The script automatically detects the best connection path:
  1. If directly reachable (Chateau WiFi/Ethernet) -> direct connection
  2. If WireGuard tunnel active -> connect via Frankfurt tunnel
  3. If neither available -> attempt to bring up WireGuard
EOF
}

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    log_err "Missing command: ${cmd}"
    exit 1
  fi
}

extract_secret() {
  local path_expr="$1"
  local raw
  raw="$(sops -d --extract "${path_expr}" "${SECRET_FILE}" | tr -d '\r')"
  raw="${raw%\"}"
  raw="${raw#\"}"
  printf '%s' "${raw}"
}

ensure_runtime() {
  if [[ ! -x "${RUNTIME_VENV}/bin/mcp-server-mikrotik" ]]; then
    log_info "Installing MCP server runtime..."
    mkdir -p "$(dirname "${RUNTIME_VENV}")"
    if [[ ! -x "${RUNTIME_VENV}/bin/python3" ]]; then
      python3 -m venv "${RUNTIME_VENV}"
    fi
    "${RUNTIME_VENV}/bin/python3" -m ensurepip --upgrade >/dev/null
    "${RUNTIME_VENV}/bin/python3" -m pip install --upgrade pip >/dev/null
    "${RUNTIME_VENV}/bin/python3" -m pip install "${MCP_PACKAGE}" >/dev/null
    log_ok "MCP server runtime installed"
  fi
}

# Check if we're directly connected to Chateau network
is_direct_network() {
  local timeout_s
  # Convert ms to seconds (minimum 1 second for ping -W)
  timeout_s=$(( (PING_TIMEOUT_MS + 999) / 1000 ))
  [[ $timeout_s -lt 1 ]] && timeout_s=1

  # Try to ping Chateau directly without going through WireGuard
  # We check local routes first to determine if we're on the same network
  if ip route get "${CHATEAU_DIRECT_IP}" 2>/dev/null | grep -qE "(dev (eth|enp|wl|wlan)|192\.168\.88\.)"; then
    # We have a local route to 192.168.88.0/24, try ping
    if ping -c "${PING_COUNT}" -W "${timeout_s}" "${CHATEAU_DIRECT_IP}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

# Check if WireGuard tunnel is active
is_wireguard_active() {
  if command -v wg >/dev/null 2>&1; then
    wg show "${WG_INTERFACE}" >/dev/null 2>&1
    return $?
  fi
  # Fallback: check if interface exists
  ip link show "${WG_INTERFACE}" >/dev/null 2>&1
}

# Get WireGuard tunnel details
get_wireguard_status() {
  if is_wireguard_active; then
    local endpoint latest_handshake
    endpoint=$(wg show "${WG_INTERFACE}" endpoints 2>/dev/null | head -1 | awk '{print $2}' || echo "unknown")
    latest_handshake=$(wg show "${WG_INTERFACE}" latest-handshakes 2>/dev/null | head -1 | awk '{print $2}' || echo "0")

    if [[ "${latest_handshake}" != "0" && "${latest_handshake}" != "" ]]; then
      local now handshake_age
      now=$(date +%s)
      handshake_age=$((now - latest_handshake))
      echo "active (endpoint: ${endpoint}, handshake: ${handshake_age}s ago)"
    else
      echo "active (endpoint: ${endpoint}, no handshake yet)"
    fi
  else
    echo "inactive"
  fi
}

# Attempt to bring up WireGuard tunnel
bring_up_wireguard() {
  log_info "Attempting to bring up WireGuard tunnel ${WG_INTERFACE}..."

  if [[ ! -f "${WG_CONFIG_PATH}" ]]; then
    log_err "WireGuard config not found: ${WG_CONFIG_PATH}"
    log_info "Deploy config from: generated/home-lab/wireguard/client-ws-nixos.conf"
    return 1
  fi

  if command -v wg-quick >/dev/null 2>&1; then
    if sudo wg-quick up "${WG_INTERFACE}" 2>&1; then
      log_ok "WireGuard tunnel ${WG_INTERFACE} activated"
      # Wait for tunnel to establish
      sleep 2
      return 0
    else
      log_err "Failed to bring up WireGuard tunnel"
      return 1
    fi
  else
    log_err "wg-quick not available, cannot auto-activate tunnel"
    log_info "Install WireGuard tools or manually start the tunnel"
    return 1
  fi
}

# Detect best connection method
detect_connection() {
  local method="none"
  local host="${CHATEAU_DIRECT_IP}"

  # Check direct network first (fastest)
  if is_direct_network; then
    method="direct"
    log_ok "Direct connection available (Chateau network detected)"
  elif is_wireguard_active; then
    method="tunnel"
    log_ok "Using WireGuard tunnel via Frankfurt"
  else
    log_warn "No direct connection, WireGuard inactive"

    # Attempt to bring up WireGuard
    if bring_up_wireguard; then
      if is_wireguard_active; then
        method="tunnel"
        log_ok "WireGuard tunnel activated successfully"
      fi
    fi
  fi

  echo "${method}"
}

# Show connection and network status
show_status() {
  echo "=== MikroTik MCP Connection Status ==="
  echo ""

  # Check direct network
  echo -n "Direct network (Chateau WiFi/Ethernet): "
  if is_direct_network; then
    echo -e "${GREEN}CONNECTED${NC}"
  else
    echo -e "${YELLOW}NOT AVAILABLE${NC}"
  fi

  # Check WireGuard
  echo -n "WireGuard tunnel (${WG_INTERFACE}): "
  local wg_status
  wg_status=$(get_wireguard_status)
  if [[ "${wg_status}" == inactive ]]; then
    echo -e "${YELLOW}${wg_status}${NC}"
  else
    echo -e "${GREEN}${wg_status}${NC}"
  fi

  # Show routing
  echo ""
  echo "Route to Chateau (${CHATEAU_DIRECT_IP}):"
  ip route get "${CHATEAU_DIRECT_IP}" 2>/dev/null | head -1 || echo "  (no route)"

  # Show recommended connection
  echo ""
  echo -n "Recommended connection method: "
  local method
  method=$(detect_connection 2>/dev/null)
  case "${method}" in
    direct) echo -e "${GREEN}DIRECT${NC}" ;;
    tunnel) echo -e "${BLUE}TUNNEL (via Frankfurt)${NC}" ;;
    *) echo -e "${RED}NONE AVAILABLE${NC}" ;;
  esac
}

main() {
  local mode="auto"
  local check_only="false"
  local status_only="false"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h)
        usage
        exit 0
        ;;
      --check)
        check_only="true"
        shift
        ;;
      --status)
        status_only="true"
        shift
        ;;
      --direct)
        mode="direct"
        shift
        ;;
      --tunnel)
        mode="tunnel"
        shift
        ;;
      *)
        log_err "Unknown option: $1"
        usage
        exit 2
        ;;
    esac
  done

  # Status mode - just show status and exit
  if [[ "${status_only}" == "true" ]]; then
    show_status
    exit 0
  fi

  # Check required commands
  need_cmd sops
  need_cmd python3
  need_cmd ping
  need_cmd ip

  if [[ ! -f "${SECRET_FILE}" ]]; then
    log_err "Secret file not found: ${SECRET_FILE}"
    exit 1
  fi

  ensure_runtime

  # Extract credentials
  local host username password
  host="$(extract_secret '["ssh"]["host"]')"
  username="$(extract_secret '["ssh"]["username"]')"
  password="$(extract_secret '["ssh"]["password"]')"

  if [[ -z "${host}" || -z "${username}" || -z "${password}" ]]; then
    log_err "Secret file is missing ssh.host/ssh.username/ssh.password"
    exit 1
  fi

  # Determine connection method
  local connection_method
  case "${mode}" in
    direct)
      if ! is_direct_network; then
        log_warn "Direct network not available, but --direct was specified"
      fi
      connection_method="direct"
      ;;
    tunnel)
      if ! is_wireguard_active; then
        log_err "WireGuard tunnel not active, cannot use --tunnel mode"
        log_info "Start tunnel with: sudo wg-quick up ${WG_INTERFACE}"
        exit 1
      fi
      connection_method="tunnel"
      ;;
    auto)
      connection_method=$(detect_connection)
      ;;
  esac

  # Validate connection is available
  if [[ "${connection_method}" == "none" ]]; then
    log_err "No connection available to MikroTik Chateau"
    log_info "Options:"
    log_info "  1. Connect to Chateau WiFi or Ethernet"
    log_info "  2. Start WireGuard tunnel: sudo wg-quick up ${WG_INTERFACE}"
    log_info "  3. Deploy WireGuard config: cp generated/home-lab/wireguard/client-ws-nixos.conf /etc/wireguard/${WG_INTERFACE}.conf"
    exit 1
  fi

  # For check mode, just print summary
  if [[ "${check_only}" == "true" ]]; then
    echo "[mikrotik-mcp][ok] connection=${connection_method} host=${host} username=${username} runtime=${RUNTIME_VENV}"
    exit 0
  fi

  # Log connection method
  case "${connection_method}" in
    direct)
      log_info "Connecting directly to ${host} (local network)"
      ;;
    tunnel)
      log_info "Connecting to ${host} via WireGuard tunnel (Frankfurt)"
      ;;
  esac

  # Set environment and run MCP server
  export MIKROTIK_HOST="${host}"
  export MIKROTIK_USERNAME="${username}"
  export MIKROTIK_PASSWORD="${password}"
  export MIKROTIK_PORT="${MIKROTIK_PORT:-22}"
  export MIKROTIK_MCP__TRANSPORT="${MIKROTIK_MCP__TRANSPORT:-stdio}"

  exec "${RUNTIME_VENV}/bin/mcp-server-mikrotik"
}

main "$@"
