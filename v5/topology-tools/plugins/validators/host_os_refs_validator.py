"""Host OS reference parity validator."""

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


class HostOsRefsValidator(ValidatorJsonPlugin):
    """Validate runtime target devices expose at least one active OS binding."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _WORKLOAD_CLASSES = {"class.compute.workload.container", "class.compute.cloud_vm"}
    _SERVICE_PREFIX = "class.service."
    _DEVICE_RUNTIME_TYPES = {"docker", "baremetal"}
    _ACTIVE_STATUSES = {"active", "mapped", "modeled"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7890",
                    severity="error",
                    stage=stage,
                    message=f"host_os_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        has_host_os_inventory = False
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row
            if row.get("class_ref") == "class.os":
                has_host_os_inventory = True

        # v4 behavior: enforce runtime target OS presence only when host_os inventory exists.
        if not has_host_os_inventory:
            return self.make_result(diagnostics)

        runtime_target_paths: dict[str, str] = {}
        for row in rows:
            class_ref = row.get("class_ref")
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"

            if class_ref in self._WORKLOAD_CLASSES:
                device_ref = self._extract_device_ref(row)
                if isinstance(device_ref, str) and device_ref:
                    runtime_target_paths.setdefault(device_ref, f"{row_prefix}.device_ref")
                continue

            if not isinstance(class_ref, str) or not class_ref.startswith(self._SERVICE_PREFIX):
                continue
            runtime = row.get("runtime")
            if not isinstance(runtime, dict):
                continue
            runtime_type = runtime.get("type")
            target_ref = runtime.get("target_ref")
            if runtime_type in self._DEVICE_RUNTIME_TYPES and isinstance(target_ref, str) and target_ref:
                runtime_target_paths.setdefault(target_ref, f"{row_prefix}.runtime.target_ref")

        for target_ref in sorted(runtime_target_paths):
            target_row = row_by_id.get(target_ref)
            if not isinstance(target_row, dict):
                continue
            if target_row.get("layer") != "L1":
                continue
            if self._has_active_os_binding(device_row=target_row, row_by_id=row_by_id):
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7892",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Device '{target_ref}': active runtime target requires at least one active "
                        "host OS binding in os_refs."
                    ),
                    path=runtime_target_paths[target_ref],
                )
            )

        return self.make_result(diagnostics)

    @staticmethod
    def _extract_device_ref(row: dict[str, Any]) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions.get("device_ref")
        return None

    def _has_active_os_binding(self, *, device_row: dict[str, Any], row_by_id: dict[str, dict[str, Any]]) -> bool:
        os_refs = device_row.get("os_refs")
        if not isinstance(os_refs, list) or not os_refs:
            return False

        for os_ref in os_refs:
            if not isinstance(os_ref, str) or not os_ref:
                continue
            os_row = row_by_id.get(os_ref)
            if not isinstance(os_row, dict):
                continue
            if os_row.get("class_ref") != "class.os":
                continue
            status = str(os_row.get("status") or "").strip().lower()
            if not status or status in self._ACTIVE_STATUSES:
                return True
        return False
