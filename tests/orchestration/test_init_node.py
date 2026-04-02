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
from scripts.orchestration.deploy.logging import resolve_init_node_log_path  # noqa: E402


class _FakeRunner:
    def __init__(self, name: str = "native") -> None:
        self.name = name
        self.staged_bundle: str = ""
        self.cleanup_calls: list[str] = []
        self.run_calls: list[list[str]] = []

    def stage_bundle(self, bundle_path: str | Path) -> str:
        self.staged_bundle = str(Path(bundle_path))
        return str(Path(bundle_path))

    def cleanup_workspace(self, workspace_ref: str) -> None:
        self.cleanup_calls.append(workspace_ref)

    def check_tool(self, tool: str, workspace_ref: str | None = None) -> bool:
        _ = workspace_ref
        return True

    def run(self, cmd: list[str], workspace_ref: str | None = None) -> SimpleNamespace:
        _ = workspace_ref
        self.run_calls.append(list(cmd))
        return SimpleNamespace(exit_code=0, stdout="", stderr="", success=True)


def _install_fake_runner(monkeypatch: pytest.MonkeyPatch, runner: _FakeRunner | None = None) -> _FakeRunner:
    fake = runner or _FakeRunner()
    monkeypatch.setattr(init_node_module, "get_runner", lambda *args, **kwargs: fake)
    return fake


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


def test_main_non_plan_mode_executes_and_marks_node_failed_with_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    fake_runner = _install_fake_runner(monkeypatch)

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
            "--skip-environment-check",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "failed"
    assert payload["selected_nodes"] == ["rtr-a"]
    assert payload["failed_count"] == 1
    assert payload["results"][0]["node"] == "rtr-a"
    assert payload["results"][0]["error_code"] == "E9758"
    assert payload["runner"] == fake_runner.name
    assert payload["workspace_ref"].endswith(bundle_id)

    state_path = resolve_state_path(repo_root=repo_root, project_id="home-lab")
    state_payload = init_node_module._load_yaml_mapping(state_path)
    row = next(item for item in state_payload["nodes"] if item["id"] == "rtr-a")
    assert row["status"] == "failed"
    assert row["attempt_count"] == 1
    log_path = resolve_init_node_log_path(repo_root=repo_root, project_id="home-lab")
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "node-execute-adapter-failed" in log_text
    assert fake_runner.cleanup_calls
    assert fake_runner.cleanup_calls[-1].endswith(bundle_id)


def test_main_verify_only_marks_initialized_node_as_verified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    fake_runner = _install_fake_runner(monkeypatch)
    plan_rc = main(
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
    assert plan_rc == 0
    _ = capsys.readouterr().out

    state_path = resolve_state_path(repo_root=repo_root, project_id="home-lab")
    state_payload = init_node_module._load_yaml_mapping(state_path)
    row = next(item for item in state_payload["nodes"] if item["id"] == "rtr-a")
    row["status"] = "initialized"
    init_node_module._write_yaml_atomic(state_path, state_payload)

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
            "--verify-only",
            "--skip-environment-check",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "executed"
    assert payload["verify_only"] is True
    assert payload["success_count"] == 1
    assert payload["results"][0]["status"] == "success"
    assert payload["runner"] == fake_runner.name
    assert payload["workspace_ref"].endswith(bundle_id)

    state_payload = init_node_module._load_yaml_mapping(state_path)
    row = next(item for item in state_payload["nodes"] if item["id"] == "rtr-a")
    assert row["status"] == "verified"
    log_path = resolve_init_node_log_path(repo_root=repo_root, project_id="home-lab")
    assert "node-verify-success" in log_path.read_text(encoding="utf-8")


def test_main_verify_only_fails_for_pending_node(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    _install_fake_runner(monkeypatch)
    plan_rc = main(
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
    assert plan_rc == 0
    _ = capsys.readouterr().out

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
            "--verify-only",
            "--skip-environment-check",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "failed"
    assert payload["results"][0]["error_code"] == "E9737"


def test_main_returns_node_not_found_for_unknown_node(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
            "unknown-node",
            "--plan-only",
            "--skip-environment-check",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "node-not-found"
    assert payload["node"] == "unknown-node"
    assert payload["available_nodes"] == ["rtr-a"]


def test_main_returns_runner_error_when_runner_resolution_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    monkeypatch.setattr(
        init_node_module, "get_runner", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("x"))
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
            "--skip-environment-check",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "runner-error"


def test_main_returns_runner_stage_error_when_bundle_staging_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    fake_runner = _FakeRunner()

    def _raise_stage(bundle_path: str | Path) -> str:
        raise RuntimeError("stage failed")

    fake_runner.stage_bundle = _raise_stage  # type: ignore[assignment]
    _install_fake_runner(monkeypatch, fake_runner)

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
            "--skip-environment-check",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "runner-stage-error"
    assert payload["runner"] == fake_runner.name


def test_main_returns_runner_tools_error_when_tools_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    fake_runner = _FakeRunner(name="docker:homelab-toolchain:latest")
    _install_fake_runner(monkeypatch, fake_runner)
    monkeypatch.setattr(
        init_node_module,
        "check_runner_tools",
        lambda runner, tools, workspace_ref=None: {"bash": True, "ssh": False, "scp": False},
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
            "--skip-environment-check",
            "--bootstrap-runner-tools",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "runner-tools-error"
    assert payload["missing_tools"] == ["ssh", "scp"]


def test_main_bootstrap_runner_tools_runs_install_command_before_execute(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root, bundle_id = _create_test_bundle(tmp_path)
    fake_runner = _FakeRunner()
    _install_fake_runner(monkeypatch, fake_runner)
    call_counter = {"value": 0}

    def _check_runner_tools(runner, tools, workspace_ref=None):
        _ = (runner, tools, workspace_ref)
        call_counter["value"] += 1
        if call_counter["value"] == 1:
            return {"bash": True, "ssh": False}
        return {"bash": True, "ssh": True}

    monkeypatch.setattr(init_node_module, "check_runner_tools", _check_runner_tools)

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
            "--skip-environment-check",
            "--bootstrap-runner-tools",
            "--runner-tools",
            "bash,ssh",
            "--runner-tools-install-command",
            "echo install-tools",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "failed"
    assert payload["results"][0]["error_code"] == "E9758"
    assert ["bash", "-lc", "echo install-tools"] in fake_runner.run_calls
