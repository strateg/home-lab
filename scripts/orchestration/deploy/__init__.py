"""
ADR 0083/0084: Deploy Domain

This package contains deploy-plane tooling for node initialization
and infrastructure deployment.

Key components:
- runner.py: DeployRunner abstraction for cross-platform execution
- init-node.py: Node initialization orchestrator (Phase 5)
- adapters/: Bootstrap mechanism adapters (Phase 5)
- checks/: Handover verification checks (Phase 5)
- state.py: Initialization state machine (Phase 5)

See ADR 0084 for execution plane model.
See ADR 0083 for initialization contract.
"""

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
    "DeployRunner",
    "DeployWorkspace",
    "DockerRunner",
    "NativeRunner",
    "RemoteLinuxRunner",
    "RunResult",
    "WSLRunner",
    "check_runner_tools",
    "get_runner",
    "resolve_deploy_workspace",
]
