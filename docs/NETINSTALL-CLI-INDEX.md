# NetInstall CLI Provisioning - Documentation Index

## 📖 Documentation Map

### Quick Start (Start Here!)
- **[NETINSTALL-CLI-VISUAL-GUIDE.md](NETINSTALL-CLI-VISUAL-GUIDE.md)** ⭐ START HERE
  - Visual flowcharts and diagrams
  - 30-second TL;DR
  - Setup method comparison charts
  - Complete workflow visualization

### Quick Reference
- **[NETINSTALL-CLI-QUICK-REFERENCE.md](NETINSTALL-CLI-QUICK-REFERENCE.md)**
  - One-liner commands
  - Cheatsheet format
  - Troubleshooting quick fixes
  - Environment variables

### Detailed Guides

#### 1. Setup Options Explained
- **[NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md)**
  - 4 different installation methods explained
  - Platform-specific instructions (Linux/macOS/Windows)
  - Pros and cons of each approach
  - Complete Docker setup guide
  - Troubleshooting for each method

#### 2. Comprehensive Provisioning Guide
- **[NETINSTALL-CLI-PROVISIONING.md](NETINSTALL-CLI-PROVISIONING.md)**
  - 300+ lines of detailed documentation
  - All installation methods with examples
  - Integration with your infrastructure
  - Advanced environment configuration
  - Extended troubleshooting section

#### 3. Bootstrap Directory Overview
- **[../local/bootstrap/README.md](../local/bootstrap/README.md)**
  - What's in the bootstrap directory
  - Docker instructions
  - Quick workflow
  - File structure

#### 4. Implementation Summary
- **[../NETINSTALL-CLI-IMPLEMENTATION-SUMMARY.md](../NETINSTALL-CLI-IMPLEMENTATION-SUMMARY.md)**
  - What was built and why
  - Feature overview
  - File locations
  - Next steps

---

## 🎯 Pick Your Path

### "Just tell me what to do" (TL;DR)
1. Read: [NETINSTALL-CLI-VISUAL-GUIDE.md](NETINSTALL-CLI-VISUAL-GUIDE.md) (2 min)
2. Run: `cd deploy && make setup-control-node` (5 min)
3. Done! ✓

### "I want to understand my options" (Medium)
1. Read: [NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md) (10 min)
2. Choose your method
3. Run the appropriate command
4. Done! ✓

### "I need complete details" (Deep Dive)
1. Start: [NETINSTALL-CLI-QUICK-REFERENCE.md](NETINSTALL-CLI-QUICK-REFERENCE.md) (5 min)
2. Read: [NETINSTALL-CLI-PROVISIONING.md](NETINSTALL-CLI-PROVISIONING.md) (20 min)
3. Reference: [NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md) (10 min)
4. Execute and troubleshoot as needed

---

## 📚 By Use Case

### I want the FASTEST setup
→ [NETINSTALL-CLI-QUICK-REFERENCE.md](NETINSTALL-CLI-QUICK-REFERENCE.md)
→ Run: `make setup-control-node`

### I want to use Docker
→ [NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md) (Docker section)
→ Or read [../local/bootstrap/README.md](../local/bootstrap/README.md)

### I want Ansible integration
→ [NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md) (Ansible section)
→ Run: `make setup-control-node-ansible`

### I'm having problems
→ [NETINSTALL-CLI-PROVISIONING.md](NETINSTALL-CLI-PROVISIONING.md) (Troubleshooting section)
→ Or [NETINSTALL-CLI-QUICK-REFERENCE.md](NETINSTALL-CLI-QUICK-REFERENCE.md) (Troubleshooting)

### I want to understand the architecture
→ [../NETINSTALL-CLI-IMPLEMENTATION-SUMMARY.md](../NETINSTALL-CLI-IMPLEMENTATION-SUMMARY.md)

### I'm new to this project
→ [NETINSTALL-CLI-VISUAL-GUIDE.md](NETINSTALL-CLI-VISUAL-GUIDE.md) (workflow diagrams)
→ Then [NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md)

---

## 🚀 Installation Methods at a Glance

| Method | Command | Time | Best For |
|--------|---------|------|----------|
| **Bash** | `make setup-control-node` | 3-5 min | Everyone (RECOMMENDED) |
| **Ansible** | `make setup-control-node-ansible` | 5-10 min | Automation |
| **Docker** | `docker-compose build` | 10-15 min | Isolation |
| **Manual** | `wget ...` | Variable | Troubleshooting |

---

## 📝 File Structure

```
docs/
├── NETINSTALL-CLI-INDEX.md                    ← You are here
├── NETINSTALL-CLI-VISUAL-GUIDE.md             ← START HERE
├── NETINSTALL-CLI-QUICK-REFERENCE.md
├── NETINSTALL-CLI-PROVISIONING.md
└── NETINSTALL-CLI-SETUP-OPTIONS.md

local/bootstrap/
├── README.md                                   ← Bootstrap overview
├── Dockerfile.control-node                     ← Docker image
└── docker-compose.yml                          ← Docker Compose config

deploy/
├── Makefile                                    (modified)
├── phases/
│   └── 00-bootstrap-setup-control-node.sh      ← Setup script
└── playbooks/
    └── provision-control-node.yml              ← Ansible playbook

NETINSTALL-CLI-IMPLEMENTATION-SUMMARY.md        ← What was created
```

---

## 🎯 Quick Commands Reference

```bash
# 1. Setup (choose one)
cd deploy
make setup-control-node                    # Bash (fastest)
make setup-control-node-ansible            # Ansible

# 2. Verify
make bootstrap-preflight RESTORE_PATH=minimal

# 3. Bootstrap MikroTik
make bootstrap-netinstall \
  RESTORE_PATH=minimal \
  MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"

# 4. Verify success
make bootstrap-postcheck \
  MIKROTIK_MGMT_IP="192.168.88.1" \
  MIKROTIK_TERRAFORM_PASSWORD_FILE="local/terraform/mikrotik/password.txt"
make bootstrap-terraform-check

# 5. Continue deployment
make deploy-all
```

---

## 🔗 Cross References

- **Main Project README:** `../README.md`
- **Makefile Help:** `make help` (in deploy/)
- **Bootstrap Info:** `make bootstrap-info` (in deploy/)
- **Architecture Decision:** `../adr/0057-*` (if it exists)

---

## ✅ What's Included

### New Files Created
- ✅ Bash setup script with multi-platform support
- ✅ Ansible playbook for automated provisioning
- ✅ Docker container image (Dockerfile)
- ✅ Docker Compose configuration
- ✅ 4 comprehensive documentation files
- ✅ Updated Makefile with new targets

### Coverage
- ✅ Linux (Debian, Ubuntu, RedHat, CentOS, Fedora)
- ✅ macOS
- ✅ Windows (WSL2 and Docker)
- ✅ Multi-language (English, with notes for Russian context)

### Modes
- ✅ Automated bash script
- ✅ Ansible playbook (idempotent)
- ✅ Docker containerized
- ✅ Manual fallback

---

## 💡 Tips

### For Fastest Setup
```bash
cd deploy && make setup-control-node
```
Takes 3-5 minutes total. Auto-detects your OS and installs everything.

### For Docker Users
```bash
cd local/bootstrap
docker-compose build
docker-compose run --rm control-node
```
Takes 10-15 minutes. Creates isolated environment.

### For CI/CD Pipelines
```bash
cd deploy
make setup-control-node-ansible  # or use playbook directly
```
Perfect for automation systems. Idempotent and repeatable.

### For Troubleshooting
```bash
make bootstrap-preflight RESTORE_PATH=minimal
```
Shows detailed diagnostics of what's installed and what's missing.

---

## 🆘 Need Help?

### Quick Issues
- Command not found? → [NETINSTALL-CLI-QUICK-REFERENCE.md](NETINSTALL-CLI-QUICK-REFERENCE.md) (Troubleshooting)
- Permission denied? → [NETINSTALL-CLI-PROVISIONING.md](NETINSTALL-CLI-PROVISIONING.md) (Troubleshooting)
- Docker errors? → [NETINSTALL-CLI-SETUP-OPTIONS.md](NETINSTALL-CLI-SETUP-OPTIONS.md) (Troubleshooting)

### Complex Issues
→ Run: `make bootstrap-preflight RESTORE_PATH=minimal`
→ Check detailed output for specific errors
→ Refer to relevant troubleshooting section in documentation

---

## 🎉 You're Ready!

Start with any of these:

**Fastest:** `cd deploy && make setup-control-node`

**Visual:** Read [NETINSTALL-CLI-VISUAL-GUIDE.md](NETINSTALL-CLI-VISUAL-GUIDE.md) first

**Docker:** `docker-compose -f local/bootstrap/docker-compose.yml build`

**Manual:** Follow [NETINSTALL-CLI-PROVISIONING.md](NETINSTALL-CLI-PROVISIONING.md)

---

**Created:** March 4, 2026
**Project:** Home Lab Infrastructure
**Topic:** Automatic NetInstall CLI Provisioning
