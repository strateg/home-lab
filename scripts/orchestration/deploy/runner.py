"""
ADR 0084/0085: Deploy Runner Abstraction

Provides a Linux-backed execution boundary for deploy-domain tooling:
- NativeRunner: Direct execution on local Linux
- WSLRunner: Execution via WSL on Windows
- DockerRunner: Containerized execution (planned)
- RemoteLinuxRunner: SSH-based execution (planned)

The runner contract is workspace-aware:
- deploy tooling stages an immutable deploy bundle,
- the runner returns a workspace reference,
- commands execute inside that workspace.

Usage:
    from scripts.orchestration.deploy.runner import get_runner

    runner = get_runner()
    workspace_ref = runner.stage_bundle(".work/deploy/bundles/example")
    result = runner.run(["ansible-playbook", "site.yml"], workspace_ref=workspace_ref)
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .profile import DeployProfile, load_deploy_profile

if TYPE_CHECKING:
    from typing import Sequence


@dataclass
class RunResult:
    """Result of a command execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0

    def __str__(self) -> str:
        status = "OK" if self.success else f"FAILED (exit={self.exit_code})"
        return f"RunResult({status})"


class DeployRunner(ABC):
    """
    Abstract base class for deploy runners.

    All deploy operations execute through a runner to ensure a consistent
    Linux-backed deploy environment with explicit workspace staging.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable runner name."""
        pass

    @abstractmethod
    def run(
        self,
        cmd: Sequence[str],
        workspace_ref: str | None = None,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        """
        Execute a command in the deploy environment.

        `workspace_ref` is the preferred execution boundary. `cwd` is kept as a
        compatibility fallback for older callers until bundle-aware consumers
        fully replace path-based execution.
        """
        pass

    @abstractmethod
    def stage_bundle(self, bundle_path: str | Path) -> str:
        """Stage a deploy bundle and return a backend-specific workspace reference."""
        pass

    @abstractmethod
    def cleanup_workspace(self, workspace_ref: str) -> None:
        """Clean up temporary workspace state if the backend requires it."""
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """Report backend capabilities required by deploy tooling."""
        pass

    @abstractmethod
    def translate_path(self, path: Path) -> str:
        """Translate a host path into a backend-accessible path."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the runner is available on the current host."""
        pass

    def check_tool(self, tool: str, workspace_ref: str | None = None) -> bool:
        """Check if a tool is available in the runner environment."""
        result = self.run(["which", tool], workspace_ref=workspace_ref)
        return result.success

    def get_tool_path(self, tool: str, workspace_ref: str | None = None) -> str | None:
        """Return the full tool path from the runner environment if available."""
        result = self.run(["which", tool], workspace_ref=workspace_ref)
        if result.success:
            return result.stdout.strip()
        return None


class NativeRunner(DeployRunner):
    """
    Execute commands natively on local Linux.

    This is the simplest backend: the staged workspace reference is simply
    a resolved local path.
    """

    @property
    def name(self) -> str:
        return "native"

    def run(
        self,
        cmd: Sequence[str],
        workspace_ref: str | None = None,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        run_cwd = self._resolve_cwd(workspace_ref=workspace_ref, cwd=cwd)

        try:
            result = subprocess.run(
                list(cmd),
                cwd=run_cwd,
                env=full_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return RunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                exit_code=-1,
                stdout=exc.stdout or "",
                stderr=f"Command timed out after {timeout}s",
            )
        except Exception as exc:  # pragma: no cover - defensive
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
            )

    def stage_bundle(self, bundle_path: str | Path) -> str:
        bundle_dir = Path(bundle_path).resolve()
        if not bundle_dir.exists():
            raise FileNotFoundError(f"Deploy bundle not found: {bundle_dir}")
        if not bundle_dir.is_dir():
            raise NotADirectoryError(f"Deploy bundle is not a directory: {bundle_dir}")
        return str(bundle_dir)

    def cleanup_workspace(self, workspace_ref: str) -> None:
        # Native runner uses the staged bundle in place.
        # Cleanup is a no-op because the immutable bundle lifecycle is managed
        # by higher-level tooling.
        return None

    def capabilities(self) -> dict[str, bool]:
        return {
            "interactive_confirmation": True,
            "host_network_access": True,
            "path_translation": False,
            "persistent_workspace": True,
            "artifact_upload_download": False,
        }

    def translate_path(self, path: Path) -> str:
        return str(path.resolve())

    def is_available(self) -> bool:
        return platform.system() == "Linux"

    @staticmethod
    def _resolve_cwd(workspace_ref: str | None, cwd: Path | None) -> Path | None:
        if workspace_ref:
            return Path(workspace_ref)
        return cwd


class WSLRunner(DeployRunner):
    """
    Execute commands via WSL on Windows.

    The workspace reference is a Linux path inside the selected WSL distro.
    """

    def __init__(self, distro: str = "Ubuntu"):
        self.distro = distro
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return f"wsl:{self.distro}"

    def run(
        self,
        cmd: Sequence[str],
        workspace_ref: str | None = None,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        wsl_cmd = ["wsl", "-d", self.distro]
        target_cwd = self._resolve_workspace_ref(workspace_ref=workspace_ref, cwd=cwd)
        if target_cwd:
            wsl_cmd.extend(["--cd", target_cwd])

        if env:
            env_exports = " ".join(f"{shlex.quote(key)}={shlex.quote(value)}" for key, value in env.items())
            cmd_payload = " ".join(shlex.quote(part) for part in cmd)
            bash_cmd = f"{env_exports} {cmd_payload}" if env_exports else cmd_payload
            wsl_cmd.extend(["--", "bash", "-lc", bash_cmd])
        else:
            wsl_cmd.extend(["--", *cmd])

        try:
            result = subprocess.run(
                wsl_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return RunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                exit_code=-1,
                stdout=exc.stdout or "",
                stderr=f"Command timed out after {timeout}s",
            )
        except Exception as exc:  # pragma: no cover - defensive
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
            )

    def stage_bundle(self, bundle_path: str | Path) -> str:
        bundle_dir = Path(bundle_path).resolve()
        if not bundle_dir.exists():
            raise FileNotFoundError(f"Deploy bundle not found: {bundle_dir}")
        if not bundle_dir.is_dir():
            raise NotADirectoryError(f"Deploy bundle is not a directory: {bundle_dir}")
        return self.translate_path(bundle_dir)

    def cleanup_workspace(self, workspace_ref: str) -> None:
        # WSL runner stages the immutable bundle by path translation only.
        return None

    def capabilities(self) -> dict[str, bool]:
        return {
            "interactive_confirmation": True,
            "host_network_access": True,
            "path_translation": True,
            "persistent_workspace": True,
            "artifact_upload_download": False,
        }

    def translate_path(self, path: Path) -> str:
        """
        Convert a Windows host path into a WSL-visible path.

        Example:
            C:\\Users\\user\\project -> /mnt/c/Users/user/project
        """
        resolved = path.resolve()
        path_str = str(resolved)
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            return f"/mnt/{drive}{rest}"
        return path_str.replace("\\", "/")

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        if platform.system() != "Windows":
            self._available = False
            return False
        if not shutil.which("wsl"):
            self._available = False
            return False
        try:
            result = subprocess.run(
                ["wsl", "-l", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            distros = result.stdout.replace("\x00", "").strip().split("\n")
            distros = [item.strip() for item in distros if item.strip()]
            self._available = self.distro in distros
        except Exception:
            self._available = False
        return self._available

    def get_available_distros(self) -> list[str]:
        """Get the list of locally available WSL distributions."""
        if platform.system() != "Windows":
            return []
        try:
            result = subprocess.run(
                ["wsl", "-l", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            distros = result.stdout.replace("\x00", "").strip().split("\n")
            return [item.strip() for item in distros if item.strip()]
        except Exception:
            return []

    def _resolve_workspace_ref(self, workspace_ref: str | None, cwd: Path | None) -> str | None:
        if workspace_ref:
            return workspace_ref
        if cwd:
            return self.translate_path(cwd)
        return None


class DockerRunner(DeployRunner):
    """Containerized deploy execution backend."""

    def __init__(
        self,
        image: str = "homelab-toolchain:latest",
        network: str = "host",
        workspace_mount: str = "/workspace",
        docker_binary: str = "docker",
    ):
        self.image = image
        self.network = network
        self.workspace_mount = workspace_mount
        self.docker_binary = docker_binary

    @property
    def name(self) -> str:
        return f"docker:{self.image}"

    def run(
        self,
        cmd: Sequence[str],
        workspace_ref: str | None = None,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        host_workspace = self._resolve_workspace_ref(workspace_ref=workspace_ref, cwd=cwd)
        if host_workspace is None:
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr="DockerRunner requires workspace_ref or cwd",
            )
        if not host_workspace.exists():
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=f"Docker workspace does not exist: {host_workspace}",
            )
        if not host_workspace.is_dir():
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=f"Docker workspace is not a directory: {host_workspace}",
            )

        docker_cmd: list[str] = [
            self.docker_binary,
            "run",
            "--rm",
            "--network",
            self.network,
            "-v",
            f"{host_workspace}:{self.workspace_mount}",
            "-w",
            self.workspace_mount,
        ]
        if env:
            for key, value in sorted(env.items(), key=lambda item: item[0]):
                docker_cmd.extend(["-e", f"{key}={value}"])
        docker_cmd.append(self.image)
        docker_cmd.extend(list(cmd))

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return RunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                exit_code=-1,
                stdout=exc.stdout or "",
                stderr=f"Command timed out after {timeout}s",
            )
        except Exception as exc:  # pragma: no cover - defensive
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
            )

    def stage_bundle(self, bundle_path: str | Path) -> str:
        bundle_dir = Path(bundle_path).resolve()
        if not bundle_dir.exists():
            raise FileNotFoundError(f"Deploy bundle not found: {bundle_dir}")
        if not bundle_dir.is_dir():
            raise NotADirectoryError(f"Deploy bundle is not a directory: {bundle_dir}")
        return str(bundle_dir)

    def cleanup_workspace(self, workspace_ref: str) -> None:
        # Docker runner mounts immutable bundle path into short-lived containers.
        # There is no backend-side mutable workspace to clean up.
        return None

    def capabilities(self) -> dict[str, bool]:
        return {
            "interactive_confirmation": False,
            "host_network_access": self.network == "host",
            "path_translation": False,
            "persistent_workspace": False,
            "artifact_upload_download": False,
        }

    def translate_path(self, path: Path) -> str:
        return str(path.resolve())

    def is_available(self) -> bool:
        if not shutil.which(self.docker_binary):
            return False
        try:
            result = subprocess.run(
                [self.docker_binary, "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _resolve_workspace_ref(self, workspace_ref: str | None, cwd: Path | None) -> Path | None:
        if workspace_ref:
            return Path(workspace_ref).resolve()
        if cwd is not None:
            return cwd.resolve()
        return None


class RemoteLinuxRunner(DeployRunner):
    """Planned for Phase 0c - remote Linux control-node execution."""

    def __init__(self, host: str, user: str = "deploy"):
        self.host = host
        self.user = user

    @property
    def name(self) -> str:
        return f"remote:{self.user}@{self.host}"

    def run(
        self,
        cmd: Sequence[str],
        workspace_ref: str | None = None,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        raise NotImplementedError("RemoteLinuxRunner planned for Phase 0c")

    def stage_bundle(self, bundle_path: str | Path) -> str:
        raise NotImplementedError("RemoteLinuxRunner planned for Phase 0c")

    def cleanup_workspace(self, workspace_ref: str) -> None:
        raise NotImplementedError("RemoteLinuxRunner planned for Phase 0c")

    def capabilities(self) -> dict[str, bool]:
        return {
            "interactive_confirmation": False,
            "host_network_access": True,
            "path_translation": False,
            "persistent_workspace": True,
            "artifact_upload_download": True,
        }

    def translate_path(self, path: Path) -> str:
        raise NotImplementedError("RemoteLinuxRunner planned for Phase 0c")

    def is_available(self) -> bool:
        return False


def get_runner(
    preference: str | None = None,
    *,
    profile: DeployProfile | None = None,
    repo_root: Path | None = None,
    project_id: str | None = None,
    **kwargs,
) -> DeployRunner:
    """
    Get a deploy runner based on explicit preference or platform auto-detection.
    """
    resolved_profile = profile
    if resolved_profile is None and (repo_root is not None or project_id is not None):
        resolved_profile = load_deploy_profile(repo_root=repo_root, project_id=project_id)

    effective_preference = preference or (resolved_profile.default_runner if resolved_profile else None)
    if effective_preference:
        return _get_explicit_runner(
            effective_preference,
            **_merge_runner_kwargs(effective_preference, resolved_profile, kwargs),
        )
    return _auto_detect_runner()


def _get_explicit_runner(preference: str, **kwargs) -> DeployRunner:
    runners = {
        "native": NativeRunner,
        "wsl": WSLRunner,
        "docker": DockerRunner,
        "remote": RemoteLinuxRunner,
    }
    runner_cls = runners.get(preference)
    if not runner_cls:
        available = ", ".join(runners.keys())
        raise ValueError(f"Unknown runner: {preference}. Available: {available}")
    runner = runner_cls(**kwargs)
    if not runner.is_available():
        raise RuntimeError(
            f"Runner '{preference}' is not available on this system. " f"Check installation and configuration."
        )
    return runner


def _merge_runner_kwargs(
    preference: str,
    profile: DeployProfile | None,
    explicit_kwargs: dict[str, object],
) -> dict[str, object]:
    merged = dict(explicit_kwargs)
    if profile is None:
        return merged

    if preference == "wsl":
        merged.setdefault("distro", profile.runners.wsl.distro)
        return merged

    if preference == "docker":
        merged.setdefault("image", profile.runners.docker.image)
        merged.setdefault("network", profile.runners.docker.network)
        return merged

    if preference == "remote":
        if "host" not in merged and profile.runners.remote.host:
            merged["host"] = profile.runners.remote.host
        merged.setdefault("user", profile.runners.remote.user)
        if "host" not in merged:
            raise ValueError("Remote runner requires 'host' in deploy profile or explicit arguments")
    return merged


def _auto_detect_runner() -> DeployRunner:
    system = platform.system()

    if system == "Windows":
        runner = WSLRunner()
        if runner.is_available():
            return runner
        raise RuntimeError(
            "Deploy plane requires Linux execution environment.\n\n"
            "You are on Windows but WSL is not available.\n"
            "Install WSL with: wsl --install -d Ubuntu\n\n"
            "See: docs/guides/OPERATOR-ENVIRONMENT-SETUP.md\n"
            "See: ADR 0084 and ADR 0085 for deploy-domain model"
        )

    if system == "Linux":
        runner = NativeRunner()
        if runner.is_available():
            return runner

    raise RuntimeError(
        f"No suitable deploy runner for platform: {system}. " "Canonical deploy execution is Linux-backed."
    )


def check_runner_tools(
    runner: DeployRunner,
    tools: list[str],
    workspace_ref: str | None = None,
) -> dict[str, bool]:
    """Check availability of multiple tools in the runner environment."""
    return {tool: runner.check_tool(tool, workspace_ref=workspace_ref) for tool in tools}
