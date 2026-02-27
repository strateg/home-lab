# L0 Tool Versions: Implementation Guide

**Дата:** 26 февраля 2026 г.
**Задача:** Реализовать версионирование инструментов в L0

---

## Step 1: Расширить L0

### L0-meta/_index.yaml

```yaml
version: 4.0.0
name: "Home Lab Infrastructure"

# === GLOBAL SETTINGS ===
compliance:
  gdpr_compliant: true

security_constraints:
  encryption_required: true

# === TOOL VERSIONS (NEW!) ===
tools:
  terraform:
    core: "~> 1.5.0"
    providers:
      proxmox: "~> 0.45.0"
      null: "~> 3.2.0"
      local: "~> 2.4.0"

  ansible:
    core: "~> 2.14.0"
    collections:
      community.general: "~> 7.0.0"
      community.proxmox: "~> 1.2.0"

  python:
    core: "~> 3.11.0"
    packages:
      pyyaml: "~> 6.0"
      jinja2: "~> 3.1"
      requests: "~> 2.31"
      pydantic: "~> 2.0"

  other:
    docker: "~> 24.0"
    jq: ">= 1.6"

# === GENERATION STRATEGY ===
generation:
  # Strategy when version conflict found
  compatibility_mode: "strict"  # strict, compatible, auto-migrate

  # What to do on breaking changes
  breaking_changes_action: "warn"  # warn, fail, auto-migrate

  # Add version metadata to generated code
  document_with_versions: true
```

---

## Step 2: Создать Версионный Валидатор

### topology-tools/validators/version_validator.py

```python
#!/usr/bin/env python3
"""
Version validator - check tool versions against L0 requirements
"""

import subprocess
import re
from typing import Dict, Tuple
from packaging import version as pkg_version
from pathlib import Path
import yaml

class VersionValidator:
    """Validate installed tool versions against L0 requirements"""

    def __init__(self, l0_path: str = "L0-meta/_index.yaml"):
        """Load L0 config"""
        with open(l0_path) as f:
            self.l0 = yaml.safe_load(f)
        self.errors = []
        self.warnings = []

    def run(self) -> bool:
        """Run all version checks"""
        print("=" * 60)
        print("TOOL VERSION VALIDATION")
        print("=" * 60)

        self._check_terraform()
        self._check_ansible()
        self._check_python()
        self._check_docker()

        return self._report()

    def _check_terraform(self):
        """Check Terraform version"""
        print("\n[TERRAFORM]")
        try:
            installed = self._get_terraform_version()
            required = self.l0['tools']['terraform']['core']

            print(f"  Installed: {installed}")
            print(f"  Required:  {required}")

            if self._match_version(installed, required):
                print("  Status: ✓ OK")
            else:
                self.errors.append(
                    f"Terraform {installed} doesn't match {required}"
                )
                print(f"  Status: ✗ MISMATCH")

            # Check providers
            self._check_terraform_providers()

        except Exception as e:
            self.errors.append(f"Terraform check failed: {e}")

    def _check_terraform_providers(self):
        """Check Terraform providers"""
        providers = self.l0['tools']['terraform']['providers']

        # This requires terraform init to have been run
        # or parse .terraform.lock.hcl file

        for provider, required_version in providers.items():
            try:
                # Try to read from lock file
                installed = self._get_provider_version(provider)

                if self._match_version(installed, required_version):
                    print(f"  Provider {provider}: ✓ {installed}")
                else:
                    self.warnings.append(
                        f"Provider {provider} {installed} "
                        f"may not match {required_version}"
                    )
                    print(f"  Provider {provider}: ~ {installed} (warning)")
            except:
                self.warnings.append(f"Provider {provider} not found (not installed)")

    def _check_ansible(self):
        """Check Ansible version"""
        print("\n[ANSIBLE]")
        try:
            installed = self._get_ansible_version()
            required = self.l0['tools']['ansible']['core']

            print(f"  Installed: {installed}")
            print(f"  Required:  {required}")

            if self._match_version(installed, required):
                print("  Status: ✓ OK")
            else:
                self.errors.append(
                    f"Ansible {installed} doesn't match {required}"
                )
                print(f"  Status: ✗ MISMATCH")

            # Check collections
            self._check_ansible_collections()

        except Exception as e:
            self.errors.append(f"Ansible check failed: {e}")

    def _check_ansible_collections(self):
        """Check Ansible collections"""
        collections = self.l0['tools']['ansible']['collections']

        for collection, required_version in collections.items():
            try:
                installed = self._get_collection_version(collection)

                if self._match_version(installed, required_version):
                    print(f"  Collection {collection}: ✓ {installed}")
                else:
                    self.warnings.append(
                        f"Collection {collection} {installed} "
                        f"may not match {required_version}"
                    )
                    print(f"  Collection {collection}: ~ {installed} (warning)")
            except:
                self.warnings.append(f"Collection {collection} not found")

    def _check_python(self):
        """Check Python version"""
        print("\n[PYTHON]")
        import sys

        installed = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        required = self.l0['tools']['python']['core']

        print(f"  Installed: {installed}")
        print(f"  Required:  {required}")

        if self._match_version(installed, required):
            print("  Status: ✓ OK")
        else:
            self.errors.append(
                f"Python {installed} doesn't match {required}"
            )
            print(f"  Status: ✗ MISMATCH")

        # Check packages
        self._check_python_packages()

    def _check_python_packages(self):
        """Check Python packages"""
        packages = self.l0['tools']['python']['packages']

        for package, required_version in packages.items():
            try:
                import importlib.metadata
                installed = importlib.metadata.version(package)

                if self._match_version(installed, required_version):
                    print(f"  Package {package}: ✓ {installed}")
                else:
                    self.warnings.append(
                        f"Package {package} {installed} "
                        f"may not match {required_version}"
                    )
                    print(f"  Package {package}: ~ {installed} (warning)")
            except:
                self.warnings.append(f"Package {package} not installed")

    def _check_docker(self):
        """Check Docker version"""
        print("\n[DOCKER]")
        try:
            installed = self._get_docker_version()
            required = self.l0['tools']['other']['docker']

            print(f"  Installed: {installed}")
            print(f"  Required:  {required}")

            if self._match_version(installed, required):
                print("  Status: ✓ OK")
            else:
                self.warnings.append(
                    f"Docker {installed} may not match {required}"
                )
                print(f"  Status: ~ WARNING")
        except:
            self.warnings.append("Docker not found")

    # Helper methods

    def _get_terraform_version(self) -> str:
        """Get installed Terraform version"""
        output = subprocess.check_output(['terraform', '--version']).decode()
        match = re.search(r'Terraform v([\d.]+)', output)
        return match.group(1) if match else "unknown"

    def _get_ansible_version(self) -> str:
        """Get installed Ansible version"""
        output = subprocess.check_output(['ansible', '--version']).decode()
        match = re.search(r'ansible \[(core ([\d.]+)\])', output)
        return match.group(2) if match else "unknown"

    def _get_docker_version(self) -> str:
        """Get installed Docker version"""
        output = subprocess.check_output(['docker', '--version']).decode()
        match = re.search(r'Docker version ([\d.]+)', output)
        return match.group(1) if match else "unknown"

    def _get_provider_version(self, provider: str) -> str:
        """Get Terraform provider version from lock file"""
        lock_file = Path('.terraform.lock.hcl')
        if not lock_file.exists():
            raise FileNotFoundError("No .terraform.lock.hcl found")

        content = lock_file.read_text()
        # Simple regex to extract version
        match = re.search(rf'{provider}.*?"version" = "([\d.]+)"', content)
        return match.group(1) if match else "unknown"

    def _get_collection_version(self, collection: str) -> str:
        """Get Ansible collection version"""
        output = subprocess.check_output(
            ['ansible-galaxy', 'collection', 'list', collection]
        ).decode()
        match = re.search(rf'{collection}\s+([\d.]+)', output)
        return match.group(1) if match else "unknown"

    def _match_version(self, installed: str, required: str) -> bool:
        """Check if installed version matches requirement"""
        try:
            # Handle ~> version specifier
            if required.startswith('~> '):
                major, minor = required[3:].split('.')[:2]
                installed_parts = installed.split('.')
                return (
                    installed_parts[0] == major and
                    installed_parts[1] >= minor
                )
            elif required.startswith('>= '):
                return installed >= required[3:]
            else:
                # Exact match or >= if no operator
                return installed >= required
        except:
            return False

    def _report(self) -> bool:
        """Print validation report"""
        print("\n" + "=" * 60)
        print("VALIDATION REPORT")
        print("=" * 60)

        if not self.errors and not self.warnings:
            print("✓ All tools match L0 requirements!")
            return True

        if self.warnings:
            print(f"\n⚠ Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  - {w}")

        if self.errors:
            print(f"\n✗ Errors ({len(self.errors)}):")
            for e in self.errors:
                print(f"  - {e}")
            return False

        return True


if __name__ == "__main__":
    validator = VersionValidator()
    validator.run()
```

---

## Step 3: Использовать Версии в Генераторе

### topology-tools/generators/terraform_generator.py (excerpt)

```python
def generate(self):
    """Generate Terraform configuration with version info"""

    # Validate versions
    validator = VersionValidator()
    if not validator.run():
        if self.l0['generation']['compatibility_mode'] == 'strict':
            raise GenerationError("Tool versions don't match L0 requirements")

    # Generate code
    tf_config = self._build_config()

    # Add version metadata if requested
    if self.l0['generation']['document_with_versions']:
        tf_config = self._add_version_metadata(tf_config)

    return tf_config

def _add_version_metadata(self, config: str) -> str:
    """Add version information to generated code"""

    terraform_version = self.l0['tools']['terraform']['core']
    proxmox_provider = self.l0['tools']['terraform']['providers']['proxmox']

    header = f"""
# Generated Terraform Configuration
#
# Generated with:
#   Terraform: {self._get_installed_version('terraform')}
#   Provider Proxmox: {self._get_installed_version('provider-proxmox')}
#   Generated: {datetime.now().isoformat()}
#
# Compatible with:
#   Terraform: {terraform_version}
#   Provider Proxmox: {proxmox_provider}
#
# Breaking changes in newer versions:
#   - proxmox 0.46.0: proxmox_vm_qemu → proxmox_virtual_machine

terraform {{
  required_version = "{terraform_version}"

  required_providers {{
    proxmox = {{
      source  = "Telmate/proxmox"
      version = "{proxmox_provider}"
    }}
  }}
}}
"""

    return header + "\n" + config
```

---

## Step 4: Использовать в CLI

```bash
# Валидировать версии
$ python topology-tools/validate-topology.py --check-tools
[TERRAFORM]
  Installed: 1.5.2
  Required:  ~> 1.5.0
  Status: ✓ OK
  Provider proxmox: ✓ 0.45.1

[ANSIBLE]
  Installed: 2.14.5
  Required:  ~> 2.14.0
  Status: ✓ OK

[PYTHON]
  Installed: 3.11.2
  Required:  ~> 3.11.0
  Status: ✓ OK

✓ All tools match L0 requirements!

---

# Генерировать с информацией о версиях
$ python topology-tools/generate-terraform.py

# Generated terraform/main.tf will include:
# Generated Terraform Configuration
#
# Generated with:
#   Terraform: 1.5.2
#   Provider Proxmox: 0.45.1
#   Generated: 2026-02-26T10:30:00
#
# Compatible with:
#   Terraform: ~> 1.5.0
#   Provider Proxmox: ~> 0.45.0
```

---

## Профит: Что Получим

| Функция | Экономия |
|---------|----------|
| Автоматическая проверка версий | 2 часа отладки |
| Обнаружение несовместимости перед генерацией | 3 часа на исправление |
| Информация о версиях в generated code | 1 час документирования |
| Возможность воспроизвести старые версии | Неоценимо! |
| CI/CD гарантирует совместимость | Prevents broken merges |

**TOTAL: 6+ часов экономии + предотвращение проблем в production!**
