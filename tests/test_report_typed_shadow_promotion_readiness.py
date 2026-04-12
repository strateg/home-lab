#!/usr/bin/env python3
"""Contract tests for typed-shadow promotion readiness reporting."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "inspection" / "report_typed_shadow_promotion_readiness.py"


def _load_module(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_gate_files(repo_root: Path) -> None:
    (repo_root / "tests").mkdir(parents=True, exist_ok=True)
    (repo_root / "taskfiles").mkdir(parents=True, exist_ok=True)
    (repo_root / "manuals" / "dev-plane").mkdir(parents=True, exist_ok=True)
    (repo_root / "adr" / "0095-analysis").mkdir(parents=True, exist_ok=True)

    (repo_root / "tests" / "test_inspection_relations.py").write_text(
        "def test_infer_relation_type_classifies_common_domains():\n    pass\n",
        encoding="utf-8",
    )
    (repo_root / "tests" / "test_inspection_json.py").write_text(
        "def test_deps_payload_typed_shadow_preserves_baseline_edge_contract():\n    pass\n",
        encoding="utf-8",
    )
    (repo_root / "tests" / "test_inspect_topology.py").write_text(
        "def test_deps_command_json_typed_shadow_preserves_baseline_edges():\n    pass\n",
        encoding="utf-8",
    )
    (repo_root / "taskfiles" / "validate.yml").write_text(
        "tasks:\n  typed-shadow-gate:\n    cmds: []\n",
        encoding="utf-8",
    )
    (repo_root / "manuals" / "dev-plane" / "DEV-COMMAND-REFERENCE.md").write_text(
        "typed shadow is non-authoritative and reports generic_ref semantics.\n",
        encoding="utf-8",
    )
    (repo_root / "adr" / "0095-topology-inspection-and-introspection-toolkit.md").write_text(
        "Semantic typing remains non-authoritative.\n",
        encoding="utf-8",
    )
    (repo_root / "adr" / "0095-analysis" / "IMPLEMENTATION-PLAN.md").write_text(
        "promotion decision remains pending\n",
        encoding="utf-8",
    )
    (repo_root / "adr" / "0095-analysis" / "SEMANTIC-TYPING-PROMOTION-CRITERIA.md").write_text(
        "## Promotion Decision Rule\n",
        encoding="utf-8",
    )


def test_build_report_marks_ready_when_all_promotion_gates_pass(tmp_path: Path) -> None:
    module = _load_module("typed_shadow_promotion_readiness_contract_pass")
    _seed_gate_files(tmp_path)

    typed_shadow_report = {
        "edge_counts": {"coverage_percent": 100.0},
        "generic_ref_share_percent": 0.5,
        "gates": {"g2_pass": True},
    }
    report = module.build_report(
        repo_root=tmp_path,
        typed_shadow_report=typed_shadow_report,
        typed_shadow_report_source="fixture",
    )

    assert report["schema_version"] == module.READINESS_SCHEMA_VERSION
    assert report["ready_for_promotion"] is True
    assert report["blocking_gates"] == []
    assert report["typed_shadow_report_snapshot"]["coverage_percent"] == 100.0
    assert report["typed_shadow_report_snapshot"]["generic_ref_share_percent"] == 0.5
    assert report["typed_shadow_report_snapshot"]["g2_pass"] is True
    assert "Record promotion decision" in report["recommended_next_step"]


def test_build_report_surfaces_blocking_gates_when_prerequisites_are_missing(tmp_path: Path) -> None:
    module = _load_module("typed_shadow_promotion_readiness_contract_fail")

    typed_shadow_report = {
        "edge_counts": {"coverage_percent": 42.0},
        "generic_ref_share_percent": 58.0,
        "gates": {"g2_pass": False},
    }
    report = module.build_report(
        repo_root=tmp_path,
        typed_shadow_report=typed_shadow_report,
        typed_shadow_report_source="fixture",
    )

    assert report["ready_for_promotion"] is False
    assert set(report["blocking_gates"]) == {
        "g1_contract_stability",
        "g2_coverage_of_meaningful_edges",
        "g3_error_drift_safety",
        "g4_operator_usability",
        "g5_adr_sync",
    }
    assert "Keep typed shadow non-authoritative" in report["recommended_next_step"]


def test_typed_shadow_report_source_prefers_existing_artifact(tmp_path: Path) -> None:
    module = _load_module("typed_shadow_promotion_readiness_source")

    report_path = tmp_path / "typed-shadow-report.json"
    report_path.write_text(
        json.dumps(
            {
                "edge_counts": {"coverage_percent": 99.0},
                "generic_ref_share_percent": 1.0,
                "gates": {"g2_pass": True},
            }
        ),
        encoding="utf-8",
    )
    effective_path = tmp_path / "effective-topology.json"
    effective_path.write_text("{}", encoding="utf-8")

    report, source = module._typed_shadow_report_from_artifact_or_effective(
        typed_shadow_report_path=report_path,
        effective_path=effective_path,
        layer=None,
        group=None,
    )

    assert report["gates"]["g2_pass"] is True
    assert source == str(report_path)


def test_main_returns_2_when_fail_on_not_ready_and_gate_is_blocked(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("typed_shadow_promotion_readiness_main_exit")
    _seed_gate_files(tmp_path)

    report_path = tmp_path / "typed-shadow-report.json"
    report_path.write_text(
        json.dumps(
            {
                "edge_counts": {"coverage_percent": 10.0},
                "generic_ref_share_percent": 90.0,
                "gates": {"g2_pass": False},
            }
        ),
        encoding="utf-8",
    )
    json_output = tmp_path / "out-readiness.json"
    text_output = tmp_path / "out-readiness.txt"

    monkeypatch.setattr(module, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--typed-shadow-report",
            str(report_path),
            "--output-json",
            str(json_output),
            "--output-text",
            str(text_output),
            "--fail-on-not-ready",
        ],
    )

    rc = module.main()

    assert rc == 2
    assert json_output.exists()
    assert text_output.exists()


def test_script_returns_2_for_invalid_typed_shadow_report_json(tmp_path: Path) -> None:
    bad_report = tmp_path / "typed-shadow-report-invalid.json"
    bad_report.write_text("{invalid-json", encoding="utf-8")
    json_output = tmp_path / "readiness.json"
    text_output = tmp_path / "readiness.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--typed-shadow-report",
            str(bad_report),
            "--output-json",
            str(json_output),
            "--output-text",
            str(text_output),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "[inspect][error]" in result.stderr
