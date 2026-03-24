import subprocess
from pathlib import Path


def test_run_fixture_matrix():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "topology-tools" / "run-fixture-matrix.py"
    if not script.exists():
        import pytest

        pytest.skip("run-fixture-matrix.py not present")

    # Run script with --help to ensure it starts without requiring environment
    result = subprocess.run(["python", str(script), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
