"""
ADR 0085: Project-scoped deploy profile loading and validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .workspace import DeployWorkspace, resolve_deploy_workspace

DEFAULT_SCHEMA_VERSION = "1.0"
DEFAULT_WSL_DISTRO = "Ubuntu"
DEFAULT_DOCKER_IMAGE = "homelab-toolchain:latest"
DEFAULT_DOCKER_NETWORK = "host"
DEFAULT_REMOTE_USER = "deploy"
DEFAULT_REMOTE_SYNC_METHOD = "rsync"
DEFAULT_TIMEOUTS = {
    "handover_total": 300,
    "handover_check": 30,
    "terraform_plan": 120,
    "ansible_playbook": 600,
}
DEFAULT_BUNDLE = {
    "retention_count": 5,
    "auto_cleanup": True,
}


@dataclass(frozen=True)
class WSLRunnerProfile:
    distro: str = DEFAULT_WSL_DISTRO


@dataclass(frozen=True)
class DockerRunnerProfile:
    image: str = DEFAULT_DOCKER_IMAGE
    network: str = DEFAULT_DOCKER_NETWORK


@dataclass(frozen=True)
class RemoteRunnerProfile:
    host: str | None = None
    user: str = DEFAULT_REMOTE_USER
    sync_method: str = DEFAULT_REMOTE_SYNC_METHOD


@dataclass(frozen=True)
class RunnerProfiles:
    wsl: WSLRunnerProfile = WSLRunnerProfile()
    docker: DockerRunnerProfile = DockerRunnerProfile()
    remote: RemoteRunnerProfile = RemoteRunnerProfile()


@dataclass(frozen=True)
class DeployTimeouts:
    handover_total: int = DEFAULT_TIMEOUTS["handover_total"]
    handover_check: int = DEFAULT_TIMEOUTS["handover_check"]
    terraform_plan: int = DEFAULT_TIMEOUTS["terraform_plan"]
    ansible_playbook: int = DEFAULT_TIMEOUTS["ansible_playbook"]


@dataclass(frozen=True)
class BundlePolicy:
    retention_count: int = DEFAULT_BUNDLE["retention_count"]
    auto_cleanup: bool = DEFAULT_BUNDLE["auto_cleanup"]


@dataclass(frozen=True)
class DeployProfile:
    schema_version: str
    project: str
    default_runner: str | None = None
    runners: RunnerProfiles = RunnerProfiles()
    timeouts: DeployTimeouts = DeployTimeouts()
    bundle: BundlePolicy = BundlePolicy()


def resolve_deploy_profile_path(workspace: DeployWorkspace) -> Path:
    return (workspace.project_root / "deploy" / "deploy-profile.yaml").resolve()


def resolve_deploy_profile_schema_path(workspace: DeployWorkspace) -> Path:
    return (workspace.framework_root / "schemas" / "deploy-profile.schema.json").resolve()


def load_deploy_profile(
    *,
    repo_root: Path | None = None,
    project_id: str | None = None,
    workspace: DeployWorkspace | None = None,
    path: Path | None = None,
    schema_path: Path | None = None,
) -> DeployProfile:
    resolved_project_id = project_id.strip() if isinstance(project_id, str) and project_id.strip() else None
    resolved_workspace = workspace

    if resolved_workspace is None and (path is None or schema_path is None or resolved_project_id is None):
        root = repo_root.resolve() if isinstance(repo_root, Path) else Path.cwd().resolve()
        resolved_workspace = resolve_deploy_workspace(repo_root=root, project_id=resolved_project_id)
        resolved_project_id = resolved_project_id or resolved_workspace.project_id

    if resolved_project_id is None:
        raise ValueError("project_id is required when workspace resolution is skipped")

    profile_path = path.resolve() if isinstance(path, Path) else None
    if profile_path is None:
        if resolved_workspace is None:
            raise ValueError("workspace is required to resolve deploy profile path")
        profile_path = resolve_deploy_profile_path(resolved_workspace)

    if not profile_path.exists():
        return default_deploy_profile(resolved_project_id)

    payload = _load_yaml_mapping(profile_path)
    schema_file = schema_path.resolve() if isinstance(schema_path, Path) else None
    if schema_file is None:
        if resolved_workspace is None:
            raise ValueError("workspace is required to resolve deploy profile schema path")
        schema_file = resolve_deploy_profile_schema_path(resolved_workspace)

    schema = _load_schema(schema_file)
    validator = jsonschema.validators.validator_for(schema)(schema)
    try:
        validator.validate(payload)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Deploy profile validation failed for {profile_path}: {exc.message}") from exc

    profile_project = str(payload.get("project", "")).strip()
    if profile_project != resolved_project_id:
        raise ValueError(
            f"Deploy profile project mismatch: expected '{resolved_project_id}', found '{profile_project}' in {profile_path}"
        )

    return _build_profile(payload, project=resolved_project_id)


def default_deploy_profile(project: str) -> DeployProfile:
    return DeployProfile(schema_version=DEFAULT_SCHEMA_VERSION, project=project)


def _build_profile(payload: dict[str, Any], *, project: str) -> DeployProfile:
    runners_payload = _mapping(payload.get("runners"))
    timeouts_payload = _mapping(payload.get("timeouts"))
    bundle_payload = _mapping(payload.get("bundle"))

    return DeployProfile(
        schema_version=str(payload.get("schema_version", DEFAULT_SCHEMA_VERSION)),
        project=project,
        default_runner=_optional_string(payload.get("default_runner")),
        runners=RunnerProfiles(
            wsl=WSLRunnerProfile(
                distro=str(_mapping(runners_payload.get("wsl")).get("distro", DEFAULT_WSL_DISTRO)),
            ),
            docker=DockerRunnerProfile(
                image=str(_mapping(runners_payload.get("docker")).get("image", DEFAULT_DOCKER_IMAGE)),
                network=str(_mapping(runners_payload.get("docker")).get("network", DEFAULT_DOCKER_NETWORK)),
            ),
            remote=RemoteRunnerProfile(
                host=_optional_string(_mapping(runners_payload.get("remote")).get("host")),
                user=str(_mapping(runners_payload.get("remote")).get("user", DEFAULT_REMOTE_USER)),
                sync_method=str(_mapping(runners_payload.get("remote")).get("sync_method", DEFAULT_REMOTE_SYNC_METHOD)),
            ),
        ),
        timeouts=DeployTimeouts(
            handover_total=int(timeouts_payload.get("handover_total", DEFAULT_TIMEOUTS["handover_total"])),
            handover_check=int(timeouts_payload.get("handover_check", DEFAULT_TIMEOUTS["handover_check"])),
            terraform_plan=int(timeouts_payload.get("terraform_plan", DEFAULT_TIMEOUTS["terraform_plan"])),
            ansible_playbook=int(timeouts_payload.get("ansible_playbook", DEFAULT_TIMEOUTS["ansible_playbook"])),
        ),
        bundle=BundlePolicy(
            retention_count=int(bundle_payload.get("retention_count", DEFAULT_BUNDLE["retention_count"])),
            auto_cleanup=bool(bundle_payload.get("auto_cleanup", DEFAULT_BUNDLE["auto_cleanup"])),
        ),
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping/object: {path}")
    return payload


def _load_schema(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON schema root must be object: {path}")
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
