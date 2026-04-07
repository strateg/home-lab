"""Hypervisor execution model linkage validator (ADR 0087 Phase 2)."""

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


class HypervisorExecutionModelValidator(ValidatorJsonPlugin):
    """Validate hypervisor execution model linkage.

    This validator enforces ADR 0087 Phase 2 requirements:
    - bare_metal hypervisors at L1 don't require hardware_ref (they ARE the hardware)
    - hosted hypervisors require host_os_ref pointing to valid OS instance
    - execution_model must be valid value from class definition
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _HYPERVISOR_CLASSES = {
        "class.compute.hypervisor",
        "class.compute.hypervisor.proxmox",
        "class.compute.hypervisor.vbox",
        "class.compute.hypervisor.hyperv",
        "class.compute.hypervisor.vmware",
        "class.compute.hypervisor.xen",
    }
    _VALID_EXECUTION_MODELS = {"bare_metal", "hosted"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7898",
                    severity="error",
                    stage=stage,
                    message=f"hypervisor_execution_model validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        # Build lookup
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # Validate each hypervisor
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref not in self._HYPERVISOR_CLASSES:
                continue

            row_id = row.get("instance")
            group = row.get("group", "devices")
            layer = row.get("layer")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = self._extensions(row)

            # Get execution_model (from extensions, top-level, or class default)
            execution_model = self._get_execution_model(row, class_ref)

            # Validate execution_model value
            if execution_model and execution_model not in self._VALID_EXECUTION_MODELS:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7899",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Hypervisor '{row_id}' has invalid execution_model '{execution_model}'. "
                            f"Must be one of: {sorted(self._VALID_EXECUTION_MODELS)}."
                        ),
                        path=f"{row_prefix}.execution_model",
                    )
                )
                continue

            # Validate linkage based on execution_model
            if execution_model == "hosted":
                # hosted hypervisors MUST have host_os_ref
                host_os_ref = extensions.get("host_os_ref") or row.get("host_os_ref")
                if not host_os_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7899",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Hypervisor '{row_id}' with execution_model 'hosted' "
                                "requires host_os_ref pointing to host OS instance."
                            ),
                            path=f"{row_prefix}.host_os_ref",
                        )
                    )
                elif isinstance(host_os_ref, str):
                    # Validate host_os_ref target exists
                    target = row_by_id.get(host_os_ref)
                    if not isinstance(target, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7899",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Hypervisor '{row_id}' host_os_ref '{host_os_ref}' "
                                    "does not reference a known instance."
                                ),
                                path=f"{row_prefix}.host_os_ref",
                            )
                        )
                    else:
                        # Validate target is an OS instance
                        target_class = target.get("class_ref", "")
                        if not target_class.startswith("class.os"):
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="W7899",
                                    severity="warning",
                                    stage=stage,
                                    message=(
                                        f"Hypervisor '{row_id}' host_os_ref '{host_os_ref}' "
                                        f"targets '{target_class}' instead of an OS class."
                                    ),
                                    path=f"{row_prefix}.host_os_ref",
                                )
                            )

            elif execution_model == "bare_metal":
                # bare_metal hypervisors at L1 don't strictly need hardware_ref
                # (the L1 instance itself represents the hardware)
                # But if hardware_ref is specified, validate it
                hardware_ref = extensions.get("hardware_ref") or row.get("hardware_ref")
                if hardware_ref and isinstance(hardware_ref, str):
                    target = row_by_id.get(hardware_ref)
                    if not isinstance(target, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7899",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Hypervisor '{row_id}' hardware_ref '{hardware_ref}' "
                                    "does not reference a known instance."
                                ),
                                path=f"{row_prefix}.hardware_ref",
                            )
                        )

                # Info diagnostic for L1 bare_metal without explicit hardware_ref
                if not hardware_ref and layer == "L1":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="I7899",
                            severity="info",
                            stage=stage,
                            message=(
                                f"Hypervisor '{row_id}' is bare_metal at L1; "
                                "instance represents both hypervisor and hardware."
                            ),
                            path=f"{row_prefix}",
                        )
                    )

        return self.make_result(diagnostics)

    def _get_execution_model(self, row: dict[str, Any], class_ref: str) -> str | None:
        """Get execution_model from row or derive from class."""
        extensions = self._extensions(row)

        # Check extensions first
        execution_model = extensions.get("execution_model")
        if isinstance(execution_model, str):
            return execution_model

        # Check top-level
        execution_model = row.get("execution_model")
        if isinstance(execution_model, str):
            return execution_model

        # Derive from class_ref defaults
        class_defaults = {
            "class.compute.hypervisor.proxmox": "bare_metal",
            "class.compute.hypervisor.xen": "bare_metal",
            "class.compute.hypervisor.vbox": "hosted",
            # hyperv and vmware support both, no default
        }
        return class_defaults.get(class_ref)

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        """Get extensions dict from row."""
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}
