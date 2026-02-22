"""Cross-layer reference validation checks (L4-L7)."""

from typing import Any, Dict, List, Set


ARCH_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x86": "i386",
    "i386": "i386",
    "arm64": "arm64",
    "aarch64": "arm64",
    "riscv64": "riscv64",
    "riscv": "riscv64",
}


def _normalize_arch(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    return ARCH_ALIASES.get(normalized, normalized)


def _device_map(topology: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    l1 = topology.get('L1_foundation', {})
    return {
        d.get('id'): d
        for d in (l1.get('devices', []) or [])
        if isinstance(d, dict) and d.get('id')
    }


def _host_os_map(topology: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    l4 = topology.get('L4_platform', {})
    return {
        h.get('id'): h
        for h in (l4.get('host_operating_systems', []) or [])
        if isinstance(h, dict) and h.get('id')
    }


def _active_host_os_by_device(topology: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    per_device: Dict[str, List[Dict[str, Any]]] = {}
    for host_os in _host_os_map(topology).values():
        status = str(host_os.get('status', '')).lower()
        if status and status != 'active':
            continue
        device_ref = host_os.get('device_ref')
        if isinstance(device_ref, str) and device_ref:
            per_device.setdefault(device_ref, []).append(host_os)
    return per_device


def _device_architecture(device: Dict[str, Any]) -> str:
    specs = device.get('specs') if isinstance(device.get('specs'), dict) else {}
    cpu = specs.get('cpu') if isinstance(specs.get('cpu'), dict) else {}
    return _normalize_arch(cpu.get('architecture'))


def check_host_os_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l1 = topology.get('L1_foundation', {})
    l4 = topology.get('L4_platform', {})
    devices = _device_map(topology)
    media_ids = {
        media.get('id')
        for media in (l1.get('media_registry', []) or [])
        if isinstance(media, dict) and media.get('id')
    }

    for host_os in l4.get('host_operating_systems', []) or []:
        if not isinstance(host_os, dict):
            continue
        hos_id = host_os.get('id')
        device_ref = host_os.get('device_ref')
        if device_ref and device_ref not in ids['devices']:
            errors.append(f"Host OS '{hos_id}': device_ref '{device_ref}' does not exist")
            continue

        installation = host_os.get('installation') if isinstance(host_os.get('installation'), dict) else {}
        media_ref = installation.get('media_ref')
        if media_ref and media_ref not in media_ids:
            errors.append(f"Host OS '{hos_id}': installation.media_ref '{media_ref}' does not exist")

        root_storage_endpoint_ref = installation.get('root_storage_endpoint_ref')
        if root_storage_endpoint_ref and root_storage_endpoint_ref not in ids['storage_endpoints']:
            errors.append(
                f"Host OS '{hos_id}': installation.root_storage_endpoint_ref '{root_storage_endpoint_ref}' does not exist"
            )

        device = devices.get(device_ref, {})
        device_arch = _device_architecture(device)
        host_arch = _normalize_arch(host_os.get('architecture'))
        if device_arch and host_arch and device_arch != host_arch:
            errors.append(
                f"Host OS '{hos_id}' architecture '{host_os.get('architecture')}' does not match "
                f"device '{device_ref}' architecture '{device.get('specs', {}).get('cpu', {}).get('architecture')}'"
            )


def check_vm_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l4 = topology.get('L4_platform', {})
    host_os_map = _host_os_map(topology)
    active_by_device = _active_host_os_by_device(topology)
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

        host_os_ref = vm.get('host_os_ref')
        if host_os_ref and host_os_ref not in ids.get('host_operating_systems', set()):
            errors.append(f"VM '{vm_id}': host_os_ref '{host_os_ref}' does not exist")
        if host_os_ref and host_os_ref in host_os_map:
            host_device_ref = host_os_map[host_os_ref].get('device_ref')
            if device_ref and host_device_ref and host_device_ref != device_ref:
                errors.append(
                    f"VM '{vm_id}': host_os_ref '{host_os_ref}' belongs to device '{host_device_ref}', "
                    f"expected '{device_ref}'"
                )
            vm_arch = _normalize_arch((vm.get('os') or {}).get('architecture'))
            host_arch = _normalize_arch(host_os_map[host_os_ref].get('architecture'))
            if vm_arch and host_arch and vm_arch != host_arch:
                errors.append(
                    f"VM '{vm_id}': guest architecture '{(vm.get('os') or {}).get('architecture')}' "
                    f"does not match host OS '{host_os_ref}' architecture '{host_os_map[host_os_ref].get('architecture')}'"
                )
        if not host_os_ref and device_ref and len(active_by_device.get(device_ref, [])) > 1:
            errors.append(
                f"VM '{vm_id}': device '{device_ref}' has multiple active host OS objects; host_os_ref is required"
            )

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
    l4 = topology.get('L4_platform', {})
    host_os_map = _host_os_map(topology)
    active_by_device = _active_host_os_by_device(topology)
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

        host_os_ref = lxc.get('host_os_ref')
        if host_os_ref and host_os_ref not in ids.get('host_operating_systems', set()):
            errors.append(f"LXC '{lxc_id}': host_os_ref '{host_os_ref}' does not exist")
        if host_os_ref and host_os_ref in host_os_map:
            host_device_ref = host_os_map[host_os_ref].get('device_ref')
            if device_ref and host_device_ref and host_device_ref != device_ref:
                errors.append(
                    f"LXC '{lxc_id}': host_os_ref '{host_os_ref}' belongs to device '{host_device_ref}', "
                    f"expected '{device_ref}'"
                )
            lxc_arch = _normalize_arch((lxc.get('os') or {}).get('architecture'))
            host_arch = _normalize_arch(host_os_map[host_os_ref].get('architecture'))
            if lxc_arch and host_arch and lxc_arch != host_arch:
                errors.append(
                    f"LXC '{lxc_id}': guest architecture '{(lxc.get('os') or {}).get('architecture')}' "
                    f"does not match host OS '{host_os_ref}' architecture '{host_os_map[host_os_ref].get('architecture')}'"
                )
        if not host_os_ref and device_ref and len(active_by_device.get(device_ref, [])) > 1:
            errors.append(
                f"LXC '{lxc_id}': device '{device_ref}' has multiple active host OS objects; host_os_ref is required"
            )

        resource_profile_ref = lxc.get('resource_profile_ref')
        if resource_profile_ref and resource_profile_ref not in ids.get('resource_profiles', set()):
            errors.append(f"LXC '{lxc_id}': resource_profile_ref '{resource_profile_ref}' does not exist")

        rootfs = lxc.get('storage', {}).get('rootfs', {})
        storage_ref = rootfs.get('storage_endpoint_ref') or rootfs.get('storage_ref')
        if storage_ref and storage_ref not in ids['storage']:
            errors.append(f"LXC '{lxc_id}': rootfs storage_ref '{storage_ref}' does not exist")
        rootfs_data_asset_ref = rootfs.get('data_asset_ref')
        if rootfs_data_asset_ref and rootfs_data_asset_ref not in ids['data_assets']:
            errors.append(f"LXC '{lxc_id}': rootfs data_asset_ref '{rootfs_data_asset_ref}' does not exist")

        if rootfs.get('storage_ref') and rootfs.get('storage_endpoint_ref'):
            warnings.append(
                f"LXC '{lxc_id}': both rootfs.storage_ref and rootfs.storage_endpoint_ref are set; prefer storage_endpoint_ref"
            )

        for volume in lxc.get('storage', {}).get('volumes', []) or []:
            if not isinstance(volume, dict):
                continue
            volume_id = volume.get('id', 'unknown')
            volume_storage_ref = volume.get('storage_endpoint_ref') or volume.get('storage_ref')
            if volume_storage_ref and volume_storage_ref not in ids['storage']:
                errors.append(
                    f"LXC '{lxc_id}' volume '{volume_id}': storage reference '{volume_storage_ref}' does not exist"
                )
            data_asset_ref = volume.get('data_asset_ref')
            if data_asset_ref and data_asset_ref not in ids['data_assets']:
                errors.append(
                    f"LXC '{lxc_id}' volume '{volume_id}': data_asset_ref '{data_asset_ref}' does not exist"
                )

        for net in lxc.get('networks', []) or []:
            bridge_ref = net.get('bridge_ref')
            if bridge_ref and bridge_ref not in ids['bridges']:
                errors.append(f"LXC '{lxc_id}': bridge_ref '{bridge_ref}' does not exist")

        if lxc.get('type'):
            warnings.append(f"LXC '{lxc_id}': legacy field 'type' is deprecated; prefer platform_type + service runtime")
        if lxc.get('role'):
            warnings.append(f"LXC '{lxc_id}': legacy field 'role' is deprecated; prefer platform_type + resource_profile_ref")
        if lxc.get('resources'):
            warnings.append(
                f"LXC '{lxc_id}': inline 'resources' is deprecated; prefer resource_profiles + resource_profile_ref"
            )

        ansible_vars = ((lxc.get('ansible') or {}).get('vars') or {})
        if isinstance(ansible_vars, dict):
            app_key_prefixes = (
                "postgresql_",
                "redis_",
                "nextcloud_",
                "grafana_",
                "prometheus_",
                "jellyfin_",
                "homeassistant_",
            )
            if any(isinstance(key, str) and key.startswith(app_key_prefixes) for key in ansible_vars):
                warnings.append(
                    f"LXC '{lxc_id}': application keys in ansible.vars are deprecated; move app config to L5 services.config"
                )


def check_service_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    l5 = topology.get('L5_application', {})
    active_by_device = _active_host_os_by_device(topology)
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

        runtime = service.get('runtime', {}) or {}
        if isinstance(runtime, dict) and runtime:
            runtime_type = runtime.get('type')
            target_ref = runtime.get('target_ref')
            network_binding_ref = runtime.get('network_binding_ref')

            if network_binding_ref and network_binding_ref not in ids['networks']:
                errors.append(f"Service '{svc_id}': runtime network_binding_ref '{network_binding_ref}' does not exist")

            if runtime_type == 'lxc' and target_ref and target_ref not in ids['lxc']:
                errors.append(f"Service '{svc_id}': runtime target_ref '{target_ref}' is not a known LXC")
            if runtime_type == 'vm' and target_ref and target_ref not in ids['vms']:
                errors.append(f"Service '{svc_id}': runtime target_ref '{target_ref}' is not a known VM")
            if runtime_type in {'docker', 'baremetal'} and target_ref and target_ref not in ids['devices']:
                errors.append(f"Service '{svc_id}': runtime target_ref '{target_ref}' is not a known device")
            if runtime_type in {'docker', 'baremetal'} and target_ref in ids['devices']:
                host_os_entries = active_by_device.get(target_ref, [])
                if not host_os_entries:
                    errors.append(
                        f"Service '{svc_id}': runtime target_ref '{target_ref}' has no active host_operating_systems entry"
                    )
                if runtime_type == 'docker' and host_os_entries:
                    has_container_capability = any(
                        any(cap in {'docker', 'container'} for cap in (entry.get('capabilities') or []))
                        for entry in host_os_entries
                    )
                    if not has_container_capability:
                        errors.append(
                            f"Service '{svc_id}': runtime type docker requires host capability 'docker' or 'container' "
                            f"for device '{target_ref}'"
                        )

            if service.get('ip'):
                warnings.append(
                    f"Service '{svc_id}': legacy field 'ip' with runtime model is deprecated; prefer runtime/network binding resolution"
                )

            if service.get('device_ref') or service.get('vm_ref') or service.get('lxc_ref'):
                warnings.append(
                    f"Service '{svc_id}': mixing runtime with legacy *_ref fields; prefer runtime only"
                )

        for data_asset_ref in service.get('data_asset_refs', []) or []:
            if data_asset_ref not in ids['data_assets']:
                errors.append(f"Service '{svc_id}': data_asset_ref '{data_asset_ref}' does not exist")

        for dep in service.get('dependencies', []) or []:
            dep_ref = dep.get('service_ref')
            if dep_ref and dep_ref not in ids['services']:
                errors.append(f"Service '{svc_id}': dependency service_ref '{dep_ref}' does not exist")

    if l5.get('external_services'):
        warnings.append(
            "L5_application.external_services is deprecated; model Docker/Baremetal workloads via services[].runtime"
        )


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
