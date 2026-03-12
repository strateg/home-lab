"""Power source relation validator for ADR0062 planned L1 lateral contracts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class PowerSourceRefsValidator(ValidatorJsonPlugin):
    """Validate `power.source_ref` L1->L1 lateral relation and outlet occupancy."""

    _ALLOWED_SOURCE_LAYER = "L1"
    _ALLOWED_TARGET_LAYER = "L1"
    _ALLOWED_TARGET_CLASSES = {"class.power.pdu", "class.power.ups"}

    @staticmethod
    def _subscribe_required(
        ctx: PluginContext,
        *,
        plugin_id: str,
        published_key: str,
    ) -> Any:
        try:
            return ctx.subscribe(plugin_id, published_key)
        except PluginDataExchangeError as exc:
            raise PluginDataExchangeError(
                f"Missing required published key '{published_key}' from '{plugin_id}': {exc}"
            ) from exc

    @staticmethod
    def _extract_power_block(row: dict[str, Any]) -> dict[str, Any] | None:
        extensions = row.get("extensions")
        if not isinstance(extensions, dict):
            return None
        power_block = extensions.get("power")
        if not isinstance(power_block, dict):
            return None
        return power_block

    @staticmethod
    def _extract_outlet_inventory(source_object_payload: Any) -> set[str]:
        if not isinstance(source_object_payload, dict):
            return set()
        properties = source_object_payload.get("properties")
        if not isinstance(properties, dict):
            return set()

        outlets_payload: Any = None
        power_block = properties.get("power")
        if isinstance(power_block, dict):
            outlets_payload = power_block.get("outlets")
        if outlets_payload is None:
            outlets_payload = properties.get("outlets")

        outlet_names: set[str] = set()
        if isinstance(outlets_payload, list):
            for item in outlets_payload:
                if isinstance(item, str) and item:
                    outlet_names.add(item)
                    continue
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name:
                        outlet_names.add(name)
        return outlet_names

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("validation_owner_power_source_refs")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        try:
            raw_rows = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.instance_rows",
                published_key="normalized_rows",
            )
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6901",
                    severity="error",
                    stage=stage,
                    message=str(exc),
                    path="pipeline:mode",
                )
            )
            return self.make_result(diagnostics)

        rows: list[dict[str, Any]] = []
        if isinstance(raw_rows, list):
            rows = [row for row in raw_rows if isinstance(row, dict)]

        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        outlet_occupancy: dict[tuple[str, str], tuple[str, str]] = {}
        relation_edges: dict[str, tuple[str, str]] = {}

        for row in rows:
            row_id = row.get("instance")
            row_layer = row.get("layer")
            group = row.get("group")
            if not isinstance(row_id, str) or not row_id:
                continue
            if not isinstance(group, str) or not group:
                continue

            path_prefix = f"instance:{group}:{row_id}"
            power_block = self._extract_power_block(row)
            if not isinstance(power_block, dict) or "source_ref" not in power_block:
                continue

            source_ref = power_block.get("source_ref")
            source_path = f"{path_prefix}.extensions.power.source_ref"

            if not isinstance(source_ref, str) or not source_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7804",
                        severity="error",
                        stage=stage,
                        message="power.source_ref must be a non-empty instance id string.",
                        path=source_path,
                    )
                )
                continue

            if row_layer != self._ALLOWED_SOURCE_LAYER:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7803",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Row '{row_id}' layer '{row_layer}' cannot use power.source_ref; "
                            f"allowed source layer: '{self._ALLOWED_SOURCE_LAYER}'."
                        ),
                        path=source_path,
                    )
                )
                continue

            target_row = row_by_id.get(source_ref)
            if not isinstance(target_row, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7801",
                        severity="error",
                        stage=stage,
                        message=f"Row '{row_id}' references unknown power source '{source_ref}'.",
                        path=source_path,
                    )
                )
                continue

            target_layer = target_row.get("layer")
            target_class = target_row.get("class_ref")
            if target_layer != self._ALLOWED_TARGET_LAYER or target_class not in self._ALLOWED_TARGET_CLASSES:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7802",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Target '{source_ref}' is invalid for power.source_ref: "
                            f"expected class in {sorted(self._ALLOWED_TARGET_CLASSES)} on layer "
                            f"'{self._ALLOWED_TARGET_LAYER}', got class '{target_class}' "
                            f"on layer '{target_layer}'."
                        ),
                        path=source_path,
                    )
                )
                continue

            if row_id == source_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7805",
                        severity="error",
                        stage=stage,
                        message=f"Row '{row_id}' cannot reference itself in power.source_ref.",
                        path=source_path,
                    )
                )
                continue

            relation_edges[row_id] = (source_ref, source_path)

            if "outlet_ref" in power_block:
                outlet_ref = power_block.get("outlet_ref")
                outlet_path = f"{path_prefix}.extensions.power.outlet_ref"
                if not isinstance(outlet_ref, str) or not outlet_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7804",
                            severity="error",
                            stage=stage,
                            message="power.outlet_ref must be a non-empty string when set.",
                            path=outlet_path,
                        )
                    )
                    continue

                source_object_ref = target_row.get("object_ref")
                source_object_payload = (
                    ctx.objects.get(source_object_ref)
                    if isinstance(source_object_ref, str) and source_object_ref
                    else None
                )
                outlet_inventory = self._extract_outlet_inventory(source_object_payload)
                if not outlet_inventory:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7806",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Power source '{source_ref}' has no outlet inventory in object "
                                f"'{source_object_ref}' but outlet_ref='{outlet_ref}' was provided."
                            ),
                            path=outlet_path,
                        )
                    )
                    continue
                if outlet_ref not in outlet_inventory:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7806",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Outlet '{outlet_ref}' is not declared by power source '{source_ref}' "
                                f"(object '{source_object_ref}'). Known outlets: {sorted(outlet_inventory)}."
                            ),
                            path=outlet_path,
                        )
                    )
                    continue

                key = (source_ref, outlet_ref)
                occupied = outlet_occupancy.get(key)
                if occupied and occupied[0] != row_id:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7805",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Outlet '{outlet_ref}' on power source '{source_ref}' is already "
                                f"assigned to '{occupied[0]}'; cannot also assign to '{row_id}'."
                            ),
                            path=outlet_path,
                        )
                    )
                    continue

                outlet_occupancy[key] = (row_id, outlet_path)

        for row_id, (_, path) in relation_edges.items():
            visited: set[str] = set()
            cursor = row_id
            while cursor in relation_edges:
                if cursor in visited:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7805",
                            severity="error",
                            stage=stage,
                            message=f"power.source_ref cycle detected starting from '{row_id}'.",
                            path=path,
                        )
                    )
                    break
                visited.add(cursor)
                cursor = relation_edges[cursor][0]

        return self.make_result(diagnostics)
