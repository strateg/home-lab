#!/bin/bash
# Quick Transmission installation script for MikroTik RouterOS 7.x
# Usage: bash install-transmission.sh [router-ip] [username]

ROUTER_IP="${1:-192.168.88.1}"
USERNAME="${2:-admin}"

echo "==================================="
echo "Transmission Container Installer"
echo "==================================="
echo "Router: $ROUTER_IP"
echo "User: $USERNAME"
echo ""
echo "This script will:"
echo "  1. Create veth interface (172.18.0.10)"
echo "  2. Set up directories and mounts"
echo "  3. Configure environment variables"
echo "  4. Pull and start Transmission container"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Connecting to router and running installation..."
echo ""

ssh ${USERNAME}@${ROUTER_IP} << 'ENDSSH'

# Print header
:put "=== Step 1: Creating veth interface ==="
/interface/veth/add name=veth-transmission address=172.18.0.10/24 gateway=172.18.0.1
/interface/bridge/port/add bridge=containers interface=veth-transmission
:put "  [OK] veth-transmission created"

# Create directories
:put ""
:put "=== Step 2: Creating directories ==="
:execute script={
  /file/print file=transmission
  :delay 1s
  /file/print file=transmission/downloads
  :delay 1s
  /file/print file=transmission/config
}
:put "  [OK] Directories created"

# Set up environment
:put ""
:put "=== Step 3: Setting up environment ==="
/container/envs/add name=transmission-env key=PUID value=1000
/container/envs/add name=transmission-env key=PGID value=1000
/container/envs/add name=transmission-env key=TZ value=Europe/Moscow
/container/envs/add name=transmission-env key=USER value=admin
/container/envs/add name=transmission-env key=PASS value=transmission
/container/envs/add name=transmission-env key=PEERPORT value=51413
:put "  [OK] Environment configured"

# Create mounts
:put ""
:put "=== Step 4: Creating mount points ==="
/container/mounts/add name=transmission-downloads src=transmission/downloads dst=/downloads
/container/mounts/add name=transmission-config src=transmission/config dst=/config
:put "  [OK] Mounts configured"

# Add container
:put ""
:put "=== Step 5: Adding Transmission container ==="
:put "  [INFO] Pulling Docker image (this may take 5-10 minutes)..."
/container/add \
  remote-image=linuxserver/transmission:latest \
  interface=veth-transmission \
  envlist=transmission-env \
  root-dir=transmission \
  mounts=transmission-downloads,transmission-config \
  logging=yes \
  comment="Transmission BitTorrent Client"
:put "  [OK] Container added"

# Wait for image pull
:put ""
:put "=== Step 6: Waiting for image download ==="
:local timeout 600
:local elapsed 0
:while ($elapsed < $timeout) do={
  :local cstatus [/container/get [find comment="Transmission BitTorrent Client"] status]
  :if ($cstatus = "stopped") do={
    :put "  [OK] Image downloaded successfully"
    :break
  }
  :if ($elapsed % 30 = 0) do={
    :put ("  [INFO] Still downloading... (" . $elapsed . "s elapsed)")
  }
  :delay 5s
  :set elapsed ($elapsed + 5)
}

# Start container
:put ""
:put "=== Step 7: Starting container ==="
/container/start [find comment="Transmission BitTorrent Client"]
:delay 10s
:put "  [OK] Container started"

# Print status
:put ""
:put "=== Installation Complete ==="
:put ""
/container/print detail where comment="Transmission BitTorrent Client"
:put ""
:put "==================================="
:put "Web UI Access:"
:put "  Local: http://transmission.local:9091"
:put "  Direct: http://172.18.0.10:9091"
:put ""
:put "Default credentials:"
:put "  Username: admin"
:put "  Password: transmission"
:put "==================================="

ENDSSH

echo ""
echo "Installation completed!"
echo ""
echo "Access Transmission Web UI at:"
echo "  http://transmission.local:9091"
echo ""
echo "Default credentials:"
echo "  Username: admin"
echo "  Password: transmission"
echo ""
