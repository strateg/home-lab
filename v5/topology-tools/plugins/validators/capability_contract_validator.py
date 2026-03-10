"""Capability contract validator plugin for v5 topology (ADR 0069 WS3).

Implements parity-oriented semantics of legacy `_validate_capability_contract`.
Ownership can be switched to plugin in plugin-first mode.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


class CapabilityContractValidator(ValidatorJsonPlugin):
    """Validate class/object capability contracts and derived capability coverage."""

    @staticmethod
    def _normalize_release_token(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    @staticmethod
    def _default_firmware_policy(class_id: str) -> str:
        if class_id.startswith("class.service."):
            return "forbidden"
        if class_id == "class.compute.workload.container":
            return "forbidden"
        if class_id.startswith("class.power."):
            return "required"
        if class_id in {
            "class.router",
            "class.compute.cloud_vm",
            "class.compute.edge_node",
            "class.compute.hypervisor",
        }:
            return "required"
        return "allowed"

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
        properties = object_payload.get("properties")
        if isinstance(properties, dict):
            return dict(properties)
        return {}

    def _extract_os_properties(self, object_payload: dict[str, Any]) -> dict[str, Any] | None:
        properties = object_payload.get("properties")
        if isinstance(properties, dict):
            family = properties.get("family")
            architecture = properties.get("architecture")
            if isinstance(family, str) and family and isinstance(architecture, str) and architecture:
                return dict(properties)

        software = object_payload.get("software")
        if isinstance(software, dict):
            os_payload = software.get("os")
            if isinstance(os_payload, dict):
                family = os_payload.get("family")
                architecture = os_payload.get("architecture")
                if isinstance(family, str) and family and isinstance(architecture, str) and architecture:
                    return dict(os_payload)
        return None

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
        properties = self._extract_firmware_properties(object_payload)
        vendor = properties.get("vendor")
        family = properties.get("family")
        architecture = properties.get("architecture")
        boot_stack = properties.get("boot_stack")
        virtual = properties.get("virtual")

        if not isinstance(vendor, str) or not vendor or not isinstance(family, str) or not family:
            return set(), diagnostics

        derived: set[str] = {f"cap.firmware.{vendor}", f"cap.firmware.{family}"}
        if isinstance(architecture, str) and architecture:
            derived.add(f"cap.firmware.arch.{architecture}")
            derived.add(f"cap.arch.{architecture}")
        if isinstance(boot_stack, str) and boot_stack:
            derived.add(f"cap.firmware.boot.{boot_stack}")
        if isinstance(virtual, bool) and virtual:
            derived.add("cap.firmware.virtual")

        for cap in sorted(derived):
            if cap not in catalog_ids:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W3201",
                        severity="warning",
                        stage=stage,
                        message=f"firmware object '{object_id}' derived capability '{cap}' is missing in capability catalog.",
                        path=path,
                    )
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
        class_ref = object_payload.get("class_ref")
        if class_ref == "class.firmware":
            return set(), diagnostics
        os_payload = self._extract_os_properties(object_payload)
        if not isinstance(os_payload, dict):
            return set(), diagnostics

        family = os_payload.get("family")
        architecture = os_payload.get("architecture")
        if not isinstance(family, str) or not family or not isinstance(architecture, str) or not architecture:
            return set(), diagnostics

        distribution = os_payload.get("distribution")
        release = os_payload.get("release")
        release_id = os_payload.get("release_id")
        codename = os_payload.get("codename")
        init_system = os_payload.get("init_system")
        package_manager = os_payload.get("package_manager")
        kernel = os_payload.get("kernel")

        if not isinstance(distribution, str) or not distribution:
            distribution = None
        if not isinstance(release, str) or not release:
            release = None
        if not isinstance(release_id, str) or not release_id:
            release_id = None
        if not isinstance(codename, str) or not codename:
            codename = None
        if not isinstance(init_system, str) or not init_system:
            init_system = None
        if not isinstance(package_manager, str) or not package_manager:
            package_manager = None
        if not isinstance(kernel, str) or not kernel:
            kernel = None

        if release and not release_id:
            release_id = self._normalize_release_token(release)
        if release and release_id:
            normalized_release = self._normalize_release_token(release)
            normalized_release_id = self._normalize_release_token(release_id)
            if normalized_release != normalized_release_id:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=(
                            f"object '{object_id}' software.os.release '{release}' does not match "
                            f"release_id '{release_id}' after normalization."
                        ),
                        path=path,
                    )
                )
                return set(), diagnostics
            release_id = normalized_release_id

        distro_inference: dict[str, tuple[str, str]] = {
            "debian": ("systemd", "apt"),
            "ubuntu": ("systemd", "apt"),
            "alpine": ("openrc", "apk"),
            "fedora": ("systemd", "dnf"),
            "nixos": ("systemd", "nix"),
            "routeros": ("proprietary", "none"),
            "openwrt": ("busybox", "opkg"),
        }
        if distribution and distribution in distro_inference:
            default_init, default_pkg = distro_inference[distribution]
            if init_system is None:
                init_system = default_init
            if package_manager is None:
                package_manager = default_pkg

        family_kernel_map = {
            "linux": "linux",
            "bsd": "bsd",
            "windows": "nt",
            "routeros": "proprietary",
            "proprietary": "proprietary",
        }
        if kernel is None:
            kernel = family_kernel_map.get(family)

        derived: set[str] = {f"cap.os.{family}", f"cap.arch.{architecture}"}
        if distribution:
            derived.add(f"cap.os.{distribution}")
        if distribution and release_id:
            derived.add(f"cap.os.{distribution}.{release_id}")
        if distribution and codename:
            derived.add(f"cap.os.{distribution}.{codename}")
        if init_system:
            derived.add(f"cap.os.init.{init_system}")
        if package_manager:
            derived.add(f"cap.os.pkg.{package_manager}")

        for cap in sorted(derived):
            if cap not in catalog_ids:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W3201",
                        severity="warning",
                        stage=stage,
                        message=f"object '{object_id}' derived capability '{cap}' is missing in capability catalog.",
                        path=path,
                    )
                )
        return derived, diagnostics

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("validation_owner_capability_contract")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        catalog_ids = {
            item for item in (ctx.config.get("capability_catalog_ids") or []) if isinstance(item, str) and item
        }
        if not catalog_ids:
            return self.make_result(diagnostics)

        packs_map_raw = ctx.config.get("capability_packs")
        packs_map = packs_map_raw if isinstance(packs_map_raw, dict) else {}
        class_paths_raw = ctx.config.get("class_module_paths")
        class_paths = class_paths_raw if isinstance(class_paths_raw, dict) else {}
        object_paths_raw = ctx.config.get("object_module_paths")
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
