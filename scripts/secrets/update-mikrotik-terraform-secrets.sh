#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/update-mikrotik-terraform-secrets.py"

if [ ! -f "${PYTHON_SCRIPT}" ]; then
    echo "Script not found: ${PYTHON_SCRIPT}" >&2
    exit 1
fi

PYTHON_BIN="python"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    PYTHON_BIN="python3"
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "Python interpreter not found (python/python3)." >&2
    exit 1
fi

"${PYTHON_BIN}" "${PYTHON_SCRIPT}" "$@"
