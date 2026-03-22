"""Runtime network reachability validator."""

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


class NetworkRuntimeReachabilityValidator(ValidatorJsonPlugin):
    """Warn when runtime target cannot reach requested network binding."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _HOST_OS_ACTIVE_STATUS = "active"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7843",
                    severity="error",
                    stage=stage,
                    message=f"runtime_reachability validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        device_to_host_os: dict[str, set[str]] = {}
        lxc_networks_by_id: dict[str, set[str]] = {}
        vm_networks_by_id: dict[str, set[str]] = {}
        network_reachable_devices: dict[str, set[str]] = {}
        network_reachable_host_os: dict[str, set[str]] = {}
        network_plane_by_id: dict[str, str] = {}
        network_manager_by_id: dict[str, str] = {}

        for row in rows:
            class_ref = row.get("class_ref")
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue

            if class_ref == "class.os":
                status = str(row.get("status") or "").strip().lower()
                if status and status != self._HOST_OS_ACTIVE_STATUS:
                    continue
                for device_row in rows:
                    if not isinstance(device_row, dict):
                        continue
                    if device_row.get("layer") != "L1":
                        continue
                    os_refs = device_row.get("os_refs")
                    if not isinstance(os_refs, list) or row_id not in os_refs:
                        continue
                    dev_id = device_row.get("instance")
                    if isinstance(dev_id, str) and dev_id:
                        device_to_host_os.setdefault(dev_id, set()).add(row_id)
                continue

            if class_ref == "class.compute.workload.container":
                lxc_networks_by_id[row_id] = self._extract_network_refs(ctx=ctx, row=row)
                continue
            if class_ref == "class.compute.cloud_vm":
                vm_networks_by_id[row_id] = self._extract_network_refs(ctx=ctx, row=row)
                continue
            if class_ref == "class.network.vlan":
                network_reachable_devices[row_id] = set()
                network_reachable_host_os[row_id] = set()
                network_plane = self._resolve_field(ctx=ctx, row=row, key="network_plane")
                managed_by_ref = self._resolve_field(ctx=ctx, row=row, key="managed_by_ref")
                if isinstance(network_plane, str) and network_plane:
                    network_plane_by_id[row_id] = network_plane
                if isinstance(managed_by_ref, str) and managed_by_ref:
                    network_manager_by_id[row_id] = managed_by_ref
                ip_allocations = self._resolve_field(ctx=ctx, row=row, key="ip_allocations")
                if isinstance(ip_allocations, list):
                    for alloc in ip_allocations:
                        if not isinstance(alloc, dict):
                            continue
                        device_ref = alloc.get("device_ref")
                        host_os_ref = alloc.get("host_os_ref")
                        if isinstance(device_ref, str) and device_ref:
                            network_reachable_devices[row_id].add(device_ref)
                        if isinstance(host_os_ref, str) and host_os_ref:
                            network_reachable_host_os[row_id].add(host_os_ref)

        for row in rows:
            class_ref = row.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref.startswith("class.service."):
                continue
            runtime = row.get("runtime")
            if not isinstance(runtime, dict):
                continue
            runtime_type = runtime.get("type")
            target_ref = runtime.get("target_ref")
            network_binding_ref = runtime.get("network_binding_ref")
            if not isinstance(target_ref, str) or not target_ref:
                continue
            if not isinstance(network_binding_ref, str) or not network_binding_ref:
                continue
            if network_binding_ref not in network_reachable_devices:
                continue

            service_id = row.get("instance")
            path = f"instance:{row.get('group')}:{service_id}.runtime.network_binding_ref"

            if runtime_type == "lxc":
                target_networks = lxc_networks_by_id.get(target_ref)
                if target_networks is not None and network_binding_ref not in target_networks:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7844",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Service '{service_id}': runtime target '{target_ref}' does not attach to "
                                f"network '{network_binding_ref}' in workload network refs."
                            ),
                            path=path,
                        )
                    )
                continue

            if runtime_type == "vm":
                target_networks = vm_networks_by_id.get(target_ref)
                if target_networks is not None and network_binding_ref not in target_networks:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7844",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Service '{service_id}': runtime target '{target_ref}' does not attach to "
                                f"network '{network_binding_ref}' in workload network refs."
                            ),
                            path=path,
                        )
                    )
                continue

            if runtime_type in {"docker", "baremetal"}:
                device_reachable = target_ref in network_reachable_devices.get(network_binding_ref, set())
                target_host_os_set = device_to_host_os.get(target_ref, set())
                host_os_reachable = bool(target_host_os_set & network_reachable_host_os.get(network_binding_ref, set()))
                overlay_managed_by_target = (
                    network_plane_by_id.get(network_binding_ref) == "overlay"
                    and network_manager_by_id.get(network_binding_ref) == target_ref
                )
                if not device_reachable and not host_os_reachable and not overlay_managed_by_target:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7844",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Service '{service_id}': runtime target '{target_ref}' has no reachable "
                                f"ownership/attachment in network '{network_binding_ref}'."
                            ),
                            path=path,
                        )
                    )

        return self.make_result(diagnostics)

    def _extract_network_refs(self, *, ctx: PluginContext, row: dict[str, Any]) -> set[str]:
        networks = self._resolve_field(ctx=ctx, row=row, key="networks")
        if not isinstance(networks, list):
            return set()
        refs: set[str] = set()
        for nic in networks:
            if not isinstance(nic, dict):
                continue
            network_ref = nic.get("network_ref")
            if isinstance(network_ref, str) and network_ref:
                refs.add(network_ref)
        return refs

    @staticmethod
    def _resolve_field(*, ctx: PluginContext, row: dict[str, Any], key: str) -> Any:
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
