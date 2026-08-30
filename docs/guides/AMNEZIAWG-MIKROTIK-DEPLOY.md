# AmneziaWG Container Deployment on MikroTik

## Overview

This guide covers deploying AmneziaWG (AWG) VPN tunnels on MikroTik using the awg-proxy container architecture.

### Architecture

```
VLAN clients -> mangle marks -> routing table -> WireGuard interface
                                                        |
                                                        v
                                              veth (172.18.x.x)
                                                        |
                                                        v
                                              awg-proxy container
                                              (AWG obfuscation)
                                                        |
                                                        v
                                              VPN server (remote)
```

**Key components:**
- **Native WireGuard interface** - handles encryption (hardware-accelerated)
- **awg-proxy container** - adds AWG 3.0 obfuscation (S1-S4, H1-H4, HeaderProtectionKey)
- **veth pair** - connects WG interface to container

## Prerequisites

1. MikroTik RouterOS 7.x with Container package
2. USB storage mounted at `/usb1`
3. AWG configuration from VPN provider (exported .conf file)
4. SOPS + age configured for secrets

## Adding New Country

### Step 1: Export Configuration from AmneziaVPN

1. Open AmneziaVPN app on mobile/desktop
2. Export configuration for the desired server
3. Save as `{country}.conf` (e.g., `russia.conf`, `germany.conf`)

Example `russia.conf`:
```ini
[Interface]
Address = 100.98.32.29/32
PrivateKey = 0oKuHsTu58UQqdf7T2DtATgi/OwaWN8YW8hyaGH/ZFY=
Jc = 7
Jmin = 10
Jmax = 80
S1 = 299
S2 = 838
S3 = 1181
S4 = 12
H1 = 1
H2 = 2
H3 = 3
H4 = 4
HeaderProtectionKey = 2PVpIksUUzRDrKyyXzJcWtSBG2NyudUHjFnIC+9H9nI=

[Peer]
PublicKey = pWFHNTQ2NKzipagkez3OIlgXZr7qKCSZu2K2fbEh4Bw=
PresharedKey = CNIeGi/u/omF8Qp65XmSxC7W/3TNeDUlSvE0KcyePnY=
Endpoint = 178.130.51.136:4714
PersistentKeepalive = 25
```

### Step 2: Derive Public Key

```bash
echo "PRIVATE_KEY_FROM_CONF" | wg pubkey
```

Save this - needed for `client_public_key` in secrets.

### Step 3: Update Secrets

Edit `projects/home-lab/secrets/terraform/mikrotik.yaml`:

```bash
sops projects/home-lab/secrets/terraform/mikrotik.yaml
```

Add under `amneziawg:`:

```yaml
amneziawg:
  {country}:  # e.g., russia, germany, sweden
    endpoint: "{IP}:{PORT}"                    # From [Peer] Endpoint
    client_private_key: "{PRIVATE_KEY}"        # From [Interface] PrivateKey
    client_public_key: "{DERIVED_PUBLIC_KEY}"  # From Step 2
    server_public_key: "{SERVER_PUBLIC_KEY}"   # From [Peer] PublicKey
    preshared_key: "{PRESHARED_KEY}"           # From [Peer] PresharedKey
    header_protection_key: "{HPK}"             # From [Interface] HeaderProtectionKey
    tunnel_address: "{ADDRESS}"                # From [Interface] Address
```

### Step 4: Create Topology Files

#### 4.1 Container Instance

Create `projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-amneziawg-{country}.yaml`:

```yaml
@instance: docker-amneziawg-{country}
@extends: obj.routeros.container.generic
@group: routeros_container
@version: 1.0.0
source_id: docker-amneziawg-{country}
notes: |
  AWG-Proxy container for obfuscated VPN exit to {Country}.

host_ref: rtr-mikrotik-chateau

network:
  type: dedicated_veth
  veth_name: veth-awg-{cc}      # 2-letter country code
  address: 172.18.{X}.2/30     # Unique /30 subnet
  gateway: 172.18.{X}.1

runtime:
  name: awg-proxy-{country}
  image: ghcr.io/timbrs/awg-proxy:latest
  architecture: arm64
  root_dir: /usb1/containers/awg-proxy-{country}
  start_on_boot: true
  logging: true
  privileged: true
  mounts: []

  env:
    AWG_LISTEN: ":51820"
    AWG_REMOTE_REF: secrets.mikrotik.amneziawg.{country}.endpoint
    AWG_JC: "{Jc}"
    AWG_JMIN: "{Jmin}"
    AWG_JMAX: "{Jmax}"
    AWG_S1: "{S1}"
    AWG_S2: "{S2}"
    AWG_S3: "{S3}"
    AWG_S4: "{S4}"
    AWG_H1: "{H1}"
    AWG_H2: "{H2}"
    AWG_H3: "{H3}"
    AWG_H4: "{H4}"
    AWG_SERVER_PUB_REF: secrets.mikrotik.amneziawg.{country}.server_public_key
    AWG_CLIENT_PUB_REF: secrets.mikrotik.amneziawg.{country}.client_public_key
    AWG_HEADER_PROTECTION_KEY_REF: secrets.mikrotik.amneziawg.{country}.header_protection_key
    AWG_MODE: "normal"

wireguard_interface:
  name: wg-awg-{country}
  listen_port: 518{XX}         # Unique port
  private_key_ref: secrets.mikrotik.amneziawg.{country}.client_private_key
  address: {TUNNEL_ADDRESS}    # From config
  peer:
    public_key_ref: secrets.mikrotik.amneziawg.{country}.server_public_key
    preshared_key_ref: secrets.mikrotik.amneziawg.{country}.preshared_key
    endpoint: 172.18.{X}.2:51820
    allowed_ips:
      - 0.0.0.0/0
    persistent_keepalive: 25

routing_policy_ref: inst.routing_policy.vpn_{country}
serves_vlan_ref: inst.vlan.vpn_{country}

tunnel_nat:
  enabled: true
  out_interface: wg-awg-{country}
```

#### 4.2 VLAN Instance (if new VLAN needed)

Create `projects/home-lab/topology/instances/network/inst.vlan.vpn_{country}.yaml`:

```yaml
@instance: inst.vlan.vpn_{country}
@extends: obj.network.vlan
vlan_id: {VLAN_ID}
name: VPN-{Country}
cidr: 192.168.{VLAN_ID}.0/24
```

#### 4.3 Routing Policy (if new policy needed)

Create or update routing policy in `projects/home-lab/topology/instances/routing/`.

### Step 5: Compile Topology

```bash
.venv/bin/python topology-tools/compile-topology.py
```

### Step 6: Deploy with Ansible

```bash
cd projects/home-lab/ansible
ansible-playbook -i inventory-overrides/production/hosts.yml \
  playbooks/mikrotik-awg-deploy.yml --tags {country}
```

Or deploy all AWG tunnels:

```bash
ansible-playbook -i inventory-overrides/production/hosts.yml \
  playbooks/mikrotik-awg-deploy.yml
```

### Step 7: Verify

```bash
# SSH to MikroTik
ssh automator@192.168.88.1

# Check WireGuard interface
/interface wireguard print where name~"awg-{country}"

# Check peer handshake
/interface wireguard peers print detail where interface=wg-awg-{country}
# Expected: last-handshake < 2 minutes

# Check container
/container print where name=awg-proxy-{country}
# Expected: RUNNING
```

## Ansible Playbook Reference

**Location:** `projects/home-lab/ansible/playbooks/mikrotik-awg-deploy.yml`

**Tags:**
- `russia` - Deploy Russia tunnel only
- `sweden` - Deploy Sweden tunnel only
- `awg` - Deploy all AWG tunnels
- `verify` - Verification only

**What it does:**
1. Updates WireGuard interface private key
2. Updates WireGuard peer public/preshared keys
3. Stops container
4. Updates container environment variables
5. Starts container
6. Displays handshake status

## Updating Existing Country

When VPN provider issues new configuration:

1. Export new `.conf` file from AmneziaVPN
2. Update secrets with new keys:
   ```bash
   sops projects/home-lab/secrets/terraform/mikrotik.yaml
   ```
3. Derive and add new `client_public_key` if private key changed
4. Run Ansible playbook:
   ```bash
   ansible-playbook -i inventory-overrides/production/hosts.yml \
     playbooks/mikrotik-awg-deploy.yml --tags {country}
   ```

## Troubleshooting

### No Handshake (last-handshake > 5 minutes)

1. **Check container is running:**
   ```
   /container print where name~"awg"
   ```

2. **Check container logs:**
   ```
   /log print where topics~"container"
   ```

3. **Verify keys match:**
   - Container `AWG_CLIENT_PUB` must match WireGuard interface public key
   - Container `AWG_SERVER_PUB` must match peer public key

4. **Check network connectivity:**
   ```
   /ping 172.18.{X}.2  # Container IP
   ```

### Container Not Starting

1. **Check image exists:**
   ```
   /container print
   ```

2. **Check USB storage:**
   ```
   /file print where name~"usb1"
   ```

3. **Pull image manually:**
   ```
   /container/add remote-image=ghcr.io/timbrs/awg-proxy:latest ...
   ```

### Internet Not Working Through VPN

1. **Check NAT rule:**
   ```
   /ip firewall nat print where out-interface~"wg-awg"
   ```

2. **Check routing table:**
   ```
   /ip route print where routing-table=awg-{country}
   ```

3. **Check mangle marks:**
   ```
   /ip firewall mangle print where new-routing-mark~"awg"
   ```

## Network Assignments

| Country | VLAN | Subnet | veth IP | WG Port |
|---------|------|--------|---------|---------|
| Russia | 57 | 192.168.57.0/24 | 172.18.22.2/30 | 51825 |
| Sweden | 58 | 192.168.58.0/24 | 172.18.23.2/30 | 51824 |

## Files Reference

| Purpose | Path |
|---------|------|
| MikroTik secrets | `projects/home-lab/secrets/terraform/mikrotik.yaml` |
| Container topology | `projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/` |
| Ansible playbook | `projects/home-lab/ansible/playbooks/mikrotik-awg-deploy.yml` |
| Ansible inventory | `projects/home-lab/ansible/inventory-overrides/production/hosts.yml` |
