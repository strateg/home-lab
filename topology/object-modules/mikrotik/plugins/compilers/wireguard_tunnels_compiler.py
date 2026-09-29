#!/usr/bin/env python3
"""MikroTik WireGuard tunnel compiler plugin (W07 migration order item 4a).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md. WireGuard
tunnel/interface/peer derivation for this router - which tunnels it
terminates, its interface and peer shape - used to run inside the MikroTik
projection at generate stage; relocated here verbatim, with no behavior
change, so the fact exists at compile stage instead of being invisible until
render time.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDataExchangeError, PluginDiagnostic, PluginResult, Stage


def _resolved_object_ref(row: dict[str, Any]) -> str:
    """Same resolution projection_core._resolved_object_ref uses."""
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_object", "materializes_object"):
            value = instance_block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


def _extract_wireguard_tunnels(
    network_rows: list[dict[str, Any]],
    router_ids: set[str],
    vlan_cidr_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract WireGuard tunnels where MikroTik router is an endpoint.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _extract_wireguard_tunnels (W07 migration order item 4a).

    Args:
        network_rows: Network instance rows from compiled JSON.
        router_ids: Set of MikroTik router instance IDs.
        vlan_cidr_index: VLAN instance_id -> CIDR index for resolving allowed_vlan_refs (ADR-0111).

    Returns:
        {
            "tunnels": [...],  # List of tunnel configs for this router
            "interfaces": [...],  # List of WireGuard interfaces with their peers
            "wireguard_address": "192.0.2.1/30",  # Primary interface address (legacy)
            "wireguard_listen_port": 51820,  # Primary listen port (legacy)
            "wireguard_mtu": 1420,
            "wireguard_peers": [...],  # Primary interface peers (legacy)
        }
    """
    if vlan_cidr_index is None:
        vlan_cidr_index = {}
    tunnels: list[dict[str, Any]] = []

    # Group by interface name for multi-interface support
    interfaces_by_name: dict[str, dict[str, Any]] = {}

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

        tunnel_name = inst_data.get("tunnel_name", "wg0")

        # Extract local interface config
        local_ip = str(local_endpoint.get("tunnel_ip", "")).strip()
        tunnel_network = str(inst_data.get("tunnel_network", "")).strip()
        interface_address = ""
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

        local_role = str(local_endpoint.get("role", "")).strip()
        # Use explicit listen_port if set, otherwise 0 for client mode
        # (ADR-0112: clients can have listen_port for legacy peer support)
        listen_port = int(local_endpoint.get("listen_port", 0) or 0)
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

        # ADR-0111: resolve allowed_vlan_refs against the compiler's map. The map
        # spans every address domain, not only the MikroTik-managed ones, because
        # a tunnel may allow a VLAN another device owns.
        remote_vlan_refs = remote_endpoint.get("allowed_vlan_refs", [])
        if isinstance(remote_vlan_refs, list):
            allowed_ips.extend(
                vlan_cidr_index[ref.strip()]
                for ref in remote_vlan_refs
                if isinstance(ref, str) and ref.strip() in vlan_cidr_index
            )

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
                peer_config["endpoint_port"] = int(remote_endpoint.get("listen_port", 51820) or 51820)
            # Client needs keepalive
            local_keepalive = local_endpoint.get("persistent_keepalive")
            keepalive = local_keepalive if local_keepalive else inst_data.get("keepalive_interval", 25)
            if keepalive:
                peer_config["persistent_keepalive"] = f"{keepalive}s"

        # Mark that secrets are needed (not stored in projection)
        peer_config["preshared_key"] = True  # Indicates preshared key is used

        # Determine interface list for MikroTik firewall
        # Priority: local_endpoint.mikrotik_interface_list > firewall.mikrotik_interface_list > "LAN"
        interface_list = local_endpoint.get("mikrotik_interface_list")
        if not interface_list:
            firewall_cfg = inst_data.get("firewall", {})
            if isinstance(firewall_cfg, dict):
                interface_list = firewall_cfg.get("mikrotik_interface_list")
        if not interface_list:
            interface_list = "LAN"

        # Initialize interface if not seen yet
        if tunnel_name not in interfaces_by_name:
            interfaces_by_name[tunnel_name] = {
                "name": tunnel_name,
                "address": interface_address,
                "listen_port": listen_port if listen_port > 0 else None,
                "mtu": mtu,
                "interface_list": interface_list,
                "peers": [],
            }
        else:
            # Update address if not set
            if not interfaces_by_name[tunnel_name]["address"] and interface_address:
                interfaces_by_name[tunnel_name]["address"] = interface_address
            # Update listen_port if we found a server endpoint
            if listen_port > 0 and not interfaces_by_name[tunnel_name]["listen_port"]:
                interfaces_by_name[tunnel_name]["listen_port"] = listen_port

        interfaces_by_name[tunnel_name]["peers"].append(peer_config)

        tunnels.append(
            {
                "instance_id": row.get("instance_id", ""),
                "tunnel_name": tunnel_name,
                "local_endpoint": local_endpoint,
                "remote_endpoint": remote_endpoint,
            }
        )

    # Build interfaces list sorted by name
    interfaces = sorted(interfaces_by_name.values(), key=lambda x: x["name"])

    # Legacy compatibility: extract primary (wg0) interface data
    primary_interface = interfaces_by_name.get("wg0", {})
    legacy_address = primary_interface.get("address", "")
    legacy_listen_port = primary_interface.get("listen_port", 51820) or 51820
    legacy_mtu = primary_interface.get("mtu", 1420)
    legacy_peers = primary_interface.get("peers", [])

    return {
        "tunnels": tunnels,
        "interfaces": interfaces,
        "wireguard_address": legacy_address,
        "wireguard_listen_port": legacy_listen_port,
        "wireguard_mtu": legacy_mtu,
        "wireguard_peers": legacy_peers,
    }


class MikrotikWireguardTunnelsCompiler(CompilerPlugin):
    """Derives MikroTik WireGuard tunnel/interface/peer shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        network_rows = instances.get("network", []) if isinstance(instances, dict) else []
        if not isinstance(devices, list):
            devices = []
        if not isinstance(network_rows, list):
            network_rows = []

        router_ids: set[str] = set()
        for row in devices:
            if not isinstance(row, dict):
                continue
            if not _resolved_object_ref(row).startswith("obj.mikrotik."):
                continue
            instance_id = row.get("instance_id")
            if isinstance(instance_id, str) and instance_id:
                router_ids.add(instance_id)

        try:
            vlan_cidr_index = ctx.subscribe("base.compiler.security_matrix", "vlan_cidr_map")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9202",
                    severity="error",
                    stage=stage,
                    message=f"failed to obtain vlan_cidr_map: {exc}",
                    path="plugin:object.mikrotik.compiler.wireguard_tunnels",
                )
            )
            return self.make_result(diagnostics)
        if not isinstance(vlan_cidr_index, dict):
            vlan_cidr_index = {}

        wireguard_tunnels = _extract_wireguard_tunnels(network_rows, router_ids, vlan_cidr_index)

        diagnostics.append(
            self.emit_diagnostic(
                code="I4211",
                severity="info",
                stage=stage,
                message=f"Derived {len(wireguard_tunnels['tunnels'])} MikroTik WireGuard tunnel(s)",
                path="plugin:object.mikrotik.compiler.wireguard_tunnels",
            )
        )

        ctx.publish("wireguard_tunnels", wireguard_tunnels)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"wireguard_tunnels": wireguard_tunnels},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize, order 60). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)
