"""Type definitions for topology v4.0 layered structure."""

from typing import Any, Dict, List, Literal, Optional, TypedDict


class L0Meta(TypedDict, total=False):
    """L0 Meta layer: version, defaults, global policies."""

    version: str
    metadata: Dict[str, Any]
    defaults: Dict[str, Any]
    security_policy: List[Dict[str, Any]]


class L1Foundation(TypedDict, total=False):
    """L1 Foundation layer: devices, interfaces, MACs, storage, links."""

    locations: Dict[str, Any]
    devices: Dict[str, Any]
    media_registry: Optional[Dict[str, Any]]
    media_attachments: Optional[Dict[str, Any]]
    data_links: Optional[Dict[str, Any]]
    power_links: Optional[Dict[str, Any]]


class L2Network(TypedDict, total=False):
    """L2 Network layer: networks, bridges, trust zones, firewall."""

    networks: Dict[str, Any]
    bridges: Optional[Dict[str, Any]]
    trust_zones: Optional[Dict[str, Any]]
    firewall: Optional[Dict[str, Any]]


class L3Compute(TypedDict, total=False):
    """L3 Data layer: storage, data assets, logical disk mappings.

    Note: Named L3Compute to avoid confusion with 'data' but represents L3 Data layer.
    """

    storage: Optional[Dict[str, Any]]
    data_assets: Optional[Dict[str, Any]]
    partitions: Optional[Dict[str, Any]]
    volume_groups: Optional[Dict[str, Any]]
    logical_volumes: Optional[Dict[str, Any]]
    filesystems: Optional[Dict[str, Any]]
    mount_points: Optional[Dict[str, Any]]
    storage_endpoints: Optional[Dict[str, Any]]


class L4Platform(TypedDict, total=False):
    """L4 Platform layer: VMs, LXC, templates."""

    vms: Optional[Dict[str, Any]]
    lxc: Optional[Dict[str, Any]]
    templates: Optional[Dict[str, Any]]
    runtimes: Optional[Dict[str, Any]]
    resource_profiles: Optional[Dict[str, Any]]


class L5Security(TypedDict, total=False):
    """L5 Application layer: services, ports, certificates, DNS.

    Note: Named L5Security but represents L5 Application layer.
    """

    services: Optional[Dict[str, Any]]
    ports: Optional[Dict[str, Any]]
    certificates: Optional[Dict[str, Any]]
    dns_records: Optional[Dict[str, Any]]


class L6Governance(TypedDict, total=False):
    """L6 Observability layer: monitoring, alerts, dashboards."""

    monitoring: Optional[Dict[str, Any]]
    alerts: Optional[Dict[str, Any]]
    dashboards: Optional[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]]


class L7Operations(TypedDict, total=False):
    """L7 Operations layer: workflows, runbooks, docs, backups."""

    workflows: Optional[Dict[str, Any]]
    runbooks: Optional[Dict[str, Any]]
    documentation: Optional[Dict[str, Any]]
    backups: Optional[Dict[str, Any]]
    power_policies: Optional[Dict[str, Any]]


class TopologyV4Structure(TypedDict):
    """Complete topology v4.0 structure with all layers."""

    L0_meta: L0Meta
    L1_foundation: L1Foundation
    L2_network: L2Network
    L3_data: L3Compute  # Named L3Compute in types, but key is L3_data
    L4_platform: L4Platform
    L5_application: L5Security  # Named L5Security in types, but key is L5_application
    L6_observability: L6Governance  # Named L6Governance in types, but key is L6_observability
    L7_operations: L7Operations


# Alias types for better semantics
L3Data = L3Compute
L5Application = L5Security
L6Observability = L6Governance
