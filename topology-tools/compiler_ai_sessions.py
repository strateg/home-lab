"""AI session preparation and execution for compile-topology orchestration.

Extended to include AiSessionRunner class for running advisory and assisted sessions.
Extracted from compile-topology.py to satisfy ADR 0069 thin orchestrator requirement.

ADR Reference: ADR 0069 (thin orchestrator), ADR 0094 (AI advisory mode)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_runtime.ai_advisory_contract import (
    build_ai_input_payload,
    parse_ai_output_payload,
    validate_ai_contract_payloads,
)
from ai_runtime.ai_ansible import (
    build_ansible_input_adapter,
    parse_ansible_output_candidates,
    validate_ansible_candidates_with_lint,
)
from ai_runtime.ai_assisted import build_candidate_diff, materialize_candidate_artifacts
from ai_runtime.ai_audit import AiAuditLogger, cleanup_ai_audit_logs
from ai_runtime.ai_promotion import promote_approved_candidates, resolve_approvals
from ai_runtime.ai_rollback import list_ai_promoted_artifacts, rollback_ai_promoted_artifacts
from ai_runtime.ai_sandbox import (
    cleanup_ai_sandbox_sessions,
    create_ai_sandbox_session,
    enforce_sandbox_resource_limits,
    ensure_relative_sandbox_path,
    sanitize_environment,
)
from yaml_loader import load_yaml_file

if TYPE_CHECKING:
    from kernel import PluginContext, Stage

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AiConfig:
    advisory: bool = False
    assisted: bool = False
    output_json: Path | None = None
    audit_retention_days: int = 30
    sandbox_retention_days: int = 7
    sandbox_max_files: int = 128
    sandbox_max_bytes: int = 10 * 1024 * 1024
    promote_approved: bool = False
    approve_all: bool = False
    approve_paths: tuple[str, ...] = ()
    rollback_all: bool = False
    rollback_paths: tuple[str, ...] = ()
    rollback_ref: str = "HEAD"
    ansible_lint: bool = False
    ansible_lint_cmd: str = "ansible-lint"
    advisory_max_latency_seconds: float = 60.0
    assisted_max_latency_seconds: float = 300.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_retention_days", max(1, int(self.audit_retention_days)))
        object.__setattr__(self, "sandbox_retention_days", max(1, int(self.sandbox_retention_days)))
        object.__setattr__(self, "sandbox_max_files", max(1, int(self.sandbox_max_files)))
        object.__setattr__(self, "sandbox_max_bytes", max(1, int(self.sandbox_max_bytes)))
        object.__setattr__(self, "approve_paths", tuple(path.strip() for path in self.approve_paths if path.strip()))
        object.__setattr__(
            self,
            "rollback_paths",
            tuple(path.strip() for path in self.rollback_paths if path.strip()),
        )
        object.__setattr__(self, "rollback_ref", self.rollback_ref.strip() or "HEAD")
        object.__setattr__(self, "ansible_lint_cmd", self.ansible_lint_cmd.strip() or "ansible-lint")
        object.__setattr__(self, "advisory_max_latency_seconds", max(1.0, float(self.advisory_max_latency_seconds)))
        object.__setattr__(self, "assisted_max_latency_seconds", max(1.0, float(self.assisted_max_latency_seconds)))


@dataclass(frozen=True)
class AiSessionPreparation:
    mode: str
    request_id: str
    cleaned_audit_logs: list[Path]
    cleaned_sandbox_sessions: list[Path]
    sandbox_session: Path
    sandbox_usage: dict[str, int]
    sanitized_env: dict[str, str]
    removed_env_keys: list[str]
    audit: AiAuditLogger
    safe_effective_payload: dict[str, Any]
    ansible_adapter: dict[str, Any]
    annotation_patterns: tuple[re.Pattern[str], ...]
    registry_patterns: tuple[re.Pattern[str], ...]
    prompt_profile: str
    ai_input: dict[str, Any]


def json_safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = json.loads(json.dumps(payload, ensure_ascii=True, default=str))
    return parsed if isinstance(parsed, dict) else {}


def prepare_ai_session(
    *,
    ai_config: AiConfig,
    repo_root: Path,
    mode: str,
    effective_payload: dict[str, Any],
    project_id: str,
    plugin_id: str,
    stages: Sequence[Any],
    enforce_initial_sandbox_limits: bool,
    annotation_patterns: tuple[re.Pattern[str], ...],
    registry_patterns: tuple[re.Pattern[str], ...],
    env: Mapping[str, str] | None = None,
) -> AiSessionPreparation:
    request_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    request_token = f"{project_id}-{request_id}"
    cleaned_audit_logs = cleanup_ai_audit_logs(
        repo_root=repo_root,
        project_id=project_id,
        retain_days=ai_config.audit_retention_days,
    )
    cleaned_sandbox_sessions = cleanup_ai_sandbox_sessions(
        repo_root=repo_root,
        project_id=project_id,
        retain_days=ai_config.sandbox_retention_days,
    )
    sandbox_session = create_ai_sandbox_session(
        repo_root=repo_root,
        project_id=project_id,
        request_id=request_token,
    )
    _ = ensure_relative_sandbox_path(sandbox_session=sandbox_session, relative_path="ai-output.json")
    sandbox_usage = (
        enforce_sandbox_resource_limits(
            sandbox_session=sandbox_session,
            max_files=ai_config.sandbox_max_files,
            max_bytes=ai_config.sandbox_max_bytes,
        )
        if enforce_initial_sandbox_limits
        else {"files": 0, "bytes": 0}
    )
    sanitized_env, removed_env_keys = sanitize_environment(dict(os.environ if env is None else env))
    audit = AiAuditLogger(
        repo_root=repo_root,
        project_id=project_id,
        request_id=request_token,
    )
    safe_effective_payload = json_safe_payload(effective_payload)
    ansible_adapter = build_ansible_input_adapter(safe_effective_payload)
    stable_projection = {
        "classes": safe_effective_payload.get("classes", {}),
        "objects": safe_effective_payload.get("objects", {}),
        "instances": safe_effective_payload.get("instances", {}),
    }
    artifact_plan = {
        "mode": mode,
        "stages": [stage.value for stage in stages],
    }
    prompt_profile = "ansible_family" if ansible_adapter.get("hosts") else "generic_topology"
    ai_input = build_ai_input_payload(
        artifact_family="topology",
        mode=mode,
        plugin_id=plugin_id,
        effective_json=safe_effective_payload,
        stable_projection=stable_projection,
        artifact_plan=artifact_plan,
        generation_context_extra={"prompt_profile": prompt_profile},
        extra_key_patterns=annotation_patterns + registry_patterns,
    )
    return AiSessionPreparation(
        mode=mode,
        request_id=request_token,
        cleaned_audit_logs=cleaned_audit_logs,
        cleaned_sandbox_sessions=cleaned_sandbox_sessions,
        sandbox_session=sandbox_session,
        sandbox_usage=sandbox_usage,
        sanitized_env=sanitized_env,
        removed_env_keys=removed_env_keys,
        audit=audit,
        safe_effective_payload=safe_effective_payload,
        ansible_adapter=ansible_adapter,
        annotation_patterns=annotation_patterns,
        registry_patterns=registry_patterns,
        prompt_profile=prompt_profile,
        ai_input=ai_input,
    )


class AiSessionRunner:
    """Runs AI advisory and assisted sessions.

    Extracted from V5Compiler to maintain thin orchestrator pattern.
    Handles all AI session logic including preparation, execution,
    validation, promotion, and rollback.

    ADR Reference: ADR 0069 (thin orchestrator), ADR 0094 (AI advisory mode)
    """

    def __init__(
        self,
        *,
        ai_config: AiConfig,
        repo_root: Path,
        stages: Sequence[Stage],
        add_diag: Callable[..., None],
        path_for_diag: Callable[[Path], str],
    ) -> None:
        """Initialize AI session runner.

        Args:
            ai_config: AI configuration settings
            repo_root: Repository root path
            stages: List of compilation stages
            add_diag: Callback to add diagnostics to compiler
            path_for_diag: Callback to format paths for diagnostics
        """
        self.ai_config = ai_config
        self.repo_root = repo_root
        self.stages = stages
        self.add_diag = add_diag
        self.path_for_diag = path_for_diag

    @staticmethod
    def _advisory_payload_hash(payload: dict[str, Any]) -> str:
        """Compute SHA256 hash of advisory payload."""
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"sha256-{digest}"

    @staticmethod
    def _extract_path_leaf_token(path: str) -> str:
        """Extract leaf token from dotted path."""
        token = path.split(".")[-1].strip()
        token = re.sub(r"\[\d+\]", "", token)
        return token

    def _collect_annotation_redaction_patterns(
        self, plugin_ctx: PluginContext | None
    ) -> tuple[re.Pattern[str], ...]:
        """Collect patterns for redacting secret annotations."""
        if plugin_ctx is None:
            return ()
        names: set[str] = set()
        published = plugin_ctx.get_published_data().get("base.compiler.annotation_resolver", {})
        for key in ("object_secret_annotations", "row_annotations_by_instance"):
            container = published.get(key)
            if not isinstance(container, dict):
                continue
            for _, annotations in container.items():
                if not isinstance(annotations, dict):
                    continue
                for path, spec in annotations.items():
                    if not isinstance(path, str) or not isinstance(spec, dict):
                        continue
                    if not bool(spec.get("secret")):
                        continue
                    leaf = self._extract_path_leaf_token(path)
                    if leaf:
                        names.add(leaf)
        return tuple(re.compile(re.escape(name), re.IGNORECASE) for name in sorted(names))

    def _collect_registry_redaction_patterns(
        self, plugin_ctx: PluginContext | None
    ) -> tuple[re.Pattern[str], ...]:
        """Collect patterns for redacting registry secrets."""
        if plugin_ctx is None:
            return ()
        secrets_root_raw = plugin_ctx.config.get("secrets_root")
        if not isinstance(secrets_root_raw, str) or not secrets_root_raw.strip():
            return ()
        secrets_root = Path(secrets_root_raw.strip())
        if not secrets_root.is_absolute():
            secrets_root = (self.repo_root / secrets_root).resolve()
        instances_dir = secrets_root / "instances"
        if not instances_dir.exists() or not instances_dir.is_dir():
            return ()

        names: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if isinstance(key, str) and key not in {"sops", "instance"}:
                        names.add(key.strip())
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        for path in sorted(instances_dir.glob("*.yaml")):
            try:
                payload = load_yaml_file(path) or {}
            except Exception:
                continue
            walk(payload)
        filtered_names = {name for name in names if name}
        return tuple(re.compile(re.escape(name), re.IGNORECASE) for name in sorted(filtered_names))

    def _load_ai_output_payload(self) -> dict[str, Any] | None:
        """Load and validate AI output JSON payload."""
        if self.ai_config.output_json is None:
            return None
        path = self.ai_config.output_json
        if not path.exists() or not path.is_file():
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message=f"AI advisory output JSON does not exist: {path}",
                path=self.path_for_diag(path),
            )
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message=f"AI advisory output JSON parse error: {exc}",
                path=self.path_for_diag(path),
            )
            return None
        if not isinstance(payload, dict):
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message="AI advisory output JSON root must be an object.",
                path=self.path_for_diag(path),
            )
            return None
        return payload

    def _print_advisory_recommendations(self, parsed_output: dict[str, Any]) -> None:
        """Print advisory recommendations to logger."""
        recommendations = parsed_output.get("recommendations", [])
        confidence_scores = parsed_output.get("confidence_scores", {})
        LOGGER.info("[ai-advisory] Recommendations:")
        if not isinstance(recommendations, list) or not recommendations:
            LOGGER.info("[ai-advisory] - No recommendations.")
            return
        for index, row in enumerate(recommendations, start=1):
            if not isinstance(row, dict):
                continue
            path = str(row.get("path", "<unknown>"))
            action = str(row.get("action", "suggest"))
            rationale = str(row.get("rationale", "")).strip()
            score = confidence_scores.get(path) if isinstance(confidence_scores, dict) else None
            score_token = f"{float(score):.2f}" if isinstance(score, (int, float)) else "n/a"
            LOGGER.info(f"[ai-advisory] {index}. {action} {path} (confidence={score_token})")
            if rationale:
                LOGGER.info(f"[ai-advisory]    rationale: {rationale}")

    def _prepare_session(
        self,
        *,
        mode: str,
        effective_payload: dict[str, Any],
        project_id: str,
        plugin_ctx: PluginContext | None,
        plugin_id: str,
        enforce_initial_sandbox_limits: bool,
    ) -> AiSessionPreparation:
        """Prepare an AI session with all required context."""
        return prepare_ai_session(
            ai_config=self.ai_config,
            repo_root=self.repo_root,
            mode=mode,
            effective_payload=effective_payload,
            project_id=project_id,
            plugin_id=plugin_id,
            stages=self.stages,
            enforce_initial_sandbox_limits=enforce_initial_sandbox_limits,
            annotation_patterns=self._collect_annotation_redaction_patterns(plugin_ctx),
            registry_patterns=self._collect_registry_redaction_patterns(plugin_ctx),
        )

    def run_advisory_session(
        self,
        *,
        effective_payload: dict[str, Any],
        project_id: str,
        plugin_ctx: PluginContext | None,
    ) -> None:
        """Run AI advisory session (read-only recommendations).

        Args:
            effective_payload: Compiled effective topology payload
            project_id: Active project identifier
            plugin_ctx: Plugin context for accessing published data
        """
        start_ts = time.monotonic()
        session = self._prepare_session(
            mode="advisory",
            effective_payload=effective_payload,
            project_id=project_id,
            plugin_ctx=plugin_ctx,
            plugin_id="base.compiler.ai_advisory",
            enforce_initial_sandbox_limits=True,
        )
        if session.cleaned_audit_logs:
            LOGGER.info(f"[ai-advisory] Cleaned {len(session.cleaned_audit_logs)} old audit day folders.")
        if session.cleaned_sandbox_sessions:
            LOGGER.info(f"[ai-advisory] Cleaned {len(session.cleaned_sandbox_sessions)} old sandbox sessions.")
        LOGGER.info(f"[ai-advisory] Sandbox session: {self.path_for_diag(session.sandbox_session)}")

        ai_input = session.ai_input
        ai_output = self._load_ai_output_payload()
        errors = validate_ai_contract_payloads(ai_input=ai_input, ai_output=ai_output, ctx=plugin_ctx)
        if errors:
            for message in errors:
                self.add_diag(
                    code="E8941",
                    severity="error",
                    stage="validate",
                    message=message,
                    path="ai-advisory:contract",
                )
            session.audit.log_event(
                event_type="candidate_validation_result",
                payload={"mode": "advisory", "status": "contract_error", "errors": errors},
                input_hash=str(ai_input.get("input_hash", "")),
            )
            return

        input_hash = str(ai_input.get("input_hash", ""))
        session.audit.log_event(
            event_type="ai_request_sent",
            payload={
                "mode": "advisory",
                "sandbox_session": self.path_for_diag(session.sandbox_session),
                "sandbox_usage": session.sandbox_usage,
                "sandbox_limits": {
                    "max_files": self.ai_config.sandbox_max_files,
                    "max_bytes": self.ai_config.sandbox_max_bytes,
                },
                "annotation_pattern_count": len(session.annotation_patterns),
                "registry_pattern_count": len(session.registry_patterns),
                "env_keys_forwarded": len(session.sanitized_env),
                "env_keys_removed": session.removed_env_keys,
            },
            input_hash=input_hash,
        )

        parsed: dict[str, Any] = {"recommendations": [], "confidence_scores": {}, "metadata": {}}
        output_hash = ""
        if ai_output is not None:
            output_hash = self._advisory_payload_hash(ai_output)
            parsed = parse_ai_output_payload(ai_output)
            session.audit.log_event(
                event_type="ai_response_received",
                payload={
                    "mode": "advisory",
                    "recommendation_count": len(parsed.get("recommendations", [])),
                },
                input_hash=input_hash,
                output_hash=output_hash,
            )

        self._print_advisory_recommendations(parsed)
        session.audit.log_event(
            event_type="candidate_validation_result",
            payload={
                "mode": "advisory",
                "status": "completed",
                "recommendation_count": len(parsed.get("recommendations", [])),
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )

        elapsed = time.monotonic() - start_ts
        if elapsed > self.ai_config.advisory_max_latency_seconds:
            self.add_diag(
                code="W8941",
                severity="warning",
                stage="validate",
                message=(
                    "AI advisory latency exceeded configured limit: "
                    f"{elapsed:.2f}s > {self.ai_config.advisory_max_latency_seconds:.2f}s"
                ),
                path="ai-advisory:latency",
            )
        LOGGER.info(f"[ai-advisory] Audit log: {self.path_for_diag(session.audit.log_path)}")

    def run_assisted_session(
        self,
        *,
        effective_payload: dict[str, Any],
        project_id: str,
        plugin_ctx: PluginContext | None,
    ) -> None:
        """Run AI assisted session (candidate artifacts in sandbox).

        Args:
            effective_payload: Compiled effective topology payload
            project_id: Active project identifier
            plugin_ctx: Plugin context for accessing published data
        """
        start_ts = time.monotonic()
        session = self._prepare_session(
            mode="assisted",
            effective_payload=effective_payload,
            project_id=project_id,
            plugin_ctx=plugin_ctx,
            plugin_id="base.compiler.ai_assisted",
            enforce_initial_sandbox_limits=False,
        )
        if session.cleaned_audit_logs:
            LOGGER.info(f"[ai-assisted] Cleaned {len(session.cleaned_audit_logs)} old audit day folders.")
        if session.cleaned_sandbox_sessions:
            LOGGER.info(f"[ai-assisted] Cleaned {len(session.cleaned_sandbox_sessions)} old sandbox sessions.")
        LOGGER.info(f"[ai-assisted] Sandbox session: {self.path_for_diag(session.sandbox_session)}")

        ai_input = session.ai_input
        ai_output = self._load_ai_output_payload()
        errors = validate_ai_contract_payloads(ai_input=ai_input, ai_output=ai_output, ctx=plugin_ctx)
        if errors:
            for message in errors:
                self.add_diag(
                    code="E8941",
                    severity="error",
                    stage="validate",
                    message=message,
                    path="ai-assisted:contract",
                )
            session.audit.log_event(
                event_type="candidate_validation_result",
                payload={"mode": "assisted", "status": "contract_error", "errors": errors},
                input_hash=str(ai_input.get("input_hash", "")),
            )
            return

        input_hash = str(ai_input.get("input_hash", ""))
        session.audit.log_event(
            event_type="ai_request_sent",
            payload={
                "mode": "assisted",
                "sandbox_session": self.path_for_diag(session.sandbox_session),
                "annotation_pattern_count": len(session.annotation_patterns),
                "registry_pattern_count": len(session.registry_patterns),
                "env_keys_forwarded": len(session.sanitized_env),
                "env_keys_removed": session.removed_env_keys,
            },
            input_hash=input_hash,
        )

        # Handle rollback request
        rollback_requested = self.ai_config.rollback_all or bool(self.ai_config.rollback_paths)
        if rollback_requested:
            self._handle_rollback(session, input_hash, project_id)
            return

        if ai_output is None:
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message="AI assisted mode requires --ai-output-json payload.",
                path="ai-assisted:output",
            )
            return

        output_hash = self._advisory_payload_hash(ai_output)
        parsed = parse_ai_output_payload(ai_output)
        raw_candidates = ai_output.get("candidate_artifacts")
        candidates = raw_candidates if isinstance(raw_candidates, list) else []

        accepted, rejected = materialize_candidate_artifacts(
            repo_root=self.repo_root,
            sandbox_session=session.sandbox_session,
            project_id=project_id,
            candidates=[row for row in candidates if isinstance(row, dict)],
        )

        for row in accepted:
            diff_payload = build_candidate_diff(
                baseline_path=Path(row["baseline_path"]),
                candidate_path=Path(row["candidate_path"]),
                logical_path=str(row["path"]),
            )
            LOGGER.info(
                f"[ai-assisted] {diff_payload['change_type']}: "
                f"{diff_payload['path']} (added_lines={diff_payload['added_lines']})"
            )
            confidence = parsed.get("confidence_scores", {}).get(str(row["path"]))
            if isinstance(confidence, (int, float)):
                LOGGER.info(f"[ai-assisted]   confidence: {float(confidence):.2f}")

        if rejected:
            for row in rejected:
                LOGGER.info(f"[ai-assisted] rejected: {row['path']} ({row['reason']})")

        # Ansible lint validation
        ansible_candidates = parse_ansible_output_candidates(project_id=project_id, ai_output=ai_output)
        if self.ai_config.ansible_lint and ansible_candidates:
            lint_failures = validate_ansible_candidates_with_lint(
                candidates=accepted,
                lint_cmd=self.ai_config.ansible_lint_cmd,
            )
            if lint_failures:
                rejected.extend(lint_failures)
                accepted = [
                    row
                    for row in accepted
                    if str(row.get("path", "")) not in {f["path"] for f in lint_failures}
                ]
                for item in lint_failures:
                    LOGGER.info(f"[ai-assisted] lint-rejected: {item['path']} ({item['reason']})")

        enforce_sandbox_resource_limits(
            sandbox_session=session.sandbox_session,
            max_files=self.ai_config.sandbox_max_files,
            max_bytes=self.ai_config.sandbox_max_bytes,
        )

        # Resolve approvals
        approve_paths_set = set(self.ai_config.approve_paths)
        approved, approval_rejected = resolve_approvals(
            candidates=accepted,
            approve_all=self.ai_config.approve_all,
            approve_paths=approve_paths_set,
        )

        session.audit.log_event(
            event_type="human_approval_decision",
            payload={
                "mode": "assisted",
                "approve_all": self.ai_config.approve_all,
                "approved_count": len(approved),
                "rejected_count": len(approval_rejected),
                "approved_paths": [str(row.get("path", "")) for row in approved],
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )

        # Handle promotion
        promoted: list[dict[str, str]] = []
        if self.ai_config.promote_approved:
            if not approved:
                LOGGER.info("[ai-assisted] promotion skipped: no approved candidates.")
            else:
                promoted = promote_approved_candidates(repo_root=self.repo_root, approved=approved)
                for row in promoted:
                    LOGGER.info(f"[ai-assisted] promoted: {row['path']}")
        else:
            LOGGER.info("[ai-assisted] promotion gate: disabled (use --ai-promote-approved).")

        session.audit.log_event(
            event_type="ai_response_received",
            payload={
                "mode": "assisted",
                "candidate_count": len(candidates),
                "accepted_candidates": len(accepted),
                "rejected_candidates": len(rejected),
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )
        session.audit.log_event(
            event_type="candidate_validation_result",
            payload={
                "mode": "assisted",
                "status": "completed",
                "accepted_candidates": len(accepted),
                "rejected_candidates": len(rejected),
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )
        session.audit.log_event(
            event_type="candidate_promotion_result",
            payload={
                "mode": "assisted",
                "promotion_enabled": self.ai_config.promote_approved,
                "promoted_count": len(promoted),
                "promoted_paths": [row["path"] for row in promoted],
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )

        elapsed = time.monotonic() - start_ts
        if elapsed > self.ai_config.assisted_max_latency_seconds:
            self.add_diag(
                code="W8941",
                severity="warning",
                stage="validate",
                message=(
                    "AI assisted latency exceeded configured limit: "
                    f"{elapsed:.2f}s > {self.ai_config.assisted_max_latency_seconds:.2f}s"
                ),
                path="ai-assisted:latency",
            )
        LOGGER.info(f"[ai-assisted] Audit log: {self.path_for_diag(session.audit.log_path)}")

    def _handle_rollback(
        self,
        session: AiSessionPreparation,
        input_hash: str,
        project_id: str,
    ) -> None:
        """Handle rollback of AI-promoted artifacts."""
        rollback_candidates = list_ai_promoted_artifacts(repo_root=self.repo_root, project_id=project_id)
        if self.ai_config.rollback_all:
            targets = rollback_candidates
        else:
            wanted = set(self.ai_config.rollback_paths)
            targets = [row for row in rollback_candidates if str(row.get("path", "")) in wanted]

        rollback = rollback_ai_promoted_artifacts(
            repo_root=self.repo_root,
            artifacts=targets,
            ref=self.ai_config.rollback_ref,
        )
        LOGGER.info(
            "[ai-assisted] rollback: "
            f"restored={len(rollback['restored'])} "
            f"deleted={len(rollback['deleted'])} "
            f"failed={len(rollback['failed'])} "
            f"duration={rollback['duration_seconds']:.3f}s"
        )
        session.audit.log_event(
            event_type="rollback_result",
            payload={
                "mode": "assisted",
                "ref": self.ai_config.rollback_ref,
                "target_count": len(targets),
                "restored": rollback["restored"],
                "deleted": rollback["deleted"],
                "failed": rollback["failed"],
                "duration_seconds": rollback["duration_seconds"],
            },
            input_hash=input_hash,
        )
        LOGGER.info(f"[ai-assisted] Audit log: {self.path_for_diag(session.audit.log_path)}")
