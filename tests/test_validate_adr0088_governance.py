#!/usr/bin/env python3
"""Contract tests for ADR0088 governance validation script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "validation" / "validate_adr0088_governance.py"
    spec = importlib.util.spec_from_file_location("validate_adr0088_governance", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load validate_adr0088_governance module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_diagnostics(path: Path, warning_code: str = "W7816", count: int = 1) -> None:
    diagnostics = [
        {"code": warning_code, "severity": "warning", "stage": "validate", "message": "warn", "path": "x"}
    ] * count
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"diagnostics": diagnostics}, ensure_ascii=True), encoding="utf-8")


def _write_policy(path: Path) -> None:
    _write_yaml(
        path,
        {
            "schema_version": 1,
            "metadata": {
                "targets": {
                    "class_modules": {
                        "root": "topology/class-modules",
                        "filename_prefix": "class.",
                        "required_keys": ["@title", "@layer"],
                        "min_coverage": {"@title": 0.9, "@layer": 0.9},
                    },
                    "object_modules": {
                        "root": "topology/object-modules",
                        "filename_prefix": "obj.",
                        "required_keys": ["@title"],
                        "min_coverage": {"@title": 0.9},
                    },
                }
            },
            "warning_governance": {
                "allowlist": ["W7816"],
                "max_counts": {"W7816": 5},
            },
            "legacy_boundary": {
                "scan_root": "projects",
                "active_instances_root": "projects/home-lab/topology/instances",
                "exclude_globs": ["projects/*/_legacy/**"],
                "key_patterns": {
                    "class_ref": r"^\s*class_ref\s*:",
                    "object_ref": r"^\s*object_ref\s*:",
                },
            },
        },
    )


def _seed_repo(tmp_path: Path, *, legacy_in_active_instances: bool = False) -> tuple[Path, Path]:
    _write_yaml(
        tmp_path / "topology/class-modules/class.router.yaml",
        {"@class": "class.router", "@version": "1.0.0"},
    )
    _write_yaml(
        tmp_path / "topology/object-modules/obj.router.yaml",
        {"@object": "obj.router", "@extends": "class.router", "@version": "1.0.0"},
    )
    if legacy_in_active_instances:
        _write_text(
            tmp_path / "projects/home-lab/topology/instances/devices/inst.router.a.yaml",
            "@version: 1.0.0\n@instance: inst.router.a\ngroup: devices\n@extends: obj.router\nclass_ref: class.router\n",
        )
    else:
        _write_yaml(
            tmp_path / "projects/home-lab/topology/instances/devices/inst.router.a.yaml",
            {
                "@version": "1.0.0",
                "@instance": "inst.router.a",
                "group": "devices",
                "@extends": "obj.router",
            },
        )
    _write_text(tmp_path / "projects/home-lab/_legacy/legacy.yaml", "class_ref: class.router\nobject_ref: obj.router\n")

    diagnostics_path = tmp_path / "build/diagnostics/report.json"
    _write_diagnostics(diagnostics_path, warning_code="W7816", count=1)
    policy_path = tmp_path / "configs/quality/adr0088-governance-policy.yaml"
    _write_policy(policy_path)
    return policy_path, diagnostics_path


def test_governance_warn_mode_reports_metadata_gap_without_errors(tmp_path: Path) -> None:
    mod = _load_module()
    policy_path, diagnostics_path = _seed_repo(tmp_path)

    report = mod.run_governance(
        repo_root=tmp_path,
        policy_path=policy_path,
        diagnostics_json=diagnostics_path,
        mode="warn",
    )

    assert report["summary"]["errors"] == 0
    assert report["summary"]["warnings"] > 0
    assert report["legacy_boundary"]["totals"]["in_scope"] == 0
    assert report["legacy_boundary"]["totals"]["excluded"] > 0


def test_governance_enforce_mode_fails_on_metadata_coverage(tmp_path: Path) -> None:
    mod = _load_module()
    policy_path, diagnostics_path = _seed_repo(tmp_path)

    report = mod.run_governance(
        repo_root=tmp_path,
        policy_path=policy_path,
        diagnostics_json=diagnostics_path,
        mode="enforce",
    )

    assert report["summary"]["errors"] > 0
    assert any(item["code"] == "G1101" for item in report["errors"])


def test_governance_fails_when_legacy_keys_present_in_active_instances(tmp_path: Path) -> None:
    mod = _load_module()
    policy_path, diagnostics_path = _seed_repo(tmp_path, legacy_in_active_instances=True)

    report = mod.run_governance(
        repo_root=tmp_path,
        policy_path=policy_path,
        diagnostics_json=diagnostics_path,
        mode="warn",
    )

    assert report["summary"]["errors"] > 0
    assert any(item["code"] == "G3101" for item in report["errors"])
