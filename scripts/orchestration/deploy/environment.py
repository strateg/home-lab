"""
ADR 0083 Phase 0 scaffold: deploy environment checks.
"""

from __future__ import annotations

import platform
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .runner import check_runner_tools, get_runner


@dataclass(frozen=True)
class DeployEnvironmentReport:
    ready: bool
    platform: str
    runner: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tools: dict[str, bool] = field(default_factory=dict)


def check_deploy_environment(
    *,
    repo_root: Path,
    project_id: str,
    runner_preference: str | None = None,
    required_tools: Sequence[str] | None = None,
) -> DeployEnvironmentReport:
    tools_to_check = _normalize_required_tools(required_tools)
    host_platform = platform.system()
    issues: list[str] = []
    warnings: list[str] = []
    tool_results: dict[str, bool] = {}
    normalized_preference = str(runner_preference or "").strip() or None

    try:
        runner = get_runner(normalized_preference, repo_root=repo_root, project_id=project_id)
    except Exception as exc:
        issues.append(str(exc))
        return DeployEnvironmentReport(
            ready=False,
            platform=host_platform,
            runner=normalized_preference or "<auto>",
            issues=issues,
            warnings=warnings,
            tools=tool_results,
        )

    if host_platform == "Windows" and not runner.name.startswith(("wsl:", "docker:", "remote:")):
        issues.append(
            "Windows host requires Linux-backed deploy runner (wsl/docker/remote). "
            "See docs/guides/OPERATOR-ENVIRONMENT-SETUP.md"
        )

    tool_results = check_runner_tools(runner, tools_to_check)
    for tool_name, ok in tool_results.items():
        if not ok:
            issues.append(f"Required tool '{tool_name}' is not available in runner '{runner.name}'.")

    return DeployEnvironmentReport(
        ready=len(issues) == 0,
        platform=host_platform,
        runner=runner.name,
        issues=issues,
        warnings=warnings,
        tools=tool_results,
    )


def _normalize_required_tools(required_tools: Sequence[str] | None) -> list[str]:
    if required_tools is None:
        return ["bash"]

    normalized: list[str] = []
    for tool_name in required_tools:
        item = str(tool_name).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized or ["bash"]
