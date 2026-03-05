# ADR 0057 - Action Items Checklist

**Date:** 5 марта 2026 г.
**Priority Order:** CRITICAL → HIGH → MEDIUM → LOW

---

## 🚨 CRITICAL (Must Fix Before Phase 2)

### [ ] CRIT-001: Create Migration Plan Document
**File to create:** `adr/0057-migration-plan.md`

**Content required:**
- [ ] Phase 0: Baseline (manual import still works)
- [ ] Phase 1: Netinstall path available (parallel with manual)
- [ ] Phase 2: Documentation updated (netinstall is primary)
- [ ] Phase 3: Validation period (both paths work)
- [ ] Phase 4: Deprecation warnings (manual path discouraged)
- [ ] Phase 5: Legacy cleanup (manual path removed)
- [ ] Entry/exit criteria for each phase
- [ ] Rollback procedures
- [ ] Compatibility matrix
- [ ] Current phase indicator

**Estimated effort:** 2-4 hours
**Assignee:** Architecture team
**Deadline:** End of Week 1

---

### [ ] CRIT-002: Add Makefile Bootstrap Targets
**File to edit:** `deploy/Makefile`

**Tasks:**
- [ ] Add `bootstrap-preflight` target
  ```makefile
  bootstrap-preflight:
  	@$(SHELL) phases/00-bootstrap-preflight.sh $(RESTORE_PATH)
  ```

- [ ] Add `bootstrap-netinstall` target
  ```makefile
  bootstrap-netinstall:
  	@ansible-playbook playbooks/bootstrap-netinstall.yml \
  	  --extra-vars="restore_path=$(RESTORE_PATH)" \
  	  --extra-vars="target_mac=$(MIKROTIK_BOOTSTRAP_MAC)"
  ```

- [ ] Add `bootstrap-postcheck` target
  ```makefile
  bootstrap-postcheck:
  	@$(SHELL) phases/00-bootstrap-postcheck.sh $(MIKROTIK_MGMT_IP)
  ```

- [ ] Update `.PHONY` declaration

- [ ] Update `bootstrap-info` to reference new targets

- [ ] Add usage examples in help text

**Estimated effort:** 1-2 hours
**Assignee:** DevOps
**Deadline:** End of Week 1

---

## ⚠️ HIGH (Fix Soon)

### [ ] HIGH-001: Fix Bootstrap Template Compliance
**File to edit:** `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2`

**Tasks:**
- [ ] Add Step 2: Management IP configuration
  ```routeros
  /ip address add address={{ mgmt_ip }}/{{ mgmt_cidr_prefix }} interface={{ mgmt_interface }}
  ```

- [ ] Review API method:
  - [ ] Option A: Keep www-ssl (REST API) → Update ADR to reflect decision
  - [ ] Option B: Change to api-ssl → Update template

- [ ] Add Step 5: Firewall rule for management
  ```routeros
  /ip firewall filter add chain=input protocol=tcp dst-port={{ api_port }} \
    src-address={{ mgmt_cidr }} action=accept comment="API access"
  ```

- [ ] Verify Step 6: Disable services correctly
  - [ ] Check if SSH should be conditionally enabled

- [ ] Regenerate outputs: `make generate-bootstrap`

- [ ] Validate generated .rsc contains all 7 steps

**Estimated effort:** 2-3 hours
**Assignee:** Template developer
**Deadline:** End of Week 2

---

### [ ] HIGH-002: Implement Secret Migration Adapter
**File to create:** `topology-tools/lib/secrets.py` (or similar)

**Tasks:**
- [ ] Create `load_bootstrap_password()` function
  ```python
  def load_bootstrap_password():
      # Try SOPS first
      try:
          return load_from_sops("secrets/production/bootstrap/rtr-mikrotik-chateau.sops.yaml")
      except FileNotFoundError:
          pass

      # Fall back to Vault
      return load_from_vault("ansible/group_vars/all/vault.yml")
  ```

- [ ] Integrate into bootstrap rendering pipeline

- [ ] Add logging for which source was used

- [ ] Test both Vault and SOPS sources

- [ ] Document current phase (Vault or SOPS or both)

**Estimated effort:** 3-4 hours
**Assignee:** Security/DevOps
**Deadline:** End of Week 2
**Depends on:** ADR 0058 Phase 1 status

---

### [ ] HIGH-003: Validate Generated Bootstrap Against Spec
**Files:** `generated/bootstrap/rtr-mikrotik-chateau/*.rsc`

**Tasks:**
- [ ] Create validation script/test
- [ ] Parse generated .rsc file
- [ ] Check for required commands:
  - [ ] `/system identity set`
  - [ ] `/ip address add` (management)
  - [ ] `/ip service enable api-ssl` (or www-ssl if documented)
  - [ ] `/user add name=terraform`
  - [ ] `/ip firewall filter add` (API access)
  - [ ] `/ip service disable` (insecure services)
- [ ] Report missing/incorrect commands
- [ ] Add to CI pipeline (optional)

**Estimated effort:** 2-3 hours
**Assignee:** QA/DevOps
**Deadline:** End of Week 2

---

## 📝 MEDIUM (Quality Improvements)

### [ ] MED-001: Add Integration Tests
**Directory:** `tests/integration/bootstrap/` (create if needed)

**Tasks:**
- [ ] Create test suite for preflight script
- [ ] Mock netinstall-cli, packages, interfaces
- [ ] Test pass scenarios
- [ ] Test fail scenarios (missing deps)
- [ ] Add to CI pipeline

**Estimated effort:** 4-6 hours
**Assignee:** QA
**Deadline:** End of Week 3

---

### [ ] MED-002: Complete Playbook Validation
**File:** `deploy/playbooks/bootstrap-netinstall.yml`

**Tasks:**
- [ ] Review existing validation tasks
- [ ] Add missing checks from ADR "Post-Bootstrap Success Criteria":
  - [ ] Device responds on mgmt_ip
  - [ ] API port reachable
  - [ ] SSH NOT responding (unless enabled)
  - [ ] Terraform user can authenticate (curl test)
  - [ ] Firewall rules correct
- [ ] Add detailed logging
- [ ] Add retry logic for device boot

**Estimated effort:** 2-3 hours
**Assignee:** Ansible developer
**Deadline:** End of Week 3

---

### [ ] MED-003: Update Bootstrap Documentation
**File:** `deploy/Makefile` → `bootstrap-info` target

**Tasks:**
- [ ] Update output to show netinstall workflow
- [ ] Document three-path strategy:
  - Path A: minimal
  - Path B: backup restore
  - Path C: safe exported config
- [ ] Show example commands:
  ```bash
  make bootstrap-preflight RESTORE_PATH=minimal
  make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC=...
  make bootstrap-postcheck MIKROTIK_MGMT_IP=...
  ```
- [ ] Reference ADR 0057
- [ ] Add troubleshooting tips

**Estimated effort:** 1-2 hours
**Assignee:** Tech writer/DevOps
**Deadline:** End of Week 3

---

## 🔧 LOW (Nice to Have)

### [ ] LOW-001: Add Deprecation Notice to Legacy Helper
**File:** `topology-tools/scripts/deployers/mikrotik_bootstrap.py`

**Tasks:**
- [ ] Add header comment:
  ```python
  # DEPRECATED: This SSH-first helper is kept for recovery scenarios only.
  # For new installations, use netinstall workflow (see ADR 0057)
  # File: adr/0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md
  ```
- [ ] Add runtime warning when executed
- [ ] Document when to use vs. netinstall

**Estimated effort:** 30 minutes
**Assignee:** Anyone
**Deadline:** End of Week 4

---

## 📋 Verification Checklist (After All Fixes)

### End-to-End Workflow Test
- [ ] `make generate-bootstrap` succeeds
- [ ] `make bootstrap-preflight RESTORE_PATH=minimal` passes all checks
- [ ] `make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC=...` succeeds
- [ ] `make bootstrap-postcheck MIKROTIK_MGMT_IP=...` validates success
- [ ] Terraform can connect and manage router
- [ ] All 7 minimal bootstrap steps present in generated .rsc
- [ ] Migration plan document exists and is complete
- [ ] Documentation updated

### Compliance Check
- [ ] ADR 0057 spec fully implemented
- [ ] No deviations without documentation
- [ ] All CRITICAL and HIGH findings closed
- [ ] Tests pass (if implemented)

---

## 📊 Progress Tracking

| Priority | Total | Done | Remaining | % Complete |
|----------|-------|------|-----------|------------|
| CRITICAL | 2 | 0 | 2 | 0% |
| HIGH | 3 | 0 | 3 | 0% |
| MEDIUM | 3 | 0 | 3 | 0% |
| LOW | 1 | 0 | 1 | 0% |
| **Total** | **9** | **0** | **9** | **0%** |

---

## 🎯 Milestones

### Milestone 1: Ready for Phase 2 (End of Week 1)
- [x] Migration plan created
- [x] Makefile targets added
- [ ] Basic workflow tested

### Milestone 2: Spec Compliant (End of Week 2)
- [ ] Template fixes complete
- [ ] Generated outputs validated
- [ ] Secret adapter implemented

### Milestone 3: Production Ready (End of Week 3)
- [ ] Tests added
- [ ] Documentation complete
- [ ] Validation complete

---

## 📞 Help Needed?

**Questions about:**
- API method (api-ssl vs www-ssl): Ask architecture team
- Secret migration: Ask security team
- Makefile best practices: Ask DevOps lead

**Blockers:**
- Report immediately in project chat/issue tracker

---

**Start Date:** 5 марта 2026 г.
**Target Completion:** End of Week 3 (26 марта 2026 г.)

**Current Status:** ⏳ Not Started - Ready to Begin
