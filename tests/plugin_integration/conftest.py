#!/usr/bin/env python3
"""Shared fixtures for plugin integration tests.

H1.2: Session-scoped compile fixture to reduce redundant subprocess compilations.
Read-only tests should use these fixtures instead of spawning independent compiles.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"


def _active_project_id() -> str:
    """Extract active project ID from topology manifest."""
    payload = yaml.safe_load(TOPOLOGY.read_text(encoding="utf-8")) or {}
    project = payload.get("project", {})
    if isinstance(project, dict):
        active = project.get("active")
        if isinstance(active, str) and active.strip():
            return active.strip()
    return "home-lab"


@pytest.fixture(scope="session")
def compiled_topology_session(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Compile topology once per session and expose artifacts for read-only tests.

    Returns a dict with:
        - effective_json: Parsed effective topology JSON
        - diagnostics: Parsed diagnostics JSON
        - artifacts_root: Path to generated artifacts directory
        - output_json_path: Path to effective.json file
        - diagnostics_json_path: Path to diagnostics.json file
        - diagnostics_txt_path: Path to diagnostics.txt file
        - project_id: Active project ID
        - project_artifacts_root: Path to project-specific artifacts

    Use this fixture for tests that only READ compiled output.
    Tests that need isolated/modified compilation should use their own subprocess.
    """
    _ = tmp_path_factory
    workdir = REPO_ROOT / "build" / "test-artifacts" / f"integration-session-{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True, exist_ok=True)

    artifacts_root = workdir / "generated"
    output_json = workdir / "effective.json"
    diagnostics_json = workdir / "diagnostics.json"
    diagnostics_txt = workdir / "diagnostics.txt"

    cmd = [
        sys.executable,
        str(COMPILER),
        "--topology",
        str(TOPOLOGY.relative_to(REPO_ROOT).as_posix()),
        "--secrets-mode",
        "passthrough",
        "--strict-model-lock",
        "--artifacts-root",
        str(artifacts_root),
        "--output-json",
        str(output_json),
        "--diagnostics-json",
        str(diagnostics_json),
        "--diagnostics-txt",
        str(diagnostics_txt),
    ]

    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, (
        "Session compile failed for plugin_integration fixture\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )

    project_id = _active_project_id()
    effective_payload = json.loads(output_json.read_text(encoding="utf-8"))
    diagnostics_payload = json.loads(diagnostics_json.read_text(encoding="utf-8"))

    return {
        "effective_json": effective_payload,
        "diagnostics": diagnostics_payload,
        "artifacts_root": artifacts_root,
        "output_json_path": output_json,
        "diagnostics_json_path": diagnostics_json,
        "diagnostics_txt_path": diagnostics_txt,
        "project_id": project_id,
        "project_artifacts_root": artifacts_root / project_id,
    }


@pytest.fixture(scope="session")
def effective_topology(compiled_topology_session: dict[str, Any]) -> dict[str, Any]:
    """Shortcut fixture for just the effective topology JSON."""
    return compiled_topology_session["effective_json"]


@pytest.fixture(scope="session")
def compiled_diagnostics(compiled_topology_session: dict[str, Any]) -> dict[str, Any]:
    """Shortcut fixture for just the diagnostics JSON."""
    return compiled_topology_session["diagnostics"]


@pytest.fixture(scope="session")
def project_artifacts_root(compiled_topology_session: dict[str, Any]) -> Path:
    """Shortcut fixture for project-specific artifacts directory."""
    return compiled_topology_session["project_artifacts_root"]
