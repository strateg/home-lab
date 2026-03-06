# ADR 0057 Implementation Review

**Date:** 2026-03-06
**Reviewer:** Claude Code
**Branch:** `adr/netinstall-provisioning-exploration`
**Commit:** `044b3d4`

---

## Summary

**ADR Status:** Accepted
**Implementation:** Phase 1-3 complete, Phase 4-5 partial, Phase 6 pending

| Component | Status | File |
|-----------|--------|------|
| ADR document | Done | `adr/0057-*.md` (2 files) |
| Minimal template | Integrated | `init-terraform-minimal.rsc.j2` |
| Generator | Updated | `generator.py:212` |
| Preflight script | Done | `00-bootstrap-preflight.sh` |
| Netinstall playbook | Done | `bootstrap-netinstall.yml` |
| Postcheck script | Done | `00-bootstrap-postcheck.sh` |
| Makefile targets | Done | `bootstrap-*` |
| Documentation | Synced | MIKROTIK-TERRAFORM.md, 00-bootstrap.sh |
| E2E hardware test | Not done | Pending |

---

## Strengths

### 1. Complete Netinstall Workflow

```
make bootstrap-preflight → make bootstrap-netinstall → make bootstrap-postcheck → make bootstrap-terraform-check
```

All four stages implemented with hard gates.

### 2. Quality Preflight with SHA256 Verification

```bash
# From 00-bootstrap-preflight.sh:40-83
if [ -n "$ROUTEROS_PACKAGE_SHA256" ]; then
    computed_sha="$(sha256sum "$ROUTEROS_PACKAGE" | ...)"
    if [ "$computed_sha" != "$expected_sha" ]; then
        fail "RouterOS package checksum mismatch"
    fi
fi
```

### 3. Password-file Support in Postcheck

```bash
# 00-bootstrap-postcheck.sh:28-34
if [ -n "$TERRAFORM_PASSWORD_FILE" ] && [ -f "$TERRAFORM_PASSWORD_FILE" ]; then
    TERRAFORM_PASSWORD="$(head -n1 "$TERRAFORM_PASSWORD_FILE" | tr -d '\r\n')"
fi
```

Secrets not passed via command line.

### 4. Three Restore Paths with Explicit Opt-in

- `minimal` (default) — handover only
- `backup` — compatibility, requires `ALLOW_NON_MINIMAL_RESTORE=true`
- `rsc` — compatibility, requires `ALLOW_NON_MINIMAL_RESTORE=true`

### 5. Generator Correctly Uses Minimal Template

```python
# generator.py:211-214
template_minimal = self.env.get_template("init-terraform-minimal.rsc.j2")
output_file = self.output_dir / "init-terraform.rsc"
output_file.write_text(template_minimal.render(**context))
```

### 6. Minimal Template Adds Management IP

```routeros
# init-terraform-minimal.rsc.j2:17-29
:if ([:len [/ip address find where interface=$mgmtIf and address="{{ router_address }}"]] = 0) do={
    /ip address add address={{ router_address }} interface=$mgmtIf
}
```

Script is idempotent.

---

## Issues

### 1. No E2E Hardware Test (Phase 4)

Migration plan requires:
> Phase 4 completes only when a newly bootstrapped router can enter the normal Terraform workflow without undocumented manual patching.

**Status:** Not done. No documented evidence that workflow tested.

**Recommendation:** Add checklist or test report to `adr/0057-migration-plan.md`.

### 2. No Ansible Vault Integration for Secrets

ADR §8 states:
> secret values come from `ansible/group_vars/all/vault.yml`

**Current state:** Generator uses placeholder `CHANGE_THIS_PASSWORD`. Password passed via file or environment variable.

**Recommendation:** Acceptable for current phase. For full integration need playbook that renders template with Vault secrets to `.work/native/`.

### 3. Playbook Does Not Use Vault

```yaml
# bootstrap-netinstall.yml — no vars_files or include_vars for Vault
vars:
  restore_path: "{{ restore_path | default('minimal') }}"
  # ...no terraform_password...
```

Playbook only runs netinstall, does not render script with secrets.

### 4. Old Template Still Exists

`init-terraform.rsc.j2` (116 lines, day-1/2 logic) still in repo. Potential confusion.

**Recommendation:** Delete or archive in Phase 6.

### 5. No Unit Tests for Generator

```bash
# Glob result:
topology-tools/scripts/generators/bootstrap/mikrotik/test*.py → No files found
```

**Recommendation:** Add pytest tests for generator.

---

## Migration Plan Phase Status

| Phase | Name | Status | Comment |
|-------|------|--------|---------|
| 0 | Re-Baseline | Done | Inventory complete |
| 1 | Freeze Contract | Done | Minimal template canonical |
| 2 | Rendering/Secrets | 80% | Password-file yes, Vault no |
| 3 | Netinstall Workflow | Done | preflight + playbook + postcheck |
| 4 | Terraform Handover | Not done | E2E test not documented |
| 5 | Cutover Entry Points | Done | Docs/Makefile updated |
| 6 | Cleanup | Not done | Old template not removed |

---

## Improvement Plan

### Priority 1: E2E Hardware Test (Phase 4)

| Task | Description |
|------|-------------|
| 1.1 | Execute full bootstrap on real MikroTik |
| 1.2 | Run `terraform plan` after bootstrap |
| 1.3 | Document result in `0057-migration-plan.md` |

### Priority 2: Cleanup (Phase 6)

| Task | File |
|------|------|
| 2.1 | Delete/archive `init-terraform.rsc.j2` | templates/bootstrap/mikrotik/ |
| 2.2 | Update ADR status | References section |

### Priority 3: Optional Improvements

| Task | Description |
|------|-------------|
| 3.1 | Add pytest for generator | test_generator.py |
| 3.2 | Ansible Vault render playbook | For `.work/native/` with secrets |

---

## Metrics

| Criterion | Previous | Current |
|-----------|----------|---------|
| ADR status | Proposed | **Accepted** |
| Minimal template integrated | No | **Yes** |
| Netinstall automation | Manual docs | **Makefile + Ansible** |
| Preflight checks | No | **SHA256 + interface check** |
| Postcheck | No | **API auth verification** |
| Password-file support | No | **Yes** |
| E2E test | No | No |
| File cleanup | 21 files | **2 files** |

---

## Conclusion

**Readiness:** 85%

**Blockers:**
1. E2E test on real hardware (required before merge to main)

**Non-blockers:**
- Cleanup old template
- Unit tests
- Vault integration (can defer)

**Recommendation:** Merge to main after successful E2E test with documented result.

---

## Hardware E2E Test Checklist

When performing the E2E test, verify:

- [ ] `make assemble-native` completes without errors
- [ ] `make bootstrap-preflight` passes all checks
- [ ] Router enters Etherboot/Netinstall mode
- [ ] `make bootstrap-netinstall` completes successfully
- [ ] Router boots with new RouterOS
- [ ] `make bootstrap-postcheck` passes (API reachable, auth works)
- [ ] `make bootstrap-terraform-check` passes
- [ ] `terraform plan` shows expected resources
- [ ] `terraform apply` succeeds (optional, constrained first apply)

Record results here after test:

```
Test Date: ____________
RouterOS Version: ____________
Control Node OS: ____________
Result: PASS / FAIL
Notes: ____________
```
