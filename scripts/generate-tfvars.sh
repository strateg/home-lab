#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS_DIR="${REPO_ROOT}/secrets/terraform"
WORK_DIR="${REPO_ROOT}/.work/native/terraform"

usage() {
    echo "Usage: $0 <target>"
    echo "  target: proxmox | mikrotik"
    echo ""
    echo "Generates terraform.tfvars from SOPS-encrypted secrets."
    echo "Output: .work/native/terraform/<target>/terraform.tfvars"
    exit 1
}

[ -z "$1" ] && usage

TARGET="$1"
SECRET_FILE="${SECRETS_DIR}/${TARGET}.yaml"
OUTPUT_DIR="${WORK_DIR}/${TARGET}"
OUTPUT_FILE="${OUTPUT_DIR}/terraform.tfvars"

if [ ! -f "$SECRET_FILE" ]; then
    echo "Error: Secret file not found: $SECRET_FILE"
    exit 1
fi

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: Output directory not found: $OUTPUT_DIR"
    echo "Run 'make assemble-native' first."
    exit 1
fi

echo "Generating ${TARGET} tfvars..."

case "$TARGET" in
    proxmox)
        sops -d "$SECRET_FILE" | yq -r '
            "proxmox_node = \"" + .proxmox.node + "\"",
            "proxmox_api_url = \"" + .proxmox.api_url + "\"",
            "proxmox_api_token = \"" + .proxmox.api_token + "\"",
            "proxmox_insecure = " + (.proxmox.insecure | tostring),
            "proxmox_ssh_user = \"" + .proxmox.ssh_user + "\"",
            "proxmox_ssh_key_path = \"" + .proxmox.ssh_key_path + "\""
        ' > "$OUTPUT_FILE"
        ;;
    mikrotik)
        sops -d "$SECRET_FILE" | yq -r '
            "mikrotik_host = \"" + .mikrotik.host + "\"",
            "mikrotik_username = \"" + .mikrotik.username + "\"",
            "mikrotik_password = \"" + .mikrotik.password + "\"",
            "mikrotik_insecure = " + (.mikrotik.insecure | tostring),
            "wireguard_private_key = \"" + .wireguard.private_key + "\"",
            "adguard_password = \"" + .containers.adguard_password + "\"",
            "tailscale_authkey = \"" + .containers.tailscale_authkey + "\""
        ' > "$OUTPUT_FILE"
        ;;
    *)
        echo "Error: Unknown target: $TARGET"
        usage
        ;;
esac

chmod 600 "$OUTPUT_FILE"
echo "Generated: $OUTPUT_FILE"
