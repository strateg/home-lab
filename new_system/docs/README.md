# Home Lab Documentation

Welcome to the home lab infrastructure documentation! This directory contains all documentation organized by topic.

---

## 📂 Documentation Structure

```
docs/
├── README.md                    # ← You are here
├── CHANGELOG.md                 # Project changelog (v2.1.0)
├── CHANGELOG-GENERATED-DIR.md   # Generated directory changelog
├── guides/                      # Practical how-to guides
│   ├── BRIDGES.md               # Network bridges setup (Terraform + Manual)
│   ├── GENERATED-QUICK-GUIDE.md # Generated directory quick reference
│   ├── ANSIBLE-VAULT-GUIDE.md   # Secrets management with Ansible Vault
│   └── RAM-OPTIMIZATION.md      # RAM optimization strategies (8GB constraint)
├── architecture/                # Architecture and design decisions
│   ├── TOPOLOGY-MODULAR.md      # Modular topology structure (v2.2)
│   └── MIGRATION-V1-TO-V2.md    # Migration guide from v1.1 to v2.0
└── archive/                     # Historical documents (superseded)
    ├── TOPOLOGY-ANALYSIS.md
    ├── TOPOLOGY-V2-ANALYSIS.md
    └── TOPOLOGY-IMPROVEMENTS-SUMMARY.md
```

---

## 🚀 Quick Start

### For New Users

1. **Understand the architecture**: Read [TOPOLOGY-MODULAR.md](architecture/TOPOLOGY-MODULAR.md)
2. **Learn the workflow**: Read [GENERATED-QUICK-GUIDE.md](guides/GENERATED-QUICK-GUIDE.md)
3. **Set up bridges**: Follow [BRIDGES.md](guides/BRIDGES.md) (Terraform automation)
4. **Manage secrets**: Read [ANSIBLE-VAULT-GUIDE.md](guides/ANSIBLE-VAULT-GUIDE.md)

### For Existing Users

- **Changelog**: See [CHANGELOG.md](CHANGELOG.md) for recent changes
- **Guides**: Browse [guides/](guides/) for specific how-tos
- **Architecture**: See [architecture/](architecture/) for design decisions

---

## 📚 Documentation by Topic

### 🔧 Infrastructure Setup

| Document | Description | Audience |
|----------|-------------|----------|
| [BRIDGES.md](guides/BRIDGES.md) | Network bridges setup (Terraform + manual methods) | DevOps, Network Admin |
| [GENERATED-QUICK-GUIDE.md](guides/GENERATED-QUICK-GUIDE.md) | Quick reference for generated/ directory workflow | All Users |
| [RAM-OPTIMIZATION.md](guides/RAM-OPTIMIZATION.md) | RAM allocation strategies for 8GB constraint | DevOps, Sysadmin |

### 🏗️ Architecture

| Document | Description | Audience |
|----------|-------------|----------|
| [TOPOLOGY-MODULAR.md](architecture/TOPOLOGY-MODULAR.md) | Modular topology structure (36 lines main + 13 modules) | Developers, Architects |
| [MIGRATION-V1-TO-V2.md](architecture/MIGRATION-V1-TO-V2.md) | v1.1 → v2.0 migration guide (historical) | Architects, Lead Devs |

### 🔒 Security

| Document | Description | Audience |
|----------|-------------|----------|
| [ANSIBLE-VAULT-GUIDE.md](guides/ANSIBLE-VAULT-GUIDE.md) | Managing secrets with Ansible Vault | DevOps, Security |

### 📊 Project Management

| Document | Description | Audience |
|----------|-------------|----------|
| [CHANGELOG.md](CHANGELOG.md) | Complete project changelog | All Users |
| [CHANGELOG-GENERATED-DIR.md](CHANGELOG-GENERATED-DIR.md) | Generated directory structure changelog | Developers |

---

## 🗂️ Documentation Conventions

### File Naming

- `UPPERCASE-KEBAB-CASE.md` - Main documentation files
- `lowercase-kebab-case.md` - Supporting files (if needed)

### Status Labels

- 🆕 **NEW** - Recently added or updated
- ✅ **STABLE** - Tested and production-ready
- 🔄 **UPDATED** - Recently revised
- ⚠️ **DEPRECATED** - Superseded by newer version (in archive/)
- 📦 **ARCHIVED** - Historical reference only

### Document Structure

All documents follow this structure:
1. **Overview** - What is this?
2. **Prerequisites** - What do you need?
3. **Step-by-step Guide** - How to use it?
4. **Troubleshooting** - Common issues
5. **References** - External links

---

## 🆕 Recent Updates (2025-10-22)

### ✨ NEW: Automated Bridge Creation

- **BRIDGES.md** updated with Terraform automation using bpg/proxmox v0.85+
- Bridges now created automatically from `topology.yaml`
- Manual methods kept as fallback

### 🔄 Documentation Reorganization

- Created structured docs/ directory with subdirectories
- Moved outdated docs to `archive/`
- Improved navigation with this README

---

## 📖 Key Concepts

### Infrastructure-as-Data

Everything is defined in `topology.yaml` (single source of truth):
```
topology.yaml (36 lines)  →  Generated configs
    ↓
topology/ (13 modules)
    ↓
scripts/generate-*.py
    ↓
generated/
├── terraform/
├── ansible/inventory/
└── docs/
```

### Generated vs. Manual Files

**Generated** (DO NOT EDIT):
- `generated/terraform/*.tf`
- `generated/ansible/inventory/`
- `generated/docs/`

**Manual** (EDIT THESE):
- `topology.yaml` and `topology/*.yaml`
- `ansible/playbooks/*.yml`
- `ansible/roles/*/tasks/*.yml`

### Modular Topology

Since v2.2.0, topology is split into 13 modules:
- **physical.yaml** - Hardware, devices
- **logical.yaml** - Networks, bridges, DNS
- **compute.yaml** - VMs and LXC
- **storage.yaml** - Storage pools
- ... (see [TOPOLOGY-MODULAR.md](architecture/TOPOLOGY-MODULAR.md))

---

## 🛠️ How to Use This Documentation

### 1. Find What You Need

Use the **Documentation by Topic** table above, or:

```bash
# Search all documentation
grep -r "keyword" docs/

# List all guides
ls docs/guides/

# List architecture docs
ls docs/architecture/
```

### 2. Read the Guide

Each guide includes:
- **Prerequisites** - What you need before starting
- **Step-by-step instructions** - How to complete the task
- **Examples** - Real-world usage
- **Troubleshooting** - Common issues and solutions

### 3. Update Documentation

If you find errors or want to improve docs:

1. Edit the source file in `docs/`
2. Follow existing conventions
3. Keep it concise and practical
4. Add examples where helpful

---

## 📦 Archive

The [archive/](archive/) directory contains historical documents that have been superseded:

| Document | Replaced By | Date Archived |
|----------|-------------|---------------|
| TOPOLOGY-ANALYSIS.md | TOPOLOGY-MODULAR.md | 2025-10-22 |
| TOPOLOGY-V2-ANALYSIS.md | CHANGELOG.md v2.1.0 | 2025-10-22 |
| TOPOLOGY-IMPROVEMENTS-SUMMARY.md | CHANGELOG.md v2.1.0 | 2025-10-22 |

These files are kept for historical reference and understanding the evolution of the project.

---

## 🔗 External References

### Terraform

- [bpg/proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)

### Ansible

- [Ansible Documentation](https://docs.ansible.com/)
- [Ansible Vault Guide (Official)](https://docs.ansible.com/ansible/latest/user_guide/vault.html)

### Proxmox

- [Proxmox VE Documentation](https://pve.proxmox.com/wiki/Main_Page)
- [Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)

### Infrastructure-as-Code

- [Infrastructure as Code (O'Reilly)](https://www.oreilly.com/library/view/infrastructure-as-code/9781098114664/)
- [GitOps Principles](https://www.gitops.tech/)

---

## 📞 Support

For questions or issues:

1. Check the [Troubleshooting](#) sections in guides
2. Review [CHANGELOG.md](CHANGELOG.md) for recent changes
3. Search existing documentation with `grep -r "keyword" docs/`

---

## 📄 License

This documentation is part of the home-lab project.

---

**Last Updated**: 2025-10-22
**Documentation Version**: 2.2.0
**Topology Version**: 2.2.0
**Generated Structure**: v1.0.0
