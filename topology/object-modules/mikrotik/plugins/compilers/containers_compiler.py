#!/usr/bin/env python3
"""MikroTik container compiler plugin (W07 migration order item 4b).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md.
Container attachment and publication shape - name, image, veth network,
environment variables, optional WireGuard interface - used to run inside the
MikroTik projection at generate stage; relocated here verbatim, with no
behavior change, so the fact exists at compile stage instead of being
invisible until render time.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


def _resolved_object_ref(row: dict[str, Any]) -> str:
    """Same resolution projection_core._resolved_object_ref uses."""
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_object", "materializes_object"):
            value = instance_block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


_MIKROTIK_ADAPTER = "cap.firewall.security_matrix.routeros"


def _is_mikrotik_enforcer(instance_id: Any, enforcer_resolution: dict[str, Any]) -> bool:
    """ADR 0118/0119 D-TYPE-1..3: is this instance a resolved RouterOS enforcer?

    Selection by declared capability (enforcer_resolution's adapter), not by
    object_ref name convention (ENFORCER-AXIS-CONFORMANCE.md V-14). A device
    with no device-kind capability, or whose OS family resolves a different
    (or no) adapter - rtr-slate, GL.iNet/OpenWrt, resolves enforcer type
    "network" but no adapter - no longer qualifies just because its object_ref
    happens to start with "obj.mikrotik.".
    """
    if not isinstance(instance_id, str) or not instance_id:
        return False
    resolution = enforcer_resolution.get(instance_id) if isinstance(enforcer_resolution, dict) else None
    return isinstance(resolution, dict) and resolution.get("adapter") == _MIKROTIK_ADAPTER


def _extract_containers(
    container_rows: list[dict[str, Any]],
    router_ids: set[str],
) -> list[dict[str, Any]]:
    """Extract container configurations from routeros_container instances.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _extract_containers (W07 migration order item 4b).

    Extracts container definitions for MikroTik routers, including:
    - Container name, image, root_dir, start_on_boot, logging
    - Veth network configuration (name, address, gateway)
    - Environment variables with _REF suffix resolution for secrets

    Note: All containers in the routeros_container group are inherently
    for RouterOS devices, so host_ref filtering is optional. When router_ids
    is provided and non-empty, containers are filtered to match.

    Args:
        container_rows: Container instance rows from routeros_container group.
        router_ids: Set of MikroTik router instance IDs (for filtering if provided).

    Returns:
        List of container definitions:
        [
            {
                "instance_id": "docker-amneziawg-russia",
                "name": "awg-proxy-russia",
                "tf_name": "awg_proxy_russia",
                "image": "ghcr.io/timbrs/awg-proxy:latest",
                "root_dir": "/usb1/containers/awg-proxy-russia",
                "start_on_boot": True,
                "logging": True,
                "comment": "AWG-Proxy container...",
                "veth_name": "veth-awg-ru",
                "veth_address": "198.51.100.2/30",
                "veth_gateway": "198.51.100.1",
                "envs": [
                    {"key": "AWG_LISTEN", "value": ":51820", "is_secret": False},
                    {"key": "AWG_REMOTE", "var_name": "awg_proxy_russia_awg_remote", "is_secret": True},
                    ...
                ],
                "managed_by_ref": "rtr-example",
            }
        ]
    """
    containers: list[dict[str, Any]] = []

    # Determine default managed_by (first router if single-router topology)
    default_router = next(iter(sorted(router_ids)), "") if router_ids else ""

    for row in container_rows:
        instance_id = str(row.get("instance_id", "")).strip()
        if not instance_id:
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            inst_data = {}

        # Try to get host_ref from various locations
        host_ref = str(inst_data.get("host_ref", "")).strip()
        if not host_ref:
            host_ref = str(row.get("host_ref", "")).strip()

        # In single-router topologies, assign all containers to that router
        # The routeros_container group is inherently for RouterOS devices
        if not host_ref and len(router_ids) == 1:
            host_ref = default_router

        # Extract runtime configuration (may be at root level or in instance_data)
        runtime = inst_data.get("runtime")
        if not isinstance(runtime, dict) or not runtime:
            runtime = row.get("runtime")
        if not isinstance(runtime, dict):
            runtime = {}

        container_name = str(runtime.get("name", "")).strip()
        if not container_name:
            # Fallback to instance_id without prefix
            container_name = instance_id.replace("docker-", "").replace("inst.", "")

        # Build Terraform-safe name (replace hyphens with underscores)
        tf_name = container_name.replace("-", "_")

        # Extract network configuration (may be at root level or in instance_data)
        network = inst_data.get("network")
        if not isinstance(network, dict) or not network:
            network = row.get("network")
        if not isinstance(network, dict):
            network = {}

        veth_name = str(network.get("veth_name", "")).strip()
        veth_address = str(network.get("address", "")).strip()
        veth_gateway = str(network.get("gateway", "")).strip()

        # Extract environment variables, handling _REF suffix for secrets
        env_dict = runtime.get("env", {})
        if not isinstance(env_dict, dict):
            env_dict = {}

        envs: list[dict[str, Any]] = []
        for key, value in sorted(env_dict.items()):
            if key.endswith("_REF"):
                # Secret reference: strip _REF suffix, generate Terraform variable name
                actual_key = key[:-4]  # Remove "_REF" suffix
                var_name = f"{tf_name}_{actual_key.lower()}"
                envs.append(
                    {
                        "key": actual_key,
                        "var_name": var_name,
                        "secrets_ref": str(value),
                        "is_secret": True,
                    }
                )
            else:
                # Literal value
                envs.append(
                    {
                        "key": key,
                        "value": str(value),
                        "is_secret": False,
                    }
                )

        # Extract notes for comment
        notes = str(row.get("notes", "")).strip()
        comment = notes.split("\n")[0] if notes else f"Container {container_name}"

        # Extract wireguard_interface configuration (for AWG proxy containers)
        wg_interface_raw = inst_data.get("wireguard_interface")
        if not isinstance(wg_interface_raw, dict) or not wg_interface_raw:
            wg_interface_raw = row.get("wireguard_interface")

        wireguard_interface = None
        if isinstance(wg_interface_raw, dict) and wg_interface_raw.get("name"):
            wg_name = str(wg_interface_raw.get("name", "")).strip()
            wg_tf_name = wg_name.replace("-", "_")

            # Extract peer configuration
            peer_raw = wg_interface_raw.get("peer", {})
            peer_config = None
            if isinstance(peer_raw, dict):
                # Endpoint is container's veth address (strip /prefix)
                endpoint_addr = veth_address.split("/")[0] if "/" in veth_address else veth_address
                # Parse endpoint port from peer.endpoint or default to 51820
                peer_endpoint = str(peer_raw.get("endpoint", "")).strip()
                if ":" in peer_endpoint:
                    endpoint_port = int(peer_endpoint.split(":")[-1])
                else:
                    endpoint_port = 51820

                peer_config = {
                    "public_key_var": f"{tf_name}_wg_peer_public_key",
                    "public_key_ref": str(peer_raw.get("public_key_ref", "")).strip(),
                    "preshared_key_var": f"{tf_name}_wg_peer_preshared_key",
                    "preshared_key_ref": str(peer_raw.get("preshared_key_ref", "")).strip() or None,
                    "endpoint_address": endpoint_addr,
                    "endpoint_port": endpoint_port,
                    "allowed_ips": peer_raw.get("allowed_ips", ["0.0.0.0/0"]),
                    "persistent_keepalive": peer_raw.get("persistent_keepalive", 25),
                }

            wireguard_interface = {
                "name": wg_name,
                "tf_name": wg_tf_name,
                "listen_port": int(wg_interface_raw.get("listen_port", 51820) or 51820),
                "private_key_var": f"{tf_name}_wg_private_key",
                "private_key_ref": str(wg_interface_raw.get("private_key_ref", "")).strip(),
                "address": str(wg_interface_raw.get("address", "")).strip(),
                "mtu": int(wg_interface_raw.get("mtu", 1420) or 1420),
                "interface_list": str(wg_interface_raw.get("interface_list", "VPN_EXIT")).strip() or "VPN_EXIT",
                "peer": peer_config,
            }

        containers.append(
            {
                "instance_id": instance_id,
                "name": container_name,
                "tf_name": tf_name,
                "image": str(runtime.get("image", "")).strip(),
                "root_dir": str(runtime.get("root_dir", "")).strip(),
                "start_on_boot": bool(runtime.get("start_on_boot", True)),
                "logging": bool(runtime.get("logging", True)),
                "comment": comment,
                "veth_name": veth_name,
                "veth_address": veth_address,
                "veth_gateway": veth_gateway,
                "envs": envs,
                "wireguard_interface": wireguard_interface,
                "managed_by_ref": host_ref,
            }
        )

    return sorted(containers, key=lambda c: c.get("name", ""))


class MikrotikContainersCompiler(CompilerPlugin):
    """Derives MikroTik container attachment/publication shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        container_rows = instances.get("routeros_container", []) if isinstance(instances, dict) else []
        if not isinstance(devices, list):
            devices = []
        if not isinstance(container_rows, list):
            container_rows = []

        if not isinstance(enforcer_resolution, dict):
            enforcer_resolution = {}

        router_ids: set[str] = set()
        for row in devices:
            if not isinstance(row, dict):
                continue
            instance_id = row.get("instance_id")
            if _is_mikrotik_enforcer(instance_id, enforcer_resolution):
                router_ids.add(instance_id)

        containers = _extract_containers(container_rows, router_ids)

        diagnostics.append(
            self.emit_diagnostic(
                code="I4212",
                severity="info",
                stage=stage,
                message=f"Derived {len(containers)} MikroTik container(s)",
                path="plugin:object.mikrotik.compiler.containers",
            )
        )

        ctx.publish("containers", containers)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"containers": containers},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize, order 60). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)
