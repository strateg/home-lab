# ADR 0049: MikroTik Bootstrap Automation

**Date:** 2026-02-28
**Status:** Superseded
**Superseded by:** ADR 0048 (topology consolidation), ADR 0057 (Netinstall bootstrap and Terraform handover)
**Related:** ADR 0048 (Topology Architecture)

---

## Context

### Problem

MikroTik router requires manual initial configuration before Terraform can manage it via REST API. Current workflow:

1. Manual: Connect via WinBox
2. Manual: Paste bootstrap script
3. Manual: Change password
4. Manual: Create terraform.tfvars
5. Automated: Run Terraform

**Goal:** Automate steps 1-4 from command line using topology as source of truth.

### Constraints

- After soft reset, router has:
  - IP: 192.168.88.1/24 on bridge
  - User: admin (no password)
  - SSH: enabled on port 22
  - REST API: disabled

- Bootstrap must enable REST API before Terraform can work
- Single source of truth: topology YAML files

---

## Research: CLI Deployment Options

### Option 1: SSH (Recommended)

RouterOS supports SSH after soft reset (default enabled).

```bash
# Execute commands via SSH
ssh admin@192.168.88.1 '/system identity print'

# Execute script file
ssh admin@192.168.88.1 < bootstrap.rsc

# Or with scp + import
scp bootstrap.rsc admin@192.168.88.1:/
ssh admin@192.168.88.1 '/import bootstrap.rsc'
```

**Pros:** Works out of box, no additional tools
**Cons:** Requires SSH key or password auth

### Option 2: MAC-Telnet

Works even without IP configuration.

```bash
# Linux: install mac-telnet
sudo apt install mac-telnet-client

# Connect via MAC address
mac-telnet AA:BB:CC:DD:EE:FF
```

**Pros:** Works without network config
**Cons:** Requires knowing MAC address, manual interaction

### Option 3: REST API

Not available until bootstrap completes (chicken-and-egg).

### Option 4: Serial Console

Physical access required.

### Decision

**Use SSH** for bootstrap deployment:
- Works after soft reset
- Scriptable from command line
- No additional tools required

---

## Design

### 1. Bootstrap Generator

Generate `bootstrap.rsc` from topology:

**Input:** Topology YAML files
**Output:** `generated/bootstrap/mikrotik/init-terraform.rsc`

**Data extracted from topology:**
- Router IP: `L2-network/networks/net-lan.yaml` → gateway
- Router identity: `L1-foundation/devices/.../rtr-mikrotik-chateau.yaml` → name
- DNS domain: `L5-application/dns/zones.yaml` → domain
- LAN network: `L2-network/networks/net-lan.yaml` → cidr

### 2. Bootstrap Deployer

CLI tool to deploy bootstrap script:

```bash
python topology-tools/deploy-mikrotik-bootstrap.py \
  --router 192.168.88.1 \
  --user admin \
  --password "" \
  --script generated/bootstrap/mikrotik/init-terraform.rsc
```

**Steps:**
1. Connect via SSH to router
2. Upload bootstrap script
3. Execute script
4. Verify REST API is available
5. Output terraform.tfvars template with generated password

### 3. Integration with Makefile

```makefile
# deploy/Makefile
bootstrap-mikrotik:
	python topology-tools/deploy-mikrotik-bootstrap.py

deploy-mikrotik: bootstrap-mikrotik
	cd generated/terraform-mikrotik && terraform apply
```

---

## Implementation Plan

### Phase 1: Generator

```
topology-tools/
├── scripts/
│   └── generators/
│       └── bootstrap/
│           └── mikrotik/
│               ├── __init__.py
│               ├── generator.py    # Generate bootstrap.rsc
│               └── cli.py
└── templates/
    └── bootstrap/
        └── mikrotik/
            └── init-terraform.rsc.j2
```

**Template variables:**
```yaml
router_name: "MikroTik-Chateau"
router_ip: "192.168.88.1"
lan_network: "192.168.88.0/24"
dns_domain: "lan"
dns_servers: ["1.1.1.1", "8.8.8.8"]
terraform_password: "{{ generated_or_provided }}"
api_port: 8443
```

### Phase 2: Deployer

```
topology-tools/
├── scripts/
│   └── deployers/
│       └── mikrotik_bootstrap.py   # SSH-based deployer
```

**Features:**
- SSH connection with paramiko or subprocess
- Password generation (secure random)
- Script upload and execution
- REST API health check
- Output terraform.tfvars

### Phase 3: Integration

- Add to `regenerate-all.py`
- Add to `deploy/Makefile`
- Update documentation

---

## Security Considerations

1. **Generated passwords:** Use cryptographically secure random
2. **Password storage:** Output to terraform.tfvars (gitignored)
3. **SSH keys:** Support key-based auth for automation
4. **Firewall:** Bootstrap restricts API to LAN only

---

## Success Criteria

- [ ] Bootstrap script generated from topology
- [ ] CLI tool deploys script via SSH
- [ ] REST API verified after deployment
- [ ] terraform.tfvars auto-generated with password
- [ ] Full automation: `make bootstrap-mikrotik deploy-mikrotik`

---

## Example Workflow

```bash
# 1. After MikroTik soft reset, from workstation:
make bootstrap-mikrotik

# Output:
# Connecting to 192.168.88.1...
# Uploading bootstrap script...
# Executing bootstrap...
# Verifying REST API...
#
# SUCCESS! Router bootstrapped.
# Password: Xk9#mP2$vL7@nQ4w
# terraform.tfvars created at: generated/terraform-mikrotik/terraform.tfvars
#
# Next: make deploy-mikrotik

# 2. Deploy full configuration
make deploy-mikrotik

# 3. Verify
curl -k https://192.168.88.1:8443/rest/system/identity
```

---

## References

- `bootstrap/mikrotik/` - Current manual scripts
- `topology/L1-foundation/devices/owned/network/rtr-mikrotik-chateau.yaml`
- `topology/L2-network/networks/net-lan.yaml`
- MikroTik Wiki: SSH, REST API

---

**Next Steps:**
1. Review and approve ADR
2. Implement Phase 1 (generator)
3. Implement Phase 2 (deployer)
4. Test on real hardware
