from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


def _load_lane_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "orchestration" / "lane.py"
    spec = importlib.util.spec_from_file_location("lane_module_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_args_accepts_timeout_and_collect_all() -> None:
    lane = _load_lane_module()

    args = lane.parse_args(["validate-v5", "--step-timeout", "30", "--collect-all-errors"])

    assert args.command == "validate-v5"
    assert args.step_timeout == 30
    assert args.collect_all_errors is True


def test_lane_exit_code_values_are_stable() -> None:
    lane = _load_lane_module()

    assert int(lane.LaneExitCode.OK) == 0
    assert int(lane.LaneExitCode.VALIDATION_ERROR) == 1
    assert int(lane.LaneExitCode.WARNING) == 2
    assert int(lane.LaneExitCode.INFRA_ERROR) == 3


def test_run_passes_timeout_to_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    lane = _load_lane_module()
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], cwd: Path, check: bool, timeout: float | None) -> None:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check
        captured["timeout"] = timeout

    monkeypatch.setattr(lane.subprocess, "run", fake_run)

    lane.run([lane.PYTHON, "-V"], timeout=15)

    assert captured == {
        "cmd": [lane.PYTHON, "-V"],
        "cwd": lane.ROOT,
        "check": True,
        "timeout": 15,
    }


def test_validate_v5_collect_all_errors_runs_all_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    lane = _load_lane_module()
    calls: list[tuple[list[str], float | None]] = []

    def fake_run(cmd: list[str], *, timeout: float | None = None) -> None:
        calls.append((cmd, timeout))
        if cmd[1].endswith("validate_v5_scaffold.py"):
            raise subprocess.CalledProcessError(returncode=2, cmd=cmd)
        if cmd[1].endswith("validate_adr0088_governance.py"):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(lane, "run", fake_run)

    with pytest.raises(lane.LaneAggregateError) as excinfo:
        lane._run_validate_v5_with_mode("passthrough", step_timeout=45, collect_all_errors=True)

    assert len(calls) == 6
    assert all(timeout == 45 for _, timeout in calls)
    assert excinfo.value.has_timeout is True
    assert excinfo.value.failures == (
        f"{lane.PYTHON} scripts/validation/validate_v5_scaffold.py exited with code 2",
        f"{lane.PYTHON} scripts/validation/validate_adr0088_governance.py --diagnostics-json build/diagnostics/report.json --output-json {lane.ADR0088_GOVERNANCE_REPORT_JSON} --mode enforce timed out after 45s",
    )


def test_validate_v5_default_mode_stops_on_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    lane = _load_lane_module()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, timeout: float | None = None) -> None:
        calls.append(cmd)
        if cmd[1].endswith("validate_v5_scaffold.py"):
            raise subprocess.CalledProcessError(returncode=3, cmd=cmd)

    monkeypatch.setattr(lane, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        lane._run_validate_v5_with_mode("inject", step_timeout=12, collect_all_errors=False)

    assert len(calls) == 2


def test_main_returns_nonzero_for_collect_all_failures(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    lane = _load_lane_module()

    monkeypatch.setattr(
        lane,
        "parse_args",
        lambda argv=None: lane.argparse.Namespace(
            command="validate-v5",
            step_timeout=20,
            collect_all_errors=True,
        ),
    )
    monkeypatch.setattr(lane, "_assert_workspace_layout", lambda: None)
    monkeypatch.setattr(
        lane,
        "validate_v5",
        lambda **kwargs: (_ for _ in ()).throw(
            lane.LaneAggregateError(
                [
                    "python step-one exited with code 2",
                    "python step-two timed out after 20s",
                ],
                has_timeout=True,
            )
        ),
    )

    assert lane.main() == lane.LaneExitCode.INFRA_ERROR
    captured = capsys.readouterr()
    assert "[lane] FAIL: 2 lane step(s) failed." in captured.err
    assert "[lane] FAIL: python step-one exited with code 2" in captured.err
    assert "[lane] FAIL: python step-two timed out after 20s" in captured.err
    assert "[lane] EXIT: INFRA_ERROR (3)" in captured.err


def test_main_returns_validation_exit_code_for_workspace_layout_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    lane = _load_lane_module()

    monkeypatch.setattr(
        lane,
        "parse_args",
        lambda argv=None: lane.argparse.Namespace(
            command="validate-v5",
            step_timeout=None,
            collect_all_errors=False,
        ),
    )
    monkeypatch.setattr(
        lane,
        "_assert_workspace_layout",
        lambda: (_ for _ in ()).throw(RuntimeError("Legacy root directories detected: v4. Remove them.")),
    )

    assert lane.main() == lane.LaneExitCode.VALIDATION_ERROR
    captured = capsys.readouterr()
    assert "[lane] FAIL: Legacy root directories detected: v4. Remove them." in captured.err
    assert "[lane] EXIT: VALIDATION_ERROR (1)" in captured.err


def test_main_returns_validation_exit_code_for_subprocess_failure(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    lane = _load_lane_module()

    monkeypatch.setattr(
        lane,
        "parse_args",
        lambda argv=None: lane.argparse.Namespace(
            command="validate-v5",
            step_timeout=None,
            collect_all_errors=False,
        ),
    )
    monkeypatch.setattr(lane, "_assert_workspace_layout", lambda: None)
    monkeypatch.setattr(
        lane,
        "validate_v5",
        lambda **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(
                returncode=7,
                cmd=[lane.PYTHON, "scripts/validation/validate_v5_scaffold.py"],
            )
        ),
    )

    assert lane.main() == lane.LaneExitCode.VALIDATION_ERROR
    captured = capsys.readouterr()
    assert "returned non-zero exit status 7" in captured.err
    assert "[lane] EXIT: VALIDATION_ERROR (1)" in captured.err
