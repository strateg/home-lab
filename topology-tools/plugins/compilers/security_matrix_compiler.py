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

    # An address domain is anything that carries a prefix and can belong to a
    # trust zone. A VLAN is one kind; a bridge is another; an overlay tunnel
    # network is a third once it is declarable. ADR 0118 AD-04 generalizes VLAN
    # into this concept, and selecting by it is what lets the set grow without
    # every consumer learning a new identifier prefix.
    _ADDRESS_DOMAIN_CLASSES = ("class.network.vlan",)

    @staticmethod
    def _class_of(row: dict) -> str | None:
        """The row's class id, from whichever shape the stage provides.

        `normalized_rows` carry `class_ref` as a string; an effective-model row
        carries a resolved `class` payload whose `lineage` ends with the id.
        Reading only one of them silently matches nothing in the other stage.
        """
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and class_ref:
            return class_ref
        payload = row.get("class")
        if isinstance(payload, dict):
            lineage = payload.get("lineage")
            if isinstance(lineage, list) and lineage:
                return lineage[-1]
        return None

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Build security matrices from inst.security_matrix.* instances."""
        diagnostics: list[PluginDiagnostic] = []

        # Get normalized rows from instance_rows compiler
        rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
        if not rows or not isinstance(rows, list):
            return self.make_result(diagnostics=diagnostics)

        # Build indices for zones, address domains, and security matrices
        zone_index: dict[str, dict[str, Any]] = {}  # zone instance -> {security_level, isolated, name}
        vlan_zone_map: dict[str, str] = {}  # address domain -> trust_zone_ref
        vlan_cidr_map: dict[str, str] = {}  # address domain -> cidr
        matrix_instances: list[dict[str, Any]] = []  # security matrix rows

        # First pass: Build indices
        #
        # Selection is by declared class, not by the shape of the instance id.
        # The prefix form read `inst.vlan.` and so could only ever see VLANs whose
        # author happened to name them that way, and could never see an overlay
        # network that is an address domain without being a VLAN - which is the
        # W05 divergence: two trust zones carry `additional_networks` precisely
        # because there was no way to declare them as domains.
        #
        # Measured before the change: both selectors return the same 10 instances
        # on the current topology, so this moves no artifact today. What it
        # removes is the dependency on identifier shape.
        for row in rows:
            instance_id = row.get("instance", "") or row.get("instance_id", "")
            if not isinstance(instance_id, str):
                continue

            class_ref = self._class_of(row)
            extensions = row.get("extensions", {})
            if not isinstance(extensions, dict):
                extensions = {}

            # Index trust zones with security_level and isolated properties
            if class_ref == "class.network.trust_zone":
                zone_data = self._extract_zone_data(row, extensions, ctx)
                if zone_data:
                    zone_index[instance_id] = zone_data

            # Index address domains with their trust_zone_ref
            elif class_ref in self._ADDRESS_DOMAIN_CLASSES:
                trust_zone_ref = extensions.get("trust_zone_ref") or row.get("trust_zone_ref")
                if isinstance(trust_zone_ref, str):
                    vlan_zone_map[instance_id] = trust_zone_ref

                # Also capture CIDR for address lists
                cidr = self._extract_vlan_cidr(row, extensions, ctx)
                if cidr:
                    vlan_cidr_map[instance_id] = cidr

            # Collect security matrix instances
            elif class_ref == "class.network.security_matrix":
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

        # Process each security matrix instance, in a stable order so that
        # security_matrices and scopes_by_enforcer below do not depend on the
        # order normalized_rows happened to arrive in (ADR 0119 D4).
        matrix_instances.sort(key=lambda row: str(row.get("instance") or row.get("instance_id") or ""))

        security_matrices: dict[str, dict[str, Any]] = {}
        # (enforcer_id, scope_id) pairs for every scope that passed attribution
        # and plane validation. Grouped into scopes_by_enforcer after the loop,
        # once every pair is known, so the published index is never built by
        # overwriting one entry per enforcer (ADR 0119 D1.1: one enforcer may
        # hold several scopes).
        enforcer_scope_pairs: list[tuple[str, str]] = []

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

            # Extract managed_by_ref for enforcer attribution. Required by the
            # class schema; an unattributed scope is enforced by nobody and,
            # before this check, compiled clean and said nothing (ADR 0118
            # analysis N-05). status: disabled is the one declared exemption -
            # it is the only convention the topology already uses to mark a
            # scope as intentionally not active, and status is otherwise inert
            # everywhere else in the pipeline, so this does not invent a new
            # general disabled-skip contract, only exempts a diagnostic newly
            # added by this change from a row the author already marked so.
            row_status = str(matrix_row.get("status") or "").strip().lower()
            is_disabled = row_status == "disabled"
            managed_by_ref = extensions.get("managed_by_ref") or matrix_row.get("managed_by_ref")
            if not isinstance(managed_by_ref, str) or not managed_by_ref.strip():
                if not is_disabled:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7010",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Security matrix '{matrix_id}' declares no managed_by_ref. "
                                "A scope with no enforcer is enforced by nobody."
                            ),
                            path=f"instance:{matrix_id}.managed_by_ref",
                        )
                    )
                continue
            managed_by_ref = managed_by_ref.strip()

            # Extract enforcement_plane (perimeter or internal). No silent
            # default: the class schema makes this required, and a default
            # here was live only because every current instance happens to
            # declare it (ADR 0118 analysis, latent default finding).
            enforcement_plane = (
                extensions.get("enforcement_plane")
                or matrix_row.get("enforcement_plane")
                or self._get_object_property(matrix_row, "enforcement_plane", ctx)
            )
            if not isinstance(enforcement_plane, str) or not enforcement_plane.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7011",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Security matrix '{matrix_id}' declares no enforcement_plane, "
                            "and neither instance nor object supplies one."
                        ),
                        path=f"instance:{matrix_id}.enforcement_plane",
                    )
                )
                continue

            enforcer_scope_pairs.append((managed_by_ref, matrix_id))

            # Extract policy_overrides from object + instance (merged)
            policy_overrides = self._merge_policy_overrides(matrix_row, extensions, ctx)

            # Resolve zone properties, in a deterministic order.
            #
            # W05 divergence 2: the compiler sorted each zone's VLAN list and the
            # generator sorted nothing, so downstream order depended on row
            # iteration on one path and not the other. Sorting the zones as well
            # makes the published channel ordered throughout - and on the current
            # topology it reproduces the generator's own output exactly, which is
            # what makes the A24 cutover a parity step rather than a reshuffle.
            zones: dict[str, dict[str, Any]] = {}
            for zone_ref in sorted(zone_refs):
                if zone_ref in zone_index:
                    zone_data = zone_index[zone_ref]
                    zones[zone_ref] = {
                        "name": zone_data.get("name", zone_ref),
                        "security_level": zone_data.get("security_level", 0),
                        "isolated": zone_data.get("isolated", False),
                        "vlans": zone_vlans.get(zone_ref, []),
                        "cidrs": self._zone_cidrs(zone_data, zone_vlans.get(zone_ref, []), vlan_cidr_map),
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

        # Group scopes by enforcer: complete (every attributed scope appears)
        # and deterministic (sorted keys, sorted values) regardless of input
        # row order. One enforcer may hold several scopes (ADR 0119 D1.1);
        # W7012 flags that case because no current adapter renders it, not
        # because the model forbids it.
        scopes_by_grouped: dict[str, list[str]] = {}
        for enforcer_id, scope_id in enforcer_scope_pairs:
            scopes_by_grouped.setdefault(enforcer_id, []).append(scope_id)
        scopes_by_enforcer: dict[str, list[str]] = {
            enforcer_id: sorted(scope_ids) for enforcer_id, scope_ids in sorted(scopes_by_grouped.items())
        }
        for enforcer_id, scope_ids in scopes_by_enforcer.items():
            if len(scope_ids) > 1:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7012",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}' holds {len(scope_ids)} scopes: "
                            f"{', '.join(scope_ids)}. No current adapter renders more than one "
                            "scope per enforcer."
                        ),
                        path=f"instance:{enforcer_id}",
                    )
                )

        # Compose one validated plan per enforcer from its attributed scopes
        # (ADR 0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md
        # section 5c, D-COMP-1..4). This fulfils ADR 0119 D1's existing
        # requirement - composition across scopes sharing an enforcer is
        # validated, not assumed - rather than adding a new obligation.
        #
        # D-COMP-1: zone_refs must be pairwise disjoint across the scopes one
        # enforcer holds. A matrix cell for (from_zone, to_zone) can only
        # exist in a scope whose zone_refs names both, so disjointness makes a
        # cross-scope cell collision structurally impossible - there is no
        # equal-cells comparison to get subtly wrong. D-COMP-2: policy
        # override names must be unique per enforcer, since only names
        # rendered into the same Terraform root can collide at
        # routeros_ip_firewall_filter.zone_override_<name>. Both are refused,
        # not silently resolved: an enforcer with either violation gets no
        # composed plan published, the same as an unattributed scope gets no
        # index entry under E7010.
        composed_matrices_by_enforcer: dict[str, dict[str, Any]] = {}
        for enforcer_id, scope_ids in scopes_by_enforcer.items():
            scopes_for_enforcer = [security_matrices[scope_id] for scope_id in scope_ids]

            zone_ref_owner: dict[str, str] = {}
            has_conflict = False
            for scope in scopes_for_enforcer:
                scope_id = scope["instance_id"]
                for zone_ref in set(scope.get("zone_refs") or []):
                    owner = zone_ref_owner.get(zone_ref)
                    if owner is not None and owner != scope_id:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7013",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Zone '{zone_ref}' is claimed by both '{owner}' and '{scope_id}', "
                                    f"both attributed to enforcer '{enforcer_id}'. Scopes sharing an "
                                    "enforcer must have disjoint zone_refs."
                                ),
                                path=f"instance:{enforcer_id}.zone_refs",
                            )
                        )
                        has_conflict = True
                    else:
                        zone_ref_owner[zone_ref] = scope_id

            override_name_owner: dict[str, str] = {}
            for scope in scopes_for_enforcer:
                scope_id = scope["instance_id"]
                for override in scope.get("policy_overrides") or []:
                    if not isinstance(override, dict):
                        continue
                    name = override.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    owner = override_name_owner.get(name)
                    if owner is not None and owner != scope_id:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7014",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Policy override '{name}' is declared by both '{owner}' and "
                                    f"'{scope_id}', both attributed to enforcer '{enforcer_id}'. "
                                    "Override names must be unique per enforcer."
                                ),
                                path=f"instance:{enforcer_id}.policy_overrides",
                            )
                        )
                        has_conflict = True
                    else:
                        override_name_owner[name] = scope_id

            if has_conflict:
                continue

            composed_zones: dict[str, Any] = {}
            composed_matrix: dict[str, dict[str, Any]] = {}
            composed_overrides: list[dict[str, Any]] = []
            for scope in scopes_for_enforcer:
                composed_zones.update(scope.get("zones") or {})
                for from_zone, to_zones in (scope.get("matrix") or {}).items():
                    composed_matrix.setdefault(from_zone, {}).update(to_zones)
                composed_overrides.extend(scope.get("policy_overrides") or [])

            composed_matrices_by_enforcer[enforcer_id] = {
                "zones": composed_zones,
                "matrix": composed_matrix,
                "policy_overrides": composed_overrides,
                # The composing scope ids, in the same sorted order used to
                # build the plan. Lets a consumer label the composed plan
                # (e.g. a generated-file comment) without a second
                # subscription to scopes_by_enforcer for the same fact.
                "scope_ids": list(scope_ids),
            }

        # Publish for downstream plugins (validators, generators)
        ctx.publish("security_matrices", security_matrices)
        ctx.publish("zone_vlans", zone_vlans)
        ctx.publish("scopes_by_enforcer", scopes_by_enforcer)
        ctx.publish("composed_matrices_by_enforcer", composed_matrices_by_enforcer)
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

        # Overlay networks the zone declares directly: authored L2 intent that
        # extends the zone's address list beyond the domains referencing it. Two
        # trust zones use it for the WireGuard admin and road-warrior networks.
        #
        # W05 recorded this as the divergence between the two derivations: the
        # generator read it and the compiler did not, so cutting the generator
        # over to this channel would have deleted two address-list entries. That
        # is a reduction of matched sources, not a refactor, so the core learns
        # the field and the cutover becomes the parity step it was meant to be.
        additional = extensions.get("additional_networks")
        if additional is None:
            additional = row.get("additional_networks")
        overlay_cidrs = self._overlay_cidrs(additional)

        # Validate required field
        if security_level is None:
            return None

        return {
            "security_level": int(security_level) if security_level is not None else 0,
            "isolated": bool(isolated) if isolated is not None else False,
            "name": name or "",
            "additional_cidrs": overlay_cidrs,
        }

    @staticmethod
    def _overlay_cidrs(declared: Any) -> list[str]:
        """The CIDRs an `additional_networks` list contributes, in authored order.

        Order is preserved rather than sorted: these are appended after the
        domain CIDRs, and the rendered address list is what the divergence was
        measured against. Sorting here would be a second behaviour change hiding
        inside the first.
        """
        if not isinstance(declared, list):
            return []
        found: list[str] = []
        for entry in declared:
            if not isinstance(entry, dict):
                continue
            cidr = str(entry.get("cidr", "")).strip()
            if cidr and cidr not in found:
                found.append(cidr)
        return found

    @staticmethod
    def _zone_cidrs(
        zone_data: dict[str, Any], vlans: list[str], vlan_cidr_map: dict[str, str]
    ) -> list[str]:
        """Domain CIDRs first, then the zone's own overlays, deduplicated.

        The order matches what the generator produced, because the rendered
        address lists are what parity is measured against.
        """
        cidrs = [vlan_cidr_map[vlan] for vlan in vlans if vlan in vlan_cidr_map]
        for cidr in zone_data.get("additional_cidrs", []):
            if cidr not in cidrs:
                cidrs.append(cidr)
        return cidrs

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
