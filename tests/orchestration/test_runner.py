from __future__ import annotations

import platform
import sys
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.orchestration.deploy.runner as runner_module  # noqa: E402
from scripts.orchestration.deploy.runner import (  # noqa: E402
    DockerRunner,
    NativeRunner,
    RemoteLinuxRunner,
    RunResult,
    WSLRunner,
    get_runner,
)


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


def test_docker_runner_stage_bundle_returns_resolved_path(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    runner = DockerRunner()

    assert runner.stage_bundle(bundle_dir) == str(bundle_dir.resolve())


def test_docker_runner_run_uses_docker_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "bundle"
    workspace.mkdir()
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], capture_output: bool, text: bool, timeout: int | None) -> SimpleNamespace:
        captured["cmd"] = cmd
        assert capture_output is True
        assert text is True
        assert timeout == 15
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = DockerRunner(image="toolchain:test", network="host")
    result = runner.run(["echo", "ok"], workspace_ref=str(workspace), env={"A": "1"}, timeout=15)

    assert result.success is True
    assert result.stdout.strip() == "ok"
    assert captured["cmd"] == [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "-v",
        f"{workspace.resolve()}:/workspace",
        "-w",
        "/workspace",
        "-e",
        "A=1",
        "toolchain:test",
        "echo",
        "ok",
    ]


def test_docker_runner_is_available_checks_docker_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_module.shutil, "which", lambda name: "C:\\docker\\docker.exe")

    def fake_run(cmd: list[str], capture_output: bool, timeout: int) -> SimpleNamespace:
        assert cmd == ["docker", "info"]
        assert capture_output is True
        assert timeout == 10
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    assert DockerRunner().is_available() is True


def test_get_runner_returns_docker_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(DockerRunner, "is_available", lambda self: True)

    runner = get_runner("docker", image="toolchain:test", network="bridge")

    assert isinstance(runner, DockerRunner)
    assert runner.image == "toolchain:test"
    assert runner.network == "bridge"


def test_remote_runner_stage_bundle_syncs_with_rsync(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "b-abc123"
    bundle_dir.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(
        runner_module.shutil,
        "which",
        lambda name: {
            "ssh": "C:\\ssh.exe",
            "rsync": "C:\\rsync.exe",
            "scp": "C:\\scp.exe",
        }.get(name),
    )

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        calls.append(cmd)
        assert capture_output is True
        assert text is True
        assert check is False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = RemoteLinuxRunner(host="control.example.com", user="deploy", sync_method="rsync")
    remote_workspace = runner.stage_bundle(bundle_dir)

    assert remote_workspace == f"/tmp/home-lab-deploy/{bundle_dir.name}"
    assert calls[0][:3] == ["ssh", "deploy@control.example.com", "bash"]
    assert calls[1][0] == "rsync"
    assert calls[1][-1] == f"deploy@control.example.com:{remote_workspace}/"


def test_remote_runner_stage_bundle_syncs_with_scp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "b-scp"
    bundle_dir.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(
        runner_module.shutil,
        "which",
        lambda name: {
            "ssh": "C:\\ssh.exe",
            "rsync": "C:\\rsync.exe",
            "scp": "C:\\scp.exe",
        }.get(name),
    )

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        calls.append(cmd)
        assert capture_output is True
        assert text is True
        assert check is False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = RemoteLinuxRunner(host="control.example.com", user="deploy", sync_method="scp")
    remote_workspace = runner.stage_bundle(bundle_dir)

    assert remote_workspace == f"/tmp/home-lab-deploy/{bundle_dir.name}"
    assert calls[1][0] == "scp"
    assert calls[1][-1] == "deploy@control.example.com:/tmp/home-lab-deploy/"


def test_remote_runner_stage_bundle_raises_on_sync_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "b-fail"
    bundle_dir.mkdir()
    call_count = {"n": 0}

    monkeypatch.setattr(
        runner_module.shutil,
        "which",
        lambda name: {
            "ssh": "C:\\ssh.exe",
            "rsync": "C:\\rsync.exe",
            "scp": "C:\\scp.exe",
        }.get(name),
    )

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        assert capture_output is True
        assert text is True
        assert check is False
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=23, stdout="", stderr="sync failed")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = RemoteLinuxRunner(host="control.example.com", user="deploy", sync_method="rsync")
    with pytest.raises(RuntimeError, match="Failed to upload bundle to remote runner"):
        runner.stage_bundle(bundle_dir)


def test_remote_runner_run_uses_ssh_command(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        text: bool,
        timeout: int | None,
    ) -> SimpleNamespace:
        captured["cmd"] = cmd
        assert capture_output is True
        assert text is True
        assert timeout == 20
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = RemoteLinuxRunner(host="control.example.com", user="deploy")
    result = runner.run(["echo", "ok"], workspace_ref="/tmp/workspace", env={"A": "1"}, timeout=20)

    assert result.success is True
    assert captured["cmd"][:3] == ["ssh", "deploy@control.example.com", "bash"]
    assert "cd /tmp/workspace" in captured["cmd"][-1]
    assert "A=1" in captured["cmd"][-1]
    assert "echo ok" in captured["cmd"][-1]


def test_remote_runner_cleanup_workspace_runs_rm(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        captured["cmd"] = cmd
        assert capture_output is True
        assert text is True
        assert timeout == 30
        assert check is False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = RemoteLinuxRunner(host="control.example.com", user="deploy")
    runner.cleanup_workspace("/tmp/work space")

    assert captured["cmd"][:3] == ["ssh", "deploy@control.example.com", "bash"]
    assert "rm -rf '/tmp/work space'" in captured["cmd"][-1]


def test_remote_runner_cleanup_workspace_skips_when_keep_workspace_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"run": False}

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        called["run"] = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = RemoteLinuxRunner(host="control.example.com", user="deploy", keep_workspace=True)
    runner.cleanup_workspace("/tmp/workspace")

    assert called["run"] is False


def test_get_runner_returns_remote_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RemoteLinuxRunner, "is_available", lambda self: True)

    runner = get_runner("remote", host="control.example.com", user="operator", sync_method="scp")

    assert isinstance(runner, RemoteLinuxRunner)
    assert runner.host == "control.example.com"
    assert runner.user == "operator"
    assert runner.sync_method == "scp"


def test_get_runner_rejects_unknown_runner() -> None:
    with pytest.raises(ValueError, match="Unknown runner: unknown"):
        get_runner("unknown")


def test_run_result_success_is_true_for_zero_exit_code() -> None:
    result = RunResult(exit_code=0, stdout="", stderr="")

    assert result.success is True


def test_run_result_success_is_false_for_nonzero_exit_code() -> None:
    result = RunResult(exit_code=7, stdout="", stderr="")

    assert result.success is False
