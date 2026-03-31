"""
ADR 0083/0084: Deploy Domain

This package contains deploy-plane tooling for node initialization
and infrastructure deployment.

Key components:
- profile.py: Deploy profile schema-aware loader
- runner.py: DeployRunner abstraction for cross-platform execution
- init-node.py: Node initialization orchestrator (Phase 5)
- adapters/: Bootstrap mechanism adapters (Phase 5)
- checks/: Handover verification checks (Phase 5)
- state.py: Initialization state machine (Phase 5)

See ADR 0084 for execution plane model.
See ADR 0083 for initialization contract.
"""

from .profile import (
    BundlePolicy,
    DeployProfile,
    DeployTimeouts,
    DockerRunnerProfile,
    RemoteRunnerProfile,
    RunnerProfiles,
    WSLRunnerProfile,
    default_deploy_profile,
    load_deploy_profile,
    resolve_deploy_profile_path,
    resolve_deploy_profile_schema_path,
)
from .runner import (
    DeployRunner,
    DockerRunner,
    NativeRunner,
    RemoteLinuxRunner,
    RunResult,
    WSLRunner,
    check_runner_tools,
    get_runner,
)
from .workspace import DeployWorkspace, resolve_deploy_workspace

__all__ = [
    "BundlePolicy",
    "DeployRunner",
    "DeployProfile",
    "DeployWorkspace",
    "DeployTimeouts",
    "DockerRunner",
    "DockerRunnerProfile",
    "NativeRunner",
    "RemoteRunnerProfile",
    "RemoteLinuxRunner",
    "RunResult",
    "RunnerProfiles",
    "WSLRunner",
    "WSLRunnerProfile",
    "check_runner_tools",
    "default_deploy_profile",
    "get_runner",
    "load_deploy_profile",
    "resolve_deploy_profile_path",
    "resolve_deploy_profile_schema_path",
    "resolve_deploy_workspace",
]
