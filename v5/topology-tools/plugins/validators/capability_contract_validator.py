"""Capability contract validator plugin for v5 topology (ADR 0069 WS3).

Implements parity-oriented semantics of legacy `_validate_capability_contract`.
Ownership can be switched to plugin in plugin-first mode.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capability_derivation import default_firmware_policy as shared_default_firmware_policy
from capability_derivation import derive_firmware_capabilities as shared_derive_firmware_capabilities
from capability_derivation import derive_os_capabilities as shared_derive_os_capabilities
from capability_derivation import extract_firmware_properties as shared_extract_firmware_properties
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


class CapabilityContractValidator(ValidatorJsonPlugin):
    """Validate class/object capability contracts and derived capability coverage."""

    def _subscribe_required(
        self,
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
    def _default_firmware_policy(class_id: str) -> str:
        return shared_default_firmware_policy(class_id)

    @staticmethod
    def _expand_capabilities(
        *,
        direct_caps: list[Any],
        pack_refs: list[Any],
        packs_map: dict[str, dict[str, Any]],
    ) -> set[str]:
        expanded: set[str] = set()
        for cap in direct_caps:
            if isinstance(cap, str):
                expanded.add(cap)
        for pack_ref in pack_refs:
            if not isinstance(pack_ref, str):
                continue
            pack = packs_map.get(pack_ref, {})
            for cap in pack.get("capabilities", []) or []:
                if isinstance(cap, str):
                    expanded.add(cap)
        return expanded

    @staticmethod
    def _extract_firmware_properties(object_payload: dict[str, Any]) -> dict[str, Any]:
        return shared_extract_firmware_properties(object_payload)

    def _extract_os_properties(self, object_payload: dict[str, Any]) -> dict[str, Any] | None:
        _ = self
        return shared_extract_os_properties(object_payload)

    def _derive_firmware_capabilities(
        self,
        *,
        object_id: str,
        object_payload: dict[str, Any],
        catalog_ids: set[str],
        path: str,
        stage: Stage,
    ) -> tuple[set[str], list[PluginDiagnostic]]:
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

        derived, _ = shared_derive_firmware_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=path,
            add_diag=_add_diag,
            emit_diagnostics=True,
        )
        return derived, diagnostics

    def _derive_os_capabilities(
        self,
        *,
        object_id: str,
        object_payload: dict[str, Any],
        catalog_ids: set[str],
        path: str,
        stage: Stage,
    ) -> tuple[set[str], list[PluginDiagnostic]]:
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

        derived, _ = shared_derive_os_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=path,
            add_diag=_add_diag,
            emit_diagnostics=True,
        )
        return derived, diagnostics

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("validation_owner_capability_contract")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        try:
            catalog_ids_raw = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.capability_contract_loader",
                published_key="catalog_ids",
            )
            packs_map_raw = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.capability_contract_loader",
                published_key="packs_map",
            )
            class_paths_raw = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.module_loader",
                published_key="class_module_paths",
            )
            object_paths_raw = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.module_loader",
                published_key="object_module_paths",
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

        catalog_ids = {item for item in (catalog_ids_raw or []) if isinstance(item, str) and item}
        if not catalog_ids:
            return self.make_result(diagnostics)

        packs_map = packs_map_raw if isinstance(packs_map_raw, dict) else {}
        class_paths = class_paths_raw if isinstance(class_paths_raw, dict) else {}
        object_paths = object_paths_raw if isinstance(object_paths_raw, dict) else {}
        require_new_model = bool(ctx.config.get("require_new_model", False))

        class_cap_sets: dict[str, set[str]] = {}
        class_required_sets: dict[str, set[str]] = {}
        valid_os_policies = {"required", "allowed", "forbidden"}
        valid_firmware_policies = {"required", "allowed", "forbidden"}

        for class_id, class_payload in sorted(ctx.classes.items(), key=lambda item: item[0]):
            if not isinstance(class_payload, dict):
                continue

            required = class_payload.get("required_capabilities", []) or []
            optional = class_payload.get("optional_capabilities", []) or []
            pack_refs = class_payload.get("capability_packs", []) or []
            os_policy_raw = class_payload.get("os_policy", "allowed")
            firmware_policy_raw = class_payload.get("firmware_policy", self._default_firmware_policy(class_id))
            path = class_paths.get(class_id, f"class:{class_id}")

            if not isinstance(required, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"class '{class_id}' required_capabilities must be list.",
                        path=path,
                    )
                )
                required = []
            if not isinstance(optional, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"class '{class_id}' optional_capabilities must be list.",
                        path=path,
                    )
                )
                optional = []
            if not isinstance(pack_refs, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"class '{class_id}' capability_packs must be list.",
                        path=path,
                    )
                )
                pack_refs = []

            class_caps: set[str] = set()
            class_required: set[str] = set()
            for cap in required:
                if not isinstance(cap, str) or not cap:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' has invalid required capability entry.",
                            path=path,
                        )
                    )
                    continue
                if cap not in catalog_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' references unknown capability '{cap}'.",
                            path=path,
                        )
                    )
                class_caps.add(cap)
                class_required.add(cap)

            for cap in optional:
                if not isinstance(cap, str) or not cap:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' has invalid optional capability entry.",
                            path=path,
                        )
                    )
                    continue
                if cap not in catalog_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' references unknown capability '{cap}'.",
                            path=path,
                        )
                    )
                class_caps.add(cap)

            for pack_ref in pack_refs:
                if not isinstance(pack_ref, str) or not pack_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' has invalid capability pack reference.",
                            path=path,
                        )
                    )
                    continue
                pack = packs_map.get(pack_ref)
                if pack is None:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' references unknown capability pack '{pack_ref}'.",
                            path=path,
                        )
                    )
                    continue
                pack_class_ref = pack.get("class_ref")
                if isinstance(pack_class_ref, str) and pack_class_ref and pack_class_ref != class_id:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class '{class_id}' references pack '{pack_ref}' bound to class '{pack_class_ref}'.",
                            path=path,
                        )
                    )
                for cap in pack.get("capabilities", []) or []:
                    if isinstance(cap, str):
                        class_caps.add(cap)

            if not isinstance(os_policy_raw, str) or os_policy_raw not in valid_os_policies:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=(
                            f"class '{class_id}' has invalid os_policy '{os_policy_raw}'. "
                            "Expected one of: required, allowed, forbidden."
                        ),
                        path=path,
                    )
                )

            if not isinstance(firmware_policy_raw, str) or firmware_policy_raw not in valid_firmware_policies:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=(
                            f"class '{class_id}' has invalid firmware_policy '{firmware_policy_raw}'. "
                            "Expected one of: required, allowed, forbidden."
                        ),
                        path=path,
                    )
                )

            class_cap_sets[class_id] = class_caps
            class_required_sets[class_id] = class_required

        for object_id, object_payload in sorted(ctx.objects.items(), key=lambda item: item[0]):
            if not isinstance(object_payload, dict):
                continue
            path = object_paths.get(object_id, f"object:{object_id}")
            class_ref = object_payload.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref:
                continue
            if class_ref not in ctx.classes:
                continue

            software_payload = object_payload.get("software")
            prerequisites_payload = object_payload.get("prerequisites")
            has_legacy_os = isinstance(software_payload, dict) and isinstance(software_payload.get("os"), dict)
            has_legacy_os_ref = isinstance(prerequisites_payload, dict) and isinstance(
                prerequisites_payload.get("os_ref"), str
            )
            if has_legacy_os or has_legacy_os_ref:
                severity = "error" if require_new_model else "warning"
                code = "E3202" if require_new_model else "W3201"
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity=severity,
                        stage=stage,
                        message=(
                            f"object '{object_id}' still contains legacy software binding fields "
                            "(software.os or prerequisites.os_ref); migrate bindings to instance-level "
                            "firmware_ref/os_refs."
                        ),
                        path=path,
                    )
                )

            derived_os_caps, os_diags = self._derive_os_capabilities(
                object_id=object_id,
                object_payload=object_payload,
                catalog_ids=catalog_ids,
                path=path,
                stage=stage,
            )
            diagnostics.extend(os_diags)
            derived_firmware_caps, fw_diags = self._derive_firmware_capabilities(
                object_id=object_id,
                object_payload=object_payload,
                catalog_ids=catalog_ids,
                path=path,
                stage=stage,
            )
            diagnostics.extend(fw_diags)

            enabled_caps = object_payload.get("enabled_capabilities", []) or []
            enabled_packs = object_payload.get("enabled_packs", []) or []
            vendor_caps = object_payload.get("vendor_capabilities", []) or []
            if not isinstance(enabled_caps, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"object '{object_id}' enabled_capabilities must be list.",
                        path=path,
                    )
                )
                enabled_caps = []
            if not isinstance(enabled_packs, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"object '{object_id}' enabled_packs must be list.",
                        path=path,
                    )
                )
                enabled_packs = []
            if vendor_caps and not isinstance(vendor_caps, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"object '{object_id}' vendor_capabilities must be list when set.",
                        path=path,
                    )
                )
                vendor_caps = []

            for pack_ref in enabled_packs:
                if not isinstance(pack_ref, str) or not pack_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"object '{object_id}' has invalid enabled_packs entry.",
                            path=path,
                        )
                    )
                    continue
                pack = packs_map.get(pack_ref)
                if pack is None:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"object '{object_id}' references unknown pack '{pack_ref}'.",
                            path=path,
                        )
                    )
                    continue
                pack_class_ref = pack.get("class_ref")
                if isinstance(pack_class_ref, str) and pack_class_ref and pack_class_ref != class_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"object '{object_id}' references pack '{pack_ref}' for class '{pack_class_ref}', "
                                f"but object class_ref is '{class_ref}'."
                            ),
                            path=path,
                        )
                    )

            expanded_declared = self._expand_capabilities(
                direct_caps=enabled_caps,
                pack_refs=enabled_packs,
                packs_map=packs_map,
            )
            expanded_effective = set(expanded_declared)
            expanded_effective.update(derived_os_caps)
            expanded_effective.update(derived_firmware_caps)
            for cap in expanded_declared:
                if cap.startswith("vendor."):
                    continue
                if cap not in catalog_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"object '{object_id}' has unknown capability '{cap}'.",
                            path=path,
                        )
                    )

            for cap in vendor_caps:
                if not isinstance(cap, str) or not cap.startswith("vendor."):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"object '{object_id}' has invalid vendor capability entry '{cap}'.",
                            path=path,
                        )
                    )

            class_allowed = class_cap_sets.get(class_ref, set())
            class_required = class_required_sets.get(class_ref, set())
            missing = sorted(cap for cap in class_required if cap not in expanded_effective)
            if missing:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"object '{object_id}' does not satisfy class '{class_ref}' required capabilities: {missing}",
                        path=path,
                    )
                )

            for cap in sorted(expanded_declared):
                if cap.startswith("vendor."):
                    continue
                if cap not in class_allowed:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"object '{object_id}' capability '{cap}' is outside class '{class_ref}' "
                                "required/optional/packs contract."
                            ),
                            path=path,
                        )
                    )

        return self.make_result(diagnostics)
