"""ID collection helpers for cross-reference checks."""

from typing import Any, Dict, Set


def collect_ids(topology: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Collect IDs by layer for reference validation."""
    ids = {
        'devices': set(),
        'interfaces': set(),
        'data_links': set(),
        'power_links': set(),
        'power_policies': set(),
        'networks': set(),
        'bridges': set(),
        'storage': set(),
        'storage_endpoints': set(),
        'data_assets': set(),
        'trust_zones': set(),
        'network_profiles': set(),
        'firewall_policies': set(),
        'vms': set(),
        'lxc': set(),
        'resource_profiles': set(),
        'host_operating_systems': set(),
        'services': set(),
        'templates': set(),
        'security_policies': set(),
    }

    l0 = topology.get('L0_meta', {})
    l1 = topology.get('L1_foundation', {})
    l2 = topology.get('L2_network', {})
    l3 = topology.get('L3_data', {})
    l4 = topology.get('L4_platform', {})
    l5 = topology.get('L5_application', {})
    l7 = topology.get('L7_operations', {})

    for policy in l0.get('security_policy', []) or []:
        if isinstance(policy, dict) and policy.get('id'):
            ids['security_policies'].add(policy['id'])

    for device in l1.get('devices', []) or []:
        if isinstance(device, dict) and device.get('id'):
            ids['devices'].add(device['id'])
        for iface in device.get('interfaces', []) or []:
            if isinstance(iface, dict) and iface.get('id'):
                ids['interfaces'].add(iface['id'])

    for link in l1.get('data_links', []) or []:
        if isinstance(link, dict) and link.get('id'):
            ids['data_links'].add(link['id'])

    for link in l1.get('power_links', []) or []:
        if isinstance(link, dict) and link.get('id'):
            ids['power_links'].add(link['id'])

    l7_power = l7.get('power_resilience', {}) or {}
    l7_policies = l7_power.get('policies', []) or []
    for policy in l7_policies:
        if isinstance(policy, dict) and policy.get('id'):
            ids['power_policies'].add(policy['id'])

    for network in l2.get('networks', []) or []:
        if isinstance(network, dict) and network.get('id'):
            ids['networks'].add(network['id'])

    profiles = l2.get('network_profiles', {}) or {}
    ids['network_profiles'] = set(profiles.keys())

    for bridge in l2.get('bridges', []) or []:
        if isinstance(bridge, dict) and bridge.get('id'):
            ids['bridges'].add(bridge['id'])

    for fw_policy in l2.get('firewall_policies', []) or []:
        if isinstance(fw_policy, dict) and fw_policy.get('id'):
            ids['firewall_policies'].add(fw_policy['id'])

    for storage in l3.get('storage', []) or []:
        if isinstance(storage, dict) and storage.get('id'):
            ids['storage'].add(storage['id'])

    for endpoint in l3.get('storage_endpoints', []) or []:
        if isinstance(endpoint, dict) and endpoint.get('id'):
            endpoint_id = endpoint['id']
            ids['storage_endpoints'].add(endpoint_id)
            # Keep legacy compatibility: treat endpoint IDs as valid storage refs for cross-layer checks.
            ids['storage'].add(endpoint_id)

    for asset in l3.get('data_assets', []) or []:
        if isinstance(asset, dict) and asset.get('id'):
            ids['data_assets'].add(asset['id'])

    trust_zones = l2.get('trust_zones', {}) or {}
    ids['trust_zones'] = set(trust_zones.keys())

    for vm in l4.get('vms', []) or []:
        if isinstance(vm, dict) and vm.get('id'):
            ids['vms'].add(vm['id'])

    for lxc in l4.get('lxc', []) or []:
        if isinstance(lxc, dict) and lxc.get('id'):
            ids['lxc'].add(lxc['id'])

    for profile in l4.get('resource_profiles', []) or []:
        if isinstance(profile, dict) and profile.get('id'):
            ids['resource_profiles'].add(profile['id'])

    for host_os in l4.get('host_operating_systems', []) or []:
        if isinstance(host_os, dict) and host_os.get('id'):
            ids['host_operating_systems'].add(host_os['id'])

    for svc in l5.get('services', []) or []:
        if isinstance(svc, dict) and svc.get('id'):
            ids['services'].add(svc['id'])

    for tpl in l4.get('templates', {}).get('lxc', []) or []:
        if isinstance(tpl, dict) and tpl.get('id'):
            ids['templates'].add(tpl['id'])
    for tpl in l4.get('templates', {}).get('vms', []) or []:
        if isinstance(tpl, dict) and tpl.get('id'):
            ids['templates'].add(tpl['id'])

    return ids
