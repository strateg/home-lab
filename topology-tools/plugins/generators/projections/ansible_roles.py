"""Role-specific projection builders for Ansible role generator (ADR 0104).

Each role has a dedicated builder function that transforms topology data
into the variable structure expected by the corresponding Ansible role.
"""

from __future__ import annotations

from typing import Any


def derive_secrets_path(secrets_ref: str) -> str:
    """Convert topology secrets_ref to relative file path.

    Args:
        secrets_ref: Reference like 'secrets.tunnels.wg-home-to-oci'

    Returns:
        Relative path like 'tunnels/wg-home-to-oci.yaml'
    """
    # secrets.tunnels.wg-home-to-oci -> tunnels/wg-home-to-oci.yaml
    if secrets_ref.startswith("secrets."):
        secrets_ref = secrets_ref[8:]  # Remove "secrets." prefix
    return secrets_ref.replace(".", "/") + ".yaml"


def _get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Get nested value from dict using dot notation."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value


def build_wireguard_gateway_vars(
    instance: dict[str, Any],
    tunnel: dict[str, Any],
    vlan: dict[str, Any],
) -> dict[str, Any]:
    """Build wireguard_gateway role variables from topology.

    Args:
        instance: VPS instance data (e.g., vps-oracle-frankfurt)
        tunnel: WireGuard tunnel instance data (e.g., inst.tunnel.wg-home-to-oci)
        vlan: VLAN instance data (e.g., inst.vlan.vpn_germany)

    Returns:
        Dict matching structure expected by wireguard_gateway role.
    """
    # Extract instance data - handle both flat and nested structures
    instance_data = instance.get("instance_data", instance)
    instance_id = instance.get("instance_id", "")

    # WireGuard gateway config
    wg_config = _get_nested(instance_data, "wireguard_gateway", {})
    if not wg_config:
        wg_config = instance.get("wireguard_gateway", {})

    # Networking config
    networking = _get_nested(instance_data, "networking", {})
    if not networking:
        networking = instance.get("networking", {})

    # Find tunnel interface config
    tunnel_interfaces = networking.get("tunnel_interfaces", [])
    tunnel_iface = next(
        (t for t in tunnel_interfaces if t.get("name") == "wg0"),
        {}
    )

    # Extract tunnel endpoint data
    tunnel_data = tunnel.get("instance_data", tunnel)
    endpoint_b = tunnel_data.get("endpoint_b", {})
    endpoint_a = tunnel_data.get("endpoint_a", {})

    # Use tunnel data if instance doesn't have it
    if not tunnel_iface:
        tunnel_iface = {
            "tunnel_ip": endpoint_b.get("tunnel_ip"),
            "listen_port": endpoint_b.get("listen_port", 51820),
            "role": endpoint_b.get("role", "server"),
        }

    # Extract VLAN data
    vlan_data = vlan.get("instance_data", vlan)
    vlan_cidr = vlan_data.get("cidr", "")

    # Build secrets paths
    secrets_ref = tunnel_data.get("secrets_ref", "")
    tunnel_secrets_path = derive_secrets_path(secrets_ref) if secrets_ref else ""
    instance_secrets_path = f"instances/{instance_id}.yaml" if instance_id else ""

    # Build peer configuration from tunnel endpoint_a
    peers = []
    if endpoint_a:
        peer = {
            "name": endpoint_a.get("device_ref", ""),
            "public_key": "{{ wireguard_secrets.mikrotik.public_key }}",
            "allowed_ips": endpoint_a.get("allowed_ips", []),
        }
        if endpoint_a.get("persistent_keepalive"):
            peer["persistent_keepalive"] = endpoint_a["persistent_keepalive"]
        peers.append(peer)

    # Build routed networks from wireguard_gateway config
    routed_networks = []
    for net in wg_config.get("routed_networks", []):
        network = net.get("network")
        if not network and vlan_cidr:
            network = vlan_cidr
        routed_networks.append({
            "network": network,
            "comment": f"VLAN {vlan_data.get('vlan_id', '')} - {vlan_data.get('notes', '').split('.')[0] if vlan_data.get('notes') else 'VPN'}",
            "nat": net.get("nat", "masquerade"),
        })

    # Get iptables rules
    iptables_rules = wg_config.get("iptables_rules", {})
    forward_rules = iptables_rules.get("forward", [])
    nat_rules = iptables_rules.get("nat", [])

    # Fallback to tunnel-level rules if not in instance
    if not forward_rules and not nat_rules:
        vps_nat = tunnel_data.get("vps_nat", {})
        if vps_nat.get("iptables_rules"):
            all_rules = vps_nat["iptables_rules"]
            forward_rules = [r for r in all_rules if "FORWARD" in r]
            nat_rules = [r for r in all_rules if "nat" in r.lower() or "POSTROUTING" in r]

    return {
        "instance_ref": instance_id,
        "instance_group": "cloud",
        "instance_role": "vpn_gateway",
        "primary_interface": networking.get("primary_interface", "ens3"),
        "tunnel_interface": "wg0",
        "wireguard": {
            "interface": "wg0",
            "listen_port": tunnel_iface.get("listen_port", 51820),
            "tunnel_ip": tunnel_iface.get("tunnel_ip") or endpoint_b.get("tunnel_ip"),
            "role": tunnel_iface.get("role", "server"),
            "private_key_file": "/etc/wireguard/private.key",
            "config_file": "/etc/wireguard/wg0.conf",
        },
        "secrets": {
            "tunnel": tunnel_secrets_path,
            "instance": instance_secrets_path,
        },
        "wireguard_peers": peers,
        "ip_forwarding": wg_config.get("ip_forwarding", True),
        "routed_networks": routed_networks,
        "iptables_forward_rules": forward_rules,
        "iptables_nat_rules": nat_rules,
    }


def resolve_tunnel_instance(
    compiled_json: dict[str, Any],
    tunnel_ref: str,
) -> dict[str, Any]:
    """Resolve tunnel instance from compiled topology.

    Args:
        compiled_json: Full compiled topology
        tunnel_ref: Reference like 'inst.tunnel.wg-home-to-oci'

    Returns:
        Tunnel instance data or empty dict if not found.
    """
    instances = compiled_json.get("instances", {})
    network_instances = instances.get("network", [])

    for inst in network_instances:
        if not isinstance(inst, dict):
            continue
        if inst.get("instance_id") == tunnel_ref:
            return inst

    return {}


def resolve_vlan_instance(
    compiled_json: dict[str, Any],
    vlan_ref: str,
) -> dict[str, Any]:
    """Resolve VLAN instance from compiled topology.

    Args:
        compiled_json: Full compiled topology
        vlan_ref: Reference like 'inst.vlan.vpn_germany'

    Returns:
        VLAN instance data or empty dict if not found.
    """
    instances = compiled_json.get("instances", {})
    network_instances = instances.get("network", [])

    for inst in network_instances:
        if not isinstance(inst, dict):
            continue
        if inst.get("instance_id") == vlan_ref:
            return inst

    return {}
