#!/usr/bin/env python3
"""
Migration assistant for ADR-0026/v5 model.

Current implementation is non-destructive and focused on reporting:
- scans legacy fields in layered topology;
- prints migration checklist grouped by layer;
- can emit JSON report for automation.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

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


def _migrate_storage_endpoints(topology: Dict[str, Any]) -> int:
    """
    Derive storage_endpoints from legacy L3 storage entries when missing.

    Returns:
        Number of storage_endpoints created.
    """
    l3 = topology.get("L3_data", {}) or {}
    legacy_storage = l3.get("storage", []) or []
    existing_endpoints = l3.get("storage_endpoints", []) or []
    existing_ids = {
        entry.get("id")
        for entry in existing_endpoints
        if isinstance(entry, dict) and entry.get("id")
    }

    created = 0
    for storage in legacy_storage:
        if not isinstance(storage, dict):
            continue
        legacy_id = storage.get("id", "")
        suffix = legacy_id.replace("storage-", "", 1) if legacy_id.startswith("storage-") else legacy_id
        endpoint_id = f"se-{suffix}" if suffix else ""
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

        existing_endpoints.append(endpoint)
        existing_ids.add(endpoint_id)
        created += 1

    if created:
        l3["storage_endpoints"] = existing_endpoints
        topology["L3_data"] = l3

    return created


def apply_migration(topology: Dict[str, Any]) -> Dict[str, int]:
    """
    Apply safe additive migration transforms.

    Legacy fields are preserved; new-model fields are added.
    """
    stats = {
        "services_runtime_added": 0,
        "lxc_resource_profiles_assigned": 0,
        "storage_endpoints_created": 0,
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

    stats["lxc_resource_profiles_assigned"] = _migrate_resource_profiles(topology)
    stats["storage_endpoints_created"] = _migrate_storage_endpoints(topology)
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
        description="Build migration checklist for topology v5 transition (non-destructive dry run)."
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

    args = parser.parse_args()

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
        stats = apply_migration(migrated)
        output_path = Path(args.output_topology)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(migrated, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        print(
            "OK Migrated topology written: "
            f"{output_path} "
            f"(services_runtime_added={stats['services_runtime_added']}, "
            f"lxc_resource_profiles_assigned={stats['lxc_resource_profiles_assigned']}, "
            f"storage_endpoints_created={stats['storage_endpoints_created']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
