"""Host OS reference parity validator."""

from __future__ import annotations

from typing import Any

from capability_derivation import extract_architecture as shared_extract_architecture
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
    _INSTALL_REQUIRED_HOST_TYPES = {"baremetal", "hypervisor"}
    _ARCH_ALIASES = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "x86": "i386",
        "i386": "i386",
        "arm64": "arm64",
        "aarch64": "arm64",
        "riscv64": "riscv64",
        "riscv": "riscv64",
    }
    _CANONICAL_ARCH_VALUES = {"x86_64", "arm64", "riscv64", "i386"}
    _CAPABILITY_ALLOWED_HOST_TYPES = {
        "lxc": {"hypervisor"},
        "vm": {"hypervisor"},
        "docker": {"baremetal", "hypervisor"},
        "container": {"embedded", "baremetal", "hypervisor"},
        "cloudinit": {"hypervisor", "baremetal"},
    }

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
        os_to_devices: dict[str, set[str]] = {}
        has_host_os_inventory = False
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row
            if row.get("class_ref") == "class.os":
                has_host_os_inventory = True
        for row in rows:
            if row.get("layer") != "L1":
                continue
            device_id = row.get("instance")
            if not isinstance(device_id, str) or not device_id:
                continue
            os_refs = row.get("os_refs")
            if not isinstance(os_refs, list):
                continue
            for os_ref in os_refs:
                if isinstance(os_ref, str) and os_ref:
                    os_to_devices.setdefault(os_ref, set()).add(device_id)

        self._validate_host_os_inventory_contracts(
            ctx=ctx,
            row_by_id=row_by_id,
            os_to_devices=os_to_devices,
            stage=stage,
            diagnostics=diagnostics,
        )

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

    def _validate_host_os_inventory_contracts(
        self,
        *,
        ctx: PluginContext,
        row_by_id: dict[str, dict[str, Any]],
        os_to_devices: dict[str, set[str]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        for os_id, os_row in row_by_id.items():
            if os_row.get("class_ref") != "class.os":
                continue
            group = os_row.get("group")
            row_prefix = f"instance:{group}:{os_id}"
            bound_devices = sorted(os_to_devices.get(os_id, set()))

            os_arch = self._row_architecture(ctx=ctx, row=os_row)
            if os_arch:
                for device_id in bound_devices:
                    device_row = row_by_id.get(device_id)
                    if not isinstance(device_row, dict):
                        continue
                    device_arch = self._row_architecture(ctx=ctx, row=device_row)
                    if device_arch and device_arch != os_arch:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7891",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"OS '{os_id}' architecture '{os_arch}' does not match "
                                    f"device '{device_id}' architecture '{device_arch}'."
                                ),
                                path=f"{row_prefix}.architecture",
                            )
                        )

            extensions = self._host_os_payload(os_row)
            host_type_raw = extensions.get("host_type")
            host_type = str(host_type_raw).strip().lower() if isinstance(host_type_raw, str) else ""

            self._validate_extension_architecture(
                os_id=os_id,
                host_type=host_type,
                extensions=extensions,
                bound_devices=bound_devices,
                ctx=ctx,
                row_by_id=row_by_id,
                stage=stage,
                diagnostics=diagnostics,
                row_prefix=row_prefix,
            )
            self._validate_host_type_capability_contract(
                os_id=os_id,
                host_type=host_type,
                extensions=extensions,
                stage=stage,
                diagnostics=diagnostics,
                row_prefix=row_prefix,
            )

            installation = extensions.get("installation")
            if installation is not None and not isinstance(installation, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7893",
                        severity="error",
                        stage=stage,
                        message=f"OS '{os_id}' installation must be an object when set.",
                        path=f"{row_prefix}.installation",
                    )
                )
                installation = {}
            if not isinstance(installation, dict):
                installation = {}

            root_storage_endpoint_ref = installation.get("root_storage_endpoint_ref")
            if root_storage_endpoint_ref is not None:
                if not isinstance(root_storage_endpoint_ref, str) or not root_storage_endpoint_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7893",
                            severity="error",
                            stage=stage,
                            message=(
                                f"OS '{os_id}' installation.root_storage_endpoint_ref "
                                "must be a non-empty string when set."
                            ),
                            path=f"{row_prefix}.installation.root_storage_endpoint_ref",
                        )
                    )
                    root_storage_endpoint_ref = None
            if isinstance(root_storage_endpoint_ref, str) and root_storage_endpoint_ref:
                endpoint_row = row_by_id.get(root_storage_endpoint_ref)
                if (
                    not isinstance(endpoint_row, dict)
                    or endpoint_row.get("class_ref") != "class.storage.storage_endpoint"
                ):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7893",
                            severity="error",
                            stage=stage,
                            message=(
                                f"OS '{os_id}' installation.root_storage_endpoint_ref '{root_storage_endpoint_ref}' "
                                "must reference class.storage.storage_endpoint."
                            ),
                            path=f"{row_prefix}.installation.root_storage_endpoint_ref",
                        )
                    )
                else:
                    self._validate_root_storage_mount_device(
                        os_id=os_id,
                        endpoint_row=endpoint_row,
                        row_by_id=row_by_id,
                        bound_devices=bound_devices,
                        stage=stage,
                        diagnostics=diagnostics,
                        row_prefix=row_prefix,
                    )

            if host_type in self._INSTALL_REQUIRED_HOST_TYPES:
                if not installation:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7894",
                            severity="error",
                            stage=stage,
                            message=f"OS '{os_id}' host_type '{host_type_raw}' requires installation object.",
                            path=f"{row_prefix}.host_type",
                        )
                    )
                elif not isinstance(root_storage_endpoint_ref, str) or not root_storage_endpoint_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7894",
                            severity="error",
                            stage=stage,
                            message=(
                                f"OS '{os_id}' host_type '{host_type_raw}' requires "
                                "installation.root_storage_endpoint_ref."
                            ),
                            path=f"{row_prefix}.installation.root_storage_endpoint_ref",
                        )
                    )

    def _validate_root_storage_mount_device(
        self,
        *,
        os_id: str,
        endpoint_row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        bound_devices: list[str],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_prefix: str,
    ) -> None:
        endpoint_ext = self._extensions(endpoint_row)
        mount_point_ref = endpoint_ext.get("mount_point_ref")
        if not isinstance(mount_point_ref, str) or not mount_point_ref:
            return
        mount_row = row_by_id.get(mount_point_ref)
        if not isinstance(mount_row, dict) or mount_row.get("class_ref") != "class.storage.mount_point":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7893",
                    severity="error",
                    stage=stage,
                    message=(
                        f"OS '{os_id}' root storage endpoint mount_point_ref '{mount_point_ref}' "
                        "must reference class.storage.mount_point."
                    ),
                    path=f"{row_prefix}.installation.root_storage_endpoint_ref",
                )
            )
            return
        mount_ext = self._extensions(mount_row)
        mount_device_ref = mount_ext.get("device_ref")
        if (
            isinstance(mount_device_ref, str)
            and mount_device_ref
            and bound_devices
            and mount_device_ref not in set(bound_devices)
        ):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7893",
                    severity="error",
                    stage=stage,
                    message=(
                        f"OS '{os_id}' installation.root_storage_endpoint_ref points to mount point "
                        f"on device '{mount_device_ref}', expected one of {bound_devices}."
                    ),
                    path=f"{row_prefix}.installation.root_storage_endpoint_ref",
                )
            )

    def _validate_extension_architecture(
        self,
        *,
        os_id: str,
        host_type: str,
        extensions: dict[str, Any],
        bound_devices: list[str],
        ctx: PluginContext,
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_prefix: str,
    ) -> None:
        del host_type
        raw_arch = extensions.get("architecture")
        if not isinstance(raw_arch, str) or not raw_arch.strip():
            return
        normalized = self._normalize_arch(raw_arch)
        if raw_arch != normalized:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7895",
                    severity="error",
                    stage=stage,
                    message=f"OS '{os_id}': architecture '{raw_arch}' must be canonical; use '{normalized}'.",
                    path=f"{row_prefix}.architecture",
                )
            )
        if normalized and normalized not in self._CANONICAL_ARCH_VALUES:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7895",
                    severity="error",
                    stage=stage,
                    message=(f"OS '{os_id}': architecture '{raw_arch}' normalizes to unsupported '{normalized}'."),
                    path=f"{row_prefix}.architecture",
                )
            )
            return
        if not normalized:
            return
        for device_id in bound_devices:
            device_row = row_by_id.get(device_id)
            if not isinstance(device_row, dict):
                continue
            device_arch_raw = self._row_architecture(ctx=ctx, row=device_row)
            device_arch = self._normalize_arch(device_arch_raw)
            if device_arch and device_arch != normalized:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7895",
                        severity="error",
                        stage=stage,
                        message=(
                            f"OS '{os_id}' architecture '{raw_arch}' does not match "
                            f"device '{device_id}' architecture '{device_arch_raw}'."
                        ),
                        path=f"{row_prefix}.architecture",
                    )
                )

    def _validate_host_type_capability_contract(
        self,
        *,
        os_id: str,
        host_type: str,
        extensions: dict[str, Any],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_prefix: str,
    ) -> None:
        capabilities = extensions.get("capabilities")
        if capabilities is None:
            return
        if not isinstance(capabilities, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7896",
                    severity="error",
                    stage=stage,
                    message=f"OS '{os_id}': capabilities must be a list when set.",
                    path=f"{row_prefix}.capabilities",
                )
            )
            return
        for idx, capability in enumerate(capabilities):
            if not isinstance(capability, str):
                continue
            normalized_cap = capability.strip().lower()
            allowed_host_types = self._CAPABILITY_ALLOWED_HOST_TYPES.get(normalized_cap)
            if allowed_host_types and host_type and host_type not in allowed_host_types:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7896",
                        severity="error",
                        stage=stage,
                        message=(f"OS '{os_id}': capability '{capability}' is not valid for host_type '{host_type}'."),
                        path=f"{row_prefix}.capabilities[{idx}]",
                    )
                )

    @staticmethod
    def _extract_device_ref(row: dict[str, Any]) -> Any:
        extensions = HostOsRefsValidator._extensions(row)
        if "device_ref" in extensions:
            return extensions.get("device_ref")
        return row.get("device_ref")

    @staticmethod
    def _host_os_payload(row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(HostOsRefsValidator._extensions(row))
        for key in ("architecture", "capabilities", "host_type", "installation"):
            if key not in payload and key in row:
                payload[key] = row.get(key)
        return payload

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions
        return {}

    @staticmethod
    def _row_architecture(*, ctx: PluginContext, row: dict[str, Any]) -> str | None:
        object_ref = row.get("object_ref")
        if isinstance(object_ref, str) and object_ref:
            object_payload = ctx.objects.get(object_ref)
            if isinstance(object_payload, dict):
                architecture = shared_extract_architecture(object_payload)
                if isinstance(architecture, str) and architecture:
                    return architecture
        extensions = HostOsRefsValidator._extensions(row)
        ext_arch = extensions.get("architecture")
        if isinstance(ext_arch, str) and ext_arch:
            return ext_arch
        row_arch = row.get("architecture")
        if isinstance(row_arch, str) and row_arch:
            return row_arch
        return None

    @classmethod
    def _normalize_arch(cls, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        normalized = value.strip().lower()
        return cls._ARCH_ALIASES.get(normalized, normalized)

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
