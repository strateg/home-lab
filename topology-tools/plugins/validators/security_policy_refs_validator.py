"""Security policy reference validator."""

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


class SecurityPolicyRefsValidator(ValidatorJsonPlugin):
    """Validate security_policy_ref links from network/service/operations rows."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7859",
                    severity="error",
                    stage=stage,
                    message=f"security_policy_refs validator requires normalized rows: {exc}",
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
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = row.get("extensions")
            if not isinstance(extensions, dict):
                continue
            ref = extensions.get("security_policy_ref")
            if ref is None:
                continue
            if not isinstance(ref, str) or not ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7859",
                        severity="error",
                        stage=stage,
                        message=f"Row '{row_id}' security_policy_ref must be a non-empty string when set.",
                        path=f"{row_prefix}.security_policy_ref",
                    )
                )
                continue

            target = row_by_id.get(ref)
            if not isinstance(target, dict) or not self._is_security_policy_row(target):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7859",
                        severity="error",
                        stage=stage,
                        message=f"Row '{row_id}' security_policy_ref '{ref}' must reference a security policy row.",
                        path=f"{row_prefix}.security_policy_ref",
                    )
                )

        return self.make_result(diagnostics)

    def _is_security_policy_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and ("security.policy" in class_ref or class_ref.startswith("class.security.")):
            return True
        group = row.get("group")
        if isinstance(group, str) and group in {"security_policies", "security_policy"}:
            return True
        return False
