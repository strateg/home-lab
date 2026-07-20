#!/usr/bin/env python3
"""Verify session-scoped compile fixture works correctly.

H1.2: This test validates the shared compile fixture infrastructure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def test_session_fixture_provides_effective_json(effective_topology: dict[str, Any]) -> None:
    """Verify fixture provides valid effective topology JSON."""
    assert isinstance(effective_topology, dict)
    assert "version" in effective_topology
    assert "instances" in effective_topology
    assert effective_topology.get("model") == "class-object-instance"


def test_session_fixture_provides_diagnostics(compiled_diagnostics: dict[str, Any]) -> None:
    """Verify fixture provides diagnostics payload."""
    assert isinstance(compiled_diagnostics, dict)
    assert "summary" in compiled_diagnostics
    assert "diagnostics" in compiled_diagnostics


def test_session_fixture_provides_artifacts_root(project_artifacts_root: Path) -> None:
    """Verify fixture provides project artifacts directory."""
    assert isinstance(project_artifacts_root, Path)
    assert project_artifacts_root.exists()
    assert project_artifacts_root.is_dir()


def test_session_fixture_provides_full_context(compiled_topology_session: dict[str, Any]) -> None:
    """Verify fixture provides complete compilation context."""
    required_keys = {
        "effective_json",
        "diagnostics",
        "artifacts_root",
        "output_json_path",
        "diagnostics_json_path",
        "diagnostics_txt_path",
        "project_id",
        "project_artifacts_root",
    }
    assert required_keys.issubset(compiled_topology_session.keys())
    assert compiled_topology_session["project_id"] == "home-lab"
