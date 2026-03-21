#!/usr/bin/env python3
"""Initialize new standalone project repo with framework submodule and compilable L0-L7 skeleton."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


LAYER_BUCKETS: dict[str, str] = {
    "L0": "L0-meta",
    "L1": "L1-foundation",
    "L2": "L2-network",
    "L3": "L3-data",
    "L4": "L4-platform",
    "L5": "L5-application",
    "L6": "L6-observability",
    "L7": "L7-operations",
}

STARTER_FILES: dict[str, str] = {
    "L1-foundation/firmware/inst.firmware.apc.backups.650va.yaml": (
        "instance: inst.firmware.apc.backups.650va\n"
        "object_ref: obj.firmware.apc.backups.650va\n"
        "group: firmware\n"
        "layer: L1\n"
        "version: 1.0.0\n"
    ),
    "L1-foundation/power/ups-main.yaml": (
        "instance: ups-main\n"
        "object_ref: obj.apc.backups.650va\n"
        "group: power\n"
        "layer: L1\n"
        "version: 1.0.0\n"
        "firmware_ref: inst.firmware.apc.backups.650va\n"
        "os_refs: []\n"
    ),
}


def _default_output_root() -> Path:
    return Path.cwd()


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def _ensure_empty_project_root(path: Path, *, force: bool) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    existing = [item for item in path.iterdir()]
    if not existing:
        return
    if not force:
        raise RuntimeError(f"output root is not empty: {path} (use --force to reset)")
    for item in existing:
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def _ensure_git_repo(root: Path) -> None:
    if (root / ".git").exists():
        return
    initialized = _run(["git", "init"], cwd=root)
    if initialized.returncode != 0:
        raise RuntimeError(f"cannot initialize git repository:\n{initialized.stdout}\n{initialized.stderr}")


def _wire_framework_submodule(*, project_root: Path, submodule_url: str, submodule_path: str, force: bool) -> Path:
    mount = submodule_path.strip() or "framework"
    submodule_root = project_root / mount
    if submodule_root.exists() and force and not (submodule_root / ".git").exists():
        shutil.rmtree(submodule_root)
    if not submodule_root.exists():
        added = _run(
            ["git", "-c", "protocol.file.allow=always", "submodule", "add", submodule_url, mount],
            cwd=project_root,
        )
        if added.returncode != 0:
            raise RuntimeError(f"cannot add framework submodule:\n{added.stdout}\n{added.stderr}")
    updated = _run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive", mount],
        cwd=project_root,
    )
    if updated.returncode != 0:
        raise RuntimeError(f"cannot update framework submodule:\n{updated.stdout}\n{updated.stderr}")
    return submodule_root


def _resolve_framework_tools(framework_root: Path) -> tuple[Path, Path]:
    extracted_tools = framework_root / "topology-tools"
    extracted_manifest = framework_root / "framework.yaml"
    if (extracted_tools / "compile-topology.py").exists() and extracted_manifest.exists():
        return extracted_tools, extracted_manifest

    monorepo_tools = framework_root / "v5" / "topology-tools"
    monorepo_manifest = framework_root / "v5" / "topology" / "framework.yaml"
    if (monorepo_tools / "compile-topology.py").exists() and monorepo_manifest.exists():
        return monorepo_tools, monorepo_manifest

    raise FileNotFoundError(
        "cannot resolve framework tools layout; expected extracted (topology-tools/) or monorepo (v5/topology-tools/)"
    )


def _bootstrap_project(*, framework_root: Path, output_root: Path, project_id: str) -> None:
    script = Path(__file__).resolve().parent / "bootstrap-project-repo.py"
    run = _run(
        [
            sys.executable,
            str(script),
            "--framework-root",
            str(framework_root),
            "--output-root",
            str(output_root),
            "--project-id",
            project_id,
            "--force",
        ],
        cwd=output_root,
    )
    if run.returncode != 0:
        raise RuntimeError(f"bootstrap-project-repo failed:\n{run.stdout}\n{run.stderr}")


def _load_group_layers(project_root: Path) -> dict[str, str]:
    topology_path = project_root / "topology.yaml"
    topology = yaml.safe_load(topology_path.read_text(encoding="utf-8")) or {}
    if not isinstance(topology, dict):
        raise RuntimeError(f"topology manifest must be mapping: {topology_path}")
    framework = topology.get("framework")
    if not isinstance(framework, dict):
        raise RuntimeError(f"topology manifest missing 'framework' section: {topology_path}")
    layer_contract = framework.get("layer_contract")
    if not isinstance(layer_contract, str) or not layer_contract.strip():
        raise RuntimeError(f"topology framework.layer_contract must be non-empty string: {topology_path}")
    layer_contract_path = project_root / layer_contract
    contract = yaml.safe_load(layer_contract_path.read_text(encoding="utf-8")) or {}
    if not isinstance(contract, dict):
        raise RuntimeError(f"layer contract must be mapping: {layer_contract_path}")
    group_layers = contract.get("group_layers")
    if not isinstance(group_layers, dict):
        raise RuntimeError(f"layer contract missing mapping 'group_layers': {layer_contract_path}")
    resolved: dict[str, str] = {}
    for group, layer in group_layers.items():
        if isinstance(group, str) and isinstance(layer, str):
            resolved[group] = layer
    return resolved


def _touch_gitkeep(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").write_text("", encoding="utf-8")


def _create_layer_structure(project_root: Path, *, group_layers: dict[str, str]) -> None:
    instances_root = project_root / "instances"
    for bucket in LAYER_BUCKETS.values():
        _touch_gitkeep(instances_root / bucket)

    for group_name in sorted(group_layers):
        layer = group_layers[group_name]
        bucket = LAYER_BUCKETS.get(layer)
        if not isinstance(bucket, str):
            continue
        _touch_gitkeep(instances_root / bucket / group_name)

    _touch_gitkeep(project_root / "secrets" / "instances")
    _touch_gitkeep(project_root / "secrets" / "terraform")
    _touch_gitkeep(project_root / "secrets" / "bootstrap")
    _touch_gitkeep(project_root / "generated")
    _touch_gitkeep(project_root / "generated-artifacts")


def _write_starter_files(project_root: Path) -> None:
    instances_root = project_root / "instances"
    for relative, content in STARTER_FILES.items():
        path = instances_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _verify_and_compile(*, project_root: Path, framework_root: Path, framework_manifest: Path, tools_root: Path) -> None:
    verify = _run(
        [
            sys.executable,
            str(tools_root / "verify-framework-lock.py"),
            "--repo-root",
            str(project_root),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_root / "project.yaml"),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_manifest),
            "--lock-file",
            str(project_root / "framework.lock.yaml"),
            "--strict",
        ],
        cwd=project_root,
    )
    if verify.returncode != 0:
        raise RuntimeError(f"verify-framework-lock failed:\n{verify.stdout}\n{verify.stderr}")

    compile_run = _run(
        [
            sys.executable,
            str(tools_root / "compile-topology.py"),
            "--repo-root",
            str(project_root),
            "--topology",
            "./topology.yaml",
            "--secrets-mode",
            "passthrough",
            "--strict-model-lock",
            "--output-json",
            "./generated/effective-topology.json",
            "--diagnostics-json",
            "./generated/diagnostics.json",
            "--diagnostics-txt",
            "./generated/diagnostics.txt",
            "--artifacts-root",
            "./generated-artifacts",
        ],
        cwd=project_root,
    )
    if compile_run.returncode != 0:
        raise RuntimeError(f"compile-topology failed:\n{compile_run.stdout}\n{compile_run.stderr}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize new standalone project repo with framework submodule.")
    parser.add_argument("--output-root", type=Path, default=_default_output_root(), help="Target project root.")
    parser.add_argument("--project-id", required=True, help="Project identifier.")
    parser.add_argument("--framework-submodule-url", required=True, help="Framework git URL/path for submodule wiring.")
    parser.add_argument(
        "--framework-submodule-path",
        default="framework",
        help="Submodule path in project repository (default: framework).",
    )
    parser.add_argument(
        "--starter-profile",
        choices=("minimal-compilable", "none"),
        default="minimal-compilable",
        help="Starter instances profile (default: minimal-compilable).",
    )
    parser.add_argument("--skip-compile-check", action="store_true", help="Skip strict verify + compile check.")
    parser.add_argument("--force", action="store_true", help="Reset output root content (except .git) when non-empty.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_root = args.output_root.resolve()
    project_id = str(args.project_id).strip()
    if not project_id:
        print("ERROR: --project-id must be non-empty")
        return 2
    framework_submodule_url = str(args.framework_submodule_url).strip()
    if not framework_submodule_url:
        print("ERROR: --framework-submodule-url must be non-empty")
        return 2

    try:
        _ensure_empty_project_root(output_root, force=bool(args.force))
        _ensure_git_repo(output_root)
        framework_root = _wire_framework_submodule(
            project_root=output_root,
            submodule_url=framework_submodule_url,
            submodule_path=str(args.framework_submodule_path),
            force=bool(args.force),
        )
        _bootstrap_project(framework_root=framework_root, output_root=output_root, project_id=project_id)
        group_layers = _load_group_layers(output_root)
        _create_layer_structure(output_root, group_layers=group_layers)
        if args.starter_profile == "minimal-compilable":
            _write_starter_files(output_root)
        if not args.skip_compile_check:
            tools_root, framework_manifest = _resolve_framework_tools(framework_root)
            _verify_and_compile(
                project_root=output_root,
                framework_root=framework_root,
                framework_manifest=framework_manifest,
                tools_root=tools_root,
            )
    except (RuntimeError, OSError, FileNotFoundError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Project initialized: {output_root}")
    print(f"Framework submodule: {framework_root}")
    print("Layer structure: L0-L7 created")
    print(f"Starter profile: {args.starter_profile}")
    if args.skip_compile_check:
        print("Compile check: skipped")
    else:
        print("Compile check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
