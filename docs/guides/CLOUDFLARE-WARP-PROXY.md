# Cloudflare WARP as Transparent Proxy on VPS

## Overview

This guide describes setting up Cloudflare WARP on a VPS to route traffic through Cloudflare's network, potentially bypassing datacenter IP detection.

**Status:** Experimental. Cloudflare IPs are also detected by many streaming services as VPN.

## Use Case

When a VPS IP (e.g., Oracle Cloud, AWS) is blocked by services detecting datacenter IPs, WARP can route traffic through Cloudflare's network with a different IP.

## Architecture

```
TV (192.168.55.x)
    |
    v
MikroTik (routing table: vpn-germany)
    |
    v [WireGuard wg0]
VPS (Oracle Cloud Frankfurt)
    |
    v [iptables PREROUTING -> redsocks]
redsocks (transparent proxy)
    |
    v [SOCKS5 localhost:40000]
Cloudflare WARP
    |
    v
Internet (Cloudflare IP)
```

## Installation

### 1. Install WARP on Ubuntu 24.04

```bash
# Add Cloudflare GPG key
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | \
  sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg

# Add repository
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] \
  https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/cloudflare-client.list

# Install
sudo apt-get update
sudo apt-get install -y cloudflare-warp
```

### 2. Configure WARP

```bash
# Register and accept TOS
warp-cli --accept-tos registration new

# Set proxy mode (doesn't capture all traffic, exposes SOCKS5 proxy)
warp-cli --accept-tos mode proxy

# Connect
warp-cli --accept-tos connect

# Verify
warp-cli --accept-tos status
# Should show: Status update: Connected

# Test proxy (default port 40000)
curl -x socks5://127.0.0.1:40000 -s ifconfig.me
# Should show Cloudflare IP (e.g., 104.28.x.x)
```

### 3. Install redsocks (transparent proxy)

```bash
sudo apt-get install -y redsocks
```

### 4. Configure redsocks

Create `/etc/redsocks.conf`:

```
base {
    log_debug = off;
    log_info = on;
    log = "syslog:daemon";
    daemon = on;
    redirector = iptables;
}

redsocks {
    local_ip = 0.0.0.0;
    local_port = 12345;
    ip = 127.0.0.1;
    port = 40000;
    type = socks5;
}
```

```bash
sudo systemctl enable redsocks
sudo systemctl start redsocks
```

### 5. Configure iptables

```bash
# Create REDSOCKS chain
iptables -t nat -N REDSOCKS

# Exclude local/private networks
iptables -t nat -A REDSOCKS -d 0.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 10.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 127.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 169.254.0.0/16 -j RETURN
iptables -t nat -A REDSOCKS -d 172.16.0.0/12 -j RETURN
iptables -t nat -A REDSOCKS -d 192.168.0.0/16 -j RETURN
iptables -t nat -A REDSOCKS -d 224.0.0.0/4 -j RETURN
iptables -t nat -A REDSOCKS -d 240.0.0.0/4 -j RETURN

# Redirect TCP to redsocks
iptables -t nat -A REDSOCKS -p tcp -j REDIRECT --to-ports 12345

# Apply to VPN VLAN traffic
iptables -t nat -I PREROUTING 1 -s 192.168.55.0/24 -p tcp -j REDSOCKS
```

### 6. Clear existing connections

```bash
# Install conntrack if needed
sudo apt-get install -y conntrack

# Clear connections to force new ones through WARP
sudo conntrack -D -s 192.168.55.0/24
```

## Verification

```bash
# Check iptables counters
iptables -t nat -L PREROUTING -n -v | grep REDSOCKS
iptables -t nat -L REDSOCKS -n -v | grep REDIRECT

# Check redsocks logs
journalctl -u redsocks -f

# Verify WARP IP
curl -x socks5://127.0.0.1:40000 -s ifconfig.me
```

## Cleanup / Removal

```bash
# Remove iptables rules
iptables -t nat -D PREROUTING -s 192.168.55.0/24 -p tcp -j REDSOCKS
iptables -t nat -F REDSOCKS
iptables -t nat -X REDSOCKS

# Stop services
sudo systemctl stop redsocks
sudo systemctl disable redsocks
warp-cli --accept-tos disconnect

# Clear conntrack
conntrack -D -s 192.168.55.0/24
```

## Limitations

1. **VPN Detection:** Cloudflare IPs (AS13335) are in VPN detection databases. Services like OTT TV, Netflix may still block.

2. **TCP Only:** redsocks only handles TCP. UDP traffic (DNS, some VPN protocols) bypasses the proxy.

3. **Latency:** Additional hop through Cloudflare adds latency.

4. **Conflicts:** May interfere with VPN apps (ProtonVPN) running on client devices.

## Comparison with Alternatives

| Solution | Datacenter Detection | VPN Detection | Cost |
|----------|---------------------|---------------|------|
| Direct VPS IP | Blocked | N/A | Free |
| Cloudflare WARP | Bypassed | Blocked | Free |
| ProtonVPN (app) | Bypassed | Bypassed | Subscription |
| Residential Proxy | Bypassed | Bypassed | $5-15/mo |

## Conclusion

WARP can bypass datacenter IP detection but is itself detected as a VPN by many streaming services. For services with strict VPN detection (OTT TV, Netflix), dedicated VPN apps like ProtonVPN remain the most reliable solution.
