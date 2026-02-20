#!/usr/bin/env python3
"""
Diagram generation helpers for topology documentation.
"""

from datetime import datetime


class DiagramDocumentationGenerator:
    """Generate all diagram-oriented documentation pages."""

    def __init__(self, docs_generator):
        self.docs_generator = docs_generator

    @property
    def topology(self):
        return self.docs_generator.topology

    @property
    def output_dir(self):
        return self.docs_generator.output_dir

    @property
    def jinja_env(self):
        return self.docs_generator.jinja_env

    @property
    def topology_version(self):
        return self.topology.get("L0_meta", {}).get("version", "4.0.0")

    @staticmethod
    def generated_at():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def generate_all(self) -> bool:
        """Generate all diagram pages and index."""
        success = True

        # Visual diagrams (Phase 1)
        success &= self.generate_power_links_topology()
        success &= self.generate_data_links_topology()
        success &= self.generate_physical_topology()
        success &= self.generate_vlan_topology()
        success &= self.generate_trust_zones()
        success &= self.generate_service_dependencies()

        # Visual diagrams (Phase 2)
        success &= self.generate_storage_topology()
        success &= self.generate_monitoring_topology()
        success &= self.generate_vpn_topology()

        # Visual diagrams (Phase 3)
        success &= self.generate_qos_topology()
        success &= self.generate_certificates_topology()
        success &= self.generate_ups_topology()

        # Index & navigation (Phase 4)
        success &= self.generate_diagrams_index()

        return success

    @staticmethod
    def summary_items():
        return [
            "Power links topology (Mermaid)",
            "Data links topology (Mermaid)",
            "Physical topology (Mermaid)",
            "VLAN topology (Mermaid)",
            "Trust zones (Mermaid)",
            "Service dependencies (Mermaid)",
            "Storage topology (Mermaid)",
            "Monitoring topology (Mermaid)",
            "VPN topology (Mermaid)",
            "QoS topology (Mermaid)",
            "Certificates topology (Mermaid)",
            "UPS topology (Mermaid)",
        ]

    def generate_physical_topology(self) -> bool:
        """Generate physical infrastructure topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/physical-topology.md.j2")

            devices = self.topology["L1_foundation"].get("devices", [])
            locations = self.topology["L1_foundation"].get("locations", [])
            physical_links = self.topology["L1_foundation"].get("data_links", [])

            content = template.render(
                devices=devices,
                locations=locations,
                physical_links=physical_links,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "physical-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating physical-topology.md: {e}")
            return False

    def generate_data_links_topology(self) -> bool:
        """Generate data-link physical topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/data-links-topology.md.j2")

            devices = self.topology["L1_foundation"].get("devices", [])
            data_links = self.topology["L1_foundation"].get("data_links", [])
            device_map = {d.get("id"): d for d in devices if isinstance(d, dict) and d.get("id")}
            linked_device_ids = set()
            external_refs = set()
            for link in data_links:
                for endpoint_key in ("endpoint_a", "endpoint_b"):
                    endpoint = link.get(endpoint_key, {}) or {}
                    device_ref = endpoint.get("device_ref")
                    external_ref = endpoint.get("external_ref")
                    if device_ref:
                        linked_device_ids.add(device_ref)
                    if external_ref:
                        external_refs.add(external_ref)
            linked_devices = [device_map[dev_id] for dev_id in sorted(linked_device_ids) if dev_id in device_map]

            content = template.render(
                linked_devices=linked_devices,
                device_map=device_map,
                data_links=data_links,
                external_refs=sorted(external_refs),
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "data-links-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating data-links-topology.md: {e}")
            return False

    def generate_power_links_topology(self) -> bool:
        """Generate power-link physical topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/power-links-topology.md.j2")

            devices = self.topology["L1_foundation"].get("devices", [])
            power_links = self.topology["L1_foundation"].get("power_links", [])
            device_map = {d.get("id"): d for d in devices if isinstance(d, dict) and d.get("id")}

            linked_device_ids = set()
            external_refs = set()
            for link in power_links:
                for endpoint_key in ("endpoint_a", "endpoint_b"):
                    endpoint = link.get(endpoint_key, {}) or {}
                    device_ref = endpoint.get("device_ref")
                    external_ref = endpoint.get("external_ref")
                    if device_ref:
                        linked_device_ids.add(device_ref)
                    if external_ref:
                        external_refs.add(external_ref)

            linked_devices = [device_map[dev_id] for dev_id in sorted(linked_device_ids) if dev_id in device_map]

            content = template.render(
                power_links=power_links,
                linked_devices=linked_devices,
                device_map=device_map,
                external_refs=sorted(external_refs),
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "power-links-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating power-links-topology.md: {e}")
            return False

    def generate_vlan_topology(self) -> bool:
        """Generate VLAN topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/vlan-topology.md.j2")

            networks = self.docs_generator._get_resolved_networks()
            bridges = self.topology["L2_network"].get("bridges", [])

            content = template.render(
                networks=networks,
                bridges=bridges,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "vlan-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating vlan-topology.md: {e}")
            return False

    def generate_trust_zones(self) -> bool:
        """Generate trust zone security diagram."""
        try:
            template = self.jinja_env.get_template("docs/trust-zones.md.j2")

            trust_zones = self.topology["L2_network"].get("trust_zones", {})
            firewall_policies = self.topology["L2_network"].get("firewall_policies", [])
            networks = self.docs_generator._get_resolved_networks()

            content = template.render(
                trust_zones=trust_zones,
                firewall_policies=firewall_policies,
                networks=networks,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "trust-zones.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating trust-zones.md: {e}")
            return False

    def generate_service_dependencies(self) -> bool:
        """Generate service dependency diagram."""
        try:
            template = self.jinja_env.get_template("docs/service-dependencies.md.j2")

            services = self.topology.get("L5_application", {}).get("services", [])
            lxc = self.topology["L4_platform"].get("lxc", [])

            content = template.render(
                services=services,
                lxc=lxc,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "service-dependencies.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating service-dependencies.md: {e}")
            return False

    def generate_storage_topology(self) -> bool:
        """Generate storage topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/storage-topology.md.j2")

            storage = self.topology.get("L3_data", {}).get("storage", [])
            data_assets = self.topology.get("L3_data", {}).get("data_assets", [])
            devices = self.topology["L1_foundation"].get("devices", [])

            content = template.render(
                storage=storage,
                data_assets=data_assets,
                devices=devices,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "storage-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating storage-topology.md: {e}")
            return False

    def generate_monitoring_topology(self) -> bool:
        """Generate monitoring topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/monitoring-topology.md.j2")

            observability = self.topology.get("L6_observability", {})
            services = self.topology.get("L5_application", {}).get("services", [])
            healthchecks = observability.get("healthchecks", [])
            network_monitoring = observability.get("network_monitoring", [])
            alerts = observability.get("alerts", [])
            notification_channels = observability.get("notification_channels", [])
            dashboard = observability.get("dashboard", {})

            content = template.render(
                services=services,
                healthchecks=healthchecks,
                network_monitoring=network_monitoring,
                alerts=alerts,
                notification_channels=notification_channels,
                dashboard=dashboard,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "monitoring-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating monitoring-topology.md: {e}")
            return False

    def generate_vpn_topology(self) -> bool:
        """Generate VPN topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/vpn-topology.md.j2")

            networks = self.topology["L2_network"].get("networks", [])
            firewall_policies = self.topology["L2_network"].get("firewall_policies", [])
            trust_zones = self.topology["L2_network"].get("trust_zones", {})
            services = self.topology.get("L5_application", {}).get("services", [])
            devices = self.topology["L1_foundation"].get("devices", [])

            vpn_networks = [net for net in networks if net.get("vpn_type")]
            vpn_network_ids = {net["id"] for net in vpn_networks}
            vpn_services = [svc for svc in services if svc.get("type") == "vpn"]

            vpn_access = {}
            for policy in firewall_policies:
                if policy.get("action") != "accept":
                    continue
                source_network = policy.get("source_network_ref")
                if source_network not in vpn_network_ids:
                    continue

                destinations = []
                if policy.get("destination_zones_ref"):
                    destinations.extend(policy["destination_zones_ref"])
                if policy.get("destination_zone_ref"):
                    destinations.append(policy["destination_zone_ref"])
                if policy.get("destination_network_ref"):
                    destinations.append(policy["destination_network_ref"])
                if not destinations:
                    continue

                vpn_access.setdefault(source_network, set()).update(destinations)

            vpn_access_list = [
                {"network_id": net_id, "destinations": sorted(list(zones))}
                for net_id, zones in sorted(vpn_access.items())
            ]

            content = template.render(
                vpn_networks=vpn_networks,
                vpn_services=vpn_services,
                vpn_access=vpn_access_list,
                trust_zones=trust_zones,
                devices=devices,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "vpn-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating vpn-topology.md: {e}")
            return False

    def generate_qos_topology(self) -> bool:
        """Generate QoS topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/qos-topology.md.j2")

            qos = self.topology["L2_network"].get("qos", {})
            networks = self.topology["L2_network"].get("networks", [])
            devices = self.topology["L1_foundation"].get("devices", [])

            content = template.render(
                qos=qos,
                networks=networks,
                devices=devices,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "qos-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating qos-topology.md: {e}")
            return False

    def generate_certificates_topology(self) -> bool:
        """Generate certificates topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/certificates-topology.md.j2")

            certificates = self.topology.get("L5_application", {}).get("certificates", {})
            services = self.topology.get("L5_application", {}).get("services", [])
            devices = self.topology["L1_foundation"].get("devices", [])

            content = template.render(
                certificates=certificates,
                services=services,
                devices=devices,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "certificates-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating certificates-topology.md: {e}")
            return False

    def generate_ups_topology(self) -> bool:
        """Generate UPS topology diagram."""
        try:
            template = self.jinja_env.get_template("docs/ups-topology.md.j2")

            l7_power = (self.topology.get("L7_operations", {}) or {}).get("power_resilience", {}) or {}
            ups = l7_power.get("policies", []) or []
            devices = self.topology["L1_foundation"].get("devices", [])
            healthchecks = self.topology.get("L6_observability", {}).get("healthchecks", [])
            alerts = self.topology.get("L6_observability", {}).get("alerts", [])

            content = template.render(
                ups=ups,
                devices=devices,
                healthchecks=healthchecks,
                alerts=alerts,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "ups-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating ups-topology.md: {e}")
            return False

    def generate_diagrams_index(self) -> bool:
        """Generate diagrams index and navigation page."""
        try:
            template = self.jinja_env.get_template("docs/diagrams-index.md.j2")

            docs_index = {
                "core": [
                    {"title": "Infrastructure Overview", "file": "overview.md", "description": "Summary and metadata"},
                    {"title": "Network Diagram", "file": "network-diagram.md", "description": "Layered network map"},
                    {"title": "IP Allocation", "file": "ip-allocation.md", "description": "Address assignments"},
                    {"title": "Services Inventory", "file": "services.md", "description": "Service catalog"},
                    {"title": "Devices Inventory", "file": "devices.md", "description": "Hardware and platform inventory"},
                ],
                "phase1": [
                    {"title": "Power Links Topology", "file": "power-links-topology.md", "description": "Physical power cabling and feed paths"},
                    {"title": "Data Links Topology", "file": "data-links-topology.md", "description": "Physical data connectivity"},
                    {"title": "Physical Topology", "file": "physical-topology.md", "description": "Physical devices and links"},
                    {"title": "VLAN Topology", "file": "vlan-topology.md", "description": "VLAN segmentation and trunking"},
                    {"title": "Trust Zones", "file": "trust-zones.md", "description": "Security zones and firewall matrix"},
                    {"title": "Service Dependencies", "file": "service-dependencies.md", "description": "Application dependency graph"},
                ],
                "phase2": [
                    {"title": "Storage Topology", "file": "storage-topology.md", "description": "Storage pools and data assets"},
                    {"title": "Monitoring Topology", "file": "monitoring-topology.md", "description": "Observability pipeline"},
                    {"title": "VPN Topology", "file": "vpn-topology.md", "description": "Remote access and VPN scope"},
                ],
                "phase3": [
                    {"title": "QoS Topology", "file": "qos-topology.md", "description": "Traffic classes and limits"},
                    {"title": "Certificates Topology", "file": "certificates-topology.md", "description": "PKI and cert distribution"},
                    {"title": "UPS Topology", "file": "ups-topology.md", "description": "Power protection and shutdown flow"},
                ],
            }

            total_docs = sum(len(items) for items in docs_index.values())

            content = template.render(
                docs_index=docs_index,
                total_docs=total_docs,
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
            )

            output_file = self.output_dir / "diagrams-index.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating diagrams-index.md: {e}")
            return False
