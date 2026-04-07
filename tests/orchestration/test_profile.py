from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "deploy-profile.schema.json"
sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.profile import load_deploy_profile  # noqa: E402
from scripts.orchestration.deploy.runner import DockerRunner, RemoteLinuxRunner, WSLRunner, get_runner  # noqa: E402


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _build_project_repo(tmp_path: Path, profile_payload: dict) -> Path:
    project_repo = tmp_path / "project-repo"
    framework_root = project_repo / "framework"
    schema_target = framework_root / "schemas" / "deploy-profile.schema.json"

    _write_yaml(
        project_repo / "topology.yaml",
        {
            "version": "5.0.0",
            "project": {"active": "home-lab", "projects_root": "."},
            "framework": {"root": "framework"},
        },
    )
    _write_yaml(
        project_repo / "project.yaml",
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "topology/instances",
            "secrets_root": "secrets",
        },
    )
    (framework_root / "topology-tools").mkdir(parents=True, exist_ok=True)
    (framework_root / "framework.yaml").write_text("schema_version: 1\nframework_id: test\n", encoding="utf-8")
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    schema_target.write_text(SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    _write_yaml(project_repo / "deploy" / "deploy-profile.yaml", profile_payload)
    return project_repo


def test_repository_deploy_profile_example_validates() -> None:
    profile = load_deploy_profile(repo_root=REPO_ROOT, project_id="home-lab")

    assert profile.schema_version == "1.0"
    assert profile.project == "home-lab"
    assert profile.default_runner == "wsl"
    assert profile.runners.wsl.distro == "Ubuntu"


def test_profile_loader_rejects_invalid_runner(tmp_path: Path) -> None:
    profile_path = tmp_path / "deploy-profile.yaml"
    _write_yaml(
        profile_path,
        {
            "schema_version": "1.0",
            "project": "home-lab",
            "default_runner": "invalid-runner",
        },
    )

    with pytest.raises(ValueError, match="Deploy profile validation failed"):
        load_deploy_profile(path=profile_path, schema_path=SCHEMA_PATH, project_id="home-lab")


def test_profile_loader_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    profile = load_deploy_profile(
        path=tmp_path / "missing-profile.yaml",
        schema_path=SCHEMA_PATH,
        project_id="home-lab",
    )

    assert profile.project == "home-lab"
    assert profile.default_runner is None
    assert profile.runners.wsl.distro == "Ubuntu"
    assert profile.bundle.retention_count == 5


def test_get_runner_uses_profile_default_from_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_repo = _build_project_repo(
        tmp_path,
        {
            "schema_version": "1.0",
            "project": "home-lab",
            "default_runner": "wsl",
            "runners": {"wsl": {"distro": "Debian"}},
        },
    )
    monkeypatch.setattr(WSLRunner, "is_available", lambda self: True)

    runner = get_runner(repo_root=project_repo, project_id="home-lab")

    assert isinstance(runner, WSLRunner)
    assert runner.distro == "Debian"


def test_explicit_wsl_runner_uses_profile_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_repo = _build_project_repo(
        tmp_path,
        {
            "schema_version": "1.0",
            "project": "home-lab",
            "default_runner": "native",
            "runners": {"wsl": {"distro": "Arch"}},
        },
    )
    monkeypatch.setattr(WSLRunner, "is_available", lambda self: True)

    runner = get_runner("wsl", repo_root=project_repo, project_id="home-lab")

    assert isinstance(runner, WSLRunner)
    assert runner.distro == "Arch"


def test_profile_loader_parses_remote_runner_settings(tmp_path: Path) -> None:
    profile_path = tmp_path / "deploy-profile.yaml"
    _write_yaml(
        profile_path,
        {
            "schema_version": "1.0",
            "project": "home-lab",
            "default_runner": "remote",
            "runners": {
                "remote": {
                    "host": "control.example.com",
                    "user": "operator",
                    "sync_method": "scp",
                }
            },
        },
    )

    profile = load_deploy_profile(path=profile_path, schema_path=SCHEMA_PATH, project_id="home-lab")

    assert profile.default_runner == "remote"
    assert profile.runners.remote.host == "control.example.com"
    assert profile.runners.remote.user == "operator"
    assert profile.runners.remote.sync_method == "scp"


def test_get_runner_uses_remote_profile_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_repo = _build_project_repo(
        tmp_path,
        {
            "schema_version": "1.0",
            "project": "home-lab",
            "default_runner": "remote",
            "runners": {
                "remote": {
                    "host": "control.example.com",
                    "user": "operator",
                    "sync_method": "scp",
                }
            },
        },
    )
    monkeypatch.setattr(RemoteLinuxRunner, "is_available", lambda self: True)

    runner = get_runner(repo_root=project_repo, project_id="home-lab")

    assert isinstance(runner, RemoteLinuxRunner)
    assert runner.host == "control.example.com"
    assert runner.user == "operator"
    assert runner.sync_method == "scp"


def test_get_runner_uses_docker_profile_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_repo = _build_project_repo(
        tmp_path,
        {
            "schema_version": "1.0",
            "project": "home-lab",
            "default_runner": "docker",
            "runners": {"docker": {"image": "toolchain:ci", "network": "bridge"}},
        },
    )
    monkeypatch.setattr(DockerRunner, "is_available", lambda self: True)

    runner = get_runner(repo_root=project_repo, project_id="home-lab")

    assert isinstance(runner, DockerRunner)
    assert runner.image == "toolchain:ci"
    assert runner.network == "bridge"
