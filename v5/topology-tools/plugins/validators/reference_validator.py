"""Reference validation plugin for v5 topology compiler (ADR 0069 WS3 prep).

Implements parity-oriented reference validation semantics equivalent to the
legacy `_validate_refs` path. Ownership can be switched to plugin in cutover.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capability_derivation import default_firmware_policy as shared_default_firmware_policy
from capability_derivation import derive_firmware_capabilities as shared_derive_firmware_capabilities
from capability_derivation import derive_os_capabilities as shared_derive_os_capabilities
from capability_derivation import extract_architecture as shared_extract_architecture
from capability_derivation import extract_firmware_properties as shared_extract_firmware_properties
from capability_derivation import extract_os_installation_model as shared_extract_os_installation_model
from capability_derivation import extract_os_properties as shared_extract_os_properties
from capability_derivation import normalize_release_token as shared_normalize_release_token
from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class ReferenceValidator(ValidatorJsonPlugin):
    """Validate references, software binding policies, and compatibility rules."""

    _STORAGE_RELATION_RULES: tuple[dict[str, Any], ...] = (
        {
            "relation": "storage.pool_ref",
            "namespace": "storage",
            "field": "pool_ref",
            "source_layers": {"L4"},
            "target_layers": {"L3"},
            "target_class": "class.storage.pool",
            "codes": {
                "not_found": "E7401",
                "target_invalid": "E7402",
                "source_invalid": "E7403",
                "format_invalid": "E7404",
            },
        },
        {
            "relation": "storage.volume_ref",
            "namespace": "storage",
            "field": "volume_ref",
            "source_layers": {"L5"},
            "target_layers": {"L3"},
            "target_class": "class.storage.volume",
            "codes": {
                "not_found": "E7401",
                "target_invalid": "E7402",
                "source_invalid": "E7403",
                "format_invalid": "E7404",
            },
        },
    )

    _NETWORK_RELATION_RULES: tuple[dict[str, Any], ...] = (
        {
            "relation": "network.bridge_ref",
            "namespace": "network",
            "field": "bridge_ref",
            "source_layers": {"L4"},
            "target_layers": {"L2"},
            "target_class": "class.network.bridge",
            "codes": {
                "not_found": "E7501",
                "target_invalid": "E7502",
                "source_invalid": "E7503",
                "format_invalid": "E7504",
            },
        },
    )

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
    def _normalize_release_token(value: str) -> str:
        return shared_normalize_release_token(value)

    @staticmethod
    def _extract_architecture(object_payload: dict[str, Any]) -> str | None:
        return shared_extract_architecture(object_payload)

    @staticmethod
    def _extract_os_installation_model(object_payload: dict[str, Any]) -> str | None:
        return shared_extract_os_installation_model(object_payload)

    @staticmethod
    def _extract_firmware_properties(object_payload: dict[str, Any]) -> dict[str, Any]:
        return shared_extract_firmware_properties(object_payload)

    def _extract_os_properties(self, object_payload: dict[str, Any]) -> dict[str, Any] | None:
        _ = self
        return shared_extract_os_properties(object_payload)

    @staticmethod
    def _default_firmware_policy(class_id: str) -> str:
        return shared_default_firmware_policy(class_id)

    def _derive_firmware_capabilities(
        self,
        *,
        object_id: str,
        object_payload: dict[str, Any],
        catalog_ids: set[str],
        path: str,
        stage: Stage,
    ) -> tuple[set[str], dict[str, Any] | None, list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []
        stage_enum = stage

        def _add_diag(*, code: str, severity: str, stage: str, message: str, path: str) -> None:
            _ = stage
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity=severity,
                    stage=stage_enum,
                    message=message,
                    path=path,
                )
            )

        derived, effective = shared_derive_firmware_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=path,
            add_diag=_add_diag,
            emit_diagnostics=True,
        )
        return derived, effective, diagnostics

    def _derive_os_capabilities(
        self,
        *,
        object_id: str,
        object_payload: dict[str, Any],
        catalog_ids: set[str],
        path: str,
        stage: Stage,
    ) -> tuple[set[str], dict[str, Any] | None, list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []
        stage_enum = stage

        def _add_diag(*, code: str, severity: str, stage: str, message: str, path: str) -> None:
            _ = stage
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity=severity,
                    stage=stage_enum,
                    message=message,
                    path=path,
                )
            )

        derived, effective = shared_derive_os_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=path,
            add_diag=_add_diag,
            emit_diagnostics=True,
        )
        return derived, effective, diagnostics

    @staticmethod
    def _extract_relation_ref_candidate(
        row: dict[str, Any],
        *,
        namespace: str,
        field: str,
    ) -> tuple[Any | None, str | None, bool]:
        extensions = row.get("extensions")
        if not isinstance(extensions, dict):
            return None, None, False
        if field in extensions:
            return extensions.get(field), f"extensions.{field}", False
        nested = extensions.get(namespace)
        if isinstance(nested, dict) and field in nested:
            return nested.get(field), f"extensions.{namespace}.{field}", True
        return None, None, False

    def _validate_relation_rules(
        self,
        *,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        rules: tuple[dict[str, Any], ...],
    ) -> None:
        for row in rows:
            group_name = row.get("group")
            row_id = row.get("instance")
            row_layer = row.get("layer")
            if not isinstance(group_name, str) or not isinstance(row_id, str):
                continue
            path_prefix = f"instance:{group_name}:{row_id}"

            for rule in rules:
                field = rule["field"]
                relation = rule["relation"]
                namespace = rule["namespace"]
                source_layers = rule["source_layers"]
                target_layers = rule["target_layers"]
                expected_target_class = rule["target_class"]
                codes = rule["codes"]

                candidate, local_path, namespaced = self._extract_relation_ref_candidate(
                    row,
                    namespace=namespace,
                    field=field,
                )
                if local_path is None:
                    continue
                full_path = f"{path_prefix}.{local_path}"

                if not isinstance(candidate, str) or not candidate:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=codes["format_invalid"],
                            severity="error",
                            stage=stage,
                            message=(f"'{relation}' must be a non-empty instance id string in row '{row_id}'."),
                            path=full_path,
                        )
                    )
                    continue

                if row_layer not in source_layers:
                    if not namespaced:
                        # Flat field names may belong to class-local properties
                        # (for example L2 vlan.bridge_ref). Ignore those here.
                        continue
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=codes["source_invalid"],
                            severity="error",
                            stage=stage,
                            message=(
                                f"Row '{row_id}' layer '{row_layer}' cannot use relation '{relation}'; "
                                f"allowed source layers: {sorted(source_layers)}."
                            ),
                            path=full_path,
                        )
                    )
                    continue

                target_row = row_by_id.get(candidate)
                if not isinstance(target_row, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=codes["not_found"],
                            severity="error",
                            stage=stage,
                            message=(f"Row '{row_id}' references unknown {relation} target '{candidate}'."),
                            path=full_path,
                        )
                    )
                    continue

                target_layer = target_row.get("layer")
                target_class = target_row.get("class_ref")
                if target_layer not in target_layers or target_class != expected_target_class:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=codes["target_invalid"],
                            severity="error",
                            stage=stage,
                            message=(
                                f"Target '{candidate}' is invalid for relation '{relation}': "
                                f"expected class '{expected_target_class}' on layers {sorted(target_layers)}, "
                                f"got class '{target_class}' on layer '{target_layer}'."
                            ),
                            path=full_path,
                        )
                    )

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("validation_owner_references")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        class_map: dict[str, dict[str, Any]] = {}
        for class_id, payload in ctx.classes.items():
            if isinstance(class_id, str) and isinstance(payload, dict):
                class_map[class_id] = payload

        object_map: dict[str, dict[str, Any]] = {}
        for object_id, payload in ctx.objects.items():
            if isinstance(object_id, str) and isinstance(payload, dict):
                object_map[object_id] = payload

        try:
            raw_rows = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.instance_rows",
                published_key="normalized_rows",
            )
            catalog_ids_raw = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.capability_contract_loader",
                published_key="catalog_ids",
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

        rows: list[dict[str, Any]] = []
        if isinstance(raw_rows, list):
            rows = [row for row in raw_rows if isinstance(row, dict)]

        catalog_ids = {item for item in (catalog_ids_raw or []) if isinstance(item, str) and item}

        valid_os_policies = {"required", "allowed", "forbidden"}
        valid_firmware_policies = {"required", "allowed", "forbidden"}

        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # Phase 0: planned cross-layer relations from ADR0062.
        self._validate_relation_rules(
            rows=rows,
            row_by_id=row_by_id,
            stage=stage,
            diagnostics=diagnostics,
            rules=self._STORAGE_RELATION_RULES,
        )
        self._validate_relation_rules(
            rows=rows,
            row_by_id=row_by_id,
            stage=stage,
            diagnostics=diagnostics,
            rules=self._NETWORK_RELATION_RULES,
        )

        # Phase 1: base class/object references.
        for row in rows:
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            path = f"instance:{row.get('group')}:{row.get('instance')}"

            if not isinstance(class_ref, str) or not class_ref:
                continue
            if not isinstance(object_ref, str) or not object_ref:
                continue

            class_payload = class_map.get(class_ref)
            object_payload = object_map.get(object_ref)

            if class_payload is None:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E2101",
                        severity="error",
                        stage="resolve",
                        message=f"Instance references unknown class_ref '{class_ref}'.",
                        path=path,
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if object_payload is None:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E2101",
                        severity="error",
                        stage="resolve",
                        message=f"Instance references unknown object_ref '{object_ref}'.",
                        path=path,
                        plugin_id=self.plugin_id,
                    )
                )
                continue

            object_class_ref = object_payload.get("class_ref")
            if object_class_ref != class_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E2403",
                        severity="error",
                        stage=stage,
                        message=f"object_ref '{object_ref}' requires class_ref '{object_class_ref}', got '{class_ref}'.",
                        path=path,
                    )
                )

        # Phase 2: software reference policies + compatibility checks.
        for row in rows:
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            row_id = row.get("instance")
            path = f"instance:{row.get('group')}:{row.get('instance')}"

            if not isinstance(class_ref, str) or not class_ref:
                continue
            if not isinstance(object_ref, str) or not object_ref:
                continue
            if not isinstance(row_id, str) or not row_id:
                continue

            class_payload = class_map.get(class_ref, {})
            object_payload = object_map.get(object_ref, {})

            os_policy = class_payload.get("os_policy", "allowed")
            if not isinstance(os_policy, str) or os_policy not in valid_os_policies:
                os_policy = "allowed"

            firmware_policy = class_payload.get("firmware_policy", self._default_firmware_policy(class_ref))
            if not isinstance(firmware_policy, str) or firmware_policy not in valid_firmware_policies:
                firmware_policy = self._default_firmware_policy(class_ref)

            firmware_ref = row.get("firmware_ref")
            os_refs = row.get("os_refs", []) or []
            if not isinstance(os_refs, list):
                os_refs = []

            if firmware_policy == "required" and not isinstance(firmware_ref, str):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance '{row_id}' class '{class_ref}' requires firmware_ref (inst.firmware.*).",
                        path=path,
                    )
                )
            if firmware_policy == "forbidden" and isinstance(firmware_ref, str):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance '{row_id}' class '{class_ref}' forbids firmware_ref.",
                        path=path,
                    )
                )

            if os_policy == "required" and not os_refs:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance '{row_id}' class '{class_ref}' requires os_refs[] (inst.os.*).",
                        path=path,
                    )
                )
            if os_policy == "forbidden" and os_refs:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance '{row_id}' class '{class_ref}' forbids os_refs[].",
                        path=path,
                    )
                )

            cardinality = class_payload.get("os_cardinality")
            min_os = 0
            max_os = 1
            if isinstance(cardinality, dict):
                min_raw = cardinality.get("min", min_os)
                max_raw = cardinality.get("max", max_os)
                if isinstance(min_raw, int) and min_raw >= 0:
                    min_os = min_raw
                if isinstance(max_raw, int) and max_raw >= 0:
                    max_os = max_raw
            else:
                if os_policy == "required":
                    min_os, max_os = 1, 1
                elif os_policy == "forbidden":
                    min_os, max_os = 0, 0
            if max_os < min_os:
                max_os = min_os

            os_count = len(os_refs)
            if os_count < min_os or os_count > max_os:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=(
                            f"instance '{row_id}' os_refs cardinality is {os_count}, "
                            f"expected range [{min_os}, {max_os}] for class '{class_ref}'."
                        ),
                        path=path,
                    )
                )

            multi_boot = class_payload.get("multi_boot", False)
            if not isinstance(multi_boot, bool):
                multi_boot = False
            if not multi_boot and os_count > 1:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance '{row_id}' has multiple OS refs but class '{class_ref}' has multi_boot=false.",
                        path=path,
                    )
                )

            seen_os_refs: set[str] = set()
            for os_ref in os_refs:
                if os_ref in seen_os_refs:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E2102",
                            severity="error",
                            stage="resolve",
                            message=f"instance '{row_id}' has duplicate os_refs entry '{os_ref}'.",
                            path=path,
                            plugin_id=self.plugin_id,
                        )
                    )
                seen_os_refs.add(os_ref)

            firmware_row: dict[str, Any] | None = None
            if isinstance(firmware_ref, str):
                firmware_row = row_by_id.get(firmware_ref)
                if firmware_row is None:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E2101",
                            severity="error",
                            stage="resolve",
                            message=f"instance '{row_id}' references unknown firmware_ref '{firmware_ref}'.",
                            path=path,
                            plugin_id=self.plugin_id,
                        )
                    )
                else:
                    firmware_class = firmware_row.get("class_ref")
                    if firmware_class != "class.firmware":
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E2403",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"instance '{row_id}' firmware_ref '{firmware_ref}' must reference class.firmware, "
                                    f"got '{firmware_class}'."
                                ),
                                path=path,
                            )
                        )

            resolved_os_rows: list[dict[str, Any]] = []
            for os_ref in os_refs:
                os_row = row_by_id.get(os_ref)
                if os_row is None:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E2101",
                            severity="error",
                            stage="resolve",
                            message=f"instance '{row_id}' references unknown os_ref '{os_ref}'.",
                            path=path,
                            plugin_id=self.plugin_id,
                        )
                    )
                    continue
                os_class = os_row.get("class_ref")
                if os_class != "class.os":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2403",
                            severity="error",
                            stage=stage,
                            message=f"instance '{row_id}' os_ref '{os_ref}' must reference class.os, got '{os_class}'.",
                            path=path,
                        )
                    )
                    continue
                resolved_os_rows.append(os_row)

            device_arch = self._extract_architecture(object_payload)
            firmware_arch: str | None = None
            if isinstance(firmware_row, dict):
                firmware_object_ref = firmware_row.get("object_ref")
                if isinstance(firmware_object_ref, str):
                    firmware_object_payload = object_map.get(firmware_object_ref, {})
                    firmware_arch = self._extract_architecture(firmware_object_payload)
                    _, _, fw_diags = self._derive_firmware_capabilities(
                        object_id=firmware_object_ref,
                        object_payload=firmware_object_payload,
                        catalog_ids=catalog_ids,
                        path=path,
                        stage=stage,
                    )
                    diagnostics.extend(fw_diags)

            if device_arch and firmware_arch and device_arch != firmware_arch:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=(
                            f"instance '{row_id}' architecture mismatch: device='{device_arch}' "
                            f"firmware='{firmware_arch}'."
                        ),
                        path=path,
                    )
                )

            allowed_install_models = class_payload.get("allowed_os_install_models")
            if not isinstance(allowed_install_models, list):
                allowed_install_models = []

            for os_row in resolved_os_rows:
                os_instance_id = os_row.get("instance")
                os_object_ref = os_row.get("object_ref")
                if not isinstance(os_object_ref, str):
                    continue
                os_object_payload = object_map.get(os_object_ref, {})
                os_arch = self._extract_architecture(os_object_payload)
                _, _, os_diags = self._derive_os_capabilities(
                    object_id=os_object_ref,
                    object_payload=os_object_payload,
                    catalog_ids=catalog_ids,
                    path=path,
                    stage=stage,
                )
                diagnostics.extend(os_diags)

                if device_arch and os_arch and device_arch != os_arch:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"instance '{row_id}' architecture mismatch: device='{device_arch}' "
                                f"os_ref '{os_instance_id}'='{os_arch}'."
                            ),
                            path=path,
                        )
                    )
                if firmware_arch and os_arch and firmware_arch != os_arch:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"instance '{row_id}' architecture mismatch: firmware='{firmware_arch}' "
                                f"os_ref '{os_instance_id}'='{os_arch}'."
                            ),
                            path=path,
                        )
                    )

                install_model = self._extract_os_installation_model(os_object_payload)
                if allowed_install_models and isinstance(install_model, str):
                    if install_model not in allowed_install_models:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E3201",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"instance '{row_id}' os_ref '{os_instance_id}' installation_model "
                                    f"'{install_model}' is outside allowed models {allowed_install_models} "
                                    f"for class '{class_ref}'."
                                ),
                                path=path,
                            )
                        )

        return self.make_result(diagnostics)
