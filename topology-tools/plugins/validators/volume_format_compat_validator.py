"""Volume format compatibility validator (ADR 0087 Phase 4)."""

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


class VolumeFormatCompatValidator(ValidatorJsonPlugin):
    """Validate volume format compatibility with pool and hypervisor.

    This validator enforces ADR 0087 Phase 4 requirements:
    - AC-19: Volume format property validated
    - AC-20: Volume↔pool format compatibility validated
    - AC-21: data_asset_ref resolves to valid L3 entity
    - AC-22: Cross-layer volume↔hypervisor format validated
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _VOLUME_CLASSES = {"class.storage.volume"}
    _POOL_CLASSES = {"class.storage.pool"}
    _DATA_ASSET_CLASSES = {"class.storage.data_asset"}

    # Pool type → allowed formats (AC-20)
    _POOL_FORMAT_COMPAT: dict[str, set[str]] = {
        "dir": {"qcow2", "raw", "vmdk", "vdi", "vhd", "vhdx"},
        "lvm": {"raw"},
        "lvmthin": {"raw"},
        "zfspool": {"raw", "subvol"},
        "nfs": {"qcow2", "raw", "vmdk", "vdi", "vhd", "vhdx"},
        "cifs": {"qcow2", "raw", "vmdk", "vdi", "vhd", "vhdx"},
        "cephfs": {"qcow2", "raw", "vmdk"},
    }

    # Hypervisor → allowed formats (AC-22)
    _HYPERVISOR_FORMAT_COMPAT: dict[str, set[str]] = {
        "class.compute.hypervisor.proxmox": {"qcow2", "raw", "vmdk"},
        "class.compute.hypervisor.vbox": {"vdi", "vmdk", "vhd", "raw"},
        "class.compute.hypervisor.hyperv": {"vhd", "vhdx"},
        "class.compute.hypervisor.vmware": {"vmdk"},
        "class.compute.hypervisor.xen": {"qcow2", "vhd", "raw"},
    }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7910",
                    severity="error",
                    stage=stage,
                    message=f"volume_format_compat validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        # Build lookups
        row_by_id: dict[str, dict[str, Any]] = {}
        pools_by_id: dict[str, dict[str, Any]] = {}
        data_assets_by_id: dict[str, dict[str, Any]] = {}
        hypervisors_by_id: dict[str, dict[str, Any]] = {}

        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            row_by_id[row_id] = row

            class_ref = row.get("class_ref", "")
            if class_ref in self._POOL_CLASSES:
                pools_by_id[row_id] = row
            elif class_ref in self._DATA_ASSET_CLASSES:
                data_assets_by_id[row_id] = row
            elif class_ref.startswith("class.compute.hypervisor"):
                hypervisors_by_id[row_id] = row

        # Validate each volume
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref not in self._VOLUME_CLASSES:
                continue

            row_id = row.get("instance")
            group = row.get("group", "volumes")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = self._extensions(row)

            # Get volume format
            volume_format = extensions.get("format") or row.get("format")
            if not isinstance(volume_format, str):
                # No format specified, skip validation (will use default)
                continue

            # AC-20: Validate volume↔pool format compatibility
            pool_ref = extensions.get("pool_ref") or row.get("pool_ref")
            if isinstance(pool_ref, str) and pool_ref:
                pool_row = pools_by_id.get(pool_ref)
                if pool_row:
                    pool_type = self._get_pool_type(pool_row)
                    if pool_type:
                        allowed_formats = self._POOL_FORMAT_COMPAT.get(pool_type, set())
                        if allowed_formats and volume_format not in allowed_formats:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E7911",
                                    severity="error",
                                    stage=stage,
                                    message=(
                                        f"Volume '{row_id}' format '{volume_format}' not compatible "
                                        f"with pool type '{pool_type}'. Allowed: {sorted(allowed_formats)}."
                                    ),
                                    path=f"{row_prefix}.format",
                                )
                            )
                else:
                    # Pool not found - emit warning
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7911",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Volume '{row_id}' pool_ref '{pool_ref}' "
                                "does not reference a known pool instance."
                            ),
                            path=f"{row_prefix}.pool_ref",
                        )
                    )

            # AC-21: Validate data_asset_ref resolves to valid L3 entity
            data_asset_ref = extensions.get("data_asset_ref") or row.get("data_asset_ref")
            if isinstance(data_asset_ref, str) and data_asset_ref:
                if data_asset_ref not in data_assets_by_id:
                    # Check if it exists at all
                    target = row_by_id.get(data_asset_ref)
                    if not target:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7912",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Volume '{row_id}' data_asset_ref '{data_asset_ref}' "
                                    "does not reference a known instance."
                                ),
                                path=f"{row_prefix}.data_asset_ref",
                            )
                        )
                    else:
                        target_class = target.get("class_ref", "")
                        if not target_class.startswith("class.storage.data_asset"):
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="W7912",
                                    severity="warning",
                                    stage=stage,
                                    message=(
                                        f"Volume '{row_id}' data_asset_ref '{data_asset_ref}' "
                                        f"targets '{target_class}' instead of data_asset class."
                                    ),
                                    path=f"{row_prefix}.data_asset_ref",
                                )
                            )

            # AC-22: Cross-layer volume↔hypervisor format validation
            # Find hypervisor through workload → host_ref chain
            hypervisor_class = self._find_hypervisor_for_volume(row, row_by_id, hypervisors_by_id)
            if hypervisor_class:
                allowed_formats = self._HYPERVISOR_FORMAT_COMPAT.get(hypervisor_class, set())
                if allowed_formats and volume_format not in allowed_formats:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7913",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Volume '{row_id}' format '{volume_format}' not compatible "
                                f"with hypervisor '{hypervisor_class}'. Allowed: {sorted(allowed_formats)}."
                            ),
                            path=f"{row_prefix}.format",
                        )
                    )

        return self.make_result(diagnostics)

    def _get_pool_type(self, pool_row: dict[str, Any]) -> str | None:
        """Get pool type from row."""
        extensions = self._extensions(pool_row)
        pool_type = extensions.get("type") or pool_row.get("type")
        return pool_type if isinstance(pool_type, str) else None

    def _find_hypervisor_for_volume(
        self,
        volume_row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        hypervisors_by_id: dict[str, dict[str, Any]],
    ) -> str | None:
        """Find hypervisor class for volume through host chain.

        Volumes are typically attached to VMs which have host_ref to hypervisors.
        We trace: volume → workload (via workload's volume_ref) → hypervisor
        """
        volume_id = volume_row.get("instance")
        if not isinstance(volume_id, str):
            return None

        # Find workload that references this volume
        for row in row_by_id.values():
            class_ref = row.get("class_ref", "")
            if not class_ref.startswith("class.compute.workload"):
                continue

            extensions = self._extensions(row)

            # Check VM disks
            disks = extensions.get("disks") or row.get("disks")
            if isinstance(disks, list):
                for disk in disks:
                    if isinstance(disk, dict):
                        vol_ref = disk.get("volume_ref")
                        if vol_ref == volume_id:
                            # Found workload, get its hypervisor
                            host_ref = self._extract_host_ref(row)
                            if host_ref and host_ref in hypervisors_by_id:
                                return hypervisors_by_id[host_ref].get("class_ref")

            # Check LXC storage
            storage = extensions.get("storage") or row.get("storage")
            if isinstance(storage, dict):
                # Check rootfs
                rootfs = storage.get("rootfs")
                if isinstance(rootfs, dict):
                    vol_ref = rootfs.get("volume_ref")
                    if vol_ref == volume_id:
                        host_ref = self._extract_host_ref(row)
                        if host_ref and host_ref in hypervisors_by_id:
                            return hypervisors_by_id[host_ref].get("class_ref")

                # Check volumes list
                volumes = storage.get("volumes")
                if isinstance(volumes, list):
                    for vol in volumes:
                        if isinstance(vol, dict):
                            vol_ref = vol.get("volume_ref")
                            if vol_ref == volume_id:
                                host_ref = self._extract_host_ref(row)
                                if host_ref and host_ref in hypervisors_by_id:
                                    return hypervisors_by_id[host_ref].get("class_ref")

        return None

    def _extract_host_ref(self, row: dict[str, Any]) -> str | None:
        """Extract host_ref from row."""
        extensions = self._extensions(row)
        for key in ("host_ref", "device_ref"):
            ref = extensions.get(key) or row.get(key)
            if isinstance(ref, str) and ref:
                return ref
        return None

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        """Get extensions dict from row."""
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}
