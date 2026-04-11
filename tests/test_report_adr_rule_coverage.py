#!/usr/bin/env python3
"""Tests for ADR0096 ADR-to-rule coverage reporting."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "validation" / "report_adr_rule_coverage.py"
    spec = importlib.util.spec_from_file_location("report_adr_rule_coverage", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load report_adr_rule_coverage module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repository_adr_rule_coverage_report_builds() -> None:
    mod = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    rule_map = yaml.safe_load((repo_root / "docs" / "ai" / "ADR-RULE-MAP.yaml").read_text(encoding="utf-8"))
    register_adrs = mod._extract_register_adrs(repo_root / "adr" / "REGISTER.md")

    report = mod._build_report(rule_map=rule_map, register_adrs=register_adrs)

    assert report["generated_from_adr"] == "0096"
    assert report["rule_count"] >= 16
    assert report["rule_pack_count"] >= 8
    assert report["covered_source_adr_count"] >= 1
    assert any(entry["adr"] == "0096" for entry in report["adr_coverage"])
    assert report["orphaned_source_adrs"] == []


def test_report_highlights_uncovered_and_orphaned_adrs(tmp_path: Path) -> None:
    mod = _load_module()

    register_path = tmp_path / "REGISTER.md"
    register_path.write_text(
        "\n".join(
            [
                "| [0001](0001.md) | One | Accepted | 2026-01-01 | - | - |",
                "| [0002](0002.md) | Two | Accepted | 2026-01-01 | - | - |",
                "| [0003](0003.md) | Three | Accepted | 2026-01-01 | - | - |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rule_map = {
        "schema_version": 1,
        "generated_from_adr": "0096",
        "purpose": "Temporary coverage fixture.",
        "adapters": {"files": ["AGENTS.md"], "required_refs": ["docs/ai/AGENT-RULEBOOK.md"]},
        "rule_packs": {
            "plugin-runtime": {
                "path": "docs/ai/rules/plugin-runtime.md",
                "source_adr": ["0001", "9999"],
                "files_glob": ["topology-tools/plugins/**"],
            }
        },
        "rules": [
            {
                "id": "PLG-001",
                "scope": "plugin-runtime",
                "trigger": "Any plugin change for test coverage",
                "must": ["Keep source_adr coverage visible."],
                "never": ["Do not hide reverse ADR coverage."],
                "validate": ["pytest tests/test_report_adr_rule_coverage.py -q"],
                "source_adr": ["0002", "9999"],
            }
        ],
    }

    report = mod._build_report(rule_map=rule_map, register_adrs=mod._extract_register_adrs(register_path))

    assert report["covered_source_adr_count"] == 3
    assert report["covered_register_adr_count"] == 2
    assert report["uncovered_register_adrs"] == ["0003"]
    assert report["orphaned_source_adrs"] == ["9999"]

    coverage_by_adr = {entry["adr"]: entry for entry in report["adr_coverage"]}
    assert coverage_by_adr["0001"]["rule_packs"] == ["plugin-runtime"]
    assert coverage_by_adr["0001"]["rule_ids"] == []
    assert coverage_by_adr["0002"]["rule_ids"] == ["PLG-001"]
    assert coverage_by_adr["9999"]["rule_ids"] == ["PLG-001"]
    assert coverage_by_adr["9999"]["rule_packs"] == ["plugin-runtime"]


def test_cli_writes_output_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "agent-rule-coverage.json"
    script = repo_root / "scripts" / "validation" / "report_adr_rule_coverage.py"

    run = subprocess.run(
        [sys.executable, str(script), "--output-json", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
        cwd=repo_root,
    )

    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["generated_from_adr"] == "0096"
    assert "adr_coverage" in payload
