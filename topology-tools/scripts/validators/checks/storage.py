"""Storage-specific validation checks for L1 and L3."""

from typing import Any, Dict, List, Optional, Set


def storage_disk_port_compatibility() -> Dict[str, Set[str]]:
    return {
        'hdd': {'ide', 'sata', 'sas', 'usb', 'virtual'},
        'ssd': {'ide', 'sata', 'sas', 'm2', 'pcie', 'usb', 'virtual'},
        'nvme': {'m2', 'pcie', 'virtual'},
        'sd-card': {'sdio', 'usb'},
        'emmc': {'emmc', 'emmc-reader', 'onboard'},
        'flash': {'qspi', 'usb', 'virtual', 'emmc', 'onboard'},
    }


def storage_mount_port_compatibility() -> Dict[str, Set[str]]:
    return {
        'soldered': {'qspi', 'emmc', 'onboard'},
        'replaceable': {'ide', 'sata', 'sas', 'm2', 'pcie', 'emmc'},
        'removable': {'usb', 'sdio', 'emmc-reader'},
        'virtual': {'virtual'},
    }


def build_l1_storage_context(topology: Dict[str, Any]) -> Dict[str, Any]:
    """Build lookup maps for L1 slot/media/attachment model."""
    l1 = topology.get('L1_foundation', {}) or {}
    devices = l1.get('devices', []) or []
    media_registry = l1.get('media_registry', []) if isinstance(l1.get('media_registry'), list) else []
    media_attachments = l1.get('media_attachments', []) if isinstance(l1.get('media_attachments'), list) else []

    device_map: Dict[str, Dict[str, Any]] = {}
    slots_by_device: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for device in devices:
        if not isinstance(device, dict):
            continue
        dev_id = device.get('id')
        if not dev_id:
            continue
        device_map[dev_id] = device
        specs = device.get('specs', {}) if isinstance(device.get('specs'), dict) else {}
        slots = specs.get('storage_slots', []) if isinstance(specs.get('storage_slots'), list) else []
        slot_map: Dict[str, Dict[str, Any]] = {}
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            slot_id = slot.get('id')
            if slot_id:
                slot_map[slot_id] = slot
        slots_by_device[dev_id] = slot_map

    media_by_id: Dict[str, Dict[str, Any]] = {}
    for media in media_registry:
        if not isinstance(media, dict):
            continue
        media_id = media.get('id')
        if media_id:
            media_by_id[media_id] = media

    attachments_by_device_slot: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for attachment in media_attachments:
        if not isinstance(attachment, dict):
            continue
        device_ref = attachment.get('device_ref')
        slot_ref = attachment.get('slot_ref')
        if not device_ref or not slot_ref:
            continue
        attachments_by_device_slot.setdefault(device_ref, {}).setdefault(slot_ref, []).append(attachment)

    return {
        'device_map': device_map,
        'slots_by_device': slots_by_device,
        'media_registry': media_registry,
        'media_attachments': media_attachments,
        'media_by_id': media_by_id,
        'attachments_by_device_slot': attachments_by_device_slot,
    }


def normalize_device_storage_inventory(
    device: Dict[str, Any],
    storage_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return normalized storage inventory resolved from slots + media attachments."""
    storage_ctx = storage_ctx or {}

    dev_id = device.get('id')
    specs = device.get('specs', {}) if isinstance(device.get('specs'), dict) else {}
    slots = specs.get('storage_slots', []) if isinstance(specs.get('storage_slots'), list) else []
    attachments_by_slot = storage_ctx.get('attachments_by_device_slot', {}).get(dev_id, {})
    media_by_id = storage_ctx.get('media_by_id', {})

    normalized_disks: List[Dict[str, Any]] = []

    for slot in slots:
        if not isinstance(slot, dict):
            continue
        slot_id = slot.get('id')
        slot_attachments = attachments_by_slot.get(slot_id, []) if slot_id else []
        selected_attachment: Optional[Dict[str, Any]] = None
        if slot_attachments:
            present = [a for a in slot_attachments if a.get('state', 'present') == 'present']
            selected_attachment = present[0] if present else slot_attachments[0]

        media = None
        media_ref = None
        if isinstance(selected_attachment, dict):
            media_ref = selected_attachment.get('media_ref')
            media = media_by_id.get(media_ref)

        if not isinstance(media, dict):
            continue

        normalized_disks.append({
            'id': media.get('id'),
            'type': media.get('type'),
            'mount_type': slot.get('mount'),
            'port_ref': slot_id,
            'port_type': slot.get('bus'),
            'removable': media.get('removable'),
            'virtual': media.get('virtual'),
            'os_device_path': media.get('device'),
            'supported_buses': media.get('supported_buses'),
            'attachment_id': selected_attachment.get('id') if isinstance(selected_attachment, dict) else None,
            'attachment_state': selected_attachment.get('state') if isinstance(selected_attachment, dict) else None,
            'media_ref': media_ref,
        })

    return {
        'slots': slots,
        'normalized_disks': normalized_disks,
    }


def check_device_storage_taxonomy(
    device: Dict[str, Any],
    *,
    storage_ctx: Optional[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> None:
    """Validate L1 compute storage slots and resolved media taxonomy."""
    dev_id = device.get('id', 'unknown')
    dev_class = device.get('class')
    dev_substrate = device.get('substrate')

    inventory = normalize_device_storage_inventory(device, storage_ctx=storage_ctx)
    slots = inventory['slots']
    disks = inventory['normalized_disks']

    if dev_class != 'compute':
        return

    os_cfg = device.get('os')
    if isinstance(os_cfg, dict):
        warnings.append(
            f"Device '{dev_id}': legacy 'os' block in L1; prefer supported_operating_systems for hardware capability only"
        )
        if os_cfg.get('planned'):
            errors.append(
                f"Device '{dev_id}': move os.planned to upper layers; keep only supported_operating_systems in L1"
            )

    if dev_substrate in {'baremetal-owned', 'baremetal-colo'} and not slots:
        errors.append(
            f"Device '{dev_id}': baremetal compute device must define specs.storage_slots inventory"
        )
    elif dev_substrate in {'baremetal-owned', 'baremetal-colo'} and not disks:
        warnings.append(
            f"Device '{dev_id}': no media attached to storage slots; check L1 media_attachments"
        )

    slot_ids: Set[str] = set()
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        slot_id = slot.get('id')
        if not slot_id:
            continue
        if slot_id in slot_ids:
            errors.append(
                f"Device '{dev_id}': duplicate storage slot id '{slot_id}'"
            )
        slot_ids.add(slot_id)
        if slot.get('media') is not None:
            errors.append(
                f"Device '{dev_id}': inline slot.media is deprecated; use L1 media_registry + media_attachments"
            )

    disk_ids: Set[str] = set()
    disk_port_compat = storage_disk_port_compatibility()
    mount_port_compat = storage_mount_port_compatibility()

    for disk in disks:
        if not isinstance(disk, dict):
            continue
        disk_id = disk.get('id')
        if disk_id:
            if disk_id in disk_ids:
                errors.append(
                    f"Device '{dev_id}': duplicate disk id '{disk_id}'"
                )
            disk_ids.add(disk_id)

        if disk.get('os_device_path'):
            errors.append(
                f"Device '{dev_id}': disk '{disk_id or 'unknown'}' contains logical OS device path; move it to L3 storage.os_device"
            )

        disk_type = disk.get('type')
        port_type = disk.get('port_type')
        allowed_ports = disk_port_compat.get(disk_type)
        if port_type and allowed_ports and port_type not in allowed_ports:
            warnings.append(
                f"Device '{dev_id}': disk '{disk_id or 'unknown'}' type '{disk_type}' "
                f"is unusual for port type '{port_type}'"
            )

        supported_buses = disk.get('supported_buses')
        if isinstance(supported_buses, list) and port_type and port_type not in set(supported_buses):
            errors.append(
                f"Device '{dev_id}': disk '{disk_id or 'unknown'}' does not support slot bus '{port_type}'"
            )

        mount_type = disk.get('mount_type')
        allowed_mount_ports = mount_port_compat.get(mount_type)
        if port_type and allowed_mount_ports and port_type not in allowed_mount_ports:
            errors.append(
                f"Device '{dev_id}': disk '{disk_id or 'unknown'}' mount_type '{mount_type}' "
                f"is incompatible with port type '{port_type}'"
            )

        removable = disk.get('removable')
        if mount_type == 'soldered' and removable is True:
            errors.append(
                f"Device '{dev_id}': soldered disk '{disk_id or 'unknown'}' cannot be removable"
            )
        if mount_type == 'removable' and removable is False:
            warnings.append(
                f"Device '{dev_id}': removable disk '{disk_id or 'unknown'}' has removable=false"
            )
        if mount_type == 'virtual' and disk.get('virtual') is not True:
            warnings.append(
                f"Device '{dev_id}': virtual disk '{disk_id or 'unknown'}' should set virtual=true"
            )


def check_l1_media_inventory(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    storage_ctx: Optional[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> None:
    """Validate global L1 media registry and slot attachment consistency."""
    del topology  # Reserved for future expansion; storage_ctx already includes resolved L1 view.
    storage_ctx = storage_ctx or {}

    media_registry = storage_ctx.get('media_registry', [])
    media_attachments = storage_ctx.get('media_attachments', [])
    slots_by_device = storage_ctx.get('slots_by_device', {})
    media_by_id = storage_ctx.get('media_by_id', {})

    disk_port_compat = storage_disk_port_compatibility()
    mount_port_compat = storage_mount_port_compatibility()

    seen_media_ids: Set[str] = set()
    for media in media_registry:
        if not isinstance(media, dict):
            continue
        media_id = media.get('id')
        if not media_id:
            continue
        if media_id in seen_media_ids:
            errors.append(f"L1 media_registry: duplicate media id '{media_id}'")
        seen_media_ids.add(media_id)

    present_slot_claims: Set[str] = set()
    present_media_claims: Dict[str, str] = {}

    for attachment in media_attachments:
        if not isinstance(attachment, dict):
            continue
        attach_id = attachment.get('id', 'unknown')
        device_ref = attachment.get('device_ref')
        slot_ref = attachment.get('slot_ref')
        media_ref = attachment.get('media_ref')
        state = attachment.get('state', 'present')

        if device_ref and device_ref not in ids['devices']:
            errors.append(
                f"L1 media attachment '{attach_id}': device_ref '{device_ref}' does not exist"
            )
            continue

        if not device_ref or not slot_ref:
            continue

        slot_map = slots_by_device.get(device_ref, {})
        slot = slot_map.get(slot_ref)
        if not slot:
            errors.append(
                f"L1 media attachment '{attach_id}': slot_ref '{slot_ref}' does not exist on device '{device_ref}'"
            )
            continue

        media = media_by_id.get(media_ref)
        if not isinstance(media, dict):
            errors.append(
                f"L1 media attachment '{attach_id}': media_ref '{media_ref}' not found in media_registry"
            )
            continue

        port_type = slot.get('bus')
        mount_type = slot.get('mount')
        media_type = media.get('type')
        media_id = media.get('id') or media_ref or 'unknown'

        allowed_ports = disk_port_compat.get(media_type)
        if port_type and allowed_ports and port_type not in allowed_ports:
            warnings.append(
                f"L1 media attachment '{attach_id}': media '{media_id}' type '{media_type}' "
                f"is unusual for port type '{port_type}'"
            )

        supported_buses = media.get('supported_buses')
        if isinstance(supported_buses, list) and port_type and port_type not in set(supported_buses):
            errors.append(
                f"L1 media attachment '{attach_id}': media '{media_id}' does not support bus '{port_type}'"
            )

        allowed_mount_ports = mount_port_compat.get(mount_type)
        if port_type and allowed_mount_ports and port_type not in allowed_mount_ports:
            errors.append(
                f"L1 media attachment '{attach_id}': mount_type '{mount_type}' is incompatible with port '{port_type}'"
            )

        removable = media.get('removable')
        if mount_type == 'soldered' and removable is True:
            errors.append(
                f"L1 media attachment '{attach_id}': soldered slot '{slot_ref}' cannot use removable media '{media_id}'"
            )
        if mount_type == 'removable' and removable is False:
            warnings.append(
                f"L1 media attachment '{attach_id}': removable slot '{slot_ref}' has media '{media_id}' with removable=false"
            )
        if mount_type == 'virtual' and media.get('virtual') is not True:
            warnings.append(
                f"L1 media attachment '{attach_id}': virtual slot '{slot_ref}' should use media with virtual=true"
            )

        if state == 'present':
            slot_key = f"{device_ref}::{slot_ref}"
            if slot_key in present_slot_claims:
                errors.append(
                    f"L1 media attachments: multiple 'present' media attached to slot '{slot_ref}' on device '{device_ref}'"
                )
            present_slot_claims.add(slot_key)

            previous_owner = present_media_claims.get(media_ref)
            this_owner = f"{device_ref}/{slot_ref}"
            if previous_owner and previous_owner != this_owner:
                errors.append(
                    f"L1 media attachments: media '{media_ref}' is 'present' in multiple slots ({previous_owner}, {this_owner})"
                )
            else:
                present_media_claims[media_ref] = this_owner


def check_l3_storage_refs(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    storage_ctx: Optional[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> None:
    """Validate L3 storage bindings to L1 media inventory and ADR-0026 compat rules."""
    l3 = topology.get('L3_data', {}) or {}
    storage_ctx = storage_ctx or {}
    media_by_id = storage_ctx.get('media_by_id', {})
    media_attachments = storage_ctx.get('media_attachments', [])
    l7_backup = (topology.get('L7_operations', {}) or {}).get('backup', {}) or {}
    backup_policies = {
        policy.get('id')
        for policy in (l7_backup.get('policies', []) or [])
        if isinstance(policy, dict) and policy.get('id')
    }

    disk_ids_by_device: Dict[str, Set[str]] = {}
    for attachment in media_attachments:
        if not isinstance(attachment, dict):
            continue
        device_ref = attachment.get('device_ref')
        media_ref = attachment.get('media_ref')
        state = attachment.get('state', 'present')
        if not device_ref or not media_ref or state == 'retired':
            continue
        disk_ids_by_device.setdefault(device_ref, set()).add(media_ref)

    for storage in l3.get('storage', []) or []:
        if not isinstance(storage, dict):
            continue
        storage_id = storage.get('id', 'unknown')
        device_ref = storage.get('device_ref')
        disk_ref = storage.get('disk_ref')
        os_device = storage.get('os_device')

        if device_ref and device_ref not in ids['devices']:
            errors.append(
                f"Storage '{storage_id}': device_ref '{device_ref}' does not exist"
            )
            continue

        if disk_ref and not device_ref:
            errors.append(
                f"Storage '{storage_id}': disk_ref '{disk_ref}' requires device_ref"
            )
            continue

        if disk_ref and disk_ref not in media_by_id:
            errors.append(
                f"Storage '{storage_id}': disk_ref '{disk_ref}' not found in L1 media_registry"
            )
            continue

        if os_device and not disk_ref:
            warnings.append(
                f"Storage '{storage_id}': os_device is set without disk_ref; prefer disk_ref+device_ref binding"
            )

        if disk_ref and not os_device:
            warnings.append(
                f"Storage '{storage_id}': disk_ref '{disk_ref}' has no os_device mapping"
            )

        if device_ref and disk_ref:
            known_disks = disk_ids_by_device.get(device_ref, set())
            if not known_disks:
                warnings.append(
                    f"Storage '{storage_id}': device '{device_ref}' has no L1 disk inventory"
                )
            elif disk_ref not in known_disks:
                errors.append(
                    f"Storage '{storage_id}': disk_ref '{disk_ref}' not found on device '{device_ref}'"
                )

    attachment_ids = {
        item.get('id')
        for item in media_attachments
        if isinstance(item, dict) and item.get('id')
    }
    partitions = {
        item.get('id'): item
        for item in (l3.get('partitions', []) or [])
        if isinstance(item, dict) and item.get('id')
    }
    volume_groups = {
        item.get('id'): item
        for item in (l3.get('volume_groups', []) or [])
        if isinstance(item, dict) and item.get('id')
    }
    volume_groups_by_name = {
        str(item.get('name')).strip(): item.get('id')
        for item in (l3.get('volume_groups', []) or [])
        if isinstance(item, dict) and item.get('id') and isinstance(item.get('name'), str) and str(item.get('name')).strip()
    }
    logical_volumes = {
        item.get('id'): item
        for item in (l3.get('logical_volumes', []) or [])
        if isinstance(item, dict) and item.get('id')
    }
    logical_volumes_by_name = {
        str(item.get('name')).strip(): item
        for item in (l3.get('logical_volumes', []) or [])
        if isinstance(item, dict) and item.get('id') and isinstance(item.get('name'), str) and str(item.get('name')).strip()
    }
    filesystems = {
        item.get('id'): item
        for item in (l3.get('filesystems', []) or [])
        if isinstance(item, dict) and item.get('id')
    }
    mount_points = {
        item.get('id'): item
        for item in (l3.get('mount_points', []) or [])
        if isinstance(item, dict) and item.get('id')
    }

    for partition_id, partition in partitions.items():
        media_attachment_ref = partition.get('media_attachment_ref')
        if media_attachment_ref and media_attachment_ref not in attachment_ids:
            errors.append(
                f"Partition '{partition_id}': media_attachment_ref '{media_attachment_ref}' not found in L1 media_attachments"
            )

    for vg_id, vg in volume_groups.items():
        vg_type = vg.get('type')
        for pv_ref in vg.get('pv_refs', []) or []:
            partition = partitions.get(pv_ref)
            if not partition:
                errors.append(
                    f"Volume group '{vg_id}': pv_ref '{pv_ref}' not found in L3 partitions"
                )
                continue
            part_type = partition.get('type')
            if vg_type == 'lvm' and part_type != 'lvm-pv':
                errors.append(
                    f"Volume group '{vg_id}': pv_ref '{pv_ref}' must reference partition type 'lvm-pv'"
                )
            if vg_type in {'zfs', 'btrfs'} and part_type == 'lvm-pv':
                warnings.append(
                    f"Volume group '{vg_id}': pv_ref '{pv_ref}' uses partition type 'lvm-pv' which is unusual for vg type '{vg_type}'"
                )

    for lv_id, lv in logical_volumes.items():
        vg_ref = lv.get('vg_ref')
        if vg_ref and vg_ref not in volume_groups:
            errors.append(
                f"Logical volume '{lv_id}': vg_ref '{vg_ref}' not found in L3 volume_groups"
            )

    for fs_id, filesystem in filesystems.items():
        lv_ref = filesystem.get('lv_ref')
        partition_ref = filesystem.get('partition_ref')
        if lv_ref and partition_ref:
            errors.append(
                f"Filesystem '{fs_id}': cannot reference both lv_ref and partition_ref"
            )
        if not lv_ref and not partition_ref:
            errors.append(
                f"Filesystem '{fs_id}': must reference lv_ref or partition_ref"
            )
        if lv_ref and lv_ref not in logical_volumes:
            errors.append(
                f"Filesystem '{fs_id}': lv_ref '{lv_ref}' not found in L3 logical_volumes"
            )
        if partition_ref and partition_ref not in partitions:
            errors.append(
                f"Filesystem '{fs_id}': partition_ref '{partition_ref}' not found in L3 partitions"
            )

    for mount_id, mount in mount_points.items():
        filesystem_ref = mount.get('filesystem_ref')
        if filesystem_ref and filesystem_ref not in filesystems:
            errors.append(
                f"Mount point '{mount_id}': filesystem_ref '{filesystem_ref}' not found in L3 filesystems"
            )

    for endpoint in l3.get('storage_endpoints', []) or []:
        if not isinstance(endpoint, dict):
            continue
        endpoint_id = endpoint.get('id', 'unknown')
        has_lv_ref = bool(endpoint.get('lv_ref'))
        has_mount_point_ref = bool(endpoint.get('mount_point_ref'))
        has_path = bool(endpoint.get('path'))
        infer_from = endpoint.get('infer_from')
        has_infer_from = isinstance(infer_from, dict) and bool(infer_from)

        if not any((has_lv_ref, has_mount_point_ref, has_path, has_infer_from)):
            warnings.append(
                f"Storage endpoint '{endpoint_id}': no lv_ref/mount_point_ref/path/infer_from set"
            )

        if has_infer_from:
            attachment_ref = infer_from.get('media_attachment_ref')
            vg_name = infer_from.get('vg_name')
            lv_name = infer_from.get('lv_name')
            if attachment_ref and attachment_ref not in attachment_ids:
                errors.append(
                    f"Storage endpoint '{endpoint_id}': infer_from.media_attachment_ref '{attachment_ref}' not found in L1 media_attachments"
                )
            if endpoint.get('type') == 'lvmthin':
                if not attachment_ref:
                    errors.append(
                        f"Storage endpoint '{endpoint_id}': infer_from.media_attachment_ref is required for type 'lvmthin'"
                    )
                if not vg_name:
                    errors.append(
                        f"Storage endpoint '{endpoint_id}': infer_from.vg_name is required for type 'lvmthin'"
                    )
                if not lv_name:
                    errors.append(
                        f"Storage endpoint '{endpoint_id}': infer_from.lv_name is required for type 'lvmthin'"
                    )

            if isinstance(vg_name, str) and vg_name.strip() and volume_groups_by_name:
                if vg_name.strip() not in volume_groups_by_name:
                    warnings.append(
                        f"Storage endpoint '{endpoint_id}': infer_from.vg_name '{vg_name}' is not present in L3 volume_groups names"
                    )

            if isinstance(lv_name, str) and lv_name.strip() and logical_volumes_by_name:
                lv_item = logical_volumes_by_name.get(lv_name.strip())
                if not lv_item:
                    warnings.append(
                        f"Storage endpoint '{endpoint_id}': infer_from.lv_name '{lv_name}' is not present in L3 logical_volumes names"
                    )
                elif isinstance(vg_name, str) and vg_name.strip() and volume_groups_by_name:
                    expected_vg_id = volume_groups_by_name.get(vg_name.strip())
                    if expected_vg_id and lv_item.get('vg_ref') and lv_item.get('vg_ref') != expected_vg_id:
                        warnings.append(
                            f"Storage endpoint '{endpoint_id}': infer_from.lv_name '{lv_name}' belongs to vg '{lv_item.get('vg_ref')}', not '{expected_vg_id}'"
                        )

            if has_lv_ref or has_mount_point_ref:
                warnings.append(
                    f"Storage endpoint '{endpoint_id}': infer_from used together with lv_ref/mount_point_ref; prefer one modeling approach"
                )

        if endpoint.get('lv_ref') and endpoint.get('lv_ref') not in logical_volumes:
            errors.append(
                f"Storage endpoint '{endpoint_id}': lv_ref '{endpoint.get('lv_ref')}' not found in L3 logical_volumes"
            )
        if endpoint.get('mount_point_ref') and endpoint.get('mount_point_ref') not in mount_points:
            errors.append(
                f"Storage endpoint '{endpoint_id}': mount_point_ref '{endpoint.get('mount_point_ref')}' not found in L3 mount_points"
            )

    engine_required_categories = {
        'database',
        'cache',
        'timeseries',
        'search-index',
        'object-storage',
    }
    for asset in l3.get('data_assets', []) or []:
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get('id', 'unknown')
        category = asset.get('category')
        criticality = asset.get('criticality')
        backup_policy_refs = asset.get('backup_policy_refs') or []

        if category in engine_required_categories and not asset.get('engine'):
            errors.append(
                f"Data asset '{asset_id}': category '{category}' requires engine"
            )

        if criticality in {'high', 'critical'} and not backup_policy_refs:
            errors.append(
                f"Data asset '{asset_id}': criticality '{criticality}' requires backup_policy_refs"
            )

        for backup_ref in backup_policy_refs:
            if backup_ref not in backup_policies:
                errors.append(
                    f"Data asset '{asset_id}': backup_policy_ref '{backup_ref}' not found in L7_operations.backup.policies"
                )

        has_placement_fields = bool(
            asset.get('storage_endpoint_ref') or asset.get('mount_point_ref') or asset.get('path')
        )
        if asset.get('category') and has_placement_fields:
            warnings.append(
                f"Data asset '{asset_id}': placement fields in L3 data_assets are deprecated; prefer L4 volume placement"
            )
