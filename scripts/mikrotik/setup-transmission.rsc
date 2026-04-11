# MikroTik RouterOS 7.x - Transmission Container Setup Script
# Execute this on the router via SSH or Terminal

# Step 1: Check if container package is installed
/system/package/print where name="container"

# Step 2: Create veth interface for Transmission container
/interface/veth/add name=veth-transmission address=172.18.0.1/24 gateway=172.18.0.1

# Step 3: Add veth interface to containers bridge
/interface/bridge/port/add bridge=containers interface=veth-transmission

# Step 4: Create directories for Transmission data
/system/script/run {
  :execute script="/file/print file=disk1/transmission"
}

# Step 5: Set up environment variables for Transmission
:local transmissionEnv ""
:set transmissionEnv "USER=admin"
:set transmissionEnv ($transmissionEnv . "\nPASS=admin")
:set transmissionEnv ($transmissionEnv . "\nPEERPORT=51413")

# Step 6: Add Transmission container
/container/add \
  remote-image=linuxserver/transmission:latest \
  interface=veth-transmission \
  envlist=transmission-env \
  root-dir=disk1/transmission \
  mounts=transmission-downloads,transmission-config \
  logging=yes \
  comment="Transmission BitTorrent Client"

# Step 7: Create environment list
/container/envs/add name=transmission-env key=PUID value=1000
/container/envs/add name=transmission-env key=PGID value=1000
/container/envs/add name=transmission-env key=TZ value=Europe/Moscow
/container/envs/add name=transmission-env key=USER value=admin
/container/envs/add name=transmission-env key=PASS value=transmission
/container/envs/add name=transmission-env key=PEERPORT value=51413

# Step 8: Create mounts for downloads and config
/container/mounts/add name=transmission-downloads src=disk1/transmission/downloads dst=/downloads
/container/mounts/add name=transmission-config src=disk1/transmission/config dst=/config

# Step 9: Start the container
/container/start [find comment="Transmission BitTorrent Client"]

# Step 10: Check container status
:delay 10s
/container/print detail where comment="Transmission BitTorrent Client"
