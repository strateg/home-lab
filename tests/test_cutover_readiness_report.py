#!/usr/bin/env python3
"""Contract tests for cutover readiness gate composition."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "topology-tools" / "utils" / "cutover-readiness-report.py"
    spec = importlib.util.spec_from_file_location("cutover_readiness_report", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load cutover-readiness-report module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_gate_commands_quick_mode_excludes_parity_and_pytest_v5():
    mod = _load_module()
    gate_names = [gate for gate, _, _ in mod._gate_commands(Path("."), quick=True)]  # noqa: SLF001
    assert "verify_framework_lock" in gate_names
    assert "rehearse_rollback" in gate_names
    assert "validate_compatibility_matrix" in gate_names
    assert "audit_strict_entrypoints" in gate_names
    assert "pytest_v4_v5_parity" not in gate_names
    assert "pytest_v5" not in gate_names
    assert "lane_validate_v5" not in gate_names
    assert "adr0088_governance" not in gate_names


def test_gate_commands_full_mode_includes_parity_and_v5_suite():
    mod = _load_module()
    gate_names = [gate for gate, _, _ in mod._gate_commands(Path("."), quick=False)]  # noqa: SLF001
    assert "pytest_v4_v5_parity" in gate_names
    assert "pytest_v5" in gate_names
    assert "lane_validate_v5" in gate_names
    assert "adr0088_governance" in gate_names
