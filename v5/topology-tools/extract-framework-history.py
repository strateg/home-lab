#!/usr/bin/env python3
"""Extract framework repository with preserved git history from monorepo."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import yaml


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_output_root() -> Path:
    return _default_repo_root() / "v5-build" / "infra-topology-framework-history"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract framework repository with preserved history.")
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
        help="Destination directory for extracted repository.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include framework tests in extracted repository.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output directory when it already exists.",
    )
    return parser.parse_args()


def _run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False, env=env)


def _rewrite_framework_manifest_for_extracted_layout(repo_root: Path) -> None:
    path = repo_root / "framework.yaml"
    if not path.exists():
        return
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return
    distribution = payload.get("distribution")
    if not isinstance(distribution, dict):
        return
    include = distribution.get("include")
    if not isinstance(include, list):
        return

    def _normalize_include_path(value: str) -> str:
        raw = value.strip()
        if raw.startswith("v5/topology/"):
            return raw.removeprefix("v5/")
        if raw == "v5/topology-tools" or raw.startswith("v5/topology-tools/"):
            return raw.removeprefix("v5/")
        return raw

    rewritten: list[str] = []
    for item in include:
        if isinstance(item, str):
            value = item.strip()
            if not value:
                continue
            rewritten.append(_normalize_include_path(value))
            continue
        if isinstance(item, dict):
            source = item.get("from")
            target = item.get("to")
            source_value = source.strip() if isinstance(source, str) else ""
            target_value = target.strip() if isinstance(target, str) else ""
            candidate = target_value or source_value
            if not candidate:
                continue
            rewritten.append(_normalize_include_path(candidate))
            continue
    distribution["include"] = rewritten
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _move_if_exists(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def _remove_if_exists(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, onerror=_on_rmtree_error)
    else:
        path.unlink()


def _on_rmtree_error(func, path: str, _exc_info) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _normalize_layout(*, repo_root: Path, include_tests: bool) -> None:
    stage = repo_root / ".framework-layout-stage"
    _remove_if_exists(stage)
    stage.mkdir(parents=True, exist_ok=True)

    _move_if_exists(repo_root / "topology" / "framework.yaml", stage / "framework.yaml")
    _move_if_exists(repo_root / "topology" / "class-modules", stage / "topology" / "class-modules")
    _move_if_exists(repo_root / "topology" / "object-modules", stage / "topology" / "object-modules")
    _move_if_exists(repo_root / "topology" / "layer-contract.yaml", stage / "topology" / "layer-contract.yaml")
    _move_if_exists(repo_root / "topology" / "model.lock.yaml", stage / "topology" / "model.lock.yaml")
    _move_if_exists(repo_root / "topology" / "profile-map.yaml", stage / "topology" / "profile-map.yaml")
    _move_if_exists(repo_root / "topology-tools", stage / "topology-tools")

    if include_tests:
        _move_if_exists(repo_root / "tests" / "plugin_api", stage / "tests" / "plugin_api")
        _move_if_exists(repo_root / "tests" / "plugin_contract", stage / "tests" / "plugin_contract")
        _move_if_exists(repo_root / "tests" / "plugin_integration", stage / "tests" / "plugin_integration")
        _move_if_exists(repo_root / "tests" / "plugin_regression", stage / "tests" / "plugin_regression")
        _move_if_exists(repo_root / "tests" / "conftest.py", stage / "tests" / "conftest.py")

    for child in repo_root.iterdir():
        if child.name in {".git", stage.name}:
            continue
        _remove_if_exists(child)

    for child in stage.iterdir():
        destination = repo_root / child.name
        if destination.exists():
            _remove_if_exists(destination)
        shutil.move(str(child), str(destination))
    _remove_if_exists(stage)

    _rewrite_framework_manifest_for_extracted_layout(repo_root)


def _commit_layout(repo_root: Path) -> None:
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "Topology Tools")
    env.setdefault("GIT_AUTHOR_EMAIL", "topology-tools@local")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])

    _run(["git", "add", "-A"], cwd=repo_root, env=env)
    diff = _run(["git", "diff", "--cached", "--quiet"], cwd=repo_root, env=env)
    if diff.returncode == 0:
        return
    committed = _run(
        ["git", "commit", "-m", "chore(0076-wave2): normalize extracted framework layout"],
        cwd=repo_root,
        env=env,
    )
    if committed.returncode != 0:
        raise RuntimeError(f"cannot commit normalized layout:\n{committed.stdout}\n{committed.stderr}")


def main() -> int:
    args = parse_args()
    source_root = args.repo_root.resolve()
    output_root = args.output_root.resolve()
    include_tests = bool(args.include_tests)

    if output_root.exists():
        if not args.force:
            print(f"ERROR: output directory already exists: {output_root} (use --force to overwrite)")
            return 2
        shutil.rmtree(output_root, onerror=_on_rmtree_error)

    temp_parent = output_root.parent if output_root.parent.exists() else source_root.parent
    temp_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="framework-history-extract-", dir=str(temp_parent)) as tmp:
        temp_root = Path(tmp)
        clone_root = temp_root / "repo"
        cloned = _run(["git", "clone", "--no-local", str(source_root), str(clone_root)])
        if cloned.returncode != 0:
            print("ERROR: cannot clone source repository")
            print(cloned.stdout)
            print(cloned.stderr)
            return cloned.returncode

        filtered = _run(
            ["git", "filter-branch", "--force", "--prune-empty", "--subdirectory-filter", "v5", "--", "HEAD"],
            cwd=clone_root,
            env={**os.environ, "FILTER_BRANCH_SQUELCH_WARNING": "1"},
        )
        if filtered.returncode != 0:
            print("ERROR: cannot run history filter")
            print(filtered.stdout)
            print(filtered.stderr)
            return filtered.returncode

        _normalize_layout(repo_root=clone_root, include_tests=include_tests)
        try:
            _commit_layout(clone_root)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1

        shutil.move(str(clone_root), str(output_root))

    print(f"Framework repository with history extracted to: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
