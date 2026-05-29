#!/usr/bin/env python3
"""Plugin output determinism tests.

Verifies that plugins produce identical output across multiple runs,
ensuring reproducible builds and stable generated artifacts.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"


def _compile_and_hash(
    run_id: str,
    artifacts_dir: Path,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    """Run compiler and return exit code, file hashes, and diagnostics.

    Returns:
        Tuple of (exit_code, file_hashes, diagnostics_report)
    """
    run_dir = artifacts_dir / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    generated_root = run_dir / "generated"
    output_json = run_dir / "effective.json"
    diagnostics_json = run_dir / "diagnostics.json"
    diagnostics_txt = run_dir / "diagnostics.txt"

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

    file_hashes: dict[str, str] = {}
    if generated_root.exists():
        for path in sorted(generated_root.rglob("*")):
            if path.is_file():
                rel_path = str(path.relative_to(generated_root))
                content = path.read_bytes()
                file_hashes[rel_path] = hashlib.sha256(content).hexdigest()

    diagnostics_report: dict[str, Any] = {}
    if diagnostics_json.exists():
        diagnostics_report = json.loads(diagnostics_json.read_text(encoding="utf-8"))

    return completed.returncode, file_hashes, diagnostics_report


def test_plugin_output_determinism(tmp_path: Path) -> None:
    """Two consecutive compiles must produce identical output.

    This test verifies:
    1. Both runs complete successfully
    2. All generated files have identical content (SHA256 match)
    3. Plugin execution is reproducible across runs
    """
    artifacts_dir = REPO_ROOT / "build" / "test-artifacts" / tmp_path.name

    # Run 1
    exit1, hashes1, diag1 = _compile_and_hash("a", artifacts_dir)
    assert exit1 == 0, f"First compile failed with exit code {exit1}"

    # Run 2
    exit2, hashes2, diag2 = _compile_and_hash("b", artifacts_dir)
    assert exit2 == 0, f"Second compile failed with exit code {exit2}"

    # Compare file sets
    files1 = set(hashes1.keys())
    files2 = set(hashes2.keys())

    only_in_run1 = files1 - files2
    only_in_run2 = files2 - files1

    assert not only_in_run1, f"Files only in run 1: {only_in_run1}"
    assert not only_in_run2, f"Files only in run 2: {only_in_run2}"

    # Compare file contents
    mismatches: list[str] = []
    for path in sorted(files1):
        if hashes1[path] != hashes2[path]:
            mismatches.append(path)

    assert not mismatches, (
        f"Determinism violation: {len(mismatches)} files differ between runs:\n"
        + "\n".join(f"  - {p}" for p in mismatches[:20])
        + (f"\n  ... and {len(mismatches) - 20} more" if len(mismatches) > 20 else "")
    )


def test_plugin_diagnostics_determinism(tmp_path: Path) -> None:
    """Plugin diagnostics must be deterministic across runs.

    Diagnostic codes and counts should be identical, though timestamps may differ.
    """
    artifacts_dir = REPO_ROOT / "build" / "test-artifacts" / tmp_path.name

    exit1, _, diag1 = _compile_and_hash("c", artifacts_dir)
    assert exit1 == 0

    exit2, _, diag2 = _compile_and_hash("d", artifacts_dir)
    assert exit2 == 0

    # Extract diagnostic codes (ignore timestamps and durations)
    def extract_codes(report: dict[str, Any]) -> list[str]:
        diagnostics = report.get("diagnostics", [])
        return sorted(d.get("code", "") for d in diagnostics if isinstance(d, dict))

    codes1 = extract_codes(diag1)
    codes2 = extract_codes(diag2)

    assert codes1 == codes2, (
        f"Diagnostic codes differ between runs:\n"
        f"Run 1: {codes1[:10]}...\n"
        f"Run 2: {codes2[:10]}..."
    )


def test_generated_file_count_stable(tmp_path: Path) -> None:
    """Generated file count must be stable across runs."""
    artifacts_dir = REPO_ROOT / "build" / "test-artifacts" / tmp_path.name

    exit1, hashes1, _ = _compile_and_hash("e", artifacts_dir)
    assert exit1 == 0

    exit2, hashes2, _ = _compile_and_hash("f", artifacts_dir)
    assert exit2 == 0

    count1 = len(hashes1)
    count2 = len(hashes2)

    assert count1 == count2, (
        f"Generated file count differs: run1={count1}, run2={count2}"
    )
    assert count1 > 0, "No files were generated"
