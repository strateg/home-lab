#!/usr/bin/env python3
"""Bootstrap standalone project repository for submodule-first framework consumption."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_framework_root() -> Path:
    return _default_repo_root()


def _default_output_root() -> Path:
    return _default_repo_root() / "v5-build" / "project-bootstrap" / "home-lab"


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


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def _detect_framework_manifest(framework_root: Path) -> tuple[Path, str]:
    monorepo_manifest = framework_root / "v5" / "topology" / "framework.yaml"
    extracted_manifest = framework_root / "framework.yaml"
    if monorepo_manifest.exists():
        return monorepo_manifest, "monorepo"
    if extracted_manifest.exists():
        return extracted_manifest, "extracted"
    raise FileNotFoundError(
        f"framework manifest not found in supported locations: {monorepo_manifest} or {extracted_manifest}"
    )


def _topology_framework_section(layout: str) -> dict[str, str]:
    if layout == "monorepo":
        prefix = "framework/v5/topology"
    else:
        prefix = "framework"
    return {
        "root": "framework",
        "class_modules_root": f"{prefix}/class-modules",
        "object_modules_root": f"{prefix}/object-modules",
        "model_lock": f"{prefix}/model.lock.yaml",
        "profile_map": f"{prefix}/profile-map.yaml",
        "layer_contract": f"{prefix}/layer-contract.yaml",
        "capability_catalog": f"{prefix}/class-modules/router/capability-catalog.yaml",
        "capability_packs": f"{prefix}/class-modules/router/capability-packs.yaml",
    }


def main() -> int:
    args = parse_args()
    framework_root = args.framework_root.resolve()
    output_root = args.output_root.resolve()
    project_id = str(args.project_id).strip()
    if not project_id:
        print("ERROR: --project-id must be non-empty")
        return 2

    try:
        framework_manifest, framework_layout = _detect_framework_manifest(framework_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    output_root.mkdir(parents=True, exist_ok=True)
    topology_path = output_root / "topology.yaml"
    project_manifest_path = output_root / "project.yaml"
    lock_path = output_root / "framework.lock.yaml"

    topology_payload = {
        "version": "5.0.0",
        "model": "class-object-instance",
        "framework": _topology_framework_section(framework_layout),
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
        "instances_root": "instances",
        "secrets_root": "secrets",
    }

    _write_yaml(topology_path, topology_payload)
    _write_yaml(project_manifest_path, project_payload)
    (output_root / "instances").mkdir(parents=True, exist_ok=True)
    (output_root / "secrets").mkdir(parents=True, exist_ok=True)
    (output_root / "overrides").mkdir(parents=True, exist_ok=True)
    (output_root / "generated").mkdir(parents=True, exist_ok=True)

    template_root = Path(__file__).resolve().parents[2] / "docs" / "framework" / "templates"
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
            str(framework_root),
            "--framework-manifest",
            str(framework_manifest),
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
    tools_prefix = "framework/v5/topology-tools" if framework_layout == "monorepo" else "framework/topology-tools"
    _write_if_missing(
        notes,
        "\n".join(
            [
                "# Project Repo Bootstrap Notes",
                "",
                "Next steps:",
                "1. Add framework as git submodule under ./framework",
                "2. Update validate workflow secrets/runner settings as needed",
                "3. Run strict gates:",
                f"   - python {tools_prefix}/verify-framework-lock.py --strict",
                f"   - python {tools_prefix}/compile-topology.py --repo-root . --topology ./topology.yaml",
                "",
            ]
        ),
        force=args.force,
    )

    print(f"Project repository bootstrap prepared: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
