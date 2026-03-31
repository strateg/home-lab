from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import scripts.orchestration.deploy.environment as environment_module  # noqa: E402
from scripts.orchestration.deploy.environment import check_deploy_environment  # noqa: E402


def test_check_deploy_environment_returns_ready_when_runner_and_tools_ok(monkeypatch) -> None:
    fake_runner = SimpleNamespace(name="wsl:Ubuntu")
    monkeypatch.setattr(environment_module, "get_runner", lambda *args, **kwargs: fake_runner)
    monkeypatch.setattr(environment_module, "check_runner_tools", lambda runner, tools: {"bash": True})

    report = check_deploy_environment(repo_root=REPO_ROOT, project_id="home-lab")

    assert report.ready is True
    assert report.runner == "wsl:Ubuntu"
    assert report.issues == []
    assert report.tools == {"bash": True}


def test_check_deploy_environment_fails_when_runner_resolution_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        environment_module, "get_runner", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    report = check_deploy_environment(repo_root=REPO_ROOT, project_id="home-lab")

    assert report.ready is False
    assert any("boom" in item for item in report.issues)


def test_check_deploy_environment_fails_when_required_tool_missing(monkeypatch) -> None:
    fake_runner = SimpleNamespace(name="wsl:Ubuntu")
    monkeypatch.setattr(environment_module, "get_runner", lambda *args, **kwargs: fake_runner)
    monkeypatch.setattr(environment_module, "check_runner_tools", lambda runner, tools: {"bash": False})

    report = check_deploy_environment(repo_root=REPO_ROOT, project_id="home-lab")

    assert report.ready is False
    assert report.tools == {"bash": False}
    assert any("Required tool 'bash'" in item for item in report.issues)


def test_check_deploy_environment_passes_runner_preference_to_get_runner(monkeypatch) -> None:
    fake_runner = SimpleNamespace(name="wsl:Ubuntu")
    captured: dict[str, object] = {}

    def _fake_get_runner(preference, **kwargs):
        captured["preference"] = preference
        captured["repo_root"] = kwargs.get("repo_root")
        captured["project_id"] = kwargs.get("project_id")
        return fake_runner

    monkeypatch.setattr(environment_module, "get_runner", _fake_get_runner)
    monkeypatch.setattr(environment_module, "check_runner_tools", lambda runner, tools: {"bash": True})

    report = check_deploy_environment(
        repo_root=REPO_ROOT,
        project_id="home-lab",
        runner_preference=" wsl ",
    )

    assert report.ready is True
    assert captured["preference"] == "wsl"
    assert captured["repo_root"] == REPO_ROOT
    assert captured["project_id"] == "home-lab"


def test_check_deploy_environment_flags_windows_with_non_linux_runner(monkeypatch) -> None:
    fake_runner = SimpleNamespace(name="native")
    monkeypatch.setattr(environment_module, "platform", SimpleNamespace(system=lambda: "Windows"))
    monkeypatch.setattr(environment_module, "get_runner", lambda *args, **kwargs: fake_runner)
    monkeypatch.setattr(environment_module, "check_runner_tools", lambda runner, tools: {"bash": True})

    report = check_deploy_environment(repo_root=REPO_ROOT, project_id="home-lab")

    assert report.ready is False
    assert any("Linux-backed deploy runner" in item for item in report.issues)
