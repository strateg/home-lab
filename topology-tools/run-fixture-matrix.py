#!/usr/bin/env python3
"""Run validation/generator matrix for legacy, mixed, and new topology fixtures."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class FixtureSpec:
    name: str
    mode: str
    expect_migration_items: bool


DEFAULT_FIXTURES: Dict[str, FixtureSpec] = {
    "legacy-only": FixtureSpec(name="legacy-only", mode="compat", expect_migration_items=True),
    "mixed": FixtureSpec(name="mixed", mode="compat", expect_migration_items=True),
    "new-only": FixtureSpec(name="new-only", mode="strict", expect_migration_items=False),
}


def run_command(args: List[str], *, cwd: Path, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    rendered = " ".join(args)
    print(f"RUN  {rendered}")
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=capture_output,
        check=True,
    )


def migration_item_count(
    *,
    python_bin: str,
    project_root: Path,
    tools_dir: Path,
    topology_path: Path,
) -> int:
    result = run_command(
        [python_bin, str(tools_dir / "migrate-to-v5.py"), "--topology", str(topology_path), "--json"],
        cwd=project_root,
        capture_output=True,
    )
    report = json.loads(result.stdout)
    if not isinstance(report, dict):
        raise ValueError("Migration report is not a JSON object")
    return sum(len(items) for items in report.values() if isinstance(items, list))


def _normalized_markdown(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith("**Date**: "):
            continue
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def compare_directories(expected: Path, actual: Path, *, normalize_markdown_dates: bool = False) -> List[str]:
    issues: List[str] = []
    if not expected.is_dir():
        issues.append(f"Missing canonical directory: {expected}")
        return issues
    if not actual.is_dir():
        issues.append(f"Missing generated directory: {actual}")
        return issues

    expected_files = {path.relative_to(expected) for path in expected.rglob("*") if path.is_file()}
    actual_files = {path.relative_to(actual) for path in actual.rglob("*") if path.is_file()}

    for missing in sorted(expected_files - actual_files):
        issues.append(f"Missing file: {missing}")
    for unexpected in sorted(actual_files - expected_files):
        issues.append(f"Unexpected file: {unexpected}")

    for rel_path in sorted(expected_files & actual_files):
        expected_path = expected / rel_path
        actual_path = actual / rel_path
        if normalize_markdown_dates and expected_path.suffix.lower() == ".md":
            if _normalized_markdown(expected_path) != _normalized_markdown(actual_path):
                issues.append(f"Content differs: {rel_path}")
            continue
        if expected_path.read_bytes() != actual_path.read_bytes():
            issues.append(f"Content differs: {rel_path}")

    return issues


def selected_specs(raw: str | None) -> List[FixtureSpec]:
    if not raw:
        return list(DEFAULT_FIXTURES.values())
    names = [item.strip() for item in raw.split(",") if item.strip()]
    missing = [name for name in names if name not in DEFAULT_FIXTURES]
    if missing:
        raise ValueError(f"Unknown fixture(s): {', '.join(missing)}")
    return [DEFAULT_FIXTURES[name] for name in names]


def generator_jobs(output_root: Path) -> Iterable[tuple[str, Path]]:
    return (
        ("generate-terraform-proxmox.py", output_root / "terraform"),
        ("generate-terraform-mikrotik.py", output_root / "terraform-mikrotik"),
        ("generate-ansible-inventory.py", output_root / "ansible" / "inventory" / "production"),
        ("generate-docs.py", output_root / "docs"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixture validation/generator matrix.")
    parser.add_argument(
        "--fixtures-root",
        default="topology-tools/fixtures",
        help="Directory with fixture topology snapshots",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root directory",
    )
    parser.add_argument(
        "--tmp-root",
        help="Temporary output root (defaults to auto-cleaned temp dir)",
    )
    parser.add_argument(
        "--fixtures",
        help="Comma-separated fixture list (default: legacy-only,mixed,new-only)",
    )
    parser.add_argument(
        "--skip-generators",
        action="store_true",
        help="Skip generator execution and compare checks",
    )
    parser.add_argument(
        "--skip-canonical-compare",
        action="store_true",
        help="Skip new-only comparison against repository generated/ snapshots",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    fixtures_root = (project_root / args.fixtures_root).resolve()
    tools_dir = project_root / "topology-tools"
    python_bin = sys.executable

    try:
        specs = selected_specs(args.fixtures)
    except ValueError as exc:
        print(f"ERROR {exc}")
        return 2

    if args.tmp_root:
        tmp_root = (project_root / args.tmp_root).resolve()
        tmp_root.mkdir(parents=True, exist_ok=True)
        temp_ctx = None
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="fixture-matrix-")
        tmp_root = Path(temp_ctx.name).resolve()

    print("=" * 70)
    print("Fixture Matrix")
    print("=" * 70)
    print(f"Fixtures root: {fixtures_root}")
    print(f"Temp output root: {tmp_root}")
    print()

    try:
        for spec in specs:
            fixture_dir = fixtures_root / spec.name
            topology_path = fixture_dir / "topology.yaml"
            if not topology_path.exists():
                print(f"ERROR Missing fixture topology: {topology_path}")
                return 2

            print("-" * 70)
            print(f"Fixture: {spec.name} (mode={spec.mode})")
            print("-" * 70)

            validate_args = [
                python_bin,
                str(tools_dir / "validate-topology.py"),
                "--topology",
                str(topology_path),
                "--no-topology-cache",
                "--strict" if spec.mode == "strict" else "--compat",
            ]
            run_command(validate_args, cwd=project_root)

            item_count = migration_item_count(
                python_bin=python_bin,
                project_root=project_root,
                tools_dir=tools_dir,
                topology_path=topology_path,
            )
            print(f"INFO migration items: {item_count}")
            if spec.expect_migration_items and item_count == 0:
                print(f"ERROR Fixture '{spec.name}' expected migration items, got 0")
                return 1
            if not spec.expect_migration_items and item_count > 0:
                print(f"ERROR Fixture '{spec.name}' expected 0 migration items, got {item_count}")
                return 1

            if args.skip_generators:
                continue

            output_root = tmp_root / spec.name
            for script_name, output_dir in generator_jobs(output_root):
                run_command(
                    [
                        python_bin,
                        str(tools_dir / script_name),
                        "--topology",
                        str(topology_path),
                        "--output",
                        str(output_dir),
                    ],
                    cwd=project_root,
                )

            if spec.name == "new-only" and not args.skip_canonical_compare:
                checks = (
                    (project_root / "generated" / "terraform", output_root / "terraform", False),
                    (project_root / "generated" / "terraform-mikrotik", output_root / "terraform-mikrotik", False),
                    (
                        project_root / "generated" / "ansible" / "inventory" / "production",
                        output_root / "ansible" / "inventory" / "production",
                        False,
                    ),
                    (project_root / "generated" / "docs", output_root / "docs", True),
                )
                for expected_dir, actual_dir, normalize_dates in checks:
                    issues = compare_directories(
                        expected_dir,
                        actual_dir,
                        normalize_markdown_dates=normalize_dates,
                    )
                    if issues:
                        print(f"ERROR Snapshot mismatch for {expected_dir}")
                        for issue in issues:
                            print(f"  - {issue}")
                        return 1

        print()
        print("OK Fixture matrix passed")
        return 0
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
