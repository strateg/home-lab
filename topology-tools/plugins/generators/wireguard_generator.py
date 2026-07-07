"""Generator plugin for WireGuard tunnel configurations.

Generates platform-specific WireGuard configurations:
- MikroTik RouterOS (.rsc scripts)
- Linux/Ubuntu (wg-quick .conf files)

Input: compiled topology with tunnel instances (obj.network.wireguard_tunnel)
Output: Configuration files for each tunnel endpoint
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.artifact_contract import (
    build_artifact_plan,
    build_generation_report,
    build_planned_output,
    compute_obsolete_entries,
    validate_contract_payloads,
    write_contract_artifacts,
)
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.capability_helpers import get_platform_type
from plugins.generators.projection_core import (
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_VM,
    _group_rows,
    _instance_groups,
    _resolved_object_ref,
)


class WireguardProjectionError(Exception):
    """Error building WireGuard projection from compiled model."""


def _decrypt_sops_file(secrets_path: Path) -> dict[str, Any]:
    """Decrypt SOPS-encrypted secrets file and return as dict."""
    import yaml

    if not secrets_path.exists():
        raise WireguardProjectionError(f"secrets file not found: {secrets_path}")

    try:
        result = subprocess.run(
            ["sops", "-d", str(secrets_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return yaml.safe_load(result.stdout) or {}
    except subprocess.CalledProcessError as e:
        raise WireguardProjectionError(f"failed to decrypt secrets: {e.stderr}") from e
    except yaml.YAMLError as e:
        raise WireguardProjectionError(f"invalid YAML in secrets: {e}") from e


def _resolve_device_public_ip(compiled: dict[str, Any], device_ref: str, secrets_root: Path) -> str | None:
    """Resolve public IP for a device from secrets or topology."""
    # Try to find in instance secrets
    secrets_path = secrets_root / "instances" / f"{device_ref}.yaml"
    if secrets_path.exists():
        try:
            secrets = _decrypt_sops_file(secrets_path)
            # Check for public_ip field or extract from OCI metadata
            if "public_ip" in secrets:
                return secrets["public_ip"]
        except WireguardProjectionError:
            pass

    # Fallback: try to find in compiled topology
    try:
        groups = _instance_groups(compiled)
    except Exception:
        return None

    # Search in devices and vm groups
    for group_name in [GROUP_DEVICES, GROUP_VM]:
        for inst in _group_rows(groups, canonical=group_name):
            inst_id = inst.get("instance_id", "")
            source_id = inst.get("source_id", "")
            if source_id == device_ref or inst_id == device_ref:
                # Check instance_data for OCI or network info
                inst_data = inst.get("instance_data", {})
                if isinstance(inst_data, dict):
                    # Check for explicit public_ip
                    if "public_ip" in inst_data:
                        return inst_data["public_ip"]
                    # Check OCI block
                    oci = inst_data.get("oci", {})
                    if isinstance(oci, dict) and oci.get("public_ip"):
                        # public_ip: true means we need dynamic lookup
                        pass
                    # Check network config
                    network = inst_data.get("network", {})
                    if isinstance(network, dict) and network.get("public_ip"):
                        return network["public_ip"]

    return None


def _load_object_properties(object_ref: str) -> dict[str, Any]:
    """Load properties from object module YAML file.

    Args:
        object_ref: Object reference (e.g., "obj.network.vlan.servers")

    Returns:
        Properties dict from object module, or empty dict if not found.
    """
    import yaml

    # Determine repo root from this file's location
    this_file = Path(__file__).resolve()
    # This file is at topology-tools/plugins/generators/wireguard_generator.py
    # Object modules are at topology/object-modules/<domain>/obj.<domain>.<name>.yaml
    repo_root = this_file.parents[3]
    object_modules_root = repo_root / "topology" / "object-modules"

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
        # Topology object modules use @-prefixed metadata keys; normalize before parsing
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


def _build_vlan_cidr_index(network_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Build VLAN instance_id -> CIDR index for reference resolution (ADR-0111).

    Args:
        network_rows: Network instance rows from compiled JSON.

    Returns:
        Dict mapping instance_id (e.g., "inst.vlan.servers") to CIDR (e.g., "10.0.30.0/24").
    """
    index: dict[str, str] = {}
    for row in network_rows:
        object_ref = _resolved_object_ref(row)
        if "vlan" not in object_ref:
            continue

        instance_id = str(row.get("instance_id", "")).strip()
        if not instance_id:
            continue

        # Get CIDR from instance_data first
        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            inst_data = {}
        cidr = str(inst_data.get("cidr", "")).strip()

        # Fallback to object module properties (load from disk)
        if not cidr:
            props = _load_object_properties(object_ref)
            cidr = str(props.get("cidr", "")).strip()

        if cidr:
            index[instance_id] = cidr

    return index


def _resolve_vlan_refs_to_cidrs(
    vlan_refs: list[Any],
    vlan_cidr_index: dict[str, str],
) -> list[str]:
    """Resolve VLAN references to their CIDRs (ADR-0111).

    Args:
        vlan_refs: List of VLAN instance refs (e.g., ["inst.vlan.lan", "inst.vlan.servers"])
        vlan_cidr_index: Mapping of instance_id -> CIDR

    Returns:
        List of resolved CIDRs (e.g., ["192.168.88.0/24", "10.0.30.0/24"])
    """
    cidrs: list[str] = []
    for ref in vlan_refs:
        if not isinstance(ref, str):
            continue
        ref = ref.strip()
        cidr = vlan_cidr_index.get(ref)
        if cidr:
            cidrs.append(cidr)
    return cidrs


def _resolve_endpoint_allowed_ips(
    endpoint: dict[str, Any],
    vlan_cidr_index: dict[str, str],
) -> dict[str, Any]:
    """Resolve allowed_vlan_refs in endpoint to allowed_ips (ADR-0111).

    Merges explicit allowed_ips with resolved allowed_vlan_refs.
    """
    if not isinstance(endpoint, dict):
        return endpoint

    # Start with explicit allowed_ips
    allowed_ips = list(endpoint.get("allowed_ips", []))

    # Resolve and append allowed_vlan_refs
    vlan_refs = endpoint.get("allowed_vlan_refs", [])
    if isinstance(vlan_refs, list):
        resolved = _resolve_vlan_refs_to_cidrs(vlan_refs, vlan_cidr_index)
        allowed_ips.extend(resolved)

    # Return updated endpoint
    return {**endpoint, "allowed_ips": allowed_ips}


def _resolve_vps_nat(
    vps_nat: dict[str, Any],
    vlan_cidr_index: dict[str, str],
) -> dict[str, Any]:
    """Resolve source_vlan_refs in vps_nat to source_networks and generate iptables rules (ADR-0111)."""
    if not isinstance(vps_nat, dict) or not vps_nat.get("enabled"):
        return vps_nat

    masquerade = vps_nat.get("masquerade", {})
    if not isinstance(masquerade, dict):
        return vps_nat

    # Resolve source_vlan_refs to CIDRs
    vlan_refs = masquerade.get("source_vlan_refs", [])
    source_networks: list[str] = []
    if isinstance(vlan_refs, list):
        source_networks = _resolve_vlan_refs_to_cidrs(vlan_refs, vlan_cidr_index)

    # Fallback to explicit source_networks if no refs
    if not source_networks:
        explicit = masquerade.get("source_networks", [])
        if isinstance(explicit, list):
            source_networks = [str(n) for n in explicit if isinstance(n, str)]

    # Generate iptables rules from resolved source_networks
    out_interface = masquerade.get("out_interface", "ens3")
    iptables_rules: list[str] = []

    if source_networks:
        # Forward rules
        iptables_rules.append(f"-I FORWARD 1 -i wg0 -o {out_interface} -j ACCEPT")
        iptables_rules.append(f"-I FORWARD 2 -i {out_interface} -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT")
        # NAT rules for each source network
        for cidr in source_networks:
            iptables_rules.append(f"-t nat -A POSTROUTING -s {cidr} -o {out_interface} -j MASQUERADE")

    return {
        **vps_nat,
        "masquerade": {
            **masquerade,
            "source_networks": source_networks,
        },
        "iptables_rules": iptables_rules,
    }


def build_wireguard_projection(
    compiled: dict[str, Any],
    *,
    secrets_root: Path,
) -> dict[str, Any]:
    """Build WireGuard projection from compiled topology.

    Returns:
        {
            "tunnels": [
                {
                    "instance_id": "inst.tunnel.wg-home-to-oci",
                    "tunnel_name": "wg0",
                    "tunnel_network": "10.100.0.0/30",
                    "endpoint_a": {...},
                    "endpoint_b": {...},
                    "secrets": {...},
                }
            ]
        }
    """
    groups = _instance_groups(compiled)
    network_instances = _group_rows(groups, canonical=GROUP_NETWORK)

    # Build VLAN CIDR index for reference resolution (ADR-0111)
    vlan_cidr_index = _build_vlan_cidr_index(network_instances)
    tunnels: list[dict[str, Any]] = []

    for inst in network_instances:
        object_ref = _resolved_object_ref(inst)
        if "wireguard_tunnel" not in object_ref:
            continue

        inst_id = inst.get("instance_id", "")
        inst_data = inst.get("instance_data", {})
        if not isinstance(inst_data, dict):
            inst_data = {}

        tunnel_name = inst_data.get("tunnel_name", "wg0")
        tunnel_network = inst_data.get("tunnel_network", "")
        # Resolve allowed_vlan_refs to allowed_ips (ADR-0111)
        endpoint_a = _resolve_endpoint_allowed_ips(inst_data.get("endpoint_a", {}), vlan_cidr_index)
        endpoint_b = _resolve_endpoint_allowed_ips(inst_data.get("endpoint_b", {}), vlan_cidr_index)
        secrets_ref = inst_data.get("secrets_ref", "")

        # Load tunnel secrets
        secrets: dict[str, Any] = {}
        if secrets_ref:
            # Convert secrets_ref like "secrets.tunnels.wg-home-to-oci" to path
            parts = secrets_ref.replace("secrets.", "").split(".")
            secrets_file = secrets_root / "/".join(parts[:-1]) / f"{parts[-1]}.yaml"
            if secrets_file.exists():
                try:
                    secrets = _decrypt_sops_file(secrets_file)
                except WireguardProjectionError:
                    # Silently continue - secrets are optional for dry-run
                    pass

        # Resolve public endpoints
        if isinstance(endpoint_b, dict) and endpoint_b.get("role") == "server":
            device_ref = endpoint_b.get("device_ref", "")
            # First try device-level secrets
            public_ip = _resolve_device_public_ip(compiled, device_ref, secrets_root)
            # Fallback to tunnel secrets (vps.public_ip)
            if not public_ip and secrets:
                public_ip = secrets.get("vps", {}).get("public_ip")
            if public_ip:
                endpoint_b = {**endpoint_b, "public_endpoint": public_ip}

        # Resolve source_vlan_refs in vps_nat and generate iptables rules (ADR-0111)
        vps_nat = _resolve_vps_nat(inst_data.get("vps_nat", {}), vlan_cidr_index)

        tunnels.append(
            {
                "instance_id": inst_id,
                "tunnel_name": tunnel_name,
                "tunnel_network": tunnel_network,
                "endpoint_a": endpoint_a,
                "endpoint_b": endpoint_b,
                "routing": inst_data.get("routing", {}),
                "firewall": inst_data.get("firewall", {}),
                "vps_nat": vps_nat,
                "secrets": secrets,
                "mtu": inst_data.get("mtu", 1420),
                "keepalive_interval": inst_data.get("keepalive_interval", 25),
            }
        )

    return {"tunnels": tunnels}


class WireguardGenerator(BaseGenerator):
    """Generate WireGuard configurations for MikroTik and Linux endpoints."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json

        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9401",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate WireGuard configs.",
                    path="generator:wireguard",
                )
            )
            return self.make_result(diagnostics)

        # Resolve secrets root from project path
        # project_root is already the project directory (e.g., projects/home-lab)
        project_root = Path(ctx.config.get("project_root", "."))
        secrets_root = project_root / "secrets"

        try:
            projection = build_wireguard_projection(payload, secrets_root=secrets_root)
        except WireguardProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9402",
                    severity="error",
                    stage=stage,
                    message=f"failed to build wireguard projection: {exc}",
                    path="generator:wireguard",
                )
            )
            return self.make_result(diagnostics)

        tunnels = projection.get("tunnels", [])
        if not tunnels:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9401",
                    severity="info",
                    stage=stage,
                    message="no WireGuard tunnels found in topology",
                    path="generator:wireguard",
                )
            )
            # Snapshot contract: declared produces must be published even on skip.
            ctx.publish("generated_files", [])
            ctx.publish("wireguard_configs", [])
            return self.make_result(diagnostics)

        out_root = self.resolve_output_path(ctx, "wireguard")
        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []

        for tunnel in tunnels:
            tunnel_name = tunnel.get("tunnel_name", "wg0")
            secrets = tunnel.get("secrets", {})
            endpoint_a = tunnel.get("endpoint_a", {})
            endpoint_b = tunnel.get("endpoint_b", {})

            # Skip tunnel if secrets are missing (passthrough mode or missing secrets files)
            mikrotik_keys = secrets.get("mikrotik", {})
            vps_keys = secrets.get("vps", {})
            if not mikrotik_keys.get("private_key") or not vps_keys.get("private_key"):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="I9402",
                        severity="info",
                        stage=stage,
                        message=f"skipping tunnel '{tunnel.get('instance_id')}': missing required secrets (mikrotik.private_key or vps.private_key)",
                        path=f"generator:wireguard:{tunnel_name}",
                    )
                )
                continue

            # Determine endpoint platforms
            endpoint_a_platform = self._detect_platform(payload, endpoint_a.get("device_ref", ""))
            endpoint_b_platform = self._detect_platform(payload, endpoint_b.get("device_ref", ""))

            template_ctx = {
                "tunnel": tunnel,
                "tunnel_name": tunnel_name,
                "tunnel_network": tunnel.get("tunnel_network", ""),
                "mtu": tunnel.get("mtu", 1420),
                "keepalive": tunnel.get("keepalive_interval", 25),
                "endpoint_a": endpoint_a,
                "endpoint_b": endpoint_b,
                "routing": tunnel.get("routing", {}),
                "vps_nat": tunnel.get("vps_nat", {}),
                "secrets": secrets,
                "mikrotik_keys": mikrotik_keys,
                "vps_keys": vps_keys,
                "psk": secrets.get("preshared_key", ""),
            }

            # Generate MikroTik config (endpoint_a)
            if endpoint_a_platform == "mikrotik":
                mikrotik_path = out_root / f"mikrotik-{tunnel_name}.rsc"
                planned_outputs.append(
                    build_planned_output(
                        path=str(mikrotik_path),
                        renderer="jinja2",
                        reason="base-family",
                    )
                )
                content = self.render_template(ctx, "wireguard/mikrotik.rsc.j2", template_ctx)
                self.write_text_atomic(mikrotik_path, content)
                written.append(str(mikrotik_path))

            # Generate Linux config (endpoint_b)
            if endpoint_b_platform == "linux":
                linux_path = out_root / f"vps-{tunnel_name}.conf"
                planned_outputs.append(
                    build_planned_output(
                        path=str(linux_path),
                        renderer="jinja2",
                        reason="base-family",
                    )
                )
                content = self.render_template(ctx, "wireguard/linux.conf.j2", template_ctx)
                self.write_text_atomic(linux_path, content)
                written.append(str(linux_path))

            # Generate README
            readme_path = out_root / "README.md"
            planned_outputs.append(
                build_planned_output(
                    path=str(readme_path),
                    renderer="jinja2",
                    reason="base-family",
                )
            )
            content = self.render_template(ctx, "wireguard/README.md.j2", {"tunnels": tunnels})
            self.write_text_atomic(readme_path, content)
            written.append(str(readme_path))

        # Artifact contract handling
        artifact_family = "wireguard.configs"
        obsolete_entries, obsolete_errors = compute_obsolete_entries(
            ctx=ctx,
            plugin_id=self.plugin_id,
            output_root=out_root,
            planned_outputs=planned_outputs,
        )
        if obsolete_errors:
            for message in obsolete_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9403",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:wireguard:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        artifact_plan = build_artifact_plan(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            projection_version="1.0",
            ir_version="1.0",
            obsolete_candidates=obsolete_entries,
            validation_profiles=[ctx.profile],
            ctx=ctx,
        )
        artifact_generation_report = build_generation_report(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            generated=written,
            obsolete=obsolete_entries,
            ctx=ctx,
        )
        contract_validation_errors = validate_contract_payloads(
            artifact_plan=artifact_plan,
            generation_report=artifact_generation_report,
            ctx=ctx,
        )
        if contract_validation_errors:
            for message in contract_validation_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9404",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:wireguard:artifact_contract",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        contract_paths = write_contract_artifacts(
            ctx=ctx,
            plugin_id=self.plugin_id,
            artifact_plan=artifact_plan,
            generation_report=artifact_generation_report,
        )

        diagnostics.append(
            self.emit_diagnostic(
                code="I9402",
                severity="info",
                stage=stage,
                message=f"generated WireGuard configs: tunnels={len(tunnels)}, files={len(written)}",
                path=str(out_root),
            )
        )

        ctx.publish("generated_dir", str(out_root))
        ctx.publish("generated_files", written)
        ctx.publish("wireguard_configs", written)
        ctx.publish("artifact_plan", artifact_plan)
        ctx.publish("artifact_generation_report", artifact_generation_report)
        ctx.publish("artifact_contract_files", sorted(contract_paths.values()))

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "wireguard_dir": str(out_root),
                "wireguard_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
            },
        )

    def _detect_platform(self, compiled: dict[str, Any], device_ref: str) -> str:
        """Detect platform type for a device using capability checks (ADR 0106).

        Uses get_platform_type() from capability_helpers instead of string matching.
        """
        try:
            groups = _instance_groups(compiled)
        except Exception:
            return "unknown"

        # Search in devices and vm groups
        for group_name in [GROUP_DEVICES, GROUP_VM]:
            for inst in _group_rows(groups, canonical=group_name):
                inst_id = inst.get("instance_id", "")
                source_id = inst.get("source_id", "")
                if source_id == device_ref or inst_id == device_ref:
                    # ADR 0106: Use capability-based platform detection
                    obj = inst.get("object", {})
                    if isinstance(obj, dict):
                        return get_platform_type(obj)
                    # Fallback: check instance data for capabilities
                    return get_platform_type(inst)

        return "unknown"

    def on_post(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Lifecycle hook for post phase."""
        return self.execute(ctx, stage)
