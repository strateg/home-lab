"""
ADR 0083 scaffold: bundle-first node initialization orchestrator.

Current scope:
- CLI contract and guardrails
- state/status file bootstrap under .work/deploy-state/<project>/
- planning + adapter preflight/execute scaffold with state transitions
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from .adapters import AdapterContext, get_adapter
from .bundle import inspect_bundle, resolve_bundle_path, resolve_bundles_root
from .environment import check_deploy_environment
from .logging import InitNodeLogger
from .runner import check_runner_tools, get_runner
from .state import StateTransitionError, build_default_node_state, normalize_status, transition_node_state

STATE_FILE_NAME = "INITIALIZATION-STATE.yaml"
DEFAULT_RUNNER_TOOLS = ("bash", "ssh", "scp")
DEFAULT_RUNNER_TOOLS_INSTALL_COMMAND = "sudo apt-get update && sudo apt-get install -y bash openssh-client"


@dataclass(frozen=True)
class InitStateSummary:
    total_nodes: int
    by_status: dict[str, int]
    updated_at: str


def resolve_state_path(*, repo_root: Path, project_id: str) -> Path:
    return (repo_root / ".work" / "deploy-state" / project_id / "nodes" / STATE_FILE_NAME).resolve()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADR 0083 node initialization orchestrator (scaffold).")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--project-id", default="home-lab")
    parser.add_argument("--bundle", default="", help="Deploy bundle id or absolute bundle path.")
    parser.add_argument(
        "--deploy-runner",
        default="",
        help="Runner override (native|wsl|docker|remote). Empty = deploy profile / auto.",
    )
    parser.add_argument("--node", default="", help="Single node id to process.")
    parser.add_argument("--all-pending", action="store_true", help="Process all nodes in pending state.")
    parser.add_argument("--status", action="store_true", help="Show current initialization state summary.")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--import-existing", action="store_true")
    parser.add_argument(
        "--phase",
        choices=("bootstrap", "recover"),
        default=_default_phase(),
        help="Execution phase. bootstrap=ssh/scp import path, recover=emergency recovery contracts.",
    )
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--confirm-reset", action="store_true")
    parser.add_argument("--acknowledge-drift", action="store_true")
    parser.add_argument("--plan-only", action="store_true", help="Render execution plan only, no state mutation.")
    parser.add_argument("--skip-environment-check", action="store_true")
    parser.add_argument(
        "--bootstrap-secret-file",
        default=os.environ.get("INIT_NODE_BOOTSTRAP_SECRET_FILE", ""),
        help=(
            "Optional SOPS-encrypted bootstrap SSH contract file. "
            "If omitted, init-node probes default project bootstrap secret paths."
        ),
    )
    parser.add_argument(
        "--bootstrap-runner-tools",
        action="store_true",
        default=_env_bool("INIT_NODE_BOOTSTRAP_RUNNER_TOOLS"),
        help="Validate required tools inside selected deploy runner and auto-install when possible.",
    )
    parser.add_argument(
        "--runner-tools",
        default=os.environ.get("INIT_NODE_RUNNER_TOOLS", ",".join(DEFAULT_RUNNER_TOOLS)),
        help="Comma/space-separated required tools for runner bootstrap checks.",
    )
    parser.add_argument(
        "--runner-tools-install-command",
        default=os.environ.get("INIT_NODE_RUNNER_TOOLS_INSTALL_COMMAND", ""),
        help="Install command executed in runner when required tools are missing.",
    )
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    has_target = bool(str(args.node or "").strip()) or bool(args.all_pending)
    if not has_target and not bool(args.status):
        raise ValueError("Select one action: --node <id>, --all-pending, or --status")
    if has_target and bool(args.status):
        raise ValueError("--status cannot be combined with --node/--all-pending")
    if bool(args.verify_only) and bool(args.force):
        raise ValueError("--verify-only cannot be combined with --force")
    if bool(args.reset) and not bool(args.confirm_reset):
        raise ValueError("E9720: --confirm-reset flag required for --reset")
    if has_target and not str(args.bundle or "").strip():
        raise ValueError("Bundle-based execution requires --bundle <bundle_id> or --bundle <absolute_path>")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env_bool(name: str) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    return False


def _default_phase() -> str:
    value = str(os.environ.get("INIT_NODE_PHASE", "bootstrap")).strip().lower()
    if value in {"bootstrap", "recover"}:
        return value
    return "bootstrap"


def _parse_runner_tools(raw_value: str) -> list[str]:
    raw = str(raw_value or "").strip()
    if not raw:
        return list(DEFAULT_RUNNER_TOOLS)
    parts = re.split(r"[,\s]+", raw)
    normalized: list[str] = []
    for item in parts:
        tool = str(item).strip()
        if tool and tool not in normalized:
            normalized.append(tool)
    return normalized or list(DEFAULT_RUNNER_TOOLS)


def _default_runner_tools_install_command(runner_name: str) -> str:
    if runner_name.startswith("docker:"):
        return ""
    return DEFAULT_RUNNER_TOOLS_INSTALL_COMMAND


def _ensure_runner_toolchain(
    *,
    runner: Any,
    workspace_ref: str,
    bootstrap_enabled: bool,
    required_tools: list[str],
    install_command: str,
) -> tuple[bool, dict[str, Any]]:
    results = check_runner_tools(runner, required_tools, workspace_ref=workspace_ref)
    missing = [name for name, ok in results.items() if not ok]
    payload: dict[str, Any] = {
        "runner": str(getattr(runner, "name", "unknown")),
        "required_tools": required_tools,
        "tool_results": results,
        "missing_tools": missing,
    }
    if not missing:
        payload["message"] = "Runner toolchain verified."
        return True, payload

    if not bootstrap_enabled:
        payload["message"] = "Required runner tools are missing."
        payload["hint"] = "Enable --bootstrap-runner-tools or install tools manually."
        return False, payload

    runner_name = str(getattr(runner, "name", ""))
    effective_install_command = install_command.strip() or _default_runner_tools_install_command(runner_name)
    if not effective_install_command:
        payload["message"] = (
            "Runner tool bootstrap is not supported for this runner. "
            "Use prepared image/runtime with required tools preinstalled."
        )
        return False, payload

    install_result = runner.run(["bash", "-lc", effective_install_command], workspace_ref=workspace_ref)
    payload["install_command"] = effective_install_command
    payload["install_exit_code"] = int(getattr(install_result, "exit_code", -1))
    payload["install_stdout"] = str(getattr(install_result, "stdout", "")).strip()
    payload["install_stderr"] = str(getattr(install_result, "stderr", "")).strip()
    if not bool(getattr(install_result, "success", False)):
        payload["message"] = "Runner tool bootstrap command failed."
        return False, payload

    results_after = check_runner_tools(runner, required_tools, workspace_ref=workspace_ref)
    missing_after = [name for name, ok in results_after.items() if not ok]
    payload["tool_results_after_install"] = results_after
    payload["missing_tools"] = missing_after
    if missing_after:
        payload["message"] = "Runner tool bootstrap finished but tools are still missing."
        return False, payload

    payload["message"] = "Runner toolchain bootstrap completed."
    return True, payload


def _resolve_bootstrap_secret_candidates(
    *,
    repo_root: Path,
    project_id: str,
    node_id: str,
    bootstrap_secret_file: str,
) -> list[Path]:
    candidates: list[Path] = []
    explicit = str(bootstrap_secret_file or "").strip()
    if explicit:
        explicit_path = Path(explicit)
        if not explicit_path.is_absolute():
            explicit_path = (repo_root / explicit_path).resolve()
        candidates.append(explicit_path)

    bootstrap_roots = [
        (repo_root / "projects" / project_id / "secrets" / "bootstrap").resolve(),
        (repo_root / "secrets" / "bootstrap").resolve(),
    ]
    dotted_node_id = node_id.replace("-", ".")
    default_names = [
        f"{node_id}.yaml",
        f"{dotted_node_id}.yaml",
        f"{node_id}-ssh.yaml",
    ]
    for root in bootstrap_roots:
        for file_name in default_names:
            candidates.append((root / file_name).resolve())

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _decrypt_sops_mapping(secret_file: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["sops", "-d", "--output-type", "json", str(secret_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"sops decrypt failed for '{secret_file}': {stderr or 'unknown error'}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON decrypted payload from '{secret_file}': {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Decrypted bootstrap secret root must be object: {secret_file}")
    return payload


def _extract_ssh_contract(payload: dict[str, Any]) -> dict[str, Any]:
    ssh_payload = payload.get("ssh")
    if not isinstance(ssh_payload, dict):
        ssh_payload = {}
    host = str(ssh_payload.get("host") or payload.get("host") or "").strip()
    username = str(ssh_payload.get("username") or payload.get("username") or "").strip()
    password = str(ssh_payload.get("password") or payload.get("password") or "").strip()
    port_raw = str(ssh_payload.get("port") or payload.get("port") or "").strip()
    port = ""
    if port_raw:
        try:
            parsed = int(port_raw)
            if parsed > 0:
                port = str(parsed)
        except ValueError:
            port = ""
    return {
        "host": host,
        "username": username,
        "password": password,
        "port": port,
    }


def _prepare_bootstrap_ssh_contract_env(
    *,
    repo_root: Path,
    project_id: str,
    node_id: str | None,
    phase: str,
    verify_only: bool,
    bootstrap_secret_file: str,
) -> tuple[bool, dict[str, Any]]:
    if verify_only or phase != "bootstrap":
        return True, {"message": "Bootstrap secret autoload skipped.", "reason": "phase-or-verify-only"}
    if not node_id:
        return True, {"message": "Bootstrap secret autoload skipped.", "reason": "no-target-node"}
    if (
        str(os.environ.get("INIT_NODE_NETINSTALL_SSH_HOST", "")).strip()
        and str(os.environ.get("INIT_NODE_NETINSTALL_SSH_USER", "")).strip()
    ):
        return True, {"message": "Bootstrap SSH contract already provided via environment."}

    candidates = _resolve_bootstrap_secret_candidates(
        repo_root=repo_root,
        project_id=project_id,
        node_id=node_id,
        bootstrap_secret_file=bootstrap_secret_file,
    )
    secret_file = next((path for path in candidates if path.exists()), None)
    if secret_file is None:
        return True, {
            "message": "Bootstrap SSH secret file was not found.",
            "candidates": [str(item) for item in candidates],
        }

    try:
        payload = _decrypt_sops_mapping(secret_file)
        contract = _extract_ssh_contract(payload)
    except RuntimeError as exc:
        return False, {"message": str(exc), "secret_file": str(secret_file)}

    host = str(contract.get("host", "")).strip()
    username = str(contract.get("username", "")).strip()
    if not host or not username:
        return False, {
            "message": "Bootstrap SSH secret must contain host and username fields.",
            "secret_file": str(secret_file),
        }

    os.environ.setdefault("INIT_NODE_NETINSTALL_SSH_HOST", host)
    os.environ.setdefault("INIT_NODE_NETINSTALL_SSH_USER", username)
    if str(contract.get("password", "")).strip():
        os.environ.setdefault("INIT_NODE_NETINSTALL_SSH_PASSWORD", str(contract["password"]).strip())
    if str(contract.get("port", "")).strip():
        os.environ.setdefault("INIT_NODE_NETINSTALL_SSH_PORT", str(contract["port"]).strip())
    os.environ.setdefault("INIT_NODE_NETINSTALL_HANDOVER_HOST", host)

    return True, {
        "message": "Bootstrap SSH contract loaded from SOPS secret.",
        "secret_file": str(secret_file),
        "host": host,
        "username": username,
        "password_loaded": bool(str(contract.get("password", "")).strip()),
    }


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"State file root must be mapping/object: {path}")
    return payload


def _write_yaml_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    tmp_path.replace(path)


def _derive_manifest_nodes(bundle_path: Path) -> list[dict[str, Any]]:
    details = inspect_bundle(bundle_path, verify_checksums=True)
    nodes_payload = details.get("manifest", {}).get("nodes", [])
    result: list[dict[str, Any]] = []
    for row in nodes_payload if isinstance(nodes_payload, list) else []:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("id", "")).strip()
        mechanism = str(row.get("mechanism", "")).strip() or "unknown"
        artifacts = row.get("artifacts", [])
        if not isinstance(artifacts, list):
            artifacts = []
        if node_id:
            result.append({"id": node_id, "mechanism": mechanism, "artifacts": artifacts})
    result.sort(key=lambda item: item["id"])
    return result


def _resolve_bundle_for_execution(*, repo_root: Path, bundle_ref: str) -> Path:
    bundles_root = resolve_bundles_root(repo_root)
    bundle_path = resolve_bundle_path(bundles_root, bundle_ref.strip())
    if not bundle_path.exists() or not bundle_path.is_dir():
        raise FileNotFoundError(f"Deploy bundle not found: {bundle_path}")
    return bundle_path


def _ensure_state_baseline(*, state_path: Path, manifest_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    state = _load_yaml_mapping(state_path)
    rows = state.get("nodes")
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            node_id = str(row.get("id", "")).strip()
            if node_id:
                by_id[node_id] = dict(row)

    for row in manifest_nodes:
        node_id = row["id"]
        if node_id in by_id:
            by_id[node_id].setdefault("mechanism", row["mechanism"])
            by_id[node_id]["status"] = normalize_status(str(by_id[node_id].get("status", "pending")))
            continue
        by_id[node_id] = build_default_node_state(node_id=node_id, mechanism=row["mechanism"])

    payload = {
        "version": "1.0",
        "updated_at": _utc_now(),
        "nodes": [by_id[key] for key in sorted(by_id.keys())],
    }
    _write_yaml_atomic(state_path, payload)
    return payload


def summarize_state(state_payload: dict[str, Any]) -> InitStateSummary:
    rows = state_payload.get("nodes")
    counts: dict[str, int] = {}
    total = 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "pending")).strip() or "pending"
        counts[status] = counts.get(status, 0) + 1
        total += 1
    return InitStateSummary(
        total_nodes=total,
        by_status=dict(sorted(counts.items(), key=lambda item: item[0])),
        updated_at=str(state_payload.get("updated_at", "")),
    )


def _state_index(state_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = state_payload.get("nodes")
    result: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("id", "")).strip()
        if node_id:
            result[node_id] = row
    return result


def _manifest_index(manifest_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in manifest_nodes:
        node_id = str(row.get("id", "")).strip()
        if node_id:
            result[node_id] = row
    return result


def _serialize_preflight_checks(checks: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for row in checks:
        payload.append(
            {
                "name": str(getattr(row, "name", "")),
                "ok": bool(getattr(row, "ok", False)),
                "details": str(getattr(row, "details", "")),
                "remediation_hint": str(getattr(row, "remediation_hint", "")),
            }
        )
    return payload


def _serialize_handover_checks(checks: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for row in checks:
        payload.append(
            {
                "name": str(getattr(row, "name", "")),
                "ok": bool(getattr(row, "ok", False)),
                "details": str(getattr(row, "details", "")),
                "attempt": int(getattr(row, "attempt", 1)),
                "total_attempts": int(getattr(row, "total_attempts", 1)),
                "error_code": str(getattr(row, "error_code", "")),
            }
        )
    return payload


def _execute_selected_nodes(
    *,
    project_id: str,
    bundle_path: Path,
    workspace_ref: str,
    state_path: Path,
    state_payload: dict[str, Any],
    manifest_nodes: list[dict[str, Any]],
    selected_nodes: list[str],
    import_existing: bool,
    logger: InitNodeLogger,
) -> tuple[int, dict[str, Any]]:
    state_by_id = _state_index(state_payload)
    manifest_by_id = _manifest_index(manifest_nodes)
    context = AdapterContext(project_id=project_id, bundle_path=bundle_path, workspace_ref=workspace_ref)

    results: list[dict[str, Any]] = []
    failure_count = 0

    for node_id in sorted(set(selected_nodes)):
        state_row = state_by_id.get(node_id)
        manifest_row = manifest_by_id.get(node_id, {"id": node_id, "mechanism": "unknown"})
        mechanism = str(manifest_row.get("mechanism", "unknown")).strip() or "unknown"

        result_row: dict[str, Any] = {
            "node": node_id,
            "mechanism": mechanism,
            "status": "failed",
            "error_code": "",
            "message": "",
            "preflight_checks": [],
        }

        if not isinstance(state_row, dict):
            result_row["error_code"] = "E9734"
            result_row["message"] = "Node state row is missing."
            logger.error(
                event="node-execute-missing-state",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9734",
            )
            results.append(result_row)
            failure_count += 1
            continue

        state_row["mechanism"] = mechanism
        current_status = normalize_status(str(state_row.get("status", "pending")))
        if current_status not in {"pending", "failed"}:
            result_row["error_code"] = "E9735"
            result_row["message"] = f"Node status '{current_status}' is not executable without reset/force flow."
            logger.error(
                event="node-execute-invalid-status",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status=current_status,
                error_code="E9735",
            )
            results.append(result_row)
            failure_count += 1
            continue

        try:
            transition_node_state(
                state_row,
                to_state="bootstrapping",
                action="bootstrap-start",
                increment_attempt=True,
                allow_same_state=False,
            )
        except StateTransitionError as exc:
            result_row["error_code"] = "E9731"
            result_row["message"] = str(exc)
            logger.error(
                event="node-execute-transition-error",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9731",
            )
            results.append(result_row)
            failure_count += 1
            continue

        try:
            adapter = get_adapter(mechanism)
        except ValueError as exc:
            transition_node_state(
                state_row,
                to_state="failed",
                action="adapter-resolution-failed",
                last_error=str(exc),
            )
            result_row["error_code"] = "E9732"
            result_row["message"] = str(exc)
            logger.error(
                event="node-execute-adapter-resolution-failed",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9732",
            )
            results.append(result_row)
            failure_count += 1
            continue

        preflight_checks = adapter.preflight(manifest_row, context)
        result_row["preflight_checks"] = _serialize_preflight_checks(preflight_checks)
        if any(not bool(getattr(check, "ok", False)) for check in preflight_checks):
            transition_node_state(
                state_row,
                to_state="failed",
                action="preflight-failed",
                last_error=f"Preflight failed for mechanism '{mechanism}'",
            )
            result_row["error_code"] = "E9733"
            result_row["message"] = "Preflight checks failed."
            logger.error(
                event="node-execute-preflight-failed",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9733",
            )
            results.append(result_row)
            failure_count += 1
            continue

        exec_result = adapter.execute(manifest_row, context)
        if exec_result.is_success():
            transition_node_state(
                state_row,
                to_state="initialized",
                action="bootstrap-complete",
                imported=import_existing,
            )
            result_row["status"] = "success"
            result_row["message"] = str(exec_result.message or "Bootstrap execution completed.")
            logger.info(
                event="node-execute-success",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="initialized",
            )
            results.append(result_row)
            continue

        transition_node_state(
            state_row,
            to_state="failed",
            action="bootstrap-failed",
            last_error=str(exec_result.message or "Adapter execution failed."),
        )
        result_row["error_code"] = str(exec_result.error_code or "E9730")
        result_row["message"] = str(exec_result.message or "Adapter execution failed.")
        logger.error(
            event="node-execute-adapter-failed",
            message=result_row["message"],
            node=node_id,
            mechanism=mechanism,
            status="failed",
            error_code=result_row["error_code"],
        )
        results.append(result_row)
        failure_count += 1

    state_payload["updated_at"] = _utc_now()
    _write_yaml_atomic(state_path, state_payload)

    payload: dict[str, Any] = {
        "status": "executed" if failure_count == 0 else "failed",
        "project_id": project_id,
        "bundle": str(bundle_path),
        "state_path": str(state_path),
        "selected_nodes": sorted(set(selected_nodes)),
        "results": results,
        "failed_count": failure_count,
        "success_count": len(results) - failure_count,
    }
    return (0 if failure_count == 0 else 2), payload


def _verify_selected_nodes(
    *,
    project_id: str,
    bundle_path: Path,
    workspace_ref: str,
    state_path: Path,
    state_payload: dict[str, Any],
    manifest_nodes: list[dict[str, Any]],
    selected_nodes: list[str],
    logger: InitNodeLogger,
) -> tuple[int, dict[str, Any]]:
    state_by_id = _state_index(state_payload)
    manifest_by_id = _manifest_index(manifest_nodes)
    context = AdapterContext(project_id=project_id, bundle_path=bundle_path, workspace_ref=workspace_ref)

    results: list[dict[str, Any]] = []
    failure_count = 0

    for node_id in sorted(set(selected_nodes)):
        state_row = state_by_id.get(node_id)
        manifest_row = manifest_by_id.get(node_id, {"id": node_id, "mechanism": "unknown", "artifacts": []})
        mechanism = str(manifest_row.get("mechanism", "unknown")).strip() or "unknown"

        result_row: dict[str, Any] = {
            "node": node_id,
            "mechanism": mechanism,
            "status": "failed",
            "error_code": "",
            "message": "",
            "handover_checks": [],
        }

        if not isinstance(state_row, dict):
            result_row["error_code"] = "E9734"
            result_row["message"] = "Node state row is missing."
            logger.error(
                event="node-verify-missing-state",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9734",
            )
            results.append(result_row)
            failure_count += 1
            continue

        state_row["mechanism"] = mechanism
        current_status = normalize_status(str(state_row.get("status", "pending")))
        if current_status not in {"initialized", "verified"}:
            result_row["error_code"] = "E9737"
            result_row["message"] = f"Node status '{current_status}' is not eligible for verify-only checks."
            logger.error(
                event="node-verify-invalid-status",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status=current_status,
                error_code="E9737",
            )
            results.append(result_row)
            failure_count += 1
            continue

        try:
            adapter = get_adapter(mechanism)
        except ValueError as exc:
            transition_node_state(
                state_row,
                to_state="failed",
                action="handover-adapter-resolution-failed",
                last_error=str(exc),
            )
            result_row["error_code"] = "E9732"
            result_row["message"] = str(exc)
            logger.error(
                event="node-verify-adapter-resolution-failed",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9732",
            )
            results.append(result_row)
            failure_count += 1
            continue

        handover_checks = adapter.handover(manifest_row, context)
        result_row["handover_checks"] = _serialize_handover_checks(handover_checks)
        if not handover_checks:
            transition_node_state(
                state_row,
                to_state="failed",
                action="handover-empty",
                last_error=f"Handover checks are not defined for mechanism '{mechanism}'",
            )
            result_row["error_code"] = "E9736"
            result_row["message"] = "Adapter returned no handover checks."
            logger.error(
                event="node-verify-empty-checks",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code="E9736",
            )
            results.append(result_row)
            failure_count += 1
            continue

        if any(not bool(getattr(check, "ok", False)) for check in handover_checks):
            transition_node_state(
                state_row,
                to_state="failed",
                action="handover-failed",
                last_error=f"Handover checks failed for mechanism '{mechanism}'",
            )
            error_codes = [str(getattr(check, "error_code", "")).strip() for check in handover_checks]
            error_codes = [code for code in error_codes if code]
            result_row["error_code"] = error_codes[0] if error_codes else "E9738"
            result_row["message"] = "Handover checks failed."
            logger.error(
                event="node-verify-checks-failed",
                message=result_row["message"],
                node=node_id,
                mechanism=mechanism,
                status="failed",
                error_code=result_row["error_code"],
            )
            results.append(result_row)
            failure_count += 1
            continue

        transition_node_state(
            state_row,
            to_state="verified",
            action="handover-verified",
            allow_same_state=True,
        )
        result_row["status"] = "success"
        result_row["message"] = "Handover checks passed."
        logger.info(
            event="node-verify-success",
            message=result_row["message"],
            node=node_id,
            mechanism=mechanism,
            status="verified",
        )
        results.append(result_row)

    state_payload["updated_at"] = _utc_now()
    _write_yaml_atomic(state_path, state_payload)

    payload: dict[str, Any] = {
        "status": "executed" if failure_count == 0 else "failed",
        "project_id": project_id,
        "bundle": str(bundle_path),
        "state_path": str(state_path),
        "selected_nodes": sorted(set(selected_nodes)),
        "results": results,
        "failed_count": failure_count,
        "success_count": len(results) - failure_count,
    }
    return (0 if failure_count == 0 else 2), payload


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_args(args)
    except ValueError as exc:
        print(f"[init-node] ERROR: {exc}")
        return 2

    repo_root = Path(args.repo_root).resolve()
    project_id = str(args.project_id).strip() or "home-lab"
    logger = InitNodeLogger(repo_root=repo_root, project_id=project_id)
    state_path = resolve_state_path(repo_root=repo_root, project_id=project_id)

    if args.status:
        state_payload = _load_yaml_mapping(state_path)
        if not state_payload:
            logger.info(
                event="status-empty",
                message="Initialization state is empty.",
                status="empty",
                details={"state_path": str(state_path)},
            )
            print(json.dumps({"status": "empty", "state_path": str(state_path)}, ensure_ascii=True))
            return 0
        summary = summarize_state(state_payload)
        logger.info(
            event="status-report",
            message="Initialization status summary generated.",
            status="ok",
            details={"total_nodes": summary.total_nodes, "state_path": str(state_path)},
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "state_path": str(state_path),
                    "total_nodes": summary.total_nodes,
                    "by_status": summary.by_status,
                    "updated_at": summary.updated_at,
                },
                ensure_ascii=True,
            )
        )
        return 0

    if not args.skip_environment_check:
        env_report = check_deploy_environment(
            repo_root=repo_root,
            project_id=project_id,
            runner_preference=(str(args.deploy_runner).strip() or None),
            required_tools=["bash"],
        )
        if not env_report.ready:
            issues = list(getattr(env_report, "issues", []))
            warnings = list(getattr(env_report, "warnings", []))
            payload = {
                "status": "environment-error",
                "platform": str(getattr(env_report, "platform", "unknown")),
                "runner": str(getattr(env_report, "runner", "unknown")),
                "issues": issues,
            }
            if warnings:
                payload["warnings"] = warnings
            logger.error(
                event="environment-error",
                message="Deploy environment check failed.",
                status="environment-error",
                error_code="E9700",
                details=payload,
            )
            print(json.dumps(payload, ensure_ascii=True))
            return 2

    bundle_path = _resolve_bundle_for_execution(repo_root=repo_root, bundle_ref=str(args.bundle))
    manifest_nodes = _derive_manifest_nodes(bundle_path)
    state_payload = _ensure_state_baseline(state_path=state_path, manifest_nodes=manifest_nodes)

    target_mode = "node" if str(args.node).strip() else "all-pending"
    target_node = str(args.node).strip() if str(args.node).strip() else None
    manifest_node_ids = {row["id"] for row in manifest_nodes}
    if target_mode == "node" and target_node and target_node not in manifest_node_ids:
        logger.error(
            event="node-not-found",
            message=f"Node '{target_node}' is not present in bundle manifest.",
            node=target_node,
            status="node-not-found",
            error_code="E9739",
            details={"available_nodes": sorted(manifest_node_ids)},
        )
        print(
            json.dumps(
                {
                    "status": "node-not-found",
                    "node": target_node,
                    "available_nodes": sorted(manifest_node_ids),
                    "bundle": str(bundle_path),
                },
                ensure_ascii=True,
            )
        )
        return 2

    selected_nodes = [target_node] if target_node else []
    if target_mode == "all-pending":
        for row in state_payload.get("nodes", []):
            if isinstance(row, dict) and str(row.get("status", "")).strip() == "pending":
                selected_nodes.append(str(row.get("id", "")).strip())
        selected_nodes = [node_id for node_id in selected_nodes if node_id]

    plan_payload = {
        "status": "planned",
        "project_id": project_id,
        "bundle": str(bundle_path),
        "state_path": str(state_path),
        "mode": target_mode,
        "selected_nodes": sorted(set(selected_nodes)),
        "verify_only": bool(args.verify_only),
        "force": bool(args.force),
        "import_existing": bool(args.import_existing),
        "reset": bool(args.reset),
        "acknowledge_drift": bool(args.acknowledge_drift),
        "plan_only": bool(args.plan_only),
        "bootstrap_runner_tools": bool(args.bootstrap_runner_tools),
        "runner_tools": _parse_runner_tools(str(args.runner_tools)),
        "phase": str(args.phase),
        "bootstrap_secret_file": str(args.bootstrap_secret_file or ""),
    }
    if args.plan_only:
        logger.info(
            event="plan-generated",
            message="Init-node plan generated.",
            status="planned",
            details={"mode": target_mode, "selected_nodes": sorted(set(selected_nodes))},
        )
        print(json.dumps(plan_payload, ensure_ascii=True))
        return 0

    if not selected_nodes:
        logger.info(
            event="no-op",
            message="No nodes selected for execution.",
            status="no-op",
            details={"mode": target_mode},
        )
        print(
            json.dumps(
                {
                    "status": "no-op",
                    "project_id": project_id,
                    "bundle": str(bundle_path),
                    "state_path": str(state_path),
                    "mode": target_mode,
                    "selected_nodes": [],
                },
                ensure_ascii=True,
            )
        )
        return 0

    runner_preference = str(args.deploy_runner).strip() or None
    try:
        runner = get_runner(runner_preference, repo_root=repo_root, project_id=project_id)
    except Exception as exc:
        payload = {
            "status": "runner-error",
            "project_id": project_id,
            "bundle": str(bundle_path),
            "message": str(exc),
        }
        logger.error(
            event="runner-init-failed",
            message=str(exc),
            status="runner-error",
            error_code="E9701",
            details={"runner_preference": runner_preference or "<auto>"},
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 2

    workspace_ref = ""
    try:
        workspace_ref = runner.stage_bundle(bundle_path)
    except Exception as exc:
        payload = {
            "status": "runner-stage-error",
            "project_id": project_id,
            "bundle": str(bundle_path),
            "runner": runner.name,
            "message": str(exc),
        }
        logger.error(
            event="runner-stage-failed",
            message=str(exc),
            status="runner-stage-error",
            error_code="E9702",
            details={"runner": runner.name, "bundle": str(bundle_path)},
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 2

    logger.info(
        event="runner-stage-success",
        message="Bundle staged in runner workspace.",
        status="staged",
        details={"runner": runner.name, "workspace_ref": workspace_ref},
    )
    previous_phase = os.environ.get("INIT_NODE_PHASE")
    os.environ["INIT_NODE_PHASE"] = str(args.phase)

    required_runner_tools = _parse_runner_tools(str(args.runner_tools))
    toolchain_ok, toolchain_payload = _ensure_runner_toolchain(
        runner=runner,
        workspace_ref=workspace_ref,
        bootstrap_enabled=bool(args.bootstrap_runner_tools),
        required_tools=required_runner_tools,
        install_command=str(args.runner_tools_install_command),
    )
    if not toolchain_ok:
        payload = {
            "status": "runner-tools-error",
            "project_id": project_id,
            "bundle": str(bundle_path),
            "runner": runner.name,
            **toolchain_payload,
        }
        logger.error(
            event="runner-tools-error",
            message=str(toolchain_payload.get("message", "Runner toolchain checks failed.")),
            status="runner-tools-error",
            error_code="E9704",
            details=payload,
        )
        try:
            runner.cleanup_workspace(workspace_ref)
        except Exception:  # pragma: no cover - defensive
            pass
        print(json.dumps(payload, ensure_ascii=True))
        return 2
    logger.info(
        event="runner-tools-ready",
        message=str(toolchain_payload.get("message", "Runner toolchain checks passed.")),
        status="runner-tools-ready",
        details={
            "runner": runner.name,
            "required_tools": required_runner_tools,
            "bootstrap_runner_tools": bool(args.bootstrap_runner_tools),
        },
    )
    contract_ok, contract_payload = _prepare_bootstrap_ssh_contract_env(
        repo_root=repo_root,
        project_id=project_id,
        node_id=(target_node if target_mode == "node" else None),
        phase=str(args.phase),
        verify_only=bool(args.verify_only),
        bootstrap_secret_file=str(args.bootstrap_secret_file or ""),
    )
    if not contract_ok:
        payload = {
            "status": "bootstrap-secret-error",
            "project_id": project_id,
            "bundle": str(bundle_path),
            "runner": runner.name,
            **contract_payload,
        }
        logger.error(
            event="bootstrap-secret-error",
            message=str(contract_payload.get("message", "Bootstrap secret resolution failed.")),
            status="bootstrap-secret-error",
            error_code="E9705",
            details=payload,
        )
        try:
            runner.cleanup_workspace(workspace_ref)
        except Exception:  # pragma: no cover - defensive
            pass
        print(json.dumps(payload, ensure_ascii=True))
        return 2
    logger.info(
        event="bootstrap-secret-ready",
        message=str(contract_payload.get("message", "Bootstrap secret contract checks completed.")),
        status="bootstrap-secret-ready",
        details={key: value for key, value in contract_payload.items() if key != "password"},
    )

    try:
        try:
            if args.verify_only:
                exit_code, execution_payload = _verify_selected_nodes(
                    project_id=project_id,
                    bundle_path=bundle_path,
                    workspace_ref=workspace_ref,
                    state_path=state_path,
                    state_payload=state_payload,
                    manifest_nodes=manifest_nodes,
                    selected_nodes=selected_nodes,
                    logger=logger,
                )
            else:
                exit_code, execution_payload = _execute_selected_nodes(
                    project_id=project_id,
                    bundle_path=bundle_path,
                    workspace_ref=workspace_ref,
                    state_path=state_path,
                    state_payload=state_payload,
                    manifest_nodes=manifest_nodes,
                    selected_nodes=selected_nodes,
                    import_existing=bool(args.import_existing),
                    logger=logger,
                )
        finally:
            try:
                runner.cleanup_workspace(workspace_ref)
                logger.info(
                    event="runner-cleanup-success",
                    message="Runner workspace cleanup completed.",
                    status="cleanup",
                    details={"runner": runner.name, "workspace_ref": workspace_ref},
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    event="runner-cleanup-failed",
                    message=str(exc),
                    status="cleanup-warning",
                    error_code="E9703",
                    details={"runner": runner.name, "workspace_ref": workspace_ref},
                )
    finally:
        if previous_phase is None:
            os.environ.pop("INIT_NODE_PHASE", None)
        else:
            os.environ["INIT_NODE_PHASE"] = previous_phase
    execution_payload["mode"] = target_mode
    execution_payload["plan_only"] = False
    execution_payload["verify_only"] = bool(args.verify_only)
    execution_payload["runner"] = runner.name
    execution_payload["workspace_ref"] = workspace_ref
    execution_payload["phase"] = str(args.phase)
    print(json.dumps(execution_payload, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
