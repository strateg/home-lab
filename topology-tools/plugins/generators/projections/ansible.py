"""Ansible domain projections: inventory, role assignments, role host_vars (ADR 0104/0106/0112)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from plugins.generators.projection_core import (
    GROUP_DEVICES,
    GROUP_LXC,
    GROUP_VM,
    _group_rows,
    _instance_groups,
    _is_ansible_host_candidate,
    _require_non_empty_str,
    _require_object_ref,
    _sorted_rows,
)


def build_ansible_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Ansible inventory generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    lxc = _group_rows(groups, canonical=GROUP_LXC)
    vm = _group_rows(groups, canonical=GROUP_VM)

    hosts: list[dict[str, Any]] = []
    for idx, row in enumerate(devices):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        if not _is_ansible_host_candidate(row):
            continue
        host = deepcopy(row)
        host.pop("instance", None)
        host["inventory_group"] = "devices"
        hosts.append(host)
    for idx, row in enumerate(lxc):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.lxc[{idx}]")
        _require_object_ref(row, path=f"compiled_json.instances.lxc[{idx}]")
        host = deepcopy(row)
        host.pop("instance", None)
        host["inventory_group"] = "lxc"
        hosts.append(host)
    for idx, row in enumerate(vm):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.vm[{idx}]")
        _require_object_ref(row, path=f"compiled_json.instances.vm[{idx}]")
        if not _is_ansible_host_candidate(row):
            continue
        host = deepcopy(row)
        host.pop("instance", None)
        host["inventory_group"] = "vm"
        hosts.append(host)

    return {
        "hosts": _sorted_rows(hosts),
        "counts": {
            "hosts": len(hosts),
        },
    }


# Capability → Role mapping for Ansible role generation (ADR 0104, ADR 0106)
CAPABILITY_ROLE_MAP: dict[str, str] = {
    # Network capabilities
    "cap.network.vpn_gateway": "wireguard_gateway",
    # Role capabilities (ADR 0106 derived from enabled_capabilities)
    "cap.role.hypervisor": "hypervisor",
    "cap.role.router": "router",
    "cap.role.container_host": "container_host",
    "cap.role.edge_node": "edge_node",
    "cap.role.vpn_endpoint": "vpn_endpoint",
    # ADR 0104: Linux host role for common configuration
    "cap.role.linux_host": "common",
    # ADR 0104: Operations roles
    "cap.role.monitoring_target": "node_exporter",
    "cap.role.backup_target": "backup_client",
    # Compute capabilities
    "cap.compute.runtime.container_host": "docker_host",
    # Platform-specific container support
    "cap.net.platform.containers": "mikrotik_containers",
}


def _get_instance_capabilities(inst: dict[str, Any]) -> set[str]:
    """Get all capabilities for a compiled instance (ADR 0106 + ADR 0104).

    Collects capabilities from:
    - inst.object.enabled_capabilities (declared in object)
    - inst.object.derived_capabilities (derived by capability_compiler)
    - inst.instance.derived_capabilities (derived from firmware_ref/os_refs)

    Args:
        inst: Compiled instance dict from effective-topology.json

    Returns:
        Set of all capability strings
    """
    caps: set[str] = set()

    # Object-level capabilities
    obj = inst.get("object", {})
    if isinstance(obj, dict):
        enabled = obj.get("enabled_capabilities", [])
        if isinstance(enabled, list):
            caps.update(c for c in enabled if isinstance(c, str))
        derived = obj.get("derived_capabilities", [])
        if isinstance(derived, list):
            caps.update(c for c in derived if isinstance(c, str))

    # Instance-level derived capabilities (from firmware_ref/os_refs)
    instance = inst.get("instance", {})
    if isinstance(instance, dict):
        derived = instance.get("derived_capabilities", [])
        if isinstance(derived, list):
            caps.update(c for c in derived if isinstance(c, str))

    return caps


def build_ansible_role_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build projection for Ansible role-based host_vars generation (ADR 0104).

    Scans instances for capability markers and yields role-specific
    variable sets for each matching instance.

    ADR 0106 + ADR 0104: Uses get_all_capabilities to include derived capabilities
    from both object-level (capability_compiler) and instance-level (firmware/OS refs).

    Returns:
        dict with 'role_assignments' list and 'counts' summary.
    """
    groups = _instance_groups(compiled_json)
    role_assignments: list[dict[str, Any]] = []

    # Scan all instance groups for capability markers
    for group_name, group_instances in groups.items():
        if not isinstance(group_instances, list):
            continue
        for inst in group_instances:
            if not isinstance(inst, dict):
                continue
            instance_id = inst.get("instance_id", "")
            if not instance_id:
                continue

            # ADR 0106 + ADR 0104: Get ALL capabilities including derived
            capabilities = _get_instance_capabilities(inst)

            # Match capabilities to roles
            for cap in capabilities:
                if cap in CAPABILITY_ROLE_MAP:
                    role_assignments.append(
                        {
                            "instance_id": instance_id,
                            "capability": cap,
                            "role": CAPABILITY_ROLE_MAP[cap],
                            "group": group_name,
                            "instance_data": deepcopy(inst),
                        }
                    )

    return {
        "role_assignments": _sorted_rows(role_assignments),
        "counts": {
            "total_assignments": len(role_assignments),
            "roles": list(set(a["role"] for a in role_assignments)),
        },
    }


# =============================================================================
# Role Projection Builders (ADR 0104)
# =============================================================================
# These builders generate template context for Ansible role host_vars generation.
# Each builder extracts role-specific data from the compiled instance.


def build_role_host_vars_context(
    *,
    instance_id: str,
    group: str,
    role: str,
    instance_data: dict[str, Any],
) -> dict[str, Any]:
    """Build base template context for any role host_vars.

    Args:
        instance_id: The instance ID (e.g., "inst.proxmox-vm.home-assistant")
        group: The instance group name (e.g., "devices", "lxc")
        role: The Ansible role name (e.g., "common", "docker_host")
        instance_data: Full compiled instance data

    Returns:
        Base context dict with instance_id, group, and role fields.
    """
    return {
        "instance_id": instance_id,
        "group": group,
        "role": role,
        "instance_data": instance_data,
    }


def build_common_host_vars(
    *,
    instance_id: str,
    group: str,
    instance_data: dict[str, Any],
) -> dict[str, Any]:
    """Build template context for common role host_vars (cap.role.linux_host).

    Extracts common Linux host configuration: timezone, locale, SSH, NTP, firewall.

    Args:
        instance_id: The instance ID
        group: The instance group name
        instance_data: Full compiled instance data

    Returns:
        Context dict for common.yml.j2 template.
    """
    idata = instance_data.get("instance_data", {}) or {}
    obj_data = instance_data.get("object", {}) or {}

    ctx = build_role_host_vars_context(
        instance_id=instance_id,
        group=group,
        role="common",
        instance_data=instance_data,
    )

    # Extract timezone/locale from instance_data or object
    ctx["timezone"] = idata.get("timezone") or obj_data.get("timezone") or "UTC"
    ctx["locale"] = idata.get("locale") or obj_data.get("locale") or "en_US.UTF-8"

    # SSH configuration
    ssh_config = idata.get("ssh", {}) or {}
    ctx["ssh_port"] = ssh_config.get("port", 22)
    ctx["ssh_permit_root"] = ssh_config.get("permit_root_login", "no")
    ctx["ssh_password_auth"] = ssh_config.get("password_authentication", "no")

    # NTP servers
    ctx["ntp_servers"] = idata.get("ntp_servers") or obj_data.get("ntp_servers")

    # Firewall settings
    firewall = idata.get("firewall", {}) or {}
    ctx["firewall_enabled"] = firewall.get("enabled", True)
    ctx["firewall_default_incoming"] = firewall.get("default_incoming", "deny")
    ctx["firewall_default_outgoing"] = firewall.get("default_outgoing", "allow")

    return ctx


def build_docker_host_vars(
    *,
    instance_id: str,
    group: str,
    instance_data: dict[str, Any],
) -> dict[str, Any]:
    """Build template context for docker_host role host_vars (cap.compute.runtime.container_host).

    Extracts Docker-specific configuration: version, storage driver, logging, networks.

    Args:
        instance_id: The instance ID
        group: The instance group name
        instance_data: Full compiled instance data

    Returns:
        Context dict for docker_host.yml.j2 template.
    """
    idata = instance_data.get("instance_data", {}) or {}
    obj_data = instance_data.get("object", {}) or {}

    ctx = build_role_host_vars_context(
        instance_id=instance_id,
        group=group,
        role="docker_host",
        instance_data=instance_data,
    )

    # Docker configuration
    docker_config = idata.get("docker", {}) or obj_data.get("docker", {}) or {}
    ctx["docker_version"] = docker_config.get("version", "latest")
    ctx["docker_storage_driver"] = docker_config.get("storage_driver", "overlay2")
    ctx["docker_log_driver"] = docker_config.get("log_driver", "json-file")
    ctx["docker_log_max_size"] = docker_config.get("log_max_size", "10m")
    ctx["docker_log_max_file"] = docker_config.get("log_max_file", "3")

    # Container runtime settings
    container_config = idata.get("container_runtime", {}) or {}
    ctx["container_data_root"] = container_config.get("data_root", "/var/lib/docker")
    ctx["container_enable_ipv6"] = container_config.get("enable_ipv6", False)

    # Docker networks from instance_data
    ctx["docker_networks"] = idata.get("docker_networks") or []

    return ctx


def build_node_exporter_host_vars(
    *,
    instance_id: str,
    group: str,
    instance_data: dict[str, Any],
) -> dict[str, Any]:
    """Build template context for node_exporter role host_vars (cap.role.monitoring_target).

    Extracts monitoring configuration: version, port, collectors.

    Args:
        instance_id: The instance ID
        group: The instance group name
        instance_data: Full compiled instance data

    Returns:
        Context dict for node_exporter.yml.j2 template.
    """
    idata = instance_data.get("instance_data", {}) or {}
    obj_data = instance_data.get("object", {}) or {}

    ctx = build_role_host_vars_context(
        instance_id=instance_id,
        group=group,
        role="node_exporter",
        instance_data=instance_data,
    )

    # Node exporter configuration
    ne_config = idata.get("node_exporter", {}) or obj_data.get("node_exporter", {}) or {}
    ctx["node_exporter_version"] = ne_config.get("version", "latest")
    ctx["node_exporter_port"] = ne_config.get("port", 9100)
    ctx["node_exporter_listen"] = ne_config.get("listen_address", "0.0.0.0")

    # Collectors
    ctx["node_exporter_collectors"] = ne_config.get("collectors")
    ctx["node_exporter_disabled_collectors"] = ne_config.get("disabled_collectors")

    # Prometheus server for firewall rules
    ctx["prometheus_server_ip"] = idata.get("prometheus_server_ip") or obj_data.get("prometheus_server_ip")

    return ctx


# Role builder registry for dynamic dispatch
ROLE_HOST_VARS_BUILDERS: dict[str, Any] = {
    "common": build_common_host_vars,
    "docker_host": build_docker_host_vars,
    "node_exporter": build_node_exporter_host_vars,
}


def build_host_vars_for_role(
    *,
    role: str,
    instance_id: str,
    group: str,
    instance_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Build host_vars context for a specific role using registered builder.

    Args:
        role: The Ansible role name
        instance_id: The instance ID
        group: The instance group name
        instance_data: Full compiled instance data

    Returns:
        Context dict for the role's host_vars template, or None if no builder.
    """
    builder = ROLE_HOST_VARS_BUILDERS.get(role)
    if builder is None:
        return None
    return builder(
        instance_id=instance_id,
        group=group,
        instance_data=instance_data,
    )
