#!/usr/bin/env python3
"""Shared fixtures for plugin regression tests."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPILER = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "v5" / "topology" / "topology.yaml"


def _active_project_id() -> str:
    payload = yaml.safe_load(TOPOLOGY.read_text(encoding="utf-8")) or {}
    project = payload.get("project", {})
    if isinstance(project, dict):
        active = project.get("active")
        if isinstance(active, str) and active.strip():
            return active.strip()
    return "home-lab"


@pytest.fixture(scope="session")
def generated_artifacts_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Compile v5 once and expose generated artifact root for parity checks."""
    _ = tmp_path_factory
    workdir = REPO_ROOT / "v5-build" / "test-artifacts" / f"v5-parity-{uuid.uuid4().hex[:8]}"
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
        "v5 compile failed for parity fixture\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return generated_root / _active_project_id()
