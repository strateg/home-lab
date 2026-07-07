"""Assemble-stage Mermaid verification gate for generated documentation.

ADR 0079 amendment: the originally planned validate-stage Mermaid validator
cannot observe generator output (validate precedes generate in the ADR 0080
stage order), so the render gate runs as an assemble/verify assembler after
the docs/diagram/topology-graph generators have published their file lists.

Diagnostic codes:
    E9861 - Mermaid block syntax problem (empty block, unsupported header,
            unresolved template tokens, unbalanced subgraph/end).
    E9862 - Mermaid CLI (mmdc) render failure (only with use_mmdc=true).
    W9861 - guard degraded (published markdown files missing on disk).
    I9861 - verification summary / graceful skip (no published sources).
"""

from __future__ import annotations

import re
import subprocess
import tempfile
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

_MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_MERMAID_HEADER_PREFIXES = (
    "graph ",
    "flowchart ",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "journey",
    "gantt",
    "pie ",
    "mindmap",
    "timeline",
    "gitGraph",
)

# Published markdown file lists emitted by the docs-plane generators.
_SOURCE_KEYS: tuple[tuple[str, str], ...] = (
    ("base.generator.docs", "docs_files"),
    ("base.generator.diagrams", "diagram_files"),
    ("base.generator.topology_graph", "topology_graph_files"),
)


class MermaidVerifyAssembler(AssemblerPlugin):
    """Verify Mermaid blocks in generated markdown before assemble finalize."""

    @staticmethod
    def _collect_markdown_files(ctx: PluginContext) -> tuple[list[str], list[str]]:
        """Gather unique .md paths from published generator file lists."""
        paths: set[str] = set()
        sources_seen: list[str] = []
        for plugin_id, key in _SOURCE_KEYS:
            try:
                value = ctx.subscribe(plugin_id, key)
            except PluginDataExchangeError:
                continue
            if not isinstance(value, list):
                continue
            sources_seen.append(f"{plugin_id}:{key}")
            for item in value:
                if isinstance(item, str) and item.strip().endswith(".md"):
                    paths.add(item.strip())
        return sorted(paths), sources_seen

    @staticmethod
    def _extract_mermaid_blocks(content: str) -> list[str]:
        return [match.group(1).strip() for match in _MERMAID_BLOCK_RE.finditer(content)]

    @staticmethod
    def _block_syntax_issues(block: str, *, rel_path: str, block_index: int) -> list[str]:
        """Return human-readable issue messages for a single Mermaid block."""
        issues: list[str] = []
        if not block:
            return [f"{rel_path}: block #{block_index} is empty"]
        first_line = block.splitlines()[0].strip()
        if not any(first_line.startswith(prefix) for prefix in _MERMAID_HEADER_PREFIXES):
            issues.append(f"{rel_path}: block #{block_index} has unsupported Mermaid header '{first_line}'")
        if "{{" in block or "{%" in block:
            issues.append(f"{rel_path}: block #{block_index} contains unresolved template tokens")
        subgraph_count = len(re.findall(r"^\s*subgraph\b", block, flags=re.MULTILINE))
        end_count = len(re.findall(r"^\s*end\s*$", block, flags=re.MULTILINE))
        if end_count < subgraph_count:
            issues.append(
                f"{rel_path}: block #{block_index} has unmatched subgraph/end sections "
                f"({subgraph_count}/{end_count})"
            )
        return issues

    @staticmethod
    def _block_mmdc_issue(block: str, *, rel_path: str, block_index: int) -> str | None:
        with tempfile.TemporaryDirectory(prefix="mermaid-verify-") as temp_dir:
            temp_root = Path(temp_dir)
            source = temp_root / "diagram.mmd"
            target = temp_root / "diagram.svg"
            source.write_text(block, encoding="utf-8")
            try:
                proc = subprocess.run(
                    ["mmdc", "-i", str(source), "-o", str(target)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                return f"{rel_path}: block #{block_index}: mmdc executable not found"
            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                message = stderr.splitlines()[-1] if stderr else "mmdc validation failed"
                return f"{rel_path}: block #{block_index}: {message}"
        return None

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        use_mmdc = ctx.config.get("use_mmdc", False)
        if not isinstance(use_mmdc, bool):
            use_mmdc = False

        markdown_files, sources_seen = self._collect_markdown_files(ctx)
        if not sources_seen:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9861",
                    severity="info",
                    stage=stage,
                    message=("no docs-plane generator file lists published; mermaid verification gate skipped."),
                    path="pipeline:assemble",
                )
            )
            summary = {
                "sources": [],
                "files_scanned": 0,
                "files_missing": 0,
                "blocks_total": 0,
                "syntax_errors": 0,
                "render_errors": 0,
                "use_mmdc": use_mmdc,
                "skipped": True,
            }
            ctx.publish("mermaid_verified", summary)
            return self.make_result(diagnostics=diagnostics, output_data={"mermaid_verified": summary})

        files_scanned = 0
        files_missing: list[str] = []
        blocks_total = 0
        syntax_errors = 0
        render_errors = 0

        for file_path in markdown_files:
            path = Path(file_path)
            if not path.is_file():
                files_missing.append(file_path)
                continue
            files_scanned += 1
            rel_path = path.name
            blocks = self._extract_mermaid_blocks(path.read_text(encoding="utf-8"))
            blocks_total += len(blocks)
            for idx, block in enumerate(blocks, start=1):
                for issue in self._block_syntax_issues(block, rel_path=rel_path, block_index=idx):
                    syntax_errors += 1
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E9861",
                            severity="error",
                            stage=stage,
                            message=f"mermaid syntax check failed: {issue}",
                            path=file_path,
                        )
                    )
                if use_mmdc:
                    mmdc_issue = self._block_mmdc_issue(block, rel_path=rel_path, block_index=idx)
                    if mmdc_issue:
                        render_errors += 1
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E9862",
                                severity="error",
                                stage=stage,
                                message=f"mermaid render check failed: {mmdc_issue}",
                                path=file_path,
                            )
                        )

        if files_missing:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9861",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"{len(files_missing)} published markdown files missing on disk; " "verified remaining files."
                    ),
                    path=files_missing[0],
                )
            )

        summary: dict[str, Any] = {
            "sources": sources_seen,
            "files_scanned": files_scanned,
            "files_missing": len(files_missing),
            "blocks_total": blocks_total,
            "syntax_errors": syntax_errors,
            "render_errors": render_errors,
            "use_mmdc": use_mmdc,
            "skipped": False,
        }
        diagnostics.append(
            self.emit_diagnostic(
                code="I9861",
                severity="info",
                stage=stage,
                message=(
                    "mermaid verification summary: "
                    f"sources={len(sources_seen)} files={files_scanned} "
                    f"blocks={blocks_total} syntax_errors={syntax_errors} "
                    f"render_errors={render_errors} mmdc={'on' if use_mmdc else 'off'}"
                ),
                path="pipeline:assemble",
            )
        )
        ctx.publish("mermaid_verified", summary)
        return self.make_result(diagnostics=diagnostics, output_data={"mermaid_verified": summary})

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
