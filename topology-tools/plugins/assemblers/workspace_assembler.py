"""Assemble-stage plugins for workspace materialization (ADR 0080 Wave F)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kernel.plugin_base import (
    AssemblerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH) PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
)
_SECRET_ASSIGNMENT_RE = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*(.+)")
_PLACEHOLDER_RE = re.compile(r"^<TODO_[A-Z0-9_]+>$")


def _is_safe_secret_reference(raw_value: str) -> bool:
    value = raw_value.strip().strip("\"'").strip()
    if not value:
        return True
    if _PLACEHOLDER_RE.fullmatch(value) is not None:
        return True

    lowered = value.lower()
    if lowered in {"example", "placeholder", "changeme", "null", "none"}:
        return True

    if value.startswith("var.") or value.startswith("local.") or value.startswith("env."):
        return True
    if value.startswith("${") and value.endswith("}"):
        return True
    if value.startswith("{{") and value.endswith("}}"):
        return True
    return False


def _has_unencrypted_secret_assignment(text_payload: str) -> bool:
    for raw_line in text_payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//") or line.startswith(";"):
            continue
        match = _SECRET_ASSIGNMENT_RE.search(line)
        if match is None:
            continue
        rhs = match.group(2).strip()
        if _is_safe_secret_reference(rhs):
            continue
        return True
    return False


class WorkspaceAssembler(AssemblerPlugin):
    """Copy generated artifacts into workspace root for downstream packaging."""

    @staticmethod
    def _repo_root(ctx: PluginContext) -> Path:
        repo_root = ctx.config.get("repo_root")
        if isinstance(repo_root, str) and repo_root.strip():
            return Path(repo_root).resolve()
        return Path.cwd()

    @staticmethod
    def _workspace_root(ctx: PluginContext) -> Path:
        if isinstance(ctx.workspace_root, str) and ctx.workspace_root.strip():
            candidate = Path(ctx.workspace_root)
            if candidate.is_absolute():
                return candidate.resolve()
            repo_root = WorkspaceAssembler._repo_root(ctx)
            return (repo_root / candidate).resolve()
        raw = ctx.config.get("workspace_root")
        if isinstance(raw, str) and raw.strip():
            candidate = Path(raw)
            if candidate.is_absolute():
                return candidate.resolve()
            repo_root = WorkspaceAssembler._repo_root(ctx)
            return (repo_root / candidate).resolve()
        return Path.cwd() / ".work" / "native"

    @staticmethod
    def _project_id(ctx: PluginContext) -> str:
        value = ctx.config.get("project_id")
        return value.strip() if isinstance(value, str) and value.strip() else "default"

    @staticmethod
    def _dest_relative(source_repo_rel: str, project_id: str) -> str:
        parts = [part for part in Path(source_repo_rel).parts if part]
        if len(parts) >= 2 and parts[0] == "generated" and parts[1] == project_id:
            return Path(*parts[2:]).as_posix()
        if len(parts) >= 1 and parts[0] == "generated":
            return Path(*parts[1:]).as_posix()
        return Path(source_repo_rel).as_posix()

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        repo_root = self._repo_root(ctx)
        workspace_root = self._workspace_root(ctx)
        workspace_root.mkdir(parents=True, exist_ok=True)
        project_id = self._project_id(ctx)

        try:
            artifact_manifest_path = Path(ctx.subscribe("base.generator.artifact_manifest", "artifact_manifest_path"))
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8101",
                    severity="error",
                    stage=stage,
                    message=f"artifact manifest is required for assemble stage: {exc}",
                    path="plugin:base.generator.artifact_manifest:artifact_manifest_path",
                )
            )
            return self.make_result(diagnostics)

        if not artifact_manifest_path.exists():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8101",
                    severity="error",
                    stage=stage,
                    message=f"artifact manifest file does not exist: {artifact_manifest_path}",
                    path=str(artifact_manifest_path),
                )
            )
            return self.make_result(diagnostics)

        try:
            artifact_manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8101",
                    severity="error",
                    stage=stage,
                    message=f"failed to parse artifact manifest: {exc}",
                    path=str(artifact_manifest_path),
                )
            )
            return self.make_result(diagnostics)

        artifacts = artifact_manifest.get("artifacts", [])
        if not isinstance(artifacts, list):
            artifacts = []

        assembled_files: list[str] = []
        for row in artifacts:
            if not isinstance(row, dict):
                continue
            source_rel = row.get("path")
            if not isinstance(source_rel, str) or not source_rel.strip():
                continue
            source_path = (repo_root / source_rel).resolve()
            if not source_path.exists() or not source_path.is_file():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8101",
                        severity="error",
                        stage=stage,
                        message=f"artifact listed in manifest does not exist: {source_path}",
                        path=str(source_path),
                    )
                )
                continue
            dest_rel = self._dest_relative(source_rel, project_id)
            dest_path = (workspace_root / dest_rel).resolve()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            assembled_files.append(str(dest_path))

        assembled_files.sort()
        ctx.workspace_root = str(workspace_root)
        try:
            ctx.publish("assembly_dir", str(workspace_root))
            ctx.publish("assembled_files", assembled_files)
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8101",
                severity="info",
                stage=stage,
                message=f"assembled workspace files: {len(assembled_files)}",
                path=str(workspace_root),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"workspace_root": str(workspace_root), "assembled_files": assembled_files},
        )

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class AssemblyVerifyAssembler(AssemblerPlugin):
    """Verify assembled files and apply simple secret-leak guard."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            assembled_files = ctx.subscribe("base.assembler.workspace", "assembled_files")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8102",
                    severity="error",
                    stage=stage,
                    message=f"assemble verification requires assembled_files: {exc}",
                    path="plugin:base.assembler.workspace:assembled_files",
                )
            )
            return self.make_result(diagnostics)

        file_list = assembled_files if isinstance(assembled_files, list) else []
        missing = [item for item in file_list if isinstance(item, str) and not Path(item).exists()]
        for missing_path in missing:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8102",
                    severity="error",
                    stage=stage,
                    message=f"assembled file is missing: {missing_path}",
                    path=missing_path,
                )
            )

        for item in file_list:
            if not isinstance(item, str):
                continue
            normalized = item.replace("\\", "/").lower()
            if "/secrets/" in normalized or normalized.endswith(".env"):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8103",
                        severity="error",
                        stage=stage,
                        message=f"secret-looking file leaked into assembled workspace: {item}",
                        path=item,
                    )
                )

            file_path = Path(item)
            if not file_path.exists() or not file_path.is_file():
                continue
            text_payload: str | None = None
            try:
                text_payload = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                text_payload = None
            if not text_payload:
                continue
            for label, pattern in _SECRET_PATTERNS:
                if pattern.search(text_payload) is None:
                    continue
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8103",
                        severity="error",
                        stage=stage,
                        message=f"secret-looking content detected ({label}) in assembled file: {item}",
                        path=item,
                    )
                )
                break
            else:
                if not _has_unencrypted_secret_assignment(text_payload):
                    continue
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8103",
                        severity="error",
                        stage=stage,
                        message=f"secret-looking content detected (secret_assignment) in assembled file: {item}",
                        path=item,
                    )
                )

        try:
            ctx.publish("assemble_verified", len([d for d in diagnostics if d.severity == "error"]) == 0)
        except PluginDataExchangeError:
            pass
        diagnostics.append(
            self.emit_diagnostic(
                code="I8102",
                severity="info",
                stage=stage,
                message=f"assemble verification completed for {len(file_list)} files",
                path="assemble:verify",
            )
        )
        return self.make_result(diagnostics=diagnostics)

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class AssemblyManifestAssembler(AssemblerPlugin):
    """Emit assembly manifest consumed by build stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        workspace_root = (
            Path(ctx.workspace_root).resolve()
            if isinstance(ctx.workspace_root, str) and ctx.workspace_root.strip()
            else Path.cwd() / ".work" / "native"
        )
        workspace_root.mkdir(parents=True, exist_ok=True)

        try:
            assembled_files = ctx.subscribe("base.assembler.workspace", "assembled_files")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8104",
                    severity="error",
                    stage=stage,
                    message=f"assemble manifest requires assembled_files: {exc}",
                    path="plugin:base.assembler.workspace:assembled_files",
                )
            )
            return self.make_result(diagnostics)

        try:
            artifact_manifest_path = str(ctx.subscribe("base.generator.artifact_manifest", "artifact_manifest_path"))
        except PluginDataExchangeError:
            artifact_manifest_path = ""

        rows: list[dict[str, Any]] = []
        for item in assembled_files if isinstance(assembled_files, list) else []:
            if not isinstance(item, str):
                continue
            path = Path(item)
            if not path.exists() or not path.is_file():
                continue
            try:
                rel = path.resolve().relative_to(workspace_root.resolve()).as_posix()
            except ValueError:
                rel = path.resolve().as_posix()
            rows.append(
                {
                    "path": rel,
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
        rows.sort(key=lambda row: str(row["path"]))

        manifest = {
            "schema_version": 1,
            "project_id": str(ctx.config.get("project_id", "")),
            "assembled_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "workspace_root": str(workspace_root),
            "source_artifact_manifest_path": artifact_manifest_path,
            "files": rows,
        }
        manifest_path = workspace_root / "assembly-manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")

        ctx.assembly_manifest = manifest
        try:
            ctx.publish("generated_files", [str(manifest_path)])
            ctx.publish("assembly_manifest_path", str(manifest_path))
            ctx.publish("assembly_manifest", manifest)
        except PluginDataExchangeError:
            pass
        diagnostics.append(
            self.emit_diagnostic(
                code="I8103",
                severity="info",
                stage=stage,
                message=f"assembly manifest generated with {len(rows)} entries",
                path=str(manifest_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"assembly_manifest_path": str(manifest_path), "files": rows},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
