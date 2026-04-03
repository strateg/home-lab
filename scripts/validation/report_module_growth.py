#!/usr/bin/env python3
"""Report module-level plugin growth metrics for ADR0082 governance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_plugins_count(manifest_path: Path) -> int:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return 0
    return sum(1 for row in plugins if isinstance(row, dict))


def _iter_module_manifests(repo_root: Path) -> tuple[list[Path], list[Path]]:
    class_root = repo_root / "topology" / "class-modules"
    object_root = repo_root / "topology" / "object-modules"
    class_manifests = sorted(path for path in class_root.rglob("plugins.yaml") if path.is_file())
    object_manifests = sorted(path for path in object_root.rglob("plugins.yaml") if path.is_file())
    return class_manifests, object_manifests


def _build_report(repo_root: Path, *, threshold: int) -> dict[str, Any]:
    base_manifest = repo_root / "topology-tools" / "plugins" / "plugins.yaml"
    class_manifests, object_manifests = _iter_module_manifests(repo_root)

    class_plugins = sum(_load_plugins_count(path) for path in class_manifests)
    object_plugins = sum(_load_plugins_count(path) for path in object_manifests)
    base_plugins = _load_plugins_count(base_manifest)
    module_manifests = len(class_manifests) + len(object_manifests)
    module_plugins = class_plugins + object_plugins
    total_plugins = base_plugins + module_plugins
    gate = "triggered" if module_manifests > threshold else "ok"

    return {
        "active_module_manifest_threshold": threshold,
        "active_module_manifests": module_manifests,
        "gate": gate,
        "base_plugins": base_plugins,
        "module_plugins": module_plugins,
        "total_plugins": total_plugins,
        "class_module_manifest_count": len(class_manifests),
        "object_module_manifest_count": len(object_manifests),
        "class_module_plugins": class_plugins,
        "object_module_plugins": object_plugins,
        "class_module_manifests": [str(path.relative_to(repo_root).as_posix()) for path in class_manifests],
        "object_module_manifests": [str(path.relative_to(repo_root).as_posix()) for path in object_manifests],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report module growth metrics and ADR0082 trigger status.")
    parser.add_argument(
        "--active-module-threshold",
        type=int,
        default=15,
        help="Trigger threshold for active module manifests (default: 15).",
    )
    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Exit with code 1 when active module manifests exceed threshold.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write JSON report.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = _repo_root()
    report = _build_report(repo_root, threshold=args.active_module_threshold)

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=True))
    if args.fail_on_threshold and report["gate"] == "triggered":
        print(
            "ERROR: active module manifests exceeded threshold: "
            f"{report['active_module_manifests']} > {report['active_module_manifest_threshold']}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
