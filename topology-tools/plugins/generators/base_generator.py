"""Shared utilities for generator plugins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from kernel.plugin_base import GeneratorPlugin, PluginContext, PluginDataExchangeError


class BaseGenerator(GeneratorPlugin):
    """Common helper methods for generator plugins."""

    _template_env: Environment | None = None
    _template_root: Path | None = None

    @staticmethod
    def project_id(ctx: PluginContext) -> str | None:
        value = ctx.config.get("project_id")
        if isinstance(value, str):
            project = value.strip()
            if project:
                return project
        return None

    def artifacts_root(self, ctx: PluginContext) -> Path:
        value = ctx.config.get("generator_artifacts_root")
        if isinstance(value, str) and value.strip():
            root = Path(value)
        elif isinstance(ctx.output_dir, str) and ctx.output_dir:
            root = Path(ctx.output_dir)
        else:
            root = Path.cwd()
        if not root.is_absolute():
            repo_root_raw = ctx.config.get("repo_root")
            if isinstance(repo_root_raw, str) and repo_root_raw.strip():
                root = (Path(repo_root_raw) / root).resolve()
            else:
                root = root.resolve()
        project = self.project_id(ctx)
        if not project:
            return root
        if root.name == project:
            return root
        return root / project

    def resolve_output_path(self, ctx: PluginContext, *parts: str) -> Path:
        return self.artifacts_root(ctx).joinpath(*parts)

    @staticmethod
    def write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.parent / f".{path.name}.tmp"
        tmp_path.write_text(content, encoding=encoding)
        tmp_path.replace(path)

    @staticmethod
    def sort_records(records: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
        return sorted(records, key=lambda item: str(item.get(key, "")))

    def template_root(self, ctx: PluginContext) -> Path:
        raw = ctx.config.get("generator_templates_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw)

        class_modules_root_raw = ctx.config.get("class_modules_root")
        if isinstance(class_modules_root_raw, str) and class_modules_root_raw.strip():
            class_modules_root = Path(class_modules_root_raw.strip())
            candidates = [
                class_modules_root.parent / "topology-tools" / "templates",
                class_modules_root.parent.parent / "topology-tools" / "templates",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate

        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            repo_root = Path(repo_root_raw.strip())
            candidates = [
                repo_root / "topology-tools" / "templates",
                repo_root / "framework" / "topology-tools" / "templates",
                repo_root / "topology-tools" / "templates",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        return Path("topology-tools/templates")

    def object_template_root(self, ctx: PluginContext, *, object_id: str) -> Path:
        """Resolve templates for object-module generators with ADR0078 fallback order."""
        raw = ctx.config.get("generator_templates_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw)

        candidates: list[Path] = []
        object_modules_root_raw = ctx.config.get("object_modules_root")
        if isinstance(object_modules_root_raw, str) and object_modules_root_raw.strip():
            candidates.append(Path(object_modules_root_raw.strip()) / object_id / "templates")
        topology_path_raw = getattr(ctx, "topology_path", None)
        if isinstance(topology_path_raw, str) and topology_path_raw.strip():
            candidates.append(Path(topology_path_raw.strip()).parent / "object-modules" / object_id / "templates")

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return self.template_root(ctx)

    def template_env(self, ctx: PluginContext) -> Environment:
        root = self.template_root(ctx)
        if self._template_env is None or self._template_root != root:
            self._template_root = root
            self._template_env = Environment(
                loader=FileSystemLoader(str(root)),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
                keep_trailing_newline=True,
                undefined=StrictUndefined,
            )
        return self._template_env

    def render_template(self, ctx: PluginContext, template_name: str, context: dict[str, Any]) -> str:
        template = self.template_env(ctx).get_template(template_name)
        return template.render(**context)

    @staticmethod
    def publish_if_possible(ctx: PluginContext, key: str, value: Any) -> bool:
        """Publish generated metadata when plugin executes through registry context.

        Direct unit/integration calls often bypass registry and have no execution
        context; in that case publish is skipped and caller can rely on output_data.
        """
        try:
            ctx.publish(key, value)
            return True
        except PluginDataExchangeError:
            return False
