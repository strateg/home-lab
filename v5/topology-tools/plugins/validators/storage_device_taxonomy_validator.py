"""L1 storage device taxonomy validator for slot/media compatibility rules."""

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


class StorageDeviceTaxonomyValidator(ValidatorJsonPlugin):
    """Validate L1 device storage_slots taxonomy against attached media inventory."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _ERROR_CODE = "E7852"
    _WARNING_CODE = "W7853"
    _BAREMETAL_SUBSTRATES = {"baremetal-owned", "baremetal-colo"}

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

        media_by_id = self._media_by_id(rows)
        attachments_by_slot = self._attachments_by_slot(rows)

        for row in rows:
            if not self._is_storage_device_row(row):
                continue
            self._validate_device_row(
                row=row,
                media_by_id=media_by_id,
                attachments_by_slot=attachments_by_slot,
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
                    message=f"storage_device_taxonomy validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return None

        if not isinstance(rows_payload, list):
            return []
        return [item for item in rows_payload if isinstance(item, dict)]

    def _validate_device_row(
        self,
        *,
        row: dict[str, Any],
        media_by_id: dict[str, dict[str, Any]],
        attachments_by_slot: dict[str, dict[str, list[dict[str, Any]]]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_prefix = self._row_prefix(row)
        extensions = self._extensions(row)
        row_id = self._row_id(row)

        substrate = extensions.get("substrate")
        os_cfg = extensions.get("os")
        if isinstance(os_cfg, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._WARNING_CODE,
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Device '{row_id}': legacy 'os' block in L1; "
                        "prefer supported_operating_systems for hardware capability only."
                    ),
                    path=f"{row_prefix}.extensions.os",
                )
            )
            if os_cfg.get("planned"):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{row_id}': move os.planned to upper layers; "
                            "keep only supported_operating_systems in L1."
                        ),
                        path=f"{row_prefix}.extensions.os.planned",
                    )
                )

        slots_raw = extensions.get("storage_slots")
        if slots_raw is None:
            slots: list[dict[str, Any]] = []
        elif isinstance(slots_raw, list):
            slots = [item for item in slots_raw if isinstance(item, dict)]
        else:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"Device '{row_id}': extensions.storage_slots must be a list when set.",
                    path=f"{row_prefix}.extensions.storage_slots",
                )
            )
            slots = []

        if substrate in self._BAREMETAL_SUBSTRATES and not slots:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._ERROR_CODE,
                    severity="error",
                    stage=stage,
                    message=f"Device '{row_id}': baremetal compute device must define storage_slots inventory.",
                    path=f"{row_prefix}.extensions.storage_slots",
                )
            )

        slot_ids: set[str] = set()
        for slot in slots:
            slot_id = slot.get("id")
            if not isinstance(slot_id, str) or not slot_id:
                continue
            slot_path = f"{row_prefix}.extensions.storage_slots[{slot_id}]"
            if slot_id in slot_ids:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=f"Device '{row_id}': duplicate storage slot id '{slot_id}'.",
                        path=slot_path,
                    )
                )
            slot_ids.add(slot_id)
            if slot.get("media") is not None:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{row_id}': inline slot.media is deprecated; "
                            "use media registry and media attachments."
                        ),
                        path=f"{slot_path}.media",
                    )
                )

        normalized_disks = self._normalized_disks(
            device_id=row_id,
            slots=slots,
            attachments_by_slot=attachments_by_slot,
            media_by_id=media_by_id,
        )
        if substrate in self._BAREMETAL_SUBSTRATES and slots and not normalized_disks:
            diagnostics.append(
                self.emit_diagnostic(
                    code=self._WARNING_CODE,
                    severity="warning",
                    stage=stage,
                    message=f"Device '{row_id}': no media attached to storage slots.",
                    path=f"{row_prefix}.extensions.storage_slots",
                )
            )

        disk_ids: set[str] = set()
        for disk in normalized_disks:
            disk_id = disk.get("id")
            disk_label = str(disk_id or "unknown")
            disk_path = f"{row_prefix}.extensions.storage_slots[{disk.get('slot_id', 'unknown')}]"

            if isinstance(disk_id, str) and disk_id:
                if disk_id in disk_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=self._ERROR_CODE,
                            severity="error",
                            stage=stage,
                            message=f"Device '{row_id}': duplicate disk id '{disk_id}'.",
                            path=disk_path,
                        )
                    )
                disk_ids.add(disk_id)

            if disk.get("os_device_path"):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{row_id}': disk '{disk_label}' contains logical os_device_path; "
                            "move it to L3 storage binding."
                        ),
                        path=disk_path,
                    )
                )

            disk_type = disk.get("type")
            port_type = disk.get("port_type")
            mount_type = disk.get("mount_type")
            removable = disk.get("removable")
            disk_virtual = disk.get("virtual")

            if isinstance(disk_type, str) and isinstance(port_type, str):
                allowed_ports = self._DISK_PORT_COMPATIBILITY.get(disk_type)
                if allowed_ports is not None and port_type not in allowed_ports:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=self._WARNING_CODE,
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Device '{row_id}': disk '{disk_label}' type '{disk_type}' "
                                f"is unusual for port type '{port_type}'."
                            ),
                            path=disk_path,
                        )
                    )

            supported_buses = disk.get("supported_buses")
            if isinstance(supported_buses, list) and isinstance(port_type, str) and port_type:
                supported = {str(item) for item in supported_buses if isinstance(item, str)}
                if supported and port_type not in supported:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=self._ERROR_CODE,
                            severity="error",
                            stage=stage,
                            message=(
                                f"Device '{row_id}': disk '{disk_label}' does not support slot bus '{port_type}'."
                            ),
                            path=disk_path,
                        )
                    )

            if isinstance(mount_type, str) and isinstance(port_type, str):
                allowed_mount_ports = self._MOUNT_PORT_COMPATIBILITY.get(mount_type)
                if allowed_mount_ports is not None and port_type not in allowed_mount_ports:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=self._ERROR_CODE,
                            severity="error",
                            stage=stage,
                            message=(
                                f"Device '{row_id}': disk '{disk_label}' mount_type '{mount_type}' "
                                f"is incompatible with port type '{port_type}'."
                            ),
                            path=disk_path,
                        )
                    )

            if mount_type == "soldered" and removable is True:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._ERROR_CODE,
                        severity="error",
                        stage=stage,
                        message=f"Device '{row_id}': soldered disk '{disk_label}' cannot be removable.",
                        path=disk_path,
                    )
                )
            if mount_type == "removable" and removable is False:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=f"Device '{row_id}': removable disk '{disk_label}' has removable=false.",
                        path=disk_path,
                    )
                )
            if mount_type == "virtual" and disk_virtual is not True:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=self._WARNING_CODE,
                        severity="warning",
                        stage=stage,
                        message=f"Device '{row_id}': virtual disk '{disk_label}' should set virtual=true.",
                        path=disk_path,
                    )
                )

    def _media_by_id(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        media_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not self._is_media_row(row):
                continue
            media_id = self._media_id(row)
            if not media_id:
                continue
            media_by_id[media_id] = self._normalize_media(row, media_id=media_id)
        return media_by_id

    def _attachments_by_slot(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
        attachments_by_slot: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for row in rows:
            if not self._is_media_attachment_row(row):
                continue
            extensions = self._extensions(row)
            device_ref = extensions.get("device_ref")
            slot_ref = extensions.get("slot_ref")
            if not isinstance(device_ref, str) or not device_ref:
                continue
            if not isinstance(slot_ref, str) or not slot_ref:
                continue
            attachments_by_slot.setdefault(device_ref, {}).setdefault(slot_ref, []).append(extensions)
        return attachments_by_slot

    def _normalized_disks(
        self,
        *,
        device_id: str,
        slots: list[dict[str, Any]],
        attachments_by_slot: dict[str, dict[str, list[dict[str, Any]]]],
        media_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        device_attachments = attachments_by_slot.get(device_id, {})
        normalized: list[dict[str, Any]] = []
        for slot in slots:
            slot_id = slot.get("id")
            if not isinstance(slot_id, str) or not slot_id:
                continue
            slot_attachments = device_attachments.get(slot_id, [])
            selected: dict[str, Any] | None = None
            if slot_attachments:
                present = [item for item in slot_attachments if item.get("state", "present") == "present"]
                selected = present[0] if present else slot_attachments[0]
            if not isinstance(selected, dict):
                continue
            media_ref = selected.get("media_ref")
            if not isinstance(media_ref, str) or not media_ref:
                continue
            media = media_by_id.get(media_ref)
            if not isinstance(media, dict):
                continue
            normalized.append(
                {
                    "id": media.get("id"),
                    "type": media.get("type"),
                    "mount_type": slot.get("mount"),
                    "port_type": slot.get("bus"),
                    "slot_id": slot_id,
                    "removable": media.get("removable"),
                    "virtual": media.get("virtual"),
                    "os_device_path": media.get("os_device_path"),
                    "supported_buses": media.get("supported_buses"),
                }
            )
        return normalized

    def _normalize_media(self, row: dict[str, Any], *, media_id: str) -> dict[str, Any]:
        extensions = self._extensions(row)
        media_type = extensions.get("media_type")
        if not isinstance(media_type, str):
            media_type = extensions.get("type")
        os_device_path = extensions.get("os_device_path")
        if os_device_path is None:
            os_device_path = extensions.get("device")
        return {
            "id": media_id,
            "type": media_type,
            "removable": extensions.get("removable"),
            "virtual": extensions.get("virtual"),
            "supported_buses": extensions.get("supported_buses"),
            "os_device_path": os_device_path,
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
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and class_ref.startswith("class.compute."):
            return True
        if row.get("group") != "devices":
            return False
        extensions = self._extensions(row)
        return any(key in extensions for key in ("storage_slots", "substrate", "os"))

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
