"""Effective model candidate compiler plugin (ADR 0069 WS2).

Builds a parity-focused candidate compiled model from loaded class/object
modules and instance bindings. During migration, this mirrors legacy effective
assembly so parity gate can compare equivalent payloads.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class EffectiveModelCompiler(CompilerPlugin):
    """Assemble candidate effective model in compile stage."""

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
        self, *, object_payload: dict[str, Any]
    ) -> tuple[set[str], dict[str, Any] | None]:
        properties = self._extract_firmware_properties(object_payload)
        vendor = properties.get("vendor")
        family = properties.get("family")
        architecture = properties.get("architecture")
        boot_stack = properties.get("boot_stack")
        virtual = properties.get("virtual")

        if not isinstance(vendor, str) or not vendor or not isinstance(family, str) or not family:
            return set(), None

        derived: set[str] = {f"cap.firmware.{vendor}", f"cap.firmware.{family}"}
        if isinstance(architecture, str) and architecture:
            derived.add(f"cap.firmware.arch.{architecture}")
            derived.add(f"cap.arch.{architecture}")
        if isinstance(boot_stack, str) and boot_stack:
            derived.add(f"cap.firmware.boot.{boot_stack}")
        if isinstance(virtual, bool) and virtual:
            derived.add("cap.firmware.virtual")

        effective: dict[str, Any] = {"vendor": vendor, "family": family}
        if isinstance(architecture, str) and architecture:
            effective["architecture"] = architecture
        if isinstance(boot_stack, str) and boot_stack:
            effective["boot_stack"] = boot_stack
        if isinstance(virtual, bool):
            effective["virtual"] = virtual
        return derived, effective

    def _derive_os_capabilities(self, *, object_payload: dict[str, Any]) -> tuple[set[str], dict[str, Any] | None]:
        class_ref = object_payload.get("class_ref")
        if class_ref == "class.firmware":
            return set(), None

        os_payload = self._extract_os_properties(object_payload)
        if not isinstance(os_payload, dict):
            return set(), None

        family = os_payload.get("family")
        architecture = os_payload.get("architecture")
        if not isinstance(family, str) or not family or not isinstance(architecture, str) or not architecture:
            return set(), None

        distribution = os_payload.get("distribution")
        release = os_payload.get("release")
        release_id = os_payload.get("release_id")
        codename = os_payload.get("codename")
        init_system = os_payload.get("init_system")
        package_manager = os_payload.get("package_manager")
        kernel = os_payload.get("kernel")
        eol_date = os_payload.get("eol_date")

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
        if not isinstance(eol_date, str) or not eol_date:
            eol_date = None

        if release and not release_id:
            release_id = self._normalize_release_token(release)
        if release and release_id:
            normalized_release = self._normalize_release_token(release)
            normalized_release_id = self._normalize_release_token(release_id)
            if normalized_release != normalized_release_id:
                return set(), None
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

        effective_os: dict[str, Any] = {
            "family": family,
            "architecture": architecture,
        }
        if distribution:
            effective_os["distribution"] = distribution
        if release:
            effective_os["release"] = release
        if release_id:
            effective_os["release_id"] = release_id
        if codename:
            effective_os["codename"] = codename
        if init_system:
            effective_os["init_system"] = init_system
        if package_manager:
            effective_os["package_manager"] = package_manager
        if kernel:
            effective_os["kernel"] = kernel
        if eol_date:
            effective_os["eol_date"] = eol_date

        return derived, effective_os

    @staticmethod
    def _normalize_instance_rows(raw_bindings: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_instances: set[str] = set()
        for group_name, group_rows in raw_bindings.items():
            if not isinstance(group_rows, list):
                continue

            for row in group_rows:
                if not isinstance(row, dict):
                    continue

                instance_id = row.get("instance")
                if not isinstance(instance_id, str) or not instance_id:
                    continue
                if instance_id in seen_instances:
                    continue
                seen_instances.add(instance_id)

                os_refs = row.get("os_refs")
                if not isinstance(os_refs, list):
                    os_refs = []
                normalized_os_refs: list[str] = []
                for os_ref in os_refs:
                    if isinstance(os_ref, str) and os_ref:
                        normalized_os_refs.append(os_ref)

                embedded_in = row.get("embedded_in")
                if not isinstance(embedded_in, str) or not embedded_in:
                    embedded_in = None

                firmware_ref = row.get("firmware_ref")
                if not isinstance(firmware_ref, str) or not firmware_ref:
                    firmware_ref = None

                rows.append(
                    {
                        "group": group_name,
                        "instance": instance_id,
                        "layer": row.get("layer"),
                        "source_id": row.get("source_id", instance_id),
                        "class_ref": row.get("class_ref"),
                        "object_ref": row.get("object_ref"),
                        "status": row.get("status", "pending"),
                        "notes": row.get("notes", ""),
                        "runtime": row.get("runtime"),
                        "firmware_ref": firmware_ref,
                        "os_refs": normalized_os_refs,
                        "embedded_in": embedded_in,
                    }
                )
        return rows

    def _derive_object_effective(
        self, *, objects: dict[str, Any]
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
        object_derived_caps: dict[str, list[str]] = {}
        object_effective_os: dict[str, dict[str, Any]] = {}
        for object_id, payload in objects.items():
            object_payload = payload if isinstance(payload, dict) else {}
            os_caps, effective_os = self._derive_os_capabilities(object_payload=object_payload)
            object_derived_caps[object_id] = sorted(os_caps)
            if effective_os:
                object_effective_os[object_id] = effective_os
        return object_derived_caps, object_effective_os

    def _derive_instance_effective(
        self, *, rows: list[dict[str, Any]], objects: dict[str, Any]
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        instance_derived_caps: dict[str, list[str]] = {}
        instance_software_refs: dict[str, dict[str, Any]] = {}

        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue

            firmware_ref = row.get("firmware_ref")
            os_refs = row.get("os_refs", []) or []
            if not isinstance(os_refs, list):
                os_refs = []

            derived_caps: set[str] = set()
            firmware_effective: dict[str, Any] | None = None

            firmware_row: dict[str, Any] | None = None
            if isinstance(firmware_ref, str):
                candidate = row_by_id.get(firmware_ref)
                if isinstance(candidate, dict):
                    firmware_row = candidate

            if isinstance(firmware_row, dict):
                firmware_object_ref = firmware_row.get("object_ref")
                if isinstance(firmware_object_ref, str):
                    firmware_object_payload = objects.get(firmware_object_ref, {})
                    if not isinstance(firmware_object_payload, dict):
                        firmware_object_payload = {}
                    fw_caps, fw_effective = self._derive_firmware_capabilities(object_payload=firmware_object_payload)
                    derived_caps.update(fw_caps)
                    firmware_effective = fw_effective

            resolved_os_refs: list[str] = []
            resolved_os_effective: list[dict[str, Any]] = []
            for os_ref in os_refs:
                os_row = row_by_id.get(os_ref)
                if not isinstance(os_row, dict):
                    continue
                if os_row.get("class_ref") != "class.os":
                    continue
                os_object_ref = os_row.get("object_ref")
                if not isinstance(os_object_ref, str):
                    continue
                os_object_payload = objects.get(os_object_ref, {})
                if not isinstance(os_object_payload, dict):
                    os_object_payload = {}
                os_caps, os_effective = self._derive_os_capabilities(object_payload=os_object_payload)
                derived_caps.update(os_caps)
                if isinstance(os_effective, dict):
                    resolved_os_effective.append(os_effective)
                os_instance_id = os_row.get("instance")
                if isinstance(os_instance_id, str):
                    resolved_os_refs.append(os_instance_id)

            instance_derived_caps[row_id] = sorted(derived_caps)
            instance_software_refs[row_id] = {
                "firmware_ref": firmware_ref if isinstance(firmware_ref, str) else None,
                "os_refs": resolved_os_refs,
                "effective": {
                    "firmware": firmware_effective,
                    "os": resolved_os_effective,
                },
            }

        return instance_derived_caps, instance_software_refs

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        raw_bindings = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(raw_bindings, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="instance_bindings must contain mapping 'instance_bindings'.",
                    path="instance_bindings",
                )
            )
            return self.make_result(diagnostics)

        rows = self._normalize_instance_rows(raw_bindings)
        object_derived_caps, object_effective_os = self._derive_object_effective(objects=ctx.objects)
        instance_derived_caps, instance_software_refs = self._derive_instance_effective(rows=rows, objects=ctx.objects)

        classes_index: dict[str, Any] = {
            class_id: payload for class_id, payload in sorted(ctx.classes.items(), key=lambda item: item[0])
        }
        objects_index: dict[str, Any] = {
            object_id: payload for object_id, payload in sorted(ctx.objects.items(), key=lambda item: item[0])
        }

        by_group: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            group_name = row.get("group")
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            instance_id = row.get("instance")

            class_payload = ctx.classes.get(class_ref, {}) if isinstance(class_ref, str) else {}
            if not isinstance(class_payload, dict):
                class_payload = {}
            object_payload = ctx.objects.get(object_ref, {}) if isinstance(object_ref, str) else {}
            if not isinstance(object_payload, dict):
                object_payload = {}

            effective_item: dict[str, Any] = {
                "instance": instance_id,
                "source_id": row.get("source_id", instance_id),
                "layer": row.get("layer"),
                "class_ref": class_ref,
                "object_ref": object_ref,
                "status": row.get("status"),
                "notes": row.get("notes"),
                "runtime": row.get("runtime"),
                "class": {
                    "version": class_payload.get("version"),
                    "os_policy": class_payload.get("os_policy", "allowed"),
                    "firmware_policy": class_payload.get(
                        "firmware_policy",
                        self._default_firmware_policy(class_ref if isinstance(class_ref, str) else ""),
                    ),
                    "os_cardinality": class_payload.get("os_cardinality"),
                    "multi_boot": class_payload.get("multi_boot", False),
                    "required_capabilities": class_payload.get("required_capabilities", []),
                    "optional_capabilities": class_payload.get("optional_capabilities", []),
                    "capability_packs": class_payload.get("capability_packs", []),
                },
                "object": {
                    "version": object_payload.get("version"),
                    "enabled_capabilities": object_payload.get("enabled_capabilities", []),
                    "enabled_packs": object_payload.get("enabled_packs", []),
                    "derived_capabilities": object_derived_caps.get(object_ref, []),
                    "vendor_capabilities": object_payload.get("vendor_capabilities", []),
                    "vendor": object_payload.get("vendor"),
                    "model": object_payload.get("model"),
                },
            }

            software_refs = instance_software_refs.get(instance_id) if isinstance(instance_id, str) else None
            if isinstance(software_refs, dict):
                effective_item["instance"] = {
                    "firmware_ref": software_refs.get("firmware_ref"),
                    "os_refs": software_refs.get("os_refs", []),
                    "derived_capabilities": instance_derived_caps.get(instance_id, []),
                    "effective_software": software_refs.get("effective", {}),
                }

            effective_os = object_effective_os.get(object_ref) if isinstance(object_ref, str) else None
            if isinstance(effective_os, dict):
                effective_item["object"]["software"] = {"os": effective_os}

            prerequisites = object_payload.get("prerequisites")
            if isinstance(prerequisites, dict):
                os_ref = prerequisites.get("os_ref")
                if isinstance(os_ref, str) and os_ref:
                    effective_item["object"]["prerequisites"] = {"os_ref": os_ref}

            by_group.setdefault(group_name, []).append(effective_item)

        for group_rows in by_group.values():
            group_rows.sort(key=lambda item: str(item.get("instance", "")))

        raw_manifest = ctx.raw_yaml if isinstance(ctx.raw_yaml, dict) else {}
        generated_at = ctx.config.get("compile_generated_at")
        if not isinstance(generated_at, str) or not generated_at:
            generated_at = _utc_now()
        candidate = {
            "version": raw_manifest.get("version", "5.0.0"),
            "model": raw_manifest.get("model", "class-object-instance"),
            "generated_at": generated_at,
            "topology_manifest": ctx.topology_path,
            "classes": classes_index,
            "objects": objects_index,
            "instances": by_group,
        }

        # Publish for dependent plugins and place into compiled_json candidate.
        ctx.publish("effective_model_candidate", candidate)
        ctx.compiled_json = candidate

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"effective_model_candidate": candidate},
        )
