"""Effective model candidate compiler plugin (ADR 0069 WS2).

Builds a parity-focused candidate compiled model from loaded class/object
modules and instance bindings. During migration, this mirrors legacy effective
assembly so parity gate can compare equivalent payloads.

ADR 0106 + ADR 0104 integration: Subscribes to capability_compiler for derived
capabilities instead of deriving independently. This eliminates code duplication
and ensures consistent capability derivation across the pipeline.

ADR 0118/0119 enforcer type/adapter resolution (D-TYPE-1..3): published here,
per instance, as "enforcer_resolution" - not in capability_compiler.py. A
hardware object's declared device-kind capability and its OS family's
capability (cap.os.routeros, cap.os.proxmox) live on two different objects
under ADR 0064's embedded-OS model (e.g. obj.mikrotik.chateau_lte7_ax vs
obj.os.routeros.7.arm64) and are joined only here, at the instance level,
via os_refs - the same join _derive_instance_effective already performs for
OS/firmware capabilities.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from capability_derivation import default_firmware_policy as shared_default_firmware_policy
from capability_derivation import derive_firmware_capabilities as shared_derive_firmware_capabilities
from capability_derivation import derive_os_capabilities as shared_derive_os_capabilities
from capability_derivation import extract_firmware_properties as shared_extract_firmware_properties
from capability_derivation import extract_os_properties as shared_extract_os_properties
from capability_derivation import normalize_release_token as shared_normalize_release_token
from kernel.plugin_base import (
    CompilerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _manifest_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EffectiveModelCompiler(CompilerPlugin):
    """Assemble candidate effective model in compile stage."""

    # ADR 0106 + ADR 0104: Subscribe to capability_compiler for derived capabilities
    _CAPABILITY_PLUGIN_ID = "base.compiler.capabilities"

    @staticmethod
    def _normalize_release_token(value: str) -> str:
        return shared_normalize_release_token(value)

    @staticmethod
    def _default_firmware_policy(class_id: str) -> str:
        return shared_default_firmware_policy(class_id)

    @staticmethod
    def _extract_firmware_properties(object_payload: dict[str, Any]) -> dict[str, Any]:
        return shared_extract_firmware_properties(object_payload)

    def _extract_os_properties(self, object_payload: dict[str, Any]) -> dict[str, Any] | None:
        _ = self
        return shared_extract_os_properties(object_payload)

    def _derive_firmware_capabilities(
        self, *, object_payload: dict[str, Any]
    ) -> tuple[set[str], dict[str, Any] | None]:
        return shared_derive_firmware_capabilities(
            object_id="plugin-effective-model",
            object_payload=object_payload,
            catalog_ids=set(),
            path="plugin:effective_model",
            add_diag=lambda **_: None,
            emit_diagnostics=False,
        )

    def _derive_os_capabilities(self, *, object_payload: dict[str, Any]) -> tuple[set[str], dict[str, Any] | None]:
        return shared_derive_os_capabilities(
            object_id="plugin-effective-model",
            object_payload=object_payload,
            catalog_ids=set(),
            path="plugin:effective_model",
            add_diag=lambda **_: None,
            emit_diagnostics=False,
        )

    @staticmethod
    def _subscribe_required(ctx: PluginContext, *, plugin_id: str, key: str) -> Any:
        try:
            return ctx.subscribe(plugin_id, key)
        except PluginDataExchangeError as exc:
            raise PluginDataExchangeError(f"Missing required published key '{key}' from '{plugin_id}': {exc}") from exc

    @staticmethod
    def _subscribe_optional(ctx: PluginContext, *, plugin_id: str, key: str, default: Any = None) -> Any:
        """Subscribe to optional published data with graceful fallback."""
        try:
            return ctx.subscribe(plugin_id, key)
        except PluginDataExchangeError:
            return default

    @staticmethod
    def _build_class_lineage_map(*, classes: dict[str, Any]) -> dict[str, list[str]]:
        class_lineage: dict[str, list[str]] = {}
        class_ids = {class_id for class_id in classes if isinstance(class_id, str)}

        for class_id in sorted(class_ids):
            chain: list[str] = []
            visited: set[str] = set()
            cursor = class_id
            while cursor in class_ids and cursor not in visited:
                visited.add(cursor)
                chain.append(cursor)
                payload = classes.get(cursor, {})
                parent_ref = payload.get("extends") if isinstance(payload, dict) else None
                if not isinstance(parent_ref, str) or not parent_ref:
                    break
                cursor = parent_ref
            class_lineage[class_id] = list(reversed(chain))
        return class_lineage

    # NOTE: _derive_object_effective removed (ADR 0106 + ADR 0104)
    # Object-level capabilities now come from capability_compiler via subscribe()

    def _derive_instance_effective(
        self,
        *,
        rows: list[dict[str, Any]],
        objects: dict[str, Any],
        subscribed_effective_os: dict[str, dict[str, Any]] | None = None,
        subscribed_effective_firmware: dict[str, dict[str, Any]] | None = None,
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

            # ADR 0106 + ADR 0104: Use subscribed data when available, fallback to local derivation
            if isinstance(firmware_row, dict):
                firmware_object_ref = firmware_row.get("object_ref")
                if isinstance(firmware_object_ref, str):
                    # Try to use subscribed firmware effective data
                    if subscribed_effective_firmware and firmware_object_ref in subscribed_effective_firmware:
                        firmware_effective = subscribed_effective_firmware[firmware_object_ref]
                        # Derive capabilities from effective firmware
                        if firmware_effective:
                            vendor = firmware_effective.get("vendor")
                            family = firmware_effective.get("family")
                            if isinstance(vendor, str) and vendor:
                                derived_caps.add(f"cap.firmware.{vendor}")
                            if isinstance(family, str) and family:
                                derived_caps.add(f"cap.firmware.{family}")
                            arch = firmware_effective.get("architecture")
                            if isinstance(arch, str) and arch:
                                derived_caps.add(f"cap.firmware.arch.{arch}")
                                derived_caps.add(f"cap.arch.{arch}")
                            boot_stack = firmware_effective.get("boot_stack")
                            if isinstance(boot_stack, str) and boot_stack:
                                derived_caps.add(f"cap.firmware.boot.{boot_stack}")
                            if firmware_effective.get("virtual"):
                                derived_caps.add("cap.firmware.virtual")
                    else:
                        # Fallback to local derivation
                        firmware_object_payload = objects.get(firmware_object_ref, {})
                        if not isinstance(firmware_object_payload, dict):
                            firmware_object_payload = {}
                        fw_caps, fw_effective = self._derive_firmware_capabilities(
                            object_payload=firmware_object_payload
                        )
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

                # ADR 0106 + ADR 0104: Use subscribed OS effective data when available
                if subscribed_effective_os and os_object_ref in subscribed_effective_os:
                    os_effective = subscribed_effective_os[os_object_ref]
                    if os_effective:
                        # Derive capabilities from effective OS
                        family = os_effective.get("family")
                        distribution = os_effective.get("distribution")
                        release_id = os_effective.get("release_id")
                        codename = os_effective.get("codename")
                        init_system = os_effective.get("init_system")
                        package_manager = os_effective.get("package_manager")
                        architecture = os_effective.get("architecture")

                        if isinstance(family, str) and family:
                            derived_caps.add(f"cap.os.{family}")
                        if isinstance(distribution, str) and distribution:
                            derived_caps.add(f"cap.os.{distribution}")
                        if (
                            isinstance(distribution, str)
                            and isinstance(release_id, str)
                            and distribution
                            and release_id
                        ):
                            derived_caps.add(f"cap.os.{distribution}.{release_id}")
                        if isinstance(distribution, str) and isinstance(codename, str) and distribution and codename:
                            derived_caps.add(f"cap.os.{distribution}.{codename}")
                        if isinstance(init_system, str) and init_system:
                            derived_caps.add(f"cap.os.init.{init_system}")
                        if isinstance(package_manager, str) and package_manager:
                            derived_caps.add(f"cap.os.pkg.{package_manager}")
                        if isinstance(architecture, str) and architecture:
                            derived_caps.add(f"cap.arch.{architecture}")

                        resolved_os_effective.append(os_effective)
                else:
                    # Fallback to local derivation
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

            # ADR 0104: Derive cap.role.linux_host from OS capabilities at instance level
            linux_os_caps = {"cap.os.debian", "cap.os.ubuntu", "cap.os.linux", "cap.os.nixos", "cap.os.alpine"}
            if derived_caps & linux_os_caps:
                derived_caps.add("cap.role.linux_host")

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

    # ADR 0118/0119 D-TYPE-1: enforcer type is gated by exactly one of these
    # two mutually exclusive device-kind capabilities.
    _ENFORCER_TYPE_CAPS: dict[str, str] = {
        "network": "cap.net.l3.security.firewall.zone_policy",
        "compute": "cap.compute.security.firewall.zone_policy",
    }

    # ADR 0118/0119 D-TYPE-2: type -> the cap.os.* family compatible with it,
    # and the adapter identifier that OS family resolves to. One family per
    # type today; a second entry per type would make W7017 (ambiguous)
    # reachable, which is registered for that reason even though it cannot
    # fire under this table.
    _ENFORCER_ADAPTER_BY_TYPE: dict[str, dict[str, str]] = {
        "network": {"cap.os.routeros": "cap.firewall.security_matrix.routeros"},
        "compute": {"cap.os.proxmox": "cap.firewall.security_matrix.pve"},
    }

    _ENFORCER_ADAPTER_IDS: frozenset[str] = frozenset(
        {
            "cap.firewall.security_matrix.routeros",
            "cap.firewall.security_matrix.pve",
        }
    )

    def _resolve_enforcer(
        self,
        *,
        instance_id: str,
        effective_caps: set[str],
        path: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        """Resolve enforcer type and adapter identity (ADR 0118/0119 D-TYPE-1..3).

        This is dispatch among mutually exclusive device kinds, not
        required_capabilities satisfaction: neither capability engine can
        express "enforced by RouterOS OR Proxmox" as a conjunction. Returns
        None for instances that declare neither device-kind capability (not
        an enforcer candidate; type=none by absence from the published map).

        `effective_caps` must already combine the hardware object's declared
        enabled_capabilities with both the object- and instance-level
        derived capabilities (the latter carries cap.os.* resolved through
        os_refs) - the caller assembles this per instance, since no single
        object carries every fact this resolution needs. Pack expansion
        (enabled_packs) is deliberately not included - N-04 stays deferred.
        """
        present_types = [t for t, cap_id in self._ENFORCER_TYPE_CAPS.items() if cap_id in effective_caps]
        if not present_types:
            return None

        if len(present_types) > 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7015",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Instance '{instance_id}' resolves both "
                        f"'{self._ENFORCER_TYPE_CAPS['network']}' and "
                        f"'{self._ENFORCER_TYPE_CAPS['compute']}'. An enforcer's type must be "
                        "exactly one device kind (ADR 0118/0119 D-TYPE-1)."
                    ),
                    path=path,
                )
            )
            return {
                "type": None,
                "adapter": None,
                "adapter_version": None,
                "considered": sorted(self._ENFORCER_TYPE_CAPS.values()),
                "compatible": [],
                "reason": "contradiction: both device-kind capabilities present",
            }

        enforcer_type = present_types[0]
        adapter_by_os = self._ENFORCER_ADAPTER_BY_TYPE[enforcer_type]
        considered = [self._ENFORCER_TYPE_CAPS[enforcer_type], *sorted(adapter_by_os)]
        compatible_os = sorted(f for f in adapter_by_os if f in effective_caps)

        direct_declaration = next((a for a in sorted(self._ENFORCER_ADAPTER_IDS) if a in effective_caps), None)
        if direct_declaration is not None:
            considered.append(direct_declaration)

        if not compatible_os:
            if direct_declaration is not None:
                # ADR 0119 D1.1: a direct declaration alongside no matching
                # OS-family fact is an input to the resolution, not an
                # override - it is taken as the sole candidate here because
                # there is nothing to reconcile it against.
                return {
                    "type": enforcer_type,
                    "adapter": direct_declaration,
                    "adapter_version": None,
                    "considered": considered,
                    "compatible": [direct_declaration],
                    "reason": "no OS-family match; using the direct adapter declaration as sole candidate",
                }
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7016",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Instance '{instance_id}' resolved enforcer type '{enforcer_type}' but no "
                        "compatible adapter exists for its OS family (ADR 0118/0119 D-TYPE-2)."
                    ),
                    path=path,
                )
            )
            return {
                "type": enforcer_type,
                "adapter": None,
                "adapter_version": None,
                "considered": considered,
                "compatible": [],
                "reason": "unsupported: no adapter for this type/OS-family combination",
            }

        if len(compatible_os) > 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7017",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Instance '{instance_id}' matches more than one OS family compatible with "
                        f"enforcer type '{enforcer_type}' (ADR 0118/0119 D-TYPE-2); ambiguous, "
                        "no priority order between them."
                    ),
                    path=path,
                )
            )
            return {
                "type": enforcer_type,
                "adapter": None,
                "adapter_version": None,
                "considered": considered,
                "compatible": sorted(adapter_by_os[f] for f in compatible_os),
                "reason": "ambiguous: more than one compatible adapter",
            }

        derived_adapter = adapter_by_os[compatible_os[0]]

        if direct_declaration is not None and direct_declaration != derived_adapter:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7019",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Instance '{instance_id}' declares adapter '{direct_declaration}' directly, "
                        f"but its OS family resolves to '{derived_adapter}' (ADR 0118/0119 "
                        "D-TYPE-2 reconciliation)."
                    ),
                    path=path,
                )
            )
            return {
                "type": enforcer_type,
                "adapter": None,
                "adapter_version": None,
                "considered": considered,
                "compatible": sorted({derived_adapter, direct_declaration}),
                "reason": "reconciliation contradiction: direct declaration disagrees with OS-family derivation",
            }

        return {
            "type": enforcer_type,
            # ADR 0119 D2's execution-context record (identity + version
            # together) is not yet implemented (blocked on G1/W03; see
            # adr/0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md
            # V-07). Plugin manifest api_version is NOT used as a stand-in:
            # it is "1.x" on every plugin in the framework (the kernel-API
            # compatibility marker), identical for every adapter, so it
            # would carry no adapter-specific information at all.
            "adapter": derived_adapter,
            "adapter_version": None,
            "considered": considered,
            "compatible": [derived_adapter],
            "reason": (
                "resolved from type x OS family"
                + (", confirmed by direct declaration" if direct_declaration is not None else "")
            ),
        }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        envelope_mode = getattr(ctx, "_snapshot", None) is not None

        plugin_rows: Any = None
        try:
            plugin_rows = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.instance_rows",
                key="normalized_rows",
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
        if isinstance(plugin_rows, list):
            rows = [row for row in plugin_rows if isinstance(row, dict)]
        else:
            rows = []

        # ADR 0106 + ADR 0104: Subscribe to capability_compiler for derived capabilities
        # This eliminates duplication and ensures consistent derivation
        subscribed_derived_caps = self._subscribe_optional(
            ctx,
            plugin_id=self._CAPABILITY_PLUGIN_ID,
            key="derived_capabilities",
            default={},
        )
        subscribed_effective_os = self._subscribe_optional(
            ctx,
            plugin_id=self._CAPABILITY_PLUGIN_ID,
            key="effective_os_map",
            default={},
        )
        subscribed_effective_firmware = self._subscribe_optional(
            ctx,
            plugin_id=self._CAPABILITY_PLUGIN_ID,
            key="effective_firmware_map",
            default={},
        )

        # Use subscribed data for object-level capabilities; instance-level still needs local derivation
        object_derived_caps: dict[str, list[str]] = (
            subscribed_derived_caps if isinstance(subscribed_derived_caps, dict) else {}
        )
        object_effective_os: dict[str, dict[str, Any]] = (
            subscribed_effective_os if isinstance(subscribed_effective_os, dict) else {}
        )

        # Instance-level derivation still needs to follow firmware_ref/os_refs chains
        instance_derived_caps, instance_software_refs = self._derive_instance_effective(
            rows=rows,
            objects=ctx.objects,
            subscribed_effective_os=object_effective_os,
            subscribed_effective_firmware=(
                subscribed_effective_firmware if isinstance(subscribed_effective_firmware, dict) else {}
            ),
        )
        class_lineage_map = self._build_class_lineage_map(classes=ctx.classes)

        classes_index: dict[str, Any] = {}
        for class_id, payload in sorted(ctx.classes.items(), key=lambda item: item[0]):
            class_payload = payload if isinstance(payload, dict) else {}
            parent_class = class_payload.get("extends") if isinstance(class_payload.get("extends"), str) else None
            normalized_class = dict(class_payload)
            normalized_class["parent_class"] = parent_class
            normalized_class["lineage"] = class_lineage_map.get(class_id, [class_id])
            classes_index[class_id] = normalized_class

        objects_index: dict[str, Any] = {}
        for object_id, payload in sorted(ctx.objects.items(), key=lambda item: item[0]):
            object_payload = payload if isinstance(payload, dict) else {}
            class_ref = object_payload.get("class_ref") if isinstance(object_payload.get("class_ref"), str) else None
            normalized_object = dict(object_payload)
            normalized_object["extends_class"] = class_ref
            normalized_object["materializes_class"] = class_ref
            if isinstance(class_ref, str) and class_ref:
                normalized_object["class_lineage"] = class_lineage_map.get(class_ref, [class_ref])
            else:
                normalized_object["class_lineage"] = []
            objects_index[object_id] = normalized_object

        by_group: dict[str, list[dict[str, Any]]] = {}
        # ADR 0118/0119 D-TYPE-1..3
        enforcer_resolution: dict[str, dict[str, Any]] = {}
        for row in rows:
            group_name = row.get("group")
            group_key = group_name if isinstance(group_name, str) and group_name else "ungrouped"
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            instance_id = row.get("instance")
            object_ref_key = object_ref if isinstance(object_ref, str) else ""
            instance_id_key = instance_id if isinstance(instance_id, str) else ""

            class_payload = ctx.classes.get(class_ref, {}) if isinstance(class_ref, str) else {}
            if not isinstance(class_payload, dict):
                class_payload = {}
            object_payload = ctx.objects.get(object_ref, {}) if isinstance(object_ref, str) else {}
            if not isinstance(object_payload, dict):
                object_payload = {}
            class_parent = class_payload.get("extends") if isinstance(class_payload.get("extends"), str) else None
            object_class_ref = (
                object_payload.get("class_ref") if isinstance(object_payload.get("class_ref"), str) else None
            )
            if isinstance(class_ref, str) and class_ref:
                resolved_lineage = class_lineage_map.get(class_ref, [class_ref])
            else:
                resolved_lineage = []

            effective_item: dict[str, Any] = {
                "instance_id": instance_id,
                "instance": instance_id,
                "source_id": row.get("source_id", instance_id),
                "layer": row.get("layer"),
                "status": row.get("status"),
                "notes": row.get("notes"),
                "runtime": row.get("runtime"),
                # ADR 0107 D9: host_ref is a first-class reserved row key,
                # "semantically equivalent to object_ref" - promoted out of
                # extensions on normalized_rows, so it must be propagated
                # here the same explicit way, not read back from
                # instance_data/extensions where it never lands.
                "host_ref": row.get("host_ref"),
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
                    "parent_class": class_parent,
                    "lineage": resolved_lineage,
                },
                "object": {
                    "version": object_payload.get("version"),
                    "enabled_capabilities": object_payload.get("enabled_capabilities", []),
                    "enabled_packs": object_payload.get("enabled_packs", []),
                    "derived_capabilities": object_derived_caps.get(object_ref_key, []),
                    "vendor_capabilities": object_payload.get("vendor_capabilities", []),
                    "vendor": object_payload.get("vendor"),
                    "model": object_payload.get("model"),
                    "extends_class": object_class_ref,
                    "materializes_class": object_class_ref,
                    "class_lineage": (
                        class_lineage_map.get(object_class_ref, [object_class_ref])
                        if isinstance(object_class_ref, str) and object_class_ref
                        else []
                    ),
                },
            }
            row_extensions = row.get("extensions")
            if isinstance(row_extensions, dict) and row_extensions:
                effective_item["instance_data"] = row_extensions

            instance_block: dict[str, Any] = {
                "extends_object": object_ref if isinstance(object_ref, str) else None,
                "materializes_object": object_ref if isinstance(object_ref, str) else None,
                "materializes_class": class_ref if isinstance(class_ref, str) else None,
                "resolved_lineage": resolved_lineage,
                "firmware_ref": None,
                "os_refs": [],
                "derived_capabilities": instance_derived_caps.get(instance_id_key, []),
                "effective_software": {},
            }
            software_refs = instance_software_refs.get(instance_id) if isinstance(instance_id, str) else None
            if isinstance(software_refs, dict):
                instance_block["firmware_ref"] = software_refs.get("firmware_ref")
                instance_block["os_refs"] = software_refs.get("os_refs", [])
                instance_block["effective_software"] = software_refs.get("effective", {})
            effective_item["instance"] = instance_block

            effective_os = object_effective_os.get(object_ref) if isinstance(object_ref, str) else None
            if isinstance(effective_os, dict):
                effective_item["object"]["software"] = {"os": effective_os}

            prerequisites = object_payload.get("prerequisites")
            if isinstance(prerequisites, dict):
                os_ref = prerequisites.get("os_ref")
                if isinstance(os_ref, str) and os_ref:
                    effective_item["object"]["prerequisites"] = {"os_ref": os_ref}

            # ADR 0118/0119 D-TYPE-1..3: combine the hardware object's declared
            # enabled_capabilities with both derived-capability sources, since
            # device-kind and OS-family facts live on two different objects
            # (see module docstring) joined only at this instance level.
            if instance_id_key:
                enforcer_effective_caps: set[str] = set()
                declared_enabled = object_payload.get("enabled_capabilities")
                if isinstance(declared_enabled, list):
                    enforcer_effective_caps.update(c for c in declared_enabled if isinstance(c, str))
                enforcer_effective_caps.update(object_derived_caps.get(object_ref_key, []))
                enforcer_effective_caps.update(instance_derived_caps.get(instance_id_key, []))
                resolution = self._resolve_enforcer(
                    instance_id=instance_id_key,
                    effective_caps=enforcer_effective_caps,
                    path=f"instance:{group_key}:{instance_id_key}",
                    stage=stage,
                    diagnostics=diagnostics,
                )
                if resolution is not None:
                    enforcer_resolution[instance_id_key] = resolution

            by_group.setdefault(group_key, []).append(effective_item)

        for group_rows in by_group.values():
            group_rows.sort(key=lambda item: str(item.get("instance", "")))

        raw_manifest = ctx.raw_yaml if isinstance(ctx.raw_yaml, dict) else {}
        generated_at = ctx.config.get("compile_generated_at")
        if not isinstance(generated_at, str) or not generated_at:
            generated_at = _utc_now()
        compiled_model_version = ctx.config.get("compiled_model_version", "1.0")
        if not isinstance(compiled_model_version, str) or not compiled_model_version:
            compiled_model_version = "1.0"
        compiler_pipeline_version = ctx.config.get("compiler_pipeline_version", "adr0069-ws2")
        if not isinstance(compiler_pipeline_version, str) or not compiler_pipeline_version:
            compiler_pipeline_version = "adr0069-ws2"
        source_manifest_digest = ctx.config.get("source_manifest_digest")
        if not isinstance(source_manifest_digest, str) or not source_manifest_digest:
            source_manifest_digest = _manifest_digest(raw_manifest)
        candidate = {
            "version": raw_manifest.get("version", "5.0.0"),
            "model": raw_manifest.get("model", "class-object-instance"),
            "generated_at": generated_at,
            "compiled_model_version": compiled_model_version,
            "compiled_at": generated_at,
            "compiler_pipeline_version": compiler_pipeline_version,
            "source_manifest_digest": source_manifest_digest,
            "topology_manifest": ctx.topology_path,
            "classes": classes_index,
            "objects": objects_index,
            "instances": by_group,
        }

        # Publish for dependent plugins and place into compiled_json candidate.
        ctx.publish("effective_model_candidate", candidate)
        ctx.publish("enforcer_resolution", enforcer_resolution)
        if not envelope_mode:
            ctx.compiled_json = candidate

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "effective_model_candidate": candidate,
                "enforcer_resolution": enforcer_resolution,
            },
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
