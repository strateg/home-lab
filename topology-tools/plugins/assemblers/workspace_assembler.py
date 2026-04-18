"""Assemble-stage plugins for workspace materialization (ADR 0080 Wave F)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
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


class ChangedInputScopesAssembler(AssemblerPlugin):
    """Compute dirty input scopes from artifact-manifest checksum deltas."""

    _STATE_FILE_NAME = ".changed-input-scopes.json"

    @staticmethod
    def _normalize_artifact_path(raw_path: str, project_id: str) -> str:
        normalized = raw_path.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part and part != "."]
        if len(parts) >= 2 and parts[0] == "generated" and parts[1] == project_id:
            parts = parts[2:]
        elif parts and parts[0] == "generated":
            parts = parts[1:]
        if parts:
            return "/".join(parts)
        tail = Path(normalized).name
        return tail if tail else normalized

    @staticmethod
    def _entry_signature(row: dict[str, Any], project_id: str) -> tuple[str, dict[str, str]] | None:
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        rel_path = ChangedInputScopesAssembler._normalize_artifact_path(raw_path.strip(), project_id)
        producer = row.get("producer_plugin")
        sha256 = row.get("sha256")
        return (
            rel_path,
            {
                "producer_plugin": producer.strip() if isinstance(producer, str) else "",
                "sha256": sha256.strip() if isinstance(sha256, str) else "",
            },
        )

    @staticmethod
    def _extract_entries(payload: dict[str, Any], project_id: str) -> dict[str, dict[str, str]]:
        rows = payload.get("artifacts")
        if not isinstance(rows, list):
            return {}
        entries: dict[str, dict[str, str]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            signature = ChangedInputScopesAssembler._entry_signature(row, project_id)
            if signature is None:
                continue
            rel_path, item = signature
            entries[rel_path] = item
        return entries

    @staticmethod
    def _manifest_path(ctx: PluginContext) -> Path | None:
        try:
            raw_value = ctx.subscribe("base.generator.artifact_manifest", "artifact_manifest_path")
        except PluginDataExchangeError:
            return None
        if not isinstance(raw_value, str) or not raw_value.strip():
            return None
        return Path(raw_value)

    @staticmethod
    def _manifest_payload(ctx: PluginContext) -> dict[str, Any] | None:
        try:
            payload = ctx.subscribe("base.generator.artifact_manifest", "artifact_manifest")
        except PluginDataExchangeError:
            payload = None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _repo_root(ctx: PluginContext) -> Path:
        return WorkspaceAssembler._repo_root(ctx)

    @staticmethod
    def _workspace_root(ctx: PluginContext) -> Path:
        return WorkspaceAssembler._workspace_root(ctx)

    @staticmethod
    def _project_id(ctx: PluginContext) -> str:
        return WorkspaceAssembler._project_id(ctx)

    @classmethod
    def _state_path(cls, ctx: PluginContext) -> Path:
        return cls._workspace_root(ctx) / cls._STATE_FILE_NAME

    @staticmethod
    def _read_previous_entries(state_path: Path) -> dict[str, dict[str, str]] | None:
        if not state_path.exists():
            return None
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return None
        normalized: dict[str, dict[str, str]] = {}
        for rel_path, row in entries.items():
            if not isinstance(rel_path, str) or not isinstance(row, dict):
                continue
            producer = row.get("producer_plugin")
            sha256 = row.get("sha256")
            normalized[rel_path] = {
                "producer_plugin": producer if isinstance(producer, str) else "",
                "sha256": sha256 if isinstance(sha256, str) else "",
            }
        return normalized

    @staticmethod
    def _derive_dirty_scopes(
        previous: dict[str, dict[str, str]] | None,
        current: dict[str, dict[str, str]],
    ) -> tuple[list[str], int]:
        changed_paths: list[str] = []
        all_paths = sorted(set(current.keys()) | set((previous or {}).keys()))
        for rel_path in all_paths:
            old = (previous or {}).get(rel_path)
            new = current.get(rel_path)
            if old != new:
                changed_paths.append(rel_path)

        scopes: set[str] = set()
        if previous is None and current:
            scopes.add("all")
        for rel_path in changed_paths:
            scopes.add("generated")
            head = rel_path.split("/", 1)[0]
            scopes.add(head if head else "root")
            old = (previous or {}).get(rel_path, {})
            new = current.get(rel_path, {})
            for row in (old, new):
                plugin_id = row.get("producer_plugin")
                if isinstance(plugin_id, str) and plugin_id:
                    scopes.add(f"plugin:{plugin_id}")
        return sorted(scopes), len(changed_paths)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        project_id = self._project_id(ctx)
        workspace_root = self._workspace_root(ctx)
        workspace_root.mkdir(parents=True, exist_ok=True)
        state_path = self._state_path(ctx)

        payload = self._manifest_payload(ctx)
        if payload is None:
            manifest_path = self._manifest_path(ctx)
            if manifest_path is not None and not manifest_path.is_absolute():
                manifest_path = (self._repo_root(ctx) / manifest_path).resolve()
            payload = self._read_manifest(manifest_path) if manifest_path is not None else None

        if payload is None:
            ctx.changed_input_scopes = None
            diagnostics.append(
                self.emit_diagnostic(
                    code="I8104",
                    severity="info",
                    stage=stage,
                    message="changed_input_scopes unavailable: artifact manifest is not readable yet.",
                    path=str(state_path),
                )
            )
            return self.make_result(diagnostics=diagnostics, output_data={"changed_input_scopes": None})

        current_entries = self._extract_entries(payload, project_id)
        previous_entries = self._read_previous_entries(state_path)
        dirty_scopes, changed_files = self._derive_dirty_scopes(previous_entries, current_entries)
        ctx.changed_input_scopes = dirty_scopes
        ctx.config["changed_input_scopes"] = dirty_scopes
        ctx.publish("changed_input_scopes", dirty_scopes)

        snapshot_payload = {
            "schema_version": 1,
            "project_id": project_id,
            "entries": current_entries,
        }
        try:
            state_path.write_text(json.dumps(snapshot_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I8104",
                    severity="info",
                    stage=stage,
                    message=f"changed_input_scopes computed but could not persist snapshot: {state_path}",
                    path=str(state_path),
                )
            )

        diagnostics.append(
            self.emit_diagnostic(
                code="I8104",
                severity="info",
                stage=stage,
                message=f"changed_input_scopes resolved: scopes={len(dirty_scopes)} changed_files={changed_files}",
                path=str(state_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"changed_input_scopes": dirty_scopes, "changed_files": changed_files},
        )

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


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
        ctx.publish("assembly_dir", str(workspace_root))
        ctx.publish("assembled_files", assembled_files)

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

        ctx.publish("assemble_verified", len([d for d in diagnostics if d.severity == "error"]) == 0)
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
        ctx.publish("generated_files", [str(manifest_path)])
        ctx.publish("assembly_manifest_path", str(manifest_path))
        ctx.publish("assembly_manifest", manifest)
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


class DeployBundleAssembler(AssemblerPlugin):
    """Assemble deploy bundle from generated artifacts for deploy-plane consumers."""

    @staticmethod
    def _repo_root(ctx: PluginContext) -> Path:
        return WorkspaceAssembler._repo_root(ctx)

    @staticmethod
    def _project_id(ctx: PluginContext) -> str:
        return WorkspaceAssembler._project_id(ctx)

    @classmethod
    def _generated_root(cls, ctx: PluginContext) -> Path:
        repo_root = cls._repo_root(ctx)
        project_id = cls._project_id(ctx)
        raw_root = ctx.config.get("generator_artifacts_root")
        if isinstance(raw_root, str) and raw_root.strip():
            candidate = Path(raw_root.strip())
            if not candidate.is_absolute():
                candidate = (repo_root / candidate).resolve()
            else:
                candidate = candidate.resolve()
        else:
            candidate = (repo_root / "generated").resolve()

        if candidate.name == project_id:
            return candidate
        return (candidate / project_id).resolve()

    @classmethod
    def _bundles_root(cls, ctx: PluginContext) -> Path:
        repo_root = cls._repo_root(ctx)
        raw_root = str(ctx.config.get("deploy_bundles_root", "")).strip()
        if raw_root:
            candidate = Path(raw_root)
            if candidate.is_absolute():
                return candidate.resolve()
            return (repo_root / candidate).resolve()
        return (repo_root / ".work" / "deploy" / "bundles").resolve()

    @classmethod
    def _load_bundle_module(cls, ctx: PluginContext):
        repo_root = cls._repo_root(ctx)
        framework_root = Path(__file__).resolve().parents[3]
        candidates = [
            (repo_root / "scripts" / "orchestration" / "deploy" / "bundle.py").resolve(),
            (framework_root / "scripts" / "orchestration" / "deploy" / "bundle.py").resolve(),
        ]
        module_path = next((path for path in candidates if path.exists()), None)
        if module_path is None:
            raise FileNotFoundError(
                "deploy bundle module not found in workspace or framework roots: "
                f"{', '.join(str(path) for path in candidates)}"
            )
        spec = importlib.util.spec_from_file_location("_deploy_bundle_module", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load deploy bundle module spec: {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        project_id = self._project_id(ctx)
        generated_root = self._generated_root(ctx)
        bundles_root = self._bundles_root(ctx)
        try:
            assemble_verified = ctx.subscribe("base.assembler.verify", "assemble_verified")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8105",
                    severity="error",
                    stage=stage,
                    message=f"deploy bundle assembly requires assemble_verified flag: {exc}",
                    path="plugin:base.assembler.verify:assemble_verified",
                )
            )
            return self.make_result(diagnostics=diagnostics)
        if assemble_verified is False:
            return PluginResult.skipped(
                self.plugin_id,
                api_version=self.api_version,
                reason="assemble verification failed",
            )

        if not generated_root.exists() or not generated_root.is_dir():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8105",
                    severity="error",
                    stage=stage,
                    message=f"deploy bundle assembly requires generated root: {generated_root}",
                    path=str(generated_root),
                )
            )
            return self.make_result(diagnostics=diagnostics)

        try:
            bundle_module = self._load_bundle_module(ctx)
            topology_hash = str(bundle_module.hash_tree(generated_root))
            secrets_hash = str(bundle_module.hash_mapping({}))
            bundle_id = str(
                bundle_module.compute_bundle_id(
                    project_id=project_id,
                    topology_hash=topology_hash,
                    secrets_hash=secrets_hash,
                )
            )
            bundle_path = (bundles_root / bundle_id).resolve()

            if bundle_path.exists():
                reused = True
            else:
                bundles_root.mkdir(parents=True, exist_ok=True)
                info = bundle_module.create_bundle(
                    project_id=project_id,
                    generated_root=generated_root,
                    bundles_root=bundles_root,
                    inject_secrets=False,
                    secrets_root=None,
                )
                bundle_id = str(info.bundle_id)
                bundle_path = Path(info.bundle_path).resolve()
                reused = False

            ctx.publish("deploy_bundle_id", bundle_id)
            ctx.publish("deploy_bundle_path", str(bundle_path))
            ctx.publish("deploy_bundle_reused", reused)

            action = "reused" if reused else "created"
            diagnostics.append(
                self.emit_diagnostic(
                    code="I8105",
                    severity="info",
                    stage=stage,
                    message=f"deploy bundle {action}: {bundle_id}",
                    path=str(bundle_path),
                )
            )
            return self.make_result(
                diagnostics=diagnostics,
                output_data={
                    "deploy_bundle_id": bundle_id,
                    "deploy_bundle_path": str(bundle_path),
                    "deploy_bundle_reused": reused,
                },
            )
        except Exception as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8105",
                    severity="error",
                    stage=stage,
                    message=f"deploy bundle assembly failed: {exc}",
                    path=str(bundles_root),
                )
            )
            return self.make_result(diagnostics=diagnostics)

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
