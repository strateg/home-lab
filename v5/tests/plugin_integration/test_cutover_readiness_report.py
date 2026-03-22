#!/usr/bin/env python3
"""Integration test for cutover readiness report utility."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "v5" / "topology-tools" / "cutover-readiness-report.py"
GENERATE_LOCK = REPO_ROOT / "v5" / "topology-tools" / "generate-framework-lock.py"


def _load_cutover_module() -> Any:
    spec = importlib.util.spec_from_file_location("cutover_readiness_report", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load cutover readiness module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cutover_readiness_report_quick_mode(tmp_path: Path) -> None:
    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATE_LOCK),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + "\n" + generated.stderr

    output_json = tmp_path / "cutover-readiness.json"
    cutover_state_json = tmp_path / "cutover-state-open.json"
    cutover_state_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "adr": "0076",
                "production_cutover_complete": False,
            }
        ),
        encoding="utf-8",
    )
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
            "--output-json",
            str(output_json),
            "--cutover-state-json",
            str(cutover_state_json),
            "--quick",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert output_json.exists()
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["quick"] is True
    assert report["ready_for_cutover"] is True
    assert report["production_cutover_complete"] is False
    assert report["ready_for_operational_baseline"] is False
    assert report["summary"]["failed"] == 0
    assert report["pending_external_steps"] == ["production cutover announcement and freeze switch"]


def test_cutover_readiness_report_marks_operational_baseline_when_manual_step_done(tmp_path: Path) -> None:
    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATE_LOCK),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + "\n" + generated.stderr

    output_json = tmp_path / "cutover-readiness-complete.json"
    cutover_state_json = tmp_path / "cutover-state-complete.json"
    cutover_state_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "adr": "0076",
                "production_cutover_complete": True,
                "completed_at": "2026-03-20T20:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
            "--output-json",
            str(output_json),
            "--cutover-state-json",
            str(cutover_state_json),
            "--quick",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["ready_for_cutover"] is True
    assert report["production_cutover_complete"] is True
    assert report["ready_for_operational_baseline"] is True
    assert report["pending_external_steps"] == []


def test_cutover_readiness_report_non_quick_includes_v4_v5_parity_gate() -> None:
    module = _load_cutover_module()
    gate_names = [name for name, _command, _env in module._gate_commands(REPO_ROOT, quick=False)]
    assert "pytest_v4_v5_parity" in gate_names

    parity_entry = next(
        (command for name, command, _env in module._gate_commands(REPO_ROOT, quick=False) if name == "pytest_v4_v5_parity"),
        None,
    )
    assert parity_entry is not None
    assert "v5/tests/plugin_integration/test_network_ip_overlap_v4_v5_parity.py" in parity_entry
    assert "v5/tests/plugin_integration/test_network_reserved_ranges_v4_v5_parity.py" in parity_entry
    assert "v5/tests/plugin_integration/test_network_ip_allocation_host_os_refs_v4_v5_parity.py" in parity_entry
