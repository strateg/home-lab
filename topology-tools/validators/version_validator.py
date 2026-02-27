#!/usr/bin/env python3
"""
Version Validator - Check tool versions against L0 requirements

Usage:
    python version_validator.py --check-all
    python version_validator.py --terraform
    python version_validator.py --report-team
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

try:
    from packaging import version as pkg_version
except ImportError:
    print("[ERROR] packaging not installed. Run: pip install packaging")
    sys.exit(1)


class VersionValidator:
    """Validate installed tool versions against L0 requirements"""

    def __init__(self, l0_path: str = "topology/L0-meta/_index.yaml"):
        """Initialize validator with L0 config"""
        self.l0_path = Path(l0_path)

        if not self.l0_path.exists():
            print(f"[ERROR] L0 config not found: {l0_path}")
            sys.exit(1)

        with open(self.l0_path) as f:
            self.l0 = yaml.safe_load(f)

        self.results = {"passed": [], "warnings": [], "errors": []}

    def run(self, checks: Optional[list] = None) -> bool:
        """Run version checks"""
        if checks is None:
            checks = ["terraform", "ansible", "python", "other"]

        print("=" * 70)
        print("TOOL VERSION VALIDATION")
        print("=" * 70)

        if "terraform" in checks:
            self._check_terraform()
        if "ansible" in checks:
            self._check_ansible()
        if "python" in checks:
            self._check_python()
        if "other" in checks:
            self._check_other()

        return self._report()

    def _check_terraform(self):
        """Check Terraform version and providers"""
        print("\n[TERRAFORM]")

        try:
            installed = self._get_terraform_version()
            required = self.l0["tools"]["terraform"]["core"]

            print(f"  Core version:")
            print(f"    Installed: {installed}")
            print(f"    Required:  {required}")

            if self._match_version(installed, required):
                self.results["passed"].append(f"Terraform {installed} ✓")
                print(f"    Status:    ✓ OK")
            else:
                self.results["errors"].append(f"Terraform {installed} doesn't match {required}")
                print(f"    Status:    ✗ MISMATCH")

            # Check providers
            print(f"\n  Providers:")
            self._check_terraform_providers()

        except Exception as e:
            self.results["errors"].append(f"Terraform check failed: {e}")
            print(f"  [ERROR] {e}")

    def _check_terraform_providers(self):
        """Check Terraform providers from lock file"""
        providers = self.l0["tools"]["terraform"].get("providers", {})
        lock_file = Path(".terraform.lock.hcl")

        if not lock_file.exists():
            self.results["warnings"].append("No .terraform.lock.hcl found - providers not checked")
            print("    [WARNING] No .terraform.lock.hcl - run 'terraform init' first")
            return

        lock_content = lock_file.read_text()

        for provider, required_version in providers.items():
            try:
                # Extract provider version from lock file
                pattern = rf'{provider}["\']?\s*{{[^}}]*?"version" = "([^"]+)"'
                match = re.search(pattern, lock_content)

                if match:
                    installed = match.group(1)
                    print(f"    {provider}:")
                    print(f"      Installed: {installed}")
                    print(f"      Required:  {required_version}")

                    if self._match_version(installed, required_version):
                        self.results["passed"].append(f"terraform-provider-{provider} {installed} ✓")
                        print(f"      Status:    ✓ OK")
                    else:
                        self.results["warnings"].append(
                            f"Provider {provider} {installed} may not match {required_version}"
                        )
                        print(f"      Status:    ~ WARNING")
                else:
                    self.results["warnings"].append(f"Provider {provider} not in lock file")
                    print(f"    {provider}: [WARNING] Not in lock file")
            except Exception as e:
                self.results["errors"].append(f"Provider {provider} check failed: {e}")

    def _check_ansible(self):
        """Check Ansible version and collections"""
        print("\n[ANSIBLE]")

        try:
            installed = self._get_ansible_version()
            required = self.l0["tools"]["ansible"]["core"]

            print(f"  Core version:")
            print(f"    Installed: {installed}")
            print(f"    Required:  {required}")

            if self._match_version(installed, required):
                self.results["passed"].append(f"Ansible {installed} ✓")
                print(f"    Status:    ✓ OK")
            else:
                self.results["errors"].append(f"Ansible {installed} doesn't match {required}")
                print(f"    Status:    ✗ MISMATCH")

            # Check collections
            print(f"\n  Collections:")
            self._check_ansible_collections()

        except Exception as e:
            self.results["errors"].append(f"Ansible check failed: {e}")
            print(f"  [ERROR] {e}")

    def _check_ansible_collections(self):
        """Check installed Ansible collections"""
        collections = self.l0["tools"]["ansible"].get("collections", {})

        for collection, required_version in collections.items():
            try:
                installed = self._get_collection_version(collection)

                print(f"    {collection}:")
                print(f"      Installed: {installed}")
                print(f"      Required:  {required_version}")

                if self._match_version(installed, required_version):
                    self.results["passed"].append(f"ansible-collection-{collection} {installed} ✓")
                    print(f"      Status:    ✓ OK")
                else:
                    self.results["warnings"].append(
                        f"Collection {collection} {installed} may not match {required_version}"
                    )
                    print(f"      Status:    ~ WARNING")
            except Exception as e:
                self.results["warnings"].append(f"Collection {collection} not found")
                print(f"    {collection}: [WARNING] Not found - {e}")

    def _check_python(self):
        """Check Python version and packages"""
        print("\n[PYTHON]")

        import sys

        installed = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        required = self.l0["tools"]["python"]["core"]

        print(f"  Core version:")
        print(f"    Installed: {installed}")
        print(f"    Required:  {required}")

        if self._match_version(installed, required):
            self.results["passed"].append(f"Python {installed} ✓")
            print(f"    Status:    ✓ OK")
        else:
            self.results["errors"].append(f"Python {installed} doesn't match {required}")
            print(f"    Status:    ✗ MISMATCH")

        # Check packages
        print(f"\n  Packages:")
        self._check_python_packages()

    def _check_python_packages(self):
        """Check installed Python packages"""
        packages = self.l0["tools"]["python"].get("packages", {})

        for package, required_version in packages.items():
            try:
                import importlib.metadata

                installed = importlib.metadata.version(package)

                print(f"    {package}:")
                print(f"      Installed: {installed}")
                print(f"      Required:  {required_version}")

                if self._match_version(installed, required_version):
                    self.results["passed"].append(f"python-package-{package} {installed} ✓")
                    print(f"      Status:    ✓ OK")
                else:
                    self.results["warnings"].append(f"Package {package} {installed} may not match {required_version}")
                    print(f"      Status:    ~ WARNING")
            except Exception as e:
                self.results["warnings"].append(f"Package {package} not installed")
                print(f"    {package}: [WARNING] Not installed")

    def _check_other(self):
        """Check Docker, jq, etc."""
        print("\n[OTHER TOOLS]")

        tools = self.l0["tools"].get("other", {})

        for tool, required_version in tools.items():
            try:
                installed = self._get_tool_version(tool)

                print(f"  {tool}:")
                print(f"    Installed: {installed}")
                print(f"    Required:  {required_version}")

                if self._match_version(installed, required_version):
                    self.results["passed"].append(f"{tool} {installed} ✓")
                    print(f"    Status:    ✓ OK")
                else:
                    self.results["warnings"].append(f"{tool} {installed} may not match {required_version}")
                    print(f"    Status:    ~ WARNING")
            except Exception as e:
                self.results["warnings"].append(f"{tool} not found")
                print(f"  {tool}: [WARNING] Not found")

    # Helper methods

    def _get_terraform_version(self) -> str:
        """Get installed Terraform version"""
        output = subprocess.check_output(["terraform", "--version"]).decode()
        match = re.search(r"Terraform v([\d.]+)", output)
        return match.group(1) if match else "unknown"

    def _get_ansible_version(self) -> str:
        """Get installed Ansible version"""
        output = subprocess.check_output(["ansible", "--version"]).decode()
        match = re.search(r"ansible \[core ([\d.]+)", output)
        return match.group(1) if match else "unknown"

    def _get_collection_version(self, collection: str) -> str:
        """Get installed Ansible collection version"""
        try:
            output = subprocess.check_output(
                ["ansible-galaxy", "collection", "list", collection], stderr=subprocess.DEVNULL
            ).decode()
            match = re.search(rf"{collection}\s+([\d.]+)", output)
            return match.group(1) if match else "unknown"
        except:
            raise Exception(f"Collection {collection} not found")

    def _get_tool_version(self, tool: str) -> str:
        """Get version of arbitrary tool (Docker, jq, etc)"""
        try:
            if tool == "docker":
                output = subprocess.check_output(["docker", "--version"]).decode()
                match = re.search(r"Docker version ([\d.]+)", output)
                return match.group(1) if match else "unknown"
            elif tool == "jq":
                output = subprocess.check_output(["jq", "--version"]).decode()
                match = re.search(r"jq-([\d.]+)", output)
                return match.group(1) if match else "unknown"
            else:
                return "unknown"
        except:
            raise Exception(f"Tool {tool} not found")

    def _match_version(self, installed: str, required: str) -> bool:
        """Check if installed version matches requirement"""
        try:
            if required.startswith("~> "):
                # ~> 1.5.0 means >= 1.5.0, < 1.6.0
                min_ver = required[3:]
                min_parts = min_ver.split(".")
                inst_parts = installed.split(".")

                # Major version must match
                if min_parts[0] != inst_parts[0]:
                    return False

                # Minor version must be >= required
                return inst_parts[1] >= min_parts[1]

            elif required.startswith(">= "):
                return pkg_version.parse(installed) >= pkg_version.parse(required[3:])

            else:
                # Assume >= if no operator
                return pkg_version.parse(installed) >= pkg_version.parse(required)
        except:
            return False

    def _report(self) -> bool:
        """Print validation report"""
        print("\n" + "=" * 70)
        print("VALIDATION REPORT")
        print("=" * 70)

        if self.results["passed"]:
            print(f"\n✓ PASSED ({len(self.results['passed'])}):")
            for item in self.results["passed"]:
                print(f"  {item}")

        if self.results["warnings"]:
            print(f"\n⚠ WARNINGS ({len(self.results['warnings'])}):")
            for item in self.results["warnings"]:
                print(f"  {item}")

        if self.results["errors"]:
            print(f"\n✗ ERRORS ({len(self.results['errors'])}):")
            for item in self.results["errors"]:
                print(f"  {item}")

        print("\n" + "=" * 70)

        if not self.results["errors"]:
            print("✓ All critical checks passed!")
            return True
        else:
            print(f"✗ {len(self.results['errors'])} error(s) found!")
            return False


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate tool versions against L0 requirements")
    parser.add_argument("--check-all", action="store_true", default=True, help="Check all tools (default)")
    parser.add_argument("--terraform", action="store_true", help="Check only Terraform")
    parser.add_argument("--ansible", action="store_true", help="Check only Ansible")
    parser.add_argument("--python", action="store_true", help="Check only Python")
    parser.add_argument("--other", action="store_true", help="Check only other tools")
    parser.add_argument("--l0", default="topology/L0-meta/_index.yaml", help="Path to L0 config file")

    args = parser.parse_args()

    # Determine which checks to run
    checks = []
    if args.terraform:
        checks.append("terraform")
    if args.ansible:
        checks.append("ansible")
    if args.python:
        checks.append("python")
    if args.other:
        checks.append("other")

    if not checks:
        checks = ["terraform", "ansible", "python", "other"]

    # Run validator
    validator = VersionValidator(args.l0)
    success = validator.run(checks)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
