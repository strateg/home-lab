#!/usr/bin/env python3
"""Integration contract tests for typed-shadow diagnostics generator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspection" / "generate_typed_shadow_report.py"


def _write_effective_fixture(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "instances": {
            "network": [
                {
                    "instance_id": "inst.router",
                    "source_id": "rtr-main",
                    "layer": "L3",
                    "instance_data": {
                        "network_gateway_ref": "gw-main",
                        "peer_refs": ["svc-api"],
                    },
                    "instance": {},
                },
                {
                    "instance_id": "inst.gateway",
                    "source_id": "gw-main",
                    "layer": "L3",
                    "instance_data": {},
                    "instance": {},
                },
            ],
            "services": [
                {
                    "instance_id": "inst.service.api",
                    "source_id": "svc-api",
                    "layer": "L5",
                    "instance_data": {
                        "runtime_host_ref": "inst.gateway",
                        "storage_volume_ref": "vol-main",
                    },
                    "instance": {},
                },
                {
                    "instance_id": "inst.volume",
                    "source_id": "vol-main",
                    "layer": "L4",
                    "instance_data": {},
                    "instance": {},
                },
            ],
        }
    }
    path = build_dir / "effective-topology.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _run(tmp_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=check,
    )


def test_generate_typed_shadow_report_writes_json_and_text_artifacts(tmp_path: Path) -> None:
    effective = _write_effective_fixture(tmp_path)
    diagnostics_dir = tmp_path / "build" / "diagnostics"
    json_output = diagnostics_dir / "typed-shadow-report.json"
    text_output = diagnostics_dir / "typed-shadow-report.txt"

    result = _run(
        tmp_path,
        "--effective",
        str(effective),
        "--json-output",
        str(json_output),
        "--text-output",
        str(text_output),
    )

    assert result.returncode == 0
    assert json_output.exists()
    assert text_output.exists()
    assert "Wrote typed-shadow JSON report" in result.stdout
    assert "Wrote typed-shadow text report" in result.stdout

    body = json.loads(json_output.read_text(encoding="utf-8"))
    text = text_output.read_text(encoding="utf-8")
    assert body["schema_version"] == "adr0095.inspect.deps.typed-shadow-report.v1"
    assert body["command"] == "typed-shadow-report"
    assert body["gates"]["g2_pass"] is True
    assert "status: PASS" in text


def test_generate_typed_shadow_report_gate_fails_when_thresholds_do_not_pass(tmp_path: Path) -> None:
    effective = _write_effective_fixture(tmp_path)
    diagnostics_dir = tmp_path / "build" / "diagnostics"
    json_output = diagnostics_dir / "typed-shadow-report-gate.json"
    text_output = diagnostics_dir / "typed-shadow-report-gate.txt"

    result = _run(
        tmp_path,
        "--effective",
        str(effective),
        "--json-output",
        str(json_output),
        "--text-output",
        str(text_output),
        "--min-coverage",
        "101",
        "--fail-on-threshold",
        check=False,
    )

    assert result.returncode == 2
    assert "Typed-shadow thresholds failed" in result.stdout

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert body["gates"]["g2_coverage_pass"] is False
    assert body["gates"]["g2_generic_share_pass"] is True
    assert body["gates"]["g2_pass"] is False
