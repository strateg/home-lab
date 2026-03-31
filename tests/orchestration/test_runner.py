from __future__ import annotations

import platform
import sys
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.orchestration.deploy.runner as runner_module  # noqa: E402
from scripts.orchestration.deploy.runner import NativeRunner, RunResult, WSLRunner, get_runner  # noqa: E402


class _FakeWindowsPath:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def resolve(self) -> PureWindowsPath:
        return PureWindowsPath(self.raw)


def test_native_runner_is_available_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_module.platform, "system", lambda: "Linux")

    assert NativeRunner().is_available() is True


def test_native_runner_run_executes_simple_command() -> None:
    runner = NativeRunner()

    result = runner.run([sys.executable, "-c", "print('runner-ok')"])

    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout.strip() == "runner-ok"
    assert result.stderr == ""


def test_native_runner_translate_path_returns_resolved_path(tmp_path: Path) -> None:
    runner = NativeRunner()
    target = tmp_path / "bundle"
    target.mkdir()

    assert runner.translate_path(target) == str(target.resolve())


def test_native_runner_capabilities_match_contract() -> None:
    runner = NativeRunner()

    assert runner.capabilities() == {
        "interactive_confirmation": True,
        "host_network_access": True,
        "path_translation": False,
        "persistent_workspace": True,
        "artifact_upload_download": False,
    }


def test_wsl_runner_translate_path_converts_windows_drive_path() -> None:
    runner = WSLRunner()

    translated = runner.translate_path(_FakeWindowsPath(r"C:\Users\user\project"))  # type: ignore[arg-type]

    assert translated == "/mnt/c/Users/user/project"


def test_wsl_runner_is_available_checks_requested_distro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(runner_module.shutil, "which", lambda name: "C:\\Windows\\System32\\wsl.exe")

    def fake_run(cmd: list[str], capture_output: bool, text: bool, timeout: int) -> SimpleNamespace:
        assert cmd == ["wsl", "-l", "-q"]
        assert capture_output is True
        assert text is True
        assert timeout == 10
        return SimpleNamespace(returncode=0, stdout="Ubuntu\nDebian\n", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    assert WSLRunner("Ubuntu").is_available() is True
    assert WSLRunner("Arch").is_available() is False


@pytest.mark.skipif(platform.system() != "Windows", reason="WSL execution path is Windows-only")
def test_wsl_runner_run_uses_wsl_command_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], capture_output: bool, text: bool, timeout: int | None) -> SimpleNamespace:
        captured["cmd"] = cmd
        assert capture_output is True
        assert text is True
        assert timeout is None
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    result = WSLRunner("Ubuntu").run(["echo", "ok"], workspace_ref="/tmp/bundle")

    assert result.success is True
    assert captured["cmd"] == ["wsl", "-d", "Ubuntu", "--cd", "/tmp/bundle", "--", "echo", "ok"]


def test_get_runner_returns_native_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(NativeRunner, "is_available", lambda self: True)

    runner = get_runner("native")

    assert isinstance(runner, NativeRunner)


def test_get_runner_returns_wsl_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(WSLRunner, "is_available", lambda self: True)

    runner = get_runner("wsl", distro="Ubuntu")

    assert isinstance(runner, WSLRunner)
    assert runner.distro == "Ubuntu"


def test_get_runner_rejects_unknown_runner() -> None:
    with pytest.raises(ValueError, match="Unknown runner: unknown"):
        get_runner("unknown")


def test_run_result_success_is_true_for_zero_exit_code() -> None:
    result = RunResult(exit_code=0, stdout="", stderr="")

    assert result.success is True


def test_run_result_success_is_false_for_nonzero_exit_code() -> None:
    result = RunResult(exit_code=7, stdout="", stderr="")

    assert result.success is False
