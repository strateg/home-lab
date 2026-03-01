# ADR 0051: Build Pipeline and Target-Centric Deploy Packages

- Status: Proposed
- Date: 2026-03-01

## Context

### Current Problems

The project has evolved organically, resulting in several structural issues:

#### 1. Scattered Manual Sources

Manual scripts and configurations are spread across multiple directories:

| Directory | Content |
|-----------|---------|
| `ansible/` | Playbooks, roles, manual inventory |
| `bootstrap/mikrotik/` | MikroTik bootstrap scripts |
| `manual-scripts/bare-metal/` | Proxmox USB installer, post-install scripts |
| `manual-scripts/opi5/` | Orange Pi 5 installation |
| `manual-scripts/openwrt/` | OpenWRT scripts |
| `configs/` | Device configs (GL.iNet, VPN) |
| `scripts/` | Utility scripts |

This fragmentation makes it difficult to understand what needs to be deployed where.

#### 2. Duplication Between Manual and Generated

| Artifact | Manual Location | Generated Location |
|----------|-----------------|-------------------|
| MikroTik init-terraform.rsc | `bootstrap/mikrotik/init-terraform.rsc` | `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc` |
| Ansible inventory hosts.yml | `ansible/inventory/production/hosts.yml` | `generated/ansible/inventory/production/hosts.yml` |
| Ansible group_vars/all.yml | `ansible/inventory/production/group_vars/all.yml` | `generated/ansible/inventory/production/group_vars/all.yml` |

The manual versions contain richer configuration (admin_users, backup policies, service registry), while generated versions contain only topology-derived data. No clear merge strategy exists.

#### 3. No Unified Deploy Artifact

When deploying to a target device, there is no single directory containing everything needed:
- Terraform files are in `generated/terraform/`
- Ansible playbooks are in `ansible/playbooks/`
- Ansible inventory is split between `ansible/inventory/` and `generated/ansible/inventory/`
- Bootstrap scripts are scattered across multiple locations

#### 4. Unclear Deployment Flow

The current `deploy/phases/` scripts assume a specific directory layout, but:
- No clear "build" step assembles all artifacts
- No validation that all required files exist
- No versioning of deploy packages

### Requirements

1. **Separation of Concerns**: Clear distinction between manual sources, generated output, and deploy artifacts
2. **Target-Centric Packaging**: Each target device should have a self-contained deploy package
3. **Merge Strategy**: Define how manual and generated content combine
4. **CI/CD Ready**: Build process should produce versioned, deployable artifacts
5. **Backward Compatible**: Existing workflows should continue to work during migration

## Decision

### 1. Consolidated Source Directory (`src/`)

All manual sources consolidate under `src/`:

```
src/
├── ansible/
│   ├── playbooks/              # Ansible playbooks
│   ├── roles/                  # Ansible roles
│   └── inventory-config/       # Manual inventory configuration
│       ├── group_vars/
│       │   └── all.yml         # Rich config: admin_users, backup, services
│       └── host_vars/
│           └── *.yml           # Per-host overrides
│
├── bootstrap/
│   ├── mikrotik/               # MikroTik manual scripts
│   │   ├── bootstrap.rsc       # Initial bootstrap
│   │   └── exported_config.rsc # Reference export
│   ├── proxmox/                # Proxmox bare-metal
│   │   ├── create-usb.sh       # USB installer creator
│   │   ├── answer.toml         # Auto-install answers
│   │   └── post-install/       # Post-installation scripts
│   │       ├── 01-install-terraform.sh
│   │       ├── 02-install-ansible.sh
│   │       ├── 03-configure-storage.sh
│   │       ├── 04-configure-network.sh
│   │       ├── 05-init-git-repo.sh
│   │       └── 06-enable-zswap.sh
│   └── opi5/                   # Orange Pi 5
│       └── install.sh
│
├── configs/                    # Device-specific configurations
│   ├── glinet/
│   │   ├── home/
│   │   └── travel/
│   └── vpn/
│       ├── oracle-cloud/
│       └── russia-vps/
│
└── scripts/                    # Utility scripts
    └── *.sh
```

### 2. Build Pipeline

```
┌─────────────────┐
│    topology/    │
│     L0-L7       │
└────────┬────────┘
         │
         │ [1] generate
         ▼
┌─────────────────┐          ┌─────────────────┐
│   generated/    │          │      src/       │
│   - terraform/  │          │   - ansible/    │
│   - ansible/    │          │   - bootstrap/  │
│   - bootstrap/  │          │   - configs/    │
│   - docs/       │          └────────┬────────┘
└────────┬────────┘                   │
         │                            │
         │         [2] assemble       │
         └──────────────┬─────────────┘
                        ▼
               ┌─────────────────┐
               │      dist/      │
               │  (per-target    │
               │   packages)     │
               └────────┬────────┘
                        │
                        │ [3] deploy
                        ▼
               ┌─────────────────┐
               │  Target Devices │
               └─────────────────┘
```

**Phase 1: Generate** (`make generate`)
- Runs `topology-tools/regenerate-all.py`
- Outputs to `generated/`

**Phase 2: Assemble** (`make assemble`)
- Runs `topology-tools/assemble-deploy.py`
- Merges `generated/` + `src/` → `dist/`
- Creates per-target packages

**Phase 3: Deploy** (`make deploy-<target>`)
- Deploys specific target package
- Or `make deploy-all` for full deployment

### 3. Target-Centric Deploy Packages (`dist/`)

Each target device gets a self-contained package:

```
dist/
├── rtr-mikrotik-chateau/
│   ├── terraform/
│   │   ├── provider.tf
│   │   ├── interfaces.tf
│   │   ├── firewall.tf
│   │   ├── dhcp.tf
│   │   ├── dns.tf
│   │   ├── vpn.tf
│   │   ├── containers.tf
│   │   ├── qos.tf
│   │   └── terraform.tfvars
│   ├── bootstrap/
│   │   ├── init-terraform.rsc    # ← generated
│   │   └── bootstrap.rsc         # ← src/bootstrap/mikrotik/
│   ├── deploy.sh                 # Target-specific deploy script
│   └── README.md
│
├── srv-gamayun/                  # Proxmox server
│   ├── terraform/
│   │   ├── provider.tf
│   │   ├── bridges.tf
│   │   ├── lxc.tf
│   │   ├── vms.tf
│   │   └── terraform.tfvars
│   ├── ansible/
│   │   ├── inventory/
│   │   │   ├── hosts.yml         # ← generated
│   │   │   ├── group_vars/
│   │   │   │   └── all.yml       # ← MERGED (generated base + src/ overrides)
│   │   │   └── host_vars/
│   │   │       └── *.yml         # ← src/ansible/inventory-config/
│   │   ├── playbooks/            # ← src/ansible/playbooks/
│   │   └── roles/                # ← src/ansible/roles/
│   ├── post-install/             # ← src/bootstrap/proxmox/post-install/
│   ├── deploy.sh
│   └── README.md
│
├── srv-orangepi5/
│   ├── cloud-init/               # ← generated/bootstrap/srv-orangepi5/
│   ├── install.sh                # ← src/bootstrap/opi5/
│   ├── configs/                  # ← src/configs/ (relevant subset)
│   ├── deploy.sh
│   └── README.md
│
└── tools/
    └── usb-installer/            # Proxmox USB installer
        ├── create-usb.sh         # ← src/bootstrap/proxmox/
        ├── answer.toml
        └── README.md
```

### 4. Ansible Inventory Merge Strategy

The assembler merges Ansible inventory using overlay approach:

```yaml
# dist/srv-gamayun/ansible/inventory/group_vars/all.yml

# ============================================================
# BASE CONFIGURATION (from generated)
# ============================================================
# Source: generated/ansible/inventory/production/group_vars/all.yml

networks:
  net-servers:
    cidr: "10.0.30.0/24"
    gateway: "10.0.30.1"
    vlan: 30
# ... other generated content

# ============================================================
# EXTENDED CONFIGURATION (from src/)
# ============================================================
# Source: src/ansible/inventory-config/group_vars/all.yml

admin_users:
  - name: admin
    ssh_keys: ["{{ lookup('file', '~/.ssh/id_rsa.pub') }}"]

backup_retention:
  keep_last: 3
  keep_daily: 7

services:
  postgresql:
    host: 10.0.30.10
    port: 5432
# ... other manual config
```

**Merge Rules:**
1. `hosts.yml`: Use generated version (topology is source of truth for hosts)
2. `group_vars/all.yml`: Deep merge (generated base + src/ extensions)
3. `host_vars/*.yml`: Copy from src/ (manual overrides only)

### 5. Assembler Implementation

New script `topology-tools/assemble-deploy.py`:

```python
class DeployAssembler:
    """Assembles deploy packages from generated + src."""

    TARGETS = {
        'rtr-mikrotik-chateau': {
            'type': 'mikrotik',
            'terraform': 'generated/terraform/mikrotik',
            'bootstrap_generated': 'generated/bootstrap/rtr-mikrotik-chateau',
            'bootstrap_manual': 'src/bootstrap/mikrotik',
        },
        'srv-gamayun': {
            'type': 'proxmox',
            'terraform': 'generated/terraform/proxmox',
            'ansible_generated': 'generated/ansible/inventory/production',
            'ansible_manual': 'src/ansible',
            'bootstrap_manual': 'src/bootstrap/proxmox/post-install',
        },
        'srv-orangepi5': {
            'type': 'sbc',
            'bootstrap_generated': 'generated/bootstrap/srv-orangepi5',
            'bootstrap_manual': 'src/bootstrap/opi5',
        },
    }

    def assemble_all(self) -> bool:
        """Assemble all target packages."""
        for target, config in self.TARGETS.items():
            self.assemble_target(target, config)
        return True

    def assemble_target(self, target: str, config: dict) -> None:
        """Assemble single target package."""
        dist_dir = Path(f'dist/{target}')
        dist_dir.mkdir(parents=True, exist_ok=True)

        # Copy terraform
        if 'terraform' in config:
            shutil.copytree(config['terraform'], dist_dir / 'terraform')

        # Merge ansible
        if 'ansible_generated' in config:
            self.merge_ansible(
                dist_dir / 'ansible',
                config['ansible_generated'],
                config['ansible_manual']
            )

        # Copy bootstrap (generated + manual)
        if 'bootstrap_generated' in config:
            shutil.copytree(config['bootstrap_generated'], dist_dir / 'bootstrap')
        if 'bootstrap_manual' in config:
            self.copy_manual_bootstrap(config['bootstrap_manual'], dist_dir / 'bootstrap')

        # Generate deploy script
        self.generate_deploy_script(target, config, dist_dir)
```

### 6. Updated Makefile

```makefile
# ============================================================
# Build Pipeline
# ============================================================

.PHONY: generate assemble build clean

generate:
	@echo "=== Generating from topology ==="
	python3 topology-tools/regenerate-all.py

assemble: generate
	@echo "=== Assembling deploy packages ==="
	python3 topology-tools/assemble-deploy.py

build: assemble
	@echo "=== Build complete ==="
	@echo "Deploy packages ready in dist/"
	@ls -la dist/

clean:
	rm -rf dist/
	rm -rf generated/

# ============================================================
# Target-specific Deployment
# ============================================================

deploy-mikrotik: build
	@echo "=== Deploying to MikroTik ==="
	cd dist/rtr-mikrotik-chateau && ./deploy.sh

deploy-proxmox: build
	@echo "=== Deploying to Proxmox ==="
	cd dist/srv-gamayun && ./deploy.sh

deploy-opi5: build
	@echo "=== Deploying to Orange Pi 5 ==="
	cd dist/srv-orangepi5 && ./deploy.sh

deploy-all: deploy-mikrotik deploy-proxmox deploy-opi5

# ============================================================
# CI/CD Targets
# ============================================================

ci-build: build
	@echo "=== Creating release artifact ==="
	tar -czf home-lab-deploy-$(shell date +%Y%m%d-%H%M%S).tar.gz dist/

ci-validate: build
	@echo "=== Validating deploy packages ==="
	cd dist/rtr-mikrotik-chateau/terraform && terraform validate
	cd dist/srv-gamayun/terraform && terraform validate
	cd dist/srv-gamayun/ansible && ansible-inventory -i inventory --list > /dev/null
```

### 7. CI/CD Integration

```yaml
# .github/workflows/build-deploy.yml
name: Build Deploy Packages

on:
  push:
    branches: [main]
    paths:
      - 'topology/**'
      - 'src/**'
      - 'topology-tools/**'
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r topology-tools/requirements.txt

      - name: Generate from topology
        run: make generate

      - name: Assemble deploy packages
        run: make assemble

      - name: Validate packages
        run: make ci-validate

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: deploy-packages-${{ github.sha }}
          path: dist/
          retention-days: 30

  release:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: deploy-packages-${{ github.sha }}

      - name: Create release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: deploy-${{ github.run_number }}
          files: |
            dist/**/*
```

## Consequences

### Positive

1. **Clear Separation**: `topology/` → `generated/` → `dist/` pipeline is explicit
2. **Target-Centric**: Each device has everything it needs in one directory
3. **No Duplication**: Single source for each artifact type
4. **Merge Strategy**: Defined rules for combining generated and manual content
5. **CI/CD Ready**: Automated builds produce versioned artifacts
6. **Self-Documenting**: Each `dist/<target>/` contains its own README

### Negative / Trade-offs

1. **Migration Required**: Existing scripts need to be moved to `src/`
2. **Build Step**: Deployment now requires explicit `make build` step
3. **Disk Space**: `dist/` duplicates some content from `src/` and `generated/`
4. **Learning Curve**: Team needs to understand new workflow

### Migration Impact

| Current Location | New Location |
|------------------|--------------|
| `ansible/playbooks/` | `src/ansible/playbooks/` |
| `ansible/roles/` | `src/ansible/roles/` |
| `ansible/inventory/production/group_vars/` | `src/ansible/inventory-config/group_vars/` |
| `bootstrap/mikrotik/` | `src/bootstrap/mikrotik/` |
| `manual-scripts/bare-metal/` | `src/bootstrap/proxmox/` |
| `manual-scripts/opi5/` | `src/bootstrap/opi5/` |
| `configs/` | `src/configs/` |
| `scripts/` | `src/scripts/` |

**Deprecated (to be removed):**
- `ansible/inventory/production/hosts.yml` — use generated version
- `bootstrap/mikrotik/init-terraform.rsc` — use generated version

## Implementation Phases

### Phase 1: Create `src/` Structure
1. Create `src/` directory structure
2. Move manual sources (preserve git history with `git mv`)
3. Update `.gitignore` for `dist/`

### Phase 2: Implement Assembler
1. Create `topology-tools/assemble-deploy.py`
2. Implement target-specific assembly logic
3. Implement Ansible inventory merge

### Phase 3: Update Build System
1. Update `deploy/Makefile` with new targets
2. Create per-target `deploy.sh` scripts
3. Add `ci-validate` target

### Phase 4: CI/CD Integration
1. Create GitHub Actions workflow
2. Add artifact upload
3. Optional: auto-release on main

### Phase 5: Cleanup
1. Remove deprecated duplicate files
2. Update CLAUDE.md with new workflow
3. Update documentation

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0028: topology-tools Architecture Consolidation
- CLAUDE.md: Project Guidelines
