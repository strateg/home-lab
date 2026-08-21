#!/bin/bash
# Bootstrap Portainer on srv-orangepi5
# ADR 0072: Secrets, ADR 0087: Docker workloads
#
# This script:
#   1. Reads admin password from SOPS secrets
#   2. Deploys password file to host
#   3. Creates Portainer container with --admin-password-file
#
# Prerequisites:
#   - SSH access to srv-orangepi5 as automator
#   - Docker installed on host
#   - Password generated via portainer-secrets.sh
#
# Usage:
#   ./scripts/bootstrap/portainer-setup.sh [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SECRETS_FILE="$REPO_ROOT/projects/home-lab/secrets/instances/srv-orangepi5.yaml"
TOPOLOGY_FILE="$REPO_ROOT/projects/home-lab/topology/instances/docker/srv-orangepi5/docker-portainer.yaml"

HOST="srv-orangepi5"
REMOTE_USER="automator"
SECRETS_DIR="/etc/portainer/secrets"
DATA_DIR="/armbian/portainer/data"

DRY_RUN=false
[[ "$1" == "--dry-run" ]] && DRY_RUN=true

# Check dependencies
command -v sops >/dev/null 2>&1 || { echo "ERROR: sops not found"; exit 1; }
command -v yq >/dev/null 2>&1 || { echo "ERROR: yq not found"; exit 1; }

echo "=== Portainer Bootstrap for $HOST ==="
echo ""

# Extract password from secrets
echo "Reading admin password from secrets..."
ADMIN_PASSWORD=$(sops -d "$SECRETS_FILE" | yq '.portainer.admin_password')

if [[ -z "$ADMIN_PASSWORD" || "$ADMIN_PASSWORD" == "null" ]]; then
    echo "ERROR: Portainer admin password not found in secrets."
    echo "Run: ./scripts/bootstrap/portainer-secrets.sh"
    exit 1
fi

# Extract config from topology (topology uses @ prefixes, filter them for yq)
echo "Reading configuration from topology..."
# Filter out @ prefixed lines and parse with yq
TOPOLOGY_CLEAN=$(grep -v '^@' "$TOPOLOGY_FILE")
IMAGE=$(echo "$TOPOLOGY_CLEAN" | yq '.runtime.image')
CONTAINER_NAME=$(echo "$TOPOLOGY_CLEAN" | yq '.runtime.container_name')
RESTART_POLICY=$(echo "$TOPOLOGY_CLEAN" | yq '.runtime.restart')

echo ""
echo "Configuration:"
echo "  Image: $IMAGE"
echo "  Container: $CONTAINER_NAME"
echo "  Host: $HOST"
echo ""

if $DRY_RUN; then
    echo "[DRY-RUN] Would execute the following on $HOST:"
    echo ""
    echo "1. Create directories:"
    echo "   sudo mkdir -p $SECRETS_DIR"
    echo "   sudo mkdir -p $DATA_DIR"
    echo ""
    echo "2. Deploy password file:"
    echo "   echo '<password>' | sudo tee $SECRETS_DIR/admin_password"
    echo "   sudo chmod 600 $SECRETS_DIR/admin_password"
    echo ""
    echo "3. Stop existing container (if running):"
    echo "   docker stop $CONTAINER_NAME 2>/dev/null || true"
    echo "   docker rm $CONTAINER_NAME 2>/dev/null || true"
    echo ""
    echo "4. Start Portainer:"
    echo "   docker run -d \\"
    echo "     --name $CONTAINER_NAME \\"
    echo "     --restart $RESTART_POLICY \\"
    echo "     -p 9000:9000 -p 9443:9443 \\"
    echo "     -v /var/run/docker.sock:/var/run/docker.sock \\"
    echo "     -v $DATA_DIR:/data \\"
    echo "     -v $SECRETS_DIR/admin_password:/run/secrets/admin_password:ro \\"
    echo "     $IMAGE \\"
    echo "     --admin-password-file=/run/secrets/admin_password"
    exit 0
fi

echo "Deploying to $HOST..."

# Create remote script
REMOTE_SCRIPT=$(cat <<EOF
set -e

# Create directories
sudo mkdir -p $SECRETS_DIR
sudo mkdir -p $DATA_DIR

# Deploy password file
echo '$ADMIN_PASSWORD' | sudo tee $SECRETS_DIR/admin_password > /dev/null
sudo chmod 600 $SECRETS_DIR/admin_password
sudo chown root:root $SECRETS_DIR/admin_password

# Stop existing container
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Pull latest image
docker pull $IMAGE

# Start Portainer
docker run -d \\
  --name $CONTAINER_NAME \\
  --restart $RESTART_POLICY \\
  -p 9000:9000 \\
  -p 9443:9443 \\
  -v /var/run/docker.sock:/var/run/docker.sock \\
  -v $DATA_DIR:/data \\
  -v $SECRETS_DIR/admin_password:/run/secrets/admin_password:ro \\
  $IMAGE \\
  --admin-password-file=/run/secrets/admin_password

echo ""
echo "Portainer started. Waiting for health check..."
sleep 5

# Check if running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "SUCCESS: Portainer is running"
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
else
    echo "ERROR: Portainer failed to start"
    docker logs $CONTAINER_NAME 2>&1 | tail -20
    exit 1
fi
EOF
)

# Execute on remote host
ssh "$REMOTE_USER@$HOST" "$REMOTE_SCRIPT"

echo ""
echo "=== Portainer Bootstrap Complete ==="
echo ""
echo "Access Portainer:"
echo "  HTTP:  http://$HOST:9000"
echo "  HTTPS: https://$HOST:9443"
echo ""
echo "Login: admin / <password from secrets>"
