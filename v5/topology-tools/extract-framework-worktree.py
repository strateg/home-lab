#!/usr/bin/env python3
"""Export framework-only worktree for ADR0076 Wave 2 bootstrap."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_output_root() -> Path:
    return _default_repo_root() / "v5-build" / "framework-extract"


def _git_revision(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return "UNKNOWN"
    value = (result.stdout or "").strip()
    return value or "UNKNOWN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract framework worktree into standalone directory.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Source monorepo root.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_default_output_root(),
        help="Destination directory for extracted framework worktree.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Copy framework tests into destination tests/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output directory when it already exists.",
    )
    return parser.parse_args()


def _copy_path(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.pyo"),
        )
        return
    shutil.copy2(source, target)


def _mapping_rows(*, include_tests: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"source": "v5/topology/framework.yaml", "target": "framework.yaml"},
        {"source": "v5/topology/class-modules", "target": "class-modules"},
        {"source": "v5/topology/object-modules", "target": "object-modules"},
        {"source": "v5/topology/layer-contract.yaml", "target": "layer-contract.yaml"},
        {"source": "v5/topology/model.lock.yaml", "target": "model.lock.yaml"},
        {"source": "v5/topology/profile-map.yaml", "target": "profile-map.yaml"},
        {"source": "v5/topology-tools", "target": "topology-tools"},
    ]
    if include_tests:
        rows.extend(
            [
                {"source": "v5/tests/plugin_api", "target": "tests/plugin_api"},
                {"source": "v5/tests/plugin_contract", "target": "tests/plugin_contract"},
                {"source": "v5/tests/plugin_integration", "target": "tests/plugin_integration"},
                {"source": "v5/tests/plugin_regression", "target": "tests/plugin_regression"},
                # conftest.py is optional because some repositories keep test fixtures self-contained.
                {"source": "v5/tests/conftest.py", "target": "tests/conftest.py", "optional": True},
            ]
        )
    return rows


def _write_manifest(
    *,
    output_root: Path,
    repo_root: Path,
    include_tests: bool,
    rows: list[dict[str, Any]],
) -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_repo_root": str(repo_root),
        "source_revision": _git_revision(repo_root),
        "include_tests": include_tests,
        "mappings": rows,
    }
    manifest_path = output_root / "extraction-manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _rewrite_framework_manifest_for_extracted_layout(output_root: Path) -> None:
    manifest_path = output_root / "framework.yaml"
    if not manifest_path.exists():
        return
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return
    distribution = payload.get("distribution")
    if not isinstance(distribution, dict):
        return
    include = distribution.get("include")
    if not isinstance(include, list):
        return

    rewritten: list[str] = []
    for item in include:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        if value.startswith("v5/topology/"):
            rewritten.append(value.removeprefix("v5/topology/"))
            continue
        if value == "v5/topology-tools" or value.startswith("v5/topology-tools/"):
            rewritten.append(value.removeprefix("v5/"))
            continue
        rewritten.append(value)
    distribution["include"] = rewritten
    manifest_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_root = args.output_root.resolve()
    include_tests = bool(args.include_tests)
    rows = _mapping_rows(include_tests=include_tests)

    if output_root.exists():
        if not args.force:
            print(f"ERROR: output directory already exists: {output_root} (use --force to overwrite)")
            return 2
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    for row in rows:
        source = (repo_root / row["source"]).resolve()
        target = (output_root / row["target"]).resolve()
        if not source.exists():
            if bool(row.get("optional")):
                continue
            print(f"ERROR: source path missing: {source}")
            return 1
        _copy_path(source, target)

    _rewrite_framework_manifest_for_extracted_layout(output_root)

    _write_manifest(
        output_root=output_root,
        repo_root=repo_root,
        include_tests=include_tests,
        rows=rows,
    )
    print(f"Framework worktree extracted to: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
