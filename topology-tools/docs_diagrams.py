#!/usr/bin/env python3
"""
Diagram generation helpers for topology documentation.
"""

from datetime import datetime
from typing import Dict, List, Tuple


class DiagramDocumentationGenerator:
    """Generate all diagram-oriented documentation pages."""

    ICON_PACK_HINT = "`si` (Simple Icons) and `mdi` (Material Design Icons)"
    DEVICE_ICON_BY_TYPE = {
        "router": "si:mikrotik",
        "hypervisor": "si:proxmox",
        "cloud-vm": "mdi:cloud-outline",
        "sbc": "mdi:chip",
        "ups": "mdi:battery-high",
        "pdu": "mdi:power-socket-eu",
        "switch": "mdi:ethernet-switch",
        "ap": "mdi:access-point",
        "nas": "mdi:nas",
    }
    DEVICE_ICON_BY_CLASS = {
        "network": "mdi:router-network",
        "compute": "mdi:server",
        "storage": "mdi:database",
        "power": "mdi:flash",
    }
    ZONE_ICON_MAP = {
        "untrusted": "mdi:earth",
        "guest": "mdi:account-question",
        "user": "mdi:account-group",
        "iot": "mdi:home-automation",
        "servers": "mdi:server",
        "management": "mdi:shield-crown",
    }

    DIAGRAMS_INDEX = {
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

    def __init__(self, docs_generator):
        self.docs_generator = docs_generator
        self._generated_at = None

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

    @property
    def use_mermaid_icons(self) -> bool:
        return bool(getattr(self.docs_generator, "mermaid_icons", False))

    def generated_at(self) -> str:
        if not self._generated_at:
            self._generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self._generated_at

    @classmethod
    def summary_items(cls) -> List[str]:
        items = []
        for phase in ("phase1", "phase2", "phase3"):
            items.extend(f"{entry['title']} (Mermaid)" for entry in cls.DIAGRAMS_INDEX.get(phase, []))
        return items

    @staticmethod
    def _sort_dicts(items, key: str = "id"):
        return sorted(items or [], key=lambda item: (item.get(key, ""), item.get("name", "")))

    def _render_document(self, template_path: str, output_name: str, **context) -> bool:
        try:
            template = self.jinja_env.get_template(template_path)
            content = template.render(
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
                use_mermaid_icons=self.use_mermaid_icons,
                mermaid_icon_pack_hint=self.ICON_PACK_HINT,
                **context,
            )
            output_file = self.output_dir / output_name
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True
        except Exception as e:
            print(f"ERROR Error generating {output_name}: {e}")
            return False

    def _collect_link_graph_data(self, links_key: str) -> Tuple[List[Dict], Dict[str, Dict], List[str], List[Dict]]:
        devices = self.topology["L1_foundation"].get("devices", [])
        links = self._sort_dicts(self.topology["L1_foundation"].get(links_key, []))
        device_map = {d.get("id"): d for d in devices if isinstance(d, dict) and d.get("id")}

        linked_device_ids = set()
        external_refs = set()
        for link in links:
            for endpoint_key in ("endpoint_a", "endpoint_b"):
                endpoint = link.get(endpoint_key, {}) or {}
                device_ref = endpoint.get("device_ref")
                external_ref = endpoint.get("external_ref")
                if device_ref:
                    linked_device_ids.add(device_ref)
                if external_ref:
                    external_refs.add(external_ref)

        linked_devices = [device_map[dev_id] for dev_id in sorted(linked_device_ids) if dev_id in device_map]
        return linked_devices, device_map, sorted(external_refs), links

    def _device_icon(self, device: Dict) -> str:
        device_type = (device.get("type") or "").lower()
        if device_type in self.DEVICE_ICON_BY_TYPE:
            return self.DEVICE_ICON_BY_TYPE[device_type]
        device_class = (device.get("class") or "").lower()
        if device_class in self.DEVICE_ICON_BY_CLASS:
            return self.DEVICE_ICON_BY_CLASS[device_class]
        return "mdi:devices"

    @staticmethod
    def _external_ref_icon(ref: str) -> str:
        text = (ref or "").lower()
        if "isp" in text or "internet" in text:
            return "mdi:cloud-outline"
        if "lte" in text or "mobile" in text:
            return "mdi:signal-cellular-3"
        if "utility" in text or "grid" in text:
            return "mdi:transmission-tower"
        if "wifi" in text:
            return "mdi:wifi"
        return "mdi:help-circle-outline"

    def generate_all(self) -> bool:
        """Generate all diagram pages and index."""
        self._generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    def generate_physical_topology(self) -> bool:
        """Generate physical infrastructure topology diagram."""
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        locations = self._sort_dicts(self.topology["L1_foundation"].get("locations", []))
        physical_links = self._sort_dicts(self.topology["L1_foundation"].get("data_links", []))
        return self._render_document(
            "docs/physical-topology.md.j2",
            "physical-topology.md",
            devices=devices,
            locations=locations,
            physical_links=physical_links,
        )

    def generate_data_links_topology(self) -> bool:
        """Generate data-link physical topology diagram."""
        linked_devices, device_map, external_refs, data_links = self._collect_link_graph_data("data_links")
        device_icons = {device.get("id"): self._device_icon(device) for device in linked_devices}
        external_icons = {ref: self._external_ref_icon(ref) for ref in external_refs}
        return self._render_document(
            "docs/data-links-topology.md.j2",
            "data-links-topology.md",
            linked_devices=linked_devices,
            device_map=device_map,
            data_links=data_links,
            external_refs=external_refs,
            device_icons=device_icons,
            external_icons=external_icons,
        )

    def generate_power_links_topology(self) -> bool:
        """Generate power-link physical topology diagram."""
        linked_devices, device_map, external_refs, power_links = self._collect_link_graph_data("power_links")
        device_icons = {device.get("id"): self._device_icon(device) for device in linked_devices}
        external_icons = {ref: self._external_ref_icon(ref) for ref in external_refs}
        return self._render_document(
            "docs/power-links-topology.md.j2",
            "power-links-topology.md",
            power_links=power_links,
            linked_devices=linked_devices,
            device_map=device_map,
            external_refs=external_refs,
            device_icons=device_icons,
            external_icons=external_icons,
        )

    def generate_vlan_topology(self) -> bool:
        """Generate VLAN topology diagram."""
        networks = self._sort_dicts(self.docs_generator._get_resolved_networks())
        bridges = self._sort_dicts(self.topology["L2_network"].get("bridges", []))
        return self._render_document(
            "docs/vlan-topology.md.j2",
            "vlan-topology.md",
            networks=networks,
            bridges=bridges,
        )

    def generate_trust_zones(self) -> bool:
        """Generate trust zone security diagram."""
        trust_zones = self.topology["L2_network"].get("trust_zones", {})
        firewall_policies = sorted(
            self.topology["L2_network"].get("firewall_policies", []),
            key=lambda policy: (policy.get("priority", 999999), policy.get("id", "")),
        )
        firewall_policy_map = {
            policy.get("id"): policy for policy in firewall_policies
            if isinstance(policy, dict) and policy.get("id")
        }
        networks = self._sort_dicts(self.docs_generator._get_resolved_networks())

        network_policy_bindings = []
        for network in networks:
            refs = network.get("firewall_policy_refs") or []
            if not refs:
                continue
            names = []
            for ref in refs:
                policy = firewall_policy_map.get(ref, {})
                names.append(policy.get("name", ref))
            network_policy_bindings.append(
                {
                    "network_id": network.get("id"),
                    "network_name": network.get("name", network.get("id")),
                    "trust_zone_ref": network.get("trust_zone_ref"),
                    "policy_refs": refs,
                    "policy_names": names,
                }
            )

        return self._render_document(
            "docs/trust-zones.md.j2",
            "trust-zones.md",
            trust_zones=trust_zones,
            firewall_policies=firewall_policies,
            networks=networks,
            firewall_policy_map=firewall_policy_map,
            network_policy_bindings=network_policy_bindings,
            zone_icons=self.ZONE_ICON_MAP,
        )

    def generate_service_dependencies(self) -> bool:
        """Generate service dependency diagram."""
        services = self._sort_dicts(self.topology.get("L5_application", {}).get("services", []))
        lxc = self._sort_dicts(self.topology["L4_platform"].get("lxc", []))
        return self._render_document(
            "docs/service-dependencies.md.j2",
            "service-dependencies.md",
            services=services,
            lxc=lxc,
        )

    def generate_storage_topology(self) -> bool:
        """Generate storage topology diagram."""
        storage = self._sort_dicts(self.topology.get("L3_data", {}).get("storage", []))
        data_assets = self._sort_dicts(self.topology.get("L3_data", {}).get("data_assets", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        return self._render_document(
            "docs/storage-topology.md.j2",
            "storage-topology.md",
            storage=storage,
            data_assets=data_assets,
            devices=devices,
        )

    def generate_monitoring_topology(self) -> bool:
        """Generate monitoring topology diagram."""
        observability = self.topology.get("L6_observability", {})
        services = self._sort_dicts(self.topology.get("L5_application", {}).get("services", []))
        healthchecks = self._sort_dicts(observability.get("healthchecks", []))
        network_monitoring = self._sort_dicts(observability.get("network_monitoring", []))
        alerts = self._sort_dicts(observability.get("alerts", []))
        notification_channels = self._sort_dicts(observability.get("notification_channels", []))
        dashboard = observability.get("dashboard", {})
        return self._render_document(
            "docs/monitoring-topology.md.j2",
            "monitoring-topology.md",
            services=services,
            healthchecks=healthchecks,
            network_monitoring=network_monitoring,
            alerts=alerts,
            notification_channels=notification_channels,
            dashboard=dashboard,
        )

    def generate_vpn_topology(self) -> bool:
        """Generate VPN topology diagram."""
        networks = self._sort_dicts(self.topology["L2_network"].get("networks", []))
        firewall_policies = self._sort_dicts(self.topology["L2_network"].get("firewall_policies", []))
        trust_zones = self.topology["L2_network"].get("trust_zones", {})
        services = self._sort_dicts(self.topology.get("L5_application", {}).get("services", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))

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

        return self._render_document(
            "docs/vpn-topology.md.j2",
            "vpn-topology.md",
            vpn_networks=vpn_networks,
            vpn_services=vpn_services,
            vpn_access=vpn_access_list,
            trust_zones=trust_zones,
            devices=devices,
        )

    def generate_qos_topology(self) -> bool:
        """Generate QoS topology diagram."""
        qos = self.topology["L2_network"].get("qos", {})
        networks = self._sort_dicts(self.topology["L2_network"].get("networks", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        return self._render_document(
            "docs/qos-topology.md.j2",
            "qos-topology.md",
            qos=qos,
            networks=networks,
            devices=devices,
        )

    def generate_certificates_topology(self) -> bool:
        """Generate certificates topology diagram."""
        certificates = self.topology.get("L5_application", {}).get("certificates", {})
        services = self._sort_dicts(self.topology.get("L5_application", {}).get("services", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        return self._render_document(
            "docs/certificates-topology.md.j2",
            "certificates-topology.md",
            certificates=certificates,
            services=services,
            devices=devices,
        )

    def generate_ups_topology(self) -> bool:
        """Generate UPS topology diagram."""
        l7_power = (self.topology.get("L7_operations", {}) or {}).get("power_resilience", {}) or {}
        ups = self._sort_dicts(l7_power.get("policies", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        healthchecks = self._sort_dicts(self.topology.get("L6_observability", {}).get("healthchecks", []))
        alerts = self._sort_dicts(self.topology.get("L6_observability", {}).get("alerts", []))
        return self._render_document(
            "docs/ups-topology.md.j2",
            "ups-topology.md",
            ups=ups,
            devices=devices,
            healthchecks=healthchecks,
            alerts=alerts,
        )

    def generate_diagrams_index(self) -> bool:
        """Generate diagrams index and navigation page."""
        docs_index = self.DIAGRAMS_INDEX
        total_docs = sum(len(items) for items in docs_index.values())
        return self._render_document(
            "docs/diagrams-index.md.j2",
            "diagrams-index.md",
            docs_index=docs_index,
            total_docs=total_docs,
        )
