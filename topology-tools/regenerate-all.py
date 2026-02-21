#!/usr/bin/env python3
"""
Regenerate ALL files from topology.yaml (v4 layered)

This script runs all generators in the correct order:
1. Validate topology
2. Generate Terraform (Proxmox)
3. Generate Terraform (MikroTik)
4. Generate Ansible inventory
5. Generate documentation
6. Validate Mermaid rendering (optional)

Usage:
    python3 topology-tools/regenerate-all.py [--topology topology.yaml]

Requirements:
    pip install pyyaml jinja2 jsonschema
"""

import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from scripts.generators.common import clear_topology_cache, warm_topology_cache


class RegenerateAll:
    """Run all generators for topology v4.0"""

    def __init__(
        self,
        topology_path: str,
        validate_mermaid: bool = True,
        mermaid_icon_mode: str = "auto",
        strict_validate: bool = True,
        fail_on_validation: bool = False,
        use_topology_cache: bool = True,
        clear_cache_first: bool = False,
    ):
        self.topology_path = topology_path
        self.scripts_dir = Path(__file__).resolve().parent
        self.project_root = self.scripts_dir.parent
        self.validate_mermaid = validate_mermaid
        self.mermaid_icon_mode = mermaid_icon_mode
        self.strict_validate = strict_validate
        self.fail_on_validation = fail_on_validation
        self.use_topology_cache = use_topology_cache
        self.clear_cache_first = clear_cache_first
        self.errors = []
        self.start_time = datetime.now()

    def print_header(self, text: str):
        """Print section header"""
        print("\n" + "="*70)
        print(f"  {text}")
        print("="*70 + "\n")

    def run_script(self, script_name: str, description: str, args: Optional[List[str]] = None) -> bool:
        """Run a Python script and capture result"""
        print(f"RUN  {description}...")
        print(f"   Script: {script_name}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}\n")

        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            error = f"Script not found: {script_path}"
            print(f"ERROR {error}\n")
            self.errors.append(error)
            return False

        try:
            command = [sys.executable, str(script_path)]
            if args:
                command.extend(args)

            subprocess.run(
                command,
                capture_output=False,
                text=True,
                check=True,
                cwd=str(self.project_root),
            )
            print(f"OK {description} completed\n")
            return True

        except subprocess.CalledProcessError as e:
            error = f"{description} failed with exit code {e.returncode}"
            print(f"ERROR {error}\n")
            self.errors.append(error)
            return False
        except Exception as e:
            error = f"{description} failed: {e}"
            print(f"ERROR {error}\n")
            self.errors.append(error)
            return False

    def run_all(self) -> bool:
        """Run all generators"""
        self.print_header("REGEN Regenerate All from topology.yaml (v4)")

        print(f"DIR Topology file: {self.topology_path}")
        print(f"TIME Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"CACHE Topology cache: {'enabled' if self.use_topology_cache else 'disabled'}")
        print(f"STEP Validation mode: {'strict' if self.strict_validate else 'compat'}")
        print(f"STEP Fail on validation error: {'yes' if self.fail_on_validation else 'no'}")
        if self.use_topology_cache and self.clear_cache_first:
            try:
                cache_removed = clear_topology_cache(self.topology_path)
                if cache_removed:
                    print("CACHE Cleared existing topology cache")
                else:
                    print("CACHE No existing topology cache to clear")
            except OSError as e:
                print(f"WARN  Failed to clear topology cache: {e}")
        total_steps = 6 if self.validate_mermaid else 5

        self.print_header(f"Step 1/{total_steps}: Validate Topology")
        validate_args = ["--topology", self.topology_path]
        validate_args.append("--strict" if self.strict_validate else "--compat")
        if not self.use_topology_cache:
            validate_args.append("--no-topology-cache")
        if not self.run_script(
            "validate-topology.py",
            "Validating topology",
            validate_args,
        ):
            if self.fail_on_validation:
                print("ERROR Validation failed, stopping due to fail-on-validation policy.")
                self.print_summary(False, False, False, False, not self.validate_mermaid)
                return False
            print("WARN  Validation failed, but continuing with generation...")
            print("   (Fix validation errors to ensure correct output)\n")

        if self.use_topology_cache:
            print("CACHE Warming shared topology cache...")
            try:
                warm_topology_cache(self.topology_path)
                print("OK Topology cache is ready\n")
            except Exception as e:
                warning = f"Topology cache warm-up failed: {e}"
                print(f"WARN  {warning}\n")
                self.errors.append(warning)

        self.print_header(f"Step 2/{total_steps}: Generate Terraform (Proxmox)")
        success_terraform = self.run_script(
            "generate-terraform-proxmox.py",
            "Generating Proxmox Terraform configuration",
            ["--topology", self.topology_path],
        )

        self.print_header(f"Step 3/{total_steps}: Generate Terraform (MikroTik)")
        success_mikrotik = self.run_script(
            "generate-terraform-mikrotik.py",
            "Generating MikroTik Terraform configuration",
            ["--topology", self.topology_path],
        )

        self.print_header(f"Step 4/{total_steps}: Generate Ansible Inventory")
        success_ansible = self.run_script(
            "generate-ansible-inventory.py",
            "Generating Ansible inventory",
            ["--topology", self.topology_path],
        )

        self.print_header(f"Step 5/{total_steps}: Generate Documentation")
        success_docs = self.run_script(
            "generate-docs.py",
            "Generating documentation",
            ["--topology", self.topology_path],
        )

        success_mermaid = True
        if self.validate_mermaid:
            self.print_header(f"Step 6/{total_steps}: Validate Mermaid Rendering")
            success_mermaid = self.run_script(
                "validate-mermaid-render.py",
                "Validating Mermaid renderability",
                ["--docs-dir", "generated/docs", "--icon-mode", self.mermaid_icon_mode],
            )

        self.print_summary(success_terraform, success_mikrotik, success_ansible, success_docs, success_mermaid)

        return success_terraform and success_mikrotik and success_ansible and success_docs and success_mermaid

    def print_summary(
        self,
        success_terraform: bool,
        success_mikrotik: bool,
        success_ansible: bool,
        success_docs: bool,
        success_mermaid: bool,
    ):
        """Print final summary"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        self.print_header("SUMMARY Summary")

        print("Results:")
        print(f"  {'OK' if success_terraform else 'ERROR'} Terraform (Proxmox):  {'Success' if success_terraform else 'Failed'}")
        print(f"  {'OK' if success_mikrotik else 'ERROR'} Terraform (MikroTik): {'Success' if success_mikrotik else 'Failed'}")
        print(f"  {'OK' if success_ansible else 'ERROR'} Ansible:              {'Success' if success_ansible else 'Failed'}")
        print(f"  {'OK' if success_docs else 'ERROR'} Documentation:        {'Success' if success_docs else 'Failed'}")
        print(f"  {'OK' if success_mermaid else 'ERROR'} Mermaid Render:      {'Success' if success_mermaid else 'Failed'}")

        print(f"\nTIME  Duration: {duration:.2f} seconds")
        print(f"TIME Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if self.errors:
            print(f"\nWARN  Errors encountered: {len(self.errors)}")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")

        print("\n" + "="*70)

        all_success = success_terraform and success_mikrotik and success_ansible and success_docs and success_mermaid
        if all_success:
            print("\nOK All generators completed successfully!")
            print("\nDIR Generated files structure:")
            print("   generated/")
            print("    terraform/              # Proxmox infrastructure")
            print("       provider.tf")
            print("       bridges.tf")
            print("       vms.tf")
            print("       lxc.tf")
            print("       variables.tf")
            print("       terraform.tfvars.example")
            print("    terraform-mikrotik/     # MikroTik RouterOS")
            print("       provider.tf")
            print("       interfaces.tf")
            print("       addresses.tf")
            print("       dhcp.tf")
            print("       firewall.tf")
            print("       qos.tf")
            print("       vpn.tf")
            print("       containers.tf")
            print("       variables.tf")
            print("       terraform.tfvars.example")
            print("    ansible/")
            print("       inventory/")
            print("           production/")
            print("               hosts.yml")
            print("               group_vars/")
            print("               host_vars/")
            print("    docs/")
            print("        overview.md")
            print("        network-diagram.md")
            print("        ip-allocation.md")
            print("        services.md")
            print("        devices.md")

            print("\nGEN Next steps:")
            print("   1. Bootstrap MikroTik: see bootstrap/mikrotik/README.md")
            print("   2. Configure terraform.tfvars files in both directories")
            print("   3. Deploy using Makefile:")
            print("      cd deploy && make deploy-all")
            print("   Or deploy manually:")
            print("      cd generated/terraform-mikrotik && terraform init && terraform apply")
            print("      cd generated/terraform && terraform init && terraform apply")
            print("      cd ansible && ansible-playbook -i inventory/production/hosts.yml site.yml")
        else:
            print("\nERROR Some generators failed. Check errors above.")
            print("   Fix issues and run again: python3 topology-tools/regenerate-all.py")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate ALL files from topology.yaml (validate + terraform + ansible + docs)"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file (default: topology.yaml)"
    )
    parser.add_argument(
        "--skip-mermaid-validate",
        action="store_true",
        help="Skip Mermaid render validation step after docs generation"
    )
    parser.add_argument(
        "--mermaid-icon-mode",
        default="auto",
        choices=["auto", "icon-nodes", "compat", "none"],
        help="Icon mode to use for Mermaid render validation (default: auto)"
    )
    parser.add_argument(
        "--no-topology-cache",
        action="store_true",
        help="Disable shared topology cache for validation/generation",
    )
    parser.add_argument(
        "--clear-topology-cache",
        action="store_true",
        help="Clear existing topology cache before regeneration",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--strict",
        dest="strict_validate",
        action="store_true",
        help="Run topology validation in strict mode (default)",
    )
    mode_group.add_argument(
        "--compat-validation",
        dest="strict_validate",
        action="store_false",
        help="Run topology validation in compatibility mode",
    )
    parser.set_defaults(strict_validate=True)
    parser.add_argument(
        "--fail-on-validation",
        action="store_true",
        help="Stop regenerate-all immediately when topology validation fails",
    )

    args = parser.parse_args()

    regenerator = RegenerateAll(
        args.topology,
        validate_mermaid=not args.skip_mermaid_validate,
        mermaid_icon_mode=args.mermaid_icon_mode,
        strict_validate=args.strict_validate,
        fail_on_validation=args.fail_on_validation or args.strict_validate,
        use_topology_cache=not args.no_topology_cache,
        clear_cache_first=args.clear_topology_cache,
    )
    success = regenerator.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

