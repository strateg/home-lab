#!/usr/bin/env python3
"""Shared fixtures for plugin regression tests.

H1.2: Session-scoped compile fixture to reduce redundant subprocess compilations.
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
    payload = yaml.safe_load(TOPOLOGY.read_text(encoding="utf-8")) or {}
    project = payload.get("project", {})
    if isinstance(project, dict):
        active = project.get("active")
        if isinstance(active, str) and active.strip():
            return active.strip()
    return "home-lab"


@pytest.fixture(scope="session")
def compiled_regression_session(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Compile v5 once per session and expose all artifacts for regression tests.

    Returns a dict with:
        - effective_json: Parsed effective topology JSON
        - diagnostics: Parsed diagnostics JSON
        - artifacts_root: Path to generated artifacts directory
        - project_artifacts_root: Path to project-specific artifacts
        - output_json_path: Path to effective.json file
        - diagnostics_json_path: Path to diagnostics.json file
    """
    _ = tmp_path_factory
    workdir = REPO_ROOT / "build" / "test-artifacts" / f"v5-parity-{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True, exist_ok=True)
    generated_root = workdir / "generated"
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
        str(generated_root),
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
        "v5 compile failed for parity fixture\n" f"stdout:\n{completed.stdout}\n" f"stderr:\n{completed.stderr}"
    )

    project_id = _active_project_id()
    effective_payload = json.loads(output_json.read_text(encoding="utf-8"))
    diagnostics_payload = json.loads(diagnostics_json.read_text(encoding="utf-8"))

    return {
        "effective_json": effective_payload,
        "diagnostics": diagnostics_payload,
        "artifacts_root": generated_root,
        "project_artifacts_root": generated_root / project_id,
        "output_json_path": output_json,
        "diagnostics_json_path": diagnostics_json,
        "project_id": project_id,
    }


@pytest.fixture(scope="session")
def generated_artifacts_root(compiled_regression_session: dict[str, Any]) -> Path:
    """Shortcut fixture for project-specific artifacts directory (backward compatible)."""
    return compiled_regression_session["project_artifacts_root"]


@pytest.fixture(scope="session")
def compiled_diagnostics(compiled_regression_session: dict[str, Any]) -> dict[str, Any]:
    """Shortcut fixture for diagnostics JSON."""
    return compiled_regression_session["diagnostics"]


@pytest.fixture(scope="session")
def effective_topology(compiled_regression_session: dict[str, Any]) -> dict[str, Any]:
    """Shortcut fixture for effective topology JSON."""
    return compiled_regression_session["effective_json"]
