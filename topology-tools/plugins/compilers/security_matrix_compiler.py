"""Security matrix compiler plugin (ADR 0110).

This plugin computes the zone-to-zone security matrix:
- Resolves zone_refs to trust_zone instances with security_level/isolated
- Builds zone_vlans mapping from VLAN trust_zone_ref
- Calculates matrix cells using R1-R6 rules
- Merges policy_overrides from object + instance levels

Runs in COMPILE stage after instance_rows, before effective_model.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class SecurityMatrixCompiler(CompilerPlugin):
    """Computes zone-to-zone security matrix (ADR 0110)."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Build security matrices from inst.security_matrix.* instances."""
        diagnostics: list[PluginDiagnostic] = []

        # Get normalized rows from instance_rows compiler
        rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
        if not rows or not isinstance(rows, list):
            return self.make_result(diagnostics=diagnostics)

        # Build indices for zones, VLANs, and security matrices
        zone_index: dict[str, dict[str, Any]] = {}  # inst.trust_zone.* -> {security_level, isolated, name}
        vlan_zone_map: dict[str, str] = {}  # inst.vlan.* -> trust_zone_ref
        vlan_cidr_map: dict[str, str] = {}  # inst.vlan.* -> cidr
        matrix_instances: list[dict[str, Any]] = []  # inst.security_matrix.* rows

        # First pass: Build indices
        for row in rows:
            instance_id = row.get("instance", "") or row.get("instance_id", "")
            if not isinstance(instance_id, str):
                continue

            extensions = row.get("extensions", {})
            if not isinstance(extensions, dict):
                extensions = {}

            # Index trust zones with security_level and isolated properties
            if instance_id.startswith("inst.trust_zone."):
                zone_data = self._extract_zone_data(row, extensions, ctx)
                if zone_data:
                    zone_index[instance_id] = zone_data

            # Index VLANs with their trust_zone_ref
            elif instance_id.startswith("inst.vlan."):
                trust_zone_ref = extensions.get("trust_zone_ref") or row.get("trust_zone_ref")
                if isinstance(trust_zone_ref, str):
                    vlan_zone_map[instance_id] = trust_zone_ref

                # Also capture CIDR for address lists
                cidr = self._extract_vlan_cidr(row, extensions, ctx)
                if cidr:
                    vlan_cidr_map[instance_id] = cidr

            # Collect security matrix instances
            elif instance_id.startswith("inst.security_matrix."):
                matrix_instances.append(row)

        # Build zone_vlans mapping: zone_ref -> [vlan_refs]
        zone_vlans: dict[str, list[str]] = {}
        for vlan_ref, zone_ref in vlan_zone_map.items():
            if zone_ref not in zone_vlans:
                zone_vlans[zone_ref] = []
            zone_vlans[zone_ref].append(vlan_ref)

        # Sort VLAN lists for deterministic output
        for zone_ref in zone_vlans:
            zone_vlans[zone_ref].sort()

        # Process each security matrix instance
        security_matrices: dict[str, dict[str, Any]] = {}
        matrix_by_enforcer: dict[str, str] = {}

        for matrix_row in matrix_instances:
            matrix_id = matrix_row.get("instance", "") or matrix_row.get("instance_id", "")
            if not matrix_id:
                continue

            extensions = matrix_row.get("extensions", {})
            if not isinstance(extensions, dict):
                extensions = {}

            # Extract zone_refs from instance or object
            zone_refs = self._extract_zone_refs(matrix_row, extensions, ctx)
            if not zone_refs:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7870",
                        severity="warning",
                        stage=stage,
                        message=f"Security matrix '{matrix_id}' has no zone_refs.",
                        path=f"instance:{matrix_id}",
                    )
                )
                continue

            # Extract managed_by_ref for enforcer mapping
            managed_by_ref = extensions.get("managed_by_ref") or matrix_row.get("managed_by_ref")
            if isinstance(managed_by_ref, str):
                matrix_by_enforcer[managed_by_ref] = matrix_id

            # Extract enforcement_plane (perimeter or internal)
            enforcement_plane = (
                extensions.get("enforcement_plane")
                or matrix_row.get("enforcement_plane")
                or self._get_object_property(matrix_row, "enforcement_plane", ctx)
                or "perimeter"
            )

            # Extract policy_overrides from object + instance (merged)
            policy_overrides = self._merge_policy_overrides(matrix_row, extensions, ctx)

            # Resolve zone properties
            zones: dict[str, dict[str, Any]] = {}
            for zone_ref in zone_refs:
                if zone_ref in zone_index:
                    zone_data = zone_index[zone_ref]
                    zones[zone_ref] = {
                        "name": zone_data.get("name", zone_ref),
                        "security_level": zone_data.get("security_level", 0),
                        "isolated": zone_data.get("isolated", False),
                        "vlans": zone_vlans.get(zone_ref, []),
                        "cidrs": [vlan_cidr_map[v] for v in zone_vlans.get(zone_ref, []) if v in vlan_cidr_map],
                    }
                else:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7852",
                            severity="error",
                            stage=stage,
                            message=f"Security matrix '{matrix_id}' references unknown zone '{zone_ref}'.",
                            path=f"instance:{matrix_id}.zone_refs",
                        )
                    )

            # Calculate matrix cells using R1-R6 rules
            matrix_cells = self._calculate_matrix(
                zones=zones,
                policy_overrides=policy_overrides,
                enforcement_plane=enforcement_plane,
            )

            # Build matrix statistics
            stats = self._compute_statistics(matrix_cells, policy_overrides)

            # Store compiled matrix
            security_matrices[matrix_id] = {
                "instance_id": matrix_id,
                "enforcement_plane": enforcement_plane,
                "managed_by_ref": managed_by_ref,
                "zones": zones,
                "zone_refs": zone_refs,
                "matrix": matrix_cells,
                "policy_overrides": policy_overrides,
                "statistics": stats,
            }

        # Publish for downstream plugins (validators, generators)
        ctx.publish("security_matrices", security_matrices)
        ctx.publish("zone_vlans", zone_vlans)
        ctx.publish("matrix_by_enforcer", matrix_by_enforcer)
        ctx.publish("vlan_cidr_map", vlan_cidr_map)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "matrix_count": len(security_matrices),
                "zone_count": len(zone_index),
                "vlan_zone_count": len(vlan_zone_map),
            },
        )

    def _extract_zone_data(
        self,
        row: dict[str, Any],
        extensions: dict[str, Any],
        ctx: PluginContext,
    ) -> dict[str, Any] | None:
        """Extract security_level and isolated from trust_zone instance/object."""
        # Try instance extensions first
        security_level = extensions.get("security_level")
        isolated = extensions.get("isolated")
        name = extensions.get("name")

        # Try row root
        if security_level is None:
            security_level = row.get("security_level")
        if isolated is None:
            isolated = row.get("isolated")
        if name is None:
            name = row.get("name")

        # Fall back to object properties
        object_ref = row.get("object_ref", "")
        if object_ref and isinstance(object_ref, str):
            object_data = ctx.objects.get(object_ref, {})
            if isinstance(object_data, dict):
                props = object_data.get("properties", {})
                if isinstance(props, dict):
                    if security_level is None:
                        security_level = props.get("security_level")
                    if isolated is None:
                        isolated = props.get("isolated")
                    if name is None:
                        name = props.get("name")

        # Validate required field
        if security_level is None:
            return None

        return {
            "security_level": int(security_level) if security_level is not None else 0,
            "isolated": bool(isolated) if isolated is not None else False,
            "name": name or "",
        }

    def _extract_vlan_cidr(
        self,
        row: dict[str, Any],
        extensions: dict[str, Any],
        ctx: PluginContext,
    ) -> str | None:
        """Extract CIDR from VLAN instance/object."""
        cidr = extensions.get("cidr") or row.get("cidr")
        if cidr:
            return str(cidr)

        # Fall back to object properties
        object_ref = row.get("object_ref", "")
        if object_ref and isinstance(object_ref, str):
            object_data = ctx.objects.get(object_ref, {})
            if isinstance(object_data, dict):
                props = object_data.get("properties", {})
                if isinstance(props, dict):
                    cidr = props.get("cidr")
                    if cidr:
                        return str(cidr)
        return None

    def _extract_zone_refs(
        self,
        row: dict[str, Any],
        extensions: dict[str, Any],
        ctx: PluginContext,
    ) -> list[str]:
        """Extract zone_refs from security_matrix instance, falling back to object."""
        zone_refs = extensions.get("zone_refs") or row.get("zone_refs")

        # Fall back to object
        if not zone_refs:
            object_ref = row.get("object_ref", "")
            if object_ref and isinstance(object_ref, str):
                object_data = ctx.objects.get(object_ref, {})
                if isinstance(object_data, dict):
                    zone_refs = object_data.get("zone_refs")

        if isinstance(zone_refs, list):
            # Resolve object-level refs to instance-level if needed
            resolved = []
            for ref in zone_refs:
                if isinstance(ref, str):
                    # If it's an object ref like obj.network.trust_zone.*,
                    # it should already be resolved by the instance
                    # For now, assume instance-level refs are provided
                    resolved.append(ref)
            return resolved

        return []

    def _get_object_property(
        self,
        row: dict[str, Any],
        prop_name: str,
        ctx: PluginContext,
    ) -> Any:
        """Get a property from the object level."""
        object_ref = row.get("object_ref", "")
        if object_ref and isinstance(object_ref, str):
            object_data = ctx.objects.get(object_ref, {})
            if isinstance(object_data, dict):
                return object_data.get(prop_name)
        return None

    def _merge_policy_overrides(
        self,
        row: dict[str, Any],
        extensions: dict[str, Any],
        ctx: PluginContext,
    ) -> list[dict[str, Any]]:
        """Merge policy_overrides from object + instance levels."""
        result: list[dict[str, Any]] = []

        # Object-level policy_overrides
        object_ref = row.get("object_ref", "")
        if object_ref and isinstance(object_ref, str):
            object_data = ctx.objects.get(object_ref, {})
            if isinstance(object_data, dict):
                obj_overrides = object_data.get("policy_overrides")
                if isinstance(obj_overrides, list):
                    for override in obj_overrides:
                        if isinstance(override, dict):
                            result.append(dict(override))

        # Instance-level policy_overrides (added on top)
        inst_overrides = extensions.get("policy_overrides") or row.get("policy_overrides")
        if isinstance(inst_overrides, list):
            for override in inst_overrides:
                if isinstance(override, dict):
                    result.append(dict(override))

        return result

    def _calculate_matrix(
        self,
        zones: dict[str, dict[str, Any]],
        policy_overrides: list[dict[str, Any]],
        enforcement_plane: str,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Calculate matrix cells using R1-R6 rules.

        Rule Evaluation Order (from ADR 0110):
            R6 (explicit override) → checked FIRST
                   ↓ (no match)
            R1 (same zone) → ALLOW
                   ↓ (different zones)
            R2 (isolated source) → DENY if dest != untrusted
                   ↓
            R3/R4/R5 (security level) → ALLOW downhill, DENY uphill/same
        """
        matrix: dict[str, dict[str, dict[str, Any]]] = {}

        zone_refs = list(zones.keys())

        for from_zone in zone_refs:
            matrix[from_zone] = {}
            from_data = zones[from_zone]
            from_level = from_data.get("security_level", 0)
            from_isolated = from_data.get("isolated", False)

            for to_zone in zone_refs:
                to_data = zones[to_zone]
                to_level = to_data.get("security_level", 0)
                to_name = to_data.get("name", "")

                # R6: Check for explicit override FIRST
                override = self._find_policy_override(from_zone, to_zone, policy_overrides)
                if override:
                    matrix[from_zone][to_zone] = {
                        "action": override.get("action", "accept"),
                        "rule": "R6",
                        "reason": f"policy_override: {override.get('name', 'unnamed')}",
                        "log": override.get("log", False),
                        "ports": override.get("ports"),
                        "override_name": override.get("name"),
                    }
                    continue

                # R1: Same zone
                if from_zone == to_zone:
                    # R1a (perimeter): same zone = ALLOW
                    # R1b (internal): same zone = DENY by default (need overrides)
                    if enforcement_plane == "internal":
                        matrix[from_zone][to_zone] = {
                            "action": "deny",
                            "rule": "R1b",
                            "reason": "internal plane: same zone requires explicit override",
                            "log": True,
                        }
                    else:
                        matrix[from_zone][to_zone] = {
                            "action": "allow",
                            "rule": "R1",
                            "reason": "same zone",
                            "log": False,
                        }
                    continue

                # R2: Isolated source zone
                # Isolated zones can only reach untrusted (internet)
                if from_isolated:
                    # Check if destination is untrusted zone
                    is_untrusted = "untrusted" in to_zone.lower() or (
                        to_level == 0 and to_name.lower() == "untrusted zone"
                    )
                    if is_untrusted:
                        # R2: Isolated zone CAN reach untrusted = ALLOW
                        matrix[from_zone][to_zone] = {
                            "action": "allow",
                            "rule": "R2",
                            "reason": "isolated zone can reach untrusted (internet)",
                            "log": False,
                        }
                        continue
                    else:
                        # R2: Isolated zone CANNOT reach non-untrusted = DENY
                        matrix[from_zone][to_zone] = {
                            "action": "deny",
                            "rule": "R2",
                            "reason": f"isolated zone cannot reach {to_zone}",
                            "log": True,
                        }
                        continue

                # R3/R4/R5: Security level comparison
                if from_level > to_level:
                    # R3: Downhill (higher to lower) = ALLOW
                    matrix[from_zone][to_zone] = {
                        "action": "allow",
                        "rule": "R3",
                        "reason": f"downhill: level {from_level} → {to_level}",
                        "log": False,
                    }
                elif from_level < to_level:
                    # R4: Uphill (lower to higher) = DENY
                    matrix[from_zone][to_zone] = {
                        "action": "deny",
                        "rule": "R4",
                        "reason": f"uphill: level {from_level} → {to_level}",
                        "log": True,
                    }
                else:
                    # R5: Same level = DENY
                    matrix[from_zone][to_zone] = {
                        "action": "deny",
                        "rule": "R5",
                        "reason": f"same level {from_level}, no override",
                        "log": True,
                    }

        return matrix

    def _find_policy_override(
        self,
        from_zone: str,
        to_zone: str,
        policy_overrides: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Find matching policy_override for zone pair."""
        for override in policy_overrides:
            from_ref = override.get("from_zone_ref", "")
            to_ref = override.get("to_zone_ref", "")

            # Match exact refs or by suffix (inst. vs obj.)
            from_match = from_ref == from_zone or from_ref.split(".")[-1] == from_zone.split(".")[-1]
            to_match = to_ref == to_zone or to_ref.split(".")[-1] == to_zone.split(".")[-1]

            if from_match and to_match:
                return override

        return None

    def _compute_statistics(
        self,
        matrix: dict[str, dict[str, dict[str, Any]]],
        policy_overrides: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Compute matrix statistics."""
        allow_count = 0
        deny_count = 0
        override_count = len(policy_overrides)

        for from_cells in matrix.values():
            for cell in from_cells.values():
                action = cell.get("action", "")
                if action == "allow":
                    allow_count += 1
                elif action == "deny":
                    deny_count += 1

        return {
            "total_pairs": allow_count + deny_count,
            "allow": allow_count,
            "deny": deny_count,
            "override": override_count,
        }
