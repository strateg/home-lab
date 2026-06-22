#!/usr/bin/env python3
"""MikroTik-owned projection helpers for object generators."""

from __future__ import annotations

from ipaddress import ip_interface
from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_SERVICES,
    ProjectionError,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _require_object_ref,
    _resolved_object_ref,
    _sorted_rows,
)


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Extract capability IDs from instance row including object capabilities."""
    caps: set[str] = set()

    # Instance-level capabilities
    instance_data = row.get("instance", {}) or {}
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = instance_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    # Object-level capabilities (from object definition)
    obj_data = row.get("object", {}) or {}
    for field_name in ("enabled_capabilities", "derived_capabilities", "vendor_capabilities"):
        raw_caps = obj_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    # Root-level capabilities (legacy compatibility)
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = row.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    return caps


def _derive_mikrotik_capability_flags(routers: list[dict[str, Any]]) -> dict[str, bool]:
    """Derive boolean capability flags for conditional Terraform generation.

    ADR0078: Capabilities must come from object definitions, not hardcoded model checks.
    """
    all_caps: set[str] = set()
    for router in routers:
        all_caps.update(_extract_capabilities(router))

    return {
        "has_wireguard": any(cap.startswith("cap.net.overlay.vpn.wireguard") for cap in all_caps),
        "has_openvpn": any(cap.startswith("cap.net.overlay.vpn.openvpn") for cap in all_caps),
        "has_ipsec": "cap.net.overlay.vpn.ipsec" in all_caps,
        "has_containers": "cap.net.platform.containers" in all_caps,
        "has_qos_basic": "cap.net.l3.qos.basic" in all_caps,
        "has_qos_advanced": "cap.net.l3.qos.advanced" in all_caps,
        "has_lte": "cap.net.interface.lte" in all_caps,
        "has_wifi": "cap.net.interface.wifi" in all_caps,
        "has_vlan": "cap.net.l2.segmentation.vlan.8021q" in all_caps,
        "has_multi_wan": "cap.net.l3.uplink.multi_uplink" in all_caps,
        "has_failover": "cap.net.l3.uplink.failover" in all_caps,
    }


def _load_object_properties(object_ref: str) -> dict[str, Any]:
    """Load properties from object module YAML file."""
    from pathlib import Path

    import yaml

    # Determine repo root from this file's location
    this_file = Path(__file__).resolve()
    # This file is at topology/object-modules/mikrotik/plugins/projections.py
    # Object modules are at topology/object-modules/<domain>/obj.<domain>.<name>.yaml
    object_modules_root = this_file.parents[2]

    # Parse object_ref: obj.network.vlan.servers -> network/obj.network.vlan.servers.yaml
    parts = object_ref.split(".")
    if len(parts) < 3:
        return {}

    domain = parts[1]  # e.g., "network"
    object_file = object_modules_root / domain / f"{object_ref}.yaml"

    if not object_file.exists():
        return {}

    try:
        raw = object_file.read_text(encoding="utf-8")
        # Topology object modules use @-prefixed metadata keys; plain PyYAML can reject
        # some unquoted forms, so normalize only metadata keys before parsing.
        normalized_lines: list[str] = []
        for line in raw.splitlines():
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            if stripped.startswith("@") and ":" in stripped:
                key, rest = stripped.split(":", 1)
                normalized_lines.append(f'{indent}"{key}":{rest}')
            else:
                normalized_lines.append(line)
        payload = yaml.safe_load("\n".join(normalized_lines)) or {}
        if isinstance(payload, dict):
            props = payload.get("properties", {})
            if isinstance(props, dict):
                return props
        return {}
    except Exception:
        return {}


def _is_staged_row(row: dict[str, Any]) -> bool:
    status = str(row.get("status", "")).strip().lower()
    notes = str(row.get("notes", "")).strip().lower()
    return status == "modeled" or "currently not configured" in notes


def _build_vlan_entry(row: dict[str, Any], *, managed_by_ref: str) -> dict[str, Any]:
    """Extract VLAN configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}

    # Load properties from object module file (defaults)
    props = _load_object_properties(object_ref)

    # Instance data overrides object properties
    vlan_id = inst_data.get("vlan_id") or props.get("vlan_id")
    cidr = inst_data.get("cidr") or props.get("cidr")
    gateway = inst_data.get("gateway") or props.get("gateway")
    mtu = inst_data.get("mtu") or props.get("mtu", 1500)
    dhcp_enabled = inst_data.get("dhcp_enabled") if "dhcp_enabled" in inst_data else props.get("dhcp_enabled", False)
    dns_servers = inst_data.get("dns_servers") or props.get("dns_servers", [])

    is_native_lan = int(vlan_id or 0) == 1
    interface_name = "bridge" if is_native_lan else f"vlan{vlan_id}"

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.vlan.", "").replace(".", "_"),
        "vlan_id": vlan_id,
        "cidr": cidr,
        "gateway": gateway,
        "mtu": mtu,
        "dhcp_enabled": dhcp_enabled,
        "dhcp_range": inst_data.get("dhcp_range"),
        "dns_servers": dns_servers,
        "managed_by_ref": managed_by_ref,
        "trust_zone_ref": inst_data.get("trust_zone_ref"),
        "staged": _is_staged_row(row),
        "is_native_lan": is_native_lan,
        "interface_name": interface_name,
        "interface_is_resource": not is_native_lan,
    }


def _build_bridge_entry(row: dict[str, Any], *, managed_by_ref: str) -> dict[str, Any]:
    """Extract bridge configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}
    props = _load_object_properties(object_ref)
    ip_addr = str(inst_data.get("ip") or "").strip()
    cidr = str(inst_data.get("cidr") or "").strip()
    if not cidr and ip_addr:
        try:
            cidr = str(ip_interface(ip_addr).network)
        except ValueError:
            cidr = ""
    name = str(props.get("name") or row.get("instance_id", "").replace("inst.bridge.", "")).strip() or "bridge"
    return {
        "instance_id": row.get("instance_id", ""),
        "name": name.replace(".", "_"),
        "bridge_name": name,
        "ip": ip_addr,
        "cidr": cidr,
        "managed_by_ref": managed_by_ref,
        "staged": _is_staged_row(row),
    }


def _build_firewall_entry(row: dict[str, Any], *, managed_by_ref: str) -> dict[str, Any]:
    """Extract firewall policy from network row."""
    object_ref = _resolved_object_ref(row)
    props = _load_object_properties(object_ref)
    inst_data = row.get("instance_data", {}) or {}

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.fw.", "").replace(".", "_"),
        "chain": str(inst_data.get("chain") or "forward"),
        "managed_by_ref": managed_by_ref,
        "priority": int(props.get("priority", 1000)),
        "default_action": str(props.get("default_action", "drop")),
        "rules": props.get("rules", []) if isinstance(props.get("rules"), list) else [],
        "comment": str(row.get("notes", "")),
        "staged": _is_staged_row(row),
    }


def _extract_wifi_config(routers: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract WiFi configuration from router instances.

    Returns:
        {
            "datapaths": [...],      # Unique datapath configurations
            "configurations": [...], # WiFi configurations (SSIDs)
            "securities": [...],     # Security profiles
        }
    """
    datapaths: dict[str, dict[str, Any]] = {}  # keyed by name to dedupe
    configurations: list[dict[str, Any]] = []
    securities: dict[str, dict[str, Any]] = {}  # keyed by name to dedupe

    for router in routers:
        instance_data = router.get("instance_data", {})
        if not isinstance(instance_data, dict):
            continue

        observed = instance_data.get("observed_runtime", {})
        if not isinstance(observed, dict):
            continue

        wifi_config = observed.get("wifi", {})
        if not isinstance(wifi_config, dict):
            continue

        for iface_name, iface_data in wifi_config.items():
            if not isinstance(iface_data, dict):
                continue

            ssid = iface_data.get("ssid")
            if not ssid:
                continue

            # Extract datapath
            datapath = iface_data.get("datapath")
            if isinstance(datapath, dict):
                dp_name = datapath.get("name", "")
                if dp_name and dp_name not in datapaths:
                    dp_entry: dict[str, Any] = {
                        "name": dp_name,
                        "bridge": datapath.get("bridge", "bridge"),
                        "comment": f"{ssid} datapath - managed by topology",
                    }
                    # Only include vlan_id if present and non-zero
                    vlan_id = datapath.get("vlan_id")
                    if vlan_id:
                        dp_entry["vlan_id"] = int(vlan_id)
                    datapaths[dp_name] = dp_entry

            # Extract security profile
            security = iface_data.get("security")
            sec_name = None
            if isinstance(security, str) and security:
                sec_name = f"sec-{iface_name}"
                if sec_name not in securities:
                    securities[sec_name] = {
                        "name": sec_name,
                        "authentication_types": [security],
                        "passphrase": True,  # indicates variable needed
                        "comment": f"{ssid} security - managed by topology",
                    }

            # Build configuration entry
            cfg_name = f"cfg-{iface_name}"
            cfg_entry: dict[str, Any] = {
                "name": cfg_name,
                "ssid": ssid,
                "mode": iface_data.get("mode", "ap"),
                "comment": f"{ssid} - managed by topology",
            }
            if sec_name:
                cfg_entry["security"] = sec_name
            if isinstance(datapath, dict) and datapath.get("name"):
                cfg_entry["datapath"] = datapath.get("name")

            configurations.append(cfg_entry)

    return {
        "datapaths": list(datapaths.values()),
        "configurations": configurations,
        "securities": list(securities.values()),
    }


def _extract_security_matrix(
    network_rows: list[dict[str, Any]],
    router_ids: set[str],
) -> dict[str, Any]:
    """Extract security matrix configuration for MikroTik routers.

    Returns:
        {
            "zones": {...},  # Zone definitions with security_level, isolated, cidrs
            "matrix": {...},  # Zone-to-zone policy matrix
            "policy_overrides": [...],  # Explicit policy overrides
            "instance_id": "inst.security_matrix.mikrotik",
        }
    """
    for row in network_rows:
        object_ref = _resolved_object_ref(row)
        if "security_matrix" not in object_ref:
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            continue

        # Check if this matrix is managed by one of our MikroTik routers
        managed_by = str(inst_data.get("managed_by_ref", "")).strip()
        if managed_by not in router_ids:
            continue

        instance_id = str(row.get("instance_id", "")).strip()

        # Extract zone_refs and build zone index
        zone_refs = inst_data.get("zone_refs", [])
        if not isinstance(zone_refs, list):
            zone_refs = []

        # Get VLAN->Zone mapping from network rows
        vlan_zone_map: dict[str, str] = {}  # vlan instance -> zone ref
        vlan_cidr_map: dict[str, str] = {}  # vlan instance -> cidr
        for net_row in network_rows:
            net_object_ref = _resolved_object_ref(net_row)
            if "vlan" not in net_object_ref:
                continue
            net_inst_data = net_row.get("instance_data", {})
            if not isinstance(net_inst_data, dict):
                continue
            vlan_instance = str(net_row.get("instance_id", "")).strip()
            trust_zone_ref = str(net_inst_data.get("trust_zone_ref", "")).strip()
            cidr = str(net_inst_data.get("cidr", "")).strip()
            # Fallback to object properties for CIDR
            if not cidr:
                props = _load_object_properties(net_object_ref)
                cidr = str(props.get("cidr", "")).strip()
            if trust_zone_ref:
                vlan_zone_map[vlan_instance] = trust_zone_ref
            if cidr:
                vlan_cidr_map[vlan_instance] = cidr

        # Build zone_vlans: zone_ref -> [vlan_refs]
        zone_vlans: dict[str, list[str]] = {}
        for vlan_ref, zone_ref in vlan_zone_map.items():
            if zone_ref not in zone_vlans:
                zone_vlans[zone_ref] = []
            zone_vlans[zone_ref].append(vlan_ref)

        # Get zone security levels from network rows (trust_zone instances)
        zone_data: dict[str, dict[str, Any]] = {}
        for net_row in network_rows:
            net_object_ref = _resolved_object_ref(net_row)
            if "trust_zone" not in net_object_ref:
                continue
            zone_instance = str(net_row.get("instance_id", "")).strip()
            if zone_instance not in zone_refs:
                continue
            # Load properties from object
            props = _load_object_properties(net_object_ref)
            net_inst_data = net_row.get("instance_data", {})
            if not isinstance(net_inst_data, dict):
                net_inst_data = {}
            security_level = net_inst_data.get("security_level") or props.get("security_level", 0)
            isolated = net_inst_data.get("isolated") or props.get("isolated", False)
            name = net_inst_data.get("name") or props.get("name", zone_instance)
            zone_data[zone_instance] = {
                "name": name,
                "security_level": int(security_level) if security_level is not None else 0,
                "isolated": bool(isolated),
                "vlans": zone_vlans.get(zone_instance, []),
                "cidrs": [vlan_cidr_map[v] for v in zone_vlans.get(zone_instance, []) if v in vlan_cidr_map],
            }

        # Calculate matrix cells using R1-R6 rules
        matrix: dict[str, dict[str, dict[str, Any]]] = {}
        for from_zone in zone_refs:
            matrix[from_zone] = {}
            from_data = zone_data.get(from_zone, {})
            from_level = from_data.get("security_level", 0)
            from_isolated = from_data.get("isolated", False)

            for to_zone in zone_refs:
                to_data = zone_data.get(to_zone, {})
                to_level = to_data.get("security_level", 0)
                to_name = to_data.get("name", "")

                # R1: Same zone = ALLOW
                if from_zone == to_zone:
                    matrix[from_zone][to_zone] = {
                        "action": "allow",
                        "rule": "R1",
                        "reason": "same zone",
                        "log": False,
                    }
                    continue

                # R2: Isolated zones
                if from_isolated:
                    is_untrusted = "untrusted" in to_zone.lower() or (to_level == 0 and "untrusted" in to_name.lower())
                    if is_untrusted:
                        matrix[from_zone][to_zone] = {
                            "action": "allow",
                            "rule": "R2",
                            "reason": "isolated zone can reach untrusted",
                            "log": False,
                        }
                    else:
                        matrix[from_zone][to_zone] = {
                            "action": "deny",
                            "rule": "R2",
                            "reason": f"isolated zone cannot reach {to_zone}",
                            "log": True,
                        }
                    continue

                # R3/R4/R5: Security level comparison
                if from_level > to_level:
                    matrix[from_zone][to_zone] = {
                        "action": "allow",
                        "rule": "R3",
                        "reason": f"downhill: level {from_level} → {to_level}",
                        "log": False,
                    }
                elif from_level < to_level:
                    matrix[from_zone][to_zone] = {
                        "action": "deny",
                        "rule": "R4",
                        "reason": f"uphill: level {from_level} → {to_level}",
                        "log": True,
                    }
                else:
                    matrix[from_zone][to_zone] = {
                        "action": "deny",
                        "rule": "R5",
                        "reason": f"same level {from_level}, no override",
                        "log": True,
                    }

        # Extract policy_overrides
        policy_overrides = inst_data.get("policy_overrides", [])
        if not isinstance(policy_overrides, list):
            policy_overrides = []
        # Also get object-level overrides
        props = _load_object_properties(object_ref)
        obj_overrides = props.get("policy_overrides", [])
        if isinstance(obj_overrides, list):
            policy_overrides = obj_overrides + policy_overrides

        # Apply R6 overrides to matrix
        for override in policy_overrides:
            if not isinstance(override, dict):
                continue
            from_ref = str(override.get("from_zone_ref", "")).strip()
            to_ref = str(override.get("to_zone_ref", "")).strip()
            action = str(override.get("action", "accept")).strip()
            name = override.get("name", "unnamed")

            # Find matching zones
            for from_zone in zone_refs:
                if from_ref == from_zone or from_ref.split(".")[-1] == from_zone.split(".")[-1]:
                    for to_zone in zone_refs:
                        if to_ref == to_zone or to_ref.split(".")[-1] == to_zone.split(".")[-1]:
                            matrix[from_zone][to_zone] = {
                                "action": action,
                                "rule": "R6",
                                "reason": f"policy_override: {name}",
                                "log": override.get("log", False),
                                "ports": override.get("ports"),
                                "override_name": name,
                            }

        return {
            "instance_id": instance_id,
            "managed_by_ref": managed_by,
            "zones": zone_data,
            "matrix": matrix,
            "policy_overrides": policy_overrides,
        }

    return {}


def _extract_wireguard_tunnels(
    network_rows: list[dict[str, Any]],
    router_ids: set[str],
) -> dict[str, Any]:
    """Extract WireGuard tunnels where MikroTik router is an endpoint.

    Returns:
        {
            "tunnels": [...],  # List of tunnel configs for this router
            "wireguard_address": "10.100.0.1/30",  # Interface address
            "wireguard_listen_port": 51820,
            "wireguard_mtu": 1420,
            "wireguard_peers": [...],  # Peer configurations
        }
    """
    tunnels: list[dict[str, Any]] = []
    peers: list[dict[str, Any]] = []
    interface_address = ""
    listen_port = 51820
    mtu = 1420

    for row in network_rows:
        object_ref = _resolved_object_ref(row)
        if "wireguard_tunnel" not in object_ref:
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            continue

        # Check if MikroTik router is endpoint_a (typically client/initiator)
        endpoint_a = inst_data.get("endpoint_a", {})
        endpoint_b = inst_data.get("endpoint_b", {})

        local_endpoint = None
        remote_endpoint = None

        # Find which endpoint is our MikroTik router
        if isinstance(endpoint_a, dict):
            device_ref = str(endpoint_a.get("device_ref", "")).strip()
            if device_ref in router_ids:
                local_endpoint = endpoint_a
                remote_endpoint = endpoint_b

        if not local_endpoint and isinstance(endpoint_b, dict):
            device_ref = str(endpoint_b.get("device_ref", "")).strip()
            if device_ref in router_ids:
                local_endpoint = endpoint_b
                remote_endpoint = endpoint_a

        if not local_endpoint or not isinstance(remote_endpoint, dict):
            continue

        # Extract local interface config
        local_ip = str(local_endpoint.get("tunnel_ip", "")).strip()
        tunnel_network = str(inst_data.get("tunnel_network", "")).strip()
        if local_ip:
            # Check if IP already includes prefix
            if "/" in local_ip:
                interface_address = local_ip
            elif tunnel_network:
                # Combine IP with network prefix from tunnel_network
                try:
                    prefix = tunnel_network.split("/")[1] if "/" in tunnel_network else "30"
                    interface_address = f"{local_ip}/{prefix}"
                except (IndexError, ValueError):
                    interface_address = f"{local_ip}/30"
            else:
                interface_address = f"{local_ip}/30"

        listen_port = int(local_endpoint.get("listen_port", 51820) or 51820)
        mtu = int(inst_data.get("mtu", 1420) or 1420)

        # Build peer config for remote endpoint
        remote_name = str(remote_endpoint.get("device_ref", "unknown")).strip()
        remote_role = str(remote_endpoint.get("role", "")).strip()

        # Allowed IPs from the remote endpoint's configuration
        # This is what the remote peer is allowed to send through the tunnel
        remote_allowed_ips = remote_endpoint.get("allowed_ips", [])
        allowed_ips: list[str] = []
        if isinstance(remote_allowed_ips, list):
            for ip in remote_allowed_ips:
                if isinstance(ip, str) and ip:
                    allowed_ips.append(ip)

        # If allowed_ips is empty, at least add remote tunnel IP
        if not allowed_ips:
            remote_ip = str(remote_endpoint.get("tunnel_ip", "")).strip()
            if remote_ip:
                # Strip prefix if present and add /32
                base_ip = remote_ip.split("/")[0] if "/" in remote_ip else remote_ip
                allowed_ips.append(f"{base_ip}/32")

        peer_config: dict[str, Any] = {
            "name": remote_name,
            "allowed_ips": allowed_ips,
            "comment": f"Remote: {remote_name}",
        }

        # Server endpoint info (for client-initiated connections)
        if remote_role == "server":
            public_endpoint = remote_endpoint.get("public_endpoint", "")
            if public_endpoint:
                peer_config["endpoint_address"] = public_endpoint
                peer_config["endpoint_port"] = int(
                    remote_endpoint.get("listen_port", 51820) or 51820
                )
            # Client needs keepalive
            keepalive = inst_data.get("keepalive_interval", 25)
            if keepalive:
                peer_config["persistent_keepalive"] = f"{keepalive}s"

        # Mark that secrets are needed (not stored in projection)
        peer_config["preshared_key"] = True  # Indicates preshared key is used

        peers.append(peer_config)
        tunnels.append({
            "instance_id": row.get("instance_id", ""),
            "tunnel_name": inst_data.get("tunnel_name", "wg0"),
            "local_endpoint": local_endpoint,
            "remote_endpoint": remote_endpoint,
        })

    return {
        "tunnels": tunnels,
        "wireguard_address": interface_address,
        "wireguard_listen_port": listen_port,
        "wireguard_mtu": mtu,
        "wireguard_peers": peers,
    }


def build_mikrotik_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for MikroTik Terraform generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    network = _group_rows(groups, canonical=GROUP_NETWORK)
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)
    firewall_rows = groups.get("firewall", [])

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(devices):
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            export_row = dict(row)
            export_row.pop("instance", None)
            instance_data = export_row.get("instance_data")
            if not isinstance(instance_data, dict):
                instance_data = {}
            routers.append(export_row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    bridges: list[dict[str, Any]] = []
    vlans: list[dict[str, Any]] = []
    firewall_policies: list[dict[str, Any]] = []

    default_router_id = next(iter(sorted(router_ids)), "")

    for idx, row in enumerate(network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.network[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.network[{idx}]")
        export_row = dict(row)
        export_row.pop("instance", None)
        networks.append(export_row)
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()

        if "bridge" in object_ref:
            host_ref = str(inst_data.get("host_ref") or "").strip()
            if not managed_by_ref and host_ref in router_ids:
                managed_by_ref = host_ref
            if managed_by_ref in router_ids:
                bridges.append(_build_bridge_entry(row, managed_by_ref=managed_by_ref))

        # Extract VLANs managed by MikroTik routers.
        if "vlan" in object_ref:
            if not managed_by_ref and len(router_ids) == 1:
                # VLAN instances are treated as router-owned in single-router topology.
                managed_by_ref = default_router_id
            if not managed_by_ref:
                allocations = inst_data.get("ip_allocations")
                if isinstance(allocations, list):
                    for item in allocations:
                        if not isinstance(item, dict):
                            continue
                        device_ref = str(item.get("device_ref") or "").strip()
                        if device_ref in router_ids:
                            managed_by_ref = device_ref
                            break
            if managed_by_ref in router_ids:
                vlan_entry = _build_vlan_entry(row, managed_by_ref=managed_by_ref)
                vlans.append(vlan_entry)

    # Extract firewall policies from dedicated firewall group.
    for idx, row in enumerate(firewall_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.firewall[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.firewall[{idx}]")
        if "firewall_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            firewall_policies.append(_build_firewall_entry(row, managed_by_ref=managed_by_ref))

    selected_services: list[dict[str, Any]] = []
    for idx, row in enumerate(service_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in router_ids:
            export_row = dict(row)
            export_row.pop("instance", None)
            selected_services.append(export_row)

    # Build trust-zone to CIDR map from VLANs for firewall zone matching.
    trust_zone_cidrs: dict[str, str] = {}
    for vlan in vlans:
        zone_ref = str(vlan.get("trust_zone_ref") or "").strip()
        cidr = str(vlan.get("cidr") or "").strip()
        if zone_ref and cidr:
            trust_zone_cidrs[zone_ref] = cidr

    # Normalize firewall rules with CIDR resolution.
    normalized_firewall: list[dict[str, Any]] = []
    for policy in firewall_policies:
        rules = policy.get("rules", [])
        normalized_rules: list[dict[str, Any]] = []
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                src_zone_ref = str(rule.get("src_zone_ref") or "").strip()
                dst_zone_ref = str(rule.get("dst_zone_ref") or "").strip()
                normalized_rules.append(
                    {
                        "action": str(rule.get("action") or policy.get("default_action") or "drop"),
                        "protocol": str(rule.get("protocol") or "any"),
                        "comment": str(rule.get("comment") or policy.get("comment") or ""),
                        "src_zone_ref": src_zone_ref,
                        "dst_zone_ref": dst_zone_ref,
                        "src_cidr": trust_zone_cidrs.get(f"inst.trust_zone.{src_zone_ref}", ""),
                        "dst_cidr": trust_zone_cidrs.get(f"inst.trust_zone.{dst_zone_ref}", ""),
                    }
                )
        normalized = dict(policy)
        normalized["rules"] = normalized_rules
        normalized_firewall.append(normalized)

    # Runtime-derived baseline (single-router case) for NAT/DHCP/addresses.
    runtime_baseline: dict[str, Any] = {
        "nat": [],
        "dns_servers": [],
        "dhcp": {
            "enabled": False,
            "pool_range": "",
            "server_name": "",
            "lease_time": "",
            "network_cidr": "",
            "gateway": "",
            "interface": "",
        },
        "addresses": [],
    }
    if len(routers) == 1:
        router_data = routers[0].get("instance_data") if isinstance(routers[0].get("instance_data"), dict) else {}
        observed = router_data.get("observed_runtime") if isinstance(router_data, dict) else {}
        if isinstance(observed, dict):
            nat_items = observed.get("nat")
            if isinstance(nat_items, list):
                runtime_baseline["nat"] = [item for item in nat_items if isinstance(item, dict)]
            dns = observed.get("dns")
            if isinstance(dns, dict):
                servers = dns.get("servers")
                if isinstance(servers, list):
                    runtime_baseline["dns_servers"] = [str(v) for v in servers if isinstance(v, str) and v]
            lan = observed.get("lan")
            if isinstance(lan, dict):
                gateway_ref = str(lan.get("gateway_ref") or "").strip()
                dhcp_pool = str(lan.get("dhcp_pool") or "").strip()
                dhcp_server = str(lan.get("dhcp_server") or "").strip()
                dhcp_lease_time = str(lan.get("dhcp_lease_time") or "").strip()
                bridge_if = str(lan.get("bridge_interface") or "bridge").strip() or "bridge"
                lan_cidr = ""
                lan_gateway = ""
                for vlan in vlans:
                    if str(vlan.get("instance_id", "")).strip() == gateway_ref:
                        lan_cidr = str(vlan.get("cidr") or "").strip()
                        lan_gateway = str(vlan.get("gateway") or "").strip()
                        break
                runtime_baseline["dhcp"] = {
                    "enabled": bool(dhcp_pool and lan_cidr and lan_gateway),
                    "pool_range": dhcp_pool,
                    "server_name": dhcp_server or "defconf",
                    "lease_time": dhcp_lease_time or "30m",
                    "network_cidr": lan_cidr,
                    "gateway": lan_gateway,
                    "interface": bridge_if,
                }
            containers = observed.get("containers")
            if isinstance(containers, dict):
                bridge_ip = str(containers.get("bridge_ip") or "").strip()
                bridge_if = str(containers.get("bridge_interface") or "containers").strip() or "containers"
                if bridge_ip:
                    runtime_baseline["addresses"].append({"address": bridge_ip, "interface": bridge_if})

    # Extract WireGuard tunnel configurations for MikroTik routers
    wireguard_data = _extract_wireguard_tunnels(network, router_ids)

    # Extract WiFi configurations from router instances
    wifi_data = _extract_wifi_config(routers)

    # Extract security matrix for zone-based firewall (ADR 0110)
    security_matrix = _extract_security_matrix(network, router_ids)

    capability_flags = _derive_mikrotik_capability_flags(routers)
    return {
        "routers": _sorted_rows(routers),
        "networks": _sorted_rows(networks),
        "bridges": sorted(bridges, key=lambda b: str(b.get("instance_id", ""))),
        "vlans": sorted(vlans, key=lambda v: (int(v.get("vlan_id") or 0), str(v.get("instance_id", "")))),
        "firewall_policies": sorted(
            normalized_firewall,
            key=lambda p: (int(p.get("priority") or 1000), str(p.get("instance_id", ""))),
        ),
        "trust_zone_cidrs": trust_zone_cidrs,
        "runtime_baseline": runtime_baseline,
        "services": _sorted_rows(selected_services),
        "capabilities": capability_flags,
        # WireGuard tunnel data for Terraform generation
        "wireguard": wireguard_data,
        # WiFi configuration data for Terraform generation
        "wifi": wifi_data,
        # Security matrix for zone-based firewall (ADR 0110)
        "security_matrix": security_matrix,
        "counts": {
            "routers": len(routers),
            "networks": len(networks),
            "bridges": len(bridges),
            "vlans": len(vlans),
            "firewall_policies": len(firewall_policies),
            "services": len(selected_services),
            "wireguard_tunnels": len(wireguard_data.get("tunnels", [])),
        },
    }
