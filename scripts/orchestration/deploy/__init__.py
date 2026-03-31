"""
ADR 0083/0084: Deploy Domain

This package contains deploy-plane tooling for node initialization
and infrastructure deployment.

Key components:
- bundle.py: Deploy bundle assembly and lifecycle operations
- profile.py: Deploy profile schema-aware loader
- runner.py: DeployRunner abstraction for cross-platform execution
- environment.py: Deploy plane environment checks
- init_node.py / init-node.py: Node initialization orchestrator scaffold (Phase 5)
- adapters/: Bootstrap mechanism adapters (Phase 5)
- checks/: Handover verification checks (Phase 5)
- logging.py: Structured console + JSONL deploy audit logging (Phase 5)
- state.py: Initialization state machine (Phase 5)

See ADR 0084 for execution plane model.
See ADR 0083 for initialization contract.
"""

from .adapters import (
    SUPPORTED_MECHANISMS,
    AdapterContext,
    AdapterStatus,
    BootstrapAdapter,
    BootstrapResult,
    HandoverCheckResult,
    NotImplementedBootstrapAdapter,
    PreflightCheck,
    get_adapter,
)
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
from .environment import DeployEnvironmentReport, check_deploy_environment
from .init_node import InitStateSummary
from .init_node import parse_args as parse_init_node_args
from .init_node import resolve_state_path, summarize_state
from .init_node import validate_args as validate_init_node_args
from .logging import InitNodeLogger, resolve_deploy_log_dir, resolve_init_node_log_path
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
from .state import (
    LEGAL_TRANSITIONS,
    StateTransition,
    StateTransitionError,
    assert_transition,
    build_default_node_state,
    can_transition,
    normalize_status,
    transition_node_state,
)
from .workspace import DeployWorkspace, resolve_deploy_workspace

__all__ = [
    "AdapterContext",
    "AdapterStatus",
    "BootstrapAdapter",
    "BootstrapResult",
    "BundleError",
    "BundleInfo",
    "BundlePolicy",
    "DeployEnvironmentReport",
    "compute_bundle_id",
    "create_bundle",
    "delete_bundle",
    "DeployRunner",
    "DeployProfile",
    "DeployWorkspace",
    "DeployTimeouts",
    "DockerRunner",
    "DockerRunnerProfile",
    "HandoverCheckResult",
    "LEGAL_TRANSITIONS",
    "NativeRunner",
    "NotImplementedBootstrapAdapter",
    "PreflightCheck",
    "RemoteRunnerProfile",
    "RemoteLinuxRunner",
    "InitStateSummary",
    "InitNodeLogger",
    "resolve_bundle_path",
    "resolve_bundle_schema_path",
    "resolve_bundles_root",
    "RunResult",
    "RunnerProfiles",
    "SUPPORTED_MECHANISMS",
    "StateTransition",
    "StateTransitionError",
    "assert_transition",
    "build_default_node_state",
    "can_transition",
    "check_deploy_environment",
    "get_adapter",
    "inspect_bundle",
    "list_bundles",
    "normalize_status",
    "parse_init_node_args",
    "transition_node_state",
    "WSLRunner",
    "WSLRunnerProfile",
    "check_runner_tools",
    "default_deploy_profile",
    "get_runner",
    "load_deploy_profile",
    "resolve_deploy_profile_path",
    "resolve_deploy_profile_schema_path",
    "resolve_deploy_log_dir",
    "resolve_init_node_log_path",
    "resolve_state_path",
    "resolve_deploy_workspace",
    "summarize_state",
    "validate_init_node_args",
    "verify_bundle_checksums",
]
