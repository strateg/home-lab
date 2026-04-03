#!/usr/bin/env bash
set -euo pipefail

# Runs mcp-server-mikrotik using credentials decrypted from SOPS at runtime.
# Expected to be started from Claude Code via: wsl -e bash -lc "<script>"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

SECRET_FILE_DEFAULT="${REPO_ROOT}/projects/home-lab/secrets/bootstrap/rtr-mikrotik.chateau.yaml"
RUNTIME_VENV_DEFAULT="${REPO_ROOT}/.work/mcp/mikrotik/.venv"
MCP_PACKAGE_DEFAULT="mcp-server-mikrotik"

SECRET_FILE="${MIKROTIK_BOOTSTRAP_SECRET_FILE:-${SECRET_FILE_DEFAULT}}"
RUNTIME_VENV="${MIKROTIK_MCP_VENV:-${RUNTIME_VENV_DEFAULT}}"
MCP_PACKAGE="${MIKROTIK_MCP_PACKAGE:-${MCP_PACKAGE_DEFAULT}}"

usage() {
  cat <<'EOF'
Usage:
  run-mikrotik-mcp.sh [--check]

Options:
  --check   Validate dependencies and print non-sensitive connection summary.

Environment:
  MIKROTIK_BOOTSTRAP_SECRET_FILE  Override SOPS bootstrap secret file path
  MIKROTIK_MCP_VENV               Override runtime venv path
  MIKROTIK_MCP_PACKAGE            Override package spec (default: mcp-server-mikrotik)
EOF
}

need_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "[mikrotik-mcp][error] Missing command: ${cmd}" >&2
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
    mkdir -p "$(dirname "${RUNTIME_VENV}")"
    if [[ ! -x "${RUNTIME_VENV}/bin/python3" ]]; then
      python3 -m venv "${RUNTIME_VENV}"
    fi
    "${RUNTIME_VENV}/bin/python3" -m ensurepip --upgrade >/dev/null
    "${RUNTIME_VENV}/bin/python3" -m pip install --upgrade pip >/dev/null
    "${RUNTIME_VENV}/bin/python3" -m pip install "${MCP_PACKAGE}" >/dev/null
  fi
}

main() {
  local check_only="false"
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi
  if [[ "${1:-}" == "--check" ]]; then
    check_only="true"
  elif [[ -n "${1:-}" ]]; then
    usage
    exit 2
  fi

  need_cmd sops
  need_cmd python3

  if [[ ! -f "${SECRET_FILE}" ]]; then
    echo "[mikrotik-mcp][error] Secret file not found: ${SECRET_FILE}" >&2
    exit 1
  fi

  ensure_runtime

  local host username password
  host="$(extract_secret '["ssh"]["host"]')"
  username="$(extract_secret '["ssh"]["username"]')"
  password="$(extract_secret '["ssh"]["password"]')"

  if [[ -z "${host}" || -z "${username}" || -z "${password}" ]]; then
    echo "[mikrotik-mcp][error] Bootstrap secret is missing ssh.host/ssh.username/ssh.password." >&2
    exit 1
  fi

  if [[ "${check_only}" == "true" ]]; then
    echo "[mikrotik-mcp][ok] host=${host} username=${username} runtime=${RUNTIME_VENV}"
    exit 0
  fi

  export MIKROTIK_HOST="${host}"
  export MIKROTIK_USERNAME="${username}"
  export MIKROTIK_PASSWORD="${password}"
  export MIKROTIK_PORT="${MIKROTIK_PORT:-22}"
  export MIKROTIK_MCP__TRANSPORT="${MIKROTIK_MCP__TRANSPORT:-stdio}"

  exec "${RUNTIME_VENV}/bin/mcp-server-mikrotik"
}

main "$@"
