"""
ADR 0084: Deploy Runner Abstraction

Provides unified interface for executing deploy commands across different backends:
- NativeRunner: Direct execution on Linux/macOS
- WSLRunner: Execution via WSL on Windows
- DockerRunner: Containerized execution (planned)
- RemoteLinuxRunner: SSH-based execution (planned)

Usage:
    from scripts.orchestration.deploy.runner import get_runner

    runner = get_runner()  # Auto-detect
    # or
    runner = get_runner("wsl")  # Explicit

    result = runner.run(["ansible-playbook", "playbook.yml"])
    if result.success:
        print(result.stdout)
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

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

    All deploy operations (Terraform, Ansible, init-node) execute through
    a runner to ensure consistent Linux-backed execution environment.
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
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        """
        Execute command in deploy environment.

        Args:
            cmd: Command and arguments to execute
            cwd: Working directory (translated to runner path)
            env: Additional environment variables
            timeout: Timeout in seconds (None = no timeout)

        Returns:
            RunResult with exit code, stdout, stderr
        """
        pass

    @abstractmethod
    def translate_path(self, path: Path) -> str:
        """
        Translate host path to runner-accessible path.

        Args:
            path: Host filesystem path

        Returns:
            Path string accessible from within the runner
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this runner is available on the current system.

        Returns:
            True if runner can be used
        """
        pass

    def check_tool(self, tool: str) -> bool:
        """
        Check if a tool is available in the runner environment.

        Args:
            tool: Tool name (e.g., "ansible-playbook", "terraform")

        Returns:
            True if tool is found
        """
        result = self.run(["which", tool])
        return result.success

    def get_tool_path(self, tool: str) -> str | None:
        """
        Get full path to a tool in the runner environment.

        Args:
            tool: Tool name

        Returns:
            Full path or None if not found
        """
        result = self.run(["which", tool])
        if result.success:
            return result.stdout.strip()
        return None


class NativeRunner(DeployRunner):
    """
    Execute commands natively on Linux/macOS.

    This is the simplest runner - direct subprocess execution.
    """

    @property
    def name(self) -> str:
        return "native"

    def run(
        self,
        cmd: Sequence[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        import os

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(
                list(cmd),
                cwd=cwd,
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
        except subprocess.TimeoutExpired as e:
            return RunResult(
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )

    def translate_path(self, path: Path) -> str:
        return str(path.resolve())

    def is_available(self) -> bool:
        system = platform.system()
        return system in ("Linux", "Darwin")


class WSLRunner(DeployRunner):
    """
    Execute commands via WSL on Windows.

    Translates Windows paths to /mnt/c/... format and wraps
    commands with wsl.exe invocation.
    """

    def __init__(self, distro: str = "Ubuntu"):
        """
        Initialize WSL runner.

        Args:
            distro: WSL distribution name (default: Ubuntu)
        """
        self.distro = distro
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return f"wsl:{self.distro}"

    def run(
        self,
        cmd: Sequence[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        # Build WSL command
        wsl_cmd = ["wsl", "-d", self.distro]

        # Add working directory if specified
        if cwd:
            wsl_cwd = self.translate_path(cwd)
            wsl_cmd.extend(["--cd", wsl_cwd])

        # Handle environment variables
        if env:
            # Prepend env vars to command via bash
            env_exports = " ".join(f'{k}="{v}"' for k, v in env.items())
            bash_cmd = f"{env_exports} {' '.join(cmd)}"
            wsl_cmd.extend(["--", "bash", "-c", bash_cmd])
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
        except subprocess.TimeoutExpired as e:
            return RunResult(
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )

    def translate_path(self, path: Path) -> str:
        """
        Convert Windows path to WSL path.

        C:\\Users\\user\\project → /mnt/c/Users/user/project
        """
        resolved = path.resolve()
        path_str = str(resolved)

        # Check for Windows drive letter (C:, D:, etc.)
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            return f"/mnt/{drive}{rest}"

        # Already Unix-style or relative
        return path_str.replace("\\", "/")

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available

        # Must be on Windows
        if platform.system() != "Windows":
            self._available = False
            return False

        # Check WSL is installed
        if not shutil.which("wsl"):
            self._available = False
            return False

        # Check distro exists
        try:
            result = subprocess.run(
                ["wsl", "-l", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # WSL output may have BOM/null chars
            distros = result.stdout.replace("\x00", "").strip().split("\n")
            distros = [d.strip() for d in distros if d.strip()]
            self._available = self.distro in distros
        except Exception:
            self._available = False

        return self._available

    def get_available_distros(self) -> list[str]:
        """Get list of available WSL distributions."""
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
            return [d.strip() for d in distros if d.strip()]
        except Exception:
            return []


# Placeholder for future implementations
class DockerRunner(DeployRunner):
    """
    Execute commands in Docker container.

    Planned for Phase 0b - CI/CD reproducible execution.
    """

    def __init__(self, image: str = "homelab-toolchain:latest"):
        self.image = image

    @property
    def name(self) -> str:
        return f"docker:{self.image}"

    def run(
        self,
        cmd: Sequence[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        raise NotImplementedError("DockerRunner planned for Phase 0b")

    def translate_path(self, path: Path) -> str:
        raise NotImplementedError("DockerRunner planned for Phase 0b")

    def is_available(self) -> bool:
        # Check docker daemon is running
        if not shutil.which("docker"):
            return False
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False


class RemoteLinuxRunner(DeployRunner):
    """
    Execute commands on remote Linux via SSH.

    Planned for Phase 0c - dedicated control node.
    """

    def __init__(self, host: str, user: str = "deploy"):
        self.host = host
        self.user = user

    @property
    def name(self) -> str:
        return f"remote:{self.user}@{self.host}"

    def run(
        self,
        cmd: Sequence[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        raise NotImplementedError("RemoteLinuxRunner planned for Phase 0c")

    def translate_path(self, path: Path) -> str:
        raise NotImplementedError("RemoteLinuxRunner planned for Phase 0c")

    def is_available(self) -> bool:
        # Would check SSH connectivity
        return False


# --- Factory Functions ---


def get_runner(preference: str | None = None, **kwargs) -> DeployRunner:
    """
    Get deploy runner based on preference or auto-detect.

    Args:
        preference: Runner type ("native", "wsl", "docker", "remote") or None for auto
        **kwargs: Additional arguments passed to runner constructor

    Returns:
        DeployRunner instance

    Raises:
        ValueError: Unknown runner type
        RuntimeError: Requested runner not available
    """
    if preference:
        return _get_explicit_runner(preference, **kwargs)
    return _auto_detect_runner()


def _get_explicit_runner(preference: str, **kwargs) -> DeployRunner:
    """Get explicitly requested runner."""
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
            f"Runner '{preference}' is not available on this system. "
            f"Check installation and configuration."
        )

    return runner


def _auto_detect_runner() -> DeployRunner:
    """Auto-detect appropriate runner for current platform."""
    system = platform.system()

    if system == "Windows":
        # Try WSL
        runner = WSLRunner()
        if runner.is_available():
            return runner

        # WSL not available - provide helpful error
        raise RuntimeError(
            "Deploy plane requires Linux execution environment.\n\n"
            "You are on Windows but WSL is not available.\n"
            "Install WSL with: wsl --install -d Ubuntu\n\n"
            "See: docs/guides/OPERATOR-ENVIRONMENT-SETUP.md\n"
            "See: ADR 0084 for execution plane model"
        )

    if system in ("Linux", "Darwin"):
        runner = NativeRunner()
        if runner.is_available():
            return runner

    raise RuntimeError(f"No suitable deploy runner for platform: {system}")


def check_runner_tools(runner: DeployRunner, tools: list[str]) -> dict[str, bool]:
    """
    Check availability of multiple tools in runner.

    Args:
        runner: DeployRunner instance
        tools: List of tool names to check

    Returns:
        Dict mapping tool name to availability
    """
    return {tool: runner.check_tool(tool) for tool in tools}
