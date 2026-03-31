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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from .adapters import AdapterContext, get_adapter
from .bundle import inspect_bundle, resolve_bundle_path, resolve_bundles_root
from .environment import check_deploy_environment
from .state import StateTransitionError, build_default_node_state, normalize_status, transition_node_state

STATE_FILE_NAME = "INITIALIZATION-STATE.yaml"


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
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--confirm-reset", action="store_true")
    parser.add_argument("--acknowledge-drift", action="store_true")
    parser.add_argument("--plan-only", action="store_true", help="Render execution plan only, no state mutation.")
    parser.add_argument("--skip-environment-check", action="store_true")
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


def _derive_manifest_nodes(bundle_path: Path) -> list[dict[str, str]]:
    details = inspect_bundle(bundle_path, verify_checksums=True)
    nodes_payload = details.get("manifest", {}).get("nodes", [])
    result: list[dict[str, str]] = []
    for row in nodes_payload if isinstance(nodes_payload, list) else []:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("id", "")).strip()
        mechanism = str(row.get("mechanism", "")).strip() or "unknown"
        if node_id:
            result.append({"id": node_id, "mechanism": mechanism})
    result.sort(key=lambda item: item["id"])
    return result


def _resolve_bundle_for_execution(*, repo_root: Path, bundle_ref: str) -> Path:
    bundles_root = resolve_bundles_root(repo_root)
    bundle_path = resolve_bundle_path(bundles_root, bundle_ref.strip())
    if not bundle_path.exists() or not bundle_path.is_dir():
        raise FileNotFoundError(f"Deploy bundle not found: {bundle_path}")
    return bundle_path


def _ensure_state_baseline(*, state_path: Path, manifest_nodes: list[dict[str, str]]) -> dict[str, Any]:
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


def _manifest_index(manifest_nodes: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
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


def _execute_selected_nodes(
    *,
    project_id: str,
    bundle_path: Path,
    state_path: Path,
    state_payload: dict[str, Any],
    manifest_nodes: list[dict[str, str]],
    selected_nodes: list[str],
    import_existing: bool,
) -> tuple[int, dict[str, Any]]:
    state_by_id = _state_index(state_payload)
    manifest_by_id = _manifest_index(manifest_nodes)
    context = AdapterContext(project_id=project_id, bundle_path=bundle_path, workspace_ref=str(bundle_path))

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
            results.append(result_row)
            failure_count += 1
            continue

        state_row["mechanism"] = mechanism
        current_status = normalize_status(str(state_row.get("status", "pending")))
        if current_status not in {"pending", "failed"}:
            result_row["error_code"] = "E9735"
            result_row["message"] = f"Node status '{current_status}' is not executable without reset/force flow."
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


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_args(args)
    except ValueError as exc:
        print(f"[init-node] ERROR: {exc}")
        return 2

    repo_root = Path(args.repo_root).resolve()
    project_id = str(args.project_id).strip() or "home-lab"
    state_path = resolve_state_path(repo_root=repo_root, project_id=project_id)

    if args.status:
        state_payload = _load_yaml_mapping(state_path)
        if not state_payload:
            print(json.dumps({"status": "empty", "state_path": str(state_path)}, ensure_ascii=True))
            return 0
        summary = summarize_state(state_payload)
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
            print(json.dumps(payload, ensure_ascii=True))
            return 2

    bundle_path = _resolve_bundle_for_execution(repo_root=repo_root, bundle_ref=str(args.bundle))
    manifest_nodes = _derive_manifest_nodes(bundle_path)
    state_payload = _ensure_state_baseline(state_path=state_path, manifest_nodes=manifest_nodes)

    target_mode = "node" if str(args.node).strip() else "all-pending"
    target_node = str(args.node).strip() if str(args.node).strip() else None
    manifest_node_ids = {row["id"] for row in manifest_nodes}
    if target_mode == "node" and target_node and target_node not in manifest_node_ids:
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
    }
    if args.plan_only:
        print(json.dumps(plan_payload, ensure_ascii=True))
        return 0

    if args.verify_only:
        print(
            json.dumps(
                {
                    "status": "not-implemented",
                    "message": "Execution mode with --verify-only is not implemented yet. Use --plan-only.",
                    "project_id": project_id,
                    "bundle": str(bundle_path),
                    "state_path": str(state_path),
                    "mode": target_mode,
                    "selected_nodes": sorted(set(selected_nodes)),
                },
                ensure_ascii=True,
            )
        )
        return 2

    if not selected_nodes:
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

    exit_code, execution_payload = _execute_selected_nodes(
        project_id=project_id,
        bundle_path=bundle_path,
        state_path=state_path,
        state_payload=state_payload,
        manifest_nodes=manifest_nodes,
        selected_nodes=selected_nodes,
        import_existing=bool(args.import_existing),
    )
    execution_payload["mode"] = target_mode
    execution_payload["plan_only"] = False
    print(json.dumps(execution_payload, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
