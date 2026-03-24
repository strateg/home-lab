#!/bin/bash
#
# Ansible Vault Helper Script
# Simplifies common vault operations
#
# Usage: ./vault-helper.sh [command]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_FILE="$SCRIPT_DIR/group_vars/all/vault.yml"
VAULT_EXAMPLE="$SCRIPT_DIR/group_vars/all/vault.yml.example"
VAULT_PASS_FILE="$SCRIPT_DIR/.vault_pass"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_cmd() {
    echo -e "${BLUE}[CMD]${NC} $1"
}

show_usage() {
    cat << EOF
Ansible Vault Helper

Usage: $0 [command]

Commands:
  init              Initialize new vault (create password and vault.yml)
  edit              Edit vault file (decrypt, edit, re-encrypt)
  view              View vault contents (read-only)
  rekey             Change vault password
  encrypt           Encrypt vault.yml
  decrypt           Decrypt vault.yml (DANGER - use with caution)
  validate          Check if vault is properly encrypted
  generate-pass     Generate strong password for vault
  encrypt-string    Encrypt a string for inline use
  status            Show vault status
  backup            Create encrypted backup of vault
  restore           Restore vault from backup
  help              Show this help message

Examples:
  $0 init                           # First-time setup
  $0 edit                           # Edit vault securely
  $0 view                           # View vault contents
  $0 encrypt-string "my_password"   # Encrypt a string
  $0 validate                       # Check vault encryption

Environment:
  EDITOR            Editor to use (default: vim)
  VAULT_PASSWORD    Override vault password file

EOF
}

check_vault_password() {
    if [[ ! -f "$VAULT_PASS_FILE" ]]; then
        log_error "Vault password file not found: $VAULT_PASS_FILE"
        log_info "Run: $0 init"
        exit 1
    fi
}

cmd_init() {
    log_info "Initializing Ansible Vault..."

    # Check if vault already exists
    if [[ -f "$VAULT_FILE" ]]; then
        log_warn "Vault file already exists: $VAULT_FILE"
        read -p "Overwrite? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log_info "Aborted."
            exit 0
        fi
    fi

    # Generate vault password
    log_info "Generating vault password..."
    VAULT_PASSWORD=$(openssl rand -base64 32)
    echo "$VAULT_PASSWORD" > "$VAULT_PASS_FILE"
    chmod 600 "$VAULT_PASS_FILE"
    log_info "Vault password saved to: $VAULT_PASS_FILE"

    # Create vault.yml from example
    if [[ -f "$VAULT_EXAMPLE" ]]; then
        log_info "Creating vault.yml from example..."
        cp "$VAULT_EXAMPLE" "$VAULT_FILE"
    else
        log_warn "Example file not found, creating empty vault..."
        cat > "$VAULT_FILE" << 'VAULT_TEMPLATE'
---
# Ansible Vault - Encrypted Secrets
# Edit with: ansible-vault edit group_vars/all/vault.yml

# Proxmox
vault_proxmox_api_token: "CHANGEME"
vault_proxmox_root_password: "CHANGEME"

# PostgreSQL
vault_postgresql_superuser_password: "CHANGEME"
vault_postgresql_app_password: "CHANGEME"

# Nextcloud
vault_nextcloud_admin_password: "CHANGEME"
vault_nextcloud_db_password: "CHANGEME"

# Redis
vault_redis_password: "CHANGEME"
VAULT_TEMPLATE
    fi

    # Encrypt vault
    log_info "Encrypting vault.yml..."
    ansible-vault encrypt "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE"

    log_info ""
    log_info "${GREEN}✅ Vault initialized successfully!${NC}"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Edit vault: $0 edit"
    log_info "  2. Replace CHANGEME values with real secrets"
    log_info "  3. Backup vault password to password manager"
    log_info ""
    log_warn "⚠️  IMPORTANT: Backup this password somewhere safe!"
    echo ""
    echo "Vault Password: $VAULT_PASSWORD"
    echo ""
}

cmd_edit() {
    check_vault_password
    log_info "Opening vault for editing..."
    log_cmd "ansible-vault edit $VAULT_FILE"
    ansible-vault edit "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE"
}

cmd_view() {
    check_vault_password
    log_info "Viewing vault contents..."
    ansible-vault view "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE"
}

cmd_rekey() {
    check_vault_password
    log_warn "Changing vault password..."
    log_info "You will need to provide the current password and new password."

    # Generate new password option
    read -p "Generate random password? (yes/no): " generate
    if [[ "$generate" == "yes" ]]; then
        NEW_PASSWORD=$(openssl rand -base64 32)
        log_info "New password: $NEW_PASSWORD"
        echo "$NEW_PASSWORD" | ansible-vault rekey "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE" --new-vault-password-file=/dev/stdin
        echo "$NEW_PASSWORD" > "$VAULT_PASS_FILE"
        chmod 600 "$VAULT_PASS_FILE"
        log_info "${GREEN}✅ Vault password changed${NC}"
        echo ""
        log_warn "⚠️  New password: $NEW_PASSWORD"
        log_warn "⚠️  Update your password manager!"
    else
        ansible-vault rekey "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE"
        log_info "${GREEN}✅ Vault password changed${NC}"
        log_warn "⚠️  Update .vault_pass file manually!"
    fi
}

cmd_encrypt() {
    check_vault_password

    if head -1 "$VAULT_FILE" | grep -q "ANSIBLE_VAULT"; then
        log_warn "Vault is already encrypted"
        exit 0
    fi

    log_info "Encrypting vault.yml..."
    ansible-vault encrypt "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE"
    log_info "${GREEN}✅ Vault encrypted${NC}"
}

cmd_decrypt() {
    check_vault_password

    log_warn "⚠️  DANGER: Decrypting vault to plain text!"
    log_warn "This should only be used for recovery or migration."
    read -p "Continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Aborted."
        exit 0
    fi

    log_info "Decrypting vault.yml..."
    ansible-vault decrypt "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE"
    log_warn "${YELLOW}⚠️  Vault is now UNENCRYPTED!${NC}"
    log_warn "Remember to re-encrypt: $0 encrypt"
}

cmd_validate() {
    log_info "Validating vault..."

    # Check if file exists
    if [[ ! -f "$VAULT_FILE" ]]; then
        log_error "Vault file not found: $VAULT_FILE"
        exit 1
    fi

    # Check if encrypted
    if head -1 "$VAULT_FILE" | grep -q "ANSIBLE_VAULT"; then
        log_info "${GREEN}✅ Vault is encrypted (AES256)${NC}"
    else
        log_error "❌ Vault is NOT encrypted!"
        log_warn "Run: $0 encrypt"
        exit 1
    fi

    # Check password file
    if [[ -f "$VAULT_PASS_FILE" ]]; then
        log_info "${GREEN}✅ Vault password file exists${NC}"

        # Check permissions
        PERMS=$(stat -c "%a" "$VAULT_PASS_FILE")
        if [[ "$PERMS" == "600" ]]; then
            log_info "${GREEN}✅ Vault password file has correct permissions (600)${NC}"
        else
            log_warn "❌ Vault password file permissions are $PERMS (should be 600)"
            log_info "Fix: chmod 600 $VAULT_PASS_FILE"
        fi
    else
        log_warn "❌ Vault password file not found"
    fi

    # Try to decrypt (test password)
    if ansible-vault view "$VAULT_FILE" --vault-password-file="$VAULT_PASS_FILE" > /dev/null 2>&1; then
        log_info "${GREEN}✅ Vault password is correct${NC}"
    else
        log_error "❌ Cannot decrypt vault (wrong password?)"
        exit 1
    fi

    log_info ""
    log_info "${GREEN}✅ Vault validation passed${NC}"
}

cmd_generate_pass() {
    log_info "Generating strong passwords..."
    echo ""
    echo "Base64 (32 chars): $(openssl rand -base64 32)"
    echo "Hex (64 chars):    $(openssl rand -hex 32)"
    echo "Alphanumeric:      $(pwgen -s 64 1 2>/dev/null || echo 'pwgen not installed')"
    echo ""
}

cmd_encrypt_string() {
    check_vault_password

    if [[ -z "${1:-}" ]]; then
        log_error "Usage: $0 encrypt-string <string> [variable_name]"
        exit 1
    fi

    STRING="$1"
    VAR_NAME="${2:-secret}"

    log_info "Encrypting string as: $VAR_NAME"
    ansible-vault encrypt_string "$STRING" --name "$VAR_NAME" --vault-password-file="$VAULT_PASS_FILE"
}

cmd_status() {
    log_info "Vault Status"
    echo ""
    echo "Vault File:     $VAULT_FILE"
    echo "Password File:  $VAULT_PASS_FILE"
    echo ""

    if [[ -f "$VAULT_FILE" ]]; then
        echo "Vault exists:   ${GREEN}✅ Yes${NC}"
        if head -1 "$VAULT_FILE" | grep -q "ANSIBLE_VAULT"; then
            echo "Encrypted:      ${GREEN}✅ Yes${NC}"
        else
            echo "Encrypted:      ${RED}❌ No${NC}"
        fi
    else
        echo "Vault exists:   ${RED}❌ No${NC}"
    fi

    if [[ -f "$VAULT_PASS_FILE" ]]; then
        echo "Password file:  ${GREEN}✅ Yes${NC}"
        echo "Permissions:    $(stat -c "%a" "$VAULT_PASS_FILE")"
    else
        echo "Password file:  ${RED}❌ No${NC}"
    fi
    echo ""
}

cmd_backup() {
    check_vault_password

    BACKUP_DIR="$SCRIPT_DIR/vault-backups"
    mkdir -p "$BACKUP_DIR"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/vault_backup_$TIMESTAMP.yml.enc"

    log_info "Creating encrypted backup..."
    cp "$VAULT_FILE" "$BACKUP_FILE"

    log_info "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
    log_info "To restore: $0 restore $BACKUP_FILE"
}

cmd_restore() {
    check_vault_password

    if [[ -z "${1:-}" ]]; then
        log_error "Usage: $0 restore <backup_file>"
        exit 1
    fi

    BACKUP_FILE="$1"

    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    log_warn "Restoring vault from backup..."
    log_warn "Current vault will be overwritten!"
    read -p "Continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Aborted."
        exit 0
    fi

    cp "$VAULT_FILE" "$VAULT_FILE.old"
    cp "$BACKUP_FILE" "$VAULT_FILE"

    log_info "${GREEN}✅ Vault restored from backup${NC}"
    log_info "Old vault saved as: $VAULT_FILE.old"
}

# Main command dispatcher
COMMAND="${1:-help}"

case "$COMMAND" in
    init)
        cmd_init
        ;;
    edit)
        cmd_edit
        ;;
    view)
        cmd_view
        ;;
    rekey)
        cmd_rekey
        ;;
    encrypt)
        cmd_encrypt
        ;;
    decrypt)
        cmd_decrypt
        ;;
    validate)
        cmd_validate
        ;;
    generate-pass)
        cmd_generate_pass
        ;;
    encrypt-string)
        shift
        cmd_encrypt_string "$@"
        ;;
    status)
        cmd_status
        ;;
    backup)
        cmd_backup
        ;;
    restore)
        shift
        cmd_restore "$@"
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
