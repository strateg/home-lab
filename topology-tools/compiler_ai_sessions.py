"""AI session preparation helpers for compile-topology orchestration."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plugins.generators.ai_advisory_contract import build_ai_input_payload
from plugins.generators.ai_ansible import build_ansible_input_adapter
from plugins.generators.ai_audit import AiAuditLogger, cleanup_ai_audit_logs
from plugins.generators.ai_sandbox import (
    cleanup_ai_sandbox_sessions,
    create_ai_sandbox_session,
    enforce_sandbox_resource_limits,
    ensure_relative_sandbox_path,
    sanitize_environment,
)


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
