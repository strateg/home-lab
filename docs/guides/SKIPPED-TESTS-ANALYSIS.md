# Skipped Tests Analysis

**Date:** 2026-04-22
**Source:** Implementation Plan A3
**Purpose:** Document intentionally skipped tests and their rationale

---

## Summary

**Total tests:** 1508
**Passed:** 1504
**Skipped:** 4 (0.26%)
**Status:** All skips are intentional and properly documented

---

## Skipped Tests Inventory

| Test | Reason | Status |
|------|--------|--------|
| `test_wsl_runner_run_uses_wsl_command_on_windows` | Windows-only WSL execution path | ✓ Intentional |
| `test_ansible_inventory_lxc_hosts_match_v4_baseline` | v4 baseline missing | ✓ Intentional |
| `test_terraform_mikrotik_file_set_matches_v4_baseline` | v4 baseline missing | ✓ Intentional |
| `test_terraform_proxmox_file_set_matches_v4_baseline` | v4 baseline missing | ✓ Intentional |

---

## 1. WSL Runner Test (Platform-Specific)

**File:** `tests/orchestration/test_runner.py`
**Test:** `test_wsl_runner_run_uses_wsl_command_on_windows`

```python
@pytest.mark.skipif(platform.system() != "Windows",
                   reason="WSL execution path is Windows-only")
def test_wsl_runner_run_uses_wsl_command_on_windows(...)
```

**Rationale:**
- Tests WSL execution backend (ADR 0084)
- Only applicable on Windows with WSL installed
- Current environment: Linux
- **Action:** None required - properly documented platform skip

---

## 2. V4 Parity Tests (Migration Regression Suite)

### 2.1 Ansible Inventory Parity

**File:** `tests/plugin_regression/test_ansible_inventory_parity.py`
**Test:** `test_ansible_inventory_lxc_hosts_match_v4_baseline`

```python
v4_hosts_path = V4_INVENTORY_ROOT / "hosts.yml"
if not v4_hosts_path.exists():
    pytest.skip(f"v4 inventory baseline missing: {v4_hosts_path}")
```

**Expected baseline:** `/home/dmpr/workspaces/projects/home-lab/v4-generated/ansible/inventory/production/hosts.yml`

### 2.2 MikroTik Terraform Parity

**File:** `tests/plugin_regression/test_terraform_mikrotik_parity.py`
**Test:** `test_terraform_mikrotik_file_set_matches_v4_baseline`

```python
if not V4_MIKROTIK.exists():
    pytest.skip(f"v4 mikrotik terraform baseline missing: {V4_MIKROTIK}")
```

**Expected baseline:** `/home/dmpr/workspaces/projects/home-lab/v4-generated/terraform/mikrotik`

### 2.3 Proxmox Terraform Parity

**File:** `tests/plugin_regression/test_terraform_proxmox_parity.py`
**Test:** `test_terraform_proxmox_file_set_matches_v4_baseline`

```python
if not V4_PROXMOX.exists():
    pytest.skip(f"v4 proxmox terraform baseline missing: {V4_PROXMOX}")
```

**Expected baseline:** `/home/dmpr/workspaces/projects/home-lab/v4-generated/terraform/proxmox`

---

## Parity Tests Rationale

These tests are **regression guards** that compare v5 generator output to v4 baseline artifacts. They serve two purposes:

1. **Migration Safety:** Ensure v5 generators produce equivalent artifacts to v4
2. **Parity Tracking:** Detect intentional/unintentional deviations during migration

**Why they skip:**
- Project status: `migration` (ADR 0080)
- v4 baseline artifacts not generated in this environment
- Tests activate when v4 baseline is available (e.g., during cutover validation)

**Migration lifecycle:**
1. **Development phase** (current): Tests skip, v5 development continues
2. **Cutover prep**: Generate v4 baseline from `archive/v4/`
3. **Parity validation**: Tests run and validate equivalence
4. **Post-migration**: Tests may be marked as historical or removed

---

## Recommendations

### Immediate (Phase 1)
- ✅ All skipped tests are intentional and properly documented
- ✅ No action required for current sprint

### Future (Post-ADR0080 Completion)
1. **Generate v4 baseline** when cutover validation is needed
2. **Document parity exceptions** in test files (see existing `test_ansible_inventory_host_vars_intentional_extension`)
3. **Consider archival** after migration complete and parity validated

---

## References

- Implementation Plan: `docs/analysis/IMPLEMENTATION-PLAN-2026-04-22.md`
- ADR 0080: V4→V5 Migration Contract
- ADR 0084: Cross-Platform Deploy Plane
- Migration Lane Guard: `CLAUDE.md` Line 124-129

---

## Metadata

```yaml
analysis_date: 2026-04-22
total_tests: 1508
skipped_tests: 4
skip_rate: 0.26%
intentional_skips: 4
require_fixes: 0

skip_categories:
  platform_specific: 1  # Windows WSL
  migration_regression: 3  # v4 parity guards

action_required: false
```
