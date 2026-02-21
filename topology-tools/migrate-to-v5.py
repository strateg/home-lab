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
from pathlib import Path
from typing import Any, Dict, List

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
