#!/usr/bin/env python3
"""Initialize new standalone project repo with framework submodule and compilable L0-L7 skeleton."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml

SEMVER_FROM_DIST_NAME_RE = re.compile(r".*-(\d+\.\d+\.\d+)\.zip$", re.IGNORECASE)


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


def _extract_framework_distribution_zip(
    *,
    project_root: Path,
    zip_path: Path,
    framework_path: str,
    force: bool,
) -> Path:
    if not zip_path.exists() or not zip_path.is_file():
        raise FileNotFoundError(f"framework distribution zip not found: {zip_path}")

    mount = framework_path.strip() or "framework"
    framework_root = project_root / mount
    if framework_root.exists():
        if not force:
            raise RuntimeError(f"framework path already exists: {framework_root} (use --force to overwrite)")
        if framework_root.is_dir():
            shutil.rmtree(framework_root)
        else:
            framework_root.unlink()

    with tempfile.TemporaryDirectory(prefix="framework-dist-extract-") as tmp_dir:
        staging_root = Path(tmp_dir).resolve()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(staging_root)

        entries = sorted(staging_root.iterdir(), key=lambda item: item.name)
        source_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else staging_root
        shutil.copytree(source_root, framework_root)

    return framework_root


def _resolve_framework_manifest_only(framework_root: Path) -> Path:
    extracted_manifest = framework_root / "framework.yaml"
    if extracted_manifest.exists():
        return extracted_manifest
    monorepo_manifest = framework_root / "v5" / "topology" / "framework.yaml"
    if monorepo_manifest.exists():
        return monorepo_manifest
    raise FileNotFoundError(
        "cannot resolve framework manifest; expected extracted (framework.yaml) "
        "or monorepo (topology/framework.yaml)"
    )


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
        "cannot resolve framework tools layout; expected extracted (topology-tools/) or monorepo (topology-tools/)"
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


def _resolve_distribution_version(*, zip_path: Path, version_override: str, framework_manifest_path: Path) -> str:
    normalized_override = version_override.strip()
    if normalized_override:
        return normalized_override

    name_match = SEMVER_FROM_DIST_NAME_RE.match(zip_path.name)
    if name_match is not None:
        return name_match.group(1)

    payload = yaml.safe_load(framework_manifest_path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, dict):
        version = payload.get("framework_api_version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    raise RuntimeError(
        f"cannot resolve framework distribution version from zip name '{zip_path.name}' or framework manifest"
    )


def _regenerate_lock_for_package(
    *,
    project_root: Path,
    framework_root: Path,
    framework_manifest: Path,
    lock_path: Path,
    repository: str,
    version: str,
) -> None:
    generate_script = Path(__file__).resolve().parent / "generate-framework-lock.py"
    run = _run(
        [
            sys.executable,
            str(generate_script),
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
            str(lock_path),
            "--source",
            "package",
            "--version",
            version,
            "--repository",
            repository,
            "--force",
        ],
        cwd=project_root,
    )
    if run.returncode != 0:
        raise RuntimeError(f"generate-framework-lock --source package failed:\n{run.stdout}\n{run.stderr}")


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


def _resolve_project_instances_root(project_root: Path) -> Path:
    project_manifest_path = project_root / "project.yaml"
    payload = yaml.safe_load(project_manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise RuntimeError(f"project manifest must be mapping: {project_manifest_path}")
    instances_root = payload.get("instances_root")
    if isinstance(instances_root, str) and instances_root.strip():
        return project_root / instances_root.strip()
    return project_root / "topology" / "instances"


def _create_layer_structure(
    project_root: Path,
    *,
    group_layers: dict[str, str],
    instances_root: Path,
) -> None:
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


def _write_starter_files(*, instances_root: Path) -> None:
    for relative, content in STARTER_FILES.items():
        path = instances_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _verify_and_compile(
    *, project_root: Path, framework_root: Path, framework_manifest: Path, tools_root: Path
) -> None:
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
    parser = argparse.ArgumentParser(description="Initialize new standalone project repo with framework dependency.")
    parser.add_argument("--output-root", type=Path, default=_default_output_root(), help="Target project root.")
    parser.add_argument("--project-id", required=True, help="Project identifier.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--framework-submodule-url",
        help="Framework git URL/path for submodule wiring.",
    )
    source_group.add_argument(
        "--framework-dist-zip",
        type=Path,
        help="Framework distribution zip artifact path (package dependency mode).",
    )
    parser.add_argument(
        "--framework-submodule-path",
        default="framework",
        help="Framework mount path in project repository (default: framework).",
    )
    parser.add_argument(
        "--framework-dist-version",
        default="",
        help="Framework distribution version override for package lock mode (default: infer from zip name).",
    )
    parser.add_argument(
        "--framework-dist-repository",
        default="",
        help="Repository/registry reference for package lock mode (default: file URI of zip artifact).",
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
    framework_submodule_url = str(args.framework_submodule_url or "").strip()
    framework_dist_zip = args.framework_dist_zip.resolve() if isinstance(args.framework_dist_zip, Path) else None

    try:
        _ensure_empty_project_root(output_root, force=bool(args.force))
        _ensure_git_repo(output_root)
        mount_path = str(args.framework_submodule_path)
        if framework_dist_zip is not None:
            framework_root = _extract_framework_distribution_zip(
                project_root=output_root,
                zip_path=framework_dist_zip,
                framework_path=mount_path,
                force=bool(args.force),
            )
        else:
            if not framework_submodule_url:
                print("ERROR: --framework-submodule-url must be non-empty")
                return 2
            framework_root = _wire_framework_submodule(
                project_root=output_root,
                submodule_url=framework_submodule_url,
                submodule_path=mount_path,
                force=bool(args.force),
            )
        _bootstrap_project(framework_root=framework_root, output_root=output_root, project_id=project_id)
        if framework_dist_zip is not None:
            framework_manifest = _resolve_framework_manifest_only(framework_root)
            dist_version = _resolve_distribution_version(
                zip_path=framework_dist_zip,
                version_override=str(args.framework_dist_version),
                framework_manifest_path=framework_manifest,
            )
            repository = str(args.framework_dist_repository).strip()
            if not repository:
                repository = framework_dist_zip.resolve().as_uri()
            _regenerate_lock_for_package(
                project_root=output_root,
                framework_root=framework_root,
                framework_manifest=framework_manifest,
                lock_path=output_root / "framework.lock.yaml",
                repository=repository,
                version=dist_version,
            )
        group_layers = _load_group_layers(output_root)
        instances_root = _resolve_project_instances_root(output_root)
        _create_layer_structure(output_root, group_layers=group_layers, instances_root=instances_root)
        if args.starter_profile == "minimal-compilable":
            _write_starter_files(instances_root=instances_root)
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
    framework_source = "distribution-zip" if framework_dist_zip is not None else "git-submodule"
    print(f"Framework source: {framework_source}")
    print(f"Framework root: {framework_root}")
    if framework_dist_zip is not None:
        print(f"Framework artifact: {framework_dist_zip}")
    print("Layer structure: L0-L7 created")
    print(f"Starter profile: {args.starter_profile}")
    if args.skip_compile_check:
        print("Compile check: skipped")
    else:
        print("Compile check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
