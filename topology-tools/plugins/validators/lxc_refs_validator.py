"""LXC reference validator."""

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


class LxcRefsValidator(ValidatorJsonPlugin):
    """Validate LXC row references (device/trust-zone/host-os/networks/storage)."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _LXC_CLASSES = {"class.compute.workload.container", "class.compute.workload.lxc"}
    _RESOURCE_PROFILE_REF_FIELD = "resource_profile_ref"
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
                    code="E7880",
                    severity="error",
                    stage=stage,
                    message=f"lxc_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        resource_profiles = self._configured_resource_profiles(ctx)
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        for row in rows:
            if row.get("class_ref") not in self._LXC_CLASSES:
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
                code="E7881",
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
                code="E7882",
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
                code="E7883",
                stage=stage,
                path=f"{row_prefix}.host_os_ref",
                diagnostics=diagnostics,
            )
            if isinstance(host_os_ref, str) and host_os_ref and isinstance(device_row, dict):
                device_os_refs = device_row.get("os_refs")
                if isinstance(device_os_refs, list) and device_os_refs and host_os_ref not in device_os_refs:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7883",
                            severity="error",
                            stage=stage,
                            message=(
                                f"LXC '{row_id}' host_os_ref '{host_os_ref}' is not listed in "
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
                            code="E7883",
                            severity="error",
                            stage=stage,
                            message=(
                                f"LXC '{row_id}' device '{device_ref}' has multiple active OS bindings "
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
                code="E7884",
                stage=stage,
                path=f"{row_prefix}.template_ref",
                diagnostics=diagnostics,
            )
            networks = extensions.get("networks")
            if networks is not None and not isinstance(networks, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7885",
                        severity="error",
                        stage=stage,
                        message="LXC networks must be a list when set.",
                        path=f"{row_prefix}.networks",
                    )
                )
            elif isinstance(networks, list):
                for idx, nic in enumerate(networks):
                    if not isinstance(nic, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7885",
                                severity="error",
                                stage=stage,
                                message="LXC network entries must be objects.",
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
                        code="E7885",
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
                        code="E7885",
                        stage=stage,
                        path=f"{row_prefix}.networks[{idx}].bridge_ref",
                        diagnostics=diagnostics,
                    )

            storage = extensions.get("storage")
            if storage is not None and not isinstance(storage, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7886",
                        severity="error",
                        stage=stage,
                        message="LXC storage must be an object when set.",
                        path=f"{row_prefix}.storage",
                    )
                )
            if isinstance(storage, dict):
                rootfs = storage.get("rootfs")
                if isinstance(rootfs, dict):
                    rootfs_storage_ref = rootfs.get("storage_endpoint_ref")
                    if rootfs_storage_ref is None:
                        rootfs_storage_ref = rootfs.get("storage_ref")
                    self._validate_ref(
                        row_id=row_id,
                        field_name="rootfs.storage_ref",
                        value=rootfs_storage_ref,
                        row_by_id=row_by_id,
                        expected=lambda target: target.get("class_ref") == "class.storage.storage_endpoint",
                        expected_label="class.storage.storage_endpoint instance",
                        code="E7886",
                        stage=stage,
                        path=f"{row_prefix}.storage.rootfs.storage_ref",
                        diagnostics=diagnostics,
                    )
                    if isinstance(rootfs_storage_ref, str):
                        self._validate_storage_platform(
                            row_id=row_id,
                            storage_ref=rootfs_storage_ref,
                            row_by_id=row_by_id,
                            code="E7886",
                            stage=stage,
                            path=f"{row_prefix}.storage.rootfs.storage_ref",
                            diagnostics=diagnostics,
                        )
                    self._validate_ref(
                        row_id=row_id,
                        field_name="rootfs.data_asset_ref",
                        value=rootfs.get("data_asset_ref"),
                        row_by_id=row_by_id,
                        expected=lambda target: target.get("class_ref") == "class.storage.data_asset",
                        expected_label="class.storage.data_asset instance",
                        code="E7887",
                        stage=stage,
                        path=f"{row_prefix}.storage.rootfs.data_asset_ref",
                        diagnostics=diagnostics,
                    )

                volumes = storage.get("volumes")
                if volumes is not None and not isinstance(volumes, list):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7886",
                            severity="error",
                            stage=stage,
                            message="LXC storage.volumes must be a list when set.",
                            path=f"{row_prefix}.storage.volumes",
                        )
                    )
                elif isinstance(volumes, list):
                    for idx, volume in enumerate(volumes):
                        if not isinstance(volume, dict):
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E7886",
                                    severity="error",
                                    stage=stage,
                                    message="LXC storage.volumes entries must be objects.",
                                    path=f"{row_prefix}.storage.volumes[{idx}]",
                                )
                            )
                            continue
                        volume_storage_ref = volume.get("storage_endpoint_ref")
                        if volume_storage_ref is None:
                            volume_storage_ref = volume.get("storage_ref")
                        self._validate_ref(
                            row_id=row_id,
                            field_name="volume.storage_ref",
                            value=volume_storage_ref,
                            row_by_id=row_by_id,
                            expected=lambda target: target.get("class_ref") == "class.storage.storage_endpoint",
                            expected_label="class.storage.storage_endpoint instance",
                            code="E7886",
                            stage=stage,
                            path=f"{row_prefix}.storage.volumes[{idx}].storage_ref",
                            diagnostics=diagnostics,
                        )
                        if isinstance(volume_storage_ref, str):
                            self._validate_storage_platform(
                                row_id=row_id,
                                storage_ref=volume_storage_ref,
                                row_by_id=row_by_id,
                                code="E7886",
                                stage=stage,
                                path=f"{row_prefix}.storage.volumes[{idx}].storage_ref",
                                diagnostics=diagnostics,
                            )
                        self._validate_ref(
                            row_id=row_id,
                            field_name="volume.data_asset_ref",
                            value=volume.get("data_asset_ref"),
                            row_by_id=row_by_id,
                            expected=lambda target: target.get("class_ref") == "class.storage.data_asset",
                            expected_label="class.storage.data_asset instance",
                            code="E7887",
                            stage=stage,
                            path=f"{row_prefix}.storage.volumes[{idx}].data_asset_ref",
                            diagnostics=diagnostics,
                        )

            self._validate_deprecated_fields(
                row=row,
                row_id=row_id,
                row_prefix=row_prefix,
                stage=stage,
                diagnostics=diagnostics,
            )
            self._validate_resource_profile_ref(
                row=row,
                row_id=row_id,
                row_prefix=row_prefix,
                resource_profiles=resource_profiles,
                stage=stage,
                diagnostics=diagnostics,
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
                required_capability="lxc",
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
                    code="W7888",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"LXC '{row_id}': guest architecture '{guest_arch}' conflicts with template "
                        f"architecture '{template_arch}'; workload value takes precedence."
                    ),
                    path=f"{row_prefix}.os.architecture",
                )
            )
        if host_arch and template_arch and host_arch != template_arch:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7888",
                    severity="error",
                    stage=stage,
                    message=(
                        f"LXC '{row_id}': template architecture '{template_arch}' does not match "
                        f"resolved host OS architecture '{host_arch}'."
                    ),
                    path=f"{row_prefix}.template_ref",
                )
            )
        if host_arch and guest_arch and host_arch != guest_arch:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7888",
                    severity="error",
                    stage=stage,
                    message=(
                        f"LXC '{row_id}': guest architecture '{guest_arch}' does not match "
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
                code="E7888",
                severity="error",
                stage=stage,
                message=(
                    f"LXC '{row_id}' resolved host OS '{host_os_ref}' lacks required capability "
                    f"'{required_capability}'."
                ),
                path=f"{row_prefix}.host_os_ref",
            )
        )

    def _validate_storage_platform(
        self,
        *,
        row_id: Any,
        storage_ref: str,
        row_by_id: dict[str, dict[str, Any]],
        code: str,
        stage: Stage,
        path: str,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        storage_target = row_by_id.get(storage_ref)
        if not isinstance(storage_target, dict):
            return
        if storage_target.get("class_ref") != "class.storage.storage_endpoint":
            return
        platform = self._storage_platform(storage_target)
        if isinstance(platform, str) and platform.strip() and platform.strip().lower() != "proxmox":
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=(
                        f"LXC '{row_id}' storage reference '{storage_ref}' has platform '{platform}', "
                        "expected 'proxmox'."
                    ),
                    path=path,
                )
            )

    def _validate_deprecated_fields(
        self,
        *,
        row: dict[str, Any],
        row_id: Any,
        row_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        if self._legacy_field(row, "type") is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7888",
                    severity="warning",
                    stage=stage,
                    message=f"LXC '{row_id}': legacy field 'type' is deprecated; prefer runtime/service contracts.",
                    path=f"{row_prefix}.type",
                )
            )
        if self._legacy_field(row, "role") is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7888",
                    severity="warning",
                    stage=stage,
                    message=f"LXC '{row_id}': legacy field 'role' is deprecated; prefer resource profile contracts.",
                    path=f"{row_prefix}.role",
                )
            )
        if self._legacy_field(row, "resources") is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7888",
                    severity="warning",
                    stage=stage,
                    message=f"LXC '{row_id}': inline 'resources' is deprecated; prefer resource profile refs.",
                    path=f"{row_prefix}.resources",
                )
            )
        ansible_payload = self._legacy_field(row, "ansible")
        ansible_vars = ansible_payload.get("vars") if isinstance(ansible_payload, dict) else None
        if isinstance(ansible_vars, dict):
            app_key_prefixes = (
                "postgresql_",
                "redis_",
                "nextcloud_",
                "grafana_",
                "prometheus_",
                "jellyfin_",
                "homeassistant_",
            )
            if any(isinstance(key, str) and key.startswith(app_key_prefixes) for key in ansible_vars):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7888",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"LXC '{row_id}': application keys in ansible.vars are deprecated; "
                            "move app config to L5 services.config."
                        ),
                        path=f"{row_prefix}.ansible.vars",
                    )
                )

    def _validate_resource_profile_ref(
        self,
        *,
        row: dict[str, Any],
        row_id: Any,
        row_prefix: str,
        resource_profiles: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        profile_ref = self._legacy_field(row, self._RESOURCE_PROFILE_REF_FIELD)
        if profile_ref is None:
            return
        if not isinstance(profile_ref, str) or not profile_ref.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7888",
                    severity="error",
                    stage=stage,
                    message=f"LXC '{row_id}' resource_profile_ref must be a non-empty string when set.",
                    path=f"{row_prefix}.{self._RESOURCE_PROFILE_REF_FIELD}",
                )
            )
            return
        if not resource_profiles:
            return
        if profile_ref not in resource_profiles:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7888",
                    severity="error",
                    stage=stage,
                    message=(
                        f"LXC '{row_id}' resource_profile_ref '{profile_ref}' is unknown; "
                        "add it to base.validator.lxc_refs resource_profiles config."
                    ),
                    path=f"{row_prefix}.{self._RESOURCE_PROFILE_REF_FIELD}",
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
                    message=f"LXC '{row_id}' {field_name} must be a non-empty string when set.",
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
                    message=f"LXC '{row_id}' {field_name} '{value}' must reference a valid {expected_label}.",
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
        if (
            isinstance(host_os_ref, str)
            and isinstance(host_os_row, dict)
            and host_os_row.get("class_ref") == "class.os"
        ):
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
        extensions = LxcRefsValidator._extensions(row)
        ext_arch = extensions.get("architecture")
        if isinstance(ext_arch, str) and ext_arch:
            return ext_arch
        row_arch = row.get("architecture")
        if isinstance(row_arch, str) and row_arch:
            return row_arch
        return None

    @staticmethod
    def _capabilities(row: dict[str, Any]) -> Any:
        extensions = LxcRefsValidator._extensions(row)
        if "capabilities" in extensions:
            return extensions.get("capabilities")
        return row.get("capabilities")

    @staticmethod
    def _storage_platform(row: dict[str, Any]) -> Any:
        extensions = LxcRefsValidator._extensions(row)
        if "platform" in extensions:
            return extensions.get("platform")
        return row.get("platform")

    @staticmethod
    def _legacy_field(row: dict[str, Any], field_name: str) -> Any:
        extensions = LxcRefsValidator._extensions(row)
        if field_name in extensions:
            return extensions.get(field_name)
        return row.get(field_name)

    @staticmethod
    def _configured_resource_profiles(ctx: PluginContext) -> dict[str, dict[str, Any]]:
        raw = ctx.config.get("resource_profiles")
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, dict[str, Any]] = {}
        for key, payload in raw.items():
            if not isinstance(key, str) or not key.strip():
                continue
            if not isinstance(payload, dict):
                continue
            normalized[key] = payload
        return normalized

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
