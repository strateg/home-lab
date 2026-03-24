"""Trust-zone default firewall reference validator."""

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


class NetworkTrustZoneFirewallRefsValidator(ValidatorJsonPlugin):
    """Validate trust-zone `default_firewall_policy_ref` cross-instance references."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _FIREWALL_CLASS = "class.network.firewall_policy"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7821",
                    severity="error",
                    stage=stage,
                    message=f"trust_zone_firewall_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        for row in rows:
            if row.get("class_ref") != "class.network.trust_zone":
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            object_ref = row.get("object_ref")
            object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
            properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
            if not isinstance(properties, dict):
                continue

            fw_ref = properties.get("default_firewall_policy_ref")
            if not isinstance(fw_ref, str) or not fw_ref:
                continue

            target = row_by_id.get(fw_ref)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7822",
                        severity="error",
                        stage=stage,
                        message=(f"Trust-zone '{row_id}' references unknown default_firewall_policy_ref '{fw_ref}'."),
                        path=f"{row_prefix}.default_firewall_policy_ref",
                    )
                )
                continue

            target_class = target.get("class_ref")
            if target_class != self._FIREWALL_CLASS:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7822",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Trust-zone '{row_id}' default_firewall_policy_ref '{fw_ref}' must reference "
                            f"'{self._FIREWALL_CLASS}', got '{target_class}'."
                        ),
                        path=f"{row_prefix}.default_firewall_policy_ref",
                    )
                )

        return self.make_result(diagnostics)
