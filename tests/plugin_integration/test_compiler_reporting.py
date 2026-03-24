#!/usr/bin/env python3
"""Tests for compiler reporting path serialization."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from compiler_reporting import write_diagnostics_report


@dataclass
class _Diag:
    code: str
    severity: str
    stage: str
    message: str
    path: str
    hint: str | None = None
    plugin_id: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "path": self.path,
        }


def test_write_diagnostics_report_supports_paths_outside_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "project"
    repo_root.mkdir(parents=True, exist_ok=True)
    topology_path = repo_root / "topology.yaml"
    output_json = repo_root / "generated" / "effective-topology.json"
    diagnostics_json = repo_root / "generated" / "diagnostics.json"
    diagnostics_txt = repo_root / "generated" / "diagnostics.txt"
    topology_path.write_text("version: 5.0.0\n", encoding="utf-8")

    external_catalog = tmp_path / "framework" / "topology-tools" / "data" / "error-catalog.yaml"
    external_catalog.parent.mkdir(parents=True, exist_ok=True)
    external_catalog.write_text("version: 1\ncodes: {}\n", encoding="utf-8")

    total, errors, warnings, infos = write_diagnostics_report(
        diagnostics=[_Diag(code="I0001", severity="info", stage="load", message="ok", path="topology.yaml")],
        diagnostics_json=diagnostics_json,
        diagnostics_txt=diagnostics_txt,
        topology_path=topology_path,
        error_catalog_path=external_catalog,
        output_json=output_json,
        repo_root=repo_root,
        now_iso=lambda: "2026-03-20T00:00:00+00:00",
    )

    assert (total, errors, warnings, infos) == (1, 0, 0, 1)
    report = json.loads(diagnostics_json.read_text(encoding="utf-8"))
    assert report["inputs"]["topology"] == "topology.yaml"
    assert report["outputs"]["effective_json"] == "generated/effective-topology.json"
    assert report["inputs"]["error_catalog"] == external_catalog.resolve().as_posix()
