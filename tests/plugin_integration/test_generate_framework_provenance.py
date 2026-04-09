#!/usr/bin/env python3
"""Tests for generate-framework-provenance utility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "generate-framework-provenance.py"


def test_generate_framework_provenance_writes_subject_digest(tmp_path: Path) -> None:
    dist_root = tmp_path / "framework-dist" / "infra-topology-framework" / "1.2.3"
    dist_root.mkdir(parents=True, exist_ok=True)
    checksums = dist_root / "checksums.sha256"
    checksums.write_text("abc  file\n", encoding="utf-8")

    output = tmp_path / "framework-dist" / "provenance" / "provenance.json"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dist-root",
            str(tmp_path / "framework-dist"),
            "--output",
            str(output),
            "--repo",
            "https://github.com/strateg/infra-topology-framework",
            "--revision",
            "deadbeef",
            "--release-tag",
            "v1.2.3",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["predicate_type"] == "https://slsa.dev/provenance/v1"
    assert payload["source"]["revision"] == "deadbeef"
    subject = payload["subject"][0]
    assert subject["name"] == "checksums.sha256"
    assert subject["uri"].startswith("file://")
    assert len(subject["digest"]["sha256"]) == 64


def test_generate_framework_provenance_fails_when_checksums_missing(tmp_path: Path) -> None:
    output = tmp_path / "framework-dist" / "provenance" / "provenance.json"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dist-root",
            str(tmp_path / "framework-dist"),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode != 0
