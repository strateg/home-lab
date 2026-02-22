"""
Terraform generator core for MikroTik RouterOS.
"""

from pathlib import Path
import re
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader

from scripts.generators.common import load_and_validate_layered_topology, prepare_output_directory


class MikrotikTerraformGenerator:
    """Generate MikroTik RouterOS Terraform configs from topology v4.0"""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = "topology-tools/templates"):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir) / "terraform" / "mikrotik"
        self.topology: Dict = {}

        self.mikrotik_device: Dict = {}
        self.networks: List[Dict] = []
        self.vlans: List[Dict] = []
        self.lan_ports: List[Dict] = []
        self.firewall_policies: List[Dict] = []
        self.firewall_address_lists: List[Dict] = []
        self.qos: Dict = {}
        self.wireguard: Dict = {}
        self.containers: Dict = {}
        self.dns_records: List[Dict] = []
        self.dns_settings: Dict = {}
        self.dhcp_leases: List[Dict] = []
        self.interface_name_by_id: Dict[str, str] = {}
        self.wan_interface_name: str = 'ether1'
        self.lte_interface_name: str = 'lte1'

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

    @staticmethod
    def _network_list_name(network_id: str) -> str:
        base = network_id[4:] if isinstance(network_id, str) and network_id.startswith('net-') else network_id
        return f"NET_{str(base).replace('-', '_').upper()}"

    @staticmethod
    def _zone_list_name(zone_id: str) -> str:
        return str(zone_id).replace('-', '_').upper()

    @staticmethod
    def _terraform_resource_name(seed: str) -> str:
        resource_name = re.sub(r'[^a-zA-Z0-9_]', '_', str(seed).lower()).strip('_')
        if not resource_name:
            resource_name = 'resource'
        if resource_name[0].isdigit():
            resource_name = f"r_{resource_name}"
        return resource_name

    def _build_interface_name_map(self) -> None:
        self.interface_name_by_id = {}
        for interface in self.mikrotik_device.get('interfaces', []):
            if not isinstance(interface, dict):
                continue
            interface_id = interface.get('id')
            interface_name = interface.get('physical_name') or interface.get('name') or interface_id
            if interface_id and interface_name:
                self.interface_name_by_id[interface_id] = interface_name

    def _resolve_interface_name(self, interface_ref: str, default_name: str = "") -> str:
        if not interface_ref:
            return default_name
        return self.interface_name_by_id.get(interface_ref, default_name or interface_ref)

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology, version_warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=['L0_meta', 'L1_foundation', 'L2_network', 'L5_application'],
            )
            print(f"OK Loaded topology: {self.topology_path}")

            if version_warning:
                print(f"WARN  {version_warning}")

            return True
        except ValueError as e:
            print(f"ERROR {e}")
            return False
        except FileNotFoundError:
            print(f"ERROR Topology file not found: {self.topology_path}")
            return False
        except Exception as e:
            print(f"ERROR Error loading topology: {e}")
            return False

    def extract_mikrotik_data(self) -> bool:
        """Extract MikroTik-relevant data from topology"""
        try:
            for device in self.topology['L1_foundation'].get('devices', []):
                if device.get('id') == 'mikrotik-chateau':
                    self.mikrotik_device = device
                    break

            if not self.mikrotik_device:
                print("ERROR MikroTik device (mikrotik-chateau) not found in L1_foundation")
                return False

            print(f"OK Found MikroTik device: {self.mikrotik_device.get('name', 'Unknown')}")

            self._extract_networks()
            self._extract_vlans()
            self._extract_lan_ports()
            self._extract_firewall_policies()
            self._extract_qos()
            self._extract_wireguard()
            self._extract_containers()
            self._extract_dns()

            return True

        except Exception as e:
            print(f"ERROR Error extracting MikroTik data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _extract_networks(self):
        """Extract networks managed by MikroTik"""
        self._build_interface_name_map()

        for network in self.topology['L2_network'].get('networks', []):
            if network.get('managed_by_ref') == 'mikrotik-chateau':
                item = dict(network)
                if item.get('vlan'):
                    item['interface_name'] = f"vlan{item['vlan']}"
                elif item.get('interface_ref'):
                    item['interface_name'] = self._resolve_interface_name(item.get('interface_ref'), default_name='bridge-lan')
                else:
                    item['interface_name'] = 'bridge-lan'
                self.networks.append(item)

        wan_network = next((n for n in self.networks if n.get('id') == 'net-wan'), None)
        if isinstance(wan_network, dict) and wan_network.get('interface_name'):
            self.wan_interface_name = wan_network['interface_name']

        lte_network = next((n for n in self.networks if n.get('id') == 'net-lte-failover'), None)
        if isinstance(lte_network, dict) and lte_network.get('interface_name'):
            self.lte_interface_name = lte_network['interface_name']

        print(f"OK Extracted {len(self.networks)} networks")

    def _extract_vlans(self):
        """Extract VLAN configurations"""
        for network in self.networks:
            vlan_id = network.get('vlan')
            if vlan_id:
                self.vlans.append({
                    'id': vlan_id,
                    'name': network.get('name', f'VLAN {vlan_id}'),
                    'network_ref': network.get('id'),
                    'cidr': network.get('cidr'),
                    'trust_zone_ref': network.get('trust_zone_ref'),
                    'untagged_ports': [],
                })

        print(f"OK Extracted {len(self.vlans)} VLANs")

    def _extract_lan_ports(self):
        """Extract LAN ports for bridge configuration"""
        for interface in self.mikrotik_device.get('interfaces', []):
            if interface.get('type') == 'ethernet' and interface.get('role') == 'lan':
                self.lan_ports.append({
                    'name': interface.get('id', '').replace('if-mikrotik-', ''),
                    'interface': interface.get('physical_name') or interface.get('name') or interface.get('id'),
                    'pvid': 1,
                    'comment': interface.get('description', ''),
                    'tagged_vlans': False,
                })

        print(f"OK Extracted {len(self.lan_ports)} LAN ports")

    def _build_firewall_address_lists(self, policies: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Build deterministic address-lists for all networks/zones referenced by firewall policies."""
        all_networks = {
            network.get('id'): network
            for network in self.topology.get('L2_network', {}).get('networks', []) or []
            if isinstance(network, dict) and network.get('id')
        }

        referenced_networks = set()
        referenced_zones = set()
        for policy in policies:
            if not isinstance(policy, dict):
                continue
            for key in ('source_network_ref', 'destination_network_ref'):
                network_ref = policy.get(key)
                if isinstance(network_ref, str) and network_ref:
                    referenced_networks.add(network_ref)
            for key in ('source_zone_ref', 'destination_zone_ref'):
                zone_ref = policy.get(key)
                if isinstance(zone_ref, str) and zone_ref:
                    referenced_zones.add(zone_ref)
            for zone_ref in policy.get('destination_zones_ref', []) or []:
                if isinstance(zone_ref, str) and zone_ref:
                    referenced_zones.add(zone_ref)

        zone_cidrs: Dict[str, set] = {}
        for network in all_networks.values():
            zone_ref = network.get('trust_zone_ref')
            cidr = network.get('cidr')
            if not isinstance(zone_ref, str) or not zone_ref:
                continue
            if not isinstance(cidr, str) or not cidr or cidr == 'dhcp':
                continue
            zone_cidrs.setdefault(zone_ref, set()).add(cidr)

        entries: List[Dict[str, str]] = []
        seen_pairs = set()
        seen_resource_names = set()

        def add_entry(list_name: str, address: str, comment: str) -> None:
            pair = (list_name, address)
            if pair in seen_pairs:
                return
            seen_pairs.add(pair)
            base_name = self._terraform_resource_name(f"addr_list_{list_name}_{address}")
            resource_name = base_name
            suffix = 2
            while resource_name in seen_resource_names:
                resource_name = f"{base_name}_{suffix}"
                suffix += 1
            seen_resource_names.add(resource_name)
            entries.append({
                'resource_name': resource_name,
                'list': list_name,
                'address': address,
                'comment': comment,
            })

        for zone_ref in sorted(referenced_zones):
            list_name = self._zone_list_name(zone_ref)
            cidrs = sorted(zone_cidrs.get(zone_ref, set()))
            if not cidrs and zone_ref == 'untrusted':
                cidrs = ['0.0.0.0/0']
            for cidr in cidrs:
                add_entry(list_name, cidr, f"Trust zone {zone_ref}")

        for network_ref in sorted(referenced_networks):
            network = all_networks.get(network_ref)
            if not isinstance(network, dict):
                continue
            cidr = network.get('cidr')
            if not isinstance(cidr, str) or not cidr or cidr == 'dhcp':
                continue
            add_entry(
                self._network_list_name(network_ref),
                cidr,
                f"Network {network_ref}",
            )

        return entries

    def _expand_firewall_policies(self, policies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Expand firewall policies into rule-ready records (including destination_zones_ref fan-out)."""
        expanded: List[Dict[str, Any]] = []

        for policy in policies:
            if not isinstance(policy, dict):
                continue

            source_list = None
            if policy.get('source_network_ref'):
                source_list = self._network_list_name(policy['source_network_ref'])
            elif policy.get('source_zone_ref'):
                source_list = self._zone_list_name(policy['source_zone_ref'])

            destination_lists: List[Any] = []
            if policy.get('destination_network_ref'):
                destination_lists = [self._network_list_name(policy['destination_network_ref'])]
            elif policy.get('destination_zone_ref'):
                destination_lists = [self._zone_list_name(policy['destination_zone_ref'])]
            else:
                for zone_ref in policy.get('destination_zones_ref', []) or []:
                    if isinstance(zone_ref, str) and zone_ref:
                        destination_lists.append(self._zone_list_name(zone_ref))
            if not destination_lists:
                destination_lists = [None]

            protocols = policy.get('protocols') or []
            protocol = protocols[0] if isinstance(protocols, list) and protocols else None
            ports = policy.get('ports') or []
            ports_csv = ",".join(str(port) for port in ports) if isinstance(ports, list) and ports else None
            connection_state = policy.get('connection_state') or []
            connection_state_csv = (
                ",".join(str(state) for state in connection_state)
                if isinstance(connection_state, list) and connection_state
                else None
            )

            for index, destination_list in enumerate(destination_lists):
                suffix = f"-dst-{index + 1}" if len(destination_lists) > 1 else ""
                effective_id = f"{policy.get('id', 'fw-policy')}{suffix}"
                expanded.append({
                    **policy,
                    'effective_id': effective_id,
                    'resource_name': effective_id.replace('-', '_'),
                    'source_address_list': source_list,
                    'destination_address_list': destination_list,
                    'protocol': protocol,
                    'ports_csv': ports_csv,
                    'connection_state_csv': connection_state_csv,
                })

        return expanded

    def _extract_firewall_policies(self):
        """Extract firewall policies"""
        policies = self.topology['L2_network'].get('firewall_policies', [])
        self.firewall_address_lists = self._build_firewall_address_lists(policies)
        self.firewall_policies = self._expand_firewall_policies(policies)

        print(
            f"OK Extracted {len(self.firewall_policies)} firewall policy rules "
            f"and {len(self.firewall_address_lists)} address-list entries"
        )

    def _extract_qos(self):
        """Extract QoS configuration"""
        qos_config = self.topology['L2_network'].get('qos', {})

        if qos_config.get('enabled'):
            self.qos = qos_config.copy()

            if 'device_limits' in self.qos:
                for limit in self.qos['device_limits']:
                    network_ref = limit.get('network_ref')
                    for net in self.networks:
                        if net.get('id') == network_ref:
                            limit['target_cidr'] = net.get('cidr')
                            break

            print(f"OK Extracted QoS config with {len(self.qos.get('queues', []))} queues")
        else:
            print("INFO  QoS is disabled in topology")

    def _extract_wireguard(self):
        """Extract WireGuard VPN configuration"""
        for network in self.networks:
            if network.get('vpn_type') == 'wireguard':
                self.wireguard = {
                    'enabled': True,
                    'port': 51820,
                    'server_ip': network.get('gateway', '10.0.200.1'),
                    'network': network.get('cidr', '10.0.200.0/24'),
                    'peers': [],
                }
                print("OK Extracted WireGuard configuration")
                return

        self.wireguard = {'enabled': False}
        print("INFO  WireGuard VPN not configured in topology")

    def _extract_containers(self):
        """Extract container configuration from services"""
        services = self.topology.get('L5_application', {}).get('services', []) or []

        self.containers = {
            'ram_limit_mb': 512,
            'services': []
        }

        def _service_target_device(service: Dict) -> str:
            runtime = service.get('runtime')
            if isinstance(runtime, dict):
                runtime_type = runtime.get('type')
                target_ref = runtime.get('target_ref')
                if runtime_type in {'docker', 'baremetal'} and isinstance(target_ref, str):
                    return target_ref
                if runtime_type == 'lxc' and isinstance(target_ref, str):
                    for lxc in self.topology.get('L4_platform', {}).get('lxc', []) or []:
                        if isinstance(lxc, dict) and lxc.get('id') == target_ref:
                            return lxc.get('device_ref', '')
                if runtime_type == 'vm' and isinstance(target_ref, str):
                    for vm in self.topology.get('L4_platform', {}).get('vms', []) or []:
                        if isinstance(vm, dict) and vm.get('id') == target_ref:
                            return vm.get('device_ref', '')
            return service.get('device_ref', '')

        for service in services:
            if not isinstance(service, dict):
                continue
            if _service_target_device(service) != 'mikrotik-chateau':
                continue
            runtime = service.get('runtime') if isinstance(service.get('runtime'), dict) else {}
            is_container = service.get('container') or runtime.get('type') == 'docker'
            if is_container:
                image = runtime.get('image') or service.get('container_image')
                self.containers['services'].append({
                    'id': service.get('id'),
                    'name': service.get('name'),
                    'image': image,
                })

        print(f"OK Extracted {len(self.containers['services'])} container configurations")

    def _extract_dns(self):
        """Extract DNS records and settings"""
        dns_config = self.topology.get('L5_application', {}).get('dns', {})

        self.dns_settings = dns_config.get('settings', {})

        for zone in dns_config.get('zones', []) or []:
            domain = zone.get('domain', 'home.local')
            for record in zone.get('records', []) or []:
                record['domain'] = domain
                self.dns_records.append(record)

        print(f"OK Extracted {len(self.dns_records)} DNS records")

    def generate_all(self) -> bool:
        """Generate all Terraform files"""
        if prepare_output_directory(self.output_dir):
            print(f"CLEAN Cleaning output directory: {self.output_dir}")

        print(f"DIR Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_file('provider.tf.j2', 'provider.tf')
        success &= self.generate_file('variables.tf.j2', 'variables.tf')
        success &= self.generate_file('interfaces.tf.j2', 'interfaces.tf')
        success &= self.generate_file('addresses.tf.j2', 'addresses.tf')
        success &= self.generate_file('dhcp.tf.j2', 'dhcp.tf')
        success &= self.generate_file('dns.tf.j2', 'dns.tf')
        success &= self.generate_file('firewall.tf.j2', 'firewall.tf')
        success &= self.generate_file('qos.tf.j2', 'qos.tf')
        success &= self.generate_file('vpn.tf.j2', 'vpn.tf')
        success &= self.generate_file('containers.tf.j2', 'containers.tf')
        success &= self.generate_file('outputs.tf.j2', 'outputs.tf')
        success &= self.generate_tfvars_example()

        # Run terraform fmt to normalize formatting
        success &= self.run_terraform_fmt()

        return success

    def run_terraform_fmt(self) -> bool:
        """Run terraform fmt to normalize file formatting"""
        import subprocess
        try:
            result = subprocess.run(
                ["terraform", "fmt"],
                cwd=str(self.output_dir),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                formatted_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
                if formatted_files and formatted_files[0]:
                    print(f"FMT Formatted {len(formatted_files)} files with terraform fmt")
                else:
                    print("FMT All files already formatted")
                return True
            else:
                print(f"WARN  terraform fmt returned non-zero: {result.stderr}")
                return True  # Non-fatal, files are still valid
        except FileNotFoundError:
            print("WARN  terraform not found in PATH, skipping fmt")
            return True  # Non-fatal
        except Exception as e:
            print(f"WARN  terraform fmt failed: {e}")
            return True  # Non-fatal

    def generate_file(self, template_name: str, output_name: str) -> bool:
        """Generate a single Terraform file from template"""
        try:
            template = self.jinja_env.get_template(template_name)

            mikrotik_mgmt_ip = '192.168.88.1'
            for network in self.networks:
                if network.get('id') == 'net-lan':
                    mikrotik_mgmt_ip = network.get('gateway', '192.168.88.1')
                    break

            context = {
                'topology_version': self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                'mikrotik_device': self.mikrotik_device,
                'mikrotik_mgmt_ip': mikrotik_mgmt_ip,
                'networks': self.networks,
                'vlans': self.vlans,
                'lan_ports': self.lan_ports,
                'firewall_policies': self.firewall_policies,
                'firewall_address_lists': self.firewall_address_lists,
                'wan_interface_name': self.wan_interface_name,
                'lte_interface_name': self.lte_interface_name,
                'lan_admin_list_name': self._network_list_name('net-lan'),
                'management_list_name': self._zone_list_name('management'),
                'qos': self.qos,
                'wireguard': self.wireguard,
                'containers': self.containers,
                'dns_records': self.dns_records,
                'dns_settings': self.dns_settings,
                'dns_domain': 'home.local',
                'dhcp_leases': self.dhcp_leases,
            }

            content = template.render(**context)

            output_file = self.output_dir / output_name
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating {output_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_tfvars_example(self) -> bool:
        """Generate terraform.tfvars.example"""
        try:
            content = """# =============================================================================
# MikroTik Terraform Variables Example
# Copy this file to terraform.tfvars and fill in your values
# DO NOT commit terraform.tfvars to version control (contains secrets)
# =============================================================================

# MikroTik Connection
mikrotik_host     = \"https://192.168.88.1:8443\"
mikrotik_username = \"terraform\"
mikrotik_password = \"YOUR_SECURE_PASSWORD\"
mikrotik_insecure = true  # Set to false with valid SSL certificate

# WireGuard VPN (generate with: wg genkey)
wireguard_private_key = \"\"

# WireGuard Peers (add your devices)
wireguard_peers = [
  # {
  #   name        = \"phone\"
  #   public_key  = \"generated_public_key_here\"
  #   allowed_ips = [\"10.0.200.10/32\"]
  #   comment     = \"My Phone\"
  # },
  # {
  #   name        = \"laptop\"
  #   public_key  = \"generated_public_key_here\"
  #   allowed_ips = [\"10.0.200.11/32\"]
  #   comment     = \"My Laptop\"
  # }
]

# Container Configuration
adguard_password  = \"\"  # bcrypt hash of admin password
tailscale_authkey = \"\"  # From Tailscale admin console
"""
            output_file = self.output_dir / "terraform.tfvars.example"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating terraform.tfvars.example: {e}")
            return False

    def print_summary(self) -> None:
        """Print generation summary."""
        print("\n" + "=" * 70)
        print("MikroTik Terraform Generation Summary")
        print("=" * 70)

        print(f"\nOK Generated Terraform configuration for MikroTik:")
        print(f"  - Device: {self.mikrotik_device.get('name', 'Unknown')}")
        print(f"  - {len(self.networks)} networks")
        print(f"  - {len(self.vlans)} VLANs")
        print(f"  - {len(self.firewall_policies)} firewall policies")
        print(f"  - {len(self.containers.get('services', []))} containers")
        print(f"  - WireGuard: {'Enabled' if self.wireguard.get('enabled') else 'Disabled'}")
        print(f"  - QoS: {'Enabled' if self.qos.get('enabled') else 'Disabled'}")

        print(f"\nOK Output directory: {self.output_dir}")

        print(f"\nWARN  Prerequisites:")
        print(f"  1. Enable REST API on MikroTik (see bootstrap/mikrotik/README.md)")
        print(f"  2. Copy terraform.tfvars.example to terraform.tfvars")
        print(f"  3. Edit terraform.tfvars with your credentials")

        print(f"\nNext steps:")
        print(f"  1. cd {self.output_dir}")
        print(f"  2. terraform init")
        print(f"  3. terraform plan")
        print(f"  4. terraform apply")


