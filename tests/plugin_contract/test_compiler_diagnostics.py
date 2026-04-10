#!/usr/bin/env python3
"""Unit tests for compiler diagnostic projection compatibility."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from compiler_diagnostics import CompilerDiagnostic, Diagnostic  # noqa: E402
from kernel import PluginDiagnostic  # noqa: E402


def test_compiler_diagnostic_alias_preserves_legacy_name() -> None:
    assert Diagnostic is CompilerDiagnostic


def test_compiler_diagnostic_report_dict_matches_legacy_shape() -> None:
    diagnostic = CompilerDiagnostic(
        code="E4001",
        severity="error",
        stage="validate",
        message="missing relation",
        path="topology.yaml",
        confidence=0.75,
    )

    assert diagnostic.as_dict() == {
        "code": "E4001",
        "severity": "error",
        "stage": "validate",
        "message": "missing relation",
        "path": "topology.yaml",
        "confidence": 0.75,
        "autofix": {"possible": False},
    }


def test_compiler_diagnostic_report_dict_includes_optional_consumer_fields() -> None:
    diagnostic = CompilerDiagnostic(
        code="W4001",
        severity="warning",
        stage="compile",
        message="partial plugin output",
        path="plugin:base.compiler.fixture",
        confidence=0.9,
        hint="check plugin manifest",
        plugin_id="base.compiler.fixture",
    )

    assert diagnostic.as_dict() == {
        "code": "W4001",
        "severity": "warning",
        "stage": "compile",
        "message": "partial plugin output",
        "path": "plugin:base.compiler.fixture",
        "confidence": 0.9,
        "autofix": {"possible": False},
        "hint": "check plugin manifest",
        "plugin_id": "base.compiler.fixture",
    }


def test_plugin_diagnostic_projection_preserves_report_consumer_fields() -> None:
    plugin_diag = PluginDiagnostic(
        code="I4001",
        severity="info",
        stage="validate",
        phase="run",
        message="plugin fixture",
        path="topology.yaml",
        plugin_id="base.validator.fixture",
        confidence=1.0,
        hint="plugin hint",
        source_file="topology.yaml",
        source_line=7,
        source_column=3,
        related=[{"file": "topology.yaml", "note": "related context"}],
    )

    diagnostic = CompilerDiagnostic.from_plugin_diagnostic(plugin_diag)

    assert diagnostic == CompilerDiagnostic(
        code="I4001",
        severity="info",
        stage="validate",
        message="plugin fixture",
        path="topology.yaml",
        confidence=1.0,
        hint="plugin hint",
        plugin_id="base.validator.fixture",
    )
    assert diagnostic.as_dict() == {
        "code": "I4001",
        "severity": "info",
        "stage": "validate",
        "message": "plugin fixture",
        "path": "topology.yaml",
        "confidence": 1.0,
        "autofix": {"possible": False},
        "hint": "plugin hint",
        "plugin_id": "base.validator.fixture",
    }
