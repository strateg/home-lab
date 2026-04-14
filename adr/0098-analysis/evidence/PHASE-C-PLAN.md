# Phase C Plan — Production Environment Migration

**Date**: 2026-04-14
**Status**: Planning (waiting for CI green)
**Previous**: Phase B Complete (dev environment migrated)

---

## Context

Phase B completed:
- ✅ pyproject.toml requires-python = ">=3.14"
- ✅ All 6 CI workflows migrated to Python 3.14
- ✅ framework.lock.yaml regenerated
- ✅ Local smoke test passed (0 errors)
- ⏳ CI verification in progress

Phase C focuses on **production infrastructure migration**:
- Proxmox host
- Orange Pi 5
- LXC containers
- Operator workstation environments

---

## Phase C Entry Criteria

- [x] Phase B complete (dev environment)
- [ ] CI green on all 6 workflows (Python 3.14)
- [ ] No Python 3.14-specific regressions identified
- [ ] ADR 0098 status updated to "Phase C"

---

## Scope

### C1. Developer Environment Transition (LOW PRIORITY)

**Current State:**
- Primary dev: WSL2 with .venv-3.14 (Python 3.14.4 via pyenv)
- CI: All workflows on Python 3.14
- Baseline: .venv still on Python 3.13.7

**Actions:**

1. **Optional**: Create `.python-version` for pyenv auto-switch
   ```bash
   echo "3.14.4" > .python-version
   pyenv local 3.14.4
   ```

2. **Migrate baseline venv** (when ready for exclusive 3.14 use):
   ```bash
   # Backup current venv (optional)
   mv .venv .venv-3.13-backup

   # Create new baseline on 3.14
   ~/.pyenv/versions/3.14.4/bin/python -m venv .venv
   .venv/bin/pip install --upgrade pip
   .venv/bin/pip install -e ".[dev]"
   .venv/bin/pip install mcp  # Don't forget MCP dependency
   ```

3. **Verify new venv**:
   ```bash
   .venv/bin/python --version  # Should show 3.14.4
   .venv/bin/pytest tests/ -q  # Should pass like .venv-3.14
   ```

**Timeline**: Can be done anytime after CI green

---

### C2. Production Platform Assessment (CRITICAL)

**Target Platforms:**

| Platform | Current Python | Target | Method | Priority |
|----------|----------------|--------|--------|----------|
| Proxmox host | 3.11 (Debian 12) | 3.14 | TBD | HIGH |
| Orange Pi 5 | 3.11 (Ubuntu 22.04) | 3.14 | TBD | HIGH |
| LXC containers | Inherited | 3.14 | From host | MEDIUM |

**Assessment Tasks:**

#### C2.1: Check Python 3.14 Availability

```bash
# Proxmox host (x86_64, Debian 12)
ssh proxmox "apt-cache search python3.14"
# Expected: Check if deadsnakes PPA or Debian packages available

# Orange Pi 5 (ARM64, Ubuntu 22.04)
ssh orangepi "apt-cache search python3.14"
# Expected: Check package availability for ARM64

# Fallback: pyenv support
ssh proxmox "uname -m && which gcc"  # Check if can build from source
ssh orangepi "uname -m && which gcc"
```

**Output**: Platform compatibility matrix
- **Method A**: System package (apt) — preferred
- **Method B**: pyenv build — fallback
- **Method C**: Docker/container isolation — last resort

#### C2.2: Dependency Verification on Target Arch

**Test on ARM64** (Orange Pi 5 is critical):
```bash
# On Orange Pi 5
python3.14 -m pip install --dry-run pyyaml jinja2 jsonschema paramiko pytest

# Check C-extensions availability
python3.14 -m pip install --dry-run cryptography  # Check ARM64 wheels
```

**Known Risks:**
- ARM64 wheel availability for some packages
- C-extension compilation on Orange Pi

---

### C3. Installation Strategy (CRITICAL)

**Decision Matrix:**

| Platform | Method | Pros | Cons | Decision |
|----------|--------|------|------|----------|
| Proxmox | apt (deadsnakes) | Easy, system-wide | May lag behind releases | **Primary** |
| Proxmox | pyenv | Latest version | Build time, user-space | Fallback |
| Orange Pi 5 | apt (deadsnakes) | Easy | ARM64 support unclear | **Primary** |
| Orange Pi 5 | pyenv | Consistent with dev | Build time ~30-60min | Fallback |
| LXC | From host | Inherited, simple | Limited flexibility | **Primary** |

**Installation Scripts:**

Reuse existing: `scripts/setup/install-python-3.14.sh`

```bash
# Proxmox host
ssh proxmox "bash -s" < scripts/setup/install-python-3.14.sh -- --method=apt

# Orange Pi 5
ssh orangepi "bash -s" < scripts/setup/install-python-3.14.sh -- --method=apt

# Fallback to pyenv if apt fails
ssh <host> "bash -s" < scripts/setup/install-python-3.14.sh -- --method=pyenv
```

---

### C4. Rollout Sequence (PHASED)

**Conservative Approach** (minimize production impact):

#### Stage 1: Test LXC Container (Rehearsal)

1. Create test LXC container on Proxmox
2. Install Python 3.14
3. Run full topology compile + validation
4. Verify all generators work
5. Check bootstrap packages build correctly

**Duration**: 1 day
**Rollback**: Delete test container

---

#### Stage 2: Proxmox Host Migration

1. **Pre-flight**:
   ```bash
   ssh proxmox "python3 --version"  # Document baseline
   ssh proxmox "which python3.11 python3"  # Check current setup
   ```

2. **Install Python 3.14**:
   ```bash
   ssh proxmox "sudo add-apt-repository ppa:deadsnakes/ppa"
   ssh proxmox "sudo apt install python3.14 python3.14-venv python3.14-dev"
   ```

3. **Create venv for topology-tools**:
   ```bash
   ssh proxmox "python3.14 -m venv ~/topology-tools-venv"
   ssh proxmox "~/topology-tools-venv/bin/pip install -e /path/to/home-lab[dev]"
   ```

4. **Verify**:
   ```bash
   ssh proxmox "~/topology-tools-venv/bin/python --version"
   ssh proxmox "cd /path/to/home-lab && ~/topology-tools-venv/bin/python topology-tools/compile-topology.py --help"
   ```

**Rollback**: Keep Python 3.11 installed, switch venv back

**Duration**: 2-3 hours
**Risk**: LOW (3.11 remains available)

---

#### Stage 3: Orange Pi 5 Migration

**Same process as Proxmox**, but:
- Check ARM64 package availability first
- May need pyenv if apt unavailable
- Test Docker services compatibility

**Duration**: 2-3 hours
**Risk**: MEDIUM (C-extensions on ARM64)

---

#### Stage 4: LXC Container Templates

**Approach**: Update container templates to use Python 3.14

1. Modify Terraform LXC provisioning to install 3.14
2. Update Ansible bootstrap playbooks
3. Rebuild container templates

**Timeline**: After Stage 2/3 success

---

## Phase C Exit Criteria

- [ ] ✅ Python 3.14 installed on Proxmox host
- [ ] ✅ Python 3.14 installed on Orange Pi 5
- [ ] ✅ Test LXC container validated
- [ ] ✅ All production workflows tested on 3.14
- [ ] ✅ Rollback procedures documented and tested
- [ ] ✅ No production services impacted

---

## Rollback Strategy

### Dev Environment Rollback

```bash
# Restore Python 3.13 venv
mv .venv .venv-3.14-broken
mv .venv-3.13-backup .venv

# Revert pyproject.toml
git checkout HEAD~1 -- pyproject.toml

# Regenerate lock
.venv/bin/python topology-tools/generate-framework-lock.py --force
```

### Production Rollback

**Proxmox/Orange Pi:**
- Python 3.11/3.13 remains installed (not removed)
- Switch venv path back to old version
- No service restart needed (venv-based isolation)

**LXC Containers:**
- Rebuild from previous template
- Or: Install older Python version in container

**Rollback SLA**: <1 hour for any single platform

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ARM64 wheel unavailable | Medium | High | Test on Orange Pi first, pyenv fallback |
| deadsnakes PPA missing Debian 12 | Low | Medium | Use pyenv as fallback |
| C-extension build failure | Low | High | Pre-test all deps before migration |
| Production service downtime | Very Low | Critical | Phased rollout, keep old Python |
| Developer productivity loss | Low | Medium | Clear migration guide, support channel |

---

## Communication Plan

**Before Phase C Starts:**

```markdown
Subject: Python 3.14 Migration - Phase C (Production Platforms)

Timeline: <start-date> to <end-date>

**What's happening:**
- Python 3.14 will be installed on Proxmox and Orange Pi 5
- All production topology compilation will use Python 3.14
- Python 3.13/3.11 will remain available as fallback

**Impact:**
- No expected downtime
- Operator workflows unchanged (venv-based)
- LXC containers unchanged (migration in Phase D)

**Action Required:**
- None for end users
- Operators: Review migration plan at adr/0098-analysis/evidence/PHASE-C-PLAN.md

**Rollback:**
- Available within 1 hour if issues detected
- Old Python versions remain installed

**Support:** <contact>
```

---

## Success Metrics

**Phase C Complete When:**

1. ✅ Proxmox can compile topology on Python 3.14
2. ✅ Orange Pi 5 can run deploy workflows on Python 3.14
3. ✅ Zero production incidents during migration
4. ✅ All operators confirmed environments working
5. ✅ Rollback procedure tested (at least on test container)

**Performance Baseline:**

| Metric | Before (3.13) | After (3.14) | Delta | Status |
|--------|---------------|--------------|-------|--------|
| Compile time | X.Xs | Y.Ys | TBD | PASS if ±10% |
| Test suite time | X.Xs | Y.Ys | TBD | PASS if ±10% |
| Memory usage | XMB | YMB | TBD | PASS if ±20% |

---

## Timeline

| Stage | Duration | Dependencies |
|-------|----------|--------------|
| C1: Dev venv migration | 1 hour | CI green |
| C2: Platform assessment | 4-6 hours | SSH access |
| C3: Installation scripts test | 2 hours | C2 complete |
| C4.1: Test LXC | 1 day | C3 complete |
| C4.2: Proxmox migration | 3 hours | C4.1 success |
| C4.3: Orange Pi migration | 3 hours | C4.2 success |
| C4.4: LXC templates | 1-2 days | C4.3 success |

**Total Estimated**: 3-5 days (phased, with verification gates)

---

## Next Phase (Phase D)

After Phase C:
- **Phase D**: Full integrated validation
  - End-to-end deploy workflow
  - Live bootstrap on new containers
  - Service chain validation
- **Phase E**: Decommission Python 3.13 support

---

**Document Status**: Draft (waiting for CI green to proceed)
**Owner**: Infrastructure team
**Approver**: TBD
