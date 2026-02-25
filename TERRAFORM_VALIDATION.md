# Terraform Generator Validation Guide

## Purpose

Validate that refactored Terraform generators (Phase 3) produce **identical** output to the original monolithic versions.

## Prerequisites

1. Baseline Terraform configs already generated:
   - `generated/terraform/proxmox/`
   - `generated/terraform/mikrotik/`

2. Working topology file: `topology.yaml`

3. Python environment with all dependencies

---

## Quick Validation

### Automatic Validation Script

Run the validation script:

```cmd
python validate_terraform_generators.py
```

**Expected output:**
```
Terraform Generator Validation
======================================================================
Topology: c:\Users\Dmitri\PycharmProjects\home-lab\topology.yaml

======================================================================
Validating PROXMOX generator
======================================================================

Generating to: generated\validation\proxmox

Comparing 7 Terraform files:
  ✅ versions.tf - IDENTICAL
  ✅ provider.tf - IDENTICAL
  ✅ bridges.tf - IDENTICAL
  ✅ vms.tf - IDENTICAL
  ✅ lxc.tf - IDENTICAL
  ✅ variables.tf - IDENTICAL
  ✅ outputs.tf - IDENTICAL

======================================================================
Validating MIKROTIK generator
======================================================================

Generating to: generated\validation\mikrotik

Comparing 11 Terraform files:
  ✅ provider.tf - IDENTICAL
  ✅ variables.tf - IDENTICAL
  ✅ interfaces.tf - IDENTICAL
  ✅ addresses.tf - IDENTICAL
  ✅ dhcp.tf - IDENTICAL
  ✅ dns.tf - IDENTICAL
  ✅ firewall.tf - IDENTICAL
  ✅ qos.tf - IDENTICAL
  ✅ vpn.tf - IDENTICAL
  ✅ containers.tf - IDENTICAL
  ✅ outputs.tf - IDENTICAL

======================================================================
Validation Summary
======================================================================
Proxmox:  ✅ PASS
MikroTik: ✅ PASS

✅ All generators produce identical output!
   Phase 3 refactoring is backward-compatible.
```

---

## Manual Validation

If you don't have baseline configs, generate them first:

### 1. Generate Baseline (Pre-Phase 3)

**Checkout previous commit:**
```cmd
git stash
git checkout HEAD~1
```

**Generate baselines:**
```cmd
python -m topology-tools.scripts.generators.terraform.proxmox.cli ^
  --topology topology.yaml ^
  --output generated\terraform\proxmox

python -m topology-tools.scripts.generators.terraform.mikrotik.cli ^
  --topology topology.yaml ^
  --output generated\terraform\mikrotik
```

**Return to current commit:**
```cmd
git checkout -
git stash pop
```

### 2. Generate Test Output (Post-Phase 3)

```cmd
python -m topology-tools.scripts.generators.terraform.proxmox.cli ^
  --topology topology.yaml ^
  --output generated\validation\proxmox

python -m topology-tools.scripts.generators.terraform.mikrotik.cli ^
  --topology topology.yaml ^
  --output generated\validation\mikrotik
```

### 3. Compare Manually

**Using diff tools:**
```cmd
fc generated\terraform\proxmox\*.tf generated\validation\proxmox\*.tf
fc generated\terraform\mikrotik\*.tf generated\validation\mikrotik\*.tf
```

**Or use a GUI diff tool:**
- WinMerge
- Beyond Compare
- VS Code diff

---

## Expected Differences (Acceptable)

The following differences are **acceptable** and don't indicate bugs:

### 1. Whitespace/Formatting
- Trailing whitespace
- Blank lines
- Indentation (if terraform fmt was run)

### 2. Comment Timestamps
- Generation timestamps in file headers
- Version comments

### 3. Order Changes (if deterministic)
- Resource ordering (if sorted by ID)
- Variable ordering (if alphabetical)

---

## Unacceptable Differences

The following indicate **bugs** that must be fixed:

### 1. Missing Resources
- Any Terraform resource present in baseline but missing in test

### 2. Changed Logic
- Different resource attributes
- Different variable values
- Different module references

### 3. Syntax Errors
- Invalid Terraform syntax
- Missing required attributes
- Type mismatches

---

## Troubleshooting

### Validation Script Fails

**Error: Topology file not found**
```
Solution: Run from repository root where topology.yaml exists
```

**Error: Generator failed with code 1**
```
Solution: Check generator logs for errors
         Verify all dependencies installed
         Check topology.yaml is valid
```

**Error: Baseline file missing**
```
Solution: Generate baseline first (see Manual Validation section)
```

### Differences Found

**Step 1:** Review the diff output
```cmd
python validate_terraform_generators.py > validation_report.txt
```

**Step 2:** Categorize differences
- Acceptable? → Document and proceed
- Unacceptable? → Fix the bug

**Step 3:** Fix bugs in resolvers/base
- Check `terraform/base.py`
- Check `terraform/resolvers.py`
- Check generator implementations

**Step 4:** Re-run validation

---

## Phase 3 Sign-off Checklist

- [ ] Validation script runs without errors
- [ ] All Proxmox files identical or acceptable
- [ ] All MikroTik files identical or acceptable
- [ ] Manual spot-check of critical resources
- [ ] Terraform plan succeeds on both versions
- [ ] Documentation updated
- [ ] Tests passing

**When all checks pass:** Phase 3 is ready to commit! ✅

---

## Next Steps After Validation

1. **Commit Phase 3:**
   ```cmd
   git add -A
   git commit -F COMMIT_MESSAGE_PHASE3.md
   ```

2. **Clean up validation outputs:**
   ```cmd
   rmdir /s /q generated\validation
   ```

3. **Proceed to Phase 4** or next refactoring task

---

## Questions?

- Review `adr/0046-generators-architecture-refactoring.md`
- Check `docs/DEVELOPERS_GUIDE_GENERATORS.md`
- Open an issue if you find bugs
