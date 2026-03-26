"""Build-stage plugins for release packaging (ADR 0080 Wave G)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kernel.plugin_base import (
    BuilderPlugin,
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


class ReleaseBundleBuilder(BuilderPlugin):
    """Create zip bundle from assembled workspace artifacts."""

    @staticmethod
    def _dist_root(ctx: PluginContext) -> Path:
        if isinstance(ctx.dist_root, str) and ctx.dist_root.strip():
            return Path(ctx.dist_root).resolve()
        raw = ctx.config.get("dist_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw).resolve()
        return Path.cwd() / "dist"

    @staticmethod
    def _workspace_root(ctx: PluginContext) -> Path:
        if isinstance(ctx.workspace_root, str) and ctx.workspace_root.strip():
            return Path(ctx.workspace_root).resolve()
        return Path.cwd() / ".work" / "native"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            assembly_manifest_path = Path(ctx.subscribe("base.assembler.manifest", "assembly_manifest_path"))
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8201",
                    severity="error",
                    stage=stage,
                    message=f"build bundle requires assembly_manifest_path: {exc}",
                    path="plugin:base.assembler.manifest:assembly_manifest_path",
                )
            )
            return self.make_result(diagnostics)

        if not assembly_manifest_path.exists():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8201",
                    severity="error",
                    stage=stage,
                    message=f"assembly manifest does not exist: {assembly_manifest_path}",
                    path=str(assembly_manifest_path),
                )
            )
            return self.make_result(diagnostics)

        try:
            assembly_manifest = json.loads(assembly_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8201",
                    severity="error",
                    stage=stage,
                    message=f"failed to parse assembly manifest: {exc}",
                    path=str(assembly_manifest_path),
                )
            )
            return self.make_result(diagnostics)

        workspace_root = self._workspace_root(ctx)
        dist_root = self._dist_root(ctx)
        dist_root.mkdir(parents=True, exist_ok=True)
        ctx.dist_root = str(dist_root)

        project_id = str(ctx.config.get("project_id", "project")).strip() or "project"
        release_tag = str(ctx.release_tag).strip() if isinstance(ctx.release_tag, str) else ""
        archive_name = f"{project_id}-{release_tag}.zip" if release_tag else f"{project_id}.zip"
        bundle_path = dist_root / archive_name

        files = assembly_manifest.get("files", [])
        if not isinstance(files, list):
            files = []

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for row in files:
                if not isinstance(row, dict):
                    continue
                rel_path = row.get("path")
                if not isinstance(rel_path, str) or not rel_path.strip():
                    continue
                source_path = workspace_root / rel_path
                if not source_path.exists() or not source_path.is_file():
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E8201",
                            severity="error",
                            stage=stage,
                            message=f"assembly file missing while building bundle: {source_path}",
                            path=str(source_path),
                        )
                    )
                    continue
                archive.write(source_path, arcname=Path(rel_path).as_posix())

        bundle_sha256 = _sha256(bundle_path)
        generated_files = [str(bundle_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("release_bundle_path", str(bundle_path))
            ctx.publish("release_bundle_sha256", bundle_sha256)
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8201",
                severity="info",
                stage=stage,
                message=f"release bundle created: {bundle_path.name}",
                path=str(bundle_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "release_bundle_path": str(bundle_path),
                "release_bundle_sha256": bundle_sha256,
                "generated_files": generated_files,
            },
        )

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class SbomBuilder(BuilderPlugin):
    """Emit minimal SBOM JSON from assembly manifest."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            assembly_manifest = ctx.subscribe("base.assembler.manifest", "assembly_manifest")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8202",
                    severity="error",
                    stage=stage,
                    message=f"sbom requires assembly_manifest payload: {exc}",
                    path="plugin:base.assembler.manifest:assembly_manifest",
                )
            )
            return self.make_result(diagnostics)

        if not isinstance(assembly_manifest, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8202",
                    severity="error",
                    stage=stage,
                    message="assembly_manifest payload is not an object.",
                    path="plugin:base.assembler.manifest:assembly_manifest",
                )
            )
            return self.make_result(diagnostics)

        dist_root = (
            Path(ctx.dist_root).resolve() if isinstance(ctx.dist_root, str) and ctx.dist_root else Path.cwd() / "dist"
        )
        sbom_root = (
            Path(ctx.sbom_output_dir).resolve()
            if isinstance(ctx.sbom_output_dir, str) and ctx.sbom_output_dir.strip()
            else dist_root / "sbom"
        )
        sbom_root.mkdir(parents=True, exist_ok=True)
        ctx.sbom_output_dir = str(sbom_root)

        sbom_path = sbom_root / "sbom.json"
        files = assembly_manifest.get("files", [])
        sbom_payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "project_id": str(ctx.config.get("project_id", "")),
            "artifacts": files if isinstance(files, list) else [],
        }
        sbom_path.write_text(json.dumps(sbom_payload, ensure_ascii=True, indent=2), encoding="utf-8")

        generated_files = [str(sbom_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("sbom_path", str(sbom_path))
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8202",
                severity="info",
                stage=stage,
                message=f"sbom generated: {sbom_path.name}",
                path=str(sbom_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"sbom_path": str(sbom_path), "generated_files": generated_files},
        )

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class ReleaseManifestBuilder(BuilderPlugin):
    """Emit release manifest from bundle + SBOM outputs."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            bundle_path = str(ctx.subscribe("base.builder.bundle", "release_bundle_path"))
            bundle_sha256 = str(ctx.subscribe("base.builder.bundle", "release_bundle_sha256"))
            sbom_path = str(ctx.subscribe("base.builder.sbom", "sbom_path"))
            assembly_manifest_path = str(ctx.subscribe("base.assembler.manifest", "assembly_manifest_path"))
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8203",
                    severity="error",
                    stage=stage,
                    message=f"release manifest requires build inputs: {exc}",
                    path="build:release-manifest",
                )
            )
            return self.make_result(diagnostics)

        dist_root = (
            Path(ctx.dist_root).resolve() if isinstance(ctx.dist_root, str) and ctx.dist_root else Path.cwd() / "dist"
        )
        dist_root.mkdir(parents=True, exist_ok=True)
        manifest_path = dist_root / "release-manifest.json"

        payload: dict[str, Any] = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "project_id": str(ctx.config.get("project_id", "")),
            "release_tag": str(ctx.release_tag or ""),
            "signing_backend": str(ctx.signing_backend or "none"),
            "bundle": {
                "path": bundle_path,
                "sha256": bundle_sha256,
                "size_bytes": Path(bundle_path).stat().st_size if Path(bundle_path).exists() else 0,
            },
            "sbom_path": sbom_path,
            "assembly_manifest_path": assembly_manifest_path,
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

        generated_files = [str(manifest_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("release_manifest_path", str(manifest_path))
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8203",
                severity="info",
                stage=stage,
                message=f"release manifest generated: {manifest_path.name}",
                path=str(manifest_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"release_manifest_path": str(manifest_path), "generated_files": generated_files},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
