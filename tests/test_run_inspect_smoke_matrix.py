#!/usr/bin/env python3
"""Integration contract tests for inspect smoke matrix runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspection" / "run_inspect_smoke_matrix.py"


def _write_fixture_repo(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    topology_dir = tmp_path / "topology" / "class-modules" / "router"
    build_dir.mkdir(parents=True, exist_ok=True)
    topology_dir.mkdir(parents=True, exist_ok=True)

    (tmp_path / "topology" / "topology.yaml").write_text(
        "\n".join(
            [
                "version: 5.0.0",
                "framework:",
                "  capability_packs: topology/class-modules/L1-foundation/router/capability-packs.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (topology_dir / "capability-packs.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "packs:",
                "  - id: pack.router.home_gateway",
                "    class_ref: class.router",
                "    capabilities:",
                "      - cap.net.interface.ethernet",
                "",
            ]
        ),
        encoding="utf-8",
    )

    effective_payload = {
        "topology_manifest": "topology/topology.yaml",
        "classes": {
            "class.router": {
                "capability_packs": ["pack.router.home_gateway"],
            }
        },
        "objects": {
            "obj.router.ok": {
                "materializes_class": "class.router",
                "enabled_packs": ["pack.router.home_gateway"],
            }
        },
        "instances": {
            "network": [
                {
                    "instance_id": "inst.router.ok",
                    "source_id": "rtr-ok",
                    "layer": "L3",
                    "instance": {
                        "materializes_object": "obj.router.ok",
                        "materializes_class": "class.router",
                    },
                    "instance_data": {},
                }
            ]
        },
    }
    path = build_dir / "effective-topology.json"
    path.write_text(json.dumps(effective_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _run(tmp_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=check,
    )


def test_smoke_matrix_runner_writes_reports_and_passes_when_all_commands_succeed(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)
    json_output = tmp_path / "build" / "diagnostics" / "inspect-smoke-matrix.json"
    text_output = tmp_path / "build" / "diagnostics" / "inspect-smoke-matrix.txt"
    dot_output = tmp_path / "build" / "diagnostics" / "deps-smoke.dot"

    result = _run(
        tmp_path,
        "--effective",
        str(effective),
        "--query",
        "router",
        "--instance",
        "rtr-ok",
        "--json-output",
        str(json_output),
        "--text-output",
        str(text_output),
        "--dot-output",
        str(dot_output),
    )

    assert result.returncode == 0
    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert body["schema_version"] == "adr0095.inspect.smoke-matrix.v1"
    assert body["summary"]["failed"] == 0
    assert body["summary"]["passed"] == body["summary"]["total"] == 10
    assert any(row["name"] == "deps-typed-shadow" and row["status"] == "PASS" for row in body["commands"])
    assert any(row["name"] == "deps-json-typed-shadow" and row["status"] == "PASS" for row in body["commands"])
    assert any(row["name"] == "deps-dot" and row["status"] == "PASS" for row in body["commands"])
    assert dot_output.exists()
    assert "Smoke summary: passed=10 failed=0 total=10" in result.stdout


def test_smoke_matrix_runner_fails_when_command_fails_unless_allow_failures(tmp_path: Path) -> None:
    effective = _write_fixture_repo(tmp_path)
    json_output = tmp_path / "build" / "diagnostics" / "inspect-smoke-matrix-fail.json"
    text_output = tmp_path / "build" / "diagnostics" / "inspect-smoke-matrix-fail.txt"

    result = _run(
        tmp_path,
        "--effective",
        str(effective),
        "--query",
        "router",
        "--instance",
        "missing-instance",
        "--json-output",
        str(json_output),
        "--text-output",
        str(text_output),
        check=False,
    )

    assert result.returncode == 2
    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert body["summary"]["failed"] >= 1
    assert any(row["name"] == "deps" and row["status"] == "FAIL" for row in body["commands"])

    allow_result = _run(
        tmp_path,
        "--effective",
        str(effective),
        "--query",
        "router",
        "--instance",
        "missing-instance",
        "--json-output",
        str(json_output),
        "--text-output",
        str(text_output),
        "--allow-failures",
    )
    assert allow_result.returncode == 0
