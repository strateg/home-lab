# Phase A Baseline — Environment Assessment

**Date**: 2026-04-13
**Status**: IN PROGRESS

---

## Current Environment

### System Information

| Property | Value |
|----------|-------|
| OS | Ubuntu 25.04 |
| Architecture | x86_64 (WSL2) |
| Current Python | 3.13.3 |
| Virtual env | `.venv/` (Python 3.13) |
| Package manager | apt |

### Python Configuration

```
pyproject.toml:
  requires-python = ">=3.13,<4"
  python_version = "3.13"

.python-version: Not present
```

---

## Python 3.14 Availability

### Official Release

| Source | Version | Status |
|--------|---------|--------|
| python.org/ftp | 3.14.4 | **Available** |

### Local System

| Method | Status | Notes |
|--------|--------|-------|
| System apt | ⬜ Not checked | May require deadsnakes PPA |
| pyenv | ⬜ Not installed | Can build from source |
| Direct build | ⬜ Available | Requires build-essential |

---

## Target Platforms (from ADR 0098)

| Platform | Architecture | Python 3.14 Status | Method |
|----------|--------------|-------------------|--------|
| Dev workstation (WSL2) | x86_64 | ⬜ Pending | apt/pyenv/build |
| Proxmox host | x86_64 | ⬜ Pending | apt (deadsnakes) |
| Orange Pi 5 | ARM64 | ⬜ Pending | apt (deadsnakes) |
| LXC containers | Mixed | ⬜ Pending | Inherited from host |

---

## Phase A Entry Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Python 3.14 officially released | ✅ PASS | 3.14.4 on python.org |
| ADR 0098 status = Accepted | ⬜ Pending | Currently "Proposed" |

---

## Next Steps

1. [x] Pre-installation dependency analysis (EV-A1-preinstall)
2. [ ] Install Python 3.14 on dev workstation
3. [ ] Create test virtual environment (.venv-3.14)
4. [ ] Live verification with verify-deps-3.14.sh
5. [ ] Run test suite on 3.14 (A4)

---

## Evidence Log

| ID | Date | Description | Result |
|----|------|-------------|--------|
| EV-000 | 2026-04-13 | Baseline assessment | Documented |
| EV-A1-preinstall | 2026-04-14 | Pre-installation dependency analysis via PyPI | **PASS** (12/12) |

---

**Current**: Pre-installation analysis complete. CI matrix updated. Ready for Python 3.14 installation.

**Blocked**: Installation requires sudo access.

**Next**: Run manually with sudo:
```bash
# Option 1: deadsnakes PPA (recommended)
./scripts/setup/install-python-3.14.sh --method=apt

# Option 2: pyenv (builds from source, ~15 min)
./scripts/setup/install-python-3.14.sh --method=pyenv

# Option 3: manual steps
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14 python3.14-venv python3.14-dev
```

After installation:
```bash
python3.14 -m venv .venv-3.14
./scripts/setup/verify-deps-3.14.sh
```
