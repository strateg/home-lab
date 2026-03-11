"""Embedded-in validation plugin for v5 topology compiler (ADR 0069 WS3).

This plugin mirrors legacy `_validate_embedded_in` semantics and can take
ownership from core validation in plugin-first mode.
"""

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


class EmbeddedInValidator(ValidatorJsonPlugin):
    """Validate embedded_in relationships for OS and device instances."""

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
    def _extract_os_installation_model(object_payload: dict[str, Any]) -> str | None:
        properties = object_payload.get("properties")
        if isinstance(properties, dict):
            model = properties.get("installation_model")
            if isinstance(model, str) and model:
                return model
        return None

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Keep legacy core as owner when runtime explicitly marks ownership.
        # If ownership key is absent, execute plugin for standalone tests/usages.
        owner = ctx.config.get("validation_owner_embedded_in")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        try:
            rows_payload = self._subscribe_required(
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

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # Validate OS instances (class.os)
        for row in rows:
            if row.get("class_ref") != "class.os":
                continue

            row_id = row.get("instance")
            object_ref = row.get("object_ref")
            embedded_in = row.get("embedded_in")
            path = f"instance:{row.get('group')}:{row_id}"

            if not isinstance(object_ref, str) or not object_ref:
                continue

            object_payload = ctx.objects.get(object_ref)
            if not isinstance(object_payload, dict):
                continue

            install_model = self._extract_os_installation_model(object_payload)
            if install_model == "embedded":
                if not isinstance(embedded_in, str) or not embedded_in:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"OS instance '{row_id}' has installation_model=embedded "
                                "but missing required 'embedded_in' field."
                            ),
                            path=path,
                        )
                    )
                else:
                    firmware_row = row_by_id.get(embedded_in)
                    if firmware_row is None:
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E2101",
                                severity="error",
                                stage="resolve",
                                message=(
                                    f"OS instance '{row_id}' embedded_in references unknown instance '{embedded_in}'."
                                ),
                                path=path,
                                plugin_id=self.plugin_id,
                            )
                        )
                    elif firmware_row.get("class_ref") != "class.firmware":
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E2403",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"OS instance '{row_id}' embedded_in '{embedded_in}' must reference "
                                    f"class.firmware, got '{firmware_row.get('class_ref')}'."
                                ),
                                path=path,
                            )
                        )
            elif install_model in ("installable", "cloud_image", "container_base"):
                if isinstance(embedded_in, str) and embedded_in:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"OS instance '{row_id}' has installation_model={install_model} "
                                "but embedded_in field is set (should be absent)."
                            ),
                            path=path,
                        )
                    )

        # Validate device instances: embedded OS embedded_in must match device firmware_ref
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref in ("class.os", "class.firmware"):
                continue

            row_id = row.get("instance")
            firmware_ref = row.get("firmware_ref")
            os_refs = row.get("os_refs", []) or []
            if not isinstance(os_refs, list):
                os_refs = []
            path = f"instance:{row.get('group')}:{row_id}"

            if not isinstance(firmware_ref, str) or not firmware_ref:
                continue

            for os_ref in os_refs:
                if not isinstance(os_ref, str):
                    continue
                os_row = row_by_id.get(os_ref)
                if not isinstance(os_row, dict):
                    continue

                os_object_ref = os_row.get("object_ref")
                if not isinstance(os_object_ref, str):
                    continue
                os_object_payload = ctx.objects.get(os_object_ref)
                if not isinstance(os_object_payload, dict):
                    continue

                install_model = self._extract_os_installation_model(os_object_payload)
                if install_model != "embedded":
                    continue

                os_embedded_in = os_row.get("embedded_in")
                if isinstance(os_embedded_in, str) and os_embedded_in != firmware_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Device instance '{row_id}' uses embedded OS '{os_ref}' "
                                f"whose embedded_in='{os_embedded_in}' does not match "
                                f"device firmware_ref='{firmware_ref}'."
                            ),
                            path=path,
                        )
                    )

        return self.make_result(diagnostics)
