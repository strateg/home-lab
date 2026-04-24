#!/usr/bin/env python3
"""Contract tests for ADR trigger reports with canonical group-root instances paths."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module(module_rel_path: str, name: str):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / module_rel_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module: {module_rel_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")


def test_adr0047_report_prefers_canonical_group_paths(tmp_path: Path) -> None:
    mod = _load_module("scripts/validation/report_adr0047_trigger.py", "report_adr0047_trigger")
    instances_root = tmp_path / "projects" / "home-lab" / "topology" / "instances"

    _touch(instances_root / "observability" / "alert-a.yaml")
    _touch(instances_root / "services" / "svc-a.yaml")
    # Also create legacy-style files; canonical roots must take precedence.
    _touch(instances_root / "L6-observability" / "observability" / "alert-legacy.yaml")
    _touch(instances_root / "L5-application" / "services" / "svc-legacy.yaml")

    report = mod._build_report(
        tmp_path,
        alert_threshold=0,
        service_threshold=0,
        project_id="home-lab",
    )

    assert report["alerts_count"] == 1
    assert report["services_count"] == 1
    assert report["alerts_root"].endswith("projects/home-lab/topology/instances/observability")
    assert report["services_root"].endswith("projects/home-lab/topology/instances/services")


def test_adr0083_trigger_snapshot_uses_legacy_fallback_when_canonical_absent(tmp_path: Path) -> None:
    mod = _load_module("scripts/validation/report_adr0083_reactivation.py", "report_adr0083_reactivation")
    instances_root = tmp_path / "projects" / "home-lab" / "topology" / "instances"

    _touch(instances_root / "L6-observability" / "observability" / "alert-legacy.yaml")
    _touch(instances_root / "L5-application" / "services" / "svc-legacy.yaml")

    snapshot = mod._trigger_snapshot(tmp_path, "home-lab")

    assert snapshot["alerts_count"] == 1
    assert snapshot["services_count"] == 1
    assert snapshot["gate"] == "ok"

