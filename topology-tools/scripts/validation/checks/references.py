"""Cross-layer reference validation checks (L4-L7)."""

from typing import Any, Dict, List, Set


def check_vm_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l4 = topology.get('L4_platform', {})
    for vm in l4.get('vms', []) or []:
        vm_id = vm.get('id')
        device_ref = vm.get('device_ref')
        if device_ref and device_ref not in ids['devices']:
            errors.append(f"VM '{vm_id}': device_ref '{device_ref}' does not exist")

        trust_zone_ref = vm.get('trust_zone_ref')
        if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
            errors.append(f"VM '{vm_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

        template_ref = vm.get('template_ref')
        if template_ref and template_ref not in ids['templates']:
            errors.append(f"VM '{vm_id}': template_ref '{template_ref}' does not exist")

        for disk in vm.get('storage', []) or []:
            storage_ref = disk.get('storage_ref')
            if storage_ref and storage_ref not in ids['storage']:
                errors.append(f"VM '{vm_id}': storage_ref '{storage_ref}' does not exist")

        for net in vm.get('networks', []) or []:
            bridge_ref = net.get('bridge_ref')
            if bridge_ref and bridge_ref not in ids['bridges']:
                errors.append(f"VM '{vm_id}': bridge_ref '{bridge_ref}' does not exist")


def check_lxc_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l4 = topology.get('L4_platform', {})
    for lxc in l4.get('lxc', []) or []:
        lxc_id = lxc.get('id')
        device_ref = lxc.get('device_ref')
        if device_ref and device_ref not in ids['devices']:
            errors.append(f"LXC '{lxc_id}': device_ref '{device_ref}' does not exist")

        trust_zone_ref = lxc.get('trust_zone_ref')
        if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
            errors.append(f"LXC '{lxc_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

        template_ref = lxc.get('template_ref')
        if template_ref and template_ref not in ids['templates']:
            errors.append(f"LXC '{lxc_id}': template_ref '{template_ref}' does not exist")

        rootfs = lxc.get('storage', {}).get('rootfs', {})
        storage_ref = rootfs.get('storage_ref')
        if storage_ref and storage_ref not in ids['storage']:
            errors.append(f"LXC '{lxc_id}': rootfs storage_ref '{storage_ref}' does not exist")

        for net in lxc.get('networks', []) or []:
            bridge_ref = net.get('bridge_ref')
            if bridge_ref and bridge_ref not in ids['bridges']:
                errors.append(f"LXC '{lxc_id}': bridge_ref '{bridge_ref}' does not exist")


def check_service_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l5 = topology.get('L5_application', {})
    for service in l5.get('services', []) or []:
        if not isinstance(service, dict):
            continue
        svc_id = service.get('id')

        device_ref = service.get('device_ref')
        if device_ref and device_ref not in ids['devices']:
            errors.append(f"Service '{svc_id}': device_ref '{device_ref}' does not exist")

        vm_ref = service.get('vm_ref')
        if vm_ref and vm_ref not in ids['vms']:
            errors.append(f"Service '{svc_id}': vm_ref '{vm_ref}' does not exist")

        lxc_ref = service.get('lxc_ref')
        if lxc_ref and lxc_ref not in ids['lxc']:
            errors.append(f"Service '{svc_id}': lxc_ref '{lxc_ref}' does not exist")

        network_ref = service.get('network_ref')
        if network_ref and network_ref not in ids['networks']:
            errors.append(f"Service '{svc_id}': network_ref '{network_ref}' does not exist")

        trust_zone_ref = service.get('trust_zone_ref')
        if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
            errors.append(f"Service '{svc_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

        for dep in service.get('dependencies', []) or []:
            dep_ref = dep.get('service_ref')
            if dep_ref and dep_ref not in ids['services']:
                errors.append(f"Service '{svc_id}': dependency service_ref '{dep_ref}' does not exist")


def check_dns_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l5 = topology.get('L5_application', {})
    dns = l5.get('dns', {})
    for zone in dns.get('zones', []) or []:
        for record in zone.get('records', []) or []:
            device_ref = record.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                errors.append(f"DNS record '{record.get('name')}' references unknown device_ref '{device_ref}'")
            lxc_ref = record.get('lxc_ref')
            if lxc_ref and lxc_ref not in ids['lxc']:
                errors.append(f"DNS record '{record.get('name')}' references unknown lxc_ref '{lxc_ref}'")
            service_ref = record.get('service_ref')
            if service_ref and service_ref not in ids['services']:
                errors.append(f"DNS record '{record.get('name')}' references unknown service_ref '{service_ref}'")


def check_certificate_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l5 = topology.get('L5_application', {})
    certs = l5.get('certificates', {})
    for cert in certs.get('certificates', []) or []:
        service_ref = cert.get('service_ref')
        if service_ref and service_ref not in ids['services']:
            errors.append(f"Certificate '{cert.get('id')}' references unknown service_ref '{service_ref}'")
    for cert in certs.get('additional', []) or []:
        for used in cert.get('used_by', []) or []:
            service_ref = used.get('service_ref')
            if service_ref and service_ref not in ids['services']:
                errors.append(f"Certificate '{cert.get('id')}' references unknown service_ref '{service_ref}'")


def check_backup_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l7 = topology.get('L7_operations', {})
    backup = l7.get('backup', {})
    for policy in backup.get('policies', []) or []:
        for target in policy.get('targets', []) or []:
            device_ref = target.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                errors.append(f"Backup '{policy.get('id')}': device_ref '{device_ref}' does not exist")
            lxc_ref = target.get('lxc_ref')
            if lxc_ref and lxc_ref not in ids['lxc']:
                errors.append(f"Backup '{policy.get('id')}': lxc_ref '{lxc_ref}' does not exist")
            data_asset_ref = target.get('data_asset_ref')
            if data_asset_ref and data_asset_ref not in ids['data_assets']:
                errors.append(f"Backup '{policy.get('id')}': data_asset_ref '{data_asset_ref}' does not exist")


def check_security_policy_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l2 = topology.get('L2_network', {})
    l5 = topology.get('L5_application', {})
    l7 = topology.get('L7_operations', {})
    valid = ids['security_policies']

    for policy in l2.get('firewall_policies', []) or []:
        ref = policy.get('security_policy_ref')
        if ref and ref not in valid:
            errors.append(f"Firewall policy '{policy.get('id')}': security_policy_ref '{ref}' does not exist")

    for svc in l5.get('services', []) or []:
        ref = svc.get('security_policy_ref')
        if ref and ref not in valid:
            errors.append(f"Service '{svc.get('id')}': security_policy_ref '{ref}' does not exist")

    backup = l7.get('backup', {})
    for policy in backup.get('policies', []) or []:
        ref = policy.get('security_policy_ref')
        if ref and ref not in valid:
            errors.append(f"Backup '{policy.get('id')}': security_policy_ref '{ref}' does not exist")

