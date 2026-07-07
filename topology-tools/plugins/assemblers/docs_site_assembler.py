"""Assemble-stage MkDocs site config emitter for generated documentation.

A1 display layer: turns the generated docs tree (docs generator + diagram
generators) into a browsable MkDocs Material site by emitting `mkdocs.yml`
next to the generated `docs/` directory. The site itself is built/served via
`task build:docs-site` / `task build:docs-serve` (A4).

Diagnostic codes:
    E9871 - failed to write mkdocs.yml.
    I9871 - emission summary / graceful skip (docs generator output unavailable).
"""

from __future__ import annotations

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

_FILE_LIST_KEYS: tuple[tuple[str, str], ...] = (
    ("base.generator.docs", "docs_files"),
    ("base.generator.diagrams", "diagram_files"),
    ("base.generator.topology_graph", "topology_graph_files"),
)

_DEFAULT_SITE_NAME = "Topology Documentation"


class DocsSiteAssembler(AssemblerPlugin):
    """Emit mkdocs.yml (Material theme + Mermaid fences + nav) for generated docs."""

    @staticmethod
    def _subscribe_optional(ctx: PluginContext, plugin_id: str, key: str) -> Any:
        try:
            return ctx.subscribe(plugin_id, key)
        except PluginDataExchangeError:
            return None

    @classmethod
    def _collect_relative_pages(cls, ctx: PluginContext, docs_root: Path) -> list[str]:
        """Collect generated .md paths relative to docs_root, sorted, deduplicated."""
        pages: set[str] = set()
        for plugin_id, key in _FILE_LIST_KEYS:
            value = cls._subscribe_optional(ctx, plugin_id, key)
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, str) or not item.strip().endswith(".md"):
                    continue
                try:
                    rel = Path(item.strip()).resolve().relative_to(docs_root)
                except ValueError:
                    continue
                pages.add(rel.as_posix())
        return sorted(pages)

    @staticmethod
    def _page_title(rel_path: str) -> str:
        stem = Path(rel_path).stem
        return stem.replace("-", " ").replace("_", " ").strip().title() or stem

    @classmethod
    def _build_nav_lines(cls, pages: list[str]) -> list[str]:
        """Build deterministic nav: Home, root docs pages, diagram pages."""
        root_pages = [page for page in pages if "/" not in page and page != "index.md"]
        diagram_pages = [page for page in pages if page.startswith("diagrams/")]
        # diagrams/index.md first, remaining sorted
        diagram_pages.sort(key=lambda page: (page != "diagrams/index.md", page))

        lines: list[str] = ["nav:", "  - Home: index.md"]
        if root_pages:
            lines.append("  - Documentation:")
            for page in root_pages:
                lines.append(f"      - {cls._page_title(page)}: {page}")
        if diagram_pages:
            lines.append("  - Diagrams:")
            for page in diagram_pages:
                lines.append(f"      - {cls._page_title(page)}: {page}")
        return lines

    def _mkdocs_config_text(self, site_name: str, pages: list[str]) -> str:
        lines = [
            f"site_name: {site_name}",
            "docs_dir: docs",
            "site_dir: site",
            "use_directory_urls: false",
            "theme:",
            "  name: material",
            "  palette:",
            "    scheme: slate",
            "markdown_extensions:",
            "  - admonition",
            "  - tables",
            "  - pymdownx.superfences:",
            "      custom_fences:",
            "        - name: mermaid",
            "          class: mermaid",
            "          format: !!python/name:pymdownx.superfences.fence_code_format",
        ]
        lines.extend(self._build_nav_lines(pages))
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        site_name = ctx.config.get("site_name", _DEFAULT_SITE_NAME)
        if not isinstance(site_name, str) or not site_name.strip():
            site_name = _DEFAULT_SITE_NAME

        docs_dir_raw = self._subscribe_optional(ctx, "base.generator.docs", "generated_dir")
        if not isinstance(docs_dir_raw, str) or not docs_dir_raw.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9871",
                    severity="info",
                    stage=stage,
                    message="docs generator output unavailable; mkdocs site config skipped.",
                    path="pipeline:assemble",
                )
            )
            ctx.publish("docs_site_config", "")
            return self.make_result(diagnostics=diagnostics, output_data={"docs_site_config": ""})

        docs_root = Path(docs_dir_raw.strip()).resolve()
        site_root = docs_root.parent
        config_path = site_root / "mkdocs.yml"
        pages = self._collect_relative_pages(ctx, docs_root)

        try:
            self._write_text_atomic(config_path, self._mkdocs_config_text(site_name.strip(), pages))
        except OSError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9871",
                    severity="error",
                    stage=stage,
                    message=f"failed to write mkdocs site config: {exc}",
                    path=str(config_path),
                )
            )
            return self.make_result(diagnostics=diagnostics)

        diagnostics.append(
            self.emit_diagnostic(
                code="I9871",
                severity="info",
                stage=stage,
                message=(f"mkdocs site config emitted: pages={len(pages)} site_name='{site_name.strip()}'"),
                path=str(config_path),
            )
        )
        ctx.publish("docs_site_config", str(config_path))
        ctx.publish("docs_site_dir", str(site_root))
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "docs_site_config": str(config_path),
                "docs_site_dir": str(site_root),
                "nav_pages": len(pages),
            },
        )

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
