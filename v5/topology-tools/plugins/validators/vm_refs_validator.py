"""VM reference validator."""

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


class VmRefsValidator(ValidatorJsonPlugin):
    """Validate VM row references (device/trust-zone/host-os/networks/storage)."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _VM_CLASS = "class.compute.cloud_vm"
    _ACTIVE_OS_STATUSES = {"active", "mapped", "modeled"}
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

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7870",
                    severity="error",
                    stage=stage,
                    message=f"vm_refs validator requires normalized rows: {exc}",
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
            if row.get("class_ref") != self._VM_CLASS:
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = self._extensions(row)
            device_ref = extensions.get("device_ref")
            host_os_ref = extensions.get("host_os_ref")
            template_ref = extensions.get("template_ref")
            device_row = row_by_id.get(device_ref) if isinstance(device_ref, str) else None
            host_os_row = row_by_id.get(host_os_ref) if isinstance(host_os_ref, str) else None

            self._validate_ref(
                row_id=row_id,
                field_name="device_ref",
                value=device_ref,
                row_by_id=row_by_id,
                expected=lambda target: target.get("layer") == "L1",
                expected_label="L1 device instance",
                code="E7871",
                stage=stage,
                path=f"{row_prefix}.device_ref",
                diagnostics=diagnostics,
            )
            self._validate_ref(
                row_id=row_id,
                field_name="trust_zone_ref",
                value=extensions.get("trust_zone_ref"),
                row_by_id=row_by_id,
                expected=lambda target: target.get("class_ref") == "class.network.trust_zone",
                expected_label="class.network.trust_zone instance",
                code="E7872",
                stage=stage,
                path=f"{row_prefix}.trust_zone_ref",
                diagnostics=diagnostics,
            )
            self._validate_ref(
                row_id=row_id,
                field_name="host_os_ref",
                value=host_os_ref,
                row_by_id=row_by_id,
                expected=lambda target: target.get("class_ref") == "class.os",
                expected_label="class.os instance",
                code="E7873",
                stage=stage,
                path=f"{row_prefix}.host_os_ref",
                diagnostics=diagnostics,
            )
            if isinstance(host_os_ref, str) and host_os_ref and isinstance(device_row, dict):
                device_os_refs = device_row.get("os_refs")
                if isinstance(device_os_refs, list) and device_os_refs and host_os_ref not in device_os_refs:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7873",
                            severity="error",
                            stage=stage,
                            message=(
                                f"VM '{row_id}' host_os_ref '{host_os_ref}' is not listed in "
                                f"device '{device_ref}' os_refs."
                            ),
                            path=f"{row_prefix}.host_os_ref",
                        )
                    )
            if host_os_ref is None and isinstance(device_row, dict):
                active_os_refs = self._active_os_refs(device_row=device_row, row_by_id=row_by_id)
                if len(active_os_refs) > 1:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7873",
                            severity="error",
                            stage=stage,
                            message=(
                                f"VM '{row_id}' device '{device_ref}' has multiple active OS bindings "
                                f"{sorted(active_os_refs)}; host_os_ref is required."
                            ),
                            path=f"{row_prefix}.host_os_ref",
                        )
                    )
            self._validate_ref(
                row_id=row_id,
                field_name="template_ref",
                value=template_ref,
                row_by_id=row_by_id,
                expected=lambda target: True,
                expected_label="known instance",
                code="E7874",
                stage=stage,
                path=f"{row_prefix}.template_ref",
                diagnostics=diagnostics,
            )
            networks = extensions.get("networks")
            if networks is not None and not isinstance(networks, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7875",
                        severity="error",
                        stage=stage,
                        message="VM networks must be a list when set.",
                        path=f"{row_prefix}.networks",
                    )
                )
            elif isinstance(networks, list):
                for idx, nic in enumerate(networks):
                    if not isinstance(nic, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7875",
                                severity="error",
                                stage=stage,
                                message="VM network entries must be objects.",
                                path=f"{row_prefix}.networks[{idx}]",
                            )
                        )
                        continue
                    self._validate_ref(
                        row_id=row_id,
                        field_name="network_ref",
                        value=nic.get("network_ref"),
                        row_by_id=row_by_id,
                        expected=lambda target: target.get("class_ref") == "class.network.vlan",
                        expected_label="class.network.vlan instance",
                        code="E7875",
                        stage=stage,
                        path=f"{row_prefix}.networks[{idx}].network_ref",
                        diagnostics=diagnostics,
                    )
                    self._validate_ref(
                        row_id=row_id,
                        field_name="bridge_ref",
                        value=nic.get("bridge_ref"),
                        row_by_id=row_by_id,
                        expected=lambda target: target.get("class_ref") == "class.network.bridge",
                        expected_label="class.network.bridge instance",
                        code="E7875",
                        stage=stage,
                        path=f"{row_prefix}.networks[{idx}].bridge_ref",
                        diagnostics=diagnostics,
                    )

            storage_items = extensions.get("storage")
            if storage_items is not None and not isinstance(storage_items, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7876",
                        severity="error",
                        stage=stage,
                        message="VM storage must be a list when set.",
                        path=f"{row_prefix}.storage",
                    )
                )
            elif isinstance(storage_items, list):
                for idx, storage in enumerate(storage_items):
                    if not isinstance(storage, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7876",
                                severity="error",
                                stage=stage,
                                message="VM storage entries must be objects.",
                                path=f"{row_prefix}.storage[{idx}]",
                            )
                        )
                        continue
                    storage_ref = storage.get("storage_endpoint_ref")
                    if storage_ref is None:
                        storage_ref = storage.get("storage_ref")
                    self._validate_ref(
                        row_id=row_id,
                        field_name="storage_ref",
                        value=storage_ref,
                        row_by_id=row_by_id,
                        expected=lambda target: target.get("class_ref") in {"class.storage.storage_endpoint", "class.storage.pool"},
                        expected_label="storage endpoint/pool instance",
                        code="E7876",
                        stage=stage,
                        path=f"{row_prefix}.storage[{idx}].storage_ref",
                        diagnostics=diagnostics,
                    )
                    if isinstance(storage_ref, str):
                        storage_target = row_by_id.get(storage_ref)
                        if (
                            isinstance(storage_target, dict)
                            and storage_target.get("class_ref") == "class.storage.storage_endpoint"
                        ):
                            platform = self._storage_platform(storage_target)
                            if isinstance(platform, str) and platform.strip() and platform.strip().lower() != "proxmox":
                                diagnostics.append(
                                    self.emit_diagnostic(
                                        code="E7876",
                                        severity="error",
                                        stage=stage,
                                        message=(
                                            f"VM '{row_id}' storage reference '{storage_ref}' has platform "
                                            f"'{platform}', expected 'proxmox'."
                                        ),
                                        path=f"{row_prefix}.storage[{idx}].storage_ref",
                                    )
                                )

            resolved_host_os_row = self._resolve_host_os_row(
                host_os_ref=host_os_ref,
                host_os_row=host_os_row,
                device_row=device_row,
                row_by_id=row_by_id,
            )
            self._validate_required_capability(
                row_id=row_id,
                row_prefix=row_prefix,
                required_capability="vm",
                resolved_host_os_row=resolved_host_os_row,
                stage=stage,
                diagnostics=diagnostics,
            )
            self._validate_architecture_semantics(
                ctx=ctx,
                row=row,
                row_id=row_id,
                row_prefix=row_prefix,
                template_ref=template_ref,
                resolved_host_os_row=resolved_host_os_row,
                row_by_id=row_by_id,
                stage=stage,
                diagnostics=diagnostics,
            )

        return self.make_result(diagnostics)

    def _validate_architecture_semantics(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_id: Any,
        row_prefix: str,
        template_ref: Any,
        resolved_host_os_row: dict[str, Any] | None,
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        guest_arch = self._guest_architecture(row)
        template_arch = ""
        if isinstance(template_ref, str) and template_ref:
            template_row = row_by_id.get(template_ref)
            if isinstance(template_row, dict):
                template_arch = self._normalize_arch(self._row_architecture(ctx=ctx, row=template_row))
        host_arch = self._normalize_arch(self._row_architecture(ctx=ctx, row=resolved_host_os_row))

        if guest_arch and template_arch and guest_arch != template_arch:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7877",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"VM '{row_id}': guest architecture '{guest_arch}' conflicts with template "
                        f"architecture '{template_arch}'; workload value takes precedence."
                    ),
                    path=f"{row_prefix}.os.architecture",
                )
            )
        if host_arch and template_arch and host_arch != template_arch:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7877",
                    severity="error",
                    stage=stage,
                    message=(
                        f"VM '{row_id}': template architecture '{template_arch}' does not match "
                        f"resolved host OS architecture '{host_arch}'."
                    ),
                    path=f"{row_prefix}.template_ref",
                )
            )
        if host_arch and guest_arch and host_arch != guest_arch:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7877",
                    severity="error",
                    stage=stage,
                    message=(
                        f"VM '{row_id}': guest architecture '{guest_arch}' does not match "
                        f"resolved host OS architecture '{host_arch}'."
                    ),
                    path=f"{row_prefix}.os.architecture",
                )
            )

    def _validate_required_capability(
        self,
        *,
        row_id: Any,
        row_prefix: str,
        required_capability: str,
        resolved_host_os_row: dict[str, Any] | None,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        if not isinstance(resolved_host_os_row, dict):
            return
        host_os_ref = resolved_host_os_row.get("instance")
        host_caps = self._capabilities(resolved_host_os_row)
        if not isinstance(host_caps, list):
            return
        normalized_caps = {str(item).strip().lower() for item in host_caps if isinstance(item, str)}
        if required_capability in normalized_caps:
            return
        diagnostics.append(
            self.emit_diagnostic(
                code="E7877",
                severity="error",
                stage=stage,
                message=(
                    f"VM '{row_id}' resolved host OS '{host_os_ref}' lacks required capability "
                    f"'{required_capability}'."
                ),
                path=f"{row_prefix}.host_os_ref",
            )
        )

    def _validate_ref(
        self,
        *,
        row_id: Any,
        field_name: str,
        value: Any,
        row_by_id: dict[str, dict[str, Any]],
        expected: Any,
        expected_label: str,
        code: str,
        stage: Stage,
        path: str,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        if value is None:
            return
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"VM '{row_id}' {field_name} must be a non-empty string when set.",
                    path=path,
                )
            )
            return

        target = row_by_id.get(value)
        if not isinstance(target, dict) or not expected(target):
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"VM '{row_id}' {field_name} '{value}' must reference a valid {expected_label}.",
                    path=path,
                )
            )

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions
        return {}

    def _resolve_host_os_row(
        self,
        *,
        host_os_ref: Any,
        host_os_row: Any,
        device_row: Any,
        row_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        if isinstance(host_os_ref, str) and isinstance(host_os_row, dict) and host_os_row.get("class_ref") == "class.os":
            return host_os_row
        if not isinstance(device_row, dict):
            return None
        active_os_refs = sorted(self._active_os_refs(device_row=device_row, row_by_id=row_by_id))
        if len(active_os_refs) == 1:
            resolved = row_by_id.get(active_os_refs[0])
            if isinstance(resolved, dict) and resolved.get("class_ref") == "class.os":
                return resolved
        return None

    def _guest_architecture(self, row: dict[str, Any]) -> str:
        extensions = self._extensions(row)
        os_payload = extensions.get("os")
        if not isinstance(os_payload, dict):
            os_payload = row.get("os")
        if isinstance(os_payload, dict):
            architecture = os_payload.get("architecture")
            return self._normalize_arch(architecture)
        return ""

    @staticmethod
    def _row_architecture(*, ctx: PluginContext, row: Any) -> str | None:
        if not isinstance(row, dict):
            return None
        object_ref = row.get("object_ref")
        if isinstance(object_ref, str) and object_ref:
            object_payload = ctx.objects.get(object_ref)
            if isinstance(object_payload, dict):
                architecture = shared_extract_architecture(object_payload)
                if isinstance(architecture, str) and architecture:
                    return architecture
        extensions = VmRefsValidator._extensions(row)
        ext_arch = extensions.get("architecture")
        if isinstance(ext_arch, str) and ext_arch:
            return ext_arch
        row_arch = row.get("architecture")
        if isinstance(row_arch, str) and row_arch:
            return row_arch
        return None

    @staticmethod
    def _capabilities(row: dict[str, Any]) -> Any:
        extensions = VmRefsValidator._extensions(row)
        if "capabilities" in extensions:
            return extensions.get("capabilities")
        return row.get("capabilities")

    @staticmethod
    def _storage_platform(row: dict[str, Any]) -> Any:
        extensions = VmRefsValidator._extensions(row)
        if "platform" in extensions:
            return extensions.get("platform")
        return row.get("platform")

    @classmethod
    def _normalize_arch(cls, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        normalized = value.strip().lower()
        return cls._ARCH_ALIASES.get(normalized, normalized)

    def _active_os_refs(self, *, device_row: dict[str, Any], row_by_id: dict[str, dict[str, Any]]) -> set[str]:
        active_refs: set[str] = set()
        os_refs = device_row.get("os_refs")
        if not isinstance(os_refs, list):
            return active_refs
        for os_ref in os_refs:
            if not isinstance(os_ref, str) or not os_ref:
                continue
            os_row = row_by_id.get(os_ref)
            if not isinstance(os_row, dict) or os_row.get("class_ref") != "class.os":
                continue
            status = str(os_row.get("status") or "").strip().lower()
            if not status or status in self._ACTIVE_OS_STATUSES:
                active_refs.add(os_ref)
        return active_refs
