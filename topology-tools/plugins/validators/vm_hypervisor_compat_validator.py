"""VM hypervisor compatibility validator (ADR 0087 Phase 3)."""

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


class VmHypervisorCompatValidator(ValidatorJsonPlugin):
    """Validate VM disk/bus/format compatibility with host hypervisor.

    This validator enforces ADR 0087 Phase 3 requirements:
    - AC-13: VM disk format validated against hypervisor.allowed_disk_formats
    - AC-14: VM disk bus validated against hypervisor.allowed_disk_buses
    - AC-15: disk_id uniqueness enforced
    - AC-16: bus:slot uniqueness enforced
    - AC-17: Exactly one boot disk enforced
    - AC-18: boot_order references validated
    """

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _VM_CLASSES = {"class.compute.workload.vm"}
    _HYPERVISOR_CLASSES = {
        "class.compute.hypervisor",
        "class.compute.hypervisor.proxmox",
        "class.compute.hypervisor.vbox",
        "class.compute.hypervisor.hyperv",
        "class.compute.hypervisor.vmware",
        "class.compute.hypervisor.xen",
    }

    # Default allowed formats/buses per hypervisor (fallback if not in class)
    _DEFAULT_ALLOWED_FORMATS: dict[str, set[str]] = {
        "class.compute.hypervisor.proxmox": {"qcow2", "raw", "vmdk"},
        "class.compute.hypervisor.vbox": {"vdi", "vmdk", "vhd", "raw"},
        "class.compute.hypervisor.hyperv": {"vhd", "vhdx"},
        "class.compute.hypervisor.vmware": {"vmdk"},
        "class.compute.hypervisor.xen": {"qcow2", "vhd", "raw"},
    }
    _DEFAULT_ALLOWED_BUSES: dict[str, set[str]] = {
        "class.compute.hypervisor.proxmox": {"scsi", "virtio", "ide", "sata"},
        "class.compute.hypervisor.vbox": {"sata", "ide", "scsi", "nvme"},
        "class.compute.hypervisor.hyperv": {"ide", "scsi"},
        "class.compute.hypervisor.vmware": {"pvscsi", "lsilogic", "ide"},
        "class.compute.hypervisor.xen": {"xvd", "ide", "scsi"},
    }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7900",
                    severity="error",
                    stage=stage,
                    message=f"vm_hypervisor_compat validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []

        # Build lookup
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        # Validate each VM
        for row in rows:
            class_ref = row.get("class_ref")
            if class_ref not in self._VM_CLASSES:
                continue

            row_id = row.get("instance")
            group = row.get("group", "vms")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = self._extensions(row)

            # Get host_ref and resolve hypervisor
            host_ref = self._extract_host_ref(row)
            if not host_ref:
                # host_ref validation is done by host_ref_dag_validator
                continue

            host_row = row_by_id.get(host_ref)
            if not isinstance(host_row, dict):
                # Unknown host is caught by other validators
                continue

            host_class = host_row.get("class_ref", "")
            host_extensions = self._extensions(host_row)

            # Get allowed formats/buses from host
            allowed_formats = self._get_allowed_formats(host_class, host_row, host_extensions)
            allowed_buses = self._get_allowed_buses(host_class, host_row, host_extensions)

            # Get disks from VM
            disks = extensions.get("disks") or row.get("disks")
            if not isinstance(disks, list):
                # No disks defined - that's fine for now (might be defined at object level)
                continue

            # Track for uniqueness checks
            seen_disk_ids: set[str] = set()
            seen_bus_slots: set[str] = set()
            boot_disk_count = 0
            disk_id_list: list[str] = []

            for idx, disk in enumerate(disks):
                if not isinstance(disk, dict):
                    continue

                disk_id = disk.get("disk_id")
                disk_path = f"{row_prefix}.disks[{idx}]"

                # AC-15: disk_id uniqueness
                if isinstance(disk_id, str) and disk_id:
                    disk_id_list.append(disk_id)
                    if disk_id in seen_disk_ids:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7901",
                                severity="error",
                                stage=stage,
                                message=f"VM '{row_id}' has duplicate disk_id '{disk_id}'.",
                                path=f"{disk_path}.disk_id",
                            )
                        )
                    seen_disk_ids.add(disk_id)

                # AC-16: bus:slot uniqueness
                bus = disk.get("bus")
                slot = disk.get("slot")
                if isinstance(bus, str) and slot is not None:
                    bus_slot = f"{bus}:{slot}"
                    if bus_slot in seen_bus_slots:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7902",
                                severity="error",
                                stage=stage,
                                message=f"VM '{row_id}' has duplicate bus:slot '{bus_slot}'.",
                                path=f"{disk_path}.bus",
                            )
                        )
                    seen_bus_slots.add(bus_slot)

                # AC-17: Count boot disks
                role = disk.get("role")
                if role == "boot":
                    boot_disk_count += 1

                # AC-13: Validate disk format against hypervisor
                disk_format = disk.get("format")
                if isinstance(disk_format, str) and allowed_formats:
                    if disk_format not in allowed_formats:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7903",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"VM '{row_id}' disk format '{disk_format}' not allowed by "
                                    f"hypervisor '{host_class}'. Allowed: {sorted(allowed_formats)}."
                                ),
                                path=f"{disk_path}.format",
                            )
                        )

                # AC-14: Validate disk bus against hypervisor
                if isinstance(bus, str) and allowed_buses:
                    if bus not in allowed_buses:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7904",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"VM '{row_id}' disk bus '{bus}' not allowed by "
                                    f"hypervisor '{host_class}'. Allowed: {sorted(allowed_buses)}."
                                ),
                                path=f"{disk_path}.bus",
                            )
                        )

            # AC-17: Exactly one boot disk
            if disks and boot_disk_count == 0:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7905",
                        severity="warning",
                        stage=stage,
                        message=f"VM '{row_id}' has no disk with role 'boot'.",
                        path=f"{row_prefix}.disks",
                    )
                )
            elif boot_disk_count > 1:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7905",
                        severity="error",
                        stage=stage,
                        message=f"VM '{row_id}' has {boot_disk_count} boot disks; exactly one required.",
                        path=f"{row_prefix}.disks",
                    )
                )

            # AC-18: boot_order references valid disk_id values
            boot_order = extensions.get("boot_order") or row.get("boot_order")
            if isinstance(boot_order, list):
                for idx, boot_entry in enumerate(boot_order):
                    if isinstance(boot_entry, str) and boot_entry not in disk_id_list:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7906",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"VM '{row_id}' boot_order[{idx}] references unknown "
                                    f"disk_id '{boot_entry}'."
                                ),
                                path=f"{row_prefix}.boot_order[{idx}]",
                            )
                        )

        return self.make_result(diagnostics)

    def _extract_host_ref(self, row: dict[str, Any]) -> str | None:
        """Extract host_ref from row (extensions or top-level)."""
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            host_ref = extensions.get("host_ref")
            if isinstance(host_ref, str) and host_ref:
                return host_ref
            device_ref = extensions.get("device_ref")
            if isinstance(device_ref, str) and device_ref:
                return device_ref

        host_ref = row.get("host_ref")
        if isinstance(host_ref, str) and host_ref:
            return host_ref
        device_ref = row.get("device_ref")
        if isinstance(device_ref, str) and device_ref:
            return device_ref

        return None

    def _get_allowed_formats(
        self, host_class: str, host_row: dict[str, Any], host_extensions: dict[str, Any]
    ) -> set[str]:
        """Get allowed disk formats from hypervisor."""
        # Check vm_constraints in extensions or top-level
        vm_constraints = host_extensions.get("vm_constraints") or host_row.get("vm_constraints")
        if isinstance(vm_constraints, dict):
            allowed = vm_constraints.get("allowed_disk_formats")
            if isinstance(allowed, list):
                return set(str(f) for f in allowed if isinstance(f, str))

        # Fall back to class defaults
        return self._DEFAULT_ALLOWED_FORMATS.get(host_class, set())

    def _get_allowed_buses(
        self, host_class: str, host_row: dict[str, Any], host_extensions: dict[str, Any]
    ) -> set[str]:
        """Get allowed disk buses from hypervisor."""
        # Check vm_constraints in extensions or top-level
        vm_constraints = host_extensions.get("vm_constraints") or host_row.get("vm_constraints")
        if isinstance(vm_constraints, dict):
            allowed = vm_constraints.get("allowed_disk_buses")
            if isinstance(allowed, list):
                return set(str(b) for b in allowed if isinstance(b, str))

        # Fall back to class defaults
        return self._DEFAULT_ALLOWED_BUSES.get(host_class, set())

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        """Get extensions dict from row."""
        extensions = row.get("extensions")
        return extensions if isinstance(extensions, dict) else {}
