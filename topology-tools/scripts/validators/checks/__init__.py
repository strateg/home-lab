"""Validation checks grouped by bounded context.

This package provides domain-specific validation functions for topology files.
Each module corresponds to a specific validation domain:

- storage: L1 storage slots, media registry, L3 storage references
- network: Bridges, VLANs, data/power links, firewall policies
- references: Cross-layer reference validation (L4-L7)
- foundation: File placement, device taxonomy
- governance: L0 contracts, version checks, IP conflicts
"""

from .foundation import check_device_taxonomy, check_file_placement
from .governance import check_ip_overlaps, check_l0_contracts, check_version
from .network import (
    check_bridge_refs,
    check_data_links,
    check_firewall_policy_addressability,
    check_network_refs,
    check_power_links,
    check_vlan_tags,
)
from .references import (
    check_backup_refs,
    check_certificate_refs,
    check_dns_refs,
    check_lxc_refs,
    check_security_policy_refs,
    check_service_refs,
    check_vm_refs,
)
from .storage import (
    build_l1_storage_context,
    check_device_storage_taxonomy,
    check_l1_media_inventory,
    check_l3_storage_refs,
    storage_disk_port_compatibility,
    storage_mount_port_compatibility,
)

__all__ = [
    # Foundation checks
    "check_device_taxonomy",
    "check_file_placement",
    # Governance checks
    "check_ip_overlaps",
    "check_l0_contracts",
    "check_version",
    # Network checks
    "check_bridge_refs",
    "check_data_links",
    "check_firewall_policy_addressability",
    "check_network_refs",
    "check_power_links",
    "check_vlan_tags",
    # Reference checks
    "check_backup_refs",
    "check_certificate_refs",
    "check_dns_refs",
    "check_lxc_refs",
    "check_security_policy_refs",
    "check_service_refs",
    "check_vm_refs",
    # Storage checks
    "build_l1_storage_context",
    "check_device_storage_taxonomy",
    "check_l1_media_inventory",
    "check_l3_storage_refs",
    "storage_disk_port_compatibility",
    "storage_mount_port_compatibility",
]
