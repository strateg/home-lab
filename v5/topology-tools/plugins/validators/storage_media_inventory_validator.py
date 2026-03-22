"""L1 storage media inventory validator for attachment consistency checks."""

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


class StorageMediaInventoryValidator(ValidatorJsonPlugin):
    """Validate media registry and media attachment contracts on L1 rows."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _ERROR_CODE = "E7854"
    _WARNING_CODE = "W7855"

    _DISK_PORT_COMPATIBILITY: dict[str, set[str]] = {
        "hdd": {"ide", "sata", "sas", "usb", "virtual"},
        "ssd": {"ide", "sata", "sas", "m2", "pcie", "usb", "virtual"},
        "nvme": {"m2", "pcie", "virtual"},
        "sd-card": {"sdio", "usb"},
        "emmc": {"emmc", "emmc-reader", "onboard"},
        "flash": {"qspi", "usb", "virtual", "emmc", "onboard"},
    }

    _MOUNT_PORT_COMPATIBILITY: dict[str, set[str]] = {
        "soldered": {"qspi", "emmc", "onboard"},
        "replaceable": {"ide", "sata", "sas", "m2", "pcie", "emmc"},
        "removable": {"usb", "sdio", "emmc-reader"},
        "virtual": {"virtual"},
    }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        rows = self._rows_from_context(ctx=ctx, stage=stage, diagnostics=diagnostics)
        if rows is None:
            return self.make_result(diagnostics)

        slots_by_device = self._slots_by_device(rows)
        device_ids = set(slots_by_device.keys())
        media_by_id, duplicate_media_ids = self._media_by_id(rows)
        for media_id in sorted(duplicate_media_ids):
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"L1 media registry: duplicate media id '{media_id}'.",
                    path="storage.media_registry",
                )
            )

        present_slot_claims: set[str] = set()
        present_media_claims: dict[str, str] = {}

        for row in rows:
            if not self._is_media_attachment_row(row):
                continue
            self._validate_attachment(
                row=row,
                device_ids=device_ids,
                slots_by_device=slots_by_device,
                media_by_id=media_by_id,
                present_slot_claims=present_slot_claims,
                present_media_claims=present_media_claims,
                stage=stage,
                diagnostics=diagnostics,
            )

        return self.make_result(diagnostics)

    def _rows_from_context(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> list[dict[str, Any]] | None:
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"storage_media_inventory validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return None

        if not isinstance(rows_payload, list):
            return []
        return [item for item in rows_payload if isinstance(item, dict)]

    def _validate_attachment(
        self,
        *,
        row: dict[str, Any],
        device_ids: set[str],
        slots_by_device: dict[str, dict[str, dict[str, Any]]],
        media_by_id: dict[str, dict[str, Any]],
        present_slot_claims: set[str],
        present_media_claims: dict[str, str],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_prefix = self._row_prefix(row)
        row_id = self._row_id(row)
        extensions = self._extensions(row)
        device_ref = extensions.get("device_ref")
        slot_ref = extensions.get("slot_ref")
        media_ref = extensions.get("media_ref")
        state = extensions.get("state", "present")

        if isinstance(device_ref, str) and device_ref and device_ref not in device_ids:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"L1 media attachment '{row_id}': unknown device_ref '{device_ref}'.",
                    path=f"{row_prefix}.extensions.device_ref",
                )
            )
            return

        if not isinstance(device_ref, str) or not device_ref:
            return
        if not isinstance(slot_ref, str) or not slot_ref:
            return

        slot = slots_by_device.get(device_ref, {}).get(slot_ref)
        if not isinstance(slot, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=(
                        f"L1 media attachment '{row_id}': slot_ref '{slot_ref}' "
                        f"does not exist on device '{device_ref}'."
                    ),
                    path=f"{row_prefix}.extensions.slot_ref",
                )
            )
            return

        if not isinstance(media_ref, str) or not media_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"L1 media attachment '{row_id}': media_ref must be a non-empty string.",
                    path=f"{row_prefix}.extensions.media_ref",
                )
            )
            return

        media = media_by_id.get(media_ref)
        if not isinstance(media, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"L1 media attachment '{row_id}': media_ref '{media_ref}' not found in media registry.",
                    path=f"{row_prefix}.extensions.media_ref",
                )
            )
            return

        port_type = slot.get("bus")
        mount_type = slot.get("mount")
        media_type = media.get("type")

        if isinstance(port_type, str) and isinstance(media_type, str):
            allowed_ports = self._DISK_PORT_COMPATIBILITY.get(media_type)
            if allowed_ports is not None and port_type not in allowed_ports:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=(
                            f"L1 media attachment '{row_id}': media '{media_ref}' type '{media_type}' "
                            f"is unusual for port type '{port_type}'."
                        ),
                        path=f"{row_prefix}.extensions.media_ref",
                    )
                )

        supported_buses = media.get("supported_buses")
        if isinstance(port_type, str) and isinstance(supported_buses, list):
            supported = {str(item) for item in supported_buses if isinstance(item, str)}
            if supported and port_type not in supported:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=(
                            f"L1 media attachment '{row_id}': media '{media_ref}' does not support bus '{port_type}'."
                        ),
                        path=f"{row_prefix}.extensions.media_ref",
                    )
                )

        if isinstance(port_type, str) and isinstance(mount_type, str):
            allowed_mount_ports = self._MOUNT_PORT_COMPATIBILITY.get(mount_type)
            if allowed_mount_ports is not None and port_type not in allowed_mount_ports:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=(
                            f"L1 media attachment '{row_id}': mount_type '{mount_type}' "
                            f"is incompatible with port '{port_type}'."
                        ),
                        path=f"{row_prefix}.extensions.slot_ref",
                    )
                )

        removable = media.get("removable")
        if mount_type == "soldered" and removable is True:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=(
                        f"L1 media attachment '{row_id}': soldered slot '{slot_ref}' "
                        f"cannot use removable media '{media_ref}'."
                    ),
                    path=f"{row_prefix}.extensions.slot_ref",
                )
            )
        if mount_type == "removable" and removable is False:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._WARNING_CODE,
                    severity="warning",
                    stage=stage,
                    message=(
                        f"L1 media attachment '{row_id}': removable slot '{slot_ref}' "
                        f"has media '{media_ref}' with removable=false."
                    ),
                    path=f"{row_prefix}.extensions.slot_ref",
                )
            )
        if mount_type == "virtual" and media.get("virtual") is not True:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._WARNING_CODE,
                    severity="warning",
                    stage=stage,
                    message=(
                        f"L1 media attachment '{row_id}': virtual slot '{slot_ref}' "
                        "should use media with virtual=true."
                    ),
                    path=f"{row_prefix}.extensions.slot_ref",
                )
            )

        if state != "present":
            return
        slot_key = f"{device_ref}::{slot_ref}"
        if slot_key in present_slot_claims:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=(
                        f"L1 media attachments: multiple 'present' media attached to "
                        f"slot '{slot_ref}' on device '{device_ref}'."
                    ),
                    path=f"{row_prefix}.extensions.slot_ref",
                )
            )
        present_slot_claims.add(slot_key)

        owner = f"{device_ref}/{slot_ref}"
        previous_owner = present_media_claims.get(media_ref)
        if previous_owner and previous_owner != owner:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=(
                        f"L1 media attachments: media '{media_ref}' is 'present' in multiple slots "
                        f"({previous_owner}, {owner})."
                    ),
                    path=f"{row_prefix}.extensions.media_ref",
                )
            )
        else:
            present_media_claims[media_ref] = owner

    def _slots_by_device(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        slots_by_device: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            if not self._is_storage_device_row(row):
                continue
            device_id = self._row_id(row)
            slot_map: dict[str, dict[str, Any]] = {}
            storage_slots = self._extensions(row).get("storage_slots")
            if not isinstance(storage_slots, list):
                slots_by_device[device_id] = slot_map
                continue
            for slot in storage_slots:
                if not isinstance(slot, dict):
                    continue
                slot_id = slot.get("id")
                if isinstance(slot_id, str) and slot_id:
                    slot_map[slot_id] = slot
            slots_by_device[device_id] = slot_map
        return slots_by_device

    def _media_by_id(self, rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], set[str]]:
        media_by_id: dict[str, dict[str, Any]] = {}
        duplicate_ids: set[str] = set()
        for row in rows:
            if not self._is_media_row(row):
                continue
            media_id = self._media_id(row)
            if not media_id:
                continue
            if media_id in media_by_id:
                duplicate_ids.add(media_id)
            media_by_id[media_id] = self._normalize_media(row, media_id=media_id)
        return media_by_id, duplicate_ids

    def _normalize_media(self, row: dict[str, Any], *, media_id: str) -> dict[str, Any]:
        extensions = self._extensions(row)
        media_type = extensions.get("media_type")
        if not isinstance(media_type, str):
            media_type = extensions.get("type")
        return {
            "id": media_id,
            "type": media_type,
            "supported_buses": extensions.get("supported_buses"),
            "removable": extensions.get("removable"),
            "virtual": extensions.get("virtual"),
        }

    def _media_id(self, row: dict[str, Any]) -> str:
        row_id = row.get("instance")
        if isinstance(row_id, str) and row_id:
            return row_id
        media_id = self._extensions(row).get("id")
        if isinstance(media_id, str) and media_id:
            return media_id
        return ""

    def _is_storage_device_row(self, row: dict[str, Any]) -> bool:
        if row.get("layer") != "L1":
            return False
        if row.get("group") == "devices":
            return True
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and class_ref.startswith("class.compute."):
            return True
        return False

    def _is_media_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if class_ref in {"class.storage.media", "class.storage.disk"}:
            return True
        group = row.get("group")
        if group in {"media_registry", "storage_media"}:
            return True
        extensions = self._extensions(row)
        return "media_type" in extensions or ("supported_buses" in extensions and "removable" in extensions)

    def _is_media_attachment_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if class_ref in {"class.storage.media_attachment"}:
            return True
        group = row.get("group")
        if group in {"media_attachments", "storage_media_attachments"}:
            return True
        extensions = self._extensions(row)
        return {"device_ref", "slot_ref", "media_ref"}.issubset(extensions.keys())

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}

    @staticmethod
    def _row_id(row: dict[str, Any]) -> str:
        row_id = row.get("instance")
        return str(row_id) if isinstance(row_id, str) and row_id else "unknown"

    @staticmethod
    def _row_prefix(row: dict[str, Any]) -> str:
        group = row.get("group")
        row_id = row.get("instance")
        group_label = group if isinstance(group, str) and group else "unknown"
        row_label = row_id if isinstance(row_id, str) and row_id else "unknown"
        return f"instance:{group_label}:{row_label}"
