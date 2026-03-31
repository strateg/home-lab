"""
ADR 0083/0084: Deploy Domain

This package contains deploy-plane tooling for node initialization
and infrastructure deployment.

Key components:
- bundle.py: Deploy bundle assembly and lifecycle operations
- profile.py: Deploy profile schema-aware loader
- runner.py: DeployRunner abstraction for cross-platform execution
- init_node.py / init-node.py: Node initialization orchestrator scaffold (Phase 5)
- adapters/: Bootstrap mechanism adapters (Phase 5)
- checks/: Handover verification checks (Phase 5)
- state.py: Initialization state machine (Phase 5)

See ADR 0084 for execution plane model.
See ADR 0083 for initialization contract.
"""

from .bundle import (
    BundleError,
    BundleInfo,
    compute_bundle_id,
    create_bundle,
    delete_bundle,
    inspect_bundle,
    list_bundles,
    resolve_bundle_path,
    resolve_bundle_schema_path,
    resolve_bundles_root,
    verify_bundle_checksums,
)
from .init_node import InitStateSummary
from .init_node import parse_args as parse_init_node_args
from .init_node import resolve_state_path, summarize_state
from .init_node import validate_args as validate_init_node_args
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
    "BundleError",
    "BundleInfo",
    "BundlePolicy",
    "compute_bundle_id",
    "create_bundle",
    "delete_bundle",
    "DeployRunner",
    "DeployProfile",
    "DeployWorkspace",
    "DeployTimeouts",
    "DockerRunner",
    "DockerRunnerProfile",
    "NativeRunner",
    "RemoteRunnerProfile",
    "RemoteLinuxRunner",
    "InitStateSummary",
    "resolve_bundle_path",
    "resolve_bundle_schema_path",
    "resolve_bundles_root",
    "RunResult",
    "RunnerProfiles",
    "inspect_bundle",
    "list_bundles",
    "parse_init_node_args",
    "WSLRunner",
    "WSLRunnerProfile",
    "check_runner_tools",
    "default_deploy_profile",
    "get_runner",
    "load_deploy_profile",
    "resolve_deploy_profile_path",
    "resolve_deploy_profile_schema_path",
    "resolve_state_path",
    "resolve_deploy_workspace",
    "summarize_state",
    "validate_init_node_args",
    "verify_bundle_checksums",
]
