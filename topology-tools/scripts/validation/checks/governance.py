"""Governance and global consistency checks."""

from datetime import datetime
from typing import Any, Dict, List, Set


def check_l0_contracts(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Validate L0 governance fields and cross-layer defaults."""
    l0 = topology.get('L0_meta', {}) or {}
    metadata = l0.get('metadata', {}) or {}
    defaults = l0.get('defaults', {}) or {}
    refs_defaults = defaults.get('refs', {}) or {}
    version = l0.get('version')

    created = metadata.get('created')
    last_updated = metadata.get('last_updated')
    if isinstance(created, str) and isinstance(last_updated, str):
        try:
            created_dt = datetime.strptime(created, '%Y-%m-%d').date()
            updated_dt = datetime.strptime(last_updated, '%Y-%m-%d').date()
            if updated_dt < created_dt:
                errors.append(
                    f"L0_meta.metadata.last_updated '{last_updated}' is earlier than created '{created}'"
                )
        except ValueError:
            warnings.append(
                "L0_meta.metadata.created/last_updated should use YYYY-MM-DD format"
            )

    changelog = metadata.get('changelog', []) or []
    if version and changelog:
        has_version = any(
            isinstance(entry, dict) and entry.get('version') == version
            for entry in changelog
        )
        if not has_version:
            warnings.append(
                f"L0_meta.metadata.changelog does not contain current version '{version}'"
            )

    default_sec_ref = refs_defaults.get('security_policy_ref')
    if default_sec_ref and default_sec_ref not in ids['security_policies']:
        errors.append(
            f"L0_meta.defaults.refs.security_policy_ref '{default_sec_ref}' does not exist"
        )

    default_mgr_ref = refs_defaults.get('network_manager_device_ref')
    if default_mgr_ref:
        l1_devices = topology.get('L1_foundation', {}).get('devices', []) or []
        device_map = {
            d.get('id'): d for d in l1_devices
            if isinstance(d, dict) and d.get('id')
        }
        if default_mgr_ref not in ids['devices']:
            errors.append(
                f"L0_meta.defaults.refs.network_manager_device_ref '{default_mgr_ref}' does not exist"
            )
        else:
            mgr_class = (device_map.get(default_mgr_ref) or {}).get('class')
            if mgr_class != 'network':
                errors.append(
                    f"L0_meta.defaults.refs.network_manager_device_ref '{default_mgr_ref}' "
                    "must reference class 'network' device"
                )


def check_version(
    topology: Dict[str, Any],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check topology version compatibility."""
    version = topology.get('L0_meta', {}).get('version', '')
    if not version:
        warnings.append("No version specified in L0_meta")
        return

    if not version.startswith('4.'):
        errors.append(f"Unsupported topology version: {version} (expected 4.x)")


def check_ip_overlaps(
    topology: Dict[str, Any],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check for duplicate/overlapping IP addresses."""
    ip_allocations = {}
    global_ips = {}

    for network in topology.get('L2_network', {}).get('networks', []) or []:
        net_id = network.get('id', 'unknown')
        ip_allocations[net_id] = {}

        for alloc in network.get('ip_allocations', []) or []:
            ip = alloc.get('ip', '')
            device_ref = alloc.get('device_ref') or alloc.get('vm_ref') or alloc.get('lxc_ref') or 'unknown'
            ip_addr = ip.split('/')[0] if ip else ''
            if not ip_addr:
                continue

            if ip_addr in ip_allocations[net_id]:
                existing = ip_allocations[net_id][ip_addr]
                errors.append(
                    f"Duplicate IP in network '{net_id}': {ip_addr} assigned to both "
                    f"'{existing}' and '{device_ref}'"
                )
            else:
                ip_allocations[net_id][ip_addr] = device_ref

            if ip_addr not in global_ips:
                global_ips[ip_addr] = []
            global_ips[ip_addr].append((net_id, device_ref))

    for lxc in topology.get('L4_platform', {}).get('lxc', []) or []:
        lxc_id = lxc.get('id', 'unknown')
        for net in lxc.get('networks', []) or []:
            ip = net.get('ip', '')
            ip_addr = ip.split('/')[0] if ip else ''
            if ip_addr:
                global_ips.setdefault(ip_addr, []).append(('lxc-config', lxc_id))

    for vm in topology.get('L4_platform', {}).get('vms', []) or []:
        vm_id = vm.get('id', 'unknown')
        for net in vm.get('networks', []) or []:
            ip_config = net.get('ip_config', {})
            if isinstance(ip_config, dict):
                ip = ip_config.get('address', '')
                ip_addr = ip.split('/')[0] if ip else ''
                if ip_addr:
                    global_ips.setdefault(ip_addr, []).append(('vm-config', vm_id))

    for ip_addr, locations in global_ips.items():
        if len(locations) >= 2:
            loc_str = ', '.join([f"{net}:{dev}" for net, dev in locations])
            warnings.append(f"IP {ip_addr} appears in {len(locations)} places: {loc_str}")

