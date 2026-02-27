# Tool Version Management: Usage Guide

**Дата:** 26 февраля 2026 г.
**Версия:** 1.0
**Статус:** Ready

---

## Overview

Tool version management in L0 enables:
- ✅ Automatic version validation
- ✅ Breaking change detection
- ✅ Version metadata in generated code
- ✅ Team synchronization
- ✅ CI/CD gating

---

## Files Created

1. **`topology/L0-meta/_index.yaml`** - L0 config with tool versions
2. **`topology-tools/validators/version_validator.py`** - Version validator
3. **`topology-tools/utils/breaking_changes.py`** - Breaking changes detector
4. **`topology-tools/data/breaking-changes.yaml`** - Breaking changes database

---

## Quick Start

### 1. Check Tool Versions

```bash
# Check all tools
$ python topology-tools/validators/version_validator.py

# Check specific tool
$ python topology-tools/validators/version_validator.py --terraform

# Check and report versions
$ python topology-tools/validators/version_validator.py --report-versions
```

### 2. Detect Breaking Changes

```bash
# Check specific tool upgrade
$ python topology-tools/utils/breaking_changes.py \
    --tool terraform \
    --from 1.5.0 \
    --to 1.6.0

# Check all tools between L0 configs
$ python topology-tools/utils/breaking_changes.py --all
```

### 3. Generate with Version Metadata

```bash
# Generated code will include version comments
$ python topology-tools/generate-terraform.py

# Generated terraform/main.tf will have:
# Generated with: Terraform 1.5.2
# terraform-provider-proxmox: 0.45.1
# Generated: 2026-02-26T10:30:00
```

---

## L0 Config Format

### Basic Structure

```yaml
# topology/L0-meta/_index.yaml

tools:
  terraform:
    core: "~> 1.5.0"
    providers:
      proxmox: "~> 0.45.0"

  ansible:
    core: "~> 2.14.0"

  python:
    core: "~> 3.11.0"
```

### Version Specifiers

```yaml
# Flexible (allows patch/minor updates)
core: "~> 1.5.0"      # Allows 1.5.x, not 1.6.0+

# Minimum version
core: ">= 1.5.0"      # Allows 1.5.0 and higher

# Exact version (for production pinning)
core: "1.5.2"         # Must be exactly 1.5.2
```

---

## Version Validator Usage

### Check All Tools

```bash
$ python topology-tools/validators/version_validator.py

[TERRAFORM]
  Core version:
    Installed: 1.5.2
    Required:  ~> 1.5.0
    Status:    ✓ OK

  Providers:
    proxmox:
      Installed: 0.45.1
      Required:  ~> 0.45.0
      Status:    ✓ OK

[ANSIBLE]
  Core version:
    Installed: 2.14.5
    Required:  ~> 2.14.0
    Status:    ✓ OK

[PYTHON]
  Core version:
    Installed: 3.11.2
    Required:  ~> 3.11.0
    Status:    ✓ OK

✓ All tools match L0 requirements!
```

### Check Specific Tool

```bash
$ python topology-tools/validators/version_validator.py --terraform

# Or just Ansible
$ python topology-tools/validators/version_validator.py --ansible

# Or just Python
$ python topology-tools/validators/version_validator.py --python
```

### Exit Codes

- `0` - All checks passed
- `1` - One or more checks failed

Use in scripts:

```bash
if ! python version_validator.py; then
    echo "Tool versions don't match L0 requirements!"
    exit 1
fi
```

---

## Breaking Changes Detector Usage

### Check Single Tool Upgrade

```bash
$ python topology-tools/utils/breaking_changes.py \
    --tool terraform-provider-proxmox \
    --from 0.45.0 \
    --to 0.46.0

======================================================================
BREAKING CHANGES: terraform-provider-proxmox 0.45.0 → 0.46.0
======================================================================

✗ BREAKING CHANGES DETECTED (1)
Severity: CRITICAL
Risk: HIGH

[CRITICAL] In version 0.46.0:
  - Resource renamed: proxmox_vm_qemu → proxmox_virtual_machine
  - Field renamed: proxmox_virtual_machine.vmid → vm_id
  - Field removed: proxmox_virtual_machine.cores_per_socket

[MIGRATION STRATEGY]
Description: Migrate from proxmox_vm_qemu to proxmox_virtual_machine

Changes to make:
  - terraform code: proxmox_vm_qemu → proxmox_virtual_machine
  - terraform code: vmid → vm_id

Validation steps:
  - Run: terraform validate
  - Run: terraform plan (should show no changes)

Risk: HIGH
```

### Check All Tools Between L0 Configs

```bash
# When upgrading from old L0 to new L0
$ cp topology/L0-meta/_index.yaml topology/L0-meta/_index.yaml.old
# ... update L0 with new tool versions ...
$ python topology-tools/utils/breaking_changes.py \
    --all \
    --from-l0 topology/L0-meta/_index.yaml.old \
    --to-l0 topology/L0-meta/_index.yaml
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/validate.yml

name: Validate Topology

on: [pull_request, push]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pyyaml packaging

      - name: Check tool versions
        run: python topology-tools/validators/version_validator.py

      - name: Detect breaking changes
        run: python topology-tools/utils/breaking_changes.py --all

      - name: Generate Terraform
        run: python topology-tools/generate-terraform.py

      - name: Validate Terraform
        run: |
          cd terraform
          terraform init
          terraform validate
```

---

## Integration with Validators

### Add to Main Validator

Update `topology-tools/validators/__init__.py`:

```python
from .version_validator import VersionValidator

def validate_topology(topology_path, check_tools=True, check_breaking=True):
    """Validate entire topology"""

    # Check tool versions
    if check_tools:
        version_validator = VersionValidator()
        if not version_validator.run():
            raise ValidationError("Tool versions don't match L0 requirements")

    # Check breaking changes
    if check_breaking:
        # Detect breaking changes in next version update
        pass

    # ... other validations ...
```

---

## Troubleshooting

### Tools Not Found

```
[ERROR] Terraform check failed: [Errno 2] No such file or directory: 'terraform'

Solution:
  - Install Terraform
  - Add to PATH
  - Run: terraform --version
```

### Lock File Not Found

```
[WARNING] No .terraform.lock.hcl - providers not checked

Solution:
  - Run: terraform init
  - Then: python version_validator.py
```

### Version Mismatch

```
[ERROR] Terraform 1.4.0 doesn't match ~> 1.5.0

Solution A (Upgrade):
  - Upgrade Terraform to 1.5.x
  - Run: terraform --version
  - Then: python version_validator.py

Solution B (Downgrade L0):
  - Edit: topology/L0-meta/_index.yaml
  - Change: tools.terraform.core: "~> 1.4.0"
  - Then: python version_validator.py
```

---

## Best Practices

### 1. Check Before Generating

Always validate tool versions before generating:

```bash
# Check tools
python topology-tools/validators/version_validator.py

# If OK, then generate
python topology-tools/generate-all.py
```

### 2. Pin Production Versions

For production, use exact versions:

```yaml
# topology/L0-meta/production.yaml
tools:
  terraform:
    core: "1.5.2"  # Exact version for prod
```

### 3. Update L0 When Upgrading Tools

When upgrading a tool:

1. Upgrade the tool
2. Update L0 config
3. Check for breaking changes
4. Update topology if needed
5. Commit both L0 and topology changes

```bash
# Example: Upgrade Terraform

# 1. Upgrade
terraform --version  # Check old version
terraform version    # Upgrade
terraform --version  # Verify new version

# 2. Update L0
vim topology/L0-meta/_index.yaml
# Change: tools.terraform.core: "~> 1.6.0"

# 3. Check breaking changes
python topology-tools/utils/breaking_changes.py \
    --tool terraform \
    --from 1.5.0 \
    --to 1.6.0

# 4. Update topology if needed
# ... make required changes ...

# 5. Validate and commit
python topology-tools/validators/version_validator.py
git add topology/L0-meta/_index.yaml topology/...
git commit -m "Upgrade Terraform to 1.6.0"
```

### 4. Team Synchronization

Report tool versions to team:

```bash
# Generate version report
python topology-tools/validators/version_validator.py \
    --report-team > /tmp/version-report.txt

# Share with team
cat /tmp/version-report.txt

# Result: Everyone sees what version to use
```

---

## Future Enhancements

Planned features:

- [ ] Auto-update L0 with installed versions: `--auto-update`
- [ ] Generate Dockerfile with pinned versions
- [ ] Generate Docker Compose for consistent environments
- [ ] Track version history in git
- [ ] Slack notifications for breaking changes
- [ ] Auto-migration scripts for breaking changes

---

## Support

For issues or questions:
1. Check `topology-tools/data/breaking-changes.yaml`
2. Review `docs/UPGRADE-GUIDE.md`
3. Check git history: `git log -p -- topology/L0-meta/`
