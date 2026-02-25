"""Data resolution module for documentation generator.

This module handles resolution of:
- Storage pools and endpoints
- Data assets placement
- L1 storage views
- Network configurations
- Service runtime compatibility fields
"""

import copy
from typing import Any, Dict, List, Optional, Set, Tuple


class DataResolver:
    """Resolves complex data structures from topology layers for documentation."""

    def __init__(self, topology: Dict[str, Any]):
        """Initialize resolver with topology data.

        Args:
            topology: Complete topology structure with all layers
        """
        self.topology = topology

    def _as_list(self, value: Any) -> List[Any]:
        """Normalize list-or-dict values to a list of items.

        Accepts:
        - list: returned as-is
        - dict: returns list of values
        - None/other: returns empty list
        """
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list(value.values())
        return []

    def get_resolved_networks(self) -> List[Dict[str, Any]]:
        """Resolve L2 networks with optional network profile defaults.

        Returns:
            List of networks with profile defaults merged
        """
        l2 = self.topology.get("L2_network", {})
        profiles = l2.get("network_profiles", {}) or {}
        resolved = []

        for network in self._as_list(l2.get("networks")):
            merged = {}
            profile_ref = network.get("profile_ref")
            if profile_ref and profile_ref in profiles and isinstance(profiles[profile_ref], dict):
                merged.update(profiles[profile_ref])
            merged.update(network)
            resolved.append(merged)

        return resolved

    def build_l1_storage_views(self) -> Dict[str, Any]:
        """Build pre-resolved storage rows per device from L1 media registry + attachments.

        Returns:
            Dictionary with:
            - rows_by_device: Storage slot rows indexed by device ID
            - media_by_id: Media registry indexed by ID
            - media_registry: Original media list
            - media_attachments: Original attachments list
        """
        l1 = self.topology.get("L1_foundation", {}) or {}
        devices = self._as_list(l1.get("devices"))
        media_registry = self._as_list(l1.get("media_registry"))
        media_attachments = self._as_list(l1.get("media_attachments"))

        # Index media by ID
        media_by_id = {
            media.get("id"): media for media in media_registry if isinstance(media, dict) and media.get("id")
        }

        # Index attachments by device and slot
        attachments_by_device_slot: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for attachment in media_attachments:
            if not isinstance(attachment, dict):
                continue
            device_ref = attachment.get("device_ref")
            slot_ref = attachment.get("slot_ref")
            if not device_ref or not slot_ref:
                continue
            attachments_by_device_slot.setdefault(device_ref, {}).setdefault(slot_ref, []).append(attachment)

        # Build rows per device
        rows_by_device: Dict[str, List[Dict[str, Any]]] = {}
        for device in devices:
            if not isinstance(device, dict):
                continue
            dev_id = device.get("id")
            if not dev_id:
                continue

            specs = device.get("specs", {}) if isinstance(device.get("specs"), dict) else {}
            slots = specs.get("storage_slots", []) if isinstance(specs.get("storage_slots"), list) else []
            device_rows: List[Dict[str, Any]] = []

            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                slot_id = slot.get("id")
                slot_attachments = attachments_by_device_slot.get(dev_id, {}).get(slot_id, []) if slot_id else []

                # Sort: present first, then by ID
                sorted_attachments = sorted(
                    slot_attachments,
                    key=lambda item: (0 if item.get("state", "present") == "present" else 1, item.get("id", "")),
                )

                if not sorted_attachments:
                    # Empty slot
                    device_rows.append(
                        {
                            "slot_id": slot_id,
                            "slot_bus": slot.get("bus"),
                            "slot_mount": slot.get("mount"),
                            "slot_name": slot.get("name"),
                            "attachment_id": None,
                            "attachment_state": "empty",
                            "media": None,
                        }
                    )
                    continue

                # Add row for each attachment
                for attachment in sorted_attachments:
                    media = media_by_id.get(attachment.get("media_ref"))
                    device_rows.append(
                        {
                            "slot_id": slot_id,
                            "slot_bus": slot.get("bus"),
                            "slot_mount": slot.get("mount"),
                            "slot_name": slot.get("name"),
                            "attachment_id": attachment.get("id"),
                            "attachment_state": attachment.get("state", "present"),
                            "media": media,
                        }
                    )

            rows_by_device[dev_id] = device_rows

        return {
            "rows_by_device": rows_by_device,
            "media_by_id": media_by_id,
            "media_registry": media_registry,
            "media_attachments": media_attachments,
        }

    def resolve_storage_pools_for_docs(self) -> List[Dict[str, Any]]:
        """Resolve storage pools for docs from legacy storage or storage_endpoints.

        For storage_endpoints, enrich with inferred device/media from L3 storage chain.

        Returns:
            List of resolved storage pool specifications
        """
        l1 = self.topology.get("L1_foundation", {}) or {}
        l3 = self.topology.get("L3_data", {}) or {}

        # Legacy storage path
        legacy_storage = self._as_list(l3.get("storage"))
        if legacy_storage:
            return legacy_storage

        # Build indexes
        media_registry = {
            media.get("id"): media
            for media in self._as_list(l1.get("media_registry"))
            if isinstance(media, dict) and media.get("id")
        }
        attachments = {
            attachment.get("id"): attachment
            for attachment in self._as_list(l1.get("media_attachments"))
            if isinstance(attachment, dict) and attachment.get("id")
        }
        partitions = {
            item.get("id"): item
            for item in self._as_list(l3.get("partitions"))
            if isinstance(item, dict) and item.get("id")
        }
        volume_groups = {
            item.get("id"): item
            for item in self._as_list(l3.get("volume_groups"))
            if isinstance(item, dict) and item.get("id")
        }
        logical_volumes = {
            item.get("id"): item
            for item in self._as_list(l3.get("logical_volumes"))
            if isinstance(item, dict) and item.get("id")
        }
        filesystems = {
            item.get("id"): item
            for item in self._as_list(l3.get("filesystems"))
            if isinstance(item, dict) and item.get("id")
        }
        mount_points = {
            item.get("id"): item
            for item in self._as_list(l3.get("mount_points"))
            if isinstance(item, dict) and item.get("id")
        }

        def _resolve_from_partition(
            partition_ref: str,
            device_ref: Optional[str],
            media_type: Optional[str],
        ) -> Tuple[Optional[str], Optional[str]]:
            """Resolve device and media type from partition reference."""
            partition = partitions.get(partition_ref, {}) if partition_ref else {}
            attachment_ref = partition.get("media_attachment_ref")
            attachment = attachments.get(attachment_ref, {}) if attachment_ref else {}
            media = media_registry.get(attachment.get("media_ref"), {}) if attachment else {}
            resolved_device = device_ref or attachment.get("device_ref")
            resolved_media = media_type or media.get("type")
            return resolved_device, resolved_media

        def _resolve_from_lv(
            lv_ref: str,
            device_ref: Optional[str],
            media_type: Optional[str],
        ) -> Tuple[Optional[str], Optional[str]]:
            """Resolve device and media type from logical volume reference."""
            lv = logical_volumes.get(lv_ref, {}) if lv_ref else {}
            vg = volume_groups.get(lv.get("vg_ref"), {}) if lv else {}
            for pv_ref in vg.get("pv_refs") or []:
                device_ref, media_type = _resolve_from_partition(pv_ref, device_ref, media_type)
                if device_ref and media_type:
                    break
            return device_ref, media_type

        # Resolve storage endpoints
        resolved: List[Dict[str, Any]] = []
        for endpoint in self._as_list(l3.get("storage_endpoints")):
            if not isinstance(endpoint, dict):
                continue

            item = copy.deepcopy(endpoint)
            device_ref = item.get("device_ref")
            media_type = item.get("media")

            # Resolve from mount point
            mount_point = mount_points.get(item.get("mount_point_ref"), {}) if item.get("mount_point_ref") else {}
            if mount_point:
                device_ref = device_ref or mount_point.get("device_ref")
                if not item.get("path"):
                    item["path"] = mount_point.get("path")

            # Resolve from filesystem
            filesystem = filesystems.get(mount_point.get("filesystem_ref"), {}) if mount_point else {}
            if filesystem.get("partition_ref"):
                device_ref, media_type = _resolve_from_partition(
                    filesystem.get("partition_ref"),
                    device_ref,
                    media_type,
                )
            elif filesystem.get("lv_ref"):
                device_ref, media_type = _resolve_from_lv(
                    filesystem.get("lv_ref"),
                    device_ref,
                    media_type,
                )

            # Resolve from LV reference
            if item.get("lv_ref"):
                device_ref, media_type = _resolve_from_lv(item.get("lv_ref"), device_ref, media_type)
                if not item.get("path"):
                    lv = logical_volumes.get(item.get("lv_ref"), {})
                    vg = volume_groups.get(lv.get("vg_ref"), {}) if lv else {}
                    vg_name = vg.get("name") or vg.get("id")
                    lv_name = lv.get("name") or lv.get("id")
                    if vg_name and lv_name:
                        item["path"] = f"{vg_name}/{lv_name}"

            # Infer from attachment
            infer_from = endpoint.get("infer_from", {}) if isinstance(endpoint.get("infer_from"), dict) else {}
            attachment_ref = infer_from.get("media_attachment_ref")
            attachment = attachments.get(attachment_ref, {}) if attachment_ref else {}
            media = media_registry.get(attachment.get("media_ref"), {}) if attachment else {}
            device_ref = device_ref or attachment.get("device_ref")
            media_type = media_type or media.get("type")

            item["device_ref"] = device_ref
            item["media"] = media_type

            # Set path from infer_from if not set
            if not item.get("path"):
                lv_name = infer_from.get("lv_name")
                vg_name = infer_from.get("vg_name")
                if vg_name and lv_name:
                    item["path"] = f"{vg_name}/{lv_name}"
                elif lv_name:
                    item["path"] = lv_name

            resolved.append(item)

        return resolved

    def resolve_data_assets_for_docs(self) -> List[Dict[str, Any]]:
        """Resolve data asset placement links for documentation.

        Canonical placement comes from L4 storage bindings (storage_endpoint_ref)
        with data_asset_ref linkage on rootfs/volumes.

        For docker/baremetal runtimes, fallback endpoint inference is derived from
        active host OS installation root storage endpoint on target device.

        Returns:
            List of resolved data asset placements
        """
        l3 = self.topology.get("L3_data", {}) or {}
        l4 = self.topology.get("L4_platform", {}) or {}
        l5 = self.topology.get("L5_application", {}) or {}
        data_assets = self._as_list(l3.get("data_assets"))

        placement_map: Dict[str, Dict[str, Set[str]]] = {}
        host_root_endpoint_by_device: Dict[str, str] = {}

        # Build host root endpoint index
        for host_os in self._as_list(l4.get("host_operating_systems")):
            if not isinstance(host_os, dict):
                continue
            status = str(host_os.get("status", "")).strip().lower()
            if status and status != "active":
                continue
            device_ref = host_os.get("device_ref")
            installation = host_os.get("installation") if isinstance(host_os.get("installation"), dict) else {}
            root_storage_ref = installation.get("root_storage_endpoint_ref")
            if isinstance(device_ref, str) and device_ref and isinstance(root_storage_ref, str) and root_storage_ref:
                host_root_endpoint_by_device.setdefault(device_ref, root_storage_ref)

        def _extract_service_mount_paths(service: Dict[str, Any]) -> List[str]:
            """Extract mount paths from service storage configuration."""
            mount_paths: Set[str] = set()

            storage = service.get("storage") if isinstance(service.get("storage"), dict) else {}
            path_single = storage.get("path")
            if isinstance(path_single, str) and path_single:
                mount_paths.add(path_single)

            path_map = storage.get("paths") if isinstance(storage.get("paths"), dict) else {}
            for value in path_map.values():
                if isinstance(value, str) and value:
                    mount_paths.add(value)

            # Extract from Docker volumes
            config = service.get("config") if isinstance(service.get("config"), dict) else {}
            docker = config.get("docker") if isinstance(config.get("docker"), dict) else {}
            volumes = docker.get("volumes") if isinstance(docker.get("volumes"), list) else []
            for volume in volumes:
                if isinstance(volume, str):
                    host_path = volume.split(":", 1)[0].strip()
                    if host_path.startswith("/"):
                        mount_paths.add(host_path)
                    continue
                if isinstance(volume, dict):
                    host_path = volume.get("source") or volume.get("host_path") or volume.get("src")
                    if isinstance(host_path, str) and host_path.startswith("/"):
                        mount_paths.add(host_path)

            return sorted(mount_paths)

        def _register(
            data_asset_ref: Optional[str],
            storage_ref: Optional[str],
            runtime_ref: Optional[str],
            mount_path: Optional[str],
            source: Optional[str],
        ) -> None:
            """Register data asset placement."""
            if not data_asset_ref:
                return
            slot = placement_map.setdefault(
                data_asset_ref,
                {
                    "storage_endpoint_refs": set(),
                    "runtime_refs": set(),
                    "mount_paths": set(),
                    "placement_sources": set(),
                },
            )
            if storage_ref:
                slot["storage_endpoint_refs"].add(storage_ref)
            if runtime_ref:
                slot["runtime_refs"].add(runtime_ref)
            if mount_path:
                slot["mount_paths"].add(mount_path)
            if source:
                slot["placement_sources"].add(source)

        # Register from LXC
        for lxc in self._as_list(l4.get("lxc")):
            if not isinstance(lxc, dict):
                continue
            runtime_ref = lxc.get("id")
            storage = lxc.get("storage", {}) if isinstance(lxc.get("storage"), dict) else {}

            rootfs = storage.get("rootfs", {}) if isinstance(storage.get("rootfs"), dict) else {}
            _register(
                rootfs.get("data_asset_ref"),
                rootfs.get("storage_endpoint_ref") or rootfs.get("storage_ref"),
                runtime_ref,
                "/",
                "l4-storage",
            )

            for volume in storage.get("volumes", []) or []:
                if not isinstance(volume, dict):
                    continue
                _register(
                    volume.get("data_asset_ref"),
                    volume.get("storage_endpoint_ref") or volume.get("storage_ref"),
                    runtime_ref,
                    volume.get("mount_path"),
                    "l4-storage",
                )

        # Register from VMs
        for vm in self._as_list(l4.get("vms")):
            if not isinstance(vm, dict):
                continue
            runtime_ref = vm.get("id")
            for disk in vm.get("storage", []) or []:
                if not isinstance(disk, dict):
                    continue
                _register(
                    disk.get("data_asset_ref"),
                    disk.get("storage_endpoint_ref") or disk.get("storage_ref"),
                    runtime_ref,
                    disk.get("mount_path") or disk.get("path") or disk.get("target"),
                    "l4-storage",
                )

        # Register from services
        for service in self._as_list(l5.get("services")):
            if not isinstance(service, dict):
                continue
            asset_refs = service.get("data_asset_refs") if isinstance(service.get("data_asset_refs"), list) else []
            if not asset_refs:
                continue

            runtime = service.get("runtime") if isinstance(service.get("runtime"), dict) else {}
            runtime_type = str(runtime.get("type") or "").strip().lower()
            runtime_target_ref = runtime.get("target_ref")
            runtime_ref = (
                runtime_target_ref if isinstance(runtime_target_ref, str) and runtime_target_ref else service.get("id")
            )
            storage_ref = runtime.get("storage_endpoint_ref") or runtime.get("storage_ref")

            # Fallback for docker/baremetal
            if (
                not storage_ref
                and runtime_type in {"docker", "baremetal"}
                and isinstance(runtime_target_ref, str)
                and runtime_target_ref
            ):
                storage_ref = host_root_endpoint_by_device.get(runtime_target_ref)

            mount_paths = _extract_service_mount_paths(service)
            source = "l5-runtime-host-root" if storage_ref and runtime_type in {"docker", "baremetal"} else "l5-runtime"

            for asset_ref in asset_refs:
                for mount_path in mount_paths or [None]:
                    _register(asset_ref, storage_ref, runtime_ref, mount_path, source)

        # Build result list
        resolved: List[Dict[str, Any]] = []
        for asset in data_assets:
            if not isinstance(asset, dict):
                continue
            asset_id = asset.get("id")
            placement = placement_map.get(asset_id, {})

            resolved.append(
                {
                    "asset": asset,
                    "storage_endpoint_refs": sorted(placement.get("storage_endpoint_refs", set())),
                    "runtime_refs": sorted(placement.get("runtime_refs", set())),
                    "mount_paths": sorted(placement.get("mount_paths", set())),
                    "placement_sources": sorted(placement.get("placement_sources", set())),
                }
            )

        return resolved

    def apply_service_runtime_compat_fields(self) -> None:
        """Enrich services with compatibility fields derived from runtime.

        Templates reference structural compatibility fields (device_ref/lxc_ref/network_ref/ip).
        This keeps docs generation stable while topology authoring moves to runtime.

        Modifies topology in-place.
        """
        l2 = self.topology.get("L2_network", {}) or {}
        l4 = self.topology.get("L4_platform", {}) or {}
        l5 = self.topology.get("L5_application", {}) or {}

        # Build indexes
        lxc_map = {
            item.get("id"): item for item in self._as_list(l4.get("lxc")) if isinstance(item, dict) and item.get("id")
        }
        vm_map = {
            item.get("id"): item for item in self._as_list(l4.get("vms")) if isinstance(item, dict) and item.get("id")
        }

        # Build IP allocation index
        ip_allocations = self._as_list(l2.get("ip_allocations"))
        alloc_by_network_device = {}
        for alloc in ip_allocations:
            if not isinstance(alloc, dict):
                continue
            network_ref = alloc.get("network_ref")
            device_ref = alloc.get("device_ref")
            ip = alloc.get("ip", "").split("/")[0].strip()  # Remove CIDR
            if network_ref and device_ref and ip:
                alloc_by_network_device[(network_ref, device_ref)] = ip

        def _ip_from_runtime_target(
            runtime_type: str,
            target_ref: str,
            network_binding_ref: str,
        ) -> str:
            """Get IP from runtime target and network binding."""
            if not target_ref or not network_binding_ref:
                return ""

            if runtime_type == "lxc":
                lxc = lxc_map.get(target_ref, {})
                device_ref = lxc.get("device_ref")
            elif runtime_type == "vm":
                vm = vm_map.get(target_ref, {})
                device_ref = vm.get("device_ref")
            else:
                device_ref = target_ref

            if device_ref:
                return alloc_by_network_device.get((network_binding_ref, device_ref), "")
            return ""

        # Enrich services
        services = list(self._as_list(l5.get("services")))
        for service in services:
            if not isinstance(service, dict):
                continue

            # Extract runtime info
            runtime = service.get("runtime") if isinstance(service.get("runtime"), dict) else {}
            runtime_type = str(runtime.get("type") or "").strip().lower()
            target_ref = runtime.get("target_ref")

            # Set device_ref
            if not service.get("device_ref"):
                if runtime_type == "lxc" and target_ref:
                    host = lxc_map.get(target_ref, {})
                    service["device_ref"] = host.get("device_ref")
                elif runtime_type == "vm" and target_ref:
                    host = vm_map.get(target_ref, {})
                    service["device_ref"] = host.get("device_ref")
                elif runtime_type in {"docker", "baremetal"} and target_ref:
                    service["device_ref"] = target_ref

            # Set lxc_ref/vm_ref for backward compatibility
            if runtime_type == "lxc" and target_ref:
                service.setdefault("lxc_ref", target_ref)
            elif runtime_type == "vm" and target_ref:
                service.setdefault("vm_ref", target_ref)

            # Set network_ref
            if not service.get("network_ref"):
                if service.get("lxc_ref"):
                    host = lxc_map.get(service["lxc_ref"], {})
                    nic = (host.get("networks", []) or [{}])[0]
                    if isinstance(nic, dict) and nic.get("network_ref"):
                        service.setdefault("network_ref", nic["network_ref"])
                elif service.get("vm_ref"):
                    host = vm_map.get(service["vm_ref"], {})
                    nic = (host.get("networks", []) or [{}])[0]
                    if isinstance(nic, dict) and nic.get("network_ref"):
                        service.setdefault("network_ref", nic["network_ref"])

            # Set IP
            if not service.get("ip"):
                inferred_ip = _ip_from_runtime_target(
                    runtime_type or "",
                    target_ref or "",
                    service.get("network_ref", ""),
                )
                if inferred_ip:
                    service["ip"] = inferred_ip

        l5["services"] = services
        self.topology["L5_application"] = l5
