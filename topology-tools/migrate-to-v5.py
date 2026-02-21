#!/usr/bin/env python3
"""
Migration assistant for ADR-0026/v5 model.

Supports two modes:
- report-only (default): scans legacy fields and prints migration checklist;
- apply mode: adds v5-compatible fields and can optionally remove migrated legacy fields.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from scripts.generators.common import load_topology_cached


def build_migration_report(topology: Dict[str, Any]) -> Dict[str, List[str]]:
    """Build grouped migration report entries."""
    l3 = topology.get("L3_data", {}) or {}
    l4 = topology.get("L4_platform", {}) or {}
    l5 = topology.get("L5_application", {}) or {}

    report: Dict[str, List[str]] = {
        "L3_data": [],
        "L4_platform": [],
        "L5_application": [],
    }

    storage_entries = len(l3.get("storage", []) or [])
    if storage_entries:
        report["L3_data"].append(
            f"storage: {storage_entries} entr{'y' if storage_entries == 1 else 'ies'} -> migrate to storage_endpoints (+ chain entities)"
        )

    for idx, asset in enumerate(l3.get("data_assets", []) or []):
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("id", f"index-{idx}")
        placement_fields = [
            key
            for key in ("storage_ref", "storage_endpoint_ref", "mount_point_ref", "path")
            if asset.get(key)
        ]
        if placement_fields:
            report["L3_data"].append(
                f"data_assets[{asset_id}]: placement fields {placement_fields} -> move placement to L4 storage.volumes"
            )

    for idx, lxc in enumerate(l4.get("lxc", []) or []):
        if not isinstance(lxc, dict):
            continue
        lxc_id = lxc.get("id", f"index-{idx}")
        if lxc.get("type"):
            report["L4_platform"].append(
                f"lxc[{lxc_id}].type -> replace with platform_type + L5 service semantics"
            )
        if lxc.get("role"):
            report["L4_platform"].append(
                f"lxc[{lxc_id}].role -> replace with resource_profile_ref + L5 service semantics"
            )
        if lxc.get("resources"):
            report["L4_platform"].append(
                f"lxc[{lxc_id}].resources -> migrate to resource_profiles + resource_profile_ref"
            )
        ansible_vars = ((lxc.get("ansible") or {}).get("vars") or {})
        if isinstance(ansible_vars, dict) and ansible_vars:
            report["L4_platform"].append(
                f"lxc[{lxc_id}].ansible.vars -> move app config to L5 services[].config"
            )

    for idx, service in enumerate(l5.get("services", []) or []):
        if not isinstance(service, dict):
            continue
        svc_id = service.get("id", f"index-{idx}")
        if service.get("ip"):
            report["L5_application"].append(
                f"services[{svc_id}].ip -> derive from runtime target + network_binding_ref"
            )
        legacy_refs = [ref for ref in ("device_ref", "vm_ref", "lxc_ref", "network_ref") if service.get(ref)]
        if legacy_refs:
            report["L5_application"].append(
                f"services[{svc_id}] legacy refs {legacy_refs} -> migrate to runtime.*"
            )
        if not service.get("runtime"):
            report["L5_application"].append(
                f"services[{svc_id}] missing runtime -> add runtime.type + runtime.target_ref"
            )

    ext_services = len(l5.get("external_services", []) or [])
    if ext_services:
        report["L5_application"].append(
            f"external_services: {ext_services} entr{'y' if ext_services == 1 else 'ies'} -> fold into services[].runtime.type=docker"
        )

    return report


def report_has_items(report: Dict[str, List[str]]) -> bool:
    return any(items for items in report.values())


def _infer_service_runtime(service: Dict[str, Any]) -> Dict[str, Any]:
    """Infer runtime block from legacy service fields."""
    runtime: Dict[str, Any] = {}

    if service.get("lxc_ref"):
        runtime["type"] = "lxc"
        runtime["target_ref"] = service["lxc_ref"]
    elif service.get("vm_ref"):
        runtime["type"] = "vm"
        runtime["target_ref"] = service["vm_ref"]
    elif service.get("device_ref"):
        runtime["type"] = "docker" if service.get("container") else "baremetal"
        runtime["target_ref"] = service["device_ref"]
    else:
        return {}

    if service.get("network_ref"):
        runtime["network_binding_ref"] = service["network_ref"]
    if service.get("container_image"):
        runtime["image"] = service["container_image"]

    return runtime


def _legacy_storage_to_endpoint_id(storage_ref: str) -> str:
    if not storage_ref:
        return ""
    suffix = storage_ref.replace("storage-", "", 1) if storage_ref.startswith("storage-") else storage_ref
    return f"se-{suffix}" if suffix else ""


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _guess_service_type(name: str) -> str:
    token = _normalize_token(name)
    for key, value in {
        "nextcloud": "web-application",
        "jellyfin": "media-server",
        "prometheus": "monitoring",
        "alertmanager": "alerting",
        "loki": "logging",
        "grafana": "visualization",
        "homeassistant": "home-automation",
        "postgres": "database",
        "postgresql": "database",
        "redis": "cache",
        "dns": "dns",
    }.items():
        if key in token:
            return value
    return "web-application"


def _service_aliases(service: Dict[str, Any]) -> Set[str]:
    aliases: Set[str] = set()
    service_id = service.get("id")
    service_name = service.get("name")
    for value in (service_id, service_name):
        if isinstance(value, str):
            token = _normalize_token(value)
            if token:
                aliases.add(token)
    if isinstance(service_id, str) and service_id.startswith("svc-"):
        token = _normalize_token(service_id[4:])
        if token:
            aliases.add(token)
    return aliases


def _migrate_lxc_platform_type(topology: Dict[str, Any]) -> int:
    """Backfill platform_type for LXC entries that only have legacy type."""
    l4 = topology.get("L4_platform", {}) or {}
    updated = 0

    for lxc in l4.get("lxc", []) or []:
        if not isinstance(lxc, dict):
            continue
        if lxc.get("platform_type"):
            continue
        if lxc.get("type"):
            # Conservative default for migration; can be refined manually later.
            lxc["platform_type"] = "lxc-unprivileged"
            updated += 1

    return updated


def _migrate_storage_refs_to_storage_endpoints(topology: Dict[str, Any]) -> int:
    """Populate storage_endpoint_ref from legacy storage_ref where possible."""
    l3 = topology.get("L3_data", {}) or {}
    l4 = topology.get("L4_platform", {}) or {}
    endpoint_ids = {
        endpoint.get("id")
        for endpoint in l3.get("storage_endpoints", []) or []
        if isinstance(endpoint, dict) and endpoint.get("id")
    }
    updated = 0

    def set_endpoint_ref(entry: Dict[str, Any]) -> int:
        if not isinstance(entry, dict):
            return 0
        if entry.get("storage_endpoint_ref"):
            return 0
        storage_ref = entry.get("storage_ref")
        if not isinstance(storage_ref, str):
            return 0
        endpoint_ref = _legacy_storage_to_endpoint_id(storage_ref)
        if not endpoint_ref or endpoint_ref not in endpoint_ids:
            return 0
        entry["storage_endpoint_ref"] = endpoint_ref
        return 1

    for lxc in l4.get("lxc", []) or []:
        if not isinstance(lxc, dict):
            continue
        storage = lxc.get("storage") or {}
        rootfs = storage.get("rootfs") or {}
        updated += set_endpoint_ref(rootfs)
        for volume in storage.get("volumes", []) or []:
            if isinstance(volume, dict):
                updated += set_endpoint_ref(volume)

    for vm in l4.get("vms", []) or []:
        if not isinstance(vm, dict):
            continue
        for disk in vm.get("disks", []) or []:
            if isinstance(disk, dict):
                updated += set_endpoint_ref(disk)

    templates = l4.get("templates", {}) or {}
    for template in templates.get("lxc", []) or []:
        if isinstance(template, dict):
            updated += set_endpoint_ref(template)
    for template in templates.get("vms", []) or []:
        if isinstance(template, dict):
            updated += set_endpoint_ref(template)

    return updated


def _migrate_external_services(topology: Dict[str, Any]) -> Dict[str, int]:
    """Map external_services docker definitions into services runtime/config fields."""
    l5 = topology.get("L5_application", {}) or {}
    services = l5.get("services", []) or []
    alias_to_index: Dict[str, int] = {}

    for index, service in enumerate(services):
        if not isinstance(service, dict):
            continue
        for alias in _service_aliases(service):
            alias_to_index.setdefault(alias, index)

    stats = {
        "external_docker_services_mapped": 0,
        "external_docker_services_created": 0,
        "external_docker_services_pending": 0,
    }

    for ext_entry in l5.get("external_services", []) or []:
        if not isinstance(ext_entry, dict):
            continue
        device_ref = ext_entry.get("device_ref")
        host_ip = ext_entry.get("ip")
        docker_services = ext_entry.get("docker_services", []) or []

        for docker_service in docker_services:
            if not isinstance(docker_service, dict):
                continue
            docker_name = docker_service.get("name")
            alias = _normalize_token(docker_name or "")
            if not alias:
                stats["external_docker_services_pending"] += 1
                continue

            index = alias_to_index.get(alias)
            if index is None:
                if not device_ref:
                    stats["external_docker_services_pending"] += 1
                    continue
                base_slug = _slugify(docker_name or "docker-service")
                candidate_id = f"svc-{base_slug or 'docker-service'}"
                used_ids = {
                    service.get("id")
                    for service in services
                    if isinstance(service, dict) and service.get("id")
                }
                suffix = 1
                while candidate_id in used_ids:
                    suffix += 1
                    candidate_id = f"svc-{base_slug}-{suffix}"
                created_service = {
                    "id": candidate_id,
                    "name": docker_name or candidate_id,
                    "type": _guess_service_type(docker_name or candidate_id),
                    "runtime": {
                        "type": "docker",
                        "target_ref": device_ref,
                    },
                    "container": True,
                }
                if docker_service.get("image"):
                    created_service["runtime"]["image"] = docker_service["image"]
                    created_service["container_image"] = docker_service["image"]
                if docker_service.get("optional"):
                    created_service["optional"] = docker_service["optional"]
                if docker_service.get("note"):
                    created_service["description"] = str(docker_service["note"])
                services.append(created_service)
                index = len(services) - 1
                for service_alias in _service_aliases(created_service):
                    alias_to_index.setdefault(service_alias, index)
                alias_to_index.setdefault(alias, index)
                stats["external_docker_services_created"] += 1

            service = services[index]
            if not isinstance(service, dict):
                stats["external_docker_services_pending"] += 1
                continue

            runtime = service.get("runtime")
            if not isinstance(runtime, dict):
                runtime = {}
                service["runtime"] = runtime
            runtime.setdefault("type", "docker")
            if runtime.get("type") != "docker":
                stats["external_docker_services_pending"] += 1
                continue
            if device_ref:
                runtime.setdefault("target_ref", device_ref)
            if not runtime.get("target_ref"):
                stats["external_docker_services_pending"] += 1
                continue
            if docker_service.get("image"):
                runtime.setdefault("image", docker_service["image"])

            config = service.get("config")
            if not isinstance(config, dict):
                config = {}
                service["config"] = config
            docker_config = config.get("docker")
            if not isinstance(docker_config, dict):
                docker_config = {}
                config["docker"] = docker_config
            for key in ("ports", "volumes", "environment", "devices", "depends_on", "note"):
                if key in docker_service and key not in docker_config:
                    docker_config[key] = docker_service[key]
            if host_ip and "host_ip" not in docker_config:
                docker_config["host_ip"] = host_ip

            stats["external_docker_services_mapped"] += 1

    l5["services"] = services
    topology["L5_application"] = l5
    return stats


def _migrate_resource_profiles(topology: Dict[str, Any]) -> int:
    """
    Convert inline LXC resources into reusable resource profiles.

    Returns:
        Number of LXC entries updated with resource_profile_ref.
    """
    l4 = topology.get("L4_platform", {}) or {}
    lxc_list = l4.get("lxc", []) or []
    existing_profiles = l4.get("resource_profiles", []) or []
    profile_keys: Dict[str, str] = {}

    for profile in existing_profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = profile.get("id")
        cpu = (profile.get("cpu") or {}).get("cores")
        memory = (profile.get("memory") or {}).get("mb")
        swap = (profile.get("memory") or {}).get("swap_mb")
        if profile_id:
            profile_keys[f"{cpu}:{memory}:{swap}"] = profile_id

    created_profiles: List[Dict[str, Any]] = []
    updated = 0
    next_idx = 1

    def new_profile_id() -> str:
        nonlocal next_idx
        while True:
            candidate = f"profile-migrated-{next_idx:02d}"
            next_idx += 1
            if all((p.get("id") != candidate) for p in existing_profiles + created_profiles):
                return candidate

    for lxc in lxc_list:
        if not isinstance(lxc, dict):
            continue
        if lxc.get("resource_profile_ref"):
            continue
        resources = lxc.get("resources")
        if not isinstance(resources, dict):
            continue

        key = f"{resources.get('cores')}:{resources.get('memory_mb')}:{resources.get('swap_mb')}"
        profile_id = profile_keys.get(key)
        if not profile_id:
            profile_id = new_profile_id()
            profile_keys[key] = profile_id
            created_profiles.append(
                {
                    "id": profile_id,
                    "name": f"Migrated profile ({resources.get('cores')}c/{resources.get('memory_mb')}MB)",
                    "cpu": {"cores": resources.get("cores")},
                    "memory": {
                        "mb": resources.get("memory_mb"),
                        "swap_mb": resources.get("swap_mb", 0),
                    },
                }
            )

        lxc["resource_profile_ref"] = profile_id
        updated += 1

    if created_profiles:
        l4.setdefault("resource_profiles", [])
        l4["resource_profiles"].extend(created_profiles)
        topology["L4_platform"] = l4

    return updated


def _service_targets_lxc(service: Dict[str, Any], lxc_id: str) -> bool:
    """Check whether service targets a given LXC via runtime or legacy field."""
    runtime = service.get("runtime") or {}
    if isinstance(runtime, dict):
        if runtime.get("type") == "lxc" and runtime.get("target_ref") == lxc_id:
            return True
    return service.get("lxc_ref") == lxc_id


def _migrate_lxc_ansible_vars_to_service_config(topology: Dict[str, Any]) -> int:
    """
    Move LXC ansible.vars into related services[].config when possible.

    Returns:
        Number of LXC entries with vars migrated.
    """
    l4 = topology.get("L4_platform", {}) or {}
    l5 = topology.get("L5_application", {}) or {}
    services = l5.get("services", []) or []
    migrated_count = 0

    for lxc in l4.get("lxc", []) or []:
        if not isinstance(lxc, dict):
            continue
        lxc_id = lxc.get("id")
        if not lxc_id:
            continue

        ansible_block = lxc.get("ansible")
        if not isinstance(ansible_block, dict):
            continue
        ansible_vars = ansible_block.get("vars")
        if not isinstance(ansible_vars, dict) or not ansible_vars:
            continue

        target_services = [
            service
            for service in services
            if isinstance(service, dict) and _service_targets_lxc(service, lxc_id)
        ]
        if not target_services:
            continue

        for service in target_services:
            config = service.get("config")
            if not isinstance(config, dict):
                config = {}
                service["config"] = config
            for key, value in ansible_vars.items():
                config.setdefault(key, value)

        # Remove migrated app vars from LXC after merge.
        ansible_block.pop("vars", None)
        if not ansible_block:
            lxc.pop("ansible", None)
        migrated_count += 1

    return migrated_count


def _migrate_storage_endpoints(topology: Dict[str, Any]) -> int:
    """
    Derive storage_endpoints from legacy L3 storage entries when missing.

    Returns:
        Number of storage_endpoints created.
    """
    l1 = topology.get("L1_foundation", {}) or {}
    l3 = topology.get("L3_data", {}) or {}
    legacy_storage = l3.get("storage", []) or []
    existing_endpoints = l3.get("storage_endpoints", []) or []
    existing_ids = {
        entry.get("id")
        for entry in existing_endpoints
        if isinstance(entry, dict) and entry.get("id")
    }
    attachment_by_device_media = {}
    for attachment in l1.get("media_attachments", []) or []:
        if not isinstance(attachment, dict):
            continue
        key = (attachment.get("device_ref"), attachment.get("media_ref"))
        attachment_id = attachment.get("id")
        if key[0] and key[1] and attachment_id:
            attachment_by_device_media[key] = attachment_id

    created = 0
    for storage in legacy_storage:
        if not isinstance(storage, dict):
            continue
        legacy_id = storage.get("id", "")
        endpoint_id = _legacy_storage_to_endpoint_id(legacy_id)
        if not endpoint_id or endpoint_id in existing_ids:
            continue

        endpoint: Dict[str, Any] = {
            "id": endpoint_id,
            "name": storage.get("name", endpoint_id),
            "platform": "proxmox",
            "type": storage.get("type", "dir"),
            "content": storage.get("content", []),
            "shared": storage.get("shared", False),
            "description": f"Migrated from L3_data.storage '{legacy_id}'",
        }
        if storage.get("path"):
            endpoint["path"] = storage.get("path")
        if storage.get("type") == "lvmthin":
            infer_from = {}
            attachment_ref = attachment_by_device_media.get((storage.get("device_ref"), storage.get("disk_ref")))
            if attachment_ref:
                infer_from["media_attachment_ref"] = attachment_ref
            if storage.get("vgname"):
                infer_from["vg_name"] = storage.get("vgname")
            if storage.get("thinpool"):
                infer_from["lv_name"] = storage.get("thinpool")
            if infer_from:
                endpoint["infer_from"] = infer_from

        existing_endpoints.append(endpoint)
        existing_ids.add(endpoint_id)
        created += 1

    if created:
        l3["storage_endpoints"] = existing_endpoints
        topology["L3_data"] = l3

    return created


def _drop_legacy_fields(topology: Dict[str, Any], *, external_services_ready: bool = False) -> Dict[str, int]:
    """Drop legacy fields only when replacement fields are present."""
    stats = {
        "l3_storage_removed": 0,
        "l3_data_asset_placement_removed": 0,
        "l3_data_asset_placement_pending": 0,
        "l4_lxc_legacy_removed": 0,
        "l4_lxc_legacy_pending": 0,
        "l4_storage_ref_legacy_removed": 0,
        "l4_storage_ref_legacy_pending": 0,
        "l5_service_legacy_removed": 0,
        "l5_service_legacy_pending": 0,
        "l5_external_services_removed": 0,
        "l5_external_services_pending": 0,
    }

    l3 = topology.get("L3_data", {}) or {}
    l4 = topology.get("L4_platform", {}) or {}
    l5 = topology.get("L5_application", {}) or {}

    def _has_l4_data_asset_binding(asset_id: str) -> bool:
        for vm in l4.get("vms", []) or []:
            if not isinstance(vm, dict):
                continue
            for volume in ((vm.get("storage") or {}).get("volumes") or []):
                if isinstance(volume, dict) and volume.get("data_asset_ref") == asset_id:
                    return True
        for lxc in l4.get("lxc", []) or []:
            if not isinstance(lxc, dict):
                continue
            for volume in ((lxc.get("storage") or {}).get("volumes") or []):
                if isinstance(volume, dict) and volume.get("data_asset_ref") == asset_id:
                    return True
        return False

    def _remove_storage_ref(entry: Dict[str, Any]) -> bool:
        if not isinstance(entry, dict):
            return False
        if "storage_ref" in entry and entry.get("storage_endpoint_ref"):
            entry.pop("storage_ref", None)
            return True
        return False

    if l3.get("storage_endpoints") and l3.get("storage"):
        stats["l3_storage_removed"] = len(l3.get("storage", []) or [])
        l3.pop("storage", None)

    for asset in l3.get("data_assets", []) or []:
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("id")
        placement_keys = [key for key in ("storage_ref", "storage_endpoint_ref", "mount_point_ref", "path") if key in asset]
        if not placement_keys:
            continue
        if asset_id and _has_l4_data_asset_binding(asset_id):
            for key in placement_keys:
                asset.pop(key, None)
            stats["l3_data_asset_placement_removed"] += 1
        else:
            stats["l3_data_asset_placement_pending"] += 1

    for lxc in l4.get("lxc", []) or []:
        if not isinstance(lxc, dict):
            continue
        removed_any = False
        removable_keys: List[str] = []

        if "resources" in lxc and lxc.get("resource_profile_ref"):
            removable_keys.append("resources")
        if "type" in lxc and lxc.get("platform_type"):
            removable_keys.append("type")
        if "role" in lxc and lxc.get("resource_profile_ref"):
            removable_keys.append("role")

        for key in removable_keys:
            if key in lxc:
                lxc.pop(key, None)
                removed_any = True
        if removed_any:
            stats["l4_lxc_legacy_removed"] += 1
        if any(key in lxc for key in ("type", "role", "resources")):
            stats["l4_lxc_legacy_pending"] += 1

        storage = lxc.get("storage") or {}
        rootfs = storage.get("rootfs") or {}
        if _remove_storage_ref(rootfs):
            stats["l4_storage_ref_legacy_removed"] += 1
        elif "storage_ref" in rootfs:
            stats["l4_storage_ref_legacy_pending"] += 1

        for volume in storage.get("volumes", []) or []:
            if not isinstance(volume, dict):
                continue
            if _remove_storage_ref(volume):
                stats["l4_storage_ref_legacy_removed"] += 1
            elif "storage_ref" in volume:
                stats["l4_storage_ref_legacy_pending"] += 1

    for vm in l4.get("vms", []) or []:
        if not isinstance(vm, dict):
            continue
        for disk in vm.get("disks", []) or []:
            if not isinstance(disk, dict):
                continue
            if _remove_storage_ref(disk):
                stats["l4_storage_ref_legacy_removed"] += 1
            elif "storage_ref" in disk:
                stats["l4_storage_ref_legacy_pending"] += 1

    templates = l4.get("templates", {}) or {}
    for template in templates.get("lxc", []) or []:
        if not isinstance(template, dict):
            continue
        if _remove_storage_ref(template):
            stats["l4_storage_ref_legacy_removed"] += 1
        elif "storage_ref" in template:
            stats["l4_storage_ref_legacy_pending"] += 1
    for template in templates.get("vms", []) or []:
        if not isinstance(template, dict):
            continue
        if _remove_storage_ref(template):
            stats["l4_storage_ref_legacy_removed"] += 1
        elif "storage_ref" in template:
            stats["l4_storage_ref_legacy_pending"] += 1

    for service in l5.get("services", []) or []:
        if not isinstance(service, dict):
            continue
        removed_any = False
        runtime = service.get("runtime")
        if isinstance(runtime, dict) and runtime.get("type") and runtime.get("target_ref"):
            for key in ("device_ref", "vm_ref", "lxc_ref", "network_ref"):
                if key in service:
                    service.pop(key, None)
                    removed_any = True
            if "ip" in service and runtime.get("network_binding_ref"):
                service.pop("ip", None)
                removed_any = True
        if removed_any:
            stats["l5_service_legacy_removed"] += 1
        if any(key in service for key in ("device_ref", "vm_ref", "lxc_ref", "network_ref", "ip")):
            stats["l5_service_legacy_pending"] += 1

    if l5.get("external_services"):
        if external_services_ready:
            stats["l5_external_services_removed"] = len(l5.get("external_services", []) or [])
            l5.pop("external_services", None)
        else:
            stats["l5_external_services_pending"] = len(l5.get("external_services", []) or [])

    topology["L3_data"] = l3
    topology["L4_platform"] = l4
    topology["L5_application"] = l5
    return stats


def apply_migration(topology: Dict[str, Any], *, drop_legacy: bool = False) -> Dict[str, int]:
    """
    Apply safe additive migration transforms.

    By default legacy fields are preserved; when drop_legacy=True, migrated legacy
    fields are removed only when replacement data is available.
    """
    stats = {
        "services_runtime_added": 0,
        "lxc_platform_type_defaulted": 0,
        "lxc_resource_profiles_assigned": 0,
        "lxc_ansible_vars_migrated": 0,
        "storage_endpoints_created": 0,
        "storage_endpoint_refs_added": 0,
        "external_docker_services_mapped": 0,
        "external_docker_services_created": 0,
        "external_docker_services_pending": 0,
    }

    l5 = topology.get("L5_application", {}) or {}
    services = l5.get("services", []) or []
    for service in services:
        if not isinstance(service, dict):
            continue
        if service.get("runtime"):
            continue
        runtime = _infer_service_runtime(service)
        if runtime:
            service["runtime"] = runtime
            stats["services_runtime_added"] += 1

    stats["storage_endpoints_created"] = _migrate_storage_endpoints(topology)
    stats["storage_endpoint_refs_added"] = _migrate_storage_refs_to_storage_endpoints(topology)
    stats["lxc_platform_type_defaulted"] = _migrate_lxc_platform_type(topology)
    stats["lxc_resource_profiles_assigned"] = _migrate_resource_profiles(topology)
    stats["lxc_ansible_vars_migrated"] = _migrate_lxc_ansible_vars_to_service_config(topology)
    stats.update(_migrate_external_services(topology))
    if drop_legacy:
        stats.update(
            _drop_legacy_fields(
                topology,
                external_services_ready=stats["external_docker_services_pending"] == 0,
            )
        )
    return stats


def print_report(report: Dict[str, List[str]]) -> None:
    print("=" * 70)
    print("Migration Assistant (ADR-0026 -> v5 model)")
    print("=" * 70)
    print()

    if not report_has_items(report):
        print("OK No legacy migration items detected.")
        return

    print("Legacy fields requiring migration:")
    for section in ("L3_data", "L4_platform", "L5_application"):
        items = report.get(section, [])
        if not items:
            continue
        print(f"\n[{section}]")
        for item in items:
            print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build migration checklist and optional transforms for topology v5 transition."
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file (default: topology.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output migration report as JSON",
    )
    parser.add_argument(
        "--output",
        help="Write report to file (stdout if omitted)",
    )
    parser.add_argument(
        "--fail-on-items",
        action="store_true",
        help="Exit with code 1 if migration items are detected",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply additive migration transforms and write resulting topology YAML",
    )
    parser.add_argument(
        "--output-topology",
        help="Output file path for migrated topology YAML (required with --apply)",
    )
    parser.add_argument(
        "--drop-legacy",
        action="store_true",
        help="With --apply: remove legacy fields after additive migration transforms",
    )

    args = parser.parse_args()
    if args.drop_legacy and not args.apply:
        print("ERROR --drop-legacy requires --apply")
        return 2

    topology_path = Path(args.topology)
    try:
        topology = load_topology_cached(topology_path)
    except FileNotFoundError:
        print(f"ERROR Topology file not found: {topology_path}")
        return 2
    except Exception as exc:  # pragma: no cover - defensive path
        print(f"ERROR Failed to load topology: {exc}")
        return 2

    report = build_migration_report(topology)

    if args.json:
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        # Keep text rendering in stdout-friendly form.
        from io import StringIO

        buffer = StringIO()
        original_stdout = sys.stdout
        try:
            sys.stdout = buffer
            print_report(report)
        finally:
            sys.stdout = original_stdout
        rendered = buffer.getvalue().rstrip() + "\n"

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"OK Migration report written: {args.output}")
    else:
        print(rendered, end="")

    if args.fail_on_items and report_has_items(report):
        return 1

    if args.apply:
        if not args.output_topology:
            print("ERROR --output-topology is required when using --apply")
            return 2
        migrated = deepcopy(topology)
        stats = apply_migration(migrated, drop_legacy=args.drop_legacy)
        output_path = Path(args.output_topology)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(migrated, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        stats_rendered = ", ".join(f"{key}={value}" for key, value in stats.items())
        print(f"OK Migrated topology written: {output_path} ({stats_rendered}, drop_legacy={args.drop_legacy})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
