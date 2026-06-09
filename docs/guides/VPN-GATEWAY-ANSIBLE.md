# VPN Gateway Ansible Configuration

## Overview

This guide describes the Ansible role and playbook for configuring the OCI VPS as a WireGuard gateway for VPN-Germany VLAN geo-bypass.

## Architecture

```
TV/Device (192.168.55.x)
    |
    v
MikroTik Chateau (VLAN 55, routing mark)
    |
    v [WireGuard wg0, 10.100.0.1]
VPS Oracle Frankfurt (10.100.0.2)
    |
    v [iptables MASQUERADE]
Internet (German IP: 92.5.172.x)
```

### Components

| Component | Role |
|-----------|------|
| MikroTik Chateau | WireGuard client, policy routing |
| VPS Oracle Frankfurt | WireGuard server, NAT gateway |
| VLAN 55 (192.168.55.0/24) | VPN-Germany network segment |

## Prerequisites

### On Control Machine

```bash
# Ansible with SOPS collection
ansible-galaxy collection install community.sops

# SOPS with age for secret decryption
# Ensure SOPS_AGE_KEY_FILE is set or age key is in default location
```

### Network Requirements

- WireGuard tunnel must be established between MikroTik and VPS
- Either public IP access or tunnel access (10.100.0.2) to VPS
- SSH key for VPS authentication

## Directory Structure

```
projects/home-lab/ansible/
├── ansible.cfg
├── requirements.yml
├── inventory/
│   └── production/
│       ├── hosts.yml                    # Host definitions
│       └── host_vars/
│           └── vps-oracle-frankfurt.yml # VPS-specific variables
├── playbooks/
│   └── vpn-gateway.yml                  # Main playbook
├── roles/
│   └── wireguard_gateway/
│       ├── defaults/main.yml
│       ├── handlers/main.yml
│       ├── tasks/
│       │   ├── main.yml
│       │   ├── install.yml
│       │   ├── configure.yml
│       │   ├── networking.yml
│       │   └── service.yml
│       └── templates/
│           └── wg0.conf.j2
└── scripts/
    └── get-vps-ip.sh                    # Dynamic IP discovery
```

## Usage

### Quick Start

```bash
cd projects/home-lab/ansible

# Option 1: Via WireGuard tunnel (default, when tunnel is up)
ansible-playbook -i inventory/production/hosts.yml playbooks/vpn-gateway.yml

# Option 2: Via public IP (when tunnel is down)
export VPS_ORACLE_FRANKFURT_IP=$(./scripts/get-vps-ip.sh)
ansible-playbook -i inventory/production/hosts.yml playbooks/vpn-gateway.yml \
  -e "ansible_host=$VPS_ORACLE_FRANKFURT_IP"
```

### SSH Key Setup

The playbook expects an SSH key. Options:

```bash
# Option 1: Extract from SOPS secrets
sops -d --extract '["ssh_private_key"]' \
  ../secrets/instances/vps-oracle-frankfurt.yaml > /tmp/vps-key
chmod 600 /tmp/vps-key
export VPS_SSH_KEY_PATH=/tmp/vps-key

# Option 2: Use existing key
export VPS_SSH_KEY_PATH=~/.ssh/vps-oracle-frankfurt
```

### Dry Run

```bash
ansible-playbook --check -i inventory/production/hosts.yml playbooks/vpn-gateway.yml \
  -e "ansible_host=<VPS_IP>" \
  -e "ansible_ssh_private_key_file=<KEY_PATH>"
```

## Configuration

### Host Variables

Edit `inventory/production/host_vars/vps-oracle-frankfurt.yml`:

```yaml
# Network interfaces
primary_interface: ens3      # Public interface for NAT
tunnel_interface: wg0        # WireGuard interface

# WireGuard settings
wireguard:
  interface: wg0
  listen_port: 51820
  tunnel_ip: 10.100.0.2/30
  role: server

# Peers (MikroTik)
wireguard_peers:
  - name: rtr-mikrotik-chateau
    public_key: "{{ wireguard_secrets.mikrotik.public_key }}"
    allowed_ips:
      - 10.100.0.1/32
      - 192.168.88.0/24
      - 192.168.55.0/24

# Networks to NAT
routed_networks:
  - network: 192.168.55.0/24
    comment: "VPN Germany VLAN"
    nat: masquerade

# iptables rules
iptables_forward_rules:
  - "-I FORWARD 1 -i wg0 -o ens3 -j ACCEPT"
  - "-I FORWARD 2 -i ens3 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT"

iptables_nat_rules:
  - "-t nat -A POSTROUTING -s 192.168.55.0/24 -o ens3 -j MASQUERADE"
```

### Secrets

Secrets are stored in SOPS-encrypted files:

| File | Contents |
|------|----------|
| `secrets/tunnels/wg-home-to-oci.yaml` | WireGuard keys (mikrotik, vps, preshared) |
| `secrets/instances/vps-oracle-frankfurt.yaml` | SSH keys, OCI IDs |

Structure of `wg-home-to-oci.yaml`:
```yaml
mikrotik:
  private_key: <base64>
  public_key: <base64>
vps:
  private_key: <base64>
  public_key: <base64>
preshared_key: <base64>
```

## What the Playbook Does

1. **Install packages**: wireguard, wireguard-tools, iptables-persistent, conntrack
2. **Deploy WireGuard config**: `/etc/wireguard/wg0.conf` from template
3. **Enable IP forwarding**: `net.ipv4.ip_forward = 1`
4. **Configure iptables**: FORWARD rules + NAT MASQUERADE
5. **Enable service**: `wg-quick@wg0` systemd service
6. **Verify**: Display WireGuard status

## Verification

After running the playbook:

```bash
# Check WireGuard status
ssh ubuntu@<VPS_IP> "sudo wg show wg0"

# Expected output:
# interface: wg0
#   public key: vj9gNv...
#   listening port: 51820
# peer: Ka+uGY...
#   preshared key: (hidden)
#   endpoint: <MikroTik_IP>:51820
#   latest handshake: X seconds ago
#   allowed ips: 10.100.0.1/32, 192.168.55.0/24, ...

# Check NAT rules
ssh ubuntu@<VPS_IP> "sudo iptables -t nat -L POSTROUTING -n -v | grep 192.168.55"

# Check IP forwarding
ssh ubuntu@<VPS_IP> "cat /proc/sys/net/ipv4/ip_forward"
# Should output: 1

# Test from VPN-Germany VLAN device
curl ifconfig.me
# Should show German IP (92.5.172.x)
```

## Troubleshooting

### Tunnel Not Establishing

**Symptoms**: No handshake, ping to 10.100.0.2 fails

**Check**:
```bash
# On VPS - verify WireGuard is listening
sudo ss -ulnp | grep 51820

# On VPS - check for handshake attempts
sudo wg show wg0

# On MikroTik - verify peer config
/interface wireguard peers print
```

**Common causes**:
- Missing preshared_key (must match on both sides)
- Firewall blocking UDP 51820
- Wrong public key

### Ansible Hangs During WireGuard Restart

**Cause**: When running Ansible through the WireGuard tunnel, restarting WireGuard disconnects the SSH session.

**Solution**: Run Ansible via public IP when making WireGuard changes:
```bash
ansible-playbook ... -e "ansible_host=<PUBLIC_IP>"
```

### No Internet from VPN VLAN

**Check**:
```bash
# Verify IP forwarding
cat /proc/sys/net/ipv4/ip_forward

# Verify NAT rules
sudo iptables -t nat -L POSTROUTING -n -v

# Verify FORWARD rules
sudo iptables -L FORWARD -n -v

# Check for existing connections (clear if needed)
sudo conntrack -D -s 192.168.55.0/24
```

### SOPS Decryption Fails

**Check**:
```bash
# Verify age key is available
echo $SOPS_AGE_KEY_FILE
# or check ~/.config/sops/age/keys.txt

# Test decryption manually
sops -d projects/home-lab/secrets/tunnels/wg-home-to-oci.yaml
```

## Dynamic IP Discovery

The VPS public IP can change on restart. Never store it statically.

### Using get-vps-ip.sh

```bash
# Discovery methods (in order):
# 1. OCI CLI (if configured)
# 2. SSH through WireGuard tunnel + curl ifconfig.me
# 3. Environment variable VPS_ORACLE_FRANKFURT_IP
# 4. Manual prompt

export VPS_ORACLE_FRANKFURT_IP=$(./scripts/get-vps-ip.sh)
```

### Inventory Fallback

The inventory uses fallback chain:
```yaml
ansible_host: "{{ lookup('env', 'VPS_ORACLE_FRANKFURT_IP') |
                  default(lookup('env', 'VPS_TUNNEL_IP')) |
                  default('10.100.0.2') }}"
```

## Idempotency

The role is idempotent:
- Packages only installed if missing
- Config only deployed if changed
- iptables rules checked before adding
- Service state verified

Running multiple times produces same result.

## Related Documentation

- [Cloudflare WARP Proxy Guide](CLOUDFLARE-WARP-PROXY.md) - Alternative geo-bypass approach
- [WireGuard Tunnel Setup](WIREGUARD-TUNNEL-SETUP.md) - Initial tunnel configuration
- [Node Initialization](NODE-INITIALIZATION.md) - General node bootstrap process

## Topology References

| File | Description |
|------|-------------|
| `topology/instances/network/inst.tunnel.wg-home-to-oci.yaml` | Tunnel definition |
| `topology/instances/network/inst.vlan.vpn_germany.yaml` | VLAN 55 definition |
| `topology/instances/network/inst.routing_policy.vpn_germany.yaml` | Routing policy |
| `topology/instances/vm/cloud/vps-oracle-frankfurt.yaml` | VPS instance |
| `topology/instances/devices/rtr-mikrotik-chateau.yaml` | Router definition |
