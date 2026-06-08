# WireGuard Tunnel Setup Guide

Automated procedure for creating site-to-site WireGuard tunnels using the Infrastructure-as-Data topology model.

## Overview

This guide covers the end-to-end process of defining, generating, and deploying WireGuard tunnels between network devices (e.g., MikroTik router and cloud VPS).

**Architecture flow:**
```
Topology Definition → Secrets → Compilation → Generation → Deployment
     (YAML)          (SOPS)     (plugins)    (templates)   (tasks)
```

## Quick Start (Task Commands)

For an existing tunnel definition, the complete deployment workflow:

### Minimal (3 Commands)

```bash
# 1. Generate configurations from topology
task build

# 2. Full VPS deployment (extracts key, deploys config, firewall, OCI, enables service)
task deploy:wireguard-full-deploy-vps

# 3. Deploy to MikroTik (reads all credentials/keys from secrets)
task deploy:wireguard-deploy-mikrotik-sshpass
```

### Step-by-Step (Granular Control)

```bash
# 1. Extract SSH key for VPS access
task deploy:wireguard-extract-vps-key

# 2. Generate configurations from topology
task build

# 3. Verify generated configs
task deploy:wireguard-show

# 4. Deploy config to VPS (auto-discovers IP from OCI)
task deploy:wireguard-deploy-vps SSH_KEY=/tmp/vps-ssh-key.pem

# 5. Configure VPS firewall (iptables - inserts before REJECT)
task deploy:wireguard-setup-vps-iptables SSH_KEY=/tmp/vps-ssh-key.pem

# 6. Add OCI Security List rule
task deploy:wireguard-oci-check-security
task deploy:wireguard-oci-add-security

# 7. Enable WireGuard service on VPS
ssh -i /tmp/vps-ssh-key.pem ubuntu@$(task deploy:wireguard-get-vps-ip) \
  "sudo systemctl enable --now wg-quick@wg0"

# 8. Deploy to MikroTik
task deploy:wireguard-deploy-mikrotik-sshpass

# 9. Verify tunnel status on both sides
task deploy:wireguard-status-vps SSH_KEY=/tmp/vps-ssh-key.pem
task deploy:wireguard-status-mikrotik MIKROTIK_HOST=192.168.88.1 MIKROTIK_USER=automator
```

### Environment Setup (Optional)

Create `.env.local` for persistent settings:
```bash
# .env.local (not committed)
export VPS_SSH_KEY=/path/to/vps-ssh-key.pem
export MIKROTIK_HOST=192.168.88.1
export MIKROTIK_USER=automator
```

Then source before running tasks:
```bash
source .env.local
task deploy:wireguard-status-vps SSH_KEY=$VPS_SSH_KEY
```

## Prerequisites

### Software Requirements

| Component | Purpose |
|-----------|---------|
| Python 3.11+ | Topology compiler and generators |
| SOPS + age | Secrets encryption |
| OCI CLI | Oracle Cloud API access (for dynamic IP) |
| Task | Task runner for deployment |
| sshpass | MikroTik password authentication |

### Access Requirements

- SSH key for VPS (stored in instance secrets)
- MikroTik automator credentials (stored in instance secrets)
- OCI CLI configured with valid credentials

## Step 1: Define Tunnel Topology

### 1.1 Object Definition (if not exists)

The WireGuard tunnel object is defined at:
```
topology/object-modules/network/obj.network.wireguard_tunnel.yaml
```

This object extends `class.network.tunnel_link` and provides:
- WireGuard-specific configuration schema
- Endpoint schema (device_ref, role, tunnel_ip, allowed_ips)
- Default values (MTU 1420, keepalive 25s, port 51820)

### 1.2 Create Tunnel Instance

Create instance file at:
```
projects/home-lab/topology/instances/network/inst.tunnel.<tunnel-name>.yaml
```

Example (`inst.tunnel.wg-home-to-oci.yaml`):
```yaml
@instance: inst.tunnel.wg-home-to-oci
@extends: obj.network.wireguard_tunnel
@group: network
@version: 1.0.0
source_id: inst.tunnel.wg-home-to-oci
status: planned

# Tunnel interface name
tunnel_name: wg0

# Tunnel network (point-to-point /30)
tunnel_network: 10.100.0.0/30

# Endpoint A: MikroTik (client/initiator)
endpoint_a:
  device_ref: rtr-mikrotik-chateau
  role: client
  tunnel_ip: 10.100.0.1/30
  persistent_keepalive: 25
  allowed_ips:
    - 10.100.0.1/32
    - 192.168.88.0/24      # LAN networks to advertise
    - 10.0.10.0/24

# Endpoint B: VPS (server/responder)
endpoint_b:
  device_ref: vps-oracle-frankfurt
  role: server
  tunnel_ip: 10.100.0.2/30
  listen_port: 51820
  allowed_ips:
    - 10.100.0.2/32
    - 0.0.0.0/0            # Route all traffic option

# Reference to secrets file
secrets_ref: secrets.tunnels.wg-home-to-oci
```

## Step 2: Generate WireGuard Keys

Generate keypairs for both endpoints:

```bash
# Generate endpoint A (MikroTik) keypair
wg genkey | tee /tmp/mikrotik.key | wg pubkey > /tmp/mikrotik.pub

# Generate endpoint B (VPS) keypair
wg genkey | tee /tmp/vps.key | wg pubkey > /tmp/vps.pub

# Generate pre-shared key
wg genpsk > /tmp/psk.key

# Display keys
echo "MikroTik private: $(cat /tmp/mikrotik.key)"
echo "MikroTik public:  $(cat /tmp/mikrotik.pub)"
echo "VPS private:      $(cat /tmp/vps.key)"
echo "VPS public:       $(cat /tmp/vps.pub)"
echo "PSK:              $(cat /tmp/psk.key)"
```

## Step 3: Create Secrets File

Create SOPS-encrypted secrets at:
```
projects/home-lab/secrets/tunnels/<tunnel-name>.yaml
```

Create plain YAML first:
```yaml
# WireGuard tunnel secrets: home MikroTik <-> OCI VPS
mikrotik:
  private_key: <mikrotik-private-key>
  public_key: <mikrotik-public-key>

vps:
  private_key: <vps-private-key>
  public_key: <vps-public-key>

preshared_key: <psk>
```

Encrypt with SOPS:
```bash
sops -e -i projects/home-lab/secrets/tunnels/wg-home-to-oci.yaml
```

## Step 4: Compile and Generate

Run the topology compiler to generate WireGuard configurations:

```bash
# Full compilation
.venv/bin/python topology-tools/compile-topology.py

# Or via task
task generate:all
```

### Generated Outputs

The WireGuard generator produces files in `generated/home-lab/wireguard/`:

| File | Format | Target |
|------|--------|--------|
| `mikrotik-wg0.rsc` | RouterOS script | MikroTik router |
| `vps-wg0.conf` | wg-quick config | Linux VPS |

## Step 5: Deploy to VPS

### 5.1 Deploy Configuration

```bash
# Auto-discovers VPS IP from OCI API
task deploy:wireguard-deploy-vps SSH_KEY=/path/to/key.pem
```

### 5.2 Set Up Firewall (iptables)

```bash
# Inserts UDP 51820 rule before any REJECT rules
task deploy:wireguard-setup-vps-iptables SSH_KEY=/path/to/key.pem
```

### 5.3 Add OCI Security List Rule

```bash
# Check if rule exists
task deploy:wireguard-oci-check-security

# Add rule if missing
task deploy:wireguard-oci-add-security
```

### 5.4 Enable WireGuard Service

```bash
ssh -i /path/to/key.pem ubuntu@<vps-ip> \
  "sudo systemctl enable --now wg-quick@wg0"
```

## Step 6: Deploy to MikroTik

### 6.1 Automated Deployment (Recommended)

Use the task that reads all credentials and keys from secrets:

```bash
task deploy:wireguard-deploy-mikrotik-sshpass
```

This task:
- Reads MikroTik automator password from secrets
- Gets VPS IP from OCI API
- Reads WireGuard keys from tunnel secrets
- Removes existing WireGuard config (if any)
- Creates interface, peer, IP address, firewall trust
- Shows result

### 6.2 Manual Deployment

If you need manual control:

```bash
# Get automator password from secrets
MIKROTIK_PASS=$(sops -d projects/home-lab/secrets/instances/rtr-mikrotik-chateau.yaml | \
  .venv/bin/python3 -c "import sys,yaml; print(yaml.safe_load(sys.stdin)['automator']['password'])")

# Deploy commands via SSH
sshpass -p "$MIKROTIK_PASS" ssh automator@192.168.88.1 << 'EOF'
/interface wireguard add name=wg0 listen-port=51820 \
  private-key="<private-key>" mtu=1420

/interface wireguard peers add interface=wg0 \
  public-key="<vps-public-key>" \
  preshared-key="<psk>" \
  endpoint-address=<vps-ip> endpoint-port=51820 \
  allowed-address=10.100.0.2/32,0.0.0.0/0 \
  persistent-keepalive=25s

/ip address add address=10.100.0.1/30 interface=wg0

/interface list member add interface=wg0 list=LAN
EOF
```

### 6.3 Alternative: Import RSC Script

If SCP works (key auth or upgraded RouterOS):
```bash
scp generated/home-lab/wireguard/mikrotik-wg0.rsc admin@192.168.88.1:/flash/
ssh admin@192.168.88.1 "/import flash/mikrotik-wg0.rsc"
```

## Step 7: Verification

### Check VPS Status

```bash
task deploy:wireguard-status-vps SSH_KEY=/path/to/key.pem

# Expected output:
# interface: wg0
#   public key: vj9gNvWsm0BHjWPK5WkJGiB3/Rlqah/bLUuCYFikDTw=
#   listening port: 51820
# peer: Ka+uGYDyX0tgJygGDrErYPvpaMqa2NIhIUYmvVemg3k=
#   latest handshake: X seconds ago
#   transfer: X KiB received, X KiB sent
```

### Check MikroTik Status

```bash
# Via task (requires MIKROTIK_HOST)
task deploy:wireguard-status-mikrotik MIKROTIK_HOST=192.168.88.1

# Or manually
sshpass -p "$MIKROTIK_PASS" ssh automator@192.168.88.1 \
  "/interface wireguard print; /interface wireguard peers print"
```

### Test Connectivity

```bash
# From MikroTik, ping VPS tunnel IP
sshpass -p "$MIKROTIK_PASS" ssh automator@192.168.88.1 \
  "/ping address=10.100.0.2 count=3"

# Expected: 0% packet loss
```

## Troubleshooting

### Problem: Handshake Not Completing

**Symptoms:**
- MikroTik peer shows `tx > 0, rx = 0`
- VPS shows no handshake timestamp

**Common causes:**

1. **Firewall blocking UDP 51820**
   ```bash
   # Check VPS iptables
   ssh ubuntu@<vps> "sudo iptables -L INPUT -n -v --line-numbers"

   # REJECT rule before ACCEPT? Fix:
   task deploy:wireguard-setup-vps-iptables
   ```

2. **OCI Security List missing rule**
   ```bash
   task deploy:wireguard-oci-check-security
   task deploy:wireguard-oci-add-security
   ```

3. **Wrong endpoint IP** (VPS IP changed)
   ```bash
   # Get current VPS IP
   task deploy:wireguard-get-vps-ip

   # Update MikroTik peer
   sshpass -p "$MIKROTIK_PASS" ssh automator@192.168.88.1 \
     "/interface wireguard peers set 0 endpoint-address=<new-ip>"
   ```

4. **Key mismatch**
   - Verify public keys match between endpoints
   - Regenerate keys if necessary

### Problem: Tunnel Up But No Traffic

**Check routing:**
```bash
# MikroTik routes
ssh automator@192.168.88.1 "/ip route print where gateway=wg0"

# VPS routes
ssh ubuntu@<vps> "ip route | grep wg0"
```

**Check allowed-address:**
- MikroTik peer must include VPS networks in `allowed-address`
- VPS peer must include MikroTik networks in `AllowedIPs`

### Problem: iptables Rules Lost After Reboot

```bash
# Save rules persistently
ssh ubuntu@<vps> "sudo iptables-save | sudo tee /etc/iptables/rules.v4"

# Or install iptables-persistent
ssh ubuntu@<vps> "sudo apt install -y iptables-persistent"
```

## Task Reference

### High-Level Tasks (Recommended)

| Task | Description |
|------|-------------|
| `deploy:wireguard-full-deploy-vps` | Full VPS deployment: extract key + config + firewall + OCI + enable service |
| `deploy:wireguard-deploy-mikrotik-sshpass` | Full MikroTik deployment via sshpass (reads credentials from secrets) |

### Granular Tasks

| Task | Description |
|------|-------------|
| `deploy:wireguard-extract-vps-key` | Extract VPS SSH key from secrets to `/tmp/vps-ssh-key.pem` |
| `deploy:wireguard-show` | List generated configs |
| `deploy:wireguard-deploy-vps` | Deploy config to VPS |
| `deploy:wireguard-deploy-mikrotik` | Deploy config to MikroTik (requires SSH key auth) |
| `deploy:wireguard-setup-vps-iptables` | Configure VPS firewall (inserts rule before REJECT) |
| `deploy:wireguard-oci-check-security` | Check OCI Security List for UDP 51820 |
| `deploy:wireguard-oci-add-security` | Add OCI Security List rule for WireGuard |
| `deploy:wireguard-status-vps` | Show VPS WireGuard status |
| `deploy:wireguard-status-mikrotik` | Show MikroTik WireGuard status |
| `deploy:wireguard-get-vps-ip` | Get VPS public IP from OCI API |

## File Reference

| Path | Purpose |
|------|---------|
| `topology/object-modules/network/obj.network.wireguard_tunnel.yaml` | Object definition |
| `projects/home-lab/topology/instances/network/inst.tunnel.*.yaml` | Tunnel instances |
| `projects/home-lab/secrets/tunnels/*.yaml` | Encrypted keys (SOPS) |
| `topology-tools/plugins/generators/wireguard_generator.py` | Generator plugin |
| `topology-tools/templates/wireguard/*.j2` | Jinja2 templates |
| `generated/home-lab/wireguard/` | Generated configs |
| `taskfiles/deploy.yml` | Deployment tasks |

## Security Notes

1. **Never commit unencrypted keys** - Always use SOPS
2. **Rotate keys periodically** - Generate new keypairs, update secrets, redeploy
3. **Use pre-shared keys** - Adds post-quantum resistance layer
4. **Limit allowed_ips** - Only advertise necessary networks
5. **Monitor tunnel** - Check for unusual traffic patterns
