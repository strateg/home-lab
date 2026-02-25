"""Improved IP Resolution with dataclasses (Phase 4).

Modern implementation of IP resolution using dataclasses for type safety
and better maintainability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class IpRef:
    """Immutable reference to an IP address in topology."""

    lxc_ref: Optional[str] = None
    vm_ref: Optional[str] = None
    host_os_ref: Optional[str] = None
    service_ref: Optional[str] = None
    network_ref: Optional[str] = None

    def __post_init__(self):
        """Validate that exactly one target ref is provided."""
        refs = [self.lxc_ref, self.vm_ref, self.host_os_ref, self.service_ref]
        ref_count = sum(1 for ref in refs if ref is not None)
        if ref_count != 1:
            raise ValueError(f"IpRef requires exactly one target ref, got {ref_count}")

    @property
    def target_type(self) -> str:
        """Get the type of target being referenced."""
        if self.lxc_ref:
            return "lxc"
        if self.vm_ref:
            return "vm"
        if self.host_os_ref:
            return "host_os"
        if self.service_ref:
            return "service"
        return "unknown"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IpRef:
        """Create IpRef from dictionary."""
        return cls(
            lxc_ref=data.get("lxc_ref"),
            vm_ref=data.get("vm_ref"),
            host_os_ref=data.get("host_os_ref"),
            service_ref=data.get("service_ref"),
            network_ref=data.get("network_ref"),
        )


@dataclass
class ResolvedIp:
    """Result of IP resolution with metadata."""

    ip: str
    source_type: str  # 'lxc', 'vm', 'host_os', 'service'
    source_id: str
    network_ref: str
    cidr: Optional[str] = None

    @property
    def ip_without_cidr(self) -> str:
        """Get IP address without CIDR notation."""
        return self.ip.split("/")[0]


@dataclass
class IpLookupCache:
    """Optimized lookup caches for IP resolution."""

    lxc_ips: Dict[str, str] = field(default_factory=dict)
    vm_ips: Dict[str, str] = field(default_factory=dict)
    host_os_ips: Dict[str, str] = field(default_factory=dict)
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def _make_key(self, target_ref: str, network_ref: str) -> str:
        """Create cache lookup key."""
        return f"{target_ref}:{network_ref}"

    def add_lxc_ip(self, lxc_ref: str, network_ref: str, ip: str) -> None:
        """Add LXC IP to cache."""
        key = self._make_key(lxc_ref, network_ref)
        self.lxc_ips[key] = ip.split("/")[0]  # Store without CIDR

    def add_vm_ip(self, vm_ref: str, network_ref: str, ip: str) -> None:
        """Add VM IP to cache."""
        key = self._make_key(vm_ref, network_ref)
        self.vm_ips[key] = ip.split("/")[0]

    def add_host_os_ip(self, host_os_ref: str, network_ref: str, ip: str) -> None:
        """Add host OS IP to cache."""
        key = self._make_key(host_os_ref, network_ref)
        self.host_os_ips[key] = ip.split("/")[0]

    def get_lxc_ip(self, lxc_ref: str, network_ref: str) -> Optional[str]:
        """Get LXC IP from cache."""
        key = self._make_key(lxc_ref, network_ref)
        return self.lxc_ips.get(key)

    def get_vm_ip(self, vm_ref: str, network_ref: str) -> Optional[str]:
        """Get VM IP from cache."""
        key = self._make_key(vm_ref, network_ref)
        return self.vm_ips.get(key)

    def get_host_os_ip(self, host_os_ref: str, network_ref: str) -> Optional[str]:
        """Get host OS IP from cache."""
        key = self._make_key(host_os_ref, network_ref)
        return self.host_os_ips.get(key)


class IpResolverV2:
    """Modern IP resolver using dataclasses and improved caching."""

    def __init__(self, topology: Dict[str, Any]):
        """Initialize resolver with topology and build caches."""
        self.topology = topology
        self.cache = IpLookupCache()
        self._build_caches()

    def _build_caches(self) -> None:
        """Build all lookup caches from topology."""
        self._build_lxc_cache()
        self._build_vm_cache()
        self._build_host_os_cache()
        self._build_service_cache()

    def _build_lxc_cache(self) -> None:
        """Build LXC IP cache from L4 platform."""
        l4 = self.topology.get("L4_platform", {})
        for lxc in l4.get("lxc", []) or []:
            if not isinstance(lxc, dict):
                continue
            lxc_id = lxc.get("id")
            if not lxc_id:
                continue
            for network in lxc.get("networks", []) or []:
                if not isinstance(network, dict):
                    continue
                network_ref = network.get("network_ref")
                ip = network.get("ip")
                if network_ref and ip:
                    self.cache.add_lxc_ip(lxc_id, network_ref, ip)

    def _build_vm_cache(self) -> None:
        """Build VM IP cache from L4 platform."""
        l4 = self.topology.get("L4_platform", {})
        for vm in l4.get("vms", []) or []:
            if not isinstance(vm, dict):
                continue
            vm_id = vm.get("id")
            if not vm_id:
                continue
            for network in vm.get("networks", []) or []:
                if not isinstance(network, dict):
                    continue
                network_ref = network.get("network_ref")
                ip_config = network.get("ip_config", {})
                if isinstance(ip_config, dict):
                    ip = ip_config.get("address")
                    if network_ref and ip:
                        self.cache.add_vm_ip(vm_id, network_ref, ip)

    def _build_host_os_cache(self) -> None:
        """Build host OS IP cache from L2 network."""
        l2 = self.topology.get("L2_network", {})
        for network in l2.get("networks", []) or []:
            if not isinstance(network, dict):
                continue
            network_id = network.get("id")
            for alloc in network.get("ip_allocations", []) or []:
                if not isinstance(alloc, dict):
                    continue
                host_os_ref = alloc.get("host_os_ref")
                ip = alloc.get("ip")
                if host_os_ref and network_id and ip:
                    self.cache.add_host_os_ip(host_os_ref, network_id, ip)

    def _build_service_cache(self) -> None:
        """Build service cache from L5 application."""
        l5 = self.topology.get("L5_application", {})
        for service in l5.get("services", []) or []:
            if not isinstance(service, dict):
                continue
            service_id = service.get("id")
            if service_id:
                self.cache.services[service_id] = service

    def resolve(self, ip_ref: IpRef) -> Optional[ResolvedIp]:
        """Resolve an IpRef to a ResolvedIp with metadata."""
        if not ip_ref.network_ref:
            return None

        # LXC resolution
        if ip_ref.lxc_ref:
            ip = self.cache.get_lxc_ip(ip_ref.lxc_ref, ip_ref.network_ref)
            if ip:
                return ResolvedIp(
                    ip=ip,
                    source_type="lxc",
                    source_id=ip_ref.lxc_ref,
                    network_ref=ip_ref.network_ref,
                )

        # VM resolution
        if ip_ref.vm_ref:
            ip = self.cache.get_vm_ip(ip_ref.vm_ref, ip_ref.network_ref)
            if ip:
                return ResolvedIp(
                    ip=ip,
                    source_type="vm",
                    source_id=ip_ref.vm_ref,
                    network_ref=ip_ref.network_ref,
                )

        # Host OS resolution
        if ip_ref.host_os_ref:
            ip = self.cache.get_host_os_ip(ip_ref.host_os_ref, ip_ref.network_ref)
            if ip:
                return ResolvedIp(
                    ip=ip,
                    source_type="host_os",
                    source_id=ip_ref.host_os_ref,
                    network_ref=ip_ref.network_ref,
                )

        # Service resolution via runtime
        if ip_ref.service_ref:
            service = self.cache.services.get(ip_ref.service_ref)
            if service:
                runtime = service.get("runtime", {})
                if isinstance(runtime, dict):
                    target_ref = runtime.get("target_ref")
                    network_binding = runtime.get("network_binding_ref")
                    if target_ref and network_binding:
                        # Try LXC
                        ip = self.cache.get_lxc_ip(target_ref, network_binding)
                        if ip:
                            return ResolvedIp(
                                ip=ip,
                                source_type="service",
                                source_id=ip_ref.service_ref,
                                network_ref=network_binding,
                            )
                        # Try VM
                        ip = self.cache.get_vm_ip(target_ref, network_binding)
                        if ip:
                            return ResolvedIp(
                                ip=ip,
                                source_type="service",
                                source_id=ip_ref.service_ref,
                                network_ref=network_binding,
                            )

        return None

    def resolve_dict(self, ip_ref_dict: Dict[str, Any]) -> Optional[ResolvedIp]:
        """Resolve from dictionary format (for backward compatibility)."""
        try:
            ip_ref = IpRef.from_dict(ip_ref_dict)
            return self.resolve(ip_ref)
        except ValueError:
            return None
