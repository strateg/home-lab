#!/usr/bin/env python3
"""Bootstrap standalone project repository for submodule-first framework consumption."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from framework_lock import default_framework_manifest_path

PROJECT_INSTANCES_ROOT = "topology/instances"


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_framework_root() -> Path:
    return _default_repo_root()


def _default_output_root() -> Path:
    return _default_repo_root() / "build" / "project-bootstrap" / "home-lab"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap standalone project repository structure.")
    parser.add_argument(
        "--framework-root",
        type=Path,
        default=_default_framework_root(),
        help="Framework source root (monorepo or extracted framework repo).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_default_output_root(),
        help="Target project repository directory.",
    )
    parser.add_argument(
        "--project-id",
        default="home-lab",
        help="Project identifier.",
    )
    parser.add_argument(
        "--project-schema-version",
        default="1.0.0",
        help="Project schema version.",
    )
    parser.add_argument(
        "--project-contract-revision",
        type=int,
        default=1,
        help="Project contract revision.",
    )
    parser.add_argument(
        "--project-min-framework-version",
        default="5.0.0",
        help="Minimum compatible framework version.",
    )
    parser.add_argument(
        "--seed-project-root",
        type=Path,
        default=None,
        help="Optional existing project root to copy instances/secrets/overrides from.",
    )
    parser.add_argument(
        "--framework-submodule-url",
        default="",
        help="Optional framework repository URL/path for git submodule wiring.",
    )
    parser.add_argument(
        "--framework-submodule-path",
        default="framework",
        help="Submodule mount path inside project repository (default: framework).",
    )
    parser.add_argument(
        "--init-git",
        action="store_true",
        help="Initialize git repository in output root before optional submodule wiring.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files when present.",
    )
    return parser.parse_args()


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_if_missing(path: Path, content: str, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False, cwd=cwd)


def _ensure_git_repo(output_root: Path) -> None:
    if (output_root / ".git").exists():
        return
    initialized = _run(["git", "init"], cwd=output_root)
    if initialized.returncode != 0:
        raise RuntimeError(f"cannot initialize git repo:\n{initialized.stdout}\n{initialized.stderr}")


def _wire_framework_submodule(
    *,
    output_root: Path,
    submodule_url: str,
    submodule_path: str,
    force: bool,
) -> Path:
    normalized_url = submodule_url.strip()
    if not normalized_url:
        return output_root

    _ensure_git_repo(output_root)

    mount = submodule_path.strip() or "framework"
    submodule_root = output_root / mount
    git_marker = submodule_root / ".git"
    if submodule_root.exists() and not git_marker.exists() and force:
        shutil.rmtree(submodule_root)

    if not submodule_root.exists():
        added = _run(
            ["git", "-c", "protocol.file.allow=always", "submodule", "add", normalized_url, mount],
            cwd=output_root,
        )
        if added.returncode != 0:
            raise RuntimeError(f"cannot add framework submodule:\n{added.stdout}\n{added.stderr}")

    updated = _run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive", mount],
        cwd=output_root,
    )
    if updated.returncode != 0:
        raise RuntimeError(f"cannot update framework submodule:\n{updated.stdout}\n{updated.stderr}")

    return submodule_root


def _copy_tree_if_exists(
    *,
    source_root: Path,
    target_root: Path,
    source_relative: str,
    force: bool,
    target_relative: str | None = None,
) -> bool:
    source = source_root / source_relative
    if not source.exists():
        return False
    destination_relative = (
        target_relative if isinstance(target_relative, str) and target_relative.strip() else source_relative
    )
    destination = target_root / destination_relative
    if destination.exists():
        if not force:
            return True
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return True


def _detect_framework_manifest(framework_root: Path) -> tuple[Path, str]:
    monorepo_manifest = framework_root / "topology" / "framework.yaml"
    extracted_manifest = framework_root / "framework.yaml"
    if monorepo_manifest.exists():
        return monorepo_manifest, "monorepo"
    if extracted_manifest.exists():
        return extracted_manifest, "extracted"
    raise FileNotFoundError(
        f"framework manifest not found in supported locations: {monorepo_manifest} or {extracted_manifest}"
    )


def _mounted_path(framework_root: Path, framework_mount: str, candidates: list[str]) -> str:
    for relative in candidates:
        if (framework_root / relative).exists():
            return f"{framework_mount}/{relative}"
    return f"{framework_mount}/{candidates[0]}"


def _topology_framework_section(layout: str, *, framework_mount: str, framework_root: Path) -> dict[str, str]:
    if layout == "monorepo":
        prefix = f"{framework_mount}/topology"
        return {
            "root": framework_mount,
            "class_modules_root": f"{prefix}/class-modules",
            "object_modules_root": f"{prefix}/object-modules",
            "model_lock": f"{prefix}/model.lock.yaml",
            "profile_map": f"{prefix}/profile-map.yaml",
            "layer_contract": f"{prefix}/layer-contract.yaml",
            "capability_catalog": f"{prefix}/class-modules/router/capability-catalog.yaml",
            "capability_packs": f"{prefix}/class-modules/router/capability-packs.yaml",
        }

    return {
        "root": framework_mount,
        "class_modules_root": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/class-modules", "class-modules"],
        ),
        "object_modules_root": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/object-modules", "object-modules"],
        ),
        "model_lock": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/model.lock.yaml", "model.lock.yaml"],
        ),
        "profile_map": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/profile-map.yaml", "profile-map.yaml"],
        ),
        "layer_contract": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/layer-contract.yaml", "layer-contract.yaml"],
        ),
        "capability_catalog": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/class-modules/router/capability-catalog.yaml", "class-modules/router/capability-catalog.yaml"],
        ),
        "capability_packs": _mounted_path(
            framework_root,
            framework_mount,
            ["topology/class-modules/router/capability-packs.yaml", "class-modules/router/capability-packs.yaml"],
        ),
    }


def _write_task_bundle(
    *,
    output_root: Path,
    framework_mount: str,
    tools_prefix: str,
    framework_manifest_rel: str,
    force: bool,
) -> None:
    root_taskfile = "\n".join(
        [
            'version: "3"',
            "",
            "vars:",
            "  PYTHON: '{{default \"python\" .PYTHON}}'",
            "  PROJECT_ROOT: '{{default \".\" .PROJECT_ROOT}}'",
            "  FRAMEWORK_ROOT: '{{default \"" + framework_mount + "\" .FRAMEWORK_ROOT}}'",
            "  FRAMEWORK_TOOLS_ROOT: '{{default \"" + tools_prefix + "\" .FRAMEWORK_TOOLS_ROOT}}'",
            "  FRAMEWORK_MANIFEST: '{{default \"" + framework_manifest_rel + "\" .FRAMEWORK_MANIFEST}}'",
            "  TOPOLOGY_FILE: '{{default \"topology.yaml\" .TOPOLOGY_FILE}}'",
            "  PROJECT_MANIFEST: '{{default \"project.yaml\" .PROJECT_MANIFEST}}'",
            "",
            "includes:",
            "  project:",
            "    taskfile: ./taskfiles/project.yml",
            "    dir: .",
            "    vars:",
            '      PYTHON: "{{.PYTHON}}"',
            '      PROJECT_ROOT: "{{.PROJECT_ROOT}}"',
            '      FRAMEWORK_ROOT: "{{.FRAMEWORK_ROOT}}"',
            '      FRAMEWORK_TOOLS_ROOT: "{{.FRAMEWORK_TOOLS_ROOT}}"',
            '      FRAMEWORK_MANIFEST: "{{.FRAMEWORK_MANIFEST}}"',
            '      TOPOLOGY_FILE: "{{.TOPOLOGY_FILE}}"',
            '      PROJECT_MANIFEST: "{{.PROJECT_MANIFEST}}"',
            "",
            "tasks:",
            "  default:",
            "    desc: List available tasks",
            "    cmds:",
            "      - task --list",
            "",
        ]
    )
    project_taskfile = "\n".join(
        [
            'version: "3"',
            "",
            "tasks:",
            "  lock:generate:",
            "    desc: Regenerate framework.lock.yaml from mounted framework",
            "    cmds:",
            '      - "{{.PYTHON}} {{.FRAMEWORK_TOOLS_ROOT}}/generate-framework-lock.py --repo-root \\"{{.PROJECT_ROOT}}\\" --project-root \\"{{.PROJECT_ROOT}}\\" --project-manifest \\"{{.PROJECT_MANIFEST}}\\" --framework-root \\"{{.FRAMEWORK_ROOT}}\\" --framework-manifest \\"{{.FRAMEWORK_MANIFEST}}\\" --lock-file \\"{{.PROJECT_ROOT}}/framework.lock.yaml\\" --force"',
            "",
            "  lock:verify:",
            "    desc: Verify framework.lock.yaml in strict mode",
            "    cmds:",
            '      - "{{.PYTHON}} {{.FRAMEWORK_TOOLS_ROOT}}/verify-framework-lock.py --repo-root \\"{{.PROJECT_ROOT}}\\" --project-root \\"{{.PROJECT_ROOT}}\\" --project-manifest \\"{{.PROJECT_MANIFEST}}\\" --framework-root \\"{{.FRAMEWORK_ROOT}}\\" --framework-manifest \\"{{.FRAMEWORK_MANIFEST}}\\" --lock-file \\"{{.PROJECT_ROOT}}/framework.lock.yaml\\" --strict"',
            "",
            "  compile:",
            "    desc: Compile topology in strict mode",
            "    cmds:",
            '      - "{{.PYTHON}} {{.FRAMEWORK_TOOLS_ROOT}}/compile-topology.py --repo-root \\"{{.PROJECT_ROOT}}\\" --topology \\"{{.TOPOLOGY_FILE}}\\" --secrets-mode passthrough --strict-model-lock --output-json \\"{{.PROJECT_ROOT}}/generated/effective-topology.json\\" --diagnostics-json \\"{{.PROJECT_ROOT}}/generated/diagnostics.json\\" --diagnostics-txt \\"{{.PROJECT_ROOT}}/generated/diagnostics.txt\\" --artifacts-root \\"{{.PROJECT_ROOT}}/generated-artifacts\\""',
            "",
            "  validate:",
            "    desc: Verify lock and compile topology",
            "    deps:",
            "      - lock:verify",
            "      - compile",
            "",
        ]
    )
    _write_if_missing(output_root / "Taskfile.yml", root_taskfile, force=force)
    _write_if_missing(output_root / "taskfiles" / "project.yml", project_taskfile, force=force)


def main() -> int:
    args = parse_args()
    framework_root = args.framework_root.resolve()
    output_root = args.output_root.resolve()
    project_id = str(args.project_id).strip()
    submodule_url = str(args.framework_submodule_url).strip()
    submodule_mount = str(args.framework_submodule_path).strip() or "framework"
    seed_project_root = args.seed_project_root.resolve() if isinstance(args.seed_project_root, Path) else None
    if not project_id:
        print("ERROR: --project-id must be non-empty")
        return 2

    try:
        _framework_manifest, framework_layout = _detect_framework_manifest(framework_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    output_root.mkdir(parents=True, exist_ok=True)
    if args.init_git:
        try:
            _ensure_git_repo(output_root)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 2

    framework_root_for_lock = framework_root
    if submodule_url:
        try:
            framework_root_for_lock = _wire_framework_submodule(
                output_root=output_root,
                submodule_url=submodule_url,
                submodule_path=submodule_mount,
                force=bool(args.force),
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 2

    topology_path = output_root / "topology.yaml"
    project_manifest_path = output_root / "project.yaml"
    lock_path = output_root / "framework.lock.yaml"

    topology_payload = {
        "version": "5.0.0",
        "model": "class-object-instance",
        "framework": _topology_framework_section(
            framework_layout,
            framework_mount=submodule_mount,
            framework_root=framework_root_for_lock,
        ),
        "project": {
            "active": project_id,
            "projects_root": ".",
        },
    }
    project_payload = {
        "schema_version": 1,
        "project_schema_version": str(args.project_schema_version).strip(),
        "project": project_id,
        "project_min_framework_version": str(args.project_min_framework_version).strip(),
        "project_contract_revision": int(args.project_contract_revision),
        "instances_root": PROJECT_INSTANCES_ROOT,
        "secrets_root": "secrets",
    }

    _write_yaml(topology_path, topology_payload)
    _write_yaml(project_manifest_path, project_payload)
    (output_root / PROJECT_INSTANCES_ROOT).mkdir(parents=True, exist_ok=True)
    (output_root / "secrets").mkdir(parents=True, exist_ok=True)
    (output_root / "overrides").mkdir(parents=True, exist_ok=True)
    (output_root / "generated").mkdir(parents=True, exist_ok=True)
    if seed_project_root is not None:
        copied_instances = _copy_tree_if_exists(
            source_root=seed_project_root,
            target_root=output_root,
            source_relative=PROJECT_INSTANCES_ROOT,
            target_relative=PROJECT_INSTANCES_ROOT,
            force=bool(args.force),
        )
        if not copied_instances:
            _copy_tree_if_exists(
                source_root=seed_project_root,
                target_root=output_root,
                source_relative="instances",
                target_relative=PROJECT_INSTANCES_ROOT,
                force=bool(args.force),
            )
        _copy_tree_if_exists(
            source_root=seed_project_root,
            target_root=output_root,
            source_relative="secrets",
            force=bool(args.force),
        )
        _copy_tree_if_exists(
            source_root=seed_project_root,
            target_root=output_root,
            source_relative="overrides",
            force=bool(args.force),
        )

    template_root = Path(__file__).resolve().parents[1] / "docs" / "framework" / "templates"
    validate_template = template_root / "project-validate.yml"
    if validate_template.exists():
        _write_if_missing(
            output_root / ".github" / "workflows" / "validate.yml",
            validate_template.read_text(encoding="utf-8"),
            force=args.force,
        )

    script_root = Path(__file__).resolve().parent
    generate_lock_script = script_root / "generate-framework-lock.py"
    generate = _run(
        [
            sys.executable,
            str(generate_lock_script),
            "--repo-root",
            str(output_root),
            "--project-root",
            str(output_root),
            "--project-manifest",
            str(project_manifest_path),
            "--framework-root",
            str(framework_root_for_lock),
            "--framework-manifest",
            str(default_framework_manifest_path(framework_root_for_lock)),
            "--lock-file",
            str(lock_path),
            "--force",
        ]
    )
    if generate.returncode != 0:
        print("ERROR: cannot generate framework.lock.yaml")
        print(generate.stdout)
        print(generate.stderr)
        return generate.returncode

    notes = output_root / "BOOTSTRAP-NOTES.md"
    tools_prefix = (
        f"{submodule_mount}/topology-tools" if framework_layout == "monorepo" else f"{submodule_mount}/topology-tools"
    )
    framework_manifest_rel = (
        f"{submodule_mount}/topology/framework.yaml"
        if framework_layout == "monorepo"
        else f"{submodule_mount}/framework.yaml"
    )
    _write_if_missing(
        notes,
        "\n".join(
            [
                "# Project Repo Bootstrap Notes",
                "",
                f"- framework_submodule_url: {submodule_url or '<not-set>'}",
                f"- framework_submodule_path: {submodule_mount}",
                f"- seed_project_root: {str(seed_project_root) if seed_project_root else '<not-set>'}",
                "",
                "Next steps:",
                (
                    f"1. Keep framework wired under ./{submodule_mount} via git submodule."
                    if submodule_url
                    else f"1. Keep framework sources mounted under ./{submodule_mount} "
                    "(package extract/vendor sync/local mirror)."
                ),
                "2. Update validate workflow secrets/runner settings as needed",
                "3. Run strict gates:",
                (
                    f"   - python {tools_prefix}/verify-framework-lock.py --repo-root . --project-root . "
                    f"--project-manifest project.yaml --framework-root {submodule_mount} "
                    f"--framework-manifest {framework_manifest_rel} --strict"
                ),
                (
                    f"   - python {tools_prefix}/compile-topology.py --repo-root . --topology ./topology.yaml "
                    "--secrets-mode passthrough"
                ),
                "4. Use task shortcuts:",
                "   - task project:lock:verify",
                "   - task project:compile",
                "   - task project:validate",
                "",
            ]
        ),
        force=args.force,
    )
    _write_task_bundle(
        output_root=output_root,
        framework_mount=submodule_mount,
        tools_prefix=tools_prefix,
        framework_manifest_rel=framework_manifest_rel,
        force=bool(args.force),
    )

    print(f"Project repository bootstrap prepared: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
