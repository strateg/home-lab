"""Nested topology scope validator (ADR 0087 Phase 5)."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class NestedTopologyScopeValidator(ValidatorJsonPlugin):
    """Validate nested topology scope declarations and references.

    This validator enforces ADR 0087 Phase 5 requirements:
    - AC-23: topology_scope property accepted on workload instances
    - AC-24: Scope reference resolution works (scope.* vs inst.*)
    - AC-25: Nesting depth > 2 rejected (delegated to host_ref_dag_validator)
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _WORKLOAD_CLASSES = {
        "class.compute.workload.lxc",
        "class.compute.workload.docker",
        "class.compute.workload.vm",
    }
    _SCOPE_PREFIX = "scope."

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7920",
                    severity="error",
                    stage=stage,
                    message=f"nested_topology_scope validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        # Build lookups
        row_by_id: dict[str, dict[str, Any]] = {}
        scope_by_id: dict[str, dict[str, Any]] = {}  # scope_id → workload row
        workloads_in_scope: dict[str, list[str]] = {}  # scope_id → list of workload IDs

        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # First pass: collect scope declarations
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref not in self._WORKLOAD_CLASSES:
                continue

            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            extensions = self._extensions(row)

            # Check for topology_scope declaration
            topology_scope = extensions.get("topology_scope") or row.get("topology_scope")
            if isinstance(topology_scope, dict):
                scope_id = topology_scope.get("scope_id")
                if isinstance(scope_id, str) and scope_id:
                    if scope_id in scope_by_id:
                        # Duplicate scope_id
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7921",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Workload '{row_id}' declares duplicate scope_id '{scope_id}'. "
                                    f"Already declared by '{scope_by_id[scope_id].get('instance')}'."
                                ),
                                path=f"instance:{row.get('group', 'workloads')}:{row_id}.topology_scope.scope_id",
                            )
                        )
                    else:
                        scope_by_id[scope_id] = row
                        workloads_in_scope[scope_id] = []

                    # Validate internal_networks structure
                    internal_networks = topology_scope.get("internal_networks")
                    if isinstance(internal_networks, list):
                        self._validate_internal_networks(
                            row_id=row_id,
                            scope_id=scope_id,
                            internal_networks=internal_networks,
                            row=row,
                            stage=stage,
                            diagnostics=diagnostics,
                        )

        # Second pass: validate scope references and build scope membership
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref not in self._WORKLOAD_CLASSES:
                continue

            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            group = row.get("group", "workloads")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = self._extensions(row)

            # Find parent scope through host_ref chain
            host_ref = self._extract_host_ref(row)
            parent_scope_id = None
            if host_ref:
                parent_row = row_by_id.get(host_ref)
                if parent_row:
                    parent_ext = self._extensions(parent_row)
                    parent_scope = parent_ext.get("topology_scope") or parent_row.get("topology_scope")
                    if isinstance(parent_scope, dict):
                        parent_scope_id = parent_scope.get("scope_id")
                        if isinstance(parent_scope_id, str) and parent_scope_id in workloads_in_scope:
                            workloads_in_scope[parent_scope_id].append(row_id)

            # Validate scope references (scope.* prefixed references)
            self._validate_scope_references(
                row_id=row_id,
                row=row,
                parent_scope_id=parent_scope_id,
                scope_by_id=scope_by_id,
                row_prefix=row_prefix,
                stage=stage,
                diagnostics=diagnostics,
            )

        # Emit info about detected scopes
        for scope_id, scope_row in scope_by_id.items():
            members = workloads_in_scope.get(scope_id, [])
            diagnostics.append(
                self.emit_diagnostic(
                    code="I7920",
                    severity="info",
                    stage=stage,
                    message=(
                        f"Scope '{scope_id}' declared by '{scope_row.get('instance')}' "
                        f"contains {len(members)} nested workloads."
                    ),
                    path=f"topology_scope:{scope_id}",
                )
            )

        return self.make_result(diagnostics)

    def _validate_internal_networks(
        self,
        *,
        row_id: str,
        scope_id: str,
        internal_networks: list[Any],
        row: dict[str, Any],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate internal_networks structure."""
        group = row.get("group", "workloads")
        row_prefix = f"instance:{group}:{row_id}"
        seen_names: set[str] = set()

        for idx, network in enumerate(internal_networks):
            if not isinstance(network, dict):
                continue

            name = network.get("name")
            if not isinstance(name, str) or not name:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7922",
                        severity="error",
                        stage=stage,
                        message=(f"Scope '{scope_id}' internal_networks[{idx}] " "requires non-empty 'name' property."),
                        path=f"{row_prefix}.topology_scope.internal_networks[{idx}].name",
                    )
                )
                continue

            if name in seen_names:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7922",
                        severity="error",
                        stage=stage,
                        message=(f"Scope '{scope_id}' has duplicate internal network name '{name}'."),
                        path=f"{row_prefix}.topology_scope.internal_networks[{idx}].name",
                    )
                )
            seen_names.add(name)

            # Validate driver if specified
            driver = network.get("driver")
            valid_drivers = {"bridge", "host", "none", "macvlan", "ipvlan"}
            if driver and driver not in valid_drivers:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7922",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Scope '{scope_id}' internal_networks[{idx}] has unknown "
                            f"driver '{driver}'. Expected one of: {sorted(valid_drivers)}."
                        ),
                        path=f"{row_prefix}.topology_scope.internal_networks[{idx}].driver",
                    )
                )

    def _validate_scope_references(
        self,
        *,
        row_id: str,
        row: dict[str, Any],
        parent_scope_id: str | None,
        scope_by_id: dict[str, dict[str, Any]],
        row_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate scope.* references resolve within declared scope."""
        extensions = self._extensions(row)

        # Check network references for scope.* prefix
        networks = extensions.get("networks") or row.get("networks")
        if isinstance(networks, list):
            for idx, network in enumerate(networks):
                if isinstance(network, dict):
                    network_ref = network.get("network_ref")
                    if isinstance(network_ref, str) and network_ref.startswith(self._SCOPE_PREFIX):
                        self._validate_scope_ref(
                            row_id=row_id,
                            ref_value=network_ref,
                            ref_path=f"{row_prefix}.networks[{idx}].network_ref",
                            parent_scope_id=parent_scope_id,
                            scope_by_id=scope_by_id,
                            stage=stage,
                            diagnostics=diagnostics,
                        )

        # Check volume references for scope.* prefix
        storage = extensions.get("storage") or row.get("storage")
        if isinstance(storage, dict):
            volumes = storage.get("volumes")
            if isinstance(volumes, list):
                for idx, volume in enumerate(volumes):
                    if isinstance(volume, dict):
                        volume_ref = volume.get("volume_ref")
                        if isinstance(volume_ref, str) and volume_ref.startswith(self._SCOPE_PREFIX):
                            self._validate_scope_ref(
                                row_id=row_id,
                                ref_value=volume_ref,
                                ref_path=f"{row_prefix}.storage.volumes[{idx}].volume_ref",
                                parent_scope_id=parent_scope_id,
                                scope_by_id=scope_by_id,
                                stage=stage,
                                diagnostics=diagnostics,
                            )

    def _validate_scope_ref(
        self,
        *,
        row_id: str,
        ref_value: str,
        ref_path: str,
        parent_scope_id: str | None,
        scope_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Validate a single scope.* reference."""
        # Extract scope_id from reference (e.g., scope.lxc-docker.network-a → lxc-docker)
        parts = ref_value.split(".")
        if len(parts) < 3:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7923",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Workload '{row_id}' has malformed scope reference '{ref_value}'. "
                        "Expected format: scope.<scope_id>.<resource_name>."
                    ),
                    path=ref_path,
                )
            )
            return

        ref_scope_id = parts[1]
        resource_name = ".".join(parts[2:])

        # Check if referenced scope exists
        if ref_scope_id not in scope_by_id:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7923",
                    severity="error",
                    stage=stage,
                    message=(f"Workload '{row_id}' references unknown scope '{ref_scope_id}' " f"in '{ref_value}'."),
                    path=ref_path,
                )
            )
            return

        # Check if workload is within the referenced scope
        if parent_scope_id != ref_scope_id:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7923",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Workload '{row_id}' references scope '{ref_scope_id}' "
                        f"but is not nested within it (parent scope: {parent_scope_id or 'none'})."
                    ),
                    path=ref_path,
                )
            )

    def _extract_host_ref(self, row: dict[str, Any]) -> str | None:
        """Extract host_ref from row."""
        extensions = self._extensions(row)
        for key in ("host_ref", "device_ref"):
            ref = extensions.get(key) or row.get(key)
            if isinstance(ref, str) and ref:
                return ref
        return None

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        """Get extensions dict from row."""
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}
