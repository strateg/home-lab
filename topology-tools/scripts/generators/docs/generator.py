"""
Documentation generation core for topology v4.0.
"""

import yaml
import re
import json
import base64
import copy
import shutil
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

from .docs_diagram import DiagramDocumentationGenerator
from scripts.generators.common import load_and_validate_layered_topology, prepare_output_directory


class DocumentationGenerator:
    """Generate documentation from topology v4.0"""

    ICON_NODE_RE = re.compile(
        r'^(?P<indent>\s*)(?P<node_id>[A-Za-z0-9_]+)@\{\s*'
        r'(?:(?!\}\s*$).)*?icon:\s*"(?P<icon>[^"]+)"'
        r'(?:(?!\}\s*$).)*?label:\s*"(?P<label>[^"]*)"'
        r'(?:(?!\}\s*$).)*?\}\s*$'
    )

    def __init__(
        self,
        topology_path: str,
        output_dir: str,
        templates_dir: str = "topology-tools/templates",
        mermaid_icons: bool = True,
        mermaid_icon_nodes: bool = True,
    ):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        self.mermaid_icons = mermaid_icons
        self.mermaid_icon_nodes = mermaid_icon_nodes
        self.topology: Dict = {}
        self._icon_pack_cache = None
        self._icon_data_uri_cache = {}
        self.generated_files: List[str] = []
        self.generated_at: str = ""

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Add custom filters for Mermaid diagram generation
        self.jinja_env.filters['mermaid_id'] = self._mermaid_id
        self.diagram_generator = DiagramDocumentationGenerator(self)

    @property
    def icon_mode(self) -> str:
        if not self.mermaid_icons:
            return "none"
        return "icon-nodes" if self.mermaid_icon_nodes else "compat"

    def icon_runtime_hint(self) -> str:
        if not self.mermaid_icons:
            return "Icon mode disabled."
        if self.mermaid_icon_nodes:
            return f"Icon-node mode enabled. Renderer must preload icon packs: {self.diagram_generator.ICON_PACK_HINT}."
        return "Compatibility icon mode enabled. Icons are embedded inline in labels; runtime icon pack preload is not required."

    def _icon_pack_search_dirs(self) -> List[Path]:
        """Discover candidate @iconify-json directories independent of the current working directory."""
        script_dir = Path(__file__).resolve().parent
        raw_roots = [
            Path.cwd(),
            self.topology_path.resolve().parent,
            script_dir,
            script_dir.parent,
        ]

        unique_roots = []
        seen_roots = set()
        for root in raw_roots:
            root_key = str(root)
            if root_key in seen_roots:
                continue
            seen_roots.add(root_key)
            unique_roots.append(root)

        search_dirs = []
        seen_dirs = set()
        for root in unique_roots:
            for parent in [root, *root.parents]:
                candidate = parent / "node_modules" / "@iconify-json"
                candidate_key = str(candidate)
                if candidate_key in seen_dirs:
                    continue
                seen_dirs.add(candidate_key)
                search_dirs.append(candidate)

        return search_dirs

    def _load_icon_packs(self):
        if self._icon_pack_cache is not None:
            return self._icon_pack_cache

        mapping = {
            "mdi": "mdi",
            "si": "simple-icons",
            "logos": "logos",
        }
        packs = {}
        search_dirs = self._icon_pack_search_dirs()
        for prefix, package_dir in mapping.items():
            for base_dir in search_dirs:
                icon_file = base_dir / package_dir / "icons.json"
                if not icon_file.exists():
                    continue
                try:
                    data = json.loads(icon_file.read_text(encoding="utf-8"))
                    packs[prefix] = data
                    break
                except Exception:
                    # Ignore malformed local packs and continue searching other paths.
                    continue

        self._icon_pack_cache = packs
        return packs

    @staticmethod
    def _icon_svg_from_pack(pack: Dict, icon_name: str) -> str:
        if not isinstance(pack, dict):
            return ""
        icons = pack.get("icons", {}) or {}
        icon = icons.get(icon_name)
        if not isinstance(icon, dict):
            return ""
        body = icon.get("body")
        if not body:
            return ""
        width = icon.get("width", pack.get("width", 24))
        height = icon.get("height", pack.get("height", 24))
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{body}</svg>'

    def _local_icon_src(self, icon_id: str) -> str:
        if icon_id in self._icon_data_uri_cache:
            return self._icon_data_uri_cache[icon_id]
        if ":" not in (icon_id or ""):
            return ""
        prefix, icon_name = icon_id.split(":", 1)
        packs = self._load_icon_packs()
        pack = packs.get(prefix)
        if not pack:
            return ""
        svg = self._icon_svg_from_pack(pack, icon_name)
        if not svg:
            return ""
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data_uri = f"data:image/svg+xml;base64,{encoded}"
        self._icon_data_uri_cache[icon_id] = data_uri
        return data_uri

    def _icon_html(self, icon_id: str) -> str:
        """
        Build HTML icon label.
        Prefer local icon assets from installed Iconify JSON packs.
        Fallback to remote Iconify API if local packs are unavailable.
        """
        local_src = self._local_icon_src(icon_id)
        if local_src:
            return f"<img src='{local_src}' height='16'/>"

        safe_icon = quote(icon_id or "mdi:help-circle-outline", safe="")
        return f"<img src='https://api.iconify.design/{safe_icon}.svg' height='16'/>"

    def transform_mermaid_icons_for_compat(self, content: str) -> str:
        """
        Convert Mermaid icon-node syntax to regular nodes with inline HTML icons.
        This keeps icon visuals for renderers that do not support `@{ icon: ... }`.
        """
        if not self.mermaid_icons or self.mermaid_icon_nodes:
            return content

        converted_lines = []
        for line in content.splitlines():
            match = self.ICON_NODE_RE.match(line)
            if not match:
                converted_lines.append(line)
                continue

            indent = match.group("indent")
            node_id = match.group("node_id")
            icon_id = match.group("icon")
            label = match.group("label").replace('"', '\\"')
            icon_html = self._icon_html(icon_id)
            converted_lines.append(f'{indent}{node_id}["{icon_html} {label}"]')

        return "\n".join(converted_lines)

    @staticmethod
    def _mermaid_id(value: str) -> str:
        """Convert string to valid Mermaid node ID (alphanumeric + underscore)"""
        if not value:
            return 'unknown'
        return value.replace('-', '_').replace('.', '_').replace(' ', '_').replace('/', '_')

    @staticmethod
    def _ip_without_cidr(value: str) -> str:
        if not isinstance(value, str):
            return ""
        return value.split("/")[0].strip()

    def _apply_service_runtime_compat_fields(self) -> None:
        """
        Enrich services with compatibility fields derived from runtime.

        Templates still reference legacy fields (device_ref/lxc_ref/network_ref/ip).
        This keeps docs generation stable while topology authoring moves to runtime.
        """
        l2 = self.topology.get("L2_network", {}) or {}
        l4 = self.topology.get("L4_platform", {}) or {}
        l5 = self.topology.get("L5_application", {}) or {}

        lxc_map = {
            item.get("id"): item
            for item in (l4.get("lxc", []) or [])
            if isinstance(item, dict) and item.get("id")
        }
        vm_map = {
            item.get("id"): item
            for item in (l4.get("vms", []) or [])
            if isinstance(item, dict) and item.get("id")
        }
        ip_allocations = l2.get("ip_allocations", []) or []
        alloc_by_network_device = {}
        for alloc in ip_allocations:
            if not isinstance(alloc, dict):
                continue
            network_ref = alloc.get("network_ref")
            device_ref = alloc.get("device_ref")
            ip = self._ip_without_cidr(alloc.get("ip"))
            if network_ref and device_ref and ip:
                alloc_by_network_device[(network_ref, device_ref)] = ip

        def _ip_from_runtime_target(
            runtime_type: str,
            target_ref: str,
            network_binding_ref: str,
        ) -> str:
            if runtime_type == "lxc":
                lxc = lxc_map.get(target_ref, {})
                for nic in lxc.get("networks", []) or []:
                    if not isinstance(nic, dict):
                        continue
                    if network_binding_ref and nic.get("network_ref") != network_binding_ref:
                        continue
                    ip = self._ip_without_cidr(nic.get("ip"))
                    if ip:
                        return ip
            elif runtime_type == "vm":
                vm = vm_map.get(target_ref, {})
                for nic in vm.get("networks", []) or []:
                    if not isinstance(nic, dict):
                        continue
                    if network_binding_ref and nic.get("network_ref") != network_binding_ref:
                        continue
                    ip = self._ip_without_cidr(nic.get("ip"))
                    if ip:
                        return ip
            elif runtime_type in {"docker", "baremetal"}:
                return alloc_by_network_device.get((network_binding_ref, target_ref), "")
            return ""

        services = l5.get("services", []) or []
        for service in services:
            if not isinstance(service, dict):
                continue
            runtime = service.get("runtime")
            if not isinstance(runtime, dict):
                continue

            runtime_type = runtime.get("type")
            target_ref = runtime.get("target_ref")
            network_binding_ref = runtime.get("network_binding_ref")

            if runtime_type == "lxc" and target_ref:
                service.setdefault("lxc_ref", target_ref)
                host = lxc_map.get(target_ref, {})
                if host.get("device_ref"):
                    service.setdefault("device_ref", host["device_ref"])
            elif runtime_type == "vm" and target_ref:
                service.setdefault("vm_ref", target_ref)
                host = vm_map.get(target_ref, {})
                if host.get("device_ref"):
                    service.setdefault("device_ref", host["device_ref"])
            elif runtime_type in {"docker", "baremetal"} and target_ref:
                service.setdefault("device_ref", target_ref)

            if network_binding_ref:
                service.setdefault("network_ref", network_binding_ref)
            else:
                # Fallback to host-first network when binding is omitted.
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

    def _get_resolved_networks(self):
        """Resolve L2 networks with optional network profile defaults."""
        l2 = self.topology.get('L2_network', {})
        profiles = l2.get('network_profiles', {}) or {}
        resolved = []

        for network in l2.get('networks', []) or []:
            merged = {}
            profile_ref = network.get('profile_ref')
            if profile_ref and profile_ref in profiles and isinstance(profiles[profile_ref], dict):
                merged.update(profiles[profile_ref])
            merged.update(network)
            resolved.append(merged)

        return resolved

    def build_l1_storage_views(self) -> Dict[str, Any]:
        """Build pre-resolved storage rows per device from L1 media registry + attachments."""
        l1 = self.topology.get('L1_foundation', {}) or {}
        devices = l1.get('devices', []) or []
        media_registry = l1.get('media_registry', []) if isinstance(l1.get('media_registry'), list) else []
        media_attachments = l1.get('media_attachments', []) if isinstance(l1.get('media_attachments'), list) else []

        media_by_id = {
            media.get('id'): media
            for media in media_registry
            if isinstance(media, dict) and media.get('id')
        }

        attachments_by_device_slot: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for attachment in media_attachments:
            if not isinstance(attachment, dict):
                continue
            device_ref = attachment.get('device_ref')
            slot_ref = attachment.get('slot_ref')
            if not device_ref or not slot_ref:
                continue
            attachments_by_device_slot.setdefault(device_ref, {}).setdefault(slot_ref, []).append(attachment)

        rows_by_device: Dict[str, List[Dict[str, Any]]] = {}
        for device in devices:
            if not isinstance(device, dict):
                continue
            dev_id = device.get('id')
            if not dev_id:
                continue

            specs = device.get('specs', {}) if isinstance(device.get('specs'), dict) else {}
            slots = specs.get('storage_slots', []) if isinstance(specs.get('storage_slots'), list) else []
            device_rows: List[Dict[str, Any]] = []

            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                slot_id = slot.get('id')
                slot_attachments = attachments_by_device_slot.get(dev_id, {}).get(slot_id, []) if slot_id else []
                sorted_attachments = sorted(
                    slot_attachments,
                    key=lambda item: (0 if item.get('state', 'present') == 'present' else 1, item.get('id', '')),
                )

                if not sorted_attachments:
                    device_rows.append({
                        'slot_id': slot_id,
                        'slot_bus': slot.get('bus'),
                        'slot_mount': slot.get('mount'),
                        'slot_name': slot.get('name'),
                        'attachment_id': None,
                        'attachment_state': 'empty',
                        'media': None,
                    })
                    continue

                for attachment in sorted_attachments:
                    media = media_by_id.get(attachment.get('media_ref'))
                    device_rows.append({
                        'slot_id': slot_id,
                        'slot_bus': slot.get('bus'),
                        'slot_mount': slot.get('mount'),
                        'slot_name': slot.get('name'),
                        'attachment_id': attachment.get('id'),
                        'attachment_state': attachment.get('state', 'present'),
                        'media': media,
                    })

            rows_by_device[dev_id] = device_rows

        return {
            'rows_by_device': rows_by_device,
            'media_by_id': media_by_id,
            'media_registry': media_registry,
            'media_attachments': media_attachments,
        }

    def resolve_storage_pools_for_docs(self) -> List[Dict[str, Any]]:
        """
        Resolve storage pools for docs from legacy `storage` or `storage_endpoints`.
        For storage_endpoints, enrich with inferred device/media from the L3 storage chain.
        """
        l1 = self.topology.get('L1_foundation', {}) or {}
        l3 = self.topology.get('L3_data', {}) or {}
        legacy_storage = l3.get('storage', []) or []
        if legacy_storage:
            return legacy_storage

        media_registry = {
            media.get('id'): media
            for media in (l1.get('media_registry', []) or [])
            if isinstance(media, dict) and media.get('id')
        }
        attachments = {
            attachment.get('id'): attachment
            for attachment in (l1.get('media_attachments', []) or [])
            if isinstance(attachment, dict) and attachment.get('id')
        }
        partitions = {
            item.get('id'): item
            for item in (l3.get('partitions', []) or [])
            if isinstance(item, dict) and item.get('id')
        }
        volume_groups = {
            item.get('id'): item
            for item in (l3.get('volume_groups', []) or [])
            if isinstance(item, dict) and item.get('id')
        }
        logical_volumes = {
            item.get('id'): item
            for item in (l3.get('logical_volumes', []) or [])
            if isinstance(item, dict) and item.get('id')
        }
        filesystems = {
            item.get('id'): item
            for item in (l3.get('filesystems', []) or [])
            if isinstance(item, dict) and item.get('id')
        }
        mount_points = {
            item.get('id'): item
            for item in (l3.get('mount_points', []) or [])
            if isinstance(item, dict) and item.get('id')
        }

        def _resolve_from_partition(
            partition_ref: str,
            device_ref: str | None,
            media_type: str | None,
        ) -> tuple[str | None, str | None]:
            partition = partitions.get(partition_ref, {}) if partition_ref else {}
            attachment_ref = partition.get('media_attachment_ref')
            attachment = attachments.get(attachment_ref, {}) if attachment_ref else {}
            media = media_registry.get(attachment.get('media_ref'), {}) if attachment else {}
            resolved_device = device_ref or attachment.get('device_ref')
            resolved_media = media_type or media.get('type')
            return resolved_device, resolved_media

        def _resolve_from_lv(
            lv_ref: str,
            device_ref: str | None,
            media_type: str | None,
        ) -> tuple[str | None, str | None]:
            lv = logical_volumes.get(lv_ref, {}) if lv_ref else {}
            vg = volume_groups.get(lv.get('vg_ref'), {}) if lv else {}
            for pv_ref in (vg.get('pv_refs') or []):
                device_ref, media_type = _resolve_from_partition(pv_ref, device_ref, media_type)
                if device_ref and media_type:
                    break
            return device_ref, media_type

        resolved: List[Dict[str, Any]] = []
        for endpoint in l3.get('storage_endpoints', []) or []:
            if not isinstance(endpoint, dict):
                continue
            item = copy.deepcopy(endpoint)
            device_ref = item.get('device_ref')
            media_type = item.get('media')

            mount_point = mount_points.get(item.get('mount_point_ref'), {}) if item.get('mount_point_ref') else {}
            if mount_point:
                device_ref = device_ref or mount_point.get('device_ref')
                if not item.get('path'):
                    item['path'] = mount_point.get('path')

            filesystem = filesystems.get(mount_point.get('filesystem_ref'), {}) if mount_point else {}
            if filesystem.get('partition_ref'):
                device_ref, media_type = _resolve_from_partition(
                    filesystem.get('partition_ref'),
                    device_ref,
                    media_type,
                )
            elif filesystem.get('lv_ref'):
                device_ref, media_type = _resolve_from_lv(
                    filesystem.get('lv_ref'),
                    device_ref,
                    media_type,
                )

            if item.get('lv_ref'):
                device_ref, media_type = _resolve_from_lv(item.get('lv_ref'), device_ref, media_type)
                if not item.get('path'):
                    lv = logical_volumes.get(item.get('lv_ref'), {})
                    vg = volume_groups.get(lv.get('vg_ref'), {}) if lv else {}
                    vg_name = vg.get('name') or vg.get('id')
                    lv_name = lv.get('name') or lv.get('id')
                    if vg_name and lv_name:
                        item['path'] = f"{vg_name}/{lv_name}"

            infer_from = endpoint.get('infer_from', {}) if isinstance(endpoint.get('infer_from'), dict) else {}
            attachment_ref = infer_from.get('media_attachment_ref')
            attachment = attachments.get(attachment_ref, {}) if attachment_ref else {}
            media = media_registry.get(attachment.get('media_ref'), {}) if attachment else {}
            device_ref = device_ref or attachment.get('device_ref')
            media_type = media_type or media.get('type')

            item['device_ref'] = device_ref
            item['media'] = media_type

            if not item.get('path'):
                lv_name = infer_from.get('lv_name')
                vg_name = infer_from.get('vg_name')
                if vg_name and lv_name:
                    item['path'] = f"{vg_name}/{lv_name}"
                elif lv_name:
                    item['path'] = lv_name
            resolved.append(item)

        return resolved

    def resolve_data_assets_for_docs(self) -> List[Dict[str, Any]]:
        """
        Resolve data asset placement links for docs.

        Canonical placement comes from L4 storage bindings (`storage_endpoint_ref`)
        with `data_asset_ref` linkage on rootfs/volumes.
        For docker/baremetal runtimes, fallback endpoint inference is derived from
        active host OS installation root storage endpoint on the target device.
        """
        l3 = self.topology.get('L3_data', {}) or {}
        l4 = self.topology.get('L4_platform', {}) or {}
        l5 = self.topology.get('L5_application', {}) or {}
        data_assets = l3.get('data_assets', []) or []

        placement_map: Dict[str, Dict[str, set[str]]] = {}
        host_root_endpoint_by_device: Dict[str, str] = {}

        for host_os in l4.get('host_operating_systems', []) or []:
            if not isinstance(host_os, dict):
                continue
            status = str(host_os.get('status', '')).strip().lower()
            if status and status != 'active':
                continue
            device_ref = host_os.get('device_ref')
            installation = host_os.get('installation') if isinstance(host_os.get('installation'), dict) else {}
            root_storage_ref = installation.get('root_storage_endpoint_ref')
            if isinstance(device_ref, str) and device_ref and isinstance(root_storage_ref, str) and root_storage_ref:
                host_root_endpoint_by_device.setdefault(device_ref, root_storage_ref)

        def _extract_service_mount_paths(service: Dict[str, Any]) -> List[str]:
            mount_paths: set[str] = set()

            storage = service.get('storage') if isinstance(service.get('storage'), dict) else {}
            path_single = storage.get('path')
            if isinstance(path_single, str) and path_single:
                mount_paths.add(path_single)

            path_map = storage.get('paths') if isinstance(storage.get('paths'), dict) else {}
            for value in path_map.values():
                if isinstance(value, str) and value:
                    mount_paths.add(value)

            config = service.get('config') if isinstance(service.get('config'), dict) else {}
            docker = config.get('docker') if isinstance(config.get('docker'), dict) else {}
            volumes = docker.get('volumes') if isinstance(docker.get('volumes'), list) else []
            for volume in volumes:
                if isinstance(volume, str):
                    host_path = volume.split(':', 1)[0].strip()
                    if host_path.startswith('/'):
                        mount_paths.add(host_path)
                    continue
                if isinstance(volume, dict):
                    host_path = volume.get('source') or volume.get('host_path') or volume.get('src')
                    if isinstance(host_path, str) and host_path.startswith('/'):
                        mount_paths.add(host_path)

            return sorted(mount_paths)

        def _register(
            data_asset_ref: str | None,
            storage_ref: str | None,
            runtime_ref: str | None,
            mount_path: str | None,
            source: str | None,
        ) -> None:
            if not data_asset_ref:
                return
            slot = placement_map.setdefault(
                data_asset_ref,
                {
                    'storage_endpoint_refs': set(),
                    'runtime_refs': set(),
                    'mount_paths': set(),
                    'placement_sources': set(),
                },
            )
            if storage_ref:
                slot['storage_endpoint_refs'].add(storage_ref)
            if runtime_ref:
                slot['runtime_refs'].add(runtime_ref)
            if mount_path:
                slot['mount_paths'].add(mount_path)
            if source:
                slot['placement_sources'].add(source)

        for lxc in l4.get('lxc', []) or []:
            if not isinstance(lxc, dict):
                continue
            runtime_ref = lxc.get('id')
            storage = lxc.get('storage', {}) if isinstance(lxc.get('storage'), dict) else {}

            rootfs = storage.get('rootfs', {}) if isinstance(storage.get('rootfs'), dict) else {}
            _register(
                rootfs.get('data_asset_ref'),
                rootfs.get('storage_endpoint_ref') or rootfs.get('storage_ref'),
                runtime_ref,
                '/',
                'l4-storage',
            )

            for volume in storage.get('volumes', []) or []:
                if not isinstance(volume, dict):
                    continue
                _register(
                    volume.get('data_asset_ref'),
                    volume.get('storage_endpoint_ref') or volume.get('storage_ref'),
                    runtime_ref,
                    volume.get('mount_path'),
                    'l4-storage',
                )

        for vm in l4.get('vms', []) or []:
            if not isinstance(vm, dict):
                continue
            runtime_ref = vm.get('id')
            for disk in vm.get('storage', []) or []:
                if not isinstance(disk, dict):
                    continue
                _register(
                    disk.get('data_asset_ref'),
                    disk.get('storage_endpoint_ref') or disk.get('storage_ref'),
                    runtime_ref,
                    disk.get('mount_path') or disk.get('path') or disk.get('target'),
                    'l4-storage',
                )

        for service in l5.get('services', []) or []:
            if not isinstance(service, dict):
                continue
            asset_refs = service.get('data_asset_refs') if isinstance(service.get('data_asset_refs'), list) else []
            if not asset_refs:
                continue

            runtime = service.get('runtime') if isinstance(service.get('runtime'), dict) else {}
            runtime_type = str(runtime.get('type') or '').strip().lower()
            runtime_target_ref = runtime.get('target_ref')
            runtime_ref = runtime_target_ref if isinstance(runtime_target_ref, str) and runtime_target_ref else service.get('id')
            storage_ref = runtime.get('storage_endpoint_ref') or runtime.get('storage_ref')

            if (
                not storage_ref
                and runtime_type in {'docker', 'baremetal'}
                and isinstance(runtime_target_ref, str)
                and runtime_target_ref
            ):
                storage_ref = host_root_endpoint_by_device.get(runtime_target_ref)

            mount_paths = _extract_service_mount_paths(service)
            source = 'l5-runtime-host-root' if storage_ref and runtime_type in {'docker', 'baremetal'} else 'l5-runtime'

            for asset_ref in asset_refs:
                if not isinstance(asset_ref, str) or not asset_ref:
                    continue
                if mount_paths:
                    for mount_path in mount_paths:
                        _register(asset_ref, storage_ref, runtime_ref, mount_path, source)
                else:
                    _register(asset_ref, storage_ref, runtime_ref, None, source)

        resolved_assets: List[Dict[str, Any]] = []
        for asset in data_assets:
            if not isinstance(asset, dict):
                continue
            item = copy.deepcopy(asset)
            placement = placement_map.get(item.get('id'), {})
            endpoint_refs = sorted(placement.get('storage_endpoint_refs', set()))
            runtime_refs = sorted(placement.get('runtime_refs', set()))
            mount_paths = sorted(placement.get('mount_paths', set()))
            placement_sources = sorted(placement.get('placement_sources', set()))

            item['resolved_storage_endpoint_refs'] = endpoint_refs
            item['resolved_runtime_refs'] = runtime_refs
            item['resolved_mount_paths'] = mount_paths
            item['placement_source'] = ', '.join(placement_sources) if placement_sources else 'l3-ownership'
            resolved_assets.append(item)

        return resolved_assets

    def _resolve_lxc_resources(self, lxc_containers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve effective LXC resources from inline resources or resource profiles."""
        l4 = self.topology.get('L4_platform', {}) or {}
        profile_map = {
            profile.get('id'): profile
            for profile in (l4.get('resource_profiles', []) or [])
            if isinstance(profile, dict) and profile.get('id')
        }
        resolved: List[Dict[str, Any]] = []

        for container in lxc_containers:
            if not isinstance(container, dict):
                continue
            item = copy.deepcopy(container)
            resources = item.get('resources') if isinstance(item.get('resources'), dict) else None
            if not resources:
                profile_ref = item.get('resource_profile_ref')
                profile = profile_map.get(profile_ref, {}) if profile_ref else {}
                cpu = (profile.get('cpu') or {})
                memory = (profile.get('memory') or {})
                item['resources'] = {
                    'cores': cpu.get('cores', 1),
                    'memory_mb': memory.get('mb', 512),
                    'swap_mb': memory.get('swap_mb', 0),
                }
            item.setdefault('type', item.get('platform_type', 'lxc'))
            item.setdefault('role', item.get('resource_profile_ref', 'resource-profile'))
            resolved.append(item)

        return resolved

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology, version_warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=['L0_meta', 'L1_foundation', 'L2_network', 'L4_platform'],
            )
            print(f"OK Loaded topology: {self.topology_path}")

            if version_warning:
                print(f"WARN  {version_warning}")

            # Runtime-first compatibility for templates that still read legacy service fields.
            self._apply_service_runtime_compat_fields()

            return True
        except ValueError as e:
            print(f"ERROR {e}")
            return False
        except FileNotFoundError:
            print(f"ERROR Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            print(f"ERROR YAML parse error: {e}")
            return False

    def generate_all(self) -> bool:
        """Generate all documentation files"""
        if prepare_output_directory(self.output_dir):
            print(f"CLEAN Cleaning output directory: {self.output_dir}")

        self._cleanup_legacy_docs_directories()
        print(f"DIR Created output directory: {self.output_dir}")
        self.generated_files = []
        self.generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        success = True
        success &= self.generate_network_diagram()
        success &= self.generate_ip_allocation()
        success &= self.generate_services_inventory()
        success &= self.generate_devices_inventory()
        success &= self.generate_overview()
        success &= self.diagram_generator.generate_all()
        success &= self._write_generation_artifacts()

        return success

    def _cleanup_legacy_docs_directories(self) -> None:
        """
        Remove obsolete side-by-side docs outputs when generating canonical docs.

        Legacy directories (`docs-compat`, `docs-icon-nodes`) were used during
        icon-mode migration and should not coexist with canonical `generated/docs`.
        """
        try:
            output_dir = self.output_dir.resolve()
        except OSError:
            return

        if output_dir.name != "docs" or output_dir.parent.name != "generated":
            return

        for legacy_name in ("docs-compat", "docs-icon-nodes"):
            legacy_dir = output_dir.parent / legacy_name
            if not legacy_dir.exists():
                continue
            try:
                shutil.rmtree(legacy_dir)
                print(f"CLEAN Removed legacy docs directory: {legacy_dir}")
            except OSError as e:
                print(f"WARN  Failed to remove legacy docs directory {legacy_dir}: {e}")

    def _register_generated_file(self, output_name: str) -> None:
        """Register generated documentation filename for deterministic artifacts."""
        if not output_name:
            return
        if output_name not in self.generated_files:
            self.generated_files.append(output_name)

    def _write_generation_artifacts(self) -> bool:
        """
        Write non-content generation artifacts:
        - _generated_at.txt: volatile generation timestamp.
        - _generated_files.txt: deterministic sorted list of generated docs files.
        """
        try:
            generated_at_file = self.output_dir / "_generated_at.txt"
            generated_files_file = self.output_dir / "_generated_files.txt"

            generated_at_file.write_text(f"{self.generated_at}\n", encoding="utf-8")

            files_sorted = sorted(self.generated_files)
            generated_files_file.write_text(
                "\n".join(files_sorted) + ("\n" if files_sorted else ""),
                encoding="utf-8",
            )

            print(f"OK Generated: {generated_at_file}")
            print(f"OK Generated: {generated_files_file}")
            return True
        except Exception as e:
            print(f"ERROR Error generating docs metadata artifacts: {e}")
            return False

    def _render_core_document(self, template_name: str, output_name: str, **context: Any) -> bool:
        """Render a core docs template and write it to output directory."""
        try:
            template = self.jinja_env.get_template(template_name)
            content = template.render(
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                **context,
            )
            content = self.transform_mermaid_icons_for_compat(content)
            output_file = self.output_dir / output_name
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            self._register_generated_file(output_name)
            return True
        except Exception as e:
            print(f"ERROR Error generating {output_name}: {e}")
            return False

    def generate_network_diagram(self) -> bool:
        """Generate network diagram in Mermaid format"""
        try:
            template = self.jinja_env.get_template('docs/network-diagram.md.j2')

            networks = self._get_resolved_networks()
            bridges = self.topology['L2_network'].get('bridges', [])
            trust_zones = self.topology['L2_network'].get('trust_zones', {})
            vms = self.topology['L4_platform'].get('vms', [])
            lxc = self.topology['L4_platform'].get('lxc', [])

            content = template.render(
                networks=networks,
                bridges=bridges,
                trust_zones=trust_zones,
                vms=vms,
                lxc=lxc,
                network_icons={
                    net.get('id'): self.diagram_generator._network_icon(net)
                    for net in networks
                    if isinstance(net, dict) and net.get('id')
                },
                lxc_icons={
                    item.get('id'): (
                        'mdi:docker'
                        if 'docker' in str(item.get('type', '')).lower()
                        else 'mdi:cube-outline'
                    )
                    for item in lxc
                    if isinstance(item, dict) and item.get('id')
                },
                zone_icons=self.diagram_generator.ZONE_ICON_MAP,
                use_mermaid_icons=self.mermaid_icons,
                icon_mode=self.icon_mode,
                mermaid_icon_runtime_hint=self.icon_runtime_hint(),
                mermaid_icon_pack_hint=self.diagram_generator.ICON_PACK_HINT,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
            )
            content = self.transform_mermaid_icons_for_compat(content)

            output_file = self.output_dir / "network-diagram.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            self._register_generated_file("network-diagram.md")
            return True

        except Exception as e:
            print(f"ERROR Error generating network-diagram.md: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_ip_allocation(self) -> bool:
        """Generate IP allocation table"""
        networks = self._get_resolved_networks()

        allocations = []
        for network in networks:
            for allocation in network.get('ip_allocations', []) or []:
                allocations.append({
                    'network': network['id'],
                    'cidr': network['cidr'],
                    'ip': allocation['ip'],
                    'device': allocation.get('device_ref', allocation.get('vm_ref', allocation.get('lxc_ref', 'unknown'))),
                    'interface': allocation.get('interface', '-'),
                    'description': allocation.get('description', '')
                })

        return self._render_core_document(
            "docs/ip-allocation.md.j2",
            "ip-allocation.md",
            networks=networks,
            allocations=allocations,
        )

    def generate_services_inventory(self) -> bool:
        """Generate services inventory"""
        services = self.topology.get('L5_application', {}).get('services', [])

        lxc_map = {lxc['id']: lxc for lxc in self.topology['L4_platform'].get('lxc', [])}
        vm_map = {vm['id']: vm for vm in self.topology['L4_platform'].get('vms', [])}

        enriched_services = []
        for service in services:
            enriched = service.copy()

            if 'lxc_ref' in service:
                host = lxc_map.get(service['lxc_ref'], {})
                enriched['host_name'] = host.get('name', 'unknown')
                enriched['host_type'] = 'LXC'
            elif 'vm_ref' in service:
                host = vm_map.get(service['vm_ref'], {})
                enriched['host_name'] = host.get('name', 'unknown')
                enriched['host_type'] = 'VM'
            elif 'device_ref' in service:
                enriched['host_name'] = service['device_ref']
                enriched['host_type'] = 'Device'
            else:
                enriched['host_name'] = 'unknown'
                enriched['host_type'] = 'unknown'

            enriched_services.append(enriched)

        return self._render_core_document(
            "docs/services.md.j2",
            "services.md",
            services=enriched_services,
        )

    def generate_devices_inventory(self) -> bool:
        """Generate devices inventory"""
        devices = self.topology['L1_foundation'].get('devices', [])
        vms = self.topology['L4_platform'].get('vms', [])
        host_operating_systems = self.topology['L4_platform'].get('host_operating_systems', [])
        lxc = self._resolve_lxc_resources(self.topology['L4_platform'].get('lxc', []))
        storage = self.resolve_storage_pools_for_docs()
        storage_views = self.build_l1_storage_views()

        return self._render_core_document(
            "docs/devices.md.j2",
            "devices.md",
            devices=devices,
            vms=vms,
            host_operating_systems=host_operating_systems,
            lxc=lxc,
            storage=storage,
            storage_rows_by_device=storage_views['rows_by_device'],
        )

    def generate_overview(self) -> bool:
        """Generate infrastructure overview"""
        metadata = self.topology.get('L0_meta', {}).get('metadata', {})
        devices = self.topology['L1_foundation'].get('devices', [])
        networks = self.topology['L2_network'].get('networks', [])
        vms = self.topology['L4_platform'].get('vms', [])
        lxc = self.topology['L4_platform'].get('lxc', [])
        services = self.topology.get('L5_application', {}).get('services', [])
        storage = self.resolve_storage_pools_for_docs()

        stats = {
            'total_devices': len(devices),
            'total_vms': len(vms),
            'total_lxc': len(lxc),
            'total_networks': len(networks),
            'total_services': len(services),
            'total_storage': len(storage),
        }

        return self._render_core_document(
            "docs/overview.md.j2",
            "overview.md",
            metadata=metadata,
            stats=stats,
        )

    def print_summary(self) -> None:
        """Print generation summary."""
        print("\n" + "="*70)
        print("Documentation Generation Summary")
        print("="*70)

        print(f"\nOK Generated documentation:")
        print(f"  Core:")
        print(f"    - Network diagram (Mermaid)")
        print(f"    - IP allocation table")
        print(f"    - Services inventory")
        print(f"    - Devices inventory")
        print(f"    - Infrastructure overview")
        print(f"  Visual Diagrams:")
        for item in self.diagram_generator.summary_items():
            print(f"    - {item}")
        print(f"  Navigation:")
        print(f"    - Diagrams index")
        print(f"\nOK Output directory: {self.output_dir}")
        print(f"\nFiles created:")
        for file in sorted(self.output_dir.glob("*.md")):
            print(f"  - {file.name}")

