#!/usr/bin/env python3
"""
Diagram generation helpers for topology documentation.
"""

from datetime import datetime
from typing import Dict, List, Tuple


class DiagramDocumentationGenerator:
    """Generate all diagram-oriented documentation pages."""

    ICON_PACK_HINT = "`si` (Simple Icons) and `mdi` (Material Design Icons)"

    # Icon-node rendering defaults (Mermaid @{ ... } syntax)
    ICON_NODE_DEFAULTS = {
        "form": "rounded",
        "pos": "b",
        "h": 46,
    }
    ICON_NODE_CIRCLE = {"form": "circle", "pos": "b", "h": 42}

    # Locations considered cloud (for template logic)
    CLOUD_LOCATIONS = frozenset({"oracle-frankfurt", "hetzner-nuremberg", "aws-eu-west-1", "gcp-europe-west1"})

    DEVICE_ICON_BY_TYPE = {
        "hypervisor": "si:proxmox",
        "router": "mdi:router-network",
        "sbc": "mdi:chip",
        "switch": "mdi:switch",
        "ap": "mdi:access-point",
        "nas": "mdi:nas",
        "cloud-vm": "mdi:cloud-outline",
        "ups": "mdi:battery-charging-high",  # Consistent with POWER_ICONS
        "pdu": "mdi:power-socket-eu",
        "firewall": "mdi:wall-fire",
        "load-balancer": "mdi:scale-balance",
        "container-host": "mdi:docker",
        "workstation": "mdi:desktop-tower-monitor",
        "laptop": "mdi:laptop",
        "phone": "mdi:cellphone",
        "iot-device": "mdi:home-automation",
    }
    DEVICE_ICON_BY_CLASS = {
        "network": "mdi:router-network",
        "compute": "mdi:server",
        "storage": "mdi:database",
        "power": "mdi:flash",
        "external": "mdi:cloud-outline",
    }
    CLOUD_PROVIDER_ICON = {
        "oracle": "si:oracle",
        "hetzner": "si:hetzner",
        "aws": "si:amazonaws",
        "gcp": "si:googlecloud",
        "azure": "si:microsoftazure",
        "digitalocean": "si:digitalocean",
    }
    ZONE_ICON_MAP = {
        "untrusted": "mdi:earth",
        "guest": "mdi:account-question",
        "user": "mdi:account-group",
        "iot": "mdi:home-automation",
        "servers": "mdi:server",
        "management": "mdi:shield-crown",
    }
    NETWORK_ICON_BY_ZONE = {
        "untrusted": "mdi:earth",
        "guest": "mdi:wifi-strength-1-alert",
        "user": "mdi:lan",
        "iot": "mdi:lan-pending",
        "servers": "mdi:server-network",
        "management": "mdi:shield-crown",
    }
    SERVICE_ICON_BY_TYPE = {
        "database": "mdi:database",
        "cache": "mdi:database-clock",
        "web-application": "mdi:web",
        "web-ui": "mdi:view-dashboard",
        "media-server": "mdi:multimedia",
        "monitoring": "mdi:chart-line",
        "alerting": "mdi:bell-alert",
        "logging": "mdi:file-document-outline",
        "visualization": "mdi:chart-areaspline",
        "dns": "mdi:dns",
        "vpn": "mdi:vpn",
    }
    STORAGE_POOL_ICON_BY_MEDIA = {
        "nvme": "mdi:memory",
        "ssd": "mdi:harddisk",
        "hdd": "mdi:harddisk-plus",
    }
    DATA_ASSET_ICON_BY_TYPE = {
        "backup": "mdi:backup-restore",
        "database": "mdi:database",
        "media": "mdi:folder-music",
        "config": "mdi:file-cog-outline",
        "logs": "mdi:file-document-outline",
    }
    ALERT_ICON_BY_SEVERITY = {
        "critical": "mdi:alert-octagon",
        "high": "mdi:alert",
        "warning": "mdi:alert-outline",
        "info": "mdi:information-outline",
    }
    CHANNEL_ICON_BY_TYPE = {
        "telegram": "mdi:send",
        "email": "mdi:email-outline",
        "webhook": "mdi:webhook",
        "slack": "si:slack",
        "discord": "si:discord",
    }
    EXTERNAL_LEGEND_SAMPLES = [
        "isp-uplink",
        "mobile-operator-lte",
        "wifi-clients-5ghz",
        "utility-grid-home",
        "external-service",
    ]

    # Power-related icons (consistent set)
    POWER_ICONS = {
        "ups": "mdi:battery-charging-high",
        "pdu": "mdi:power-socket-eu",
        "utility-grid": "mdi:transmission-tower",
        "battery": "mdi:battery-high",
        "solar": "mdi:solar-power",
        "generator": "mdi:engine",
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
            {"title": "Icon Legend", "file": "icon-legend.md", "description": "Icon mapping used in professional diagrams"},
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

    @classmethod
    def is_cloud_location(cls, location: str) -> bool:
        """Check if location is a cloud provider location."""
        return (location or "").lower() in cls.CLOUD_LOCATIONS

    @staticmethod
    def _icon_for(entity: dict, type_key: str, mapping: dict, default: str) -> str:
        """Unified icon lookup: get type from entity, lookup in mapping, fallback to default."""
        if not isinstance(entity, dict):
            return default
        entity_type = (entity.get(type_key) or "").lower()
        return mapping.get(entity_type, default)

    def _render_document(self, template_path: str, output_name: str, **context) -> bool:
        try:
            template = self.jinja_env.get_template(template_path)
            content = template.render(
                topology_version=self.topology_version,
                generated_at=self.generated_at(),
                use_mermaid_icons=self.use_mermaid_icons,
                icon_mode=getattr(self.docs_generator, "icon_mode", "none"),
                mermaid_icon_runtime_hint=self.docs_generator.icon_runtime_hint(),
                mermaid_icon_pack_hint=self.ICON_PACK_HINT,
                # Icon-node styling constants (available in all templates)
                icon_node_defaults=self.ICON_NODE_DEFAULTS,
                icon_node_circle=self.ICON_NODE_CIRCLE,
                **context,
            )
            content = self.docs_generator.transform_mermaid_icons_for_compat(content)
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
        device_id = (device.get("id") or "").lower()
        device_type = (device.get("type") or "").lower()
        device_model = (device.get("model") or "").lower()

        # Provider-specific cloud icons look better than generic cloud nodes.
        cloud = device.get("cloud") or {}
        provider = (cloud.get("provider") or "").lower()
        if device_type == "cloud-vm" and provider in self.CLOUD_PROVIDER_ICON:
            return self.CLOUD_PROVIDER_ICON[provider]

        # Local vendor hints.
        if "mikrotik" in device_id or "mikrotik" in device_model:
            return "si:mikrotik"
        if "proxmox" in device_model:
            return "si:proxmox"
        if "openwrt" in device_model or "gl-inet" in device_model:
            return "si:openwrt"

        if device_type in self.DEVICE_ICON_BY_TYPE:
            return self.DEVICE_ICON_BY_TYPE[device_type]
        device_class = (device.get("class") or "").lower()
        if device_class in self.DEVICE_ICON_BY_CLASS:
            return self.DEVICE_ICON_BY_CLASS[device_class]
        return "mdi:devices"

    @classmethod
    def _external_ref_icon(cls, ref: str) -> str:
        text = (ref or "").lower()
        if "isp" in text or "internet" in text:
            return "mdi:cloud-outline"
        if "lte" in text or "mobile" in text:
            return "mdi:signal-cellular-3"
        # Power-related external refs use consistent POWER_ICONS
        if "utility" in text or "grid" in text:
            return cls.POWER_ICONS["utility-grid"]
        if "ups" in text or "battery" in text:
            return cls.POWER_ICONS["ups"]
        if "solar" in text:
            return cls.POWER_ICONS["solar"]
        if "generator" in text:
            return cls.POWER_ICONS["generator"]
        if "wifi" in text:
            return "mdi:wifi"
        if "vpn" in text:
            return "mdi:vpn"
        if "oracle" in text:
            return "si:oracle"
        if "hetzner" in text:
            return "si:hetzner"
        return "mdi:help-circle-outline"

    def _network_icon(self, network: Dict) -> str:
        if not isinstance(network, dict):
            return "mdi:lan"
        zone = (network.get("trust_zone_ref") or "").lower()
        if zone in self.NETWORK_ICON_BY_ZONE:
            return self.NETWORK_ICON_BY_ZONE[zone]
        if network.get("vpn_type"):
            return "mdi:vpn"
        if network.get("vlan"):
            return "mdi:lan-connect"
        return "mdi:lan"

    def _service_icon(self, service: Dict) -> str:
        if not isinstance(service, dict):
            return "mdi:application-cog-outline"
        service_type = (service.get("type") or "").lower()
        if service_type in self.SERVICE_ICON_BY_TYPE:
            return self.SERVICE_ICON_BY_TYPE[service_type]
        if service.get("vpn_type"):
            return "mdi:vpn"
        return "mdi:application-cog-outline"

    def _storage_pool_icon(self, pool: Dict) -> str:
        if not isinstance(pool, dict):
            return "mdi:database"
        media = (pool.get("media") or "").lower()
        if media in self.STORAGE_POOL_ICON_BY_MEDIA:
            return self.STORAGE_POOL_ICON_BY_MEDIA[media]
        pool_type = (pool.get("type") or "").lower()
        if "nfs" in pool_type or "smb" in pool_type:
            return "mdi:folder-network-outline"
        if "backup" in pool_type:
            return "mdi:backup-restore"
        return "mdi:database"

    def _data_asset_icon(self, asset: Dict) -> str:
        return self._icon_for(asset, "type", self.DATA_ASSET_ICON_BY_TYPE, "mdi:file-outline")

    def _alert_icon(self, alert: Dict) -> str:
        return self._icon_for(alert, "severity", self.ALERT_ICON_BY_SEVERITY, "mdi:alert-circle-outline")

    def _channel_icon(self, channel: Dict) -> str:
        return self._icon_for(channel, "type", self.CHANNEL_ICON_BY_TYPE, "mdi:message-alert-outline")

    def generate_all(self) -> bool:
        """Generate all diagram pages and index."""
        self._generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        success = True

        # Visual diagrams (Phase 1)
        success &= self.generate_power_links_topology()
        success &= self.generate_data_links_topology()
        success &= self.generate_icon_legend()
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
        device_icons = {device.get("id"): self._device_icon(device) for device in devices if device.get("id")}
        external_refs = sorted(
            {
                endpoint.get("external_ref")
                for link in physical_links
                for endpoint in [link.get("endpoint_a", {}) or {}, link.get("endpoint_b", {}) or {}]
                if endpoint.get("external_ref")
            }
        )
        external_icons = {ref: self._external_ref_icon(ref) for ref in external_refs}
        # Precompute cloud device IDs for template (avoids hardcoded location checks)
        cloud_device_ids = {
            device.get("id")
            for device in devices
            if device.get("id") and self.is_cloud_location(device.get("location", ""))
        }
        return self._render_document(
            "docs/physical-topology.md.j2",
            "physical-topology.md",
            devices=devices,
            locations=locations,
            physical_links=physical_links,
            device_icons=device_icons,
            external_refs=external_refs,
            external_icons=external_icons,
            cloud_device_ids=cloud_device_ids,
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
        network_icons = {network.get("id"): self._network_icon(network) for network in networks if network.get("id")}
        return self._render_document(
            "docs/vlan-topology.md.j2",
            "vlan-topology.md",
            networks=networks,
            bridges=bridges,
            network_icons=network_icons,
        )

    def generate_icon_legend(self) -> bool:
        """Generate icon legend used across professional Mermaid diagrams."""
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        trust_zones = self.topology["L2_network"].get("trust_zones", {})

        device_type_entries = []
        observed_types = {device.get("type") for device in devices if device.get("type")}
        for device_type in sorted(observed_types):
            icon = self.DEVICE_ICON_BY_TYPE.get(device_type, "mdi:devices")
            device_type_entries.append({"label": device_type, "icon": icon})

        for device_type, icon in sorted(self.DEVICE_ICON_BY_TYPE.items()):
            if device_type not in observed_types:
                device_type_entries.append({"label": device_type, "icon": icon})

        observed_providers = {
            (device.get("cloud") or {}).get("provider")
            for device in devices
            if isinstance(device, dict)
        }
        provider_entries = [
            {"label": provider, "icon": self.CLOUD_PROVIDER_ICON.get(provider, "mdi:cloud-outline")}
            for provider in sorted(provider for provider in observed_providers if provider)
        ]

        zone_entries = []
        for zone_id in sorted(trust_zones.keys()):
            zone_entries.append({"label": zone_id, "icon": self.ZONE_ICON_MAP.get(zone_id, "mdi:shield-outline")})

        external_entries = []
        for ref in self.EXTERNAL_LEGEND_SAMPLES:
            external_entries.append({"label": ref, "icon": self._external_ref_icon(ref)})

        return self._render_document(
            "docs/icon-legend.md.j2",
            "icon-legend.md",
            device_type_entries=device_type_entries,
            provider_entries=provider_entries,
            zone_entries=zone_entries,
            external_entries=external_entries,
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
        service_icons = {service.get("id"): self._service_icon(service) for service in services if service.get("id")}
        return self._render_document(
            "docs/service-dependencies.md.j2",
            "service-dependencies.md",
            services=services,
            lxc=lxc,
            service_icons=service_icons,
        )

    def generate_storage_topology(self) -> bool:
        """Generate storage topology diagram."""
        storage = self._sort_dicts(self.topology.get("L3_data", {}).get("storage", []))
        data_assets = self._sort_dicts(self.topology.get("L3_data", {}).get("data_assets", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        device_icons = {device.get("id"): self._device_icon(device) for device in devices if device.get("id")}
        pool_icons = {pool.get("id"): self._storage_pool_icon(pool) for pool in storage if pool.get("id")}
        asset_icons = {asset.get("id"): self._data_asset_icon(asset) for asset in data_assets if asset.get("id")}
        return self._render_document(
            "docs/storage-topology.md.j2",
            "storage-topology.md",
            storage=storage,
            data_assets=data_assets,
            devices=devices,
            device_icons=device_icons,
            pool_icons=pool_icons,
            asset_icons=asset_icons,
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
        service_icons = {service.get("id"): self._service_icon(service) for service in services if service.get("id")}
        healthcheck_icons = {hc.get("id"): "mdi:stethoscope" for hc in healthchecks if hc.get("id")}
        network_monitoring_icons = {nm.get("id"): "mdi:lan-check" for nm in network_monitoring if nm.get("id")}
        alert_icons = {alert.get("id"): self._alert_icon(alert) for alert in alerts if alert.get("id")}
        channel_icons = {
            channel.get("id"): self._channel_icon(channel)
            for channel in notification_channels
            if channel.get("id")
        }
        return self._render_document(
            "docs/monitoring-topology.md.j2",
            "monitoring-topology.md",
            services=services,
            healthchecks=healthchecks,
            network_monitoring=network_monitoring,
            alerts=alerts,
            notification_channels=notification_channels,
            dashboard=dashboard,
            service_icons=service_icons,
            healthcheck_icons=healthcheck_icons,
            network_monitoring_icons=network_monitoring_icons,
            alert_icons=alert_icons,
            channel_icons=channel_icons,
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
        vpn_service_icons = {svc.get("id"): self._service_icon(svc) for svc in vpn_services if svc.get("id")}
        vpn_network_icons = {net.get("id"): self._network_icon(net) for net in vpn_networks if net.get("id")}

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
            vpn_service_icons=vpn_service_icons,
            vpn_network_icons=vpn_network_icons,
            zone_icons=self.ZONE_ICON_MAP,
        )

    def generate_qos_topology(self) -> bool:
        """Generate QoS topology diagram."""
        qos = self.topology["L2_network"].get("qos", {})
        networks = self._sort_dicts(self.topology["L2_network"].get("networks", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        network_map = {network.get("id"): network for network in networks if network.get("id")}
        limit_icons = {}
        for limit in qos.get("device_limits", []) or []:
            network_ref = limit.get("network_ref")
            if not network_ref:
                continue
            limit_icons[network_ref] = self._network_icon(network_map.get(network_ref, {}))
        return self._render_document(
            "docs/qos-topology.md.j2",
            "qos-topology.md",
            qos=qos,
            networks=networks,
            devices=devices,
            limit_icons=limit_icons,
        )

    def generate_certificates_topology(self) -> bool:
        """Generate certificates topology diagram."""
        certificates = self.topology.get("L5_application", {}).get("certificates", {})
        services = self._sort_dicts(self.topology.get("L5_application", {}).get("services", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        service_icons = {service.get("id"): self._service_icon(service) for service in services if service.get("id")}
        cert_icons = {}
        for cert in certificates.get("certificates", []) or []:
            cert_id = cert.get("id")
            if cert_id:
                cert_icons[cert_id] = "mdi:certificate-outline"
        for cert in certificates.get("additional", []) or []:
            cert_id = cert.get("id")
            if not cert_id:
                continue
            if (cert.get("type") or "").lower() == "self-signed":
                cert_icons[cert_id] = "mdi:certificate"
            else:
                cert_icons[cert_id] = "mdi:certificate-outline"
        device_map = {device.get("id"): device for device in devices if device.get("id")}
        distribution_icons = {}
        for node in certificates.get("local_ca", {}).get("distribution", []) or []:
            device_ref = node.get("device_ref")
            if not device_ref:
                continue
            distribution_icons[device_ref] = self._device_icon(device_map.get(device_ref, {"id": device_ref}))
        return self._render_document(
            "docs/certificates-topology.md.j2",
            "certificates-topology.md",
            certificates=certificates,
            services=services,
            devices=devices,
            service_icons=service_icons,
            cert_icons=cert_icons,
            distribution_icons=distribution_icons,
        )

    def generate_ups_topology(self) -> bool:
        """Generate UPS topology diagram."""
        l7_power = (self.topology.get("L7_operations", {}) or {}).get("power_resilience", {}) or {}
        ups = self._sort_dicts(l7_power.get("policies", []))
        devices = self._sort_dicts(self.topology["L1_foundation"].get("devices", []))
        healthchecks = self._sort_dicts(self.topology.get("L6_observability", {}).get("healthchecks", []))
        alerts = self._sort_dicts(self.topology.get("L6_observability", {}).get("alerts", []))
        device_map = {device.get("id"): device for device in devices if device.get("id")}
        protected_device_icons = {}
        for unit in ups:
            for protected_device in unit.get("protected_devices", []) or []:
                device_ref = protected_device.get("device_ref")
                if not device_ref:
                    continue
                protected_device_icons[device_ref] = self._device_icon(
                    device_map.get(device_ref, {"id": device_ref})
                )
        return self._render_document(
            "docs/ups-topology.md.j2",
            "ups-topology.md",
            ups=ups,
            devices=devices,
            healthchecks=healthchecks,
            alerts=alerts,
            protected_device_icons=protected_device_icons,
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
