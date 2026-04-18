"""Generator plugin that emits consolidated artifact manifest (ADR 0080 Wave E.1)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator


class ArtifactManifestGenerator(BaseGenerator):
    """Collect generated artifacts from publish bus and emit deterministic manifest."""

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _repo_relative(path: Path, repo_root: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        repo_root_raw = ctx.config.get("repo_root")
        repo_root = (
            Path(str(repo_root_raw)).resolve() if isinstance(repo_root_raw, str) and repo_root_raw else Path.cwd()
        )
        artifacts_root = self.artifacts_root(ctx)
        artifacts_root.mkdir(parents=True, exist_ok=True)

        published = ctx.get_published_data()
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for plugin_id in self._producer_ids(ctx, published):
            payload = published.get(plugin_id)
            if not isinstance(payload, dict):
                continue
            generated_files = payload.get("generated_files")
            if not isinstance(generated_files, list):
                continue
            for item in generated_files:
                if not isinstance(item, str) or not item.strip():
                    continue
                artifact_path = Path(item.strip())
                if not artifact_path.is_absolute():
                    artifact_path = (repo_root / artifact_path).resolve()
                key = (plugin_id, artifact_path.as_posix())
                if key in seen:
                    continue
                seen.add(key)

                if not artifact_path.exists() or not artifact_path.is_file():
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3901",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Plugin '{plugin_id}' published generated file that does not exist: "
                                f"{artifact_path}"
                            ),
                            path=f"plugin:{plugin_id}:generated_files",
                        )
                    )
                    continue

                rows.append(
                    {
                        "producer_plugin": plugin_id,
                        "path": self._repo_relative(artifact_path, repo_root),
                        "sha256": self._sha256(artifact_path),
                        "size_bytes": artifact_path.stat().st_size,
                    }
                )

        rows.sort(key=lambda row: (str(row["path"]), str(row["producer_plugin"])))
        manifest = {
            "schema_version": 1,
            "project_id": self.project_id(ctx) or "",
            "generated_at": str(ctx.config.get("compile_generated_at", "")),
            "artifact_count": len(rows),
            "artifacts": rows,
        }

        manifest_path = artifacts_root / "artifact-manifest.json"
        self.write_text_atomic(
            manifest_path,
            json.dumps(manifest, ensure_ascii=True, indent=2),
        )

        generated_files = [str(manifest_path)]
        ctx.publish("generated_files", generated_files)
        ctx.publish("artifact_manifest_path", str(manifest_path))
        ctx.publish("artifact_manifest", manifest)

        diagnostics.append(
            self.emit_diagnostic(
                code="I3901",
                severity="info",
                stage=stage,
                message=f"generated artifact manifest with {len(rows)} entries",
                path=str(manifest_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "artifact_manifest_path": str(manifest_path),
                "generated_files": generated_files,
                "artifact_count": len(rows),
            },
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    @staticmethod
    def _producer_ids(ctx: PluginContext, published: dict[str, dict[str, Any]]) -> list[str]:
        raw = ctx.config.get("artifact_manifest_producers")
        if not isinstance(raw, list):
            return sorted(published.keys())
        return sorted({item.strip() for item in raw if isinstance(item, str) and item.strip()})
