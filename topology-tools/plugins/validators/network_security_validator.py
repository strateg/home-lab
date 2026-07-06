"""Network security validator plugin (ADR 0110 + ADR 0111).

Validates network security configuration:
- E7850: VLAN ID collision
- E7851: CIDR overlap
- E7853: policy_override refs must exist
- W7855: Same security_level needs override
- W7856: Isolated zone override to non-untrusted
- W7860: Zone has no VLANs

Runs in VALIDATE stage, after security_matrix_compiler.
"""

from __future__ import annotations

import ipaddress
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


class NetworkSecurityValidator(ValidatorJsonPlugin):
    """Validates network security configuration (ADR 0110 + ADR 0111)."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Validate VLAN uniqueness, CIDR overlap, and security matrix completeness."""
        diagnostics: list[PluginDiagnostic] = []

        # Get normalized rows
        rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
        if not rows or not isinstance(rows, list):
            return self.make_result(diagnostics=diagnostics)

        # Get security matrices from compiler
        security_matrices = None
        try:
            security_matrices = ctx.subscribe("base.compiler.security_matrix", "security_matrices")
        except Exception:
            pass  # Optional - may not exist if no security_matrix instances

        zone_vlans = None
        try:
            zone_vlans = ctx.subscribe("base.compiler.security_matrix", "zone_vlans")
        except Exception:
            pass

        # Build VLAN index for collision detection
        vlan_ids: dict[int, list[str]] = {}  # vlan_id -> [instance_ids]
        vlan_cidrs: dict[str, tuple[str, str]] = {}  # instance_id -> (cidr_str, instance_id)

        for row in rows:
            instance_id = row.get("instance", "") or row.get("instance_id", "")
            if not isinstance(instance_id, str) or not instance_id.startswith("inst.vlan."):
                continue

            extensions = row.get("extensions", {})
            if not isinstance(extensions, dict):
                extensions = {}

            # Get VLAN ID
            vlan_id = extensions.get("vlan_id") or row.get("vlan_id")
            if vlan_id is None:
                # Try object properties
                object_ref = row.get("object_ref", "")
                if object_ref and isinstance(object_ref, str):
                    object_data = ctx.objects.get(object_ref, {})
                    if isinstance(object_data, dict):
                        props = object_data.get("properties", {})
                        if isinstance(props, dict):
                            vlan_id = props.get("vlan_id")

            if vlan_id is not None:
                vlan_id = int(vlan_id)
                if vlan_id not in vlan_ids:
                    vlan_ids[vlan_id] = []
                vlan_ids[vlan_id].append(instance_id)

            # Get CIDR
            cidr = extensions.get("cidr") or row.get("cidr")
            if cidr is None:
                object_ref = row.get("object_ref", "")
                if object_ref and isinstance(object_ref, str):
                    object_data = ctx.objects.get(object_ref, {})
                    if isinstance(object_data, dict):
                        props = object_data.get("properties", {})
                        if isinstance(props, dict):
                            cidr = props.get("cidr")

            if cidr:
                vlan_cidrs[instance_id] = (str(cidr), instance_id)

        # E7850: VLAN ID collision
        for vlan_id, instances in vlan_ids.items():
            if len(instances) > 1:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7850",
                        severity="error",
                        stage=stage,
                        message=(f"VLAN ID {vlan_id} is used by multiple instances: " f"{', '.join(instances)}."),
                        path=f"network:vlan_id:{vlan_id}",
                    )
                )

        # E7851: CIDR overlap detection
        cidr_list = list(vlan_cidrs.items())
        for i, (inst1, (cidr1_str, _)) in enumerate(cidr_list):
            try:
                net1 = ipaddress.IPv4Network(cidr1_str, strict=False)
            except ValueError:
                continue

            for inst2, (cidr2_str, _) in cidr_list[i + 1 :]:
                try:
                    net2 = ipaddress.IPv4Network(cidr2_str, strict=False)
                except ValueError:
                    continue

                if net1.overlaps(net2):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7851",
                            severity="error",
                            stage=stage,
                            message=(
                                f"VLAN CIDRs overlap: {inst1} ({cidr1_str}) " f"overlaps with {inst2} ({cidr2_str})."
                            ),
                            path=f"network:cidr_overlap",
                        )
                    )

        # Validate security matrices
        if isinstance(security_matrices, dict):
            for matrix_id, matrix_data in security_matrices.items():
                if not isinstance(matrix_data, dict):
                    continue

                policy_overrides = matrix_data.get("policy_overrides", [])
                zones = matrix_data.get("zones", {})
                matrix_cells = matrix_data.get("matrix", {})

                # Build zone index
                zone_refs = set(zones.keys()) if isinstance(zones, dict) else set()

                # E7853: policy_override refs must exist
                if isinstance(policy_overrides, list):
                    for override in policy_overrides:
                        if not isinstance(override, dict):
                            continue

                        from_ref = override.get("from_zone_ref", "")
                        to_ref = override.get("to_zone_ref", "")
                        name = override.get("name", "unnamed")

                        # Check from_zone_ref
                        from_found = any(
                            from_ref == z or from_ref.split(".")[-1] == z.split(".")[-1] for z in zone_refs
                        )
                        if not from_found and from_ref:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E7853",
                                    severity="error",
                                    stage=stage,
                                    message=(
                                        f"Policy override '{name}' in {matrix_id} "
                                        f"references unknown from_zone_ref '{from_ref}'."
                                    ),
                                    path=f"instance:{matrix_id}.policy_overrides",
                                )
                            )

                        # Check to_zone_ref
                        to_found = any(to_ref == z or to_ref.split(".")[-1] == z.split(".")[-1] for z in zone_refs)
                        if not to_found and to_ref:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E7853",
                                    severity="error",
                                    stage=stage,
                                    message=(
                                        f"Policy override '{name}' in {matrix_id} "
                                        f"references unknown to_zone_ref '{to_ref}'."
                                    ),
                                    path=f"instance:{matrix_id}.policy_overrides",
                                )
                            )

                # W7855: Same security_level needs override (warn if no override exists)
                if isinstance(zones, dict) and isinstance(matrix_cells, dict):
                    for from_zone, to_cells in matrix_cells.items():
                        if not isinstance(to_cells, dict):
                            continue
                        for to_zone, cell in to_cells.items():
                            if not isinstance(cell, dict):
                                continue
                            if cell.get("rule") == "R5":
                                # R5 means same security level, denied by default
                                # This is expected behavior, but warn if it might be unintentional
                                from_data = zones.get(from_zone, {})
                                to_data = zones.get(to_zone, {})
                                from_level = from_data.get("security_level", 0) if isinstance(from_data, dict) else 0
                                to_level = to_data.get("security_level", 0) if isinstance(to_data, dict) else 0
                                if from_level == to_level and from_level > 0:
                                    diagnostics.append(
                                        self.emit_diagnostic(
                                            code="W7855",
                                            severity="warning",
                                            stage=stage,
                                            message=(
                                                f"Zones {from_zone} and {to_zone} have same "
                                                f"security_level ({from_level}) - traffic denied "
                                                f"by default (R5). Add policy_override if needed."
                                            ),
                                            path=f"instance:{matrix_id}.matrix",
                                        )
                                    )

                # W7856: Isolated zone with override to non-untrusted
                if isinstance(zones, dict) and isinstance(policy_overrides, list):
                    for override in policy_overrides:
                        if not isinstance(override, dict):
                            continue

                        from_ref = override.get("from_zone_ref", "")
                        to_ref = override.get("to_zone_ref", "")
                        name = override.get("name", "unnamed")

                        # Find matching from_zone
                        from_zone_data = None
                        for zone_ref, zone_data in zones.items():
                            if from_ref == zone_ref or from_ref.split(".")[-1] == zone_ref.split(".")[-1]:
                                from_zone_data = zone_data
                                break

                        if isinstance(from_zone_data, dict) and from_zone_data.get("isolated"):
                            # Check if to_zone is untrusted
                            is_to_untrusted = "untrusted" in to_ref.lower()
                            if not is_to_untrusted:
                                diagnostics.append(
                                    self.emit_diagnostic(
                                        code="W7856",
                                        severity="warning",
                                        stage=stage,
                                        message=(
                                            f"Policy override '{name}' allows traffic from "
                                            f"isolated zone to non-untrusted zone '{to_ref}'. "
                                            f"This bypasses isolation (R2)."
                                        ),
                                        path=f"instance:{matrix_id}.policy_overrides",
                                    )
                                )

        # W7860: Zone has no VLANs
        if isinstance(zone_vlans, dict) and isinstance(security_matrices, dict):
            # Get all zones referenced in any matrix
            all_matrix_zones: set[str] = set()
            for matrix_data in security_matrices.values():
                if isinstance(matrix_data, dict):
                    zones = matrix_data.get("zones", {})
                    if isinstance(zones, dict):
                        all_matrix_zones.update(zones.keys())

            # Check if any zone has no VLANs
            for zone_ref in all_matrix_zones:
                if zone_ref not in zone_vlans or not zone_vlans[zone_ref]:
                    # Skip untrusted zone (no VLANs expected)
                    if "untrusted" in zone_ref.lower():
                        continue
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7860",
                            severity="warning",
                            stage=stage,
                            message=(f"Zone '{zone_ref}' is in security matrix but has no VLANs assigned."),
                            path=f"network:zone_vlans:{zone_ref}",
                        )
                    )

        return self.make_result(diagnostics=diagnostics)
