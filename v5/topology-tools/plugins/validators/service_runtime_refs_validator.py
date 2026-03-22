"""Service runtime reference validator."""

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


class ServiceRuntimeRefsValidator(ValidatorJsonPlugin):
    """Validate runtime target refs and binding refs for service instances."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _SERVICE_PREFIX = "class.service."
    _RUNTIME_TYPES = {"lxc", "vm", "docker", "baremetal"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7841",
                    severity="error",
                    stage=stage,
                    message=f"service_runtime_refs validator requires normalized rows: {exc}",
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
            class_ref = row.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref.startswith(self._SERVICE_PREFIX):
                continue
            runtime = row.get("runtime")
            if not isinstance(runtime, dict):
                continue

            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"

            runtime_type = runtime.get("type")
            target_ref = runtime.get("target_ref")
            network_binding_ref = runtime.get("network_binding_ref")

            if not isinstance(runtime_type, str) or runtime_type not in self._RUNTIME_TYPES:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7842",
                        severity="warning",
                        stage=stage,
                        message=f"Service '{row_id}' runtime.type '{runtime_type}' is not in {sorted(self._RUNTIME_TYPES)}.",
                        path=f"{row_prefix}.runtime.type",
                    )
                )
                continue

            if isinstance(network_binding_ref, str) and network_binding_ref:
                target = row_by_id.get(network_binding_ref)
                if not isinstance(target, dict) or target.get("class_ref") != "class.network.vlan":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime.network_binding_ref '{network_binding_ref}' "
                                "must reference a class.network.vlan instance."
                            ),
                            path=f"{row_prefix}.runtime.network_binding_ref",
                        )
                    )

            if not isinstance(target_ref, str) or not target_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7841",
                        severity="error",
                        stage=stage,
                        message=f"Service '{row_id}' runtime.target_ref must be a non-empty string.",
                        path=f"{row_prefix}.runtime.target_ref",
                    )
                )
                continue

            target = row_by_id.get(target_ref)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7841",
                        severity="error",
                        stage=stage,
                        message=f"Service '{row_id}' runtime.target_ref '{target_ref}' does not exist.",
                        path=f"{row_prefix}.runtime.target_ref",
                    )
                )
                continue

            target_class = target.get("class_ref")
            target_layer = target.get("layer")
            if runtime_type == "lxc":
                if target_class != "class.compute.workload.container":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime type lxc requires target class "
                                f"'class.compute.workload.container', got '{target_class}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )
            elif runtime_type == "vm":
                if target_class not in {"class.compute.cloud_vm"}:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime type vm requires target class "
                                f"'class.compute.cloud_vm', got '{target_class}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )
            elif runtime_type in {"docker", "baremetal"}:
                if target_layer != "L1":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime type {runtime_type} requires L1 target, "
                                f"got layer '{target_layer}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )

        return self.make_result(diagnostics)
