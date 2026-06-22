"""IP address derivation compiler plugin (ADR 0111).

This plugin derives IP addresses from vlan_ref + host pattern:
- Resolves vlan_ref → VLAN instance CIDR
- Computes _resolved_ip and _resolved_gateway
- Validates host uniqueness and reserved gateway
- Emits warnings for deprecated hardcoded IP patterns

Runs in COMPILE stage after instance_rows, before effective_model.
"""

from __future__ import annotations

import ipaddress
from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class IpDerivationCompiler(CompilerPlugin):
    """Derives IP addresses from vlan_ref + host pattern (ADR 0111)."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Derive IP addresses and validate host assignments."""
        diagnostics: list[PluginDiagnostic] = []

        # Get normalized rows from instance_rows compiler
        rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
        if not rows or not isinstance(rows, list):
            return self.make_result(diagnostics=diagnostics)

        # Build VLAN CIDR index for resolution
        # CIDR can be in instance extensions, instance root, or inherited from object
        vlan_cidrs: dict[str, str] = {}
        for row in rows:
            instance_id = row.get("instance", "") or row.get("instance_id", "")
            if instance_id.startswith("inst.vlan."):
                cidr = None
                # Check instance extensions first
                extensions = row.get("extensions", {})
                if isinstance(extensions, dict):
                    cidr = extensions.get("cidr")
                # Check instance root
                if not cidr:
                    cidr = row.get("cidr")
                # Check object properties (inherited CIDR)
                if not cidr:
                    object_ref = row.get("object_ref", "")
                    if object_ref:
                        object_data = ctx.objects.get(object_ref, {})
                        if isinstance(object_data, dict):
                            props = object_data.get("properties", {})
                            if isinstance(props, dict):
                                cidr = props.get("cidr")
                if cidr:
                    vlan_cidrs[instance_id] = cidr

        # Host registry for duplicate detection: vlan_ref -> {host -> instance_id}
        host_registry: dict[str, dict[int, str]] = {}

        # Process rows with network field (in extensions)
        resolved_count = 0
        warning_count = 0

        for row in rows:
            instance_id = row.get("instance", "") or row.get("instance_id", "")
            extensions = row.get("extensions", {})
            if not isinstance(extensions, dict):
                continue
            network = extensions.get("network")
            if not isinstance(network, dict):
                continue

            path = f"instance:{instance_id}"
            vlan_ref = network.get("vlan_ref")
            host = network.get("host")
            hardcoded_ip = network.get("ip")

            # Case 1: vlan_ref + host pattern (ADR 0111 canonical)
            if vlan_ref and host is not None:
                # Validate no mixed patterns
                if hardcoded_ip:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7865",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Instance '{instance_id}' mixes vlan_ref/host with "
                                f"hardcoded ip. Use one pattern only."
                            ),
                            path=f"{path}.network",
                        )
                    )
                    continue

                # Validate host not reserved (gateway)
                if host == 1:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7862",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Instance '{instance_id}' uses host: 1 which is "
                                f"reserved for VLAN gateway."
                            ),
                            path=f"{path}.network.host",
                        )
                    )
                    continue

                # Validate host uniqueness within vlan_ref
                if vlan_ref not in host_registry:
                    host_registry[vlan_ref] = {}

                if host in host_registry[vlan_ref]:
                    existing = host_registry[vlan_ref][host]
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7861",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Duplicate host {host} in {vlan_ref}: "
                                f"'{instance_id}' conflicts with '{existing}'."
                            ),
                            path=f"{path}.network.host",
                        )
                    )
                    continue

                host_registry[vlan_ref][host] = instance_id

                # Resolve IP from VLAN CIDR
                cidr = vlan_cidrs.get(vlan_ref)
                if not cidr:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7866",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Instance '{instance_id}' references unknown VLAN "
                                f"'{vlan_ref}' or VLAN has no CIDR."
                            ),
                            path=f"{path}.network.vlan_ref",
                        )
                    )
                    continue

                # Compute resolved IP and gateway
                resolved_ip, resolved_gw = self._resolve_ip(cidr, host)
                if resolved_ip:
                    # Validate host within CIDR range
                    try:
                        net = ipaddress.IPv4Network(cidr, strict=False)
                        if host < 1 or host > net.num_addresses - 2:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E7863",
                                    severity="error",
                                    stage=stage,
                                    message=(
                                        f"Instance '{instance_id}' host {host} exceeds "
                                        f"VLAN CIDR {cidr} range (1-{net.num_addresses - 2})."
                                    ),
                                    path=f"{path}.network.host",
                                )
                            )
                            continue
                    except ValueError:
                        pass  # Invalid CIDR handled elsewhere

                    network["_resolved_ip"] = resolved_ip
                    network["_resolved_gateway"] = resolved_gw
                    resolved_count += 1

            # Case 2: Hardcoded IP pattern (deprecated)
            elif hardcoded_ip and not vlan_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7864",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Instance '{instance_id}' uses hardcoded IP '{hardcoded_ip}'. "
                            f"Migrate to vlan_ref + host pattern (ADR 0111)."
                        ),
                        path=f"{path}.network.ip",
                    )
                )
                warning_count += 1

        # Publish stats
        ctx.publish(
            "ip_derivation_stats",
            {
                "resolved_count": resolved_count,
                "warning_count": warning_count,
                "vlan_count": len(vlan_cidrs),
            },
        )

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "resolved_count": resolved_count,
                "warning_count": warning_count,
            },
        )

    @staticmethod
    def _resolve_ip(cidr: str, host: int) -> tuple[str | None, str | None]:
        """Resolve IP address from CIDR and host number.

        Args:
            cidr: VLAN CIDR (e.g., "10.0.30.0/24")
            host: Host number (e.g., 10)

        Returns:
            Tuple of (resolved_ip, resolved_gateway) or (None, None) on error.
        """
        try:
            # Parse CIDR
            network_part, prefix = cidr.rsplit("/", 1)
            octets = network_part.rsplit(".", 1)
            if len(octets) != 2:
                return None, None

            base = octets[0]
            resolved_ip = f"{base}.{host}/{prefix}"
            resolved_gw = f"{base}.1"
            return resolved_ip, resolved_gw
        except (ValueError, IndexError):
            return None, None
