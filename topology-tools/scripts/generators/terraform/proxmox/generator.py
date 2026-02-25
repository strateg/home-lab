"""
Terraform generator core for Proxmox resources.
"""

from scripts.generators.terraform.base import TerraformGeneratorBase
from scripts.generators.terraform.resolvers import build_storage_map, resolve_interface_names, resolve_lxc_resources


class TerraformGenerator(TerraformGeneratorBase):
    """Generate Terraform configs from topology v4.0"""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = "topology-tools/templates"):
        super().__init__(
            topology_path=topology_path,
            output_dir=output_dir,
            templates_dir=templates_dir,
            template_subdir=None,
            autoescape=True,
        )

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        return super().load_topology(
            required_sections=["L0_meta", "L1_foundation", "L2_network", "L3_data", "L4_platform"],
        )

    def generate_all(self) -> bool:
        """Generate all Terraform files"""
        self.prepare_output()

        success = True
        success &= self.generate_versions()
        success &= self.generate_provider()
        success &= self.generate_bridges()
        success &= self.generate_vms()
        success &= self.generate_lxc()
        success &= self.generate_variables()
        success &= self.generate_outputs()

        return success

    def generate_provider(self) -> bool:
        """Generate provider.tf with Proxmox configuration"""
        proxmox_device = None
        for device in self.topology["L1_foundation"].get("devices", []):
            if device.get("type") == "hypervisor" and device.get("role") == "compute":
                proxmox_device = device
                break

        if not proxmox_device:
            print("WARN  Warning: No Proxmox hypervisor found in L1_foundation")

        mgmt_network = None
        for network in self.topology["L2_network"].get("networks", []):
            if "management" in network.get("id", ""):
                mgmt_network = network
                break

        return self.render_template(
            "terraform/proxmox/provider.tf.j2",
            "provider.tf",
            {
                "proxmox_device": proxmox_device,
                "mgmt_network": mgmt_network,
            },
        )

    def generate_versions(self) -> bool:
        """Generate versions.tf with required Terraform and provider versions"""
        return self.render_template(
            "terraform/proxmox/versions.tf.j2",
            "versions.tf",
            {"topology_version": self.topology_version},
        )

    def generate_bridges(self) -> bool:
        """Generate bridges.tf with network bridge resources"""
        bridges = self.topology["L2_network"].get("bridges", [])
        bridges = resolve_interface_names(self.topology, bridges)
        return self.render_template(
            "terraform/proxmox/bridges.tf.j2",
            "bridges.tf",
            {
                "bridges": bridges,
                "topology_version": self.topology_version,
            },
        )

    def generate_vms(self) -> bool:
        """Generate vms.tf with VM resources"""
        vms = self.topology["L4_platform"].get("vms", [])
        storage_map = build_storage_map(self.topology, platform="proxmox")
        bridge_map = {b["id"]: b for b in self.topology["L2_network"].get("bridges", [])}

        return self.render_template(
            "terraform/proxmox/vms.tf.j2",
            "vms.tf",
            {
                "vms": vms,
                "storage_map": storage_map,
                "bridge_map": bridge_map,
                "topology_version": self.topology_version,
            },
        )

    def generate_lxc(self) -> bool:
        """Generate lxc.tf with LXC container resources"""
        lxc_containers = self.topology["L4_platform"].get("lxc", [])
        lxc_containers = resolve_lxc_resources(self.topology, lxc_containers)
        storage_map = build_storage_map(self.topology, platform="proxmox")
        bridge_map = {b["id"]: b for b in self.topology["L2_network"].get("bridges", [])}

        return self.render_template(
            "terraform/proxmox/lxc.tf.j2",
            "lxc.tf",
            {
                "lxc_containers": lxc_containers,
                "storage_map": storage_map,
                "bridge_map": bridge_map,
                "topology_version": self.topology_version,
            },
        )

    def generate_variables(self) -> bool:
        """Generate variables.tf and terraform.tfvars.example"""
        success = True
        success &= self.render_template(
            "terraform/proxmox/variables.tf.j2",
            "variables.tf",
            {},
        )

        mgmt_network = None
        for network in self.topology["L2_network"].get("networks", []):
            if "management" in network.get("id", ""):
                mgmt_network = network
                break

        success &= self.render_template(
            "terraform/proxmox/terraform.tfvars.example.j2",
            "terraform.tfvars.example",
            {"mgmt_network": mgmt_network},
        )

        return success

    def generate_outputs(self) -> bool:
        """Generate outputs.tf with infrastructure outputs"""
        bridges = self.topology["L2_network"].get("bridges", [])
        lxc_containers = self.topology["L4_platform"].get("lxc", [])
        vms = self.topology["L4_platform"].get("vms", [])
        storage = sorted(
            build_storage_map(self.topology, platform="proxmox").values(),
            key=lambda item: str(item.get("id") or item.get("name") or ""),
        )
        devices = self.topology["L1_foundation"].get("devices", [])

        return self.render_template(
            "terraform/proxmox/outputs.tf.j2",
            "outputs.tf",
            {
                "bridges": bridges,
                "lxc_containers": lxc_containers,
                "vms": vms,
                "storage": storage,
                "devices": devices,
                "topology_version": self.topology_version,
            },
        )

    def print_summary(self) -> None:
        """Print generation summary."""
        print("\n" + "=" * 70)
        print("Terraform Generation Summary")
        print("=" * 70)

        bridges = len(self.topology["L2_network"].get("bridges", []))
        vms = len(self.topology["L4_platform"].get("vms", []))
        lxc = len(self.topology["L4_platform"].get("lxc", []))

        print("\nOK Generated Terraform configuration for:")
        print(f"  - {bridges} network bridges")
        print(f"  - {vms} VMs")
        print(f"  - {lxc} LXC containers")
        print(f"\nOK Output directory: {self.output_dir}")
        print("\n Note: Using bpg/proxmox provider v0.85+ for automated bridge creation")
        print("   If bridges fail to create, see BRIDGES.md for manual setup")
        print("\nNext steps:")
        print("  1. Verify physical interface names in topology/L1-foundation.yaml")
        print("     - if-eth-usb -> check actual USB Ethernet name (enxXXXX)")
        print("     - if-eth-builtin -> check actual built-in Ethernet name (enp3s0)")
        print("  2. Copy terraform.tfvars.example to terraform.tfvars")
        print("  3. Edit terraform.tfvars with your credentials")
        print(f"  4. Run: cd {self.output_dir} && terraform init -upgrade")
        print("  5. Run: terraform plan")
        print("  6. Run: terraform apply")
