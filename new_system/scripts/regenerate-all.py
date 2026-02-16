#!/usr/bin/env python3
"""
Regenerate ALL files from topology.yaml

This script runs all generators in the correct order:
1. Validate topology
2. Generate Terraform (Proxmox)
3. Generate Terraform (MikroTik)
4. Generate Ansible inventory
5. Generate documentation

Usage:
    python3 scripts/regenerate-all.py [--topology topology.yaml]

Requirements:
    pip install pyyaml jinja2 jsonschema
"""

import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


class RegenerateAll:
    """Run all generators for topology v2.0"""

    def __init__(self, topology_path: str):
        self.topology_path = topology_path
        self.scripts_dir = Path("scripts")
        self.errors = []
        self.start_time = datetime.now()

    def print_header(self, text: str):
        """Print section header"""
        print("\n" + "="*70)
        print(f"  {text}")
        print("="*70 + "\n")

    def run_script(self, script_name: str, description: str) -> bool:
        """Run a Python script and capture result"""
        print(f"▶️  {description}...")
        print(f"   Script: {script_name}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}\n")

        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            error = f"Script not found: {script_path}"
            print(f"❌ {error}\n")
            self.errors.append(error)
            return False

        try:
            result = subprocess.run(
                ["python3", str(script_path), "--topology", self.topology_path],
                capture_output=False,  # Show output in real-time
                text=True,
                check=True
            )
            print(f"✅ {description} completed\n")
            return True

        except subprocess.CalledProcessError as e:
            error = f"{description} failed with exit code {e.returncode}"
            print(f"❌ {error}\n")
            self.errors.append(error)
            return False
        except Exception as e:
            error = f"{description} failed: {e}"
            print(f"❌ {error}\n")
            self.errors.append(error)
            return False

    def run_all(self) -> bool:
        """Run all generators"""
        self.print_header("🔄 Regenerate All from topology.yaml")

        print(f"📁 Topology file: {self.topology_path}")
        print(f"🕐 Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Step 1: Validate topology
        self.print_header("Step 1/5: Validate Topology")
        if not self.run_script("validate-topology.py", "Validating topology"):
            print("⚠️  Validation failed, but continuing with generation...")
            print("   (Fix validation errors to ensure correct output)\n")

        # Step 2: Generate Terraform (Proxmox)
        self.print_header("Step 2/5: Generate Terraform (Proxmox)")
        success_terraform = self.run_script("generate-terraform.py", "Generating Proxmox Terraform configuration")

        # Step 3: Generate Terraform (MikroTik)
        self.print_header("Step 3/5: Generate Terraform (MikroTik)")
        success_mikrotik = self.run_script("generate-terraform-mikrotik.py", "Generating MikroTik Terraform configuration")

        # Step 4: Generate Ansible inventory
        self.print_header("Step 4/5: Generate Ansible Inventory")
        success_ansible = self.run_script("generate-ansible-inventory.py", "Generating Ansible inventory")

        # Step 5: Generate documentation
        self.print_header("Step 5/5: Generate Documentation")
        success_docs = self.run_script("generate-docs.py", "Generating documentation")

        # Summary
        self.print_summary(success_terraform, success_mikrotik, success_ansible, success_docs)

        # Return True only if all critical generators succeeded
        return success_terraform and success_mikrotik and success_ansible and success_docs

    def print_summary(self, success_terraform: bool, success_mikrotik: bool, success_ansible: bool, success_docs: bool):
        """Print final summary"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        self.print_header("📊 Summary")

        print("Results:")
        print(f"  {'✅' if success_terraform else '❌'} Terraform (Proxmox):  {'Success' if success_terraform else 'Failed'}")
        print(f"  {'✅' if success_mikrotik else '❌'} Terraform (MikroTik): {'Success' if success_mikrotik else 'Failed'}")
        print(f"  {'✅' if success_ansible else '❌'} Ansible:              {'Success' if success_ansible else 'Failed'}")
        print(f"  {'✅' if success_docs else '❌'} Documentation:        {'Success' if success_docs else 'Failed'}")

        print(f"\n⏱️  Duration: {duration:.2f} seconds")
        print(f"🕐 Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if self.errors:
            print(f"\n⚠️  Errors encountered: {len(self.errors)}")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")

        print("\n" + "="*70)

        all_success = success_terraform and success_mikrotik and success_ansible and success_docs
        if all_success:
            print("\n✅ All generators completed successfully!")
            print("\n📁 Generated files structure:")
            print("   generated/")
            print("   ├── terraform/              # Proxmox infrastructure")
            print("   │   ├── provider.tf")
            print("   │   ├── bridges.tf")
            print("   │   ├── vms.tf")
            print("   │   ├── lxc.tf")
            print("   │   ├── variables.tf")
            print("   │   └── terraform.tfvars.example")
            print("   ├── terraform-mikrotik/     # MikroTik RouterOS")
            print("   │   ├── provider.tf")
            print("   │   ├── interfaces.tf")
            print("   │   ├── addresses.tf")
            print("   │   ├── dhcp.tf")
            print("   │   ├── firewall.tf")
            print("   │   ├── qos.tf")
            print("   │   ├── vpn.tf")
            print("   │   ├── containers.tf")
            print("   │   ├── variables.tf")
            print("   │   └── terraform.tfvars.example")
            print("   ├── ansible/")
            print("   │   └── inventory/")
            print("   │       └── production/")
            print("   │           ├── hosts.yml")
            print("   │           ├── group_vars/")
            print("   │           └── host_vars/")
            print("   └── docs/")
            print("       ├── overview.md")
            print("       ├── network-diagram.md")
            print("       ├── ip-allocation.md")
            print("       ├── services.md")
            print("       └── devices.md")

            print("\n📝 Next steps:")
            print("   1. Bootstrap MikroTik: see bootstrap/mikrotik/README.md")
            print("   2. Configure terraform.tfvars files in both directories")
            print("   3. Deploy using Makefile:")
            print("      cd deploy && make deploy-all")
            print("   Or deploy manually:")
            print("      cd generated/terraform-mikrotik && terraform init && terraform apply")
            print("      cd generated/terraform && terraform init && terraform apply")
            print("      cd ansible && ansible-playbook -i inventory/production/hosts.yml site.yml")
        else:
            print("\n❌ Some generators failed. Check errors above.")
            print("   Fix issues and run again: python3 scripts/regenerate-all.py")

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

    args = parser.parse_args()

    regenerator = RegenerateAll(args.topology)
    success = regenerator.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
