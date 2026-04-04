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
    _LEGACY_RUNTIME_HINTS = {
        "container": "runtime.type=docker",
        "native": "runtime.type=baremetal",
        "container_image": "runtime.image",
    }
    _DOCKER_CAPABILITIES = {"docker", "container"}
    _BAREMETAL_ALLOWED_HOST_TYPES = {"baremetal", "embedded", "hypervisor"}
    _ACTIVE_OS_STATUSES = {"active", "mapped", "modeled"}
    _LXC_CLASSES = {"class.compute.workload.lxc"}
    _VM_CLASSES = {"class.compute.workload.vm"}
    _EXTERNAL_SERVICES_DEPRECATION = (
        "L5_application.external_services is deprecated; " "model Docker/Baremetal workloads via services[].runtime."
    )

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
        self._warn_on_legacy_external_services(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
        )
        row_by_id: dict[str, dict[str, Any]] = {}
        active_host_os_by_device: dict[str, list[dict[str, Any]]] = {}
        has_host_os_inventory = any(row.get("class_ref") == "class.os" for row in rows)
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row
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
                if not isinstance(os_ref, str) or not os_ref:
                    continue
                os_row = row_by_id.get(os_ref)
                if not isinstance(os_row, dict) or os_row.get("class_ref") != "class.os":
                    continue
                status = str(os_row.get("status") or "").strip().lower()
                if status and status not in self._ACTIVE_OS_STATUSES:
                    continue
                active_host_os_by_device.setdefault(device_id, []).append(os_row)

        for row in rows:
            class_ref = row.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref.startswith(self._SERVICE_PREFIX):
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            self._validate_service_legacy_contracts(
                ctx=ctx,
                row=row,
                row_id=row_id,
                row_prefix=row_prefix,
                row_by_id=row_by_id,
                stage=stage,
                diagnostics=diagnostics,
            )
            runtime = self._resolve_service_field(ctx=ctx, row=row, key="runtime")
            if not isinstance(runtime, dict):
                continue

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
                if target_class not in self._LXC_CLASSES:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime type lxc requires target class "
                                f"in {sorted(self._LXC_CLASSES)}, got '{target_class}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )
            elif runtime_type == "vm":
                if target_class not in self._VM_CLASSES:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime type vm requires target class "
                                f"in {sorted(self._VM_CLASSES)}, got '{target_class}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )
            elif runtime_type in {"docker", "baremetal"}:
                if target_layer == "L1":
                    self._validate_device_runtime_contract(
                        ctx=ctx,
                        row=row,
                        row_id=row_id,
                        row_prefix=row_prefix,
                        runtime_type=runtime_type,
                        target_ref=target_ref,
                        row_by_id=row_by_id,
                        active_host_os_by_device=active_host_os_by_device,
                        has_host_os_inventory=has_host_os_inventory,
                        stage=stage,
                        diagnostics=diagnostics,
                    )
                elif runtime_type == "docker" and target_layer == "L4" and target_class == "class.compute.workload.docker":
                    pass
                else:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}' runtime type {runtime_type} requires L1 target, "
                                "or for docker a L4 class.compute.workload.docker target, "
                                f"got class '{target_class}' layer '{target_layer}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )

        return self.make_result(diagnostics)

    def _warn_on_legacy_external_services(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        sources = (
            ("L5_application.external_services", self._extract_external_services(ctx.raw_yaml)),
            ("compiled_json.L5_application.external_services", self._extract_external_services(ctx.compiled_json)),
        )
        for path, external_services in sources:
            if not external_services:
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7845",
                    severity="warning",
                    stage=stage,
                    message=self._EXTERNAL_SERVICES_DEPRECATION,
                    path=path,
                )
            )
            return

    @staticmethod
    def _extract_external_services(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return None
        l5_payload = payload.get("L5_application")
        if not isinstance(l5_payload, dict):
            return None
        return l5_payload.get("external_services")

    def _validate_service_legacy_contracts(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_id: Any,
        row_prefix: str,
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        for field_name, replacement in self._LEGACY_RUNTIME_HINTS.items():
            if self._resolve_service_field(ctx=ctx, row=row, key=field_name) is None:
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7845",
                    severity="warning",
                    stage=stage,
                    message=f"Service '{row_id}': legacy field '{field_name}' is deprecated; use {replacement}.",
                    path=f"{row_prefix}.{field_name}",
                )
            )

        config = self._resolve_service_field(ctx=ctx, row=row, key="config")
        docker_cfg = (
            config.get("docker") if isinstance(config, dict) and isinstance(config.get("docker"), dict) else None
        )
        if isinstance(docker_cfg, dict) and docker_cfg.get("host_ip") is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7845",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Service '{row_id}': config.docker.host_ip is deprecated; "
                        "derive binding from runtime.target_ref + runtime.network_binding_ref."
                    ),
                    path=f"{row_prefix}.config.docker.host_ip",
                )
            )

        protocol = str(self._resolve_service_field(ctx=ctx, row=row, key="protocol") or "").strip().lower()
        security = self._resolve_service_field(ctx=ctx, row=row, key="security")
        ssl_certificate = security.get("ssl_certificate") if isinstance(security, dict) else None
        if protocol == "https" and not ssl_certificate:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7845",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Service '{row_id}': protocol 'https' should declare security.ssl_certificate "
                        "(certificate intent/source)."
                    ),
                    path=f"{row_prefix}.security.ssl_certificate",
                )
            )

        self._validate_legacy_refs(
            ctx=ctx,
            row=row,
            row_id=row_id,
            row_prefix=row_prefix,
            row_by_id=row_by_id,
            stage=stage,
            diagnostics=diagnostics,
        )

        runtime = self._resolve_service_field(ctx=ctx, row=row, key="runtime")
        if not isinstance(runtime, dict):
            return
        if self._resolve_service_field(ctx=ctx, row=row, key="ip") is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7845",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Service '{row_id}': legacy field 'ip' with runtime model is deprecated; "
                        "prefer runtime/network binding resolution."
                    ),
                    path=f"{row_prefix}.ip",
                )
            )

        legacy_ref_keys = ("device_ref", "vm_ref", "lxc_ref")
        if any(self._resolve_service_field(ctx=ctx, row=row, key=key) is not None for key in legacy_ref_keys):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7845",
                    severity="warning",
                    stage=stage,
                    message=f"Service '{row_id}': mixing runtime with legacy *_ref fields; prefer runtime only.",
                    path=f"{row_prefix}.runtime",
                )
            )

    def _validate_legacy_refs(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_id: Any,
        row_prefix: str,
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        ref_rules = (
            ("device_ref", "L1", None),
            ("vm_ref", None, self._VM_CLASSES),
            ("lxc_ref", None, self._LXC_CLASSES),
            ("network_ref", None, "class.network.vlan"),
            ("trust_zone_ref", None, "class.network.trust_zone"),
        )
        for field_name, expected_layer, expected_classes in ref_rules:
            value = self._resolve_service_field(ctx=ctx, row=row, key=field_name)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7841",
                        severity="error",
                        stage=stage,
                        message=f"Service '{row_id}': {field_name} must be a non-empty string when set.",
                        path=f"{row_prefix}.{field_name}",
                    )
                )
                continue
            target = row_by_id.get(value)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7841",
                        severity="error",
                        stage=stage,
                        message=f"Service '{row_id}': {field_name} '{value}' does not exist.",
                        path=f"{row_prefix}.{field_name}",
                    )
                )
                continue
            if expected_layer and target.get("layer") != expected_layer:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7841",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Service '{row_id}': {field_name} '{value}' must reference layer {expected_layer}, "
                            f"got '{target.get('layer')}'."
                        ),
                        path=f"{row_prefix}.{field_name}",
                    )
                )
                continue
            if expected_classes:
                target_class = target.get("class_ref")
                if isinstance(expected_classes, str):
                    class_ok = target_class == expected_classes
                    expected_label = expected_classes
                else:
                    class_ok = target_class in expected_classes
                    expected_label = sorted(expected_classes)
                if class_ok:
                    continue
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7841",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Service '{row_id}': {field_name} '{value}' must reference class '{expected_label}', "
                            f"got '{target_class}'."
                        ),
                        path=f"{row_prefix}.{field_name}",
                    )
                )

    def _validate_device_runtime_contract(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_id: Any,
        row_prefix: str,
        runtime_type: str,
        target_ref: Any,
        row_by_id: dict[str, dict[str, Any]],
        active_host_os_by_device: dict[str, list[dict[str, Any]]],
        has_host_os_inventory: bool,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        if runtime_type not in {"docker", "baremetal"}:
            return
        if not isinstance(target_ref, str) or not target_ref:
            return
        target = row_by_id.get(target_ref)
        if not isinstance(target, dict) or target.get("layer") != "L1":
            return

        host_os_entries = active_host_os_by_device.get(target_ref, [])
        if has_host_os_inventory and not host_os_entries:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7841",
                    severity="error",
                    stage=stage,
                    message=(f"Service '{row_id}': runtime target_ref '{target_ref}' has no active host OS entry."),
                    path=f"{row_prefix}.runtime.target_ref",
                )
            )
            return

        if runtime_type == "docker" and host_os_entries:
            capability_declared = any(self._host_os_declares_capabilities(os_row) for os_row in host_os_entries)
            if capability_declared:
                has_container_capability = any(
                    bool(self._host_os_capabilities(os_row) & self._DOCKER_CAPABILITIES) for os_row in host_os_entries
                )
                if not has_container_capability:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}': runtime type docker requires host capability "
                                f"'docker' or 'container' for device '{target_ref}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )

        if runtime_type == "baremetal" and host_os_entries:
            host_type_declared = any(self._host_os_declares_host_type(os_row) for os_row in host_os_entries)
            if host_type_declared:
                has_native_host_type = any(
                    self._host_os_host_type(os_row) in self._BAREMETAL_ALLOWED_HOST_TYPES for os_row in host_os_entries
                )
                if not has_native_host_type:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7841",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Service '{row_id}': runtime type baremetal requires host_type "
                                f"in {sorted(self._BAREMETAL_ALLOWED_HOST_TYPES)} for device '{target_ref}'."
                            ),
                            path=f"{row_prefix}.runtime.target_ref",
                        )
                    )

    @staticmethod
    def _host_os_capabilities(os_row: dict[str, Any]) -> set[str]:
        extensions = os_row.get("extensions")
        raw = None
        if isinstance(extensions, dict) and "capabilities" in extensions:
            raw = extensions.get("capabilities")
        elif "capabilities" in os_row:
            raw = os_row.get("capabilities")
        if not isinstance(raw, list):
            return set()
        return {str(item).strip().lower() for item in raw if isinstance(item, str) and item.strip()}

    @staticmethod
    def _host_os_host_type(os_row: dict[str, Any]) -> str:
        extensions = os_row.get("extensions")
        value = None
        if isinstance(extensions, dict) and "host_type" in extensions:
            value = extensions.get("host_type")
        elif "host_type" in os_row:
            value = os_row.get("host_type")
        return str(value).strip().lower() if isinstance(value, str) else ""

    @staticmethod
    def _host_os_declares_capabilities(os_row: dict[str, Any]) -> bool:
        extensions = os_row.get("extensions")
        if isinstance(extensions, dict) and "capabilities" in extensions:
            return True
        return "capabilities" in os_row

    @staticmethod
    def _host_os_declares_host_type(os_row: dict[str, Any]) -> bool:
        extensions = os_row.get("extensions")
        if isinstance(extensions, dict) and "host_type" in extensions:
            return True
        return "host_type" in os_row

    @staticmethod
    def _resolve_service_field(*, ctx: PluginContext, row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict) and key in extensions:
            return extensions.get(key)
        if key in row:
            return row.get(key)
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        if isinstance(properties, dict):
            return properties.get(key)
        return None
