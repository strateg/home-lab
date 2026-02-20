# VPN Client Setup Guide

This guide covers client configuration for the home lab VPN infrastructure.

## Overview

| VPN Type | Server | Port | Use Case |
|----------|--------|------|----------|
| WireGuard | MikroTik Chateau | 51820/UDP | Full LAN access, mobile devices |
| Tailscale | MikroTik Container | Dynamic | Zero-config mesh, cloud servers |

---

## WireGuard Client Configuration

### Network Details

- **Server Endpoint**: `home.example.com:51820` (replace with your domain/IP)
- **VPN Subnet**: `10.0.200.0/24`
- **Server Address**: `10.0.200.1`
- **DNS**: `192.168.88.1` (AdGuard Home)

### Full Tunnel Configuration

Routes all traffic through home network:

```ini
[Interface]
PrivateKey = <YOUR_CLIENT_PRIVATE_KEY>
Address = 10.0.200.X/24
DNS = 192.168.88.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = home.example.com:51820
PersistentKeepalive = 25
```

### Split Tunnel Configuration

Only routes home network traffic through VPN:

```ini
[Interface]
PrivateKey = <YOUR_CLIENT_PRIVATE_KEY>
Address = 10.0.200.X/24
DNS = 192.168.88.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
AllowedIPs = 192.168.88.0/24, 10.0.30.0/24, 10.0.99.0/24, 10.0.200.0/24
Endpoint = home.example.com:51820
PersistentKeepalive = 25
```

### Accessible Networks via WireGuard

| Network | CIDR | Access |
|---------|------|--------|
| LAN | 192.168.88.0/24 | Full |
| Servers | 10.0.30.0/24 | Full |
| Management | 10.0.99.0/24 | Full |
| VPN Peers | 10.0.200.0/24 | Full |
| IoT | 192.168.40.0/24 | Blocked |
| Guest | 192.168.30.0/24 | Blocked |

---

## Tailscale Client Setup

### Installation

```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install tailscale

# Windows
# Download from https://tailscale.com/download
```

### Connect to Network

```bash
# Basic connection
tailscale up

# Accept advertised routes from MikroTik
tailscale up --accept-routes

# Use as exit node (route all traffic)
tailscale up --exit-node=<mikrotik-tailscale-ip>
```

### Accessible Networks via Tailscale

| Network | CIDR | Access |
|---------|------|--------|
| LAN | 192.168.88.0/24 | Via subnet routing |
| Servers | 10.0.30.0/24 | Via subnet routing |
| Tailscale Mesh | 100.64.0.0/10 | Direct |
| Management | 10.0.99.0/24 | Blocked |

### MagicDNS

Tailscale provides automatic DNS for devices:
- `device-name.tailnet-name.ts.net`

---

## Troubleshooting

### WireGuard Connection Issues

```bash
# Check handshake status
wg show

# Test connectivity
ping 10.0.200.1

# Check if endpoint is reachable
nc -vzu home.example.com 51820
```

### Tailscale Connection Issues

```bash
# Check status
tailscale status

# Check network connectivity
tailscale ping <peer-ip>

# Debug mode
tailscale up --reset
```

### Common Problems

| Problem | Solution |
|---------|----------|
| No handshake | Check firewall, verify endpoint, check keys |
| Slow connection | Disable PersistentKeepalive or increase value |
| DNS not working | Verify DNS server is reachable, check AdGuard status |
| Can't reach LAN | Check AllowedIPs includes target subnet |

---

## Security Notes

1. **Never share private keys** - Generate new keys for each device
2. **Use split tunnel when possible** - Reduces load on home connection
3. **Rotate keys periodically** - Recommended every 90 days
4. **Monitor connections** - Check Grafana VPN dashboard for anomalies

---

## Related Documentation

- [Home Russia VPN Setup](HOME-RUSSIA-VPN-SETUP.md) - Specific setup for Russia access
- [AmneziaWG Setup](AMNEZIAWG-SETUP.md) - Obfuscated WireGuard for censored networks
- [VPN Topology Template](../../scripts/templates/docs/vpn-topology.md.j2) - Source template for generated diagram
- Local generated output: `generated/docs/vpn-topology.md` (after `python scripts/topology/generate-docs.py`)
