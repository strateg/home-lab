"""
Tests for verify-framework-lock.py CLI script.

Validates argument parsing and main execution logic.
"""

# Add topology-tools to path
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TOPOLOGY_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(TOPOLOGY_TOOLS))

# Import module with dashes in name
spec = importlib.util.spec_from_file_location(
    "verify_framework_lock",
    TOPOLOGY_TOOLS / "verify-framework-lock.py",
)
assert spec and spec.loader
verify_module = importlib.util.module_from_spec(spec)
sys.modules["verify_framework_lock"] = verify_module  # Register for patch() to find
spec.loader.exec_module(verify_module)

main = verify_module.main
parse_args = verify_module.parse_args


@pytest.fixture
def mock_verify_framework_lock():
    """Mock the verify_framework_lock function."""
    with patch("verify_framework_lock.verify_framework_lock") as mock:
        # Default: successful verification
        result = MagicMock()
        result.ok = True
        result.diagnostics = []
        mock.return_value = result
        yield mock


@pytest.fixture
def mock_resolve_paths():
    """Mock the resolve_paths function."""
    with patch("verify_framework_lock.resolve_paths") as mock:
        paths = MagicMock()
        paths.repo_root = Path("/test/repo")
        paths.project_root = Path("/test/repo/projects/test-project")
        paths.lock_path = Path("/test/repo/projects/test-project/framework.lock.yaml")
        mock.return_value = paths
        yield mock


def test_parse_args_defaults():
    """Test parse_args with default arguments."""
    with patch("sys.argv", ["verify-framework-lock.py"]):
        args = parse_args()

    assert args.repo_root is not None
    assert isinstance(args.repo_root, Path)
    assert args.topology is not None
    assert isinstance(args.topology, Path)
    assert args.project == ""
    assert args.project_root is None
    assert args.strict is False
    assert args.enforce_package_trust is False


def test_parse_args_with_custom_paths(tmp_path: Path):
    """Test parse_args with custom paths."""
    custom_repo = tmp_path / "custom-repo"
    custom_topology = tmp_path / "custom-topology.yaml"

    with patch(
        "sys.argv",
        [
            "verify-framework-lock.py",
            "--repo-root",
            str(custom_repo),
            "--topology",
            str(custom_topology),
        ],
    ):
        args = parse_args()

    assert args.repo_root == custom_repo
    assert args.topology == custom_topology


def test_parse_args_with_strict_mode():
    """Test parse_args with --strict flag."""
    with patch("sys.argv", ["verify-framework-lock.py", "--strict"]):
        args = parse_args()

    assert args.strict is True


def test_parse_args_with_package_trust_flags():
    """Test parse_args with package trust verification flags."""
    with patch(
        "sys.argv",
        [
            "verify-framework-lock.py",
            "--enforce-package-trust",
            "--verify-package-artifact-files",
            "--verify-package-signature",
        ],
    ):
        args = parse_args()

    assert args.enforce_package_trust is True
    assert args.verify_package_artifact_files is True
    assert args.verify_package_signature is True


def test_parse_args_with_custom_cosign_bin():
    """Test parse_args with custom cosign binary path."""
    with patch("sys.argv", ["verify-framework-lock.py", "--cosign-bin", "/usr/local/bin/cosign"]):
        args = parse_args()

    assert args.cosign_bin == "/usr/local/bin/cosign"


def test_main_success(mock_verify_framework_lock, mock_resolve_paths, capsys):
    """Test main() with successful verification."""
    with patch("sys.argv", ["verify-framework-lock.py"]):
        exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Framework lock verification: OK" in captured.out


def test_main_with_diagnostics_but_ok(mock_verify_framework_lock, mock_resolve_paths, capsys):
    """Test main() with diagnostics but overall OK status."""
    # Create a diagnostic
    diag = MagicMock()
    diag.severity = "warning"
    diag.code = "W001"
    diag.path = "/test/path"
    diag.message = "Test warning message"

    # Set up mock to return diagnostics but ok=True
    result = MagicMock()
    result.ok = True
    result.diagnostics = [diag]
    mock_verify_framework_lock.return_value = result

    with patch("sys.argv", ["verify-framework-lock.py"]):
        exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "WARNING W001 /test/path: Test warning message" in captured.out


def test_main_with_errors(mock_verify_framework_lock, mock_resolve_paths, capsys):
    """Test main() with verification errors."""
    # Create error diagnostics
    error = MagicMock()
    error.severity = "error"
    error.code = "E001"
    error.path = "/test/path"
    error.message = "Test error message"

    # Set up mock to return errors and ok=False
    result = MagicMock()
    result.ok = False
    result.diagnostics = [error]
    mock_verify_framework_lock.return_value = result

    with patch("sys.argv", ["verify-framework-lock.py"]):
        exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ERROR E001 /test/path: Test error message" in captured.out


def test_main_calls_verify_with_correct_args(mock_verify_framework_lock, mock_resolve_paths):
    """Test that main() calls verify_framework_lock with correct arguments."""
    with patch(
        "sys.argv",
        [
            "verify-framework-lock.py",
            "--strict",
            "--enforce-package-trust",
            "--verify-package-artifact-files",
            "--cosign-bin",
            "/custom/cosign",
        ],
    ):
        main()

    # Verify the call
    mock_verify_framework_lock.assert_called_once()
    call_kwargs = mock_verify_framework_lock.call_args.kwargs

    assert call_kwargs["strict"] is True
    assert call_kwargs["enforce_package_trust"] is True
    assert call_kwargs["verify_package_artifact_files"] is True
    assert call_kwargs["verify_package_signature"] is False  # Not specified in argv
    assert call_kwargs["cosign_bin"] == "/custom/cosign"


def test_main_with_project_override(mock_verify_framework_lock, mock_resolve_paths):
    """Test main() with --project override."""
    with patch("sys.argv", ["verify-framework-lock.py", "--project", "custom-project"]):
        main()

    # Verify resolve_paths was called with project_id
    mock_resolve_paths.assert_called_once()
    call_kwargs = mock_resolve_paths.call_args.kwargs
    assert call_kwargs["project_id"] == "custom-project"
