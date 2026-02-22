"""Foundation-layer validation checks (placement and device taxonomy)."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Set

import yaml
from yaml.tokens import AliasToken

from scripts.validators.checks.storage import (
    build_l1_storage_context,
    check_device_storage_taxonomy,
    check_l1_media_inventory,
)


def _check_expected_prefix(
    *,
    rel: str,
    expected_prefix: str,
    suggestion: str,
    policy_get: Callable[[List[str], Any], Any],
    emit_by_severity: Callable[[str, str], None],
) -> None:
    if not rel.startswith(expected_prefix):
        severity = policy_get(['checks', 'file_placement', 'severity'], 'warning')
        emit_by_severity(
            severity,
            f"File placement lint: '{rel}' does not match recommended layout; expected under "
            f"'{expected_prefix}' (suggested: '{suggestion}')"
        )


def _is_fixture_topology(topology_path: Path) -> bool:
    """Return True when validator is pointed to bundled fixture topology."""
    parts = {part.lower() for part in topology_path.resolve().parts}
    return 'topology-tools' in parts and 'fixtures' in parts


def check_modular_include_contract(
    *,
    topology_path: Path,
    errors: List[str],
) -> None:
    """
    Enforce deterministic include contract for migrated high-churn L1/L2 domains.

    Enforced domains:
    - L1: devices, media, media-attachments, data-links, power-links
    - L2: networks
    - L4 (when modular tree exists): defaults/resource-profiles/workloads/templates
    """
    if _is_fixture_topology(topology_path):
        # Keep fixture suites backward-compatible (legacy/new/mixed snapshots).
        return

    root = topology_path.resolve().parent
    l1_file = root / 'topology' / 'L1-foundation.yaml'
    l2_file = root / 'topology' / 'L2-network.yaml'
    l4_file = root / 'topology' / 'L4-platform.yaml'
    l4_dir = root / 'topology' / 'L4-platform'

    expected_lines_by_file = {
        l1_file: [
            "devices: !include_dir_sorted L1-foundation/devices",
            "media_registry: !include_dir_sorted L1-foundation/media",
            "media_attachments: !include_dir_sorted L1-foundation/media-attachments",
            "data_links: !include_dir_sorted L1-foundation/data-links",
            "power_links: !include_dir_sorted L1-foundation/power-links",
        ],
        l2_file: [
            "networks: !include_dir_sorted L2-network/networks",
        ],
    }
    if l4_dir.exists():
        expected_lines_by_file[l4_file] = [
            "_defaults: !include L4-platform/defaults.yaml",
            "resource_profiles: !include_dir_sorted L4-platform/resource-profiles",
            "lxc: !include_dir_sorted L4-platform/workloads/lxc",
            "vms: !include_dir_sorted L4-platform/workloads/vms",
            "lxc: !include_dir_sorted L4-platform/templates/lxc",
            "vms: !include_dir_sorted L4-platform/templates/vms",
        ]

    for composition_file, expected_lines in expected_lines_by_file.items():
        if not composition_file.exists():
            continue
        try:
            content = composition_file.read_text(encoding='utf-8')
        except OSError as exc:
            errors.append(f"Include contract: cannot read '{composition_file}': {exc}")
            continue
        for expected_line in expected_lines:
            if expected_line not in content:
                errors.append(
                    f"Include contract: '{composition_file}' must define `{expected_line}`"
                )

    migrated_dirs = [
        root / 'topology' / 'L1-foundation' / 'devices',
        root / 'topology' / 'L1-foundation' / 'media',
        root / 'topology' / 'L1-foundation' / 'media-attachments',
        root / 'topology' / 'L1-foundation' / 'data-links',
        root / 'topology' / 'L1-foundation' / 'power-links',
        root / 'topology' / 'L2-network' / 'networks',
    ]
    if l4_dir.exists():
        migrated_dirs.extend([
            l4_dir / 'resource-profiles',
            l4_dir / 'workloads' / 'lxc',
            l4_dir / 'workloads' / 'vms',
            l4_dir / 'templates' / 'lxc',
            l4_dir / 'templates' / 'vms',
        ])

    for domain_dir in migrated_dirs:
        if not domain_dir.exists():
            continue
        index_files = sorted(
            candidate.relative_to(root).as_posix()
            for candidate in domain_dir.rglob('_index.yaml')
        )
        for index_file in index_files:
            errors.append(
                f"Include contract: manual index file is not allowed in migrated domain ('{index_file}')"
            )

    if l4_dir.exists():
        _check_l4_workload_alias_usage(root=root, errors=errors)


def _check_l4_workload_alias_usage(*, root: Path, errors: List[str]) -> None:
    """Disallow YAML alias usage in modular L4 workloads to prevent cross-file anchor coupling."""
    workload_roots = [
        root / 'topology' / 'L4-platform' / 'workloads' / 'lxc',
        root / 'topology' / 'L4-platform' / 'workloads' / 'vms',
    ]
    for workload_root in workload_roots:
        if not workload_root.exists():
            continue
        for file_path in sorted(workload_root.rglob('*.yaml')):
            try:
                content = file_path.read_text(encoding='utf-8')
            except OSError as exc:
                errors.append(f"Include contract: cannot read '{file_path}': {exc}")
                continue

            try:
                has_alias = any(isinstance(token, AliasToken) for token in yaml.scan(content))
            except yaml.YAMLError as exc:
                errors.append(f"Include contract: cannot parse '{file_path}' for alias scan: {exc}")
                continue

            if has_alias:
                rel = file_path.relative_to(root).as_posix()
                errors.append(
                    f"Include contract: YAML aliases are not allowed in modular L4 workloads ('{rel}')"
                )


def _check_device_file_path(
    *,
    rel: str,
    file_path: Path,
    device: Dict[str, Any],
    policy_get: Callable[[List[str], Any], Any],
    emit_by_severity: Callable[[str, str], None],
) -> None:
    device_id = device.get('id', file_path.stem)
    device_class = device.get('class', 'unknown')
    substrate = device.get('substrate')

    expected_group = policy_get(
        ['l1_device_group_by_substrate', str(substrate)],
        'owned'
    )

    devices_root = policy_get(['paths', 'l1_devices_root'], "topology/L1-foundation/devices/")
    expected_path = f"{devices_root}{expected_group}/{device_class}/{device_id}.yaml"

    if not rel.startswith(devices_root):
        severity = policy_get(['checks', 'file_placement', 'severity'], 'warning')
        emit_by_severity(
            severity,
            f"File placement lint: device file '{rel}' should be in L1 devices "
            f"(suggested: '{expected_path}')"
        )
        return

    rel_inside = rel.replace(devices_root, "", 1)
    parts = rel_inside.split('/')
    if len(parts) < 3:
        severity = policy_get(['checks', 'file_placement', 'severity'], 'warning')
        emit_by_severity(
            severity,
            f"File placement lint: device file '{rel}' should follow "
            f"'topology/L1-foundation/devices/<group>/<class>/<id>.yaml'"
        )
        return

    group, class_dir = parts[0], parts[1]

    if group != expected_group:
        severity = policy_get(['checks', 'file_placement', 'severity'], 'warning')
        emit_by_severity(
            severity,
            f"File placement lint: device '{device_id}' substrate '{substrate}' expects group "
            f"'{expected_group}', got '{group}' (suggested: '{expected_path}')"
        )

    if class_dir != device_class:
        severity = policy_get(['checks', 'file_placement', 'severity'], 'warning')
        emit_by_severity(
            severity,
            f"File placement lint: device '{device_id}' class '{device_class}' expects folder "
            f"'{device_class}', got '{class_dir}' (suggested: '{expected_path}')"
        )


def check_file_placement(
    *,
    topology_path: Path,
    policy_get: Callable[[List[str], Any], Any],
    emit_by_severity: Callable[[str, str], None],
    warnings: List[str],
) -> None:
    """
    Validate that module objects are stored in expected directories.
    The object model (fields inside files) is authoritative; paths are validated against it.
    """
    if not policy_get(['checks', 'file_placement', 'enabled'], True):
        return

    topology_dir = topology_path.parent / 'topology'
    if not topology_dir.exists():
        warnings.append("Topology directory not found for placement checks: topology/")
        return

    for file_path in topology_dir.rglob('*.yaml'):
        if file_path.name == '_index.yaml':
            continue

        rel = file_path.relative_to(topology_path.parent).as_posix()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                obj = yaml.safe_load(f)
        except yaml.YAMLError:
            # Composite files with !include are validated elsewhere.
            continue
        except OSError as e:
            warnings.append(f"Cannot read file for placement check '{rel}': {e}")
            continue

        if not isinstance(obj, dict):
            continue

        obj_id = obj.get('id')
        if isinstance(obj_id, str) and obj_id and file_path.stem != obj_id:
            severity = policy_get(
                ['checks', 'file_placement', 'filename_id_mismatch_severity'],
                'warning'
            )
            emit_by_severity(
                severity,
                f"File '{rel}': filename '{file_path.stem}' differs from id '{obj_id}'"
            )

        if {'id', 'type', 'role', 'class', 'substrate'}.issubset(obj.keys()):
            _check_device_file_path(
                rel=rel,
                file_path=file_path,
                device=obj,
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if {'id', 'endpoint_a', 'endpoint_b', 'medium'}.issubset(obj.keys()):
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l1_data_links_root'], "topology/L1-foundation/data-links/"),
                suggestion=f"topology/L1-foundation/data-links/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if {'id', 'endpoint_a', 'endpoint_b', 'mode'}.issubset(obj.keys()) and str(obj.get('id', '')).startswith('plink-'):
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l1_power_links_root'], "topology/L1-foundation/power-links/"),
                suggestion=f"topology/L1-foundation/power-links/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if (
            isinstance(obj.get('id'), str)
            and obj.get('id', '').startswith('disk-')
            and {'type', 'size_gb'}.issubset(obj.keys())
        ):
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l1_media_root'], "topology/L1-foundation/media/"),
                suggestion=f"topology/L1-foundation/media/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if (
            isinstance(obj.get('id'), str)
            and obj.get('id', '').startswith('attach-')
            and {'device_ref', 'slot_ref', 'media_ref'}.issubset(obj.keys())
        ):
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l1_media_attachments_root'], "topology/L1-foundation/media-attachments/"),
                suggestion=f"topology/L1-foundation/media-attachments/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if isinstance(obj.get('id'), str) and obj.get('id', '').startswith('net-') and 'cidr' in obj:
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l2_networks_root'], "topology/L2-network/networks/"),
                suggestion=f"topology/L2-network/networks/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if isinstance(obj.get('id'), str) and obj.get('id', '').startswith('bridge-') and 'device_ref' in obj:
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l2_bridges_root'], "topology/L2-network/bridges/"),
                suggestion=f"topology/L2-network/bridges/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )
            continue

        if isinstance(obj.get('id'), str) and obj.get('id', '').startswith('fw-') and 'chain' in obj:
            _check_expected_prefix(
                rel=rel,
                expected_prefix=policy_get(['paths', 'l2_firewall_policies_root'], "topology/L2-network/firewall/policies/"),
                suggestion=f"topology/L2-network/firewall/policies/<group>/{obj.get('id', file_path.name)}.yaml",
                policy_get=policy_get,
                emit_by_severity=emit_by_severity,
            )


def check_device_taxonomy(
    topology: Dict[str, Any],
    ids: Dict[str, Set[str]],
    *,
    errors: List[str],
    warnings: List[str],
) -> None:
    """Validate L1 foundation taxonomy and substrate consistency."""
    l1 = topology.get('L1_foundation', {})
    devices = l1.get('devices', []) or []
    locations = {loc.get('id'): loc for loc in l1.get('locations', []) or [] if isinstance(loc, dict)}
    device_map = {d.get('id'): d for d in devices if isinstance(d, dict) and d.get('id')}
    storage_ctx = build_l1_storage_context(topology)
    power_device_ids = {
        d.get('id') for d in devices
        if isinstance(d, dict) and d.get('id') and d.get('class') == 'power'
    }
    class_type_map = {
        'network': {'router', 'switch', 'ap'},
        'compute': {'hypervisor', 'sbc', 'cloud-vm'},
        'storage': {'nas'},
        'power': {'ups', 'pdu'},
    }

    for device in devices:
        if not isinstance(device, dict):
            continue

        dev_id = device.get('id', 'unknown')
        dev_type = device.get('type')
        dev_class = device.get('class')
        dev_substrate = device.get('substrate')
        dev_access = device.get('access')
        location_ref = device.get('location')
        location_type = locations.get(location_ref, {}).get('type') if location_ref in locations else None

        if location_ref and location_ref not in locations:
            errors.append(f"Device '{dev_id}': location '{location_ref}' does not exist")

        power_cfg = device.get('power') if isinstance(device.get('power'), dict) else {}
        upstream_power_ref = power_cfg.get('upstream_power_ref')
        if upstream_power_ref and upstream_power_ref not in power_device_ids:
            errors.append(
                f"Device '{dev_id}': upstream_power_ref '{upstream_power_ref}' must reference an existing class 'power' device"
            )

        allowed_types = class_type_map.get(dev_class)
        if allowed_types and dev_type not in allowed_types:
            errors.append(
                f"Device '{dev_id}': class '{dev_class}' is inconsistent with type '{dev_type}'"
            )

        if dev_type == 'cloud-vm' and location_ref in locations and location_type != 'cloud':
            errors.append(
                f"Device '{dev_id}': cloud-vm is expected in cloud location, got '{location_ref}'"
            )

        if dev_type == 'cloud-vm' and dev_substrate != 'provider-instance':
            errors.append(
                f"Device '{dev_id}': cloud-vm must use substrate 'provider-instance'"
            )

        if dev_type != 'cloud-vm' and dev_substrate == 'provider-instance':
            errors.append(
                f"Device '{dev_id}': substrate 'provider-instance' is reserved for cloud-vm"
            )

        if dev_substrate == 'provider-instance' and dev_access == 'local-lan':
            warnings.append(
                f"Device '{dev_id}': provider-instance usually should not use access 'local-lan'"
            )

        if dev_substrate == 'provider-instance' and dev_access not in {'public', 'vpn-only'}:
            warnings.append(
                f"Device '{dev_id}': provider-instance access is usually 'public' or 'vpn-only'"
            )

        if dev_substrate in {'baremetal-owned', 'baremetal-colo'} and location_type == 'cloud':
            warnings.append(
                f"Device '{dev_id}': baremetal substrate mapped to cloud location '{location_ref}'"
            )

        if dev_class == 'compute':
            specs = device.get('specs') if isinstance(device.get('specs'), dict) else {}
            cpu = specs.get('cpu') if isinstance(specs.get('cpu'), dict) else {}
            cpu_arch = cpu.get('architecture')
            if not isinstance(cpu_arch, str) or not cpu_arch.strip():
                errors.append(
                    f"Device '{dev_id}': compute devices must declare specs.cpu.architecture "
                    f"(for host/runtime compile target compatibility)"
                )

        check_device_storage_taxonomy(
            device,
            storage_ctx=storage_ctx,
            errors=errors,
            warnings=warnings,
        )

    check_l1_media_inventory(
        topology,
        ids,
        storage_ctx=storage_ctx,
        errors=errors,
        warnings=warnings,
    )

    l7 = topology.get('L7_operations', {}) or {}
    l7_power = l7.get('power_resilience', {}) or {}
    l7_policies = l7_power.get('policies', []) or []
    for policy in l7_policies:
        if not isinstance(policy, dict):
            continue

        policy_id = policy.get('id', 'unknown')
        policy_device_ref = policy.get('device_ref')

        if policy_device_ref and policy_device_ref not in ids['devices']:
            errors.append(
                f"Power policy '{policy_id}': device_ref '{policy_device_ref}' does not exist"
            )
        elif policy_device_ref and (device_map.get(policy_device_ref) or {}).get('class') != 'power':
            errors.append(
                f"Power policy '{policy_id}': device_ref '{policy_device_ref}' must reference class 'power' device"
            )

        connection = policy.get('connection')
        if isinstance(connection, dict):
            connected_to = connection.get('connected_to')
            if connected_to and connected_to not in ids['devices']:
                errors.append(
                    f"Power policy '{policy_id}': connection.connected_to '{connected_to}' does not exist"
                )

        for protected in policy.get('protected_devices', []) or []:
            if not isinstance(protected, dict):
                continue
            protected_ref = protected.get('device_ref')
            if protected_ref and protected_ref not in ids['devices']:
                errors.append(
                    f"Power policy '{policy_id}': protected_devices device_ref '{protected_ref}' does not exist"
                )
