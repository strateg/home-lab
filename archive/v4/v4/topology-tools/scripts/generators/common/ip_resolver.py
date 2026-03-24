"""
IP Resolution from topology refs.

Implements ADR-0044 IP derivation from refs pattern.
Resolves ip_refs to actual IP addresses from L2 ip_allocations and L4 workload networks.
"""

import re
from typing import Any, Dict, Optional


class IpResolver:
    """Resolves IP references from topology entities."""

    def __init__(self, topology: Dict[str, Any]):
        """Initialize resolver with loaded topology."""
        self.topology = topology
        self._build_lookup_caches()

    def _build_lookup_caches(self):
        """Build lookup caches for fast IP resolution."""
        # Cache L2 ip_allocations by host_os_ref + network_ref
        self.l2_ip_cache: Dict[str, str] = {}
        for network in self.topology.get("L2_network", {}).get("networks", []):
            network_id = network.get("id")
            for alloc in network.get("ip_allocations", []) or []:
                host_os_ref = alloc.get("host_os_ref")
                device_ref = alloc.get("device_ref")  # deprecated but still check
                ip = alloc.get("ip")
                if ip:
                    if host_os_ref:
                        # Strip CIDR notation if present
                        ip_addr = ip.split("/")[0]
                        self.l2_ip_cache[f"{host_os_ref}:{network_id}"] = ip_addr
                    if device_ref:
                        ip_addr = ip.split("/")[0]
                        self.l2_ip_cache[f"device:{device_ref}:{network_id}"] = ip_addr

        # Cache L4 LXC IPs by lxc_ref + network_ref
        self.lxc_ip_cache: Dict[str, str] = {}
        for lxc in self.topology.get("L4_platform", {}).get("lxc", []):
            lxc_id = lxc.get("id")
            for net in lxc.get("networks", []) or []:
                network_ref = net.get("network_ref")
                ip = net.get("ip")
                if network_ref and ip:
                    # Strip CIDR notation if present
                    ip_addr = ip.split("/")[0]
                    self.lxc_ip_cache[f"{lxc_id}:{network_ref}"] = ip_addr

        # Cache L4 VM IPs by vm_ref + network_ref
        self.vm_ip_cache: Dict[str, str] = {}
        for vm in self.topology.get("L4_platform", {}).get("vms", []):
            vm_id = vm.get("id")
            for net in vm.get("networks", []) or []:
                network_ref = net.get("network_ref")
                ip_config = net.get("ip_config", {})
                if isinstance(ip_config, dict):
                    ip = ip_config.get("address")
                    if network_ref and ip:
                        ip_addr = ip.split("/")[0]
                        self.vm_ip_cache[f"{vm_id}:{network_ref}"] = ip_addr

        # Cache services for service_ref resolution
        self.services_cache: Dict[str, Dict] = {}
        for service in self.topology.get("L5_application", {}).get("services", []):
            self.services_cache[service.get("id")] = service

    def resolve_ip_ref(self, ip_ref: Dict[str, str]) -> Optional[str]:
        """
        Resolve an IpRef to an IP address.

        Args:
            ip_ref: Dict with one of:
                - lxc_ref + network_ref
                - vm_ref + network_ref
                - host_os_ref + network_ref
                - service_ref (resolves via runtime target)

        Returns:
            IP address string or None if not resolvable
        """
        if not ip_ref:
            return None

        network_ref = ip_ref.get("network_ref")

        # LXC resolution
        if "lxc_ref" in ip_ref:
            lxc_ref = ip_ref["lxc_ref"]
            key = f"{lxc_ref}:{network_ref}"
            return self.lxc_ip_cache.get(key)

        # VM resolution
        if "vm_ref" in ip_ref:
            vm_ref = ip_ref["vm_ref"]
            key = f"{vm_ref}:{network_ref}"
            return self.vm_ip_cache.get(key)

        # Host OS resolution
        if "host_os_ref" in ip_ref:
            host_os_ref = ip_ref["host_os_ref"]
            key = f"{host_os_ref}:{network_ref}"
            return self.l2_ip_cache.get(key)

        # Service resolution - resolve via service's runtime
        if "service_ref" in ip_ref:
            service_ref = ip_ref["service_ref"]
            service = self.services_cache.get(service_ref)
            if service:
                runtime = service.get("runtime", {})
                target_ref = runtime.get("target_ref")
                network_binding_ref = runtime.get("network_binding_ref")
                if target_ref and network_binding_ref:
                    # Try LXC first
                    key = f"{target_ref}:{network_binding_ref}"
                    if key in self.lxc_ip_cache:
                        return self.lxc_ip_cache[key]
                    # Try VM
                    if key in self.vm_ip_cache:
                        return self.vm_ip_cache[key]
                    # Try host_os_ref pattern (for baremetal services)
                    for hos in self.topology.get("L4_platform", {}).get("host_operating_systems", []):
                        if hos.get("device_ref") == target_ref:
                            hos_key = f"{hos.get('id')}:{network_binding_ref}"
                            if hos_key in self.l2_ip_cache:
                                return self.l2_ip_cache[hos_key]

        return None

    def resolve_service_ip_refs(self, service: Dict[str, Any]) -> Dict[str, str]:
        """
        Resolve all ip_refs in a service to IP addresses.

        Args:
            service: Service dict with optional ip_refs field

        Returns:
            Dict mapping ref names to resolved IP addresses
        """
        resolved = {}
        ip_refs = service.get("ip_refs", {})

        for name, ref in ip_refs.items():
            ip = self.resolve_ip_ref(ref)
            if ip:
                resolved[name] = ip

        return resolved

    def resolve_service_url(self, service: Dict[str, Any]) -> Optional[str]:
        """
        Generate URL for service with url_derived=true.

        Args:
            service: Service dict with url_derived and runtime

        Returns:
            Generated URL or None if cannot resolve
        """
        if not service.get("url_derived"):
            return service.get("url")

        runtime = service.get("runtime", {})
        target_ref = runtime.get("target_ref")
        network_binding_ref = runtime.get("network_binding_ref")

        if not target_ref or not network_binding_ref:
            return None

        # Resolve IP from runtime target
        ip_ref = {}

        # Check if target is LXC
        if target_ref in [lxc.get("id") for lxc in self.topology.get("L4_platform", {}).get("lxc", [])]:
            ip_ref = {"lxc_ref": target_ref, "network_ref": network_binding_ref}
        # Check if target is device (baremetal)
        elif target_ref in [d.get("id") for d in self.topology.get("L1_foundation", {}).get("devices", [])]:
            # Find host OS for this device
            for hos in self.topology.get("L4_platform", {}).get("host_operating_systems", []):
                if hos.get("device_ref") == target_ref:
                    ip_ref = {"host_os_ref": hos.get("id"), "network_ref": network_binding_ref}
                    break

        ip = self.resolve_ip_ref(ip_ref)
        if not ip:
            return None

        # Determine protocol and port
        protocol = service.get("protocol", "http")
        port = service.get("url_port") or service.get("port")

        # Build URL
        if port and port not in (80, 443):
            return f"{protocol}://{ip}:{port}"
        else:
            return f"{protocol}://{ip}"

    def substitute_ip_refs(self, config: Any, resolved_refs: Dict[str, str]) -> Any:
        """
        Substitute {{ ip_refs.* }} placeholders in config with resolved IPs.

        Args:
            config: Config dict/list/string with placeholders
            resolved_refs: Dict of resolved IP addresses

        Returns:
            Config with placeholders substituted
        """
        if isinstance(config, str):
            # Replace {{ ip_refs.name }} patterns
            pattern = r"\{\{\s*ip_refs\.(\w+)\s*\}\}"

            def replacer(match):
                ref_name = match.group(1)
                return resolved_refs.get(ref_name, match.group(0))

            return re.sub(pattern, replacer, config)

        elif isinstance(config, dict):
            return {k: self.substitute_ip_refs(v, resolved_refs) for k, v in config.items()}

        elif isinstance(config, list):
            return [self.substitute_ip_refs(item, resolved_refs) for item in config]

        else:
            return config


def resolve_all_service_ips(topology: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Resolve all IP refs and URLs for all services in topology.

    Args:
        topology: Full loaded topology

    Returns:
        Dict mapping service_id to resolved data:
            {
                'service_id': {
                    'ip_refs': {'name': 'ip', ...},
                    'url': 'resolved_url',
                    'config': {...}  # with substituted IPs
                }
            }
    """
    resolver = IpResolver(topology)
    results = {}

    for service in topology.get("L5_application", {}).get("services", []):
        service_id = service.get("id")
        if not service_id:
            continue

        resolved = {
            "ip_refs": resolver.resolve_service_ip_refs(service),
            "url": resolver.resolve_service_url(service),
        }

        # Substitute IP refs in config
        if service.get("config"):
            resolved["config"] = resolver.substitute_ip_refs(
                service["config"],
                resolved["ip_refs"],  # type: ignore[arg-type]
            )

        results[service_id] = resolved

    return results
