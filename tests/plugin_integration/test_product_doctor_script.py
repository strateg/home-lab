#!/usr/bin/env python3
"""Tests for ADR0090 product doctor status resolver."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "orchestration" / "product" / "doctor.py"


def _module():
    spec = importlib.util.spec_from_file_location("product_doctor", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_product_doctor_prefers_operator_readiness_report(tmp_path: Path) -> None:
    module = _module()
    project_id = "home-lab"
    operator_path = tmp_path / "generated" / project_id / "product" / "reports" / "operator-readiness.json"
    operator_path.parent.mkdir(parents=True, exist_ok=True)
    operator_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project_id": project_id,
                "status": "yellow",
                "evidence": {"backup-and-restore": "partial"},
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )

    snapshot = module.resolve_product_doctor_status(repo_root=tmp_path, project_id=project_id)

    assert snapshot["status"] == "yellow"
    assert snapshot["source"] == "operator-readiness"


def test_product_doctor_falls_back_to_profile_state(tmp_path: Path) -> None:
    module = _module()
    profile_state_path = tmp_path / "build" / "diagnostics" / "product-profile-state.json"
    profile_state_path.parent.mkdir(parents=True, exist_ok=True)
    profile_state_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project_id": "home-lab",
                "status": "green",
                "migration_state": "migrated-hard",
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )

    snapshot = module.resolve_product_doctor_status(repo_root=tmp_path, project_id="home-lab")

    assert snapshot["status"] == "green"
    assert snapshot["source"] == "product-profile-state"


def test_product_doctor_returns_red_when_no_evidence_exists(tmp_path: Path) -> None:
    module = _module()

    snapshot = module.resolve_product_doctor_status(repo_root=tmp_path, project_id="home-lab")

    assert snapshot["status"] == "red"
    assert snapshot["source"] == "none"
