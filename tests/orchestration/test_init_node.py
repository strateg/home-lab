from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import scripts.orchestration.deploy.init_node as init_node_module  # noqa: E402
from scripts.orchestration.deploy.bundle import create_bundle  # noqa: E402
from scripts.orchestration.deploy.init_node import main, parse_args, resolve_state_path, validate_args  # noqa: E402


def _create_test_bundle(tmp_path: Path) -> tuple[Path, str]:
    repo_root = tmp_path / "repo"
    generated_root = repo_root / "generated" / "home-lab"
    bundles_root = repo_root / ".work" / "deploy" / "bundles"
    bootstrap_file = generated_root / "bootstrap" / "rtr-a" / "netinstall" / "init.rsc"
    bootstrap_file.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_file.write_text("# bootstrap\n", encoding="utf-8")
    info = create_bundle(project_id="home-lab", generated_root=generated_root, bundles_root=bundles_root)
    return repo_root, info.bundle_id


def test_parse_args_supports_help() -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--help"])
    assert exc.value.code == 0


def test_validate_args_requires_action() -> None:
    args = parse_args([])
    with pytest.raises(ValueError, match="Select one action"):
        validate_args(args)


def test_validate_args_requires_bundle_for_node_execution() -> None:
    args = parse_args(["--node", "rtr-a"])
    with pytest.raises(ValueError, match="Bundle-based execution requires"):
        validate_args(args)


def test_validate_args_allows_status_without_bundle() -> None:
    args = parse_args(["--status"])
    validate_args(args)


def test_validate_args_requires_confirm_for_reset() -> None:
    args = parse_args(["--node", "rtr-a", "--bundle", "b-1", "--reset"])
    with pytest.raises(ValueError, match="E9720"):
        validate_args(args)


def test_main_status_reports_empty_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = tmp_path / "repo"

    rc = main(["--repo-root", str(repo_root), "--project-id", "home-lab", "--status"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "empty"
    assert payload["state_path"] == str(resolve_state_path(repo_root=repo_root, project_id="home-lab"))


def test_main_node_action_bootstraps_state_and_emits_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)

    rc = main(
        [
            "--repo-root",
            str(repo_root),
            "--project-id",
            "home-lab",
            "--bundle",
            bundle_id,
            "--node",
            "rtr-a",
            "--plan-only",
            "--skip-environment-check",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "planned"
    assert payload["mode"] == "node"
    assert payload["selected_nodes"] == ["rtr-a"]
    state_path = Path(payload["state_path"])
    assert state_path.exists()


def test_main_returns_environment_error_when_check_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    monkeypatch.setattr(
        init_node_module,
        "check_deploy_environment",
        lambda **kwargs: SimpleNamespace(
            ready=False,
            platform="Windows",
            runner="wsl",
            issues=["runner unavailable"],
        ),
    )
    rc = main(
        [
            "--repo-root",
            str(repo_root),
            "--project-id",
            "home-lab",
            "--bundle",
            bundle_id,
            "--node",
            "rtr-a",
            "--plan-only",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "environment-error"
    assert payload["platform"] == "Windows"
    assert payload["runner"] == "wsl"
