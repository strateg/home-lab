"""Network and link-specific validation checks."""

import ipaddress
from typing import Any, Dict, List, Set


def check_vlan_tags(
    topology: Dict[str, Any],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check VLAN tags for LXC networks against L2 network definitions."""
    l2 = topology.get('L2_network', {})
    l4 = topology.get('L4_platform', {})

    networks = {n.get('id'): n for n in l2.get('networks', []) or []}
    bridges = {b.get('id'): b for b in l2.get('bridges', []) or []}

    for lxc in l4.get('lxc', []) or []:
        lxc_id = lxc.get('id', 'unknown')
        for nic in lxc.get('networks', []) or []:
            network_ref = nic.get('network_ref')
            vlan_tag = nic.get('vlan_tag')
            bridge_ref = nic.get('bridge_ref')

            if not network_ref or network_ref not in networks:
                continue

            network = networks[network_ref]
            network_vlan = network.get('vlan')

            if network_vlan is not None:
                if vlan_tag is None:
                    warnings.append(
                        f"LXC '{lxc_id}': network '{network_ref}' uses VLAN {network_vlan} "
                        "but vlan_tag is not set"
                    )
                elif vlan_tag != network_vlan:
                    errors.append(
                        f"LXC '{lxc_id}': vlan_tag {vlan_tag} does not match network '{network_ref}' VLAN {network_vlan}"
                    )
            elif vlan_tag is not None:
                warnings.append(
                    f"LXC '{lxc_id}': vlan_tag {vlan_tag} set but network '{network_ref}' has no VLAN"
                )

            bridge = bridges.get(bridge_ref) if bridge_ref else None
            if vlan_tag is not None and bridge and bridge.get('vlan_aware') is False:
                warnings.append(
                    f"LXC '{lxc_id}': vlan_tag {vlan_tag} used on non-vlan-aware bridge '{bridge_ref}'"
                )


def check_network_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    l2 = topology.get('L2_network', {})
    l1 = topology.get('L1_foundation', {})
    profiles = l2.get('network_profiles', {}) or {}
    trust_zones = l2.get('trust_zones', {}) or {}
    firewall_policy_map = {
        policy.get('id'): policy for policy in l2.get('firewall_policies', []) or []
        if isinstance(policy, dict) and policy.get('id')
    }
    global_firewall_policy_ids = {
        policy_id for policy_id, policy in firewall_policy_map.items()
        if not policy.get('source_zone_ref') and not policy.get('source_network_ref')
    }
    profile_fields = ['network_plane', 'segmentation_type', 'transport', 'volatility']
    device_map = {
        d.get('id'): d for d in l1.get('devices', []) or []
        if isinstance(d, dict) and d.get('id')
    }

    for network in l2.get('networks', []) or []:
        net_id = network.get('id')
        effective = {}
        profile_ref = network.get('profile_ref')

        if profile_ref and profile_ref in profiles and isinstance(profiles[profile_ref], dict):
            effective.update(profiles[profile_ref])
        effective.update(network)

        trust_zone_ref = network.get('trust_zone_ref')
        if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
            errors.append(f"Network '{net_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

        if profile_ref and profile_ref not in ids['network_profiles']:
            errors.append(f"Network '{net_id}': profile_ref '{profile_ref}' does not exist")
        elif profile_ref:
            profile = profiles.get(profile_ref)
            if isinstance(profile, dict):
                explicit_fields = [field for field in profile_fields if field in network]
                redundant_fields = [
                    field for field in explicit_fields
                    if network.get(field) == profile.get(field)
                ]
                if explicit_fields and len(redundant_fields) == len(explicit_fields):
                    warnings.append(
                        f"Network '{net_id}': redundant profile overrides for '{profile_ref}': "
                        f"{', '.join(redundant_fields)}"
                    )

        if not profile_ref:
            missing = [field for field in profile_fields if network.get(field) in (None, [], '')]
            if missing:
                warnings.append(
                    f"Network '{net_id}': no profile_ref and missing fields for analysis: {', '.join(missing)}"
                )

        bridge_ref = network.get('bridge_ref')
        if bridge_ref and bridge_ref not in ids['bridges']:
            errors.append(f"Network '{net_id}': bridge_ref '{bridge_ref}' does not exist")

        managed_by_ref = network.get('managed_by_ref')
        if managed_by_ref and managed_by_ref not in ids['devices']:
            errors.append(f"Network '{net_id}': managed_by_ref '{managed_by_ref}' does not exist or is not a device")
        elif managed_by_ref:
            managed_device = device_map.get(managed_by_ref, {})
            if managed_device.get('class') != 'network':
                errors.append(
                    f"Network '{net_id}': managed_by_ref '{managed_by_ref}' must reference class 'network' device"
                )
        else:
            warnings.append(f"Network '{net_id}': missing managed_by_ref")

        interface_ref = network.get('interface_ref')
        if interface_ref and interface_ref not in ids['interfaces']:
            errors.append(f"Network '{net_id}': interface_ref '{interface_ref}' does not exist")
        elif interface_ref and managed_by_ref:
            managed_device = device_map.get(managed_by_ref, {})
            managed_ifaces = {i.get('id') for i in managed_device.get('interfaces', []) or [] if isinstance(i, dict)}
            if interface_ref not in managed_ifaces:
                errors.append(
                    f"Network '{net_id}': interface_ref '{interface_ref}' does not belong to managed_by_ref '{managed_by_ref}'"
                )

        firewall_policy_refs = network.get('firewall_policy_refs') or []
        if len(firewall_policy_refs) != len(set(firewall_policy_refs)):
            warnings.append(
                f"Network '{net_id}': duplicate entries in firewall_policy_refs"
            )

        zone = trust_zones.get(trust_zone_ref, {}) if trust_zone_ref else {}
        if isinstance(zone, dict) and zone.get('isolated') is True and not firewall_policy_refs:
            warnings.append(
                f"Network '{net_id}': isolated trust zone '{trust_zone_ref}' should define firewall_policy_refs"
            )

        for fw_ref in firewall_policy_refs:
            if fw_ref not in ids['firewall_policies']:
                errors.append(f"Network '{net_id}': firewall_policy_refs '{fw_ref}' does not exist")
                continue

            if fw_ref in global_firewall_policy_ids:
                continue

            policy = firewall_policy_map.get(fw_ref, {})
            policy_source_network = policy.get('source_network_ref')
            policy_source_zone = policy.get('source_zone_ref')

            if policy_source_network and policy_source_network != net_id:
                errors.append(
                    f"Network '{net_id}': firewall policy '{fw_ref}' source_network_ref "
                    f"'{policy_source_network}' does not match network id"
                )

            if policy_source_zone and policy_source_zone != trust_zone_ref:
                errors.append(
                    f"Network '{net_id}': firewall policy '{fw_ref}' source_zone_ref "
                    f"'{policy_source_zone}' does not match trust_zone_ref '{trust_zone_ref}'"
                )

        plane = effective.get('network_plane')
        segmentation = effective.get('segmentation_type')
        transport = effective.get('transport') or []
        vlan = network.get('vlan')

        if segmentation == 'uplink' and plane != 'underlay-uplink':
            errors.append(
                f"Network '{net_id}': segmentation_type 'uplink' requires network_plane 'underlay-uplink'"
            )

        if segmentation in {'overlay-vpn', 'mesh-overlay'} and plane != 'overlay':
            errors.append(
                f"Network '{net_id}': segmentation_type '{segmentation}' requires network_plane 'overlay'"
            )

        if segmentation == 'vlan' and vlan is None:
            errors.append(f"Network '{net_id}': segmentation_type 'vlan' requires non-null vlan")

        if segmentation == 'bridge' and vlan is not None:
            errors.append(f"Network '{net_id}': segmentation_type 'bridge' requires vlan: null")

        if plane == 'underlay-uplink':
            if trust_zone_ref != 'untrusted':
                errors.append(
                    f"Network '{net_id}': underlay-uplink networks must use trust_zone_ref 'untrusted'"
                )
            if network.get('bridge_ref') is not None:
                errors.append(f"Network '{net_id}': underlay-uplink cannot set bridge_ref")
            if vlan is not None:
                errors.append(f"Network '{net_id}': underlay-uplink cannot set vlan")
            if not interface_ref:
                warnings.append(f"Network '{net_id}': underlay-uplink should set interface_ref")

        if plane == 'overlay':
            if not network.get('vpn_type'):
                warnings.append(f"Network '{net_id}': overlay network should set vpn_type")
            if network.get('bridge_ref') is not None:
                warnings.append(f"Network '{net_id}': overlay network should keep bridge_ref null")
            if vlan is not None:
                warnings.append(f"Network '{net_id}': overlay network should keep vlan null")

        if managed_by_ref:
            managed_device = device_map.get(managed_by_ref, {})
            iface_types = {
                i.get('type') for i in managed_device.get('interfaces', []) or []
                if isinstance(i, dict) and i.get('type')
            }
            transport_type_map = {
                'ethernet': {'ethernet', 'pci-ethernet', 'usb-ethernet'},
                'fiber': {'ethernet', 'pci-ethernet', 'usb-ethernet'},
                'wifi': {'wifi-5ghz', 'wifi-2.4ghz'},
                'lte': {'lte'},
            }
            for medium in transport:
                allowed_iface_types = transport_type_map.get(medium)
                if allowed_iface_types and not (iface_types & allowed_iface_types):
                    warnings.append(
                        f"Network '{net_id}': transport '{medium}' is not backed by interfaces on '{managed_by_ref}'"
                    )


def check_bridge_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l2 = topology.get('L2_network', {})
    for bridge in l2.get('bridges', []) or []:
        bridge_id = bridge.get('id')
        device_ref = bridge.get('device_ref')
        if device_ref and device_ref not in ids['devices']:
            errors.append(f"Bridge '{bridge_id}': device_ref '{device_ref}' does not exist")

        network_ref = bridge.get('network_ref')
        if network_ref and network_ref not in ids['networks']:
            errors.append(f"Bridge '{bridge_id}': network_ref '{network_ref}' does not exist")

        for port in bridge.get('ports', []) or []:
            if port not in ids['interfaces']:
                errors.append(f"Bridge '{bridge_id}': port '{port}' does not exist in device interfaces")


def _build_interface_owner(topology: Dict[str, Any]) -> Dict[str, Any]:
    l1 = topology.get('L1_foundation', {})
    interface_owner = {}
    for device in l1.get('devices', []) or []:
        device_id = device.get('id')
        for iface in device.get('interfaces', []) or []:
            iface_id = iface.get('id')
            if iface_id:
                interface_owner[iface_id] = device_id
    return interface_owner


def check_data_links(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    del warnings
    l1 = topology.get('L1_foundation', {})
    links = l1.get('data_links', []) or []
    if not links:
        return

    device_map = {
        d.get('id'): d for d in l1.get('devices', []) or []
        if isinstance(d, dict) and d.get('id')
    }
    interface_owner = _build_interface_owner(topology)

    for link in links:
        link_id = link.get('id', 'unknown')
        for endpoint_key in ('endpoint_a', 'endpoint_b'):
            endpoint = link.get(endpoint_key, {}) or {}
            device_ref = endpoint.get('device_ref')
            interface_ref = endpoint.get('interface_ref')
            external_ref = endpoint.get('external_ref')

            if device_ref and device_ref not in ids['devices']:
                errors.append(
                    f"Data link '{link_id}' {endpoint_key}: device_ref '{device_ref}' does not exist"
                )
            elif device_ref and device_map.get(device_ref, {}).get('substrate') == 'provider-instance':
                errors.append(
                    f"Data link '{link_id}' {endpoint_key}: device_ref '{device_ref}' is provider-instance"
                )

            if interface_ref and interface_ref not in ids['interfaces']:
                errors.append(
                    f"Data link '{link_id}' {endpoint_key}: interface_ref '{interface_ref}' does not exist"
                )

            if device_ref and interface_ref in interface_owner and interface_owner[interface_ref] != device_ref:
                owner = interface_owner[interface_ref]
                errors.append(
                    f"Data link '{link_id}' {endpoint_key}: interface_ref '{interface_ref}' "
                    f"belongs to '{owner}', not '{device_ref}'"
                )

            if not device_ref and not external_ref:
                errors.append(
                    f"Data link '{link_id}' {endpoint_key}: either device_ref or external_ref is required"
                )

        power_delivery = link.get('power_delivery')
        medium = link.get('medium')
        if isinstance(power_delivery, dict):
            if medium != 'ethernet':
                errors.append(
                    f"Data link '{link_id}': power_delivery is allowed only on medium 'ethernet'"
                )
            mode = power_delivery.get('mode')
            if mode and mode != 'poe':
                errors.append(
                    f"Data link '{link_id}': power_delivery.mode must be 'poe' for data links"
                )


def check_power_links(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    l1 = topology.get('L1_foundation', {})
    links = l1.get('power_links', []) or []
    if not links:
        return

    device_map = {
        d.get('id'): d for d in l1.get('devices', []) or []
        if isinstance(d, dict) and d.get('id')
    }
    interface_owner = _build_interface_owner(topology)

    for link in links:
        link_id = link.get('id', 'unknown')
        mode = link.get('mode')
        data_link_ref = link.get('data_link_ref')

        if data_link_ref and data_link_ref not in ids['data_links']:
            errors.append(
                f"Power link '{link_id}': data_link_ref '{data_link_ref}' does not exist"
            )

        if mode == 'poe' and not data_link_ref:
            warnings.append(
                f"Power link '{link_id}': PoE link should set data_link_ref to matching data link"
            )
        elif mode != 'poe' and data_link_ref:
            warnings.append(
                f"Power link '{link_id}': data_link_ref is typically used only with mode 'poe'"
            )

        if mode == 'wireless-inductive' and data_link_ref:
            errors.append(
                f"Power link '{link_id}': wireless-inductive mode must not set data_link_ref"
            )

        for endpoint_key in ('endpoint_a', 'endpoint_b'):
            endpoint = link.get(endpoint_key, {}) or {}
            device_ref = endpoint.get('device_ref')
            interface_ref = endpoint.get('interface_ref')
            external_ref = endpoint.get('external_ref')

            if device_ref and device_ref not in ids['devices']:
                errors.append(
                    f"Power link '{link_id}' {endpoint_key}: device_ref '{device_ref}' does not exist"
                )
            elif device_ref and device_map.get(device_ref, {}).get('substrate') == 'provider-instance':
                errors.append(
                    f"Power link '{link_id}' {endpoint_key}: device_ref '{device_ref}' is provider-instance"
                )

            if interface_ref and interface_ref not in ids['interfaces']:
                errors.append(
                    f"Power link '{link_id}' {endpoint_key}: interface_ref '{interface_ref}' does not exist"
                )

            if device_ref and interface_ref in interface_owner and interface_owner[interface_ref] != device_ref:
                owner = interface_owner[interface_ref]
                errors.append(
                    f"Power link '{link_id}' {endpoint_key}: interface_ref '{interface_ref}' "
                    f"belongs to '{owner}', not '{device_ref}'"
                )

            if not device_ref and not external_ref:
                errors.append(
                    f"Power link '{link_id}' {endpoint_key}: either device_ref or external_ref is required"
                )


def check_mtu_consistency(
    topology: Dict[str, Any],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check MTU and jumbo_frames consistency."""
    del warnings
    l2 = topology.get('L2_network', {})

    for network in l2.get('networks', []) or []:
        net_id = network.get('id')
        mtu = network.get('mtu')
        jumbo_frames = network.get('jumbo_frames', False)

        if jumbo_frames and mtu is not None and mtu <= 1500:
            errors.append(
                f"Network '{net_id}': jumbo_frames is true but mtu ({mtu}) <= 1500"
            )


def check_vlan_zone_consistency(
    topology: Dict[str, Any],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check that network VLAN is in its trust zone's vlan_ids."""
    l2 = topology.get('L2_network', {})
    trust_zones = l2.get('trust_zones', {}) or {}

    for network in l2.get('networks', []) or []:
        net_id = network.get('id')
        vlan = network.get('vlan')
        trust_zone_ref = network.get('trust_zone_ref')

        if vlan is None or not trust_zone_ref:
            continue

        zone = trust_zones.get(trust_zone_ref, {})
        if not isinstance(zone, dict):
            continue

        vlan_ids = zone.get('vlan_ids')
        if vlan_ids is None:
            continue

        if vlan not in vlan_ids:
            warnings.append(
                f"Network '{net_id}': VLAN {vlan} not in trust zone '{trust_zone_ref}' vlan_ids {vlan_ids}"
            )


def check_reserved_ranges(
    topology: Dict[str, Any],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check reserved_ranges validity."""
    del warnings
    l2 = topology.get('L2_network', {})

    for network in l2.get('networks', []) or []:
        net_id = network.get('id')
        cidr = network.get('cidr')
        reserved_ranges = network.get('reserved_ranges') or []

        if not reserved_ranges or cidr == 'dhcp':
            continue

        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue

        parsed_ranges = []
        for rng in reserved_ranges:
            start_str = rng.get('start')
            end_str = rng.get('end')
            purpose = rng.get('purpose', 'unknown')

            if not start_str or not end_str:
                errors.append(
                    f"Network '{net_id}': reserved range missing start or end"
                )
                continue

            try:
                start_ip = ipaddress.ip_address(start_str)
                end_ip = ipaddress.ip_address(end_str)
            except ValueError as e:
                errors.append(
                    f"Network '{net_id}': invalid IP in reserved range: {e}"
                )
                continue

            if start_ip not in net or end_ip not in net:
                errors.append(
                    f"Network '{net_id}': reserved range {start_str}-{end_str} not within CIDR {cidr}"
                )
                continue

            if start_ip > end_ip:
                errors.append(
                    f"Network '{net_id}': reserved range start {start_str} > end {end_str}"
                )
                continue

            parsed_ranges.append((start_ip, end_ip, purpose))

        for i, (start1, end1, purpose1) in enumerate(parsed_ranges):
            for j, (start2, end2, purpose2) in enumerate(parsed_ranges):
                if i >= j:
                    continue
                if start1 <= end2 and start2 <= end1:
                    errors.append(
                        f"Network '{net_id}': reserved ranges overlap: "
                        f"{start1}-{end1} ({purpose1}) and {start2}-{end2} ({purpose2})"
                    )


def check_trust_zone_firewall_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Check that trust zone default_firewall_policy_ref exists."""
    del warnings
    l2 = topology.get('L2_network', {})
    trust_zones = l2.get('trust_zones', {}) or {}

    for zone_id, zone in trust_zones.items():
        if not isinstance(zone, dict):
            continue

        fw_ref = zone.get('default_firewall_policy_ref')
        if fw_ref and fw_ref not in ids['firewall_policies']:
            errors.append(
                f"Trust zone '{zone_id}': default_firewall_policy_ref '{fw_ref}' does not exist"
            )

