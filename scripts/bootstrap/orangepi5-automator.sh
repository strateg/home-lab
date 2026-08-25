#!/bin/bash
# Bootstrap automator user on srv-orangepi5
# ADR 0072: Secrets, ADR 0083: Node Initialization
#
# Prerequisites:
#   1. SSH access to orangepi5 as 'strateg' user (with sudo)
#   2. Password for strateg (for --ask-pass) OR SSH key configured
#
# Usage:
#   ./scripts/bootstrap/orangepi5-automator.sh [--ask-pass]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ANSIBLE_DIR="$REPO_ROOT/projects/home-lab/ansible"

cd "$ANSIBLE_DIR"

echo "=== Bootstrap automator on srv-orangepi5 ==="
echo ""
echo "This will:"
echo "  1. Create 'automator' user"
echo "  2. Add SSH key for automation"
echo "  3. Configure passwordless sudo"
echo ""

# Check if --ask-pass is needed
EXTRA_ARGS=""
if [[ "$1" == "--ask-pass" ]] || [[ "$1" == "-k" ]]; then
    EXTRA_ARGS="--ask-pass --ask-become-pass"
    echo "Using password authentication..."
else
    echo "Using SSH key authentication..."
fi

# Run bootstrap playbook
ansible-playbook \
    -i inventory/production \
    playbooks/bootstrap-automator.yml \
    -e target_host=srv-orangepi5 \
    -e ansible_user=strateg \
    -e ansible_ssh_private_key_file=~/.ssh/id_ed25519 \
    $EXTRA_ARGS

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Test automator access:"
echo "  ssh orangepi5"
echo ""
echo "Show Docker containers:"
echo "  ssh orangepi5 'docker ps'"
