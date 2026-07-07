#!/usr/bin/env python3
"""Integration checks for assemble-stage Mermaid verification gate."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from kernel.plugin_registry import PluginRegistry
from plugins.assemblers.mermaid_verify_assembler import MermaidVerifyAssembler

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test

PLUGIN_ID = "base.assembler.mermaid_verify"
_SOURCE_PLUGINS = {
    "base.generator.docs",
    "base.generator.diagrams",
    "base.generator.topology_graph",
}


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _ctx(config: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config=dict(config or {}),
    )


def _run_gate(plugin: MermaidVerifyAssembler, ctx: PluginContext):
    return run_plugin_for_test(plugin, ctx, Stage.ASSEMBLE, consumes_keys=set(_SOURCE_PLUGINS))


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


_VALID_DOC = """# Sample

```mermaid
graph TB
    subgraph zone["Zone"]
        node_a["Node A"]
    end
    node_a --> node_b
```
"""

_BROKEN_DOC = """# Broken

```mermaid
graph TB
    subgraph zone["Zone"]
        node_a["{{ unresolved_token }}"]
```

```mermaid
unknownDiagram XX
    a --> b
```
"""


def test_mermaid_verify_passes_on_valid_docs(tmp_path: Path) -> None:
    doc = _write(tmp_path / "docs" / "overview.md", _VALID_DOC)
    diagram = _write(tmp_path / "docs" / "diagrams" / "unified-topology.md", _VALID_DOC)
    plain = _write(tmp_path / "docs" / "notes.md", "# No diagrams here\n")

    ctx = _ctx()
    publish_for_test(ctx, "base.generator.docs", "docs_files", [doc, plain])
    publish_for_test(ctx, "base.generator.topology_graph", "topology_graph_files", [diagram])

    result = _run_gate(MermaidVerifyAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.SUCCESS
    summary = result.output_data["mermaid_verified"]
    assert summary["skipped"] is False
    assert summary["files_scanned"] == 3
    assert summary["blocks_total"] == 2
    assert summary["syntax_errors"] == 0
    assert sorted(summary["sources"]) == [
        "base.generator.docs:docs_files",
        "base.generator.topology_graph:topology_graph_files",
    ]
    assert any(diag.code == "I9861" for diag in result.diagnostics)


def test_mermaid_verify_fails_on_broken_blocks(tmp_path: Path) -> None:
    broken = _write(tmp_path / "docs" / "diagrams" / "network-topology.md", _BROKEN_DOC)

    ctx = _ctx()
    publish_for_test(ctx, "base.generator.diagrams", "diagram_files", [broken])

    result = _run_gate(MermaidVerifyAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.FAILED
    errors = [diag for diag in result.diagnostics if diag.code == "E9861"]
    messages = "\n".join(diag.message for diag in errors)
    assert "unresolved template tokens" in messages
    assert "unmatched subgraph/end" in messages
    assert "unsupported Mermaid header" in messages
    summary = result.output_data["mermaid_verified"]
    assert summary["syntax_errors"] == len(errors) == 3


def test_mermaid_verify_skips_without_published_sources() -> None:
    ctx = _ctx()

    result = _run_gate(MermaidVerifyAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.SUCCESS
    assert any(diag.code == "I9861" and diag.severity == "info" for diag in result.diagnostics)
    summary = result.output_data["mermaid_verified"]
    assert summary["skipped"] is True
    assert summary["files_scanned"] == 0


def test_mermaid_verify_warns_on_missing_files(tmp_path: Path) -> None:
    doc = _write(tmp_path / "docs" / "overview.md", _VALID_DOC)
    missing = str(tmp_path / "docs" / "does-not-exist.md")

    ctx = _ctx()
    publish_for_test(ctx, "base.generator.docs", "docs_files", [doc, missing])

    result = _run_gate(MermaidVerifyAssembler(PLUGIN_ID), ctx)

    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W9861" for diag in result.diagnostics)
    summary = result.output_data["mermaid_verified"]
    assert summary["files_scanned"] == 1
    assert summary["files_missing"] == 1


def test_mermaid_verify_manifest_registration() -> None:
    registry = _registry()

    spec = registry.specs[PLUGIN_ID]
    assert spec.phase == "verify"
    assert spec.order == 419
    assert set(spec.depends_on) == _SOURCE_PLUGINS
    produced = {item["key"] for item in spec.produces if isinstance(item, dict)}
    assert "mermaid_verified" in produced
